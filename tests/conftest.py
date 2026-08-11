import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def registry():
    from core.plugin_loader import PluginRegistry

    return PluginRegistry(ROOT).load()


@pytest.fixture
def store(tmp_path):
    from backend.storage import SQLiteStore

    return SQLiteStore(tmp_path / "test.db")


class FakeAgent:
    def reason(self, incident, plugin):
        return {
            "action_id": "alert_operator",
            "risk": "low",
            "trace": ["guardrail=action verified against manifest"],
            "confidence": 0.9,
            "summary": "test decision",
        }


class FakeExecutor:
    def __init__(self):
        self.submissions = []

    async def submit(self, incident_id, action_id, plugin, trace, context):
        self.submissions.append((incident_id, action_id))


@pytest.fixture
def pipeline(store, registry):
    from backend.detection import AnomalyPipeline
    from backend.hub import StreamingHub
    from core.config import get_settings

    settings = get_settings()
    hub = StreamingHub(settings)
    return AnomalyPipeline(store, hub, registry, settings)
