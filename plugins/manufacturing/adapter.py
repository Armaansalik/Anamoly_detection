"""Manufacturing domain adapter: raw machine telemetry -> canonical SensorEvents.

Raw payload example (from an ESP32 / PLC / gateway):
    {"temperature": 82.5, "vibration": 3.2, "current": 11.9, "rpm": 1430}

Unknown keys are ignored so the adapter is tolerant of payload growth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from core.events import SensorEvent

VALID_METRICS = {
    "temperature": "C",
    "vibration": "mm/s",
    "current": "A",
    "rpm": "rpm",
}


class Adapter:
    """Translates manufacturing raw telemetry into the platform event schema."""

    def convert(self, raw: Dict[str, Any], source_id: str) -> List[SensorEvent]:
        events: List[SensorEvent] = []
        for key, value in raw.items():
            if key not in VALID_METRICS:
                continue
            events.append(
                SensorEvent(
                    source_id=source_id,
                    domain="manufacturing",
                    timestamp=datetime.now(timezone.utc),
                    metric_name=key,
                    value=float(value),
                    unit=VALID_METRICS[key],
                )
            )
        return events
