# SentinelAgent

**Autonomous Anomaly Detection & Self-Healing Agent** — a production-grade, domain-agnostic platform that ingests live sensor telemetry, detects anomalies with continuously monitored ML models, reasons about them with an agent (tool-calling + memory + guardrails), and takes safe, auditable, reversible actions in real time.

The core engine is **plugin-based**: manufacturing, server health, cold-chain, fraud — any domain is a plugin folder (`manifest.yaml` + `adapter.py` + `actions.py` + `dashboard.json`). The core never changes when a new domain joins.

> Full build specification: [`docs/ANOMALY_AGENT_FULL_BUILD_SPEC.md`](docs/ANOMALY_AGENT_FULL_BUILD_SPEC.md)
>
> **Non-technical? Read this first:** [`docs/PLAIN_ENGLISH_GUIDE.md`](docs/PLAIN_ENGLISH_GUIDE.md) — what it does in plain language, ML terms translated, and what's new vs. existing tools.
>
> **Stakeholders / judges:** [`docs/PROJECT_MANAGEMENT_PLAN.md`](docs/PROJECT_MANAGEMENT_PLAN.md) — charter, requirements, milestones, risks, KPIs, acceptance criteria.

---

## Architecture (8 layers)

```
LAYER 8  Experience    Live dashboard (WebSockets) · conversational copilot · 3D digital twin · explainability
LAYER 7  Action        Risk-tiered executor · rollback · full audit log
LAYER 6  Reasoning     Agent with tools (history, RAG over incidents, propose_action) · guardrails · reasoning trace
LAYER 5  ML Detection  Isolation Forest · rolling z-score · LSTM autoencoder · KL-drift monitor · retraining API
LAYER 4  Storage       SQLite (dev) / TimescaleDB (prod) · incident + audit store
LAYER 3  Ingestion     FastAPI REST + WebSocket · schema validation · MQTT optional
LAYER 2  Edge          Sensors / gateways (ESP32, PLC, agents) — any payload
LAYER 1  Plugins       Domain plugin SDK — the "fits any problem" part
```

## Features

- **Domain-agnostic plugin core** — two shipped plugins prove it: `manufacturing` (temperature/vibration/current/rpm) and `server_health` (CPU/memory/latency). Entirely different domains, zero core changes.
- **Real ML, not a demo** — Isolation Forest + rolling z-score combined scoring, optional numpy LSTM autoencoder, and a KL-divergence **drift monitor** that logs a retraining recommendation (no silent model rot). Manual/API retraining: `POST /api/v1/models/retrain`.
- **Agentic reasoning with guardrails** — the agent uses tools (`get_machine_history`, `get_similar_past_incidents`, `propose_action`), can only pick actions declared in the plugin manifest, and stores a human-readable reasoning trace on every incident. Drop-in LLM backend when `SENTINEL_OPENAI_API_KEY` is set; built-in rule engine otherwise.
- **Safe autonomous actions** — low-risk actions auto-execute; high-risk actions wait for human approval on the dashboard. Every action has a rollback step. Every step is audited (who/what/why/outcome).
- **Real-time experience layer** — WebSocket-fed dashboard (no polling), live charts, 3D digital twin color-coded by health, conversational copilot that reuses the same agent, and a SHAP-style explainability panel.
- **Everything containerized** — `docker compose up --build` runs backend + frontend (MQTT broker via profile).

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Pydantic v2, uvicorn |
| ML | scikit-learn (Isolation Forest), numpy (LSTM AE, drift KL) |
| Storage | SQLite (dev, WAL), TimescaleDB-ready interface |
| Streaming | In-process pub/sub + WebSockets; optional MQTT (paho-mqtt) |
| Agent | Built-in rule engine, pluggable OpenAI backend |
| Frontend | React 18, Vite, Recharts, Three.js |
| Ops | Docker Compose, JSON structured logging, `.env` config |

## Quickstart (local, no Docker)

Prerequisites: Python 3.11+, Node 18+.

```bash
# 1. Python environment
py -3.11 -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 2. Config
copy .env.example .env           # Windows

# 3. Start the backend
uvicorn backend.main:app --reload --port 8000

# 4. In another terminal — stream simulated sensor data (injects anomalies!)
py simulator/sensor_simulator.py --interval 2

# 5. In a third terminal — start the dashboard
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Watch the dashboard: sources appear, charts stream live, anomalies get flagged, the agent reasons and either auto-acts (low risk) or queues high-risk actions for your approval.

## Docker quickstart

```bash
copy .env.example .env
docker compose up --build        # backend :8000, frontend :5173
# optional MQTT broker:
docker compose --profile broker up
```

## Tests

```bash
pytest tests/ -v        # 22 tests: schema, plugin loader, detection, drift, LSTM AE
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/events` | Ingest a raw domain payload `{domain, source_id, payload}` |
| POST | `/api/v1/events/batch` | Batch ingestion |
| GET | `/api/v1/plugins` | Loaded plugins + metrics + actions |
| GET | `/api/v1/sources` | Source health scores |
| GET | `/api/v1/incidents` | Incident list |
| POST | `/api/v1/incidents/{id}/approve` | Approve/reject a queued high-risk action |
| POST | `/api/v1/incidents/{id}/rollback` | Manually roll back an executed action |
| GET | `/api/v1/incidents/{id}/audit` | Audit trail for an incident |
| POST | `/api/v1/chat` | Conversational copilot (reuses the agent) |
| GET | `/api/v1/sources/{id}/explain` | Feature-level contribution (SHAP-style) |
| POST | `/api/v1/models/retrain` | Refit all detectors, reset drift baselines |
| GET | `/api/v1/drift` | Drift records / retraining recommendations |
| WS | `/ws` | Live events, alerts, actions, drift notices |

## Adding a new plugin in under 30 minutes

1. Create `plugins/<your_domain>/`:
   - **`manifest.yaml`** — declare metrics with `unit`, `warn`, `critical` thresholds, and the permitted `actions` with risk tiers:
     ```yaml
     name: cold_chain
     display_name: Cold Chain Logistics
     metrics:
       temperature:
         unit: C
         warn: 6.0
         critical: 10.0
       humidity:
         unit: "%"
         warn: 65.0
         critical: 80.0
     actions:
       - id: alert_operator
         risk: low
         description: Notify the operator
       - id: switch_cooler
         risk: high
         description: Switch to backup cooling unit (requires approval)
     ```
2. **`adapter.py`** — a class `Adapter` with `convert(raw: dict, source_id: str) -> list[SensorEvent]`. Copy the pattern from `plugins/manufacturing/adapter.py`; map your raw payload keys to `SensorEvent(metric_name, value, unit, ...)`.
3. **`actions.py`** — a `get_actions()` returning `{id, risk, description, execute, rollback}` entries. Look at `plugins/manufacturing/actions.py`.
4. **`dashboard.json`** *(optional)* — widget declarations for the UI.

Restart the backend — the plugin loader picks it up. The core engine (ingestion, ML, agent, executor, dashboard) never needs a change. That's the whole point.

## Project structure

```
core/                     # event schema, plugin loader, config, JSON logging
plugins/manufacturing/    # reference plugin: adapter, actions, manifest
plugins/server_health/    # second plugin proving extensibility
backend/                  # FastAPI app: ingestion, storage, detection, agent, executor
simulator/                # synthetic sensor stream with anomaly injection
frontend/                 # React dashboard (WebSockets, charts, 3D twin, chat)
tests/                    # pytest suite
```

## Roadmap

- [ ] TimescaleDB / pgvector storage backend (same method surface, drop-in)
- [ ] Kafka/Redpanda ingestion for production scale
- [ ] Evidently AI integration for richer drift reports
- [ ] Voice interface (Whisper STT + TTS) for the factory floor
- [ ] Keycloak auth + multi-tenant onboarding

## License

MIT
