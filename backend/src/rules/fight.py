"""
打架检测 — 多人近距离 + 高速运动 + Pose 姿态增强（手腕挥拳特征）
"""

import math
import time
import logging
from typing import List, Dict, Any

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class FightRule(BaseAnomalyRule):

    def __init__(self, proximity_radius: float = 150.0,
                 min_speed: float = 60.0,
                 min_persons: int = 2,
                 confirm_frames: int = 3,
                 cooldown: float = 30.0):
        super().__init__("fight", confirm_frames, cooldown)
        self.proximity_radius = proximity_radius
        self.min_speed = min_speed
        self.min_persons = min_persons
        self._prev_positions: Dict[int, tuple] = {}
        self._prev_times: Dict[int, float] = {}
        self._prev_wrists: Dict[int, list] = {}

    def _calc_limb_speed(self, det: Detection, now: float) -> float:
        """计算手腕运动速度（Pose 增强）"""
        if det.keypoints is None or det.track_id < 0:
            return 0.0

        kp = det.keypoints
        wrists = []
        for idx in [9, 10]:  # 左右手腕
            if kp[idx][2] > 0.15:
                wrists.append((float(kp[idx][0]), float(kp[idx][1])))

        if not wrists:
            return 0.0

        prev = self._prev_wrists.get(det.track_id)
        self._prev_wrists[det.track_id] = wrists

        if prev is None:
            return 0.0

        prev_time = self._prev_times.get(det.track_id, now)
        dt = now - prev_time
        if dt <= 0:
            return 0.0

        max_speed = 0.0
        for w in wrists:
            for pw in prev:
                speed = math.dist(w, pw) / dt
                max_speed = max(max_speed, speed)
        return max_speed

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        events = []
        now = frame_ts if frame_ts > 0 else time.time()

        person_dets = [d for d in detections
                       if d.track_id >= 0 and d.class_name == "person"]

        speeds: Dict[int, float] = {}
        limb_speeds: Dict[int, float] = {}
        for det in person_dets:
            prev_pos = self._prev_positions.get(det.track_id)
            prev_time = self._prev_times.get(det.track_id)
            self._prev_positions[det.track_id] = det.center

            limb_spd = self._calc_limb_speed(det, now)
            limb_speeds[det.track_id] = limb_spd
            self._prev_times[det.track_id] = now

            if prev_pos is not None and prev_time is not None:
                dt = now - prev_time
                if dt > 0:
                    speeds[det.track_id] = math.dist(det.center, prev_pos) / dt

        # 清理已消失的 track
        active_ids = {d.track_id for d in person_dets}
        for tid in list(self._prev_positions.keys()):
            if tid not in active_ids:
                self._prev_positions.pop(tid, None)
                self._prev_times.pop(tid, None)
                self._prev_wrists.pop(tid, None)

        if len(person_dets) < self.min_persons:
            self._confirm_count.clear()
            return events

        for i, det_i in enumerate(person_dets):
            nearby_fast = []
            speed_i = speeds.get(det_i.track_id, 0)
            limb_i = limb_speeds.get(det_i.track_id, 0)
            effective_speed_i = max(speed_i, limb_i)

            for j, det_j in enumerate(person_dets):
                if i == j:
                    continue
                dist = math.dist(det_i.center, det_j.center)
                speed_j = speeds.get(det_j.track_id, 0)
                limb_j = limb_speeds.get(det_j.track_id, 0)
                effective_speed_j = max(speed_j, limb_j)
                if (dist < self.proximity_radius and
                        (effective_speed_i > self.min_speed or
                         effective_speed_j > self.min_speed)):
                    nearby_fast.append(det_j.track_id)

            is_fight = (len(nearby_fast) >= (self.min_persons - 1) and
                        effective_speed_i > self.min_speed)
            key = f"fight_{det_i.track_id}"

            if self._check_confirm_and_cooldown(key, is_fight, now=now):
                involved = [det_i.track_id] + nearby_fast
                avg_speed = sum(speeds.get(t, 0) for t in involved) / len(involved)
                has_pose = any(limb_speeds.get(t, 0) > 0 for t in involved)
                events.append({
                    "type": "anomaly",
                    "sub_type": "fight",
                    "camera_id": camera_id,
                    "track_id": det_i.track_id,
                    "class_name": "person",
                    "involved_count": len(involved),
                    "avg_speed": round(avg_speed, 1),
                    "bbox": det_i.bbox,
                    "detail": (f"疑似打架：{len(involved)}人近距离剧烈运动，"
                               f"平均速度{avg_speed:.0f}px/s"
                               + (" [Pose增强]" if has_pose else "")),
                    "timestamp": now,
                })
                logger.info(f"[打架] cam={camera_id} involved={len(involved)} "
                            f"speed={avg_speed:.0f}")
                break

        return events
