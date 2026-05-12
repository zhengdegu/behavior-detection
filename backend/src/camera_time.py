"""
Camera time synchronization — correct event timestamps to match camera clock.

Strategies (in priority order):
1. Manual offset from database config (most reliable, user-configured)
2. ONVIF GetSystemDateAndTime (automatic, if camera supports it)
3. OSD OCR (read timestamp from video overlay, one-shot at startup)
4. Fallback: server time (offset = 0)

Usage:
    sync = CameraTimeSync()
    sync.register_camera("cam01", "rtsp://192.168.1.100:554/stream", manual_offset=-3600)
    sync.start()
    
    # In frame processing:
    camera_time = sync.get_camera_time("cam01")  # Returns corrected Unix timestamp
"""

import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# ONVIF GetSystemDateAndTime SOAP request body
_ONVIF_GET_TIME_SOAP = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
  <s:Body>
    <tds:GetSystemDateAndTime/>
  </s:Body>
</s:Envelope>"""

# Refresh interval for ONVIF time offset (seconds)
_REFRESH_INTERVAL = 300  # 5 minutes


def _extract_host_from_url(url: str) -> Optional[str]:
    """Extract host/IP from RTSP URL like rtsp://admin:pass@192.168.1.100:554/stream"""
    try:
        parsed = urlparse(url)
        return parsed.hostname
    except Exception:
        return None


def _parse_onvif_datetime(xml_text: str) -> Optional[datetime]:
    """Parse ONVIF GetSystemDateAndTime XML response to extract UTC datetime"""
    try:
        utc_match = re.search(r'<(?:tt:)?UTCDateTime>(.*?)</(?:tt:)?UTCDateTime>', xml_text, re.DOTALL)
        if not utc_match:
            return None

        utc_block = utc_match.group(1)

        hour = _extract_xml_int(utc_block, 'Hour')
        minute = _extract_xml_int(utc_block, 'Minute')
        second = _extract_xml_int(utc_block, 'Second')
        year = _extract_xml_int(utc_block, 'Year')
        month = _extract_xml_int(utc_block, 'Month')
        day = _extract_xml_int(utc_block, 'Day')

        if any(v is None for v in [hour, minute, second, year, month, day]):
            return None

        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    except Exception as e:
        logger.debug(f"Failed to parse ONVIF datetime: {e}")
        return None


def _extract_xml_int(xml_text: str, tag: str) -> Optional[int]:
    """Extract integer value from XML tag like <tt:Hour>14</tt:Hour>"""
    match = re.search(rf'<(?:tt:)?{tag}>(\d+)</(?:tt:)?{tag}>', xml_text)
    if match:
        return int(match.group(1))
    return None


def _query_onvif_time(host: str, port: int = 80, timeout: float = 5.0) -> Optional[datetime]:
    """Query camera system time via ONVIF GetSystemDateAndTime"""
    url = f"http://{host}:{port}/onvif/device_service"
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, content=_ONVIF_GET_TIME_SOAP, headers=headers)
            if resp.status_code == 200:
                camera_time = _parse_onvif_datetime(resp.text)
                if camera_time:
                    return camera_time
    except Exception:
        pass

    return None


class CameraTimeSyncEntry:
    """Time sync state for a single camera"""

    def __init__(self, camera_id: str, host: str, manual_offset: Optional[float] = None):
        self.camera_id = camera_id
        self.host = host
        self.manual_offset = manual_offset  # User-configured offset (highest priority)
        self.auto_offset: float = 0.0  # ONVIF-detected offset
        self.synced: bool = False
        self.last_sync_time: float = 0.0
        self.sync_failures: int = 0

    @property
    def offset(self) -> float:
        """Effective offset: manual takes priority over auto"""
        if self.manual_offset is not None:
            return self.manual_offset
        return self.auto_offset

    @property
    def is_configured(self) -> bool:
        """Whether this camera has a valid time offset (manual or auto)"""
        return self.manual_offset is not None or self.synced

    def needs_refresh(self) -> bool:
        """Check if ONVIF offset needs to be refreshed (skip if manual is set)"""
        if self.manual_offset is not None:
            return False  # Manual offset, no need for auto sync
        if not self.synced:
            return True
        return (time.time() - self.last_sync_time) > _REFRESH_INTERVAL


class CameraTimeSync:
    """
    Manages time synchronization for all cameras.
    
    Supports three modes:
    1. Manual offset: User configures offset_seconds in camera settings
    2. ONVIF auto-sync: Queries camera time via ONVIF protocol
    3. Fallback: Uses server time (offset = 0)
    """

    def __init__(self, onvif_port: int = 80, enable_onvif: bool = True):
        self._entries: Dict[str, CameraTimeSyncEntry] = {}
        self._lock = threading.Lock()
        self._onvif_port = onvif_port
        self._enable_onvif = enable_onvif
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False

    def register_camera(self, camera_id: str, rtsp_url: str,
                        manual_offset: Optional[float] = None) -> None:
        """
        Register a camera for time synchronization.
        
        Args:
            camera_id: Camera identifier
            rtsp_url: RTSP stream URL (used to extract camera IP for ONVIF)
            manual_offset: Manual time offset in seconds (camera_time - server_time).
                          Positive = camera is ahead, Negative = camera is behind.
                          If set, ONVIF auto-sync is skipped for this camera.
        """
        host = _extract_host_from_url(rtsp_url)
        if not host:
            logger.warning(f"[TimeSync] Cannot extract host from URL for camera {camera_id}")
            return

        with self._lock:
            entry = CameraTimeSyncEntry(camera_id, host, manual_offset)
            self._entries[camera_id] = entry

            if manual_offset is not None:
                logger.info(
                    f"[TimeSync] Camera {camera_id}: manual offset={manual_offset:+.1f}s "
                    f"(camera {'ahead' if manual_offset > 0 else 'behind'} by {abs(manual_offset):.1f}s)"
                )
            else:
                logger.info(f"[TimeSync] Camera {camera_id}: registered for ONVIF auto-sync (host={host})")

    def unregister_camera(self, camera_id: str) -> None:
        """Remove a camera from time synchronization"""
        with self._lock:
            self._entries.pop(camera_id, None)

    def update_manual_offset(self, camera_id: str, offset: Optional[float]) -> None:
        """Update manual offset for a camera (None to clear and use ONVIF)"""
        with self._lock:
            entry = self._entries.get(camera_id)
            if entry:
                entry.manual_offset = offset
                if offset is not None:
                    logger.info(f"[TimeSync] Camera {camera_id}: manual offset updated to {offset:+.1f}s")
                else:
                    logger.info(f"[TimeSync] Camera {camera_id}: manual offset cleared, using ONVIF")

    def start(self) -> None:
        """Start background ONVIF sync thread"""
        if self._running or not self._enable_onvif:
            return
        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info("[TimeSync] Background sync thread started")

    def stop(self) -> None:
        """Stop background sync thread"""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=10)

    def get_camera_time(self, camera_id: str) -> float:
        """
        Get the current camera time as a Unix timestamp.
        Returns server_time + offset (corrected to camera clock).
        If not synced and no manual offset, returns server time.
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
                    "host": entry.host,
                    "manual_offset": entry.manual_offset,
                    "auto_offset": entry.auto_offset,
                    "effective_offset": entry.offset,
                    "synced": entry.is_configured,
                    "source": "manual" if entry.manual_offset is not None else ("onvif" if entry.synced else "none"),
                })
            return results

    # ── Internal ──

    def _sync_loop(self) -> None:
        """Background loop that periodically syncs cameras via ONVIF"""
        time.sleep(2)
        self._sync_all()

        while self._running:
            time.sleep(30)
            self._sync_all()

    def _sync_all(self) -> None:
        """Sync all cameras that need ONVIF refresh"""
        with self._lock:
            entries = [e for e in self._entries.values() if e.needs_refresh()]

        for entry in entries:
            if not self._running:
                break
            self._do_onvif_sync(entry)

    def _do_onvif_sync(self, entry: CameraTimeSyncEntry) -> bool:
        """Perform ONVIF time sync for a single camera"""
        t_before = time.time()
        camera_time = _query_onvif_time(entry.host, self._onvif_port)
        t_after = time.time()

        if camera_time is None:
            entry.sync_failures += 1
            if entry.sync_failures <= 3:
                logger.warning(
                    f"[TimeSync] ONVIF failed for camera {entry.camera_id} "
                    f"(host={entry.host}, attempt={entry.sync_failures})"
                )
            elif entry.sync_failures == 4:
                logger.info(
                    f"[TimeSync] Camera {entry.camera_id}: ONVIF unavailable, "
                    f"using server time. Set manual offset in camera config if needed."
                )
            return False

        server_ref_time = (t_before + t_after) / 2.0
        camera_unix = camera_time.timestamp()
        offset = camera_unix - server_ref_time

        with self._lock:
            entry.auto_offset = offset
            entry.synced = True
            entry.last_sync_time = time.time()
            entry.sync_failures = 0

        logger.info(
            f"[TimeSync] Camera {entry.camera_id} ONVIF synced: offset={offset:+.1f}s"
        )
        return True
