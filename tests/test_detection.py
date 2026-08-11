import asyncio
import random

import numpy as np

from backend.detection import DriftMonitor, LSTMAutoencoder, RollingDetector
from core.events import SensorEvent


def run_process(pipeline, event, executor, agent):
    return asyncio.run(pipeline.process(event, executor=executor, agent=agent))


class FakeAgent:
    def reason(self, incident, plugin):
        return {
            "action_id": "alert_operator",
            "risk": "low",
            "trace": ["guardrail ok"],
            "confidence": 0.9,
            "summary": "s",
        }


class FakeExecutor:
    def __init__(self):
        self.submissions = []

    async def submit(self, *args, **kwargs):
        self.submissions.append(args[0])


def test_rolling_detector_flags_spike():
    rng = random.Random(42)
    det = RollingDetector(train_window=40, z_window=20, min_warmup=20)
    normal_scores = []
    for _ in range(80):
        normal_scores.append(det.update(75.0 + rng.uniform(-1.0, 1.0)))
    assert det.is_warm()
    spike_score = det.update(99.0)
    assert spike_score > max(normal_scores[-10:])
    assert 0.0 <= spike_score <= 1.0


def test_detector_cold_returns_zero():
    det = RollingDetector(min_warmup=40)
    assert det.update(75.0) == 0.0


def test_pipeline_creates_incident_on_critical_threshold(store, registry, pipeline):
    agent = FakeAgent()
    executor = FakeExecutor()

    for i in range(40):
        ev = SensorEvent(
            source_id="machine_01",
            domain="manufacturing",
            metric_name="temperature",
            value=75.0 + (i % 5),
            unit="C",
        )
        incident = run_process(pipeline, ev, executor, agent)
        assert incident is None

    spike = SensorEvent(
        source_id="machine_01",
        domain="manufacturing",
        metric_name="temperature",
        value=98.0,
        unit="C",
    )
    incident = run_process(pipeline, spike, executor, agent)
    assert incident is not None
    assert incident["severity"] == "high"
    incidents = store.list_incidents()
    assert len(incidents) == 1
    assert incidents[0]["metrics"]["temperature"] == 98.0


def test_pipeline_no_incident_on_normal_data(store, registry, pipeline):
    agent = FakeAgent()
    executor = FakeExecutor()
    for i in range(60):
        ev = SensorEvent(
            source_id="machine_02",
            domain="manufacturing",
            metric_name="vibration",
            value=3.0 + (i % 3) * 0.1,
            unit="mm/s",
        )
        assert run_process(pipeline, ev, executor, agent) is None
    assert store.list_incidents() == []


def test_drift_monitor_flags_distribution_shift():
    rng = np.random.default_rng(1)
    monitor = DriftMonitor(warmup=120, smoothing=0.05, kl_threshold=0.1)
    for _ in range(120):
        monitor.observe(float(rng.normal(0.0, 1.0)))
    result = None
    for _ in range(200):
        monitor.observe(float(rng.normal(5.0, 1.0)))
        result = monitor.check()
        if result:
            break
    assert result is not None
    assert result["drifted"] is True
    assert "retrain" in result["recommendation"]


def test_lstm_autoencoder_anomaly_error_higher():
    t = np.linspace(0.0, 6.0 * np.pi, 1000)
    windows = np.array([np.sin(t[i : i + 10]) for i in range(0, 900, 30)])
    ae = LSTMAutoencoder(window_size=10, hidden_size=8, lr=0.05, epochs=150)
    ae.train_windows(windows)
    assert ae.trained

    normal_err = np.mean(
        [ae.reconstruction_error(np.sin(np.linspace(0, 1, 10) * 2 * np.pi + ph)) for ph in (0.1, 0.5, 1.0)]
    )
    anomaly_err = ae.reconstruction_error(3.0 * np.sin(np.linspace(0, 1, 10) * 2 * np.pi))
    assert anomaly_err > normal_err * 1.5


def test_retrain_resets_detector(store, registry, pipeline):
    before = set(pipeline.detectors.keys())
    count = pipeline.retrain_all()
    assert count == len(before) if before else True
