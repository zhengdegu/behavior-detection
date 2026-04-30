"""
Fall detection — bbox aspect ratio sudden change + Pose enhancement (head below hips)
"""

import time
import logging
from typing import List, Dict, Any

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class FallRule(BaseAnomalyRule):

    def __init__(self, ratio_threshold: float = 1.0,
                 min_ratio_change: float = 0.5,
                 min_y_drop: float = 20.0,
                 confirm_frames: int = 2,
                 cooldown: float = 30.0):
        super().__init__("fall", confirm_frames, cooldown)
        self.ratio_threshold = ratio_threshold
        self.min_ratio_change = min_ratio_change
        self.min_y_drop = min_y_drop
        self._prev_ratios: Dict[int, float] = {}
        self._prev_centers: Dict[int, tuple] = {}

    @staticmethod
    def _pose_is_fallen(kp) -> bool:
        """Determine fall via keypoints: head Y > hip Y → fallen"""
        import numpy as _np

        head_pts = []
        for idx in [0, 1, 2]:  # nose, left_eye, right_eye
            if kp[idx][2] > 0.3:
                head_pts.append(kp[idx][:2])

        hip_pts = []
        for idx in [11, 12]:  # left_hip, right_hip
            if kp[idx][2] > 0.3:
                hip_pts.append(kp[idx][:2])

        if not head_pts or not hip_pts:
            return False

        head_y = _np.mean([p[1] for p in head_pts])
        hip_y = _np.mean([p[1] for p in hip_pts])

        if head_y > hip_y:
            return True

        # Additional: torso nearly horizontal
        shoulder_pts = [kp[i][:2] for i in [5, 6] if kp[i][2] > 0.3]
        ankle_pts = [kp[i][:2] for i in [15, 16] if kp[i][2] > 0.3]

        if shoulder_pts and ankle_pts:
            shoulder_y = _np.mean([p[1] for p in shoulder_pts])
            ankle_y = _np.mean([p[1] for p in ankle_pts])
            shoulder_x = _np.mean([p[0] for p in shoulder_pts])
            ankle_x = _np.mean([p[0] for p in ankle_pts])
            dy = abs(ankle_y - shoulder_y)
            dx = abs(ankle_x - shoulder_x)
            if dx > 0 and dy / dx < 0.5:
                return True

        return False

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        events = []
        now = frame_ts if frame_ts > 0 else time.time()

        person_dets = [d for d in detections
                       if d.track_id >= 0 and d.class_name == "person"]

        active_ids = {d.track_id for d in person_dets}
        for tid in list(self._prev_ratios.keys()):
            if tid not in active_ids:
                self._prev_ratios.pop(tid, None)
                self._prev_centers.pop(tid, None)

        for det in person_dets:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            if h <= 0:
                continue
            ratio = w / h

            prev_ratio = self._prev_ratios.get(det.track_id)
            prev_center = self._prev_centers.get(det.track_id)
            self._prev_ratios[det.track_id] = ratio
            self._prev_centers[det.track_id] = det.center

            pose_fallen = False
            if det.keypoints is not None:
                pose_fallen = self._pose_is_fallen(det.keypoints)

            if pose_fallen:
                is_fall = True
                detail = "Suspected fall: abnormal posture (head below hips) [Pose enhanced]"
            elif ratio > 1.3:
                is_fall = True
                detail = f"Suspected fall: lying posture (aspect ratio {ratio:.2f}) [static detection]"
            elif prev_ratio is not None and prev_center is not None:
                ratio_change = ratio - prev_ratio
                y_drop = det.center[1] - prev_center[1]
                is_fall = (ratio > self.ratio_threshold
                           and ratio_change > self.min_ratio_change
                           and y_drop > self.min_y_drop)
                detail = (f"Suspected fall: aspect ratio {ratio:.2f}"
                          f" (change +{ratio_change:.2f}), dropped {y_drop:.0f}px")
            else:
                continue

            key = f"fall_{det.track_id}"
            if self._check_confirm_and_cooldown(key, is_fall, now=now):
                events.append({
                    "type": "anomaly",
                    "sub_type": "fall",
                    "camera_id": camera_id,
                    "track_id": det.track_id,
                    "class_name": "person",
                    "confidence": det.confidence,
                    "bbox": det.bbox,
                    "detail": detail,
                    "timestamp": now,
                })
                logger.info(f"[Fall] cam={camera_id} track={det.track_id} "
                            f"pose={'Y' if pose_fallen else 'N'}")

        return events
