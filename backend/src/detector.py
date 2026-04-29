"""
目标检测与跟踪模块 — YOLO 检测 + ByteTrack 跟踪 + Pose 姿态估计
"""

import logging
from typing import List, Optional

import torch
import numpy as np

from .detection import Detection

logger = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"推理设备: {DEVICE}" +
            (f" ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else ""))


class YOLODetector:
    """YOLO 检测器 + ByteTrack 跟踪"""

    def __init__(self, model_path: str = "data/models/yolo26m.pt",
                 confidence: float = 0.5,
                 tracker_config: str = "bytetrack.yaml"):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.model.to(DEVICE)
        self.confidence = confidence
        self.tracker_config = tracker_config
        # 只检测 person 类别 (class_id=0)
        self.allowed_classes = [0]
        logger.info(f"YOLO 模型已加载: {model_path}, 设备: {DEVICE}")

    def _parse_results(self, results, with_track: bool = False) -> List[Detection]:
        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                if self.allowed_classes and cls_id not in self.allowed_classes:
                    continue
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                track_id = -1
                if with_track and boxes.id is not None:
                    track_id = int(boxes.id[i].item())
                cls_name = self.model.names.get(cls_id, str(cls_id))
                detections.append(Detection(
                    track_id=track_id, class_id=cls_id, class_name=cls_name,
                    confidence=conf, bbox=[x1, y1, x2, y2],
                    center=(cx, cy), foot=(cx, y2),
                ))
        return detections

    def track(self, frame: np.ndarray) -> List[Detection]:
        """检测 + 跟踪"""
        results = self.model.track(
            frame, conf=self.confidence, persist=True,
            tracker=self.tracker_config, device=DEVICE, verbose=False,
        )
        return self._parse_results(results, with_track=True)


class PoseDetector:
    """YOLO Pose 检测器 — 输出人体关键点，增强打架/跌倒精度"""

    def __init__(self, model_path: str = "data/models/yolo26m-pose.pt",
                 confidence: float = 0.3,
                 tracker_config: str = "bytetrack.yaml"):
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.model.to(DEVICE)
        self.confidence = confidence
        self.tracker_config = tracker_config
        logger.info(f"Pose 模型已加载: {model_path}, 设备: {DEVICE}")

    def track(self, frame: np.ndarray) -> List[Detection]:
        results = self.model.track(
            frame, conf=self.confidence, persist=True,
            tracker=self.tracker_config, device=DEVICE, verbose=False,
        )
        return self._parse_results(results, with_track=True)

    def _parse_results(self, results, with_track: bool = False) -> List[Detection]:
        detections = []
        for r in results:
            boxes = r.boxes
            kps = r.keypoints
            if boxes is None or len(boxes) == 0:
                continue
            for i in range(len(boxes)):
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                track_id = -1
                if with_track and boxes.id is not None:
                    track_id = int(boxes.id[i].item())
                keypoints = None
                if kps is not None and kps.data is not None and i < len(kps.data):
                    keypoints = kps.data[i].cpu().numpy()
                detections.append(Detection(
                    track_id=track_id, class_id=0, class_name="person",
                    confidence=conf, bbox=[x1, y1, x2, y2],
                    center=(cx, cy), foot=(cx, y2), keypoints=keypoints,
                ))
        return detections
