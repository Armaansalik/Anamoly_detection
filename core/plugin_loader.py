"""Domain plugin loader — the extensibility core of the platform.

A plugin is a folder under <root>/plugins/<domain>/ containing:
    manifest.yaml    - metrics, thresholds, units, permitted actions
    adapter.py       - raw domain payload -> list[SensorEvent]
    actions.py       - permitted automated responses (execute + rollback)
    dashboard.json   - widget declarations for the UI

The core engine (layers 2-8) never imports domain-specific code; it only talks
to the Plugin/PluginAction abstractions below. Adding a new domain is: write a
plugin folder, no core changes.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from core.config import get_settings
from core.events import SensorEvent
from core.logging import get_logger

log = get_logger("sentinel.plugins")

ALLOWED_RISKS = ("low", "medium", "high")
REQUIRED_MANIFEST_FIELDS = ("name", "metrics", "actions")


@dataclass
class MetricSpec:
    name: str
    unit: str
    warn: float
    critical: float

    @property
    def thresholds(self) -> Dict[str, float]:
        return {"warn": self.warn, "critical": self.critical}


@dataclass
class PluginAction:
    id: str
    risk: str
    description: str
    execute: Callable[..., Dict[str, Any]]
    rollback: Optional[Callable[..., Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "risk": self.risk, "description": self.description}


@dataclass
class Plugin:
    name: str
    display_name: str
    description: str
    metrics: Dict[str, MetricSpec]
    actions: Dict[str, PluginAction]
    adapter: Any
    dashboard: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "metrics": [
                {"name": m.name, "unit": m.unit, "thresholds": m.thresholds}
                for m in self.metrics.values()
            ],
            "actions": [a.to_dict() for a in self.actions.values()],
            "dashboard": self.dashboard,
        }


class PluginError(Exception):
    pass


class PluginRegistry:
    """Loads every plugin folder under base_dir/plugins/* and exposes them."""

    def __init__(self, base_dir: Optional[Path] = None):
        settings = get_settings()
        base = Path(base_dir) if base_dir else settings.project_root
        self.plugins_dir = base / settings.plugins_dir
        self.plugins: Dict[str, Plugin] = {}
        self.errors: Dict[str, str] = {}

    def load(self) -> "PluginRegistry":
        if not self.plugins_dir.exists():
            log.error("plugins dir not found", extra={"path": str(self.plugins_dir)})
            return self
        for folder in sorted(self.plugins_dir.iterdir()):
            if not folder.is_dir() or folder.name.startswith((".", "_")):
                continue
            try:
                plugin = self._load_plugin_folder(folder)
                if plugin:
                    self.plugins[plugin.name] = plugin
                    log.info(
                        "plugin loaded",
                        extra={
                            "plugin": plugin.name,
                            "metrics": len(plugin.metrics),
                            "actions": len(plugin.actions),
                        },
                    )
            except Exception as exc:  # keep the platform alive if one plugin breaks
                self.errors[folder.name] = str(exc)
                log.error("failed to load plugin", extra={"plugin": folder.name, "error": str(exc)})
        return self

    def _load_plugin_folder(self, folder: Path) -> Optional[Plugin]:
        manifest_path = folder / "manifest.yaml"
        if not manifest_path.exists():
            raise PluginError("manifest.yaml missing")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        for field_name in REQUIRED_MANIFEST_FIELDS:
            if field_name not in manifest:
                raise PluginError(f"manifest missing required field: {field_name}")

        name = manifest["name"]
        metrics: Dict[str, MetricSpec] = {}
        for metric_name, spec in (manifest.get("metrics") or {}).items():
            metrics[metric_name] = MetricSpec(
                name=metric_name,
                unit=str(spec.get("unit", "")),
                warn=float(spec.get("warn", 0.0)),
                critical=float(spec.get("critical", 0.0)),
            )

        adapter_mod = importlib.import_module(f"plugins.{name}.adapter")
        adapter_cls = getattr(adapter_mod, "Adapter", None)
        if adapter_cls is None:
            raise PluginError(f"plugins/{name}/adapter.py must define class Adapter")
        adapter = adapter_cls()

        actions_mod = importlib.import_module(f"plugins.{name}.actions")
        actions: Dict[str, PluginAction] = {}
        for raw in actions_mod.get_actions():
            risk = raw.get("risk", "low")
            if risk not in ALLOWED_RISKS:
                raise PluginError(f"action {raw['id']}: invalid risk {risk!r}")
            actions[raw["id"]] = PluginAction(
                id=raw["id"],
                risk=risk,
                description=raw.get("description", ""),
                execute=raw["execute"],
                rollback=raw.get("rollback"),
            )

        dashboard: List[Dict[str, Any]] = []
        dash_path = folder / "dashboard.json"
        if dash_path.exists():
            dashboard = json.loads(dash_path.read_text(encoding="utf-8"))

        return Plugin(
            name=name,
            display_name=manifest.get("display_name", name),
            description=manifest.get("description", ""),
            metrics=metrics,
            actions=actions,
            adapter=adapter,
            dashboard=dashboard,
        )

    def get(self, domain: str) -> Plugin:
        if domain not in self.plugins:
            raise PluginError(f"unknown domain/plugin: {domain!r}")
        return self.plugins[domain]

    def adapt(self, domain: str, raw: Dict[str, Any], source_id: str) -> List[SensorEvent]:
        """Translate a raw domain payload into canonical events (no core coupling)."""
        plugin = self.get(domain)
        events = plugin.adapter.convert(raw, source_id)
        if not isinstance(events, (list, tuple)):
            raise PluginError(f"adapter for {domain!r} must return a list of SensorEvent")
        return list(events)
