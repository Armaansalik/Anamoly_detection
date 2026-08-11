from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.events import SensorEvent


def test_valid_event():
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    event = SensorEvent(
        source_id="machine_01",
        domain="manufacturing",
        timestamp=ts,
        metric_name="temperature",
        value=82.5,
        unit="C",
    )
    assert event.source_id == "machine_01"
    assert event.value == 82.5
    assert event.unit == "C"
    assert event.metadata == {}
    assert event.timestamp == ts


def test_default_timestamp_is_utc():
    event = SensorEvent(source_id="m1", domain="d", metric_name="x", value=1.0, unit="u")
    assert event.timestamp.tzinfo is not None


def test_missing_required_field_rejected():
    with pytest.raises(ValidationError):
        SensorEvent(source_id="m1", domain="d", metric_name="x", value=1.0)  # no unit


def test_invalid_value_rejected():
    with pytest.raises(ValidationError):
        SensorEvent(source_id="m1", domain="d", metric_name="x", value="hot", unit="C")


def test_numeric_string_coerced():
    event = SensorEvent(source_id="m1", domain="d", metric_name="x", value="12.5", unit="u")
    assert event.value == 12.5


def test_metadata_defaults_to_dict():
    event = SensorEvent(source_id="m1", domain="d", metric_name="x", value=1.0, unit="u")
    assert isinstance(event.metadata, dict)


def test_metadata_roundtrip():
    event = SensorEvent(
        source_id="m1",
        domain="d",
        metric_name="x",
        value=1.0,
        unit="u",
        metadata={"zone": "line_a"},
    )
    assert event.metadata["zone"] == "line_a"
