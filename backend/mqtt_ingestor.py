"""MQTT ingestion layer — receives real sensor data from ESP32 / edge devices.

Subscribe to topic: sentinel/sensors/{domain}/{source_id}
Payload format: {"metric_name": value, ...} or {"temperature": 82.5, "vibration": 3.1}

ESP32 sends JSON via PubSubClient to Mosquitto broker (port 1883).
This module bridges MQTT → the same AnomalyPipeline the REST API uses.
"""

from __future__ import annotations

import json
import threading
from typing import Any, Dict, Optional

from core.config import Settings
from core.logging import get_logger

log = get_logger("sentinel.mqtt")

try:
    import paho.mqtt.client as mqtt

    _HAVE_MQTT = True
except ImportError:
    _HAVE_MQTT = False


class MQTTIngestor:
    """Subscribes to MQTT topics and feeds sensor data into the pipeline."""

    def __init__(self, settings: Settings, registry, pipeline, storage):
        self.settings = settings
        self.registry = registry
        self.pipeline = pipeline
        self.storage = storage
        self._client: Optional[mqtt.Client] = None
        self._running = False

    def start(self) -> None:
        if not self.settings.mqtt_enabled or not _HAVE_MQTT:
            log.info("mqtt ingestion disabled", extra={"enabled": self.settings.mqtt_enabled, "available": _HAVE_MQTT})
            return

        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect
            self._client.connect_async(self.settings.mqtt_broker, self.settings.mqtt_port, keepalive=60)
            self._client.loop_start()
            self._running = True
            log.info(
                "mqtt ingestor started",
                extra={"broker": self.settings.mqtt_broker, "port": self.settings.mqtt_port},
            )
        except Exception as exc:
            log.error("mqtt ingestor failed to start", extra={"error": str(exc)})

    def stop(self) -> None:
        if self._client and self._running:
            self._client.loop_stop()
            self._client.disconnect()
            self._running = False
            log.info("mqtt ingestor stopped")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            log.info("mqtt connected to broker")
            client.subscribe("sentinel/sensors/#")
            client.subscribe("sentinel/+/+/data")
            log.info("mqtt subscribed to sentinel/sensors/# and sentinel/+/+/data")
        else:
            log.error("mqtt connection failed", extra={"rc": str(rc)})

    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        log.warning("mqtt disconnected", extra={"rc": str(rc)})

    def _on_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split("/")
            payload = json.loads(msg.payload.decode("utf-8"))

            if msg.topic.startswith("sentinel/sensors/"):
                domain = topic_parts[2] if len(topic_parts) > 2 else "manufacturing"
                source_id = topic_parts[3] if len(topic_parts) > 3 else "unknown"
                raw = payload
            elif len(topic_parts) >= 4 and topic_parts[0] == "sentinel":
                domain = topic_parts[1]
                source_id = topic_parts[2]
                raw = payload
            else:
                log.warning("mqtt unrecognized topic", extra={"topic": msg.topic})
                return

            if not isinstance(raw, dict):
                log.warning("mqtt payload not a dict", extra={"topic": msg.topic, "type": type(raw).__name__})
                return

            self._process_payload(domain, source_id, raw)

        except json.JSONDecodeError:
            log.warning("mqtt invalid JSON", extra={"topic": msg.topic})
        except Exception as exc:
            log.error("mqtt message processing error", extra={"error": str(exc), "topic": msg.topic})

    def _process_payload(self, domain: str, source_id: str, raw: Dict[str, Any]) -> None:
        import asyncio

        try:
            events = self.registry.adapt(domain, raw, source_id)
        except Exception as exc:
            log.warning("mqtt adapter failed", extra={"domain": domain, "error": str(exc)})
            return

        for event in events:
            self.storage.insert_event(event)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self.pipeline.process(event))
                else:
                    loop.run_until_complete(self.pipeline.process(event))
            except RuntimeError:
                asyncio.run(self.pipeline.process(event))

        log.info(
            "mqtt events ingested",
            extra={"domain": domain, "source_id": source_id, "count": len(events)},
        )
