"""
Event session manager — event lifecycle (triggered → updating → resolved) + merge logic
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from .config import MQTTConfig, CameraMQTTPublishConfig
from .mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


@dataclass
class EventSession:
    """Single event session"""
    event_id: str
    camera_id: str
    camera_name: str
    event_type: str  # "crowd" | "fight" | "fall"
    status: str = "triggered"  # "triggered" | "updating" | "resolved"
    created_at: float = 0.0
    last_update_time: float = 0.0
    last_publish_time: float = 0.0
    untriggered_frame_count: int = 0
    resolve_threshold: int = 10  # confirm_frames × 2
    latest_event_data: dict = field(default_factory=dict)
    track_ids: Set[int] = field(default_factory=set)
    image_url: str = ""


class EventSessionManager:
    """Event session manager — sits between BehaviorEngine and MQTTPublisher"""

    def __init__(self, mqtt_publisher: MQTTPublisher,
                 mqtt_config_repo, camera_repo):
        self._mqtt_publisher = mqtt_publisher
        self._mqtt_config_repo = mqtt_config_repo
        self._camera_repo = camera_repo
        self._sessions: Dict[str, EventSession] = {}
        self._lock = threading.Lock()

    def handle_event(self, event: dict, camera_config: dict) -> None:
        """Process events produced by BehaviorEngine"""
        try:
            # Three-level switch filtering
            if not self._should_process(event, camera_config):
                return

            with self._lock:
                self._handle_event_locked(event, camera_config)
        except Exception as e:
            logger.error(f"EventSessionManager.handle_event error: {e}")

    def tick_no_event(self, camera_id: str, untriggered_types: list) -> None:
        """Called when BehaviorEngine finishes processing a frame but certain event types were not triggered"""
        try:
            with self._lock:
                self._tick_no_event_locked(camera_id, untriggered_types)
        except Exception as e:
            logger.error(f"EventSessionManager.tick_no_event error: {e}")

    def get_active_session_count(self) -> int:
        """Return current active session count"""
        with self._lock:
            return len(self._sessions)

    # ── Internal methods ──

    def _should_process(self, event: dict, camera_config: dict) -> bool:
        """Three-level switch filtering: global → camera → event type"""
        # 1. Global MQTT switch
        mqtt_config = self._mqtt_config_repo.get()
        if not mqtt_config.enabled:
            return False

        # 2. Camera-level switch
        mqtt_publish = camera_config.get("mqtt_publish", {})
        if not mqtt_publish.get("enabled", False):
            return False

        # 3. Event type switch
        event_type = event.get("sub_type", "")
        if not mqtt_publish.get(event_type, True):
            return False

        return True

    def _handle_event_locked(self, event: dict, camera_config: dict) -> None:
        """Process event (lock already held)"""
        camera_id = event.get("camera_id", "")
        event_type = event.get("sub_type", "")
        now = time.time()

        # Try to match existing session
        session = self._match_session(event)

        if session:
            # Merge into existing session
            session.latest_event_data = event
            session.last_update_time = now
            session.untriggered_frame_count = 0
            session.image_url = event.get("image", "")

            # Update track_ids
            self._update_track_ids(session, event)

            # Check if updating message needs to be sent
            if self._should_send_updating(session):
                session.status = "updating"
                self._publish_message(session)
                session.last_publish_time = now
        else:
            # Create new session
            session = self._create_session(event, camera_config, now)
            self._sessions[session.event_id] = session
            self._publish_message(session)
            session.last_publish_time = now

    def _tick_no_event_locked(self, camera_id: str, untriggered_types: list) -> None:
        """Increment untriggered frame counter, check for resolved (lock already held)"""
        resolved_keys = []

        for key, session in self._sessions.items():
            if session.camera_id != camera_id:
                continue
            if session.event_type not in untriggered_types:
                continue

            session.untriggered_frame_count += 1

            if session.untriggered_frame_count >= session.resolve_threshold:
                session.status = "resolved"
                self._publish_message(session)
                resolved_keys.append(key)

        for key in resolved_keys:
            del self._sessions[key]

    def _match_session(self, event: dict) -> Optional[EventSession]:
        """Event merge matching logic"""
        camera_id = event.get("camera_id", "")
        event_type = event.get("sub_type", "")

        for session in self._sessions.values():
            if session.camera_id != camera_id:
                continue
            if session.event_type != event_type:
                continue

            if event_type == "crowd":
                # Crowd events from same camera are directly merged
                return session

            elif event_type == "fight":
                # Fight events: merge only if track_ids overlap
                event_track_ids = set()
                if "track_ids" in event:
                    event_track_ids = set(event.get("track_ids", []))
                elif "track_id" in event:
                    event_track_ids = {event["track_id"]}
                if session.track_ids & event_track_ids:
                    return session

            elif event_type == "fall":
                # Fall events: merge only if same track_id
                event_track_id = event.get("track_id", -1)
                if event_track_id in session.track_ids:
                    return session

        return None

    def _create_session(self, event: dict, camera_config: dict,
                        now: float) -> EventSession:
        """Create a new event session"""
        camera_id = event.get("camera_id", "")
        event_type = event.get("sub_type", "")
        camera_name = camera_config.get("name", camera_id)

        # Generate event_id
        dt = datetime.now(timezone.utc)
        event_id = f"evt_{camera_id}_{event_type}_{dt.strftime('%Y%m%d_%H%M%S')}"

        # Calculate resolve_threshold
        rules_config = camera_config.get("rules", {})
        type_config = rules_config.get(event_type, {})
        confirm_frames = type_config.get("confirm_frames", 5)
        resolve_threshold = confirm_frames * 2

        # Extract track_ids
        track_ids: Set[int] = set()
        if "track_ids" in event:
            track_ids = set(event["track_ids"])
        elif "track_id" in event:
            track_ids = {event["track_id"]}

        return EventSession(
            event_id=event_id,
            camera_id=camera_id,
            camera_name=camera_name,
            event_type=event_type,
            status="triggered",
            created_at=now,
            last_update_time=now,
            last_publish_time=0.0,
            untriggered_frame_count=0,
            resolve_threshold=resolve_threshold,
            latest_event_data=event,
            track_ids=track_ids,
            image_url=event.get("image", ""),
        )

    def _update_track_ids(self, session: EventSession, event: dict) -> None:
        """Update session track_ids"""
        if "track_ids" in event:
            session.track_ids.update(event["track_ids"])
        elif "track_id" in event:
            session.track_ids.add(event["track_id"])

    def _should_send_updating(self, session: EventSession) -> bool:
        """Check if an updating message needs to be sent"""
        mqtt_config = self._mqtt_config_repo.get()
        update_interval = mqtt_config.update_interval
        now = time.time()
        return (now - session.last_publish_time) >= update_interval

    def _publish_message(self, session: EventSession) -> None:
        """Build and publish MQTT message"""
        mqtt_config = self._mqtt_config_repo.get()
        if not mqtt_config.enabled or not mqtt_config.topic:
            return

        message = self._build_mqtt_message(session)
        self._mqtt_publisher.publish(mqtt_config.topic, message)

    def _build_mqtt_message(self, session: EventSession) -> dict:
        """Build MQTT JSON message body"""
        now = time.time()
        duration = now - session.created_at

        event = session.latest_event_data
        event_type = session.event_type

        # Build data field (by event type)
        data = {}
        if event_type == "crowd":
            data = {
                "count": event.get("count", 0),
                "track_ids": sorted(session.track_ids),
                "bbox": event.get("bbox", []),
                "confidence": event.get("confidence", 0.0),
            }
        elif event_type == "fight":
            data = {
                "involved_count": event.get("involved_count", 0),
                "track_ids": sorted(session.track_ids),
                "bbox": event.get("bbox", []),
                "avg_speed": event.get("avg_speed", 0.0),
            }
        elif event_type == "fall":
            data = {
                "track_id": event.get("track_id", -1),
                "bbox": event.get("bbox", []),
                "confidence": event.get("confidence", 0.0),
            }

        timestamp = datetime.now(timezone.utc).isoformat()

        return {
            "event_id": session.event_id,
            "status": session.status,
            "type": session.event_type,
            "camera_id": session.camera_id,
            "camera_name": session.camera_name,
            "timestamp": timestamp,
            "detail": event.get("detail", ""),
            "data": data,
            "image_url": session.image_url,
            "duration": round(duration, 1),
        }
