"""
视频分析管线 — 拉流 → 检测+跟踪 → 行为规则引擎 → 事件
每路摄像头一个 Analyzer 线程。

RTSP 流使用 ffmpeg 子进程拉流（参考 warehouse-vision / Frigate 架构），
本地文件使用 OpenCV VideoCapture。
"""

import json as _json
import os
import subprocess
import time
import logging
import threading
from typing import Dict, Any, Optional, Callable

import cv2
import numpy as np

from .detector import YOLODetector, PoseDetector
from .detection import Detection
from .rules.engine import BehaviorEngine

logger = logging.getLogger(__name__)

# 事件截图保存目录
EVENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "events")
os.makedirs(EVENTS_DIR, exist_ok=True)


def _is_rtsp_url(url: str) -> bool:
    return url.startswith("rtsp://") or url.startswith("rtmp://")


def _probe_resolution(url: str) -> tuple:
    """用 ffprobe 探测视频分辨率，返回 (width, height)"""
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
        logger.warning(f"ffprobe 探测失败: {e}")
        return 0, 0


class CameraAnalyzer:
    """单路摄像头分析器"""

    def __init__(self, camera_config: dict, model_config: dict,
                 on_event: Optional[Callable] = None,
                 on_frame: Optional[Callable] = None,
                 on_detections: Optional[Callable] = None,
                 restream_url: Optional[str] = None,
                 event_session_mgr=None):
        self.camera_id = camera_config["id"]
        self.camera_name = camera_config.get("name", self.camera_id)
        self.url = camera_config["url"]
        self.fps = camera_config.get("detect", {}).get("fps", 5)
        self.on_event = on_event
        self.on_frame = on_frame
        self.on_detections = on_detections
        self.restream_url = restream_url
        self._event_session_mgr = event_session_mgr
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
        logger.info(f"[{self.camera_id}] 分析器已启动")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info(f"[{self.camera_id}] 分析器已停止")

    def get_frame(self) -> Optional[np.ndarray]:
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    # ── 初始化检测器 ──

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

    # ── 主入口 ──

    def _run(self):
        self._init_detectors()
        if _is_rtsp_url(self.url) or (self.restream_url and _is_rtsp_url(self.restream_url)):
            self._run_ffmpeg()
        else:
            self._run_opencv()

    # ── ffmpeg 命令构建 ──

    def _build_ffmpeg_cmd_direct(self, width: int, height: int) -> list[str]:
        """构建直连摄像头 RTSP 的 ffmpeg 命令（完整参数）"""
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
        """构建从 go2rtc restream 拉流的 ffmpeg 命令（简化参数）"""
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

    # ── ffmpeg 子进程拉流（RTSP）──

    def _run_ffmpeg(self):
        """用 ffmpeg 子进程拉 RTSP 流 — 支持 go2rtc restream 优先 + 直连回退"""
        # 探测分辨率（使用原始 URL 探测）
        probe_url = self.restream_url if self.restream_url else self.url
        width, height = _probe_resolution(probe_url)
        if width == 0 or height == 0:
            # 如果 restream 探测失败，尝试直连 URL 探测
            if self.restream_url and probe_url != self.url:
                width, height = _probe_resolution(self.url)
        if width == 0 or height == 0:
            # fallback: 用默认分辨率，ffmpeg 会自动适配
            width, height = 1920, 1080
            logger.warning(f"[{self.camera_id}] 无法探测分辨率，使用默认 {width}x{height}")
        else:
            logger.info(f"[{self.camera_id}] 探测到分辨率: {width}x{height}")

        frame_size = width * height * 3  # BGR24
        frame_interval = 1.0 / self.fps
        reconnect_delay = 3.0

        while self._running:
            # 决定使用 restream 还是直连
            use_restream = self.restream_url is not None
            if use_restream:
                cmd = self._build_ffmpeg_cmd_restream(width, height)
                source_label = f"restream ({self.restream_url})"
            else:
                cmd = self._build_ffmpeg_cmd_direct(width, height)
                source_label = f"direct ({self.url})"

            logger.info(f"[{self.camera_id}] 启动 ffmpeg 拉流 [{source_label}]: "
                        f"{width}x{height} @ {self.fps}fps")
            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    bufsize=frame_size * 5,
                )
            except FileNotFoundError:
                logger.error(f"[{self.camera_id}] ffmpeg 未安装，无法拉 RTSP 流")
                return
            except Exception as e:
                logger.error(f"[{self.camera_id}] ffmpeg 启动失败: {e}")
                time.sleep(reconnect_delay)
                continue

            logger.info(f"[{self.camera_id}] ffmpeg 已启动 (PID={process.pid})")
            last_frame_time = time.time()
            got_frames = False

            while self._running:
                t0 = time.time()

                # 从 ffmpeg stdout 读一帧 BGR24
                raw = process.stdout.read(frame_size)
                if len(raw) != frame_size:
                    # ffmpeg 进程可能已退出
                    if process.poll() is not None:
                        stderr = process.stderr.read().decode(errors="ignore")[-500:]
                        logger.warning(f"[{self.camera_id}] ffmpeg 进程退出: {stderr}")
                        break
                    # 数据不完整，跳过
                    continue

                got_frames = True
                frame = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
                last_frame_time = time.time()

                # 处理帧
                self._process_frame(frame)

                # 帧率控制
                elapsed = time.time() - t0
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            # 清理 ffmpeg 进程
            try:
                process.terminate()
                process.wait(timeout=3)
            except Exception:
                process.kill()

            # restream 失败时回退到直连
            if use_restream and not got_frames and self._running:
                logger.warning(f"[{self.camera_id}] restream 连接失败，回退到直连模式")
                self.restream_url = None  # 后续循环将使用直连
                time.sleep(reconnect_delay)
                continue

            if self._running:
                logger.info(f"[{self.camera_id}] {reconnect_delay}s 后重连...")
                time.sleep(reconnect_delay)

    # ── OpenCV 拉流（本地文件）──

    def _run_opencv(self):
        """用 OpenCV VideoCapture 读取本地文件或非 RTSP 流"""
        cap = cv2.VideoCapture(self.url)
        if not cap.isOpened():
            logger.error(f"[{self.camera_id}] 无法打开视频: {self.url}")
            return

        frame_interval = 1.0 / self.fps
        logger.info(f"[{self.camera_id}] 视频流已连接 (OpenCV), FPS={self.fps}")

        while self._running:
            t0 = time.time()
            ret, frame = cap.read()
            if not ret:
                # 本地文件播完了，循环播放
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                time.sleep(0.1)
                continue

            self._process_frame(frame)

            elapsed = time.time() - t0
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

    # ── 帧处理（检测 + 规则 + 绘制）──

    def _process_frame(self, frame: np.ndarray):
        """处理单帧：检测 → 规则引擎 → 推送检测数据 → 事件"""
        detections = self._detector.track(frame)

        if self._pose_detector:
            pose_dets = self._pose_detector.track(frame)
            self._merge_pose(detections, pose_dets)

        now = time.time()
        events = self._engine.update(detections, self.camera_id, frame_ts=now)

        # 存储原始帧（未标注）用于 snapshot API
        with self._frame_lock:
            self._latest_frame = frame.copy()

        if self.on_frame:
            self.on_frame(self.camera_id, frame)

        # 推送归一化检测结果
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
                logger.error(f"[{self.camera_id}] on_detections 回调异常: {e}")

        for evt in events:
            img_name = self._save_event_screenshot(frame, evt, detections)
            if img_name:
                evt["image"] = img_name
            if self.on_event:
                self.on_event(evt)

        # ── MQTT 事件会话处理 ──
        if self._event_session_mgr:
            for evt in events:
                try:
                    self._event_session_mgr.handle_event(evt, self._camera_config)
                except Exception as e:
                    logger.error(f"[{self.camera_id}] MQTT handle_event 异常: {e}")

            # 通知未触发的事件类型（用于 resolved 检测）
            triggered_types = {evt.get("sub_type") for evt in events}
            enabled_types = self._get_enabled_event_types()
            untriggered_types = list(enabled_types - triggered_types)
            if untriggered_types:
                try:
                    self._event_session_mgr.tick_no_event(self.camera_id, untriggered_types)
                except Exception as e:
                    logger.error(f"[{self.camera_id}] MQTT tick_no_event 异常: {e}")

    # ── 辅助方法 ──

    def _merge_pose(self, detections, pose_dets):
        pose_map = {d.track_id: d.keypoints for d in pose_dets
                    if d.track_id >= 0 and d.keypoints is not None}
        for det in detections:
            if det.track_id in pose_map:
                det.keypoints = pose_map[det.track_id]

    def _get_enabled_event_types(self) -> set:
        """根据 rules_config 返回启用的事件类型列表"""
        rules = self._camera_config.get("rules", {})
        types = set()
        if rules.get("crowd", {}).get("enabled", False):
            types.add("crowd")
        if rules.get("fight", {}).get("enabled", False):
            types.add("fight")
        if rules.get("fall", {}).get("enabled", False):
            types.add("fall")
        return types

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
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
                label = f"{det.class_name} #{det.track_id}"
                cv2.putText(img, label, (x1, max(y1 - 6, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            bbox = event.get("bbox")
            if bbox:
                ex1, ey1, ex2, ey2 = [int(v) for v in bbox]
                sub = event.get("sub_type", "event")
                evt_color = {"crowd": (0, 0, 255), "fight": (0, 0, 255),
                             "fall": (0, 165, 255)}.get(sub, (0, 0, 255))
                cv2.rectangle(img, (ex1, ey1), (ex2, ey2), evt_color, 3)
                cv2.putText(img, sub.upper(), (ex1, max(ey1 - 10, 16)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, evt_color, 2)

            ts = time.strftime("%Y%m%d_%H%M%S")
            ms = int((time.time() % 1) * 1000)
            sub_type = event.get("sub_type", "event")
            track_id = event.get("track_id", 0)
            filename = f"{self.camera_id}_{sub_type}_t{track_id}_{ts}_{ms:03d}.jpg"
            filepath = os.path.join(EVENTS_DIR, filename)
            cv2.imwrite(filepath, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            logger.info(f"事件截图已保存: {filename}")
            return filename
        except Exception as e:
            logger.error(f"保存事件截图失败: {e}")
            return None

    def _draw(self, frame: np.ndarray, detections, events) -> np.ndarray:
        img = frame.copy()
        for det in detections:
            if det.track_id < 0:
                continue
            x1, y1, x2, y2 = [int(v) for v in det.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{det.class_name} #{det.track_id}"
            cv2.putText(img, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        for evt in events:
            sub = evt.get("sub_type", "")
            bbox = evt.get("bbox")
            if bbox:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                color = {"crowd": (0, 0, 255), "fight": (0, 0, 255),
                         "fall": (0, 165, 255)}.get(sub, (0, 0, 255))
                cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
                cv2.putText(img, sub.upper(), (x1, y1 - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        return img
