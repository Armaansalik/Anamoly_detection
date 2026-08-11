"""Core event schema — the single contract every domain plugin translates into.

The entire platform only ever talks to this schema. Domain plugins (manufacturing,
server health, cold-chain, fraud, ...) convert their raw domain payloads into
SensorEvent instances; nothing downstream knows or cares about domain specifics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class SensorEvent(BaseModel):
    """Canonical event emitted by any domain plugin adapter."""

    source_id: str = Field(..., min_length=1, description="Unique source identifier, e.g. machine_01")
    domain: str = Field(..., min_length=1, description="Plugin/domain name, e.g. manufacturing")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metric_name: str = Field(..., min_length=1, description="Metric identifier, e.g. temperature")
    value: float = Field(..., description="Numeric reading in the declared unit")
    unit: str = Field(..., min_length=1, description="Unit of measurement, e.g. C, mm/s, A")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Free-form extra context")

    @field_validator("value")
    @classmethod
    def _value_is_number(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError(f"value must be numeric, got {v!r}")


def event_to_dict(event: "SensorEvent") -> Dict[str, Any]:
    return event.model_dump(mode="json")
