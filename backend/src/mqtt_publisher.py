"""
MQTT 发布器 — 封装 paho-mqtt v2 客户端
"""

import json
import logging
from typing import Optional

import paho.mqtt.client as mqtt

from .config import MQTTConfig

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT 发布器 — 连接管理 + 消息发布"""

    def __init__(self):
        self._client: Optional[mqtt.Client] = None
        self._connected: bool = False
        self._config: Optional[MQTTConfig] = None

    def connect(self, config: MQTTConfig) -> None:
        """根据配置连接 MQTT Broker"""
        if not config.host:
            logger.warning("MQTT Broker 地址为空，跳过连接")
            return

        self._config = config

        try:
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"behavior-detection-{id(self)}",
            )

            # 设置回调
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_publish = self._on_publish

            # 设置认证（如有）
            if config.username:
                self._client.username_pw_set(config.username, config.password)

            # 配置指数退避重连（1s ~ 60s）
            self._client.reconnect_delay_set(min_delay=1, max_delay=60)

            # 连接
            self._client.connect(config.host, config.port, keepalive=60)

            # 启动网络循环线程
            self._client.loop_start()

            logger.info(f"MQTT 正在连接: {config.host}:{config.port}")

        except Exception as e:
            logger.error(f"MQTT 连接失败: {e}")
            self._connected = False

    def disconnect(self) -> None:
        """优雅断开连接"""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception as e:
                logger.warning(f"MQTT 断开连接异常: {e}")
            finally:
                self._client = None
                self._connected = False
                logger.info("MQTT 已断开连接")

    def publish(self, topic: str, payload: dict) -> bool:
        """发布 JSON 消息到指定主题（QoS 1）"""
        if not self._client or not self._connected:
            event_id = payload.get("event_id", "unknown")
            logger.warning(f"MQTT 未连接，消息丢弃: event_id={event_id}")
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
                logger.error(f"MQTT 发布失败: event_id={event_id}, rc={result.rc}")
                return False
            return True

        except Exception as e:
            event_id = payload.get("event_id", "unknown")
            logger.error(f"MQTT 发布异常: event_id={event_id}, error={e}")
            return False

    def is_connected(self) -> bool:
        """返回当前连接状态"""
        return self._connected

    def update_config(self, config: MQTTConfig) -> None:
        """更新配置：断开旧连接，用新配置重连"""
        self.disconnect()
        if config.enabled and config.host:
            self.connect(config)

    # ── paho-mqtt v2 回调 ──

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """连接成功/失败回调"""
        if reason_code == 0:
            self._connected = True
            host = self._config.host if self._config else "unknown"
            port = self._config.port if self._config else 0
            logger.info(f"MQTT 已连接: {host}:{port}")
        else:
            self._connected = False
            logger.error(f"MQTT 连接被拒绝: reason_code={reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """断开连接回调"""
        self._connected = False
        if reason_code != 0:
            logger.warning(f"MQTT 连接断开（将自动重连）: reason_code={reason_code}")
        else:
            logger.info("MQTT 连接已正常断开")

    def _on_publish(self, client, userdata, mid, reason_codes, properties):
        """消息发布确认回调"""
        logger.debug(f"MQTT 消息已发布: mid={mid}")
