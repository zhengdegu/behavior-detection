"""
Camera time synchronization — format event timestamps in camera's local timezone.

Simplified timezone-based approach:
- Each camera has a configured timezone (IANA format, e.g. 'Asia/Shanghai')
- Unix timestamps remain unchanged (always server/UTC time)
- Timezone is applied only when formatting timestamps for display or MQTT output

Usage:
    sync = CameraTimeSync()
    sync.register_camera("cam01", camera_timezone="Asia/Shanghai")
    
    # Format a timestamp in camera's timezone:
    iso_str = sync.format_timestamp("cam01", unix_ts)  # "2026-05-13T19:30:52+08:00"
    
    # Get timezone info:
    tz = sync.get_timezone("cam01")  # ZoneInfo('Asia/Shanghai') or None
"""

import logging
import threading
import time
from datetime import datetime, timezone as tz
from typing import Dict, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class CameraTimeSyncEntry:
    """Time sync state for a single camera"""

    def __init__(self, camera_id: str, camera_timezone: Optional[str] = None):
        self.camera_id = camera_id
        self.camera_timezone = camera_timezone
        self._zone_info: Optional[ZoneInfo] = None
        if camera_timezone:
            try:
                self._zone_info = ZoneInfo(camera_timezone)
            except Exception as e:
                logger.warning(f"[TimeSync] Invalid timezone '{camera_timezone}' for camera {camera_id}: {e}")

    @property
    def zone_info(self) -> Optional[ZoneInfo]:
        return self._zone_info

    @property
    def is_configured(self) -> bool:
        """Whether this camera has a valid timezone configured"""
        return self._zone_info is not None


class CameraTimeSync:
    """
    Manages timezone configuration for all cameras.
    
    Does NOT modify Unix timestamps. Only provides timezone info
    for formatting timestamps in the camera's local time.
    """

    def __init__(self):
        self._entries: Dict[str, CameraTimeSyncEntry] = {}
        self._lock = threading.Lock()

    def register_camera(self, camera_id: str, rtsp_url: str = "",
                        manual_offset: Optional[float] = None,
                        camera_timezone: Optional[str] = None) -> None:
        """
        Register a camera for timezone-aware timestamp formatting.
        
        Args:
            camera_id: Camera identifier
            rtsp_url: RTSP stream URL (kept for API compatibility, not used)
            manual_offset: Deprecated, kept for API compatibility
            camera_timezone: IANA timezone string (e.g. 'Asia/Shanghai')
        """
        with self._lock:
            entry = CameraTimeSyncEntry(camera_id, camera_timezone)
            self._entries[camera_id] = entry

            if camera_timezone and entry.is_configured:
                logger.info(f"[TimeSync] Camera {camera_id}: timezone={camera_timezone}")
            elif camera_timezone:
                logger.warning(f"[TimeSync] Camera {camera_id}: invalid timezone '{camera_timezone}', using server timezone")
            else:
                logger.info(f"[TimeSync] Camera {camera_id}: no timezone set, using server timezone")

    def unregister_camera(self, camera_id: str) -> None:
        """Remove a camera from time synchronization"""
        with self._lock:
            self._entries.pop(camera_id, None)

    def update_timezone(self, camera_id: str, camera_timezone: Optional[str]) -> None:
        """Update timezone for a camera. Auto-registers the camera if not already tracked."""
        with self._lock:
            new_entry = CameraTimeSyncEntry(camera_id, camera_timezone)
            self._entries[camera_id] = new_entry
            if camera_timezone:
                logger.info(f"[TimeSync] Camera {camera_id}: timezone updated to {camera_timezone}")
            else:
                logger.info(f"[TimeSync] Camera {camera_id}: timezone cleared, using server timezone")

    def update_manual_offset(self, camera_id: str, offset: Optional[float]) -> None:
        """Deprecated: kept for API compatibility. Use update_timezone instead."""
        pass

    def start(self) -> None:
        """No-op: timezone-based sync doesn't need a background thread"""
        pass

    def stop(self) -> None:
        """No-op"""
        pass

    def get_camera_time(self, camera_id: str) -> float:
        """
        Get the current time as a Unix timestamp.
        
        NOTE: Always returns server time (time.time()). Unix timestamps are
        timezone-independent. Use format_timestamp() or get_timezone() when
        you need timezone-aware output.
        """
        return time.time()

    def get_timezone(self, camera_id: str) -> Optional[ZoneInfo]:
        """Get the ZoneInfo for a camera, or None if not configured"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry and entry.is_configured:
                return entry.zone_info
        return None

    def get_timezone_str(self, camera_id: str) -> Optional[str]:
        """Get the timezone string for a camera, or None if not configured"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry:
                return entry.camera_timezone
        return None

    def format_timestamp(self, camera_id: str, unix_ts: float) -> str:
        """
        Format a Unix timestamp as ISO 8601 string in the camera's timezone.
        Falls back to server local timezone if camera timezone is not configured.
        """
        camera_tz = self.get_timezone(camera_id)
        if camera_tz:
            dt = datetime.fromtimestamp(unix_ts, tz=camera_tz)
        else:
            # Use server local timezone
            dt = datetime.fromtimestamp(unix_ts).astimezone()
        return dt.isoformat()

    def get_offset(self, camera_id: str) -> Tuple[float, bool]:
        """Get (offset_seconds_from_utc, is_configured) for a camera"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry and entry.is_configured:
                now = datetime.now(tz.utc)
                offset = now.astimezone(entry.zone_info).utcoffset().total_seconds()
                return offset, True
        return 0.0, False

    def get_all_status(self) -> list:
        """Get sync status for all cameras"""
        now = datetime.now(tz.utc)
        server_offset = datetime.now().astimezone().utcoffset().total_seconds()

        with self._lock:
            results = []
            for entry in self._entries.values():
                if entry.is_configured:
                    camera_offset = now.astimezone(entry.zone_info).utcoffset().total_seconds()
                    effective_offset = camera_offset - server_offset
                else:
                    effective_offset = 0.0

                results.append({
                    "camera_id": entry.camera_id,
                    "timezone": entry.camera_timezone,
                    "effective_offset": effective_offset,
                    "synced": entry.is_configured,
                    "source": "timezone" if entry.is_configured else "none",
                })
            return results
