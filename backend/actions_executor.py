"""Layer 7 - Action & orchestration: risk-tiered execution with rollback.

Low-risk actions auto-execute; high-risk actions are queued for human
approval on the dashboard. Every automated action has a defined rollback
step, and everything is written to the audit log (what, why, who approved,
outcome).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.hub import StreamingHub
from backend.storage import SQLiteStore
from core.logging import get_logger
from core.plugin_loader import Plugin, PluginRegistry

log = get_logger("sentinel.executor")


class ActionExecutor:
    def __init__(self, store: SQLiteStore, hub: StreamingHub, registry: PluginRegistry):
        self.store = store
        self.hub = hub
        self.registry = registry

    async def submit(
        self,
        incident_id: str,
        action_id: str,
        plugin: Plugin,
        trace: list,
        context: Dict[str, Any],
    ) -> None:
        action = plugin.actions[action_id]
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return
        incident["action"] = {
            "id": action.id,
            "risk": action.risk,
            "description": action.description,
            "status": "queued",
        }
        incident["agent_trace"] = trace
        if action.risk == "low":
            incident["action"]["status"] = "executing"
            self.store.update_incident(incident_id, status="executing", agent_trace=trace, action=incident["action"])
            await self._execute(incident_id, action, context, actor="agent:auto")
        else:
            incident["action"]["status"] = "pending_approval"
            self.store.update_incident(incident_id, status="pending_approval", agent_trace=trace, action=incident["action"])
            await self.hub.publish(
                "action",
                incident_id=incident_id,
                source_id=incident["source_id"],
                action=incident["action"],
                message=f"Human approval required for high-risk action '{action.id}'",
            )

    async def _execute(
        self,
        incident_id: str,
        action,
        context: Dict[str, Any],
        actor: str,
    ) -> None:
        try:
            result = action.execute(context["source_id"], context.get("event"), context)
            incident = self.store.get_incident(incident_id)
            if incident and incident.get("action"):
                incident["action"]["status"] = "executed"
                incident["action"]["result"] = result
                self.store.update_incident(incident_id, status="executed", action=incident["action"])
            self.store.insert_audit(incident_id, actor, action.id, "executed", result.get("detail", ""))
            await self.hub.publish(
                "action",
                incident_id=incident_id,
                source_id=context["source_id"],
                action={"id": action.id, "status": "executed", "detail": result.get("detail", "")},
            )
        except Exception as exc:
            self.store.insert_audit(incident_id, actor, action.id, "execute_failed", str(exc))
            if action.rollback is not None:
                try:
                    rb = action.rollback(context["source_id"], context.get("event"), context)
                    self.store.insert_audit(incident_id, actor, action.id, "rolled_back", rb.get("detail", ""))
                    self.store.update_incident(incident_id, status="rolled_back")
                except Exception as rb_exc:
                    self.store.insert_audit(incident_id, actor, action.id, "rollback_failed", str(rb_exc))
                    self.store.update_incident(incident_id, status="failed")
            else:
                self.store.update_incident(incident_id, status="failed")

    async def approve(self, incident_id: str, approve: bool, approver: str) -> Dict[str, Any]:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return {"ok": False, "reason": "incident not found"}
        if incident["status"] != "pending_approval":
            return {"ok": False, "reason": f"incident is {incident['status']}, not awaiting approval"}
        action_info = incident["action"] or {}
        action_id = action_info.get("id")
        plugin = self.registry.get(incident["domain"])
        action = plugin.actions.get(action_id)
        if action is None:
            return {"ok": False, "reason": f"action {action_id!r} not in plugin manifest"}
        context: Dict[str, Any] = {"source_id": incident["source_id"], "event": None, "message": incident["message"]}
        if not approve:
            self.store.insert_audit(incident_id, approver, action.id, "rejected", f"Rejected by {approver}")
            self.store.update_incident(incident_id, status="rejected")
            await self.hub.publish(
                "action",
                incident_id=incident_id,
                source_id=incident["source_id"],
                action={"id": action.id, "status": "rejected", "detail": f"Rejected by {approver}"},
            )
            return {"ok": True, "status": "rejected"}
        await self._execute(incident_id, action, context, actor=approver)
        return {"ok": True, "status": "executed"}

    async def rollback(self, incident_id: str, actor: str) -> Dict[str, Any]:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return {"ok": False, "reason": "incident not found"}
        action_info = incident["action"] or {}
        action_id = action_info.get("id")
        plugin = self.registry.get(incident["domain"])
        action = plugin.actions.get(action_id)
        if action is None or action.rollback is None:
            return {"ok": False, "reason": "no rollback defined for this action"}
        context: Dict[str, Any] = {"source_id": incident["source_id"], "event": None, "message": incident["message"]}
        if action_info.get("result"):
            context.update(action_info["result"])
        try:
            rb = action.rollback(incident["source_id"], None, context)
            self.store.insert_audit(incident_id, actor, action.id, "rolled_back", rb.get("detail", ""))
            self.store.update_incident(incident_id, status="rolled_back")
            await self.hub.publish(
                "action",
                incident_id=incident_id,
                source_id=incident["source_id"],
                action={"id": action.id, "status": "rolled_back", "detail": rb.get("detail", "")},
            )
            return {"ok": True, "status": "rolled_back"}
        except Exception as exc:
            self.store.insert_audit(incident_id, actor, action.id, "rollback_failed", str(exc))
            return {"ok": False, "reason": str(exc)}
