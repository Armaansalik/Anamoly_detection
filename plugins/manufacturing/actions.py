"""Manufacturing plugin actions — safe, permitted automated responses.

Each action declares a risk tier and both an `execute` and a `rollback` step.
The action executor (Layer 7) enforces: low risk -> auto-execute,
high risk -> human approval. Rollback is always defined so every automated
action has an "undo" path (audited).
"""

from __future__ import annotations

from typing import Any, Dict

from core.logging import get_logger

log = get_logger("sentinel.plugins.manufacturing.actions")

MOTOR_SPEED = {"machine_01": 100, "machine_02": 100, "machine_03": 100}


def _alert_operator(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    detail = f"Operator alerted for {source_id}: {context.get('message', 'anomaly detected')}"
    log.info("action executed", extra={"action": "alert_operator", "source_id": source_id, "detail": detail})
    return {"status": "executed", "detail": detail}


def _alert_operator_rollback(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "rolled_back", "detail": "Alert dismissed"}


def _throttle_motor(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    prev = MOTOR_SPEED.get(source_id, 100)
    new = max(0, int(prev * 0.8))
    MOTOR_SPEED[source_id] = new
    detail = f"Motor throttled from {prev}% to {new}% speed for {source_id}"
    log.info("action executed", extra={"action": "throttle_motor", "source_id": source_id, "detail": detail})
    return {"status": "executed", "detail": detail, "prev_speed": prev, "new_speed": new}


def _throttle_motor_rollback(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    prev = context.get("prev_speed", 100)
    MOTOR_SPEED[source_id] = prev
    return {"status": "rolled_back", "detail": f"Motor speed restored to {prev}% for {source_id}"}


def _restart_process(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    detail = f"Production process restarted for {source_id}"
    log.info("action executed", extra={"action": "restart_process", "source_id": source_id, "detail": detail})
    return {"status": "executed", "detail": detail}


def _restart_process_rollback(source_id: str, event, context: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "rolled_back", "detail": f"Process restart reverted (no-op) for {source_id}"}


def get_actions() -> list[Dict[str, Any]]:
    return [
        {
            "id": "alert_operator",
            "risk": "low",
            "description": "Notify the operator on the dashboard and sound an audible alert",
            "execute": _alert_operator,
            "rollback": _alert_operator_rollback,
        },
        {
            "id": "throttle_motor",
            "risk": "low",
            "description": "Reduce motor speed by 20% to protect the machine",
            "execute": _throttle_motor,
            "rollback": _throttle_motor_rollback,
        },
        {
            "id": "restart_process",
            "risk": "high",
            "description": "Restart the production process (requires human approval)",
            "execute": _restart_process,
            "rollback": _restart_process_rollback,
        },
    ]
