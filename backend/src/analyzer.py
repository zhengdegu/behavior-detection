"""
Video analysis pipeline — pull stream → detect+track → behavior rule engine → events
One Analyzer thread per camera.

RTSP streams use ffmpeg subprocess (inspired by warehouse-vision / Frigate architecture),
local files use OpenCV VideoCapture.
"""

import json as _json
import os
import subprocess
import time
import logging
import threading
from datetime import datetime, time as dt_time
from typing import Dict, Any, Optional, Callable, Set

import cv2
import numpy as np

from .camera_time import CameraTimeSync
from .detector import YOLODetector, PoseDetector
from .detection import Detection
from .rules.engine import BehaviorEngine

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Event screenshot save directory
EVENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "events")
os.makedirs(EVENTS_DIR, exist_ok=True)


def _is_rtsp_url(url: str) -> bool:
    return url.startswith("rtsp://") or url.startswith("rtmp://")


def _probe_resolution(url: str) -> tuple:
    """Probe video resolution with ffprobe, returns (width, height)"""
    cmd = [
        "ffprobe", "-rtsp_transport", "tcp",
        "-v", "quiet", "-print_format", "json",
        "-show_streams", "-select_streams", "v:0",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
        info = _json.loads(r.stdout)
        stream = info.get("streams", [{}])[0]
        return int(stream.get("width", 0)), int(stream.get("height", 0))
    except Exception as e:
        logger.warning(f"ffprobe detection failed: {e}")
        return 0, 0


class CameraAnalyzer:
    """Single camera analyzer"""

    def __init__(self, camera_config: dict, model_config: dict,
                 on_event: Optional[Callable] = None,
                 on_frame: Optional[Callable] = None,
                 on_detections: Optional[Callable] = None,
                 restream_url: Optional[str] = None,
                 event_session_mgr=None,
                 camera_time_sync: Optional[CameraTimeSync] = None):
        self.camera_id = camera_config["id"]
        self.camera_name = camera_config.get("name", self.camera_id)
        self.url = camera_config["url"]
        self.fps = camera_config.get("detect", {}).get("fps", 5)
        self.on_event = on_event
        self.on_frame = on_frame
        self.on_detections = on_detections
        self.restream_url = restream_url
        self._event_session_mgr = event_session_mgr
        self._camera_time_sync = camera_time_sync
        self._camera_config = camera_config  # Store full config for MQTT

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        self._model_config = model_config
        self._detector: Optional[YOLODetector] = None
        self._pose_detector: Optional[PoseDetector] = None

        rules_cfg = camera_config.get("rules", {})
        roi = camera_config.get("roi", [])
        self._engine = BehaviorEngine(rules_cfg, roi=roi if roi else None)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[{self.camera_id}] Analyzer started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        # Force resolve remaining MQTT sessions for this camera
        if self._event_session_mgr:
            self._event_session_mgr.force_resolve_camera(self.camera_id)
        logger.info(f"[{self.camera_id}] Analyzer stopped")

    def get_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    # ── Initialize detectors ──

    def _init_detectors(self):
        mc = self._model_config or {}
        self._detector = YOLODetector(
            model_path=mc.get("detector_path", "data/models/yolo26m.pt"),
            confidence=mc.get("confidence", 0.5),
            tracker_config=mc.get("tracker_config", "bytetrack.yaml"),
        )
        pose_path = mc.get("pose_path", "")
        if pose_path:
            self._pose_detector = PoseDetector(
                model_path=pose_path,
                confidence=mc.get("pose_confidence", 0.3),
                tracker_config=mc.get("tracker_config", "bytetrack.yaml"),
            )

    # ── Main entry ──

    def _run(self):
        self._init_detectors()
        if _is_rtsp_url(self.url) or (self.restream_url and _is_rtsp_url(self.restream_url)):
            self._run_ffmpeg()
        else:
            self._run_opencv()

    # ── ffmpeg command building ──

    def _build_ffmpeg_cmd_direct(self, width: int, height: int) -> list[str]:
        """Build ffmpeg command for direct RTSP camera connection (full parameters)"""
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts+discardcorrupt",
            "-rtsp_transport", "tcp",
            "-timeout", "10000000",
            "-use_wallclock_as_timestamps", "1",
            "-i", self.url,
            "-r", str(self.fps),
            "-vf", f"fps={self.fps},scale={width}:{height}",
            "-threads", "2",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "pipe:",
        ]

    def _build_ffmpeg_cmd_restream(self, width: int, height: int) -> list[str]:
        """Build ffmpeg command for pulling stream from go2rtc restream (simplified parameters)"""
        return [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp",
            "-timeout", "10000000",
            "-i", self.restream_url,
            "-r", str(self.fps),
            "-vf", f"fps={self.fps},scale={width}:{height}",
            "-threads", "2",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "pipe:",
        ]

    # ── ffmpeg subprocess stream pulling (RTSP) ──

    def _run_ffmpeg(self):
        """Pull RTSP stream via ffmpeg subprocess — supports go2rtc restream priority + direct fallback"""
        # Probe resolution (using original URL)
        probe_url = self.restream_url if self.restream_url else self.url
        width, height = _probe_resolution(probe_url)
        if width == 0 or height == 0:
            # If restream probe fails, try direct URL probe
            if self.restream_url and probe_url != self.url:
                width, height = _probe_resolution(self.url)
        if width == 0 or height == 0:
            # fallback: use default resolution, ffmpeg will auto-adapt
            width, height = 1920, 1080
            logger.warning(f"[{self.camera_id}] Unable to detect resolution, using default {width}x{height}")
        else:
            logger.info(f"[{self.camera_id}] Detected resolution: {width}x{height}")

        frame_size = width * height * 3  # BGR24
        frame_interval = 1.0 / self.fps
        reconnect_delay = 3.0

        while self._running:
            # Decide whether to use restream or direct connection
            use_restream = self.restream_url is not None
            if use_restream:
                cmd = self._build_ffmpeg_cmd_restream(width, height)
                source_label = f"restream ({self.restream_url})"
            else:
                cmd = self._build_ffmpeg_cmd_direct(width, height)
                source_label = f"direct ({self.url})"

            logger.info(f"[{self.camera_id}] Starting ffmpeg stream [{source_label}]: "
                        f"{width}x{height} @ {self.fps}fps")
            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=frame_size * 5,
                )
            except FileNotFoundError:
                logger.error(f"[{self.camera_id}] ffmpeg not installed, cannot pull RTSP stream")
                return
            except Exception as e:
                logger.error(f"[{self.camera_id}] ffmpeg failed to start: {e}")
                time.sleep(reconnect_delay)
                continue

            logger.info(f"[{self.camera_id}] ffmpeg started (PID={process.pid})")
            last_frame_time = time.time()
            got_frames = False

            while self._running:
                t0 = time.time()

                # Read one BGR24 frame from ffmpeg stdout
                raw = process.stdout.read(frame_size)
                if len(raw) != frame_size:
                    # ffmpeg process may have exited
                    if process.poll() is not None:
                        stderr = process.stderr.read().decode(errors="ignore")[-500:]
                        logger.warning(f"[{self.camera_id}] ffmpeg process exited: {stderr}")
                        break
                    # Incomplete data, skip
                    continue

                got_frames = True
                frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
                last_frame_time = time.time()

                # Process frame
                self._process_frame(frame)

                # Frame rate control
                elapsed = time.time() - t0
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # Clean up ffmpeg process
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()

            # Fall back to direct connection when restream fails
            if use_restream and not got_frames and self._running:
                logger.warning(f"[{self.camera_id}] Restream connection failed, falling back to direct mode")
                self.restream_url = None  # Subsequent loops will use direct connection
                time.sleep(reconnect_delay)
                continue

            if self._running:
                logger.info(f"[{self.camera_id}] Reconnecting in {reconnect_delay}s...")
                time.sleep(reconnect_delay)

    # ── OpenCV stream pulling (local files) ──

    def _run_opencv(self):
        """Read local files or non-RTSP streams using OpenCV VideoCapture"""
        cap = cv2.VideoCapture(self.url)
        if not cap.isOpened():
            logger.error(f"[{self.camera_id}] Unable to open video: {self.url}")
            return

        frame_interval = 1.0 / self.fps
        logger.info(f"[{self.camera_id}] Video stream connected (OpenCV), FPS={self.fps}")

        while self._running:
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                # Local file finished, loop playback
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.1)
                continue

            self._process_frame(frame)

            elapsed = time.time() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    # ── Frame processing (detection + rules + drawing) ──

    def _process_frame(self, frame: np.ndarray):
        """Process single frame: detection → rule engine → push detection data → events"""
        detections = self._detector.track(frame)

        if self._pose_detector:
            pose_dets = self._pose_detector.track(frame)
            self._merge_pose(detections, pose_dets)

        # Use camera-synced time if available, otherwise fall back to server time
        if self._camera_time_sync:
            now = self._camera_time_sync.get_camera_time(self.camera_id)
        else:
            now = time.time()

        # Check schedule: determine which rules to skip at current time
        skip_rules = self._get_skipped_rules_by_schedule(now)

        events = self._engine.update(detections, self.camera_id, frame_ts=now,
                                     skip_rules=skip_rules)

        # Store raw frame (unannotated) for snapshot API
        with self._frame_lock:
            self._latest_frame = frame.copy()

        if self.on_frame:
            self.on_frame(self.camera_id, frame)

        # Push normalized detection results
        if self.on_detections:
            h, w = frame.shape[:2]
            det_data = [
                {
                    "bbox": [
                        d.bbox[0] / w,
                        d.bbox[1] / h,
                        d.bbox[2] / w,
                        d.bbox[3] / h,
                    ],
                    "class_name": d.class_name,
                    "track_id": d.track_id,
                    "confidence": round(d.confidence, 3),
                }
                for d in detections
                if d.track_id >= 0
            ]
            try:
                self.on_detections(self.camera_id, now, det_data)
            except Exception as e:
                logger.error(f"[{self.camera_id}] on_detections callback error: {e}")

        for evt in events:
            img_name = self._save_event_screenshot(frame, evt, detections)
            if img_name:
                evt["image"] = img_name
            if self.on_event:
                self.on_event(evt)

        # ── MQTT event session handling ──
        if self._event_session_mgr:
            for evt in events:
                try:
                    self._event_session_mgr.handle_event(evt, self._camera_config)
                except Exception as e:
                    logger.error(f"[{self.camera_id}] MQTT handle_event error: {e}")

            # Notify untriggered event types (for resolved detection)
            triggered_types = {evt.get("sub_type") for evt in events}
            enabled_types = self._get_enabled_event_types()
            untriggered_types = list(enabled_types - triggered_types)
            if untriggered_types:
                try:
                    self._event_session_mgr.tick_no_event(self.camera_id, untriggered_types)
                except Exception as e:
                    logger.error(f"[{self.camera_id}] MQTT tick_no_event error: {e}")

    # ── Helper methods ──

    def _merge_pose(self, detections, pose_dets):
        pose_map = {d.track_id: d.keypoints for d in pose_dets
                    if d.track_id >= 0 and d.keypoints is not None}
        for det in detections:
            if det.track_id in pose_map:
                det.keypoints = pose_map[det.track_id]

    def _get_enabled_event_types(self) -> set:
        """Return enabled event types based on rules_config"""
        rules = self._camera_config.get("rules", {})
        types = set()
        if rules.get("crowd", {}).get("enabled", False):
            types.add("crowd")
        if rules.get("fight", {}).get("enabled", False):
            types.add("fight")
        if rules.get("fall", {}).get("enabled", False):
            types.add("fall")
        if rules.get("loiter", {}).get("enabled", False):
            types.add("loiter")
        return types

    def _get_skipped_rules_by_schedule(self, frame_ts: float) -> Set[str]:
        """Determine which rules should be skipped based on camera local time and schedule config."""
        if not self._camera_time_sync:
            return set()

        camera_tz = self._camera_time_sync.get_timezone(self.camera_id)
        if camera_tz:
            local_dt = datetime.fromtimestamp(frame_ts, tz=camera_tz)
        else:
            local_dt = datetime.fromtimestamp(frame_ts).astimezone()

        local_time = local_dt.time()
        weekday = local_dt.weekday()  # 0=Monday, 6=Sunday

        skipped: Set[str] = set()
        rules_cfg = self._camera_config.get("rules", {})

        for rule_name in ("crowd", "fight", "fall", "loiter"):
            cfg = rules_cfg.get(rule_name, {})
            schedule = cfg.get("schedule", {})
            if not schedule.get("enabled", False):
                continue  # schedule disabled = detect 24/7
            periods = schedule.get("periods", [])
            if not periods:
                continue  # no periods defined = detect 24/7
            if not self._in_any_period(local_time, weekday, periods):
                skipped.add(rule_name)

        return skipped

    @staticmethod
    def _in_any_period(current_time: dt_time, weekday: int, periods: list) -> bool:
        """Check if current_time + weekday falls within any of the given periods."""
        for period in periods:
            days = period.get("days", [0, 1, 2, 3, 4, 5, 6])
            if weekday not in days:
                continue
            start = CameraAnalyzer._parse_hhmm(period.get("start", "00:00"))
            end = CameraAnalyzer._parse_hhmm(period.get("end", "23:59"), as_end=True)
            if start <= end:
                # Normal period: e.g. 08:00 - 18:00
                if start <= current_time <= end:
                    return True
            else:
                # Cross-midnight: e.g. 22:00 - 06:00
                if current_time >= start or current_time <= end:
                    return True
        return False

    @staticmethod
    def _parse_hhmm(s: str, as_end: bool = False) -> dt_time:
        """Parse 'HH:MM' string into datetime.time.
        
        Args:
            as_end: if True and time is "23:59", return time(23, 59, 59) to cover
                    the full last minute of the day.
        """
        try:
            parts = s.split(":")
            h, m = int(parts[0]), int(parts[1])
            if as_end and h == 23 and m == 59:
                return dt_time(23, 59, 59)
            return dt_time(h, m)
        except (ValueError, IndexError):
            return dt_time(0, 0)

    def _save_event_screenshot(self, frame: np.ndarray, event: dict,
                                detections: list) -> Optional[str]:
        try:
            img = frame.copy()
            for det in detections:
                if det.track_id < 0:
                    continue
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                color = (0, 255, 0)
                evt_tids = event.get("track_ids", [])
                if det.track_id == event.get("track_id") or det.track_id in evt_tids:
                    color = (0, 0, 255)
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
                label = f"{det.class_name} #{det.track_id}"
                cv2.putText(img, label, (x1, max(y1 - 6, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            bbox = event.get("bbox")
            if bbox:
                ex1, ey1, ex2, ey2 = [int(v) for v in bbox]
                sub = event.get("sub_type", "event")
                evt_color = {"crowd": (0, 0, 255), "fight": (0, 0, 255),
                             "fall": (0, 165, 255), "loiter": (0, 200, 200)}.get(sub, (0, 0, 255))
                cv2.rectangle(img, (ex1, ey1), (ex2, ey2), evt_color, 1)
                cv2.putText(img, sub.upper(), (ex1, max(ey1 - 10, 16)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, evt_color, 1)

            ts = time.strftime("%Y%m%d_%H%M%S")
            ms = int((time.time() % 1) * 1000)
            sub_type = event.get("sub_type", "event")
            track_id = event.get("track_id", 0)
            filename = f"{self.camera_id}_{sub_type}_t{track_id}_{ts}_{ms:03d}.jpg"
            filepath = os.path.join(EVENTS_DIR, filename)
            cv2.imwrite(filepath, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            logger.info(f"Event screenshot saved: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Failed to save event screenshot: {e}")
            return None

    def _draw(self, frame: np.ndarray, detections, events) -> np.ndarray:
        img = frame.copy()
        for det in detections:
            if det.track_id < 0:
                continue
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
            label = f"{det.class_name} #{det.track_id}"
            cv2.putText(img, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        for evt in events:
            sub = evt.get("sub_type", "")
            bbox = evt.get("bbox")
            if bbox:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                color = {"crowd": (0, 0, 255), "fight": (0, 0, 255),
                         "fall": (0, 165, 255), "loiter": (0, 200, 200)}.get(sub, (0, 0, 255))
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 1)
                cv2.putText(img, sub.upper(), (x1, y1 - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1)
        return img
