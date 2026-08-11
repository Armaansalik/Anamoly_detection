def test_both_plugins_loaded(registry):
    assert "manufacturing" in registry.plugins
    assert "server_health" in registry.plugins
    assert not registry.errors


def test_manufacturing_manifest(registry):
    plugin = registry.get("manufacturing")
    for metric in ("temperature", "vibration", "current", "rpm"):
        spec = plugin.metrics[metric]
        assert spec.unit
        assert spec.warn > 0
        assert spec.critical > spec.warn


def test_manufacturing_actions(registry):
    plugin = registry.get("manufacturing")
    assert plugin.actions["alert_operator"].risk == "low"
    assert plugin.actions["throttle_motor"].risk == "low"
    assert plugin.actions["restart_process"].risk == "high"
    assert all(a.execute and a.rollback for a in plugin.actions.values())


def test_server_health_manifest(registry):
    plugin = registry.get("server_health")
    for metric in ("cpu", "memory", "latency_ms"):
        assert metric in plugin.metrics
    assert plugin.actions["restart_service"].risk == "high"
    assert plugin.actions["alert_operator"].risk == "low"


def test_manufacturing_adapter_converts(registry):
    plugin = registry.get("manufacturing")
    events = plugin.adapter.convert(
        {"temperature": 82.5, "vibration": 3.2, "current": 11.9, "rpm": 1430},
        "machine_01",
    )
    assert len(events) == 4
    by_name = {e.metric_name: e for e in events}
    assert by_name["temperature"].unit == "C"
    assert by_name["vibration"].unit == "mm/s"
    assert by_name["current"].unit == "A"
    assert by_name["rpm"].unit == "rpm"
    assert all(e.domain == "manufacturing" for e in events)
    assert all(e.source_id == "machine_01" for e in events)


def test_adapter_ignores_unknown_keys(registry):
    plugin = registry.get("manufacturing")
    events = plugin.adapter.convert({"temperature": 80.0, "unexpected_field": "x"}, "machine_01")
    assert len(events) == 1
    assert events[0].metric_name == "temperature"


def test_server_health_adapter_converts(registry):
    plugin = registry.get("server_health")
    events = plugin.adapter.convert({"cpu": 42.1, "memory": 55.2, "latency_ms": 12.3}, "server_a")
    assert len(events) == 3
    by_name = {e.metric_name: e for e in events}
    assert by_name["cpu"].unit == "%"
    assert by_name["latency_ms"].unit == "ms"


def test_unknown_domain_rejected(registry):
    import pytest

    from core.plugin_loader import PluginError

    with pytest.raises(PluginError):
        registry.adapt("does_not_exist", {"x": 1}, "s1")
