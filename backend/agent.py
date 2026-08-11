"""Layer 6 - Agentic reasoning: tools, guardrails, and a reasoning trace.

The agent has three tools:
    get_machine_history(source_id, window)      - recent readings
    get_similar_past_incidents(incident)        - RAG over resolved incidents
    propose_action(action_id, risk_level)       - drafts, never executes

Guardrail: the agent can only pick actions present in the plugin manifest's
allowed action list. Every decision emits a human-readable reasoning trace
stored with the incident. With SENTINEL_OPENAI_API_KEY set, an LLM (optional
`openai` package) takes over the decision step; otherwise the built-in rule
engine produces the same trace structure - no API key required to run.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from backend.storage import SQLiteStore
from core.config import Settings
from core.logging import get_logger
from core.plugin_loader import Plugin

log = get_logger("sentinel.agent")


class ReasoningAgent:
    def __init__(self, store: SQLiteStore, registry, settings: Settings):
        self.store = store
        self.registry = registry
        self.settings = settings
        self._llm = None
        if settings.openai_api_key:
            try:
                from openai import OpenAI

                self._llm = OpenAI(api_key=settings.openai_api_key)
                log.info("llm backend enabled", extra={"model": settings.llm_model})
            except ImportError:
                log.warning("openai package missing; using rule engine despite API key")

    # ------------------------------------------------------------------ public
    def reason(self, incident: Dict[str, Any], plugin: Plugin) -> Dict[str, Any]:
        source_id = incident["source_id"]
        trace: List[str] = []

        history = self.store.recent_events(source_id, None, limit=50)
        trace.append(f"tool=get_machine_history({source_id}, window=50) -> {len(history)} readings reviewed")

        similar = self._similar_incidents(incident, limit=2)
        if similar:
            ids = ", ".join(s["id"][:8] for s in similar)
            trace.append(f"tool=get_similar_past_incidents() -> {len(similar)} similar resolved incident(s): {ids}")
        else:
            trace.append("tool=get_similar_past_incidents() -> no similar past incidents found")

        if self._llm is not None:
            decision = self._llm_decide(incident, plugin)
        else:
            decision = self._rule_decide(incident, plugin)

        action_id = decision["action_id"]
        if action_id not in plugin.actions:
            log.error("agent proposed disallowed action; falling back", extra={"action": action_id})
            action_id = next(iter(plugin.actions))
        action = plugin.actions[action_id]
        trace.append(f"tool=propose_action({action_id}, risk={action.risk})")
        trace.append("guardrail=action verified against manifest allowed list")
        if decision.get("reason"):
            trace.append(f"reasoning={decision['reason']}")

        return {
            "action_id": action_id,
            "risk": action.risk,
            "confidence": decision.get("confidence", 0.7),
            "trace": trace,
            "summary": f"Detected {incident['severity']} anomaly on {source_id}; recommended action: {action_id}.",
        }

    def chat(self, message: str, source_id: Optional[str] = None) -> Dict[str, Any]:
        trace: List[str] = []
        target = self._resolve_source(message, source_id)
        if target:
            trace.append(f"tool=resolve_source('{message}') -> {target}")
        else:
            trace.append("tool=resolve_source('" + message + "') -> no specific source; answered generally")

        incidents = self.store.list_incidents(limit=50)
        relevant = [i for i in incidents if (target is None or i["source_id"] == target)]
        trace.append(f"tool=search_incidents() -> {len(relevant)} relevant incident(s)")

        history = self.store.recent_events(target, None, limit=60) if target else []
        trace.append(f"tool=get_machine_history({target}) -> {len(history)} readings")

        similar = self._keyword_similar(message, incidents, limit=2)
        if similar:
            trace.append(f"tool=get_similar_past_incidents() -> {len(similar)} similar past incidents")

        if self._llm is not None:
            response = self._llm_chat(message, relevant, history, similar)
        else:
            response = self._rule_answer(message, relevant, history, similar)

        incident_id = relevant[0]["id"] if relevant else None
        return {"response": response, "trace": trace, "incident_id": incident_id}

    # ------------------------------------------------------------------ tools
    def _resolve_source(self, message: str, source_id: Optional[str]) -> Optional[str]:
        if source_id:
            return source_id
        text = message.lower()
        for source in self._known_sources():
            if source.lower() in text:
                return source
        return None

    def _known_sources(self) -> List[str]:
        sources = {inc["source_id"] for inc in self.store.list_incidents(limit=200)}
        for sid in list(sources):
            for r in self.store.recent_events(sid, None, limit=1):
                sources.add(r["source_id"])
        return sorted(sources)

    def _similar_incidents(self, incident: Dict[str, Any], limit: int = 2) -> List[Dict[str, Any]]:
        resolved = [i for i in self.store.list_incidents(limit=200) if i["status"] in ("executed", "rolled_back")]
        if not resolved:
            return []
        query = {incident["source_id"], incident["domain"]} | set(incident.get("metrics", {}))
        scored = []
        for other in resolved:
            if other["id"] == incident.get("id"):
                continue
            overlap = query & ({other["source_id"], other["domain"]} | set(other.get("metrics", {})))
            scored.append((len(overlap), other))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit] if s[0] > 0]

    def _keyword_similar(self, message: str, incidents: List[Dict[str, Any]], limit: int = 2) -> List[Dict[str, Any]]:
        tokens = set(re.findall(r"[a-z0-9_]+", message.lower()))
        scored = []
        for inc in incidents:
            blob = " ".join([inc["source_id"], inc["domain"], inc["message"].lower()])
            overlap = len(tokens & set(re.findall(r"[a-z0-9_]+", blob)))
            scored.append((overlap, inc))
        scored.sort(key=lambda x: -x[0])
        return [s[1] for s in scored[:limit] if s[0] > 0]

    # ------------------------------------------------------------- decisions
    def _rule_decide(self, incident: Dict[str, Any], plugin: Plugin) -> Dict[str, Any]:
        metrics = incident.get("metrics", {})
        critical_hit = any(
            m in plugin.metrics and v >= plugin.metrics[m].critical for m, v in metrics.items()
        )
        warn_hit = any(m in plugin.metrics and v >= plugin.metrics[m].warn for m, v in metrics.items())
        if critical_hit:
            high = [a for a in plugin.actions.values() if a.risk == "high"]
            if high:
                reason = f"critical threshold breached on {incident['source_id']}; highest-severity action required"
                return {"action_id": high[0].id, "confidence": 0.85, "reason": reason}
        if warn_hit or incident.get("anomaly_score", 0) >= 0.5:
            alert = plugin.actions.get("alert_operator")
            if alert:
                return {
                    "action_id": "alert_operator",
                    "confidence": 0.7,
                    "reason": f"warning-level anomaly on {incident['source_id']}; operator notification is appropriate",
                }
        low = [a for a in plugin.actions.values() if a.risk == "low"]
        action_id = low[0].id if low else next(iter(plugin.actions))
        return {"action_id": action_id, "confidence": 0.6, "reason": "default safe action selected"}

    def _llm_decide(self, incident: Dict[str, Any], plugin: Plugin) -> Dict[str, Any]:
        try:
            allowed = [{"id": a.id, "risk": a.risk, "description": a.description} for a in plugin.actions.values()]
            prompt = (
                "You are the reasoning core of an autonomous anomaly-response agent.\n"
                f"Incident: {json.dumps(incident)}\n"
                f"Allowed actions (choose exactly one id): {json.dumps(allowed)}\n"
                "Reply with JSON only: {\"action_id\": \"...\", \"reason\": \"...\"}"
            )
            resp = self._llm.chat.completions.create(
                model=self.settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = resp.choices[0].message.content
            parsed = json.loads(content)
            return {"action_id": str(parsed["action_id"]), "confidence": 0.9, "reason": str(parsed.get("reason", ""))}
        except Exception as exc:
            log.error("llm decision failed; falling back to rules", extra={"error": str(exc)})
            return self._rule_decide(incident, plugin)

    def _rule_answer(self, message: str, relevant: List[Dict[str, Any]], history, similar) -> str:
        if not relevant:
            return (
                f"I could not find an incident matching '{message}'. "
                "Send data through the ingestion API and I will monitor it live."
            )
        latest = relevant[0]
        action = latest.get("action")
        parts = [
            f"Here is what happened on {latest['source_id']} ({latest['domain']}): {latest['message']}",
            f"Severity: {latest['severity']} | anomaly score: {latest['anomaly_score']:.2f} | status: {latest['status']}",
        ]
        if action:
            parts.append(f"Action: {action['id']} (risk {action['risk']}, status {action['status']})")
        if similar:
            parts.append(
                "Similar past incidents: "
                + "; ".join(f"{s['id'][:8]} ({s['status']})" for s in similar)
            )
        return " ".join(parts)

    def _llm_chat(self, message: str, relevant, history, similar) -> str:
        try:
            context = {
                "question": message,
                "incidents": relevant[:5],
                "history_points": len(history),
                "similar": [s["id"] for s in similar],
            }
            resp = self._llm.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are SentinelAgent's conversational copilot. Answer operators concisely using only the provided context."},
                    {"role": "user", "content": json.dumps(context)},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            log.error("llm chat failed; falling back to rules", extra={"error": str(exc)})
            return self._rule_answer(message, relevant, history, similar)
