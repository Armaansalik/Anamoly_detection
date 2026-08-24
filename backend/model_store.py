"""ML model persistence — save/load trained models to disk.

Prevents cold-start retraining on every server restart. Models are saved
per (source_id, metric) in a JSON format using numpy serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from core.config import get_settings
from core.logging import get_logger

log = get_logger("sentinel.model_store")


class ModelStore:
    """Persists ML model parameters to disk for fast reload."""

    def __init__(self, base_dir: Optional[Path] = None):
        settings = get_settings()
        self.base_dir = Path(base_dir) if base_dir else settings.db_path.parent / "models"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, source_id: str, metric_name: str) -> Path:
        safe_name = f"{source_id}_{metric_name}".replace("/", "_").replace("\\", "_")
        return self.base_dir / f"{safe_name}.json"

    def save_iforest(self, source_id: str, metric_name: str, model: Any) -> bool:
        try:
            params = {
                "type": "iforest",
                "estimators": [],
                "offset": float(model.offset_) if hasattr(model, "offset_") else 0.0,
                "threshold": float(model.threshold_) if hasattr(model, "threshold_") else -0.5,
            }
            for est in model.estimators_:
                tree = est.tree_
                params["estimators"].append({
                    "feature": tree.feature.tolist(),
                    "threshold": tree.threshold.tolist(),
                    "children_left": tree.children_left.tolist(),
                    "children_right": tree.children_right.tolist(),
                    "n_node_samples": tree.n_node_samples.tolist(),
                    "impurity": tree.impurity.tolist(),
                })
            path = self._key_path(source_id, metric_name)
            path.write_text(json.dumps(params), encoding="utf-8")
            log.info("model saved", extra={"source_id": source_id, "metric": metric_name, "path": str(path)})
            return True
        except Exception as exc:
            log.warning("model save failed", extra={"error": str(exc)})
            return False

    def load_iforest(self, source_id: str, metric_name: str) -> Optional[Dict[str, Any]]:
        path = self._key_path(source_id, metric_name)
        if not path.exists():
            return None
        try:
            params = json.loads(path.read_text(encoding="utf-8"))
            log.info("model loaded", extra={"source_id": source_id, "metric": metric_name})
            return params
        except Exception as exc:
            log.warning("model load failed", extra={"error": str(exc)})
            return None

    def save_drift_baseline(self, source_id: str, metric_name: str, values: list) -> bool:
        try:
            path = self._key_path(source_id, f"{metric_name}_drift_baseline")
            params = {"values": list(values[-200:])}
            path.write_text(json.dumps(params), encoding="utf-8")
            return True
        except Exception:
            return False

    def load_drift_baseline(self, source_id: str, metric_name: str) -> Optional[list]:
        path = self._key_path(source_id, f"{metric_name}_drift_baseline")
        if not path.exists():
            return None
        try:
            params = json.loads(path.read_text(encoding="utf-8"))
            return params.get("values", [])
        except Exception:
            return None

    def list_models(self) -> list:
        return [f.stem for f in self.base_dir.glob("*.json")]
