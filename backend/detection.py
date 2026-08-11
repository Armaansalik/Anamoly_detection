"""Layer 5 - ML detection: Isolation Forest + rolling z-score + (optional)
numpy LSTM autoencoder + drift monitor. Layer 6/7 wiring: AnomalyPipeline
creates incidents, asks the agent, and submits actions to the executor.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest

from backend.storage import SQLiteStore
from core.config import Settings
from core.events import SensorEvent
from core.logging import get_logger
from core.plugin_loader import PluginRegistry

log = get_logger("sentinel.detection")


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class RollingDetector:
    """Per (source, metric) detector: Isolation Forest + rolling z-score.

    Scores in [0, 1]. Warmup requires a minimum buffer; before that returns 0.
    The isolation forest is refit on the value history periodically (never
    including the value currently being scored).
    """

    def __init__(self, train_window: int = 100, z_window: int = 60, min_warmup: int = 40):
        self.train_window = train_window
        self.z_window = z_window
        self.min_warmup = min_warmup
        self.values: Deque[float] = deque(maxlen=train_window + z_window + 10)
        self.model: Optional[IsolationForest] = None
        self.last_score: float = 0.0

    def is_warm(self) -> bool:
        return len(self.values) >= self.min_warmup

    def update(self, value: float) -> float:
        self.values.append(value)
        score = self._score()
        self.last_score = score
        return score

    def _score(self) -> float:
        data = list(self.values)
        if len(data) < self.min_warmup:
            return 0.0
        current = data[-1]
        hist = data[:-1]
        recent = hist[-self.z_window:]
        mean = float(np.mean(recent))
        std = float(np.std(recent))
        z = (current - mean) / (std + 1e-9)
        z_score = _sigmoid(abs(z) - 3.0)

        if len(hist) >= 20 and (self.model is None or len(self.values) % 20 == 0):
            self.model = IsolationForest(
                n_estimators=50, contamination=0.05, random_state=42
            ).fit(np.asarray(hist, dtype=float).reshape(-1, 1))

        if_score = 0.0
        if self.model is not None:
            raw = float(self.model.decision_function(np.array([[current]]))[0])
            if_score = float(np.clip(0.5 - raw, 0.0, 1.0))
        return max(z_score, if_score)

    def refit(self) -> None:
        self.model = None


class DriftMonitor:
    """KL-divergence drift detector between the training and live distributions.

    When the EMA of the KL divergence between the reference (training) and live
    distributions exceeds the threshold, the platform flags drift and logs a
    retraining recommendation (it does not silently retrain).
    """

    def __init__(
        self,
        warmup: int = 120,
        smoothing: float = 0.05,
        kl_threshold: float = 0.10,
        bins: int = 20,
    ):
        self.warmup = warmup
        self.smoothing = smoothing
        self.kl_threshold = kl_threshold
        self.bins = bins
        self.reference: Deque[float] = deque(maxlen=warmup)
        self.live: Deque[float] = deque(maxlen=300)
        self.ema: float = 0.0
        self.drifted: bool = False

    def observe(self, value: float) -> None:
        if len(self.reference) < self.reference.maxlen:
            self.reference.append(value)
        else:
            self.live.append(value)

    def check(self) -> Optional[Dict[str, Any]]:
        if len(self.reference) < 60 or len(self.live) < 30:
            return None
        kl = self._kl_divergence()
        self.ema = self.smoothing * kl + (1.0 - self.smoothing) * self.ema
        if not self.drifted and self.ema > self.kl_threshold:
            self.drifted = True
            return {
                "kl": round(self.ema, 4),
                "drifted": True,
                "recommendation": "Data distribution diverged from training data; retrain the model (POST /api/v1/models/retrain).",
            }
        if self.drifted and self.ema < self.kl_threshold * 0.5:
            self.drifted = False
        return None

    def _kl_divergence(self) -> float:
        ref = np.asarray(list(self.reference), dtype=float)
        live = np.asarray(list(self.live), dtype=float)
        lo = min(float(ref.min()), float(live.min()))
        hi = max(float(ref.max()), float(live.max()))
        if hi - lo < 1e-9:
            hi = lo + 1.0
        edges = np.linspace(lo, hi, self.bins + 1)
        p = np.histogram(live, bins=edges, density=True)[0]
        q = np.histogram(ref, bins=edges, density=True)[0]
        p = p + 1e-9
        q = q + 1e-9
        return float(np.sum(p * np.log(p / q)))

    def reset(self) -> None:
        self.reference.extend(list(self.live))
        self.live.clear()
        self.ema = 0.0
        self.drifted = False


class LSTMAutoencoder:
    """Minimal numpy LSTM autoencoder for sequence reconstruction error.

    Encodes a window with one LSTM layer, decodes the final hidden state with a
    linear layer back to the full window. Windows unlike the training
    distribution reconstruct poorly - that error is the anomaly signal.
    Trained with full BPTT in pure numpy (no torch dependency).
    """

    def __init__(self, window_size: int = 10, hidden_size: int = 8, lr: float = 0.05, epochs: int = 150):
        self.T = window_size
        self.H = hidden_size
        self.lr = lr
        self.epochs = epochs
        self.mean: float = 0.0
        self.std: float = 1.0
        scale = 0.2
        rng = np.random.default_rng(7)
        self.Wf, self.Uf, self.bf = rng.normal(0, scale, self.H), rng.normal(0, scale, (self.H, self.H)), np.zeros(self.H)
        self.Wi, self.Ui, self.bi = rng.normal(0, scale, self.H), rng.normal(0, scale, (self.H, self.H)), np.zeros(self.H)
        self.Wg, self.Ug, self.bg = rng.normal(0, scale, self.H), rng.normal(0, scale, (self.H, self.H)), np.zeros(self.H)
        self.Wo, self.Uo, self.bo = rng.normal(0, scale, self.H), rng.normal(0, scale, (self.H, self.H)), np.zeros(self.H)
        self.Wout = rng.normal(0, scale, (self.T, self.H))
        self.bout = np.zeros(self.T)
        self.trained = False

    @staticmethod
    def _sig(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def _forward(self, xs: np.ndarray) -> Tuple[np.ndarray, Dict[int, Dict[str, np.ndarray]]]:
        h = np.zeros(self.H)
        c = np.zeros(self.H)
        states: Dict[int, Dict[str, np.ndarray]] = {}
        for t in range(self.T):
            x = xs[t]
            f = self._sig(self.Wf * x + self.Uf @ h + self.bf)
            i = self._sig(self.Wi * x + self.Ui @ h + self.bi)
            g = np.tanh(self.Wg * x + self.Ug @ h + self.bg)
            o = self._sig(self.Wo * x + self.Uo @ h + self.bo)
            c = f * c + i * g
            h = o * np.tanh(c)
            states[t] = {"h": h, "c": c, "f": f, "i": i, "g": g, "o": o, "x": x, "h_prev": h}
        recon = self.Wout @ h + self.bout
        return recon, states

    def train_windows(self, windows: np.ndarray) -> None:
        windows = np.asarray(windows, dtype=float)
        if windows.ndim == 1:
            windows = windows.reshape(1, -1)
        if windows.shape[1] != self.T:
            windows = windows[:, : self.T]
        if len(windows) == 0:
            return
        self.mean = float(np.mean(windows))
        self.std = float(np.std(windows)) + 1e-9
        x_norm = (windows - self.mean) / self.std
        for _ in range(self.epochs):
            gWf = np.zeros_like(self.Wf)
            gUf = np.zeros_like(self.Uf)
            gbf = np.zeros_like(self.bf)
            gWi = np.zeros_like(self.Wi)
            gUi = np.zeros_like(self.Ui)
            gbi = np.zeros_like(self.bi)
            gWg = np.zeros_like(self.Wg)
            gUg = np.zeros_like(self.Ug)
            gbg = np.zeros_like(self.bg)
            gWo = np.zeros_like(self.Wo)
            gUo = np.zeros_like(self.Uo)
            gbo = np.zeros_like(self.bo)
            gWout = np.zeros_like(self.Wout)
            gbout = np.zeros_like(self.bout)
            for sample in x_norm:
                recon, states = self._forward(sample)
                d_recon = 2.0 * (recon - sample)
                gWout += np.outer(d_recon, states[self.T - 1]["h"])
                gbout += d_recon
                delta_h = self.Wout.T @ d_recon
                delta_c_next = np.zeros(self.H)
                for t in range(self.T - 1, -1, -1):
                    st = states[t]
                    dc_from_h = delta_h * st["o"] * (1.0 - np.tanh(st["c"]) ** 2)
                    delta_c = dc_from_h + delta_c_next
                    d_o = delta_h * np.tanh(st["c"]) * st["o"] * (1.0 - st["o"])
                    c_prev = np.zeros(self.H) if t == 0 else states[t - 1]["c"]
                    h_prev = np.zeros(self.H) if t == 0 else states[t - 1]["h"]
                    d_f = delta_c * c_prev * st["f"] * (1.0 - st["f"])
                    d_i = delta_c * st["g"] * st["i"] * (1.0 - st["i"])
                    d_g = delta_c * st["i"] * (1.0 - st["g"] ** 2)
                    x = st["x"]
                    gWf += d_f * x
                    gUf += np.outer(d_f, h_prev)
                    gbf += d_f
                    gWi += d_i * x
                    gUi += np.outer(d_i, h_prev)
                    gbi += d_i
                    gWg += d_g * x
                    gUg += np.outer(d_g, h_prev)
                    gbg += d_g
                    gWo += d_o * x
                    gUo += np.outer(d_o, h_prev)
                    gbo += d_o
                    delta_h = self.Uf.T @ d_f + self.Ui.T @ d_i + self.Ug.T @ d_g + self.Uo.T @ d_o
                    delta_c_next = delta_c * st["f"]
            n = len(x_norm)
            self.Wf -= self.lr * gWf / n
            self.Uf -= self.lr * gUf / n
            self.bf -= self.lr * gbf / n
            self.Wi -= self.lr * gWi / n
            self.Ui -= self.lr * gUi / n
            self.bi -= self.lr * gbi / n
            self.Wg -= self.lr * gWg / n
            self.Ug -= self.lr * gUg / n
            self.bg -= self.lr * gbg / n
            self.Wo -= self.lr * gWo / n
            self.Uo -= self.lr * gUo / n
            self.bo -= self.lr * gbo / n
            self.Wout -= self.lr * gWout / n
            self.bout -= self.lr * gbout / n
        self.trained = True

    def reconstruction_error(self, window: np.ndarray) -> float:
        window = np.asarray(window, dtype=float)[: self.T]
        if len(window) < self.T:
            return 0.0
        x_norm = (window - self.mean) / self.std
        recon, _ = self._forward(x_norm)
        return float(np.mean((recon - x_norm) ** 2))

    def score(self, window: np.ndarray) -> float:
        if not self.trained:
            return 0.0
        err = self.reconstruction_error(window)
        return float(np.clip(err / (err + 0.5), 0.0, 1.0))


class AnomalyPipeline:
    """Orchestrates detection -> incident -> agent -> action for every event."""

    def __init__(self, store: SQLiteStore, hub, registry: PluginRegistry, settings: Settings):
        self.store = store
        self.hub = hub
        self.registry = registry
        self.settings = settings
        self.detectors: Dict[Tuple[str, str], RollingDetector] = {}
        self.drift_monitors: Dict[Tuple[str, str], DriftMonitor] = {}
        self.lstm: Dict[Tuple[str, str], LSTMAutoencoder] = {}
        self.lstm_windows: Dict[Tuple[str, str], Deque[np.ndarray]] = {}
        self.latest: Dict[str, Dict[str, float]] = {}
        self.source_scores: Dict[str, float] = {}

    async def process(self, event: SensorEvent, executor=None, agent=None) -> Optional[Dict[str, Any]]:
        """Returns the created incident dict, or None if no anomaly."""
        key = (event.source_id, event.metric_name)
        self.latest.setdefault(event.source_id, {})[event.metric_name] = event.value

        detector = self.detectors.setdefault(
            key,
            RollingDetector(self.settings.detection_train_window, self.settings.detection_z_window),
        )
        ml_score = detector.update(event.value)

        drift = self.drift_monitors.setdefault(
            key, DriftMonitor(warmup=self.settings.drift_warmup, kl_threshold=self.settings.drift_alpha)
        )
        drift.observe(event.value)
        drift_hit = drift.check()
        if drift_hit:
            self.store.insert_drift(event.source_id, event.metric_name, drift_hit["kl"], drift_hit["recommendation"])
            await self.hub.publish("drift", source_id=event.source_id, metric=event.metric_name, **drift_hit)

        lstm_score = 0.0
        if self.settings.enable_lstm_ae:
            lstm_score = self._lstm_update(event)

        combined = max(ml_score, lstm_score)

        plugin = self.registry.get(event.domain)
        metric_spec = plugin.metrics.get(event.metric_name)
        critical_hit = metric_spec is not None and event.value >= metric_spec.critical
        warn_hit = metric_spec is not None and event.value >= metric_spec.warn

        if combined >= self.settings.anomaly_score_threshold or critical_hit or (warn_hit and combined >= 0.4):
            incident = await self._create_incident(event, combined, critical_hit, executor, agent)
            return incident
        return None

    def _lstm_update(self, event: SensorEvent) -> float:
        key = (event.source_id, event.metric_name)
        windows = self.lstm_windows.setdefault(key, deque(maxlen=40))
        model = self.lstm.setdefault(key, LSTMAutoencoder())
        if not model.trained:
            if len(windows) >= 30:
                model.train_windows(np.asarray(list(windows), dtype=float))
            windows.append(event.value)
            return 0.0
        windows.append(event.value)
        return model.score(np.asarray(list(windows), dtype=float))

    async def _create_incident(self, event: SensorEvent, combined: float, critical_hit: bool, executor, agent) -> Dict[str, Any]:
        plugin = self.registry.get(event.domain)
        metric_spec = plugin.metrics.get(event.metric_name)
        severity = "high" if critical_hit or combined >= 0.8 else "medium"
        unit = metric_spec.unit if metric_spec else ""
        message = (
            f"{event.source_id}: {event.metric_name} = {event.value:.2f} {unit} "
            f"outside expected range (ML score {combined:.2f})"
        )
        incident = {
            "source_id": event.source_id,
            "domain": event.domain,
            "created_at": event.timestamp.isoformat(),
            "anomaly_score": round(combined, 4),
            "severity": severity,
            "status": "open",
            "message": message,
            "metrics": {event.metric_name: event.value},
        }
        incident_id = self.store.insert_incident(incident)
        incident["id"] = incident_id
        self.source_scores[event.source_id] = max(self.source_scores.get(event.source_id, 0.0), combined)

        decision = agent.reason(incident, plugin)
        incident["agent_trace"] = decision["trace"]
        incident["action"] = {
            "id": decision["action_id"],
            "risk": decision["risk"],
            "description": plugin.actions[decision["action_id"]].description,
            "status": "queued",
        }
        self.store.update_incident(incident_id, status="open", agent_trace=decision["trace"], action=incident["action"])

        await executor.submit(
            incident_id,
            decision["action_id"],
            plugin,
            decision["trace"],
            {"source_id": event.source_id, "event": event, "message": message},
        )
        incident = self.store.get_incident(incident_id)
        await self.hub.publish("alert", incident=incident)
        log.warning(
            "incident created",
            extra={
                "incident_id": incident_id,
                "source_id": event.source_id,
                "metric": event.metric_name,
                "score": combined,
                "severity": severity,
            },
        )
        return incident

    def sources_status(self) -> List[Dict[str, Any]]:
        result = []
        for source_id, metrics in self.latest.items():
            score = self.source_scores.get(source_id, 0.0)
            health = max(0.0, 1.0 - score)
            if health < 0.55:
                status = "critical"
            elif health < 0.85:
                status = "warning"
            else:
                status = "healthy"
            result.append(
                {
                    "id": source_id,
                    "domain": self._domain_for(source_id),
                    "health_score": round(health, 3),
                    "status": status,
                    "latest": metrics,
                    "updated_at": self.store.sources_summary().get(source_id, {}).get("updated_at"),
                }
            )
        return result

    def _domain_for(self, source_id: str) -> str:
        summary = self.store.sources_summary().get(source_id)
        if summary:
            return summary["domain"]
        for key in self.detectors:
            if key[0] == source_id:
                return self.registry.get("manufacturing").name
        return "unknown"

    def retrain_all(self) -> int:
        count = 0
        for key, detector in self.detectors.items():
            detector.refit()
            count += 1
        for key, monitor in self.drift_monitors.items():
            monitor.reset()
        for key, model in self.lstm.items():
            model.trained = False
            windows = self.lstm_windows.get(key, deque(maxlen=40))
            if len(windows) >= 30:
                model.train_windows(np.asarray(list(windows), dtype=float))
        log.info("models retrained", extra={"detectors": count})
        return count
