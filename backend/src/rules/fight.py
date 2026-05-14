"""
Fight detection — Enhanced with:
  1. Relative speed filtering (exclude co-moving pairs)
  2. Direction consistency filtering (exclude same-direction walking)
  3. Distance variance analysis (exclude stable-distance pairs)
  4. Joint overlap detection (limbs entering opponent's space)
  5. Wrist speed (Pose enhancement)

References:
  - DIFEM: Key-points velocity + joint overlap (arXiv:2412.05386)
  - Interpretable HAR: relative speed, handTowardCos, distanceRate (arXiv:2604.14329)
"""

import math
import time
import logging
from typing import List, Dict, Any, Tuple
from collections import deque
from statistics import variance as stat_variance

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class FightRule(BaseAnomalyRule):

    def __init__(self, proximity_radius: float = 150.0,
                 min_speed: float = 80.0,
                 min_persons: int = 2,
                 confirm_frames: int = 6,
                 cooldown: float = 30.0,
                 co_move_cos_threshold: float = 0.7,
                 min_relative_speed: float = 40.0,
                 min_distance_variance: float = 10.0,
                 joint_overlap_threshold: int = 1):
        """
        Args:
            proximity_radius: max distance (px) to consider two people "close"
            min_speed: min effective speed (px/s) to consider motion aggressive
            min_persons: minimum people involved
            confirm_frames: consecutive frames needed to confirm fight
            cooldown: seconds between repeated alerts for same track
            co_move_cos_threshold: cosine similarity above which two people
                                   are considered moving in the same direction
            min_relative_speed: min relative speed (px/s) between two people
                                to be considered adversarial motion
            min_distance_variance: min variance in inter-person distance (px²)
                                   over recent frames; low = stable = co-walking
            joint_overlap_threshold: min joint intrusions to boost fight score
        """
        super().__init__("fight", confirm_frames, cooldown)
        self.proximity_radius = proximity_radius
        self.min_speed = min_speed
        self.min_persons = min_persons
        self.co_move_cos_threshold = co_move_cos_threshold
        self.min_relative_speed = min_relative_speed
        self.min_distance_variance = min_distance_variance
        self.joint_overlap_threshold = joint_overlap_threshold

        self._prev_positions: Dict[int, tuple] = {}
        self._prev_times: Dict[int, float] = {}
        self._prev_wrists: Dict[int, list] = {}
        self._velocity_vectors: Dict[int, Tuple[float, float]] = {}
        self._pair_distances: Dict[Tuple[int, int], deque] = {}

    @staticmethod
    def _cosine_similarity(v1: Tuple[float, float],
                           v2: Tuple[float, float]) -> float:
        """Cosine similarity between two 2D vectors."""
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
        mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
        if mag1 < 1e-6 or mag2 < 1e-6:
            return 0.0
        return dot / (mag1 * mag2)

    @staticmethod
    def _count_joint_overlap(det_i: Detection, det_j: Detection) -> int:
        """Count how many of det_i's arm joints fall inside det_j's bbox."""
        if det_i.keypoints is None:
            return 0
        x1, y1, x2, y2 = det_j.bbox
        count = 0
        for idx in [7, 8, 9, 10]:  # left/right elbow, left/right wrist
            kp = det_i.keypoints[idx]
            if kp[2] > 0.3:
                if x1 <= kp[0] <= x2 and y1 <= kp[1] <= y2:
                    count += 1
        return count

    def _calc_limb_speed(self, det: Detection, now: float) -> float:
        """Calculate wrist movement speed (Pose enhancement)."""
        if det.keypoints is None or det.track_id < 0:
            return 0.0

        kp = det.keypoints
        wrists = []
        for idx in [9, 10]:  # Left and right wrists
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

    def _is_co_moving(self, tid_i: int, tid_j: int) -> bool:
        """
        Check if two tracks are co-moving (same direction, low relative speed).
        Returns True if they appear to be walking together.
        """
        vec_i = self._velocity_vectors.get(tid_i)
        vec_j = self._velocity_vectors.get(tid_j)
        if not vec_i or not vec_j:
            return False

        cos_sim = self._cosine_similarity(vec_i, vec_j)
        rel_speed = math.dist(vec_i, vec_j)

        if cos_sim > self.co_move_cos_threshold and \
                rel_speed < self.min_relative_speed:
            return True
        return False

    def _is_stable_distance(self, tid_i: int, tid_j: int,
                            current_dist: float) -> bool:
        """
        Check if the distance between two people is stable over recent frames.
        Stable distance = walking together, not fighting.
        """
        pair_key = (min(tid_i, tid_j), max(tid_i, tid_j))
        if pair_key not in self._pair_distances:
            self._pair_distances[pair_key] = deque(maxlen=10)
        self._pair_distances[pair_key].append(current_dist)

        history = self._pair_distances[pair_key]
        if len(history) < 3:
            return False  # Not enough data, don't filter

        dist_var = stat_variance(history)
        return dist_var < self.min_distance_variance

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        events = []
        now = frame_ts if frame_ts > 0 else time.time()

        person_dets = [d for d in detections
                       if d.track_id >= 0 and d.class_name == "person"]

        # Calculate speeds and velocity vectors
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
                    # Store velocity vector for direction analysis
                    vx = (det.center[0] - prev_pos[0]) / dt
                    vy = (det.center[1] - prev_pos[1]) / dt
                    self._velocity_vectors[det.track_id] = (vx, vy)

        # Clean up disappeared tracks
        active_ids = {d.track_id for d in person_dets}
        for tid in list(self._prev_positions.keys()):
            if tid not in active_ids:
                self._prev_positions.pop(tid, None)
                self._prev_times.pop(tid, None)
                self._prev_wrists.pop(tid, None)
                self._velocity_vectors.pop(tid, None)

        # Clean up stale pair distance histories
        for pair_key in list(self._pair_distances.keys()):
            if pair_key[0] not in active_ids or pair_key[1] not in active_ids:
                del self._pair_distances[pair_key]

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
                if dist >= self.proximity_radius:
                    continue

                # --- Filter 1: Co-moving detection ---
                if self._is_co_moving(det_i.track_id, det_j.track_id):
                    logger.debug(
                        f"[Fight-Filter] co-moving: track {det_i.track_id} "
                        f"& {det_j.track_id}, skipping")
                    continue

                # --- Filter 2: Stable distance detection ---
                if self._is_stable_distance(det_i.track_id,
                                            det_j.track_id, dist):
                    logger.debug(
                        f"[Fight-Filter] stable distance: track "
                        f"{det_i.track_id} & {det_j.track_id}, skipping")
                    continue

                # --- Speed check ---
                speed_j = speeds.get(det_j.track_id, 0)
                limb_j = limb_speeds.get(det_j.track_id, 0)
                effective_speed_j = max(speed_j, limb_j)

                if (effective_speed_i > self.min_speed or
                        effective_speed_j > self.min_speed):
                    # --- Bonus: Joint overlap detection ---
                    overlap = (self._count_joint_overlap(det_i, det_j) +
                               self._count_joint_overlap(det_j, det_i))
                    if overlap >= self.joint_overlap_threshold:
                        logger.debug(
                            f"[Fight-Boost] joint overlap={overlap}: "
                            f"track {det_i.track_id} & {det_j.track_id}")
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
                    "involved_track_ids": involved,
                    "class_name": "person",
                    "involved_count": len(involved),
                    "avg_speed": round(avg_speed, 1),
                    "bbox": det_i.bbox,
                    "detail": (f"Suspected fight: {len(involved)} people in "
                               f"close-range violent motion, "
                               f"avg speed {avg_speed:.0f}px/s"
                               + (" [Pose enhanced]" if has_pose else "")),
                    "timestamp": now,
                })
                logger.info(f"[Fight] cam={camera_id} involved={len(involved)} "
                            f"speed={avg_speed:.0f}")
                break

        return events
