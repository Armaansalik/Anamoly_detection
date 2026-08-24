"""SentinelAgent - FastAPI entry point (Layers 3, 4, 8 wiring).

Run:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Annotated

from backend import explanations
from backend.actions_executor import ActionExecutor
from backend.agent import ReasoningAgent
from backend.auth import (
    authenticate_request,
    create_token,
    verify_password,
    DEFAULT_USERS,
)
from backend.detection import AnomalyPipeline
from backend.hub import StreamingHub
from backend.storage import SQLiteStore
from core.config import get_settings
from core.logging import get_logger, setup_logging
from core.plugin_loader import PluginRegistry

from backend.mqtt_ingestor import MQTTIngestor

settings = get_settings()
log = get_logger("sentinel.api")

registry: PluginRegistry
store: SQLiteStore
hub: StreamingHub
pipeline: AnomalyPipeline
agent: ReasoningAgent
executor: ActionExecutor
mqtt_ingestor: Optional[MQTTIngestor] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global registry, store, hub, pipeline, agent, executor, mqtt_ingestor
    setup_logging(settings.log_level)
    registry = PluginRegistry().load()
    store = SQLiteStore(settings.db_path)
    hub = StreamingHub(settings)
    agent = ReasoningAgent(store, registry, settings)
    executor = ActionExecutor(store, hub, registry)
    pipeline = AnomalyPipeline(store, hub, registry, settings)
    mqtt_ingestor = MQTTIngestor(settings, registry, pipeline, store)
    mqtt_ingestor.start()
    log.info("SentinelAgent started", extra={"plugins": list(registry.plugins), "db": str(settings.db_path), "mqtt": settings.mqtt_enabled})
    yield
    if mqtt_ingestor:
        mqtt_ingestor.stop()
    yield


app = FastAPI(
    title="SentinelAgent",
    version="1.0.0",
    description="Autonomous Anomaly Detection & Self-Healing Agent Platform for MSME Factories",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    return await call_next(request)


# ------------------------------------------------------------------ models
class RawEventIn(BaseModel):
    domain: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    payload: Dict[str, Any]


class BatchIn(BaseModel):
    events: List[RawEventIn]


class ApproveIn(BaseModel):
    approve: bool = True
    approver: str = "operator"


class ActorIn(BaseModel):
    actor: str = "operator"


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1)
    source_id: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    user: str
    role: str
    display_name: str


async def require_auth(authorization: Optional[str] = Header(None)):
    user = authenticate_request(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized — valid Bearer token required")
    return user


# ------------------------------------------------------------------ health
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "plugins": list(registry.plugins)}


@app.post("/api/v1/auth/login", response_model=LoginOut)
async def login(body: LoginIn) -> LoginOut:
    user = DEFAULT_USERS.get(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token({"sub": body.username, "role": user["role"]})
    return LoginOut(token=token, user=body.username, role=user["role"], display_name=user["display_name"])


@app.get("/api/v1/plugins")
async def list_plugins() -> Dict[str, Any]:
    return {"plugins": [p.to_dict() for p in registry.plugins.values()]}


# -------------------------------------------------------------- ingestion
@app.post("/api/v1/events")
async def ingest(raw: RawEventIn) -> Dict[str, Any]:
    events = registry.adapt(raw.domain, raw.payload, raw.source_id)
    event_ids: List[str] = []
    for ev in events:
        event_id = store.insert_event(ev)
        event_ids.append(event_id)
        await pipeline.process(ev, executor=executor, agent=agent)
        await hub.publish("event", event=ev.model_dump(mode="json"))
    return {"accepted": len(event_ids), "event_ids": event_ids}


@app.post("/api/v1/events/batch")
async def ingest_batch(batch: BatchIn) -> Dict[str, Any]:
    total = 0
    for raw in batch.events:
        result = await ingest(raw)
        total += result["accepted"]
    return {"accepted": total}


# ---------------------------------------------------------------- sources
@app.get("/api/v1/sources")
async def sources() -> Dict[str, Any]:
    return {"sources": pipeline.sources_status()}


# -------------------------------------------------------------- incidents
@app.get("/api/v1/incidents")
async def incidents(limit: int = 100) -> Dict[str, Any]:
    return {"incidents": store.list_incidents(limit=limit)}


@app.post("/api/v1/incidents/{incident_id}/approve")
async def approve(incident_id: str, body: ApproveIn) -> Dict[str, Any]:
    return await executor.approve(incident_id, body.approve, body.approver)


@app.post("/api/v1/incidents/{incident_id}/rollback")
async def rollback(incident_id: str, body: ActorIn) -> Dict[str, Any]:
    return await executor.rollback(incident_id, body.actor)


@app.get("/api/v1/incidents/{incident_id}/audit")
async def audit(incident_id: str) -> Dict[str, Any]:
    return {"audit": store.list_audit(incident_id)}


# ------------------------------------------------------------- explainability
@app.get("/api/v1/sources/{source_id}/explain")
async def explain(source_id: str) -> Dict[str, Any]:
    latest = pipeline.latest.get(source_id, {})
    units = {m.name: m.unit for p in registry.plugins.values() for m in p.metrics.values()}
    thresholds = {
        m.name: {"warn": m.warn, "critical": m.critical}
        for p in registry.plugins.values()
        for m in p.metrics.values()
    }
    return explanations.explain_source(store, source_id, units, latest, thresholds=thresholds)


# ------------------------------------------------------------------- agent
@app.post("/api/v1/chat")
async def chat(body: ChatIn) -> Dict[str, Any]:
    return agent.chat(body.message, body.source_id)


# -------------------------------------------------------------------- ml
@app.post("/api/v1/models/retrain")
async def retrain() -> Dict[str, Any]:
    count = pipeline.retrain_all()
    return {"retrained": count}


@app.get("/api/v1/stats")
async def stats() -> Dict[str, Any]:
    data = store.get_stats()
    data["sources"] = pipeline.sources_status()
    return data


@app.get("/api/v1/drift")
async def drift() -> Dict[str, Any]:
    return {"records": store.list_drift()}


@app.get("/api/v1/models")
async def list_models() -> Dict[str, Any]:
    from backend.model_store import ModelStore
    ms = ModelStore()
    return {"models": ms.list_models(), "count": len(ms.list_models())}


@app.get("/api/v1/sensors/mqtt/status")
async def mqtt_status() -> Dict[str, Any]:
    enabled = settings.mqtt_enabled
    connected = mqtt_ingestor._running if mqtt_ingestor else False
    return {"enabled": enabled, "connected": connected, "broker": settings.mqtt_broker, "port": settings.mqtt_port}


@app.post("/api/v1/sensors/mqtt/publish")
async def mqtt_publish(topic: str, payload: str) -> Dict[str, Any]:
    if mqtt_ingestor and mqtt_ingestor._client and mqtt_ingestor._running:
        mqtt_ingestor._client.publish(topic, payload)
        return {"published": True, "topic": topic}
    return {"published": False, "reason": "MQTT not connected"}


# -------------------------------------------------------------------- ws
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    hub.register(ws)
    log.info("ws client connected", extra={"peers": len(hub.connections)})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.unregister(ws)
        log.info("ws client disconnected", extra={"peers": len(hub.connections)})
