"""
Camera time synchronization — correct event timestamps to match camera clock.

Simplified timezone-based approach:
- Each camera has a configured timezone (IANA format, e.g. 'Asia/Shanghai')
- Offset is calculated as: camera_local_time - server_local_time
- If no timezone is configured, server time is used (offset = 0)

Usage:
    sync = CameraTimeSync()
    sync.register_camera("cam01", timezone="Asia/Shanghai")
    
    # In frame processing:
    camera_time = sync.get_camera_time("cam01")  # Returns corrected Unix timestamp
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


def _get_timezone_offset_seconds(timezone_str: str) -> float:
    """
    Calculate the offset in seconds between the given timezone and the server's local timezone.
    Returns: camera_utc_offset - server_utc_offset (in seconds)
    """
    now = datetime.now(tz.utc)
    
    # Camera's UTC offset
    camera_tz = ZoneInfo(timezone_str)
    camera_offset = now.astimezone(camera_tz).utcoffset().total_seconds()
    
    # Server's UTC offset (local timezone)
    server_offset = datetime.now().astimezone().utcoffset().total_seconds()
    
    return camera_offset - server_offset


class CameraTimeSyncEntry:
    """Time sync state for a single camera"""

    def __init__(self, camera_id: str, camera_timezone: Optional[str] = None):
        self.camera_id = camera_id
        self.camera_timezone = camera_timezone

    @property
    def offset(self) -> float:
        """Calculate effective offset based on timezone difference"""
        if self.camera_timezone:
            try:
                return _get_timezone_offset_seconds(self.camera_timezone)
            except Exception as e:
                logger.warning(f"[TimeSync] Invalid timezone '{self.camera_timezone}' for camera {self.camera_id}: {e}")
                return 0.0
        return 0.0

    @property
    def is_configured(self) -> bool:
        """Whether this camera has a valid timezone configured"""
        return self.camera_timezone is not None


class CameraTimeSync:
    """
    Manages time synchronization for all cameras using timezone configuration.
    """

    def __init__(self):
        self._entries: Dict[str, CameraTimeSyncEntry] = {}
        self._lock = threading.Lock()

    def register_camera(self, camera_id: str, rtsp_url: str = "",
                        manual_offset: Optional[float] = None,
                        camera_timezone: Optional[str] = None) -> None:
        """
        Register a camera for time synchronization.
        
        Args:
            camera_id: Camera identifier
            rtsp_url: RTSP stream URL (kept for API compatibility, not used)
            manual_offset: Deprecated, kept for API compatibility
            camera_timezone: IANA timezone string (e.g. 'Asia/Shanghai')
        """
        with self._lock:
            entry = CameraTimeSyncEntry(camera_id, camera_timezone)
            self._entries[camera_id] = entry

            if camera_timezone:
                offset = entry.offset
                logger.info(
                    f"[TimeSync] Camera {camera_id}: timezone={camera_timezone}, "
                    f"offset={offset:+.0f}s vs server"
                )
            else:
                logger.info(f"[TimeSync] Camera {camera_id}: no timezone set, using server time")

    def unregister_camera(self, camera_id: str) -> None:
        """Remove a camera from time synchronization"""
        with self._lock:
            self._entries.pop(camera_id, None)

    def update_timezone(self, camera_id: str, camera_timezone: Optional[str]) -> None:
        """Update timezone for a camera"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry:
                entry.camera_timezone = camera_timezone
                if camera_timezone:
                    logger.info(f"[TimeSync] Camera {camera_id}: timezone updated to {camera_timezone}")
                else:
                    logger.info(f"[TimeSync] Camera {camera_id}: timezone cleared, using server time")

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
        Get the current camera time as a Unix timestamp.
        Returns server_time + offset (corrected to camera clock).
        """
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry and entry.is_configured:
                return time.time() + entry.offset
        return time.time()

    def get_offset(self, camera_id: str) -> Tuple[float, bool]:
        """Get (offset_seconds, is_configured) for a camera"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry:
                return entry.offset, entry.is_configured
        return 0.0, False

    def get_all_status(self) -> list:
        """Get sync status for all cameras"""
        with self._lock:
            results = []
            for entry in self._entries.values():
                results.append({
                    "camera_id": entry.camera_id,
                    "timezone": entry.camera_timezone,
                    "effective_offset": entry.offset,
                    "synced": entry.is_configured,
                    "source": "timezone" if entry.camera_timezone else "none",
                })
            return results
