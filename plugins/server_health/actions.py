"""Server health plugin actions — a different action set from manufacturing."""

from __future__ import annotations

from typing import Any, Dict

from core.logging import get_logger

log = get_logger("sentinel.plugins.server_health.actions")

SERVICES = {}


def _alert_operator(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    detail = f"Ops alerted for {source_id}: {context.get('message', 'anomaly detected')}"
    log.info("action executed", extra={"action": "alert_operator", "source_id": source_id, "detail": detail})
    return {"status": "executed", "detail": detail}


def _alert_operator_rollback(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "rolled_back", "detail": "Alert dismissed"}


def _restart_service(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    prev = SERVICES.get(source_id, {"state": "running"})
    SERVICES[source_id] = {"state": "restarted"}
    detail = f"Service on {source_id} restarted (was {prev['state']})"
    log.info("action executed", extra={"action": "restart_service", "source_id": source_id, "detail": detail})
    return {"status": "executed", "detail": detail}


def _restart_service_rollback(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    SERVICES[source_id] = {"state": "running"}
    return {"status": "rolled_back", "detail": f"Service state restored for {source_id}"}


def get_actions() -> list[Dict[str, Any]]:
    return [
        {
            "id": "alert_operator",
            "risk": "low",
            "description": "Notify the ops team on the dashboard",
            "execute": _alert_operator,
            "rollback": _alert_operator_rollback,
        },
        {
            "id": "restart_service",
            "risk": "high",
            "description": "Restart the failing service (requires human approval)",
            "execute": _restart_service,
            "rollback": _restart_service_rollback,
        },
    ]
