"""Streaming hub: in-process pub/sub that fans events, alerts, actions and drift
notices out to every connected WebSocket client (and optionally an MQTT broker).
This is what makes the dashboard live - no polling anywhere.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, Optional, Set

from core.config import Settings
from core.logging import get_logger

log = get_logger("sentinel.hub")

try:
    import paho.mqtt.client as mqtt  # type: ignore

    _HAVE_MQTT = True
except Exception:  # pragma: no cover
    _HAVE_MQTT = False


class StreamingHub:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.connections: Set[Any] = set()
        self._mqtt_client = None
        if settings.mqtt_enabled:
            self._init_mqtt()

    def _init_mqtt(self) -> None:
        if not _HAVE_MQTT:
            log.warning("paho-mqtt not installed; MQTT publisher disabled")
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.connect_async(self.settings.mqtt_broker, self.settings.mqtt_port)
        client.loop_start()
        self._mqtt_client = client
        log.info("mqtt publisher connected", extra={"broker": self.settings.mqtt_broker})

    async def publish(self, msg_type: str, **data: Any) -> None:
        payload = json.dumps({"type": msg_type, **data}, default=str)
        if self._mqtt_client is not None:
            try:
                self._mqtt_client.publish(self.settings.mqtt_topic, payload)
            except Exception as exc:
                log.error("mqtt publish failed", extra={"error": str(exc)})
        for ws in list(self.connections):
            try:
                await ws.send_text(payload)
            except Exception:
                self.connections.discard(ws)

    def register(self, websocket: Any) -> None:
        self.connections.add(websocket)

    def unregister(self, websocket: Any) -> None:
        self.connections.discard(websocket)
