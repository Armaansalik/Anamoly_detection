"""Explainability: feature-level contribution to a source's anomaly status.

A lightweight, dependency-free stand-in for SHAP: for each metric we compare
the latest reading against the source's own recent distribution (z-score) and
normalize so the contributions sum in magnitude to 1. The dashboard renders
these as a bar panel, answering "why did this flag?".
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from backend.storage import SQLiteStore
from core.logging import get_logger

log = get_logger("sentinel.explanations")


def explain_source(
    store: SQLiteStore,
    source_id: str,
    metric_units: Dict[str, str],
    latest: Dict[str, float],
    thresholds: Dict[str, Any] = None,
    limit: int = 200,
) -> Dict[str, Any]:
    thresholds = thresholds or {}
    contributions: List[Dict[str, Any]] = []
    for metric, value in latest.items():
        unit = metric_units.get(metric, "")
        rows = store.recent_events(source_id, metric, limit=limit)
        values = np.array([float(r["value"]) for r in rows], dtype=float)
        if values.size >= 10 and np.std(values) >= 1e-9:
            z = (value - np.mean(values)) / np.std(values)
            contribution = float(np.tanh(z / 3.0))
        else:
            spec = thresholds.get(metric)
            if spec and spec.get("critical", 0) > spec.get("warn", 0):
                warn, critical = spec["warn"], spec["critical"]
                excess = (value - warn) / (critical - warn)
                contribution = float(np.tanh(excess * 1.5))
            else:
                contribution = 0.0
        contributions.append({"metric": metric, "value": value, "unit": unit, "contribution": contribution})

    magnitude = sum(abs(c["contribution"]) for c in contributions) or 1.0
    for c in contributions:
        c["contribution"] = round(c["contribution"] / magnitude, 4)

    top = max(contributions, key=lambda c: abs(c["contribution"]), default=None)
    if top and abs(top["contribution"]) > 0.01:
        direction = "elevated" if top["contribution"] > 0 else "suppressed"
        summary = "Most influential metric is " + str(top["metric"]) + " (" + direction + ", contribution " + str(top["contribution"]) + ")."
    else:
        summary = "No metric is statistically unusual right now."

    return {"source_id": source_id, "contributions": contributions, "summary": summary}
