"""
Event session manager — event lifecycle (triggered → updating → resolved) + merge logic
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from .config import MQTTConfig, CameraMQTTPublishConfig
from .camera_time import CameraTimeSync
from .mqtt_publisher import MQTTPublisher

logger = logging.getLogger(__name__)


@dataclass
class EventSession:
    """Single event session"""
    event_id: str
    camera_id: str
    camera_name: str
    event_type: str  # "crowd" | "fight" | "fall" | "loiter"
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
                 mqtt_config_repo, camera_repo,
                 camera_time_sync: Optional[CameraTimeSync] = None,
                 session_repo=None):
        self._mqtt_publisher = mqtt_publisher
        self._mqtt_config_repo = mqtt_config_repo
        self._camera_repo = camera_repo
        self._camera_time_sync = camera_time_sync
        self._session_repo = session_repo  # MQTTSessionRepository for persistence
        self._sessions: Dict[str, EventSession] = {}
        self._lock = threading.Lock()
        # Cached MQTT config to avoid querying database every frame
        self._cached_mqtt_config: Optional[MQTTConfig] = None
        self._cached_mqtt_config_time: float = 0.0
        self._mqtt_config_cache_ttl: float = 5.0  # refresh every 5 seconds

        # Watchdog config
        self._watchdog_interval = 60.0  # check every 60 seconds
        self._max_session_age = 300.0   # force resolve after 5 minutes without update
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

        # Startup recovery: resolve stale sessions from previous run
        self._recover_stale_sessions()

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

    def force_resolve_camera(self, camera_id: str) -> None:
        """Force resolve all active sessions for a camera (called when analyzer stops)"""
        try:
            with self._lock:
                resolved_keys = []
                for key, session in self._sessions.items():
                    if session.camera_id != camera_id:
                        continue
                    session.status = "resolved"
                    self._publish_message(session)
                    self._delete_persisted_session(session.event_id)
                    resolved_keys.append(key)

                for key in resolved_keys:
                    del self._sessions[key]

                if resolved_keys:
                    logger.info(f"Force resolved {len(resolved_keys)} sessions for camera {camera_id}")
        except Exception as e:
            logger.error(f"force_resolve_camera error: {e}")

    def stop(self) -> None:
        """Stop watchdog thread (called on shutdown)"""
        self._watchdog_running = False

    # ── Internal methods ──

    def _recover_stale_sessions(self) -> None:
        """Startup recovery: resolve all sessions persisted from previous run"""
        if not self._session_repo:
            return
        try:
            stale_sessions = self._session_repo.get_all_active()
            if not stale_sessions:
                return

            logger.info(f"Recovering {len(stale_sessions)} stale MQTT sessions from previous run")
            mqtt_config = self._get_mqtt_config()

            resolved_count = 0
            for s in stale_sessions:
                # Build a minimal resolved message
                message = {
                    "event_id": s["event_id"],
                    "status": "resolved",
                    "type": s["event_type"],
                    "camera_id": s["camera_id"],
                    "camera_name": s["camera_name"],
                    "timestamp": self._format_event_timestamp(
                        s["camera_id"], time.time()),
                    "detail": "",
                    "data": {},
                    "image_url": "",
                    "duration": round(time.time() - s["created_at"], 1),
                }
                if mqtt_config.enabled and mqtt_config.topic:
                    self._mqtt_publisher.publish(mqtt_config.topic, message)
                resolved_count += 1

            # Clear all persisted sessions after recovery
            self._session_repo.delete_all()
            logger.info(f"Recovered and resolved {resolved_count} stale sessions")
        except Exception as e:
            logger.error(f"Session recovery failed: {e}")

    def _watchdog_loop(self) -> None:
        """Background watchdog: force resolve stale sessions that haven't been updated"""
        while self._watchdog_running:
            time.sleep(self._watchdog_interval)
            if not self._watchdog_running:
                break
            try:
                with self._lock:
                    now = time.time()
                    stale_keys = []
                    for key, session in self._sessions.items():
                        age = now - session.last_update_time
                        if age > self._max_session_age:
                            session.status = "resolved"
                            self._publish_message(session)
                            self._delete_persisted_session(session.event_id)
                            stale_keys.append(key)

                    for key in stale_keys:
                        del self._sessions[key]

                    if stale_keys:
                        logger.warning(f"Watchdog force resolved {len(stale_keys)} stale sessions")
            except Exception as e:
                logger.error(f"Session watchdog error: {e}")

    def _get_mqtt_config(self) -> MQTTConfig:
        """Get MQTT config with caching to avoid querying database every frame"""
        now = time.time()
        if (self._cached_mqtt_config is None or
                now - self._cached_mqtt_config_time > self._mqtt_config_cache_ttl):
            self._cached_mqtt_config = self._mqtt_config_repo.get()
            self._cached_mqtt_config_time = now
        return self._cached_mqtt_config

    def invalidate_mqtt_config_cache(self) -> None:
        """Invalidate cache when config is updated via API"""
        self._cached_mqtt_config = None
        self._cached_mqtt_config_time = 0.0

    def _should_process(self, event: dict, camera_config: dict) -> bool:
        """Three-level switch filtering: global → camera → event type"""
        # 1. Global MQTT switch
        mqtt_config = self._get_mqtt_config()
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
            # Persist to database for crash recovery
            self._persist_session(session)

    def _tick_no_event_locked(self, camera_id: str, untriggered_types: list) -> None:
        """Increment untriggered frame counter, check for resolved (lock already held)
        
        Uses time-based resolved detection: an event is resolved when it hasn't been
        triggered for longer than its cooldown period. This prevents premature resolved
        messages during cooldown gaps.
        """
        resolved_keys = []
        now = time.time()

        for key, session in self._sessions.items():
            if session.camera_id != camera_id:
                continue
            if session.event_type not in untriggered_types:
                continue

            session.untriggered_frame_count += 1

            # Time-based resolve: use time since last update instead of frame count
            # Resolve only after cooldown period has passed without new events
            time_since_last_update = now - session.last_update_time
            if time_since_last_update >= session.resolve_threshold:
                session.status = "resolved"
                if self._publish_message(session):
                    resolved_keys.append(key)
                    self._delete_persisted_session(session.event_id)
                else:
                    # Publish failed, revert status and retry next frame
                    session.status = "updating"
                    logger.warning(f"Resolved publish failed for {session.event_id}, will retry next frame")

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
                # Fight events: merge if any involved track_id overlaps with session
                event_track_ids = self._extract_all_track_ids(event)
                if session.track_ids & event_track_ids:
                    return session

            elif event_type == "fall":
                # Fall events: merge only if same track_id
                event_track_id = event.get("track_id", -1)
                if event_track_id in session.track_ids:
                    return session

            elif event_type == "loiter":
                # Loiter events: merge only if same track_id
                event_track_id = event.get("track_id", -1)
                if event_track_id in session.track_ids:
                    return session

        return None

    @staticmethod
    def _extract_all_track_ids(event: dict) -> Set[int]:
        """Extract all track_ids from an event (including involved_track_ids for fight)"""
        track_ids: Set[int] = set()
        if "track_ids" in event:
            track_ids.update(event["track_ids"])
        if "involved_track_ids" in event:
            track_ids.update(event["involved_track_ids"])
        if "track_id" in event:
            track_ids.add(event["track_id"])
        return track_ids

    def _create_session(self, event: dict, camera_config: dict,
                        now: float) -> EventSession:
        """Create a new event session"""
        camera_id = event.get("camera_id", "")
        event_type = event.get("sub_type", "")
        camera_name = camera_config.get("name", camera_id)

        # Generate event_id with millisecond precision + short UUID to avoid collision
        event_ts = event.get("timestamp", now)
        dt = datetime.fromtimestamp(event_ts, tz=timezone.utc)
        ms = int((event_ts % 1) * 1000)
        short_id = uuid.uuid4().hex[:6]
        event_id = f"evt_{camera_id}_{event_type}_{dt.strftime('%Y%m%d_%H%M%S')}_{ms:03d}_{short_id}"

        # Calculate resolve_threshold (in seconds, based on cooldown)
        # Use cooldown as the resolve time — event is resolved only after
        # no triggers for the full cooldown period
        rules_config = camera_config.get("rules", {})
        type_config = rules_config.get(event_type, {})
        cooldown = type_config.get("cooldown", 30)
        resolve_threshold = cooldown  # time-based (seconds)

        # Extract all track_ids (including involved participants for fight)
        track_ids: Set[int] = self._extract_all_track_ids(event)

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
        """Update session track_ids (includes all involved participants)"""
        session.track_ids.update(self._extract_all_track_ids(event))

    def _should_send_updating(self, session: EventSession) -> bool:
        """Check if an updating message needs to be sent"""
        mqtt_config = self._get_mqtt_config()
        update_interval = mqtt_config.update_interval
        now = time.time()
        return (now - session.last_publish_time) >= update_interval

    def _publish_message(self, session: EventSession) -> bool:
        """Build and publish MQTT message. Returns True if successful."""
        mqtt_config = self._get_mqtt_config()
        if not mqtt_config.enabled or not mqtt_config.topic:
            return True  # Config disabled is not a failure, allow cleanup

        message = self._build_mqtt_message(session)
        return self._mqtt_publisher.publish(mqtt_config.topic, message)

    # ── Persistence helpers ──

    def _persist_session(self, session: EventSession) -> None:
        """Persist session to database for crash recovery"""
        if not self._session_repo:
            return
        try:
            self._session_repo.save({
                "event_id": session.event_id,
                "camera_id": session.camera_id,
                "camera_name": session.camera_name,
                "event_type": session.event_type,
                "status": session.status,
                "created_at": session.created_at,
                "last_update_time": session.last_update_time,
                "resolve_threshold": session.resolve_threshold,
                "latest_event_data": session.latest_event_data,
                "track_ids": list(session.track_ids),
            })
        except Exception as e:
            logger.error(f"Failed to persist session {session.event_id}: {e}")

    def _delete_persisted_session(self, event_id: str) -> None:
        """Remove session from persistence after resolved is sent"""
        if not self._session_repo:
            return
        try:
            self._session_repo.delete(event_id)
        except Exception as e:
            logger.error(f"Failed to delete persisted session {event_id}: {e}")

    # ── MQTT message building ──

    def _build_mqtt_message(self, session: EventSession) -> dict:
        """Build MQTT JSON message body"""
        now = time.time()
        duration = now - session.created_at

        event = session.latest_event_data
        event_type = session.event_type

        # Build data field (by event type)
        data = {}
        if event_type == "crowd":
            count = event.get("count", 0)
            data = {
                "count": count,
                "track_ids": sorted(session.track_ids),
                "bbox": event.get("bbox", []),
                # Crowd confidence: ratio of detected count to threshold
                # (capped at 1.0, higher count = higher confidence)
                "confidence": round(min(count / max(event.get("max_count", 5), 1), 1.0), 2) if count > 0 else 0.0,
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

        timestamp = self._format_event_timestamp(session.camera_id, event.get("timestamp", time.time()))

        return {
            "event_id": session.event_id,
            "status": session.status,
            "type": session.event_type,
            "camera_id": session.camera_id,
            "camera_name": session.camera_name,
            "timestamp": timestamp,
            "detail": event.get("detail", ""),
            "data": data,
            "image_url": f"/events/{session.image_url}" if session.image_url else "",
            "duration": round(duration, 1),
        }

    def _format_event_timestamp(self, camera_id: str, unix_ts: float) -> str:
        """Format Unix timestamp as ISO 8601 in camera's timezone (or server local timezone)"""
        if self._camera_time_sync:
            return self._camera_time_sync.format_timestamp(camera_id, unix_ts)
        # Fallback: server local timezone
        dt = datetime.fromtimestamp(unix_ts).astimezone()
        return dt.isoformat()
