"""
MQTT publisher — wraps paho-mqtt v2 client
"""

import json
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from .config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT publisher — connection management + message publishing"""

    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._connected: bool = False
        self._config: Optional[MQTTConfig] = None

    def connect(self, config: MQTTConfig) -> None:
        """Connect to MQTT Broker based on configuration"""
        if not config.host:
            logger.warning("MQTT Broker address is empty, skipping connection")
            return

        self._config = config

        try:
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"behavior-detection-{id(self)}",
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_publish = self._on_publish

            # Set authentication (if any)
            if config.username:
                self._client.username_pw_set(config.username, config.password)

            # Configure TLS (for port 8883 or explicit tls_enabled)
            if config.tls_enabled:
                import ssl
                if config.tls_insecure:
                    # Skip all certificate verification (self-signed certs)
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    self._client.tls_set_context(context)
                else:
                    # Verify server certificate against system CA store
                    context = ssl.create_default_context()
                    self._client.tls_set_context(context)
                logger.info("MQTT TLS enabled (insecure=%s)", config.tls_insecure)

            # Configure exponential backoff reconnection (1s ~ 60s)
            self._client.reconnect_delay_set(min_delay=1, max_delay=60)

            # Connect
            self._client.connect(config.host, config.port, keepalive=60)

            # Start network loop thread
            self._client.loop_start()

            logger.info(f"MQTT connecting: {config.host}:{config.port}")

        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self._connected = False

    def disconnect(self) -> None:
        """Gracefully disconnect"""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as e:
                logger.warning(f"MQTT disconnect error: {e}")
            finally:
                self._client = None
                self._connected = False
                logger.info("MQTT disconnected")

    def publish(self, topic: str, payload: dict) -> bool:
        """Publish JSON message to specified topic (QoS 1)"""
        if not self._client or not self._connected:
            event_id = payload.get("event_id", "unknown")
            logger.warning(f"MQTT not connected, message dropped: event_id={event_id}")
            return False

        try:
            message = json.dumps(payload, ensure_ascii=False, default=str)
            result = self._client.publish(
                topic,
                message.encode("utf-8"),
                qos=1,
            )
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                event_id = payload.get("event_id", "unknown")
                logger.error(f"MQTT publish failed: event_id={event_id}, rc={result.rc}")
                return False
            return True

        except Exception as e:
            event_id = payload.get("event_id", "unknown")
            logger.error(f"MQTT publish error: event_id={event_id}, error={e}")
            return False

    def is_connected(self) -> bool:
        """Return current connection status"""
        return self._connected

    def update_config(self, config: MQTTConfig) -> None:
        """Update configuration: disconnect old connection, reconnect with new config"""
        self.disconnect()
        if config.enabled and config.host:
            self.connect(config)

    # ── paho-mqtt v2 callbacks ──

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Connection success/failure callback"""
        if reason_code == 0:
            self._connected = True
            host = self._config.host if self._config else "unknown"
            port = self._config.port if self._config else 0
            logger.info(f"MQTT connected: {host}:{port}")
        else:
            self._connected = False
            logger.error(f"MQTT connection rejected: reason_code={reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Disconnect callback"""
        self._connected = False
        if reason_code != 0:
            logger.warning(f"MQTT connection lost (will auto-reconnect): reason_code={reason_code}")
        else:
            logger.info("MQTT connection closed normally")

    def _on_publish(self, client, userdata, mid, reason_codes, properties):
        """Message publish confirmation callback"""
        logger.debug(f"MQTT message published: mid={mid}")
