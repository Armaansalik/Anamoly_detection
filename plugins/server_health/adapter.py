"""Server health domain adapter: raw infra telemetry -> canonical SensorEvents.

Raw payload example (from a node exporter / agent):
    {"cpu": 42.1, "memory": 55.2, "latency_ms": 12.3}

Deliberately different from manufacturing (different metrics, units, and
semantics) to prove the core is domain-agnostic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from core.events import SensorEvent

VALID_METRICS = {
    "cpu": "%",
    "memory": "%",
    "latency_ms": "ms",
}


class Adapter:
    """Translates infrastructure telemetry into the platform event schema."""

    def convert(self, raw: Dict[str, Any], source_id: str) -> List[SensorEvent]:
        events: List[SensorEvent] = []
        for key, value in raw.items():
            if key not in VALID_METRICS:
                continue
            events.append(
                SensorEvent(
                    source_id=source_id,
                    domain="server_health",
                    timestamp=datetime.now(timezone.utc),
                    metric_name=key,
                    value=float(value),
                    unit=VALID_METRICS[key],
                )
            )
        return events
