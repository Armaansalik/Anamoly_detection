"""SQLite-backed storage: time-series events, incidents, audit log, drift records.

Uses WAL mode and a connection per call — safe for the threaded/async FastAPI
context while staying dependency-free for local dev. Swap for TimescaleDB by
implementing the same method surface (see README).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.events import SensorEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_source_metric_ts
    ON events (source_id, metric_name, timestamp);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at TEXT NOT NULL,
    anomaly_score REAL NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    metrics TEXT NOT NULL DEFAULT '{}',
    agent_trace TEXT NOT NULL DEFAULT '[]',
    action TEXT
);
CREATE INDEX IF NOT EXISTS idx_incidents_source ON incidents (source_id, created_at);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drift_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    kl REAL NOT NULL,
    recommendation TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------ events
    def insert_event(self, event: SensorEvent) -> str:
        event_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (id, source_id, domain, timestamp, metric_name, value, unit, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    event.source_id,
                    event.domain,
                    event.timestamp.isoformat(),
                    event.metric_name,
                    event.value,
                    event.unit,
                    json.dumps(event.metadata),
                ),
            )
        return event_id

    def recent_events(self, source_id: str, metric_name: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            if metric_name:
                rows = conn.execute(
                    "SELECT * FROM events WHERE source_id = ? AND metric_name = ? ORDER BY timestamp DESC LIMIT ?",
                    (source_id, metric_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM events WHERE source_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (source_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def all_events_for_training(self, source_id: str, metric_name: str, limit: int = 1000) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE source_id = ? AND metric_name = ? "
                "ORDER BY timestamp ASC LIMIT ?",
                (source_id, metric_name, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def sources_summary(self) -> Dict[str, Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT source_id, domain, MAX(timestamp) AS updated_at FROM events GROUP BY source_id"
            ).fetchall()
        return {r["source_id"]: dict(r) for r in rows}

    # ---------------------------------------------------------- incidents
    def insert_incident(self, incident: Dict[str, Any]) -> str:
        incident_id = incident.get("id") or str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO incidents (id, source_id, domain, created_at, anomaly_score, severity, "
                "status, message, metrics, agent_trace, action) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident_id,
                    incident["source_id"],
                    incident["domain"],
                    incident.get("created_at", _now()),
                    incident.get("anomaly_score", 0.0),
                    incident.get("severity", "medium"),
                    incident.get("status", "open"),
                    incident.get("message", ""),
                    json.dumps(incident.get("metrics", {})),
                    json.dumps(incident.get("agent_trace", [])),
                    json.dumps(incident.get("action")) if incident.get("action") else None,
                ),
            )
        return incident_id

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return self._row_to_incident(row) if row else None

    def list_incidents(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_incident(r) for r in rows]

    def update_incident(self, incident_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"status", "anomaly_score", "severity", "message", "agent_trace", "action"}
        assignments = [f"{k} = ?" for k in fields if k in allowed]
        values = []
        for k in fields:
            if k not in allowed:
                continue
            v = fields[k]
            if k in ("agent_trace", "action") and not isinstance(v, str):
                v = json.dumps(v)
            values.append(v)
        if not assignments:
            return
        values.append(incident_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE incidents SET {', '.join(assignments)} WHERE id = ?", values)

    @staticmethod
    def _row_to_incident(row: sqlite3.Row) -> Dict[str, Any]:
        incident = dict(row)
        incident["metrics"] = json.loads(incident.get("metrics") or "{}")
        incident["agent_trace"] = json.loads(incident.get("agent_trace") or "[]")
        incident["action"] = json.loads(incident["action"]) if incident.get("action") else None
        return incident

    # ----------------------------------------------------------- audit log
    def insert_audit(self, incident_id: str, actor: str, action: str, outcome: str, detail: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (incident_id, actor, action, outcome, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (incident_id, actor, action, outcome, detail, _now()),
            )

    def list_audit(self, incident_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE incident_id = ? ORDER BY created_at DESC", (incident_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------- drift records
    def list_drift(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM drift_records ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_drift(self, source_id: str, metric_name: str, kl: float, recommendation: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO drift_records (source_id, metric_name, kl, recommendation, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (source_id, metric_name, kl, recommendation, _now()),
            )
