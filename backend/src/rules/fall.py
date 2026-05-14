"""
Fall detection — Two-stage approach:
  Stage 1 (Falling): Rapid posture change from upright state (velocity + angle)
  Stage 2 (Fallen): Sustained abnormal posture confirmation (inactivity)

References:
  - OpenPose fall detection (hip velocity + body angle + aspect ratio)
  - Dual-Channel Feature Integration (falling-state + fallen-state)
  - Two-Stage Fall Recognition (deflection angle + spine ratio)
"""

import time
import logging
from typing import List, Dict, Any, Optional
from collections import deque

import numpy as np

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class FallRule(BaseAnomalyRule):

    def __init__(self, ratio_threshold: float = 1.0,
                 min_ratio_change: float = 0.5,
                 min_y_drop: float = 20.0,
                 confirm_frames: int = 5,
                 cooldown: float = 30.0,
                 # New parameters for enhanced detection
                 min_hip_velocity: float = 30.0,
                 spine_angle_threshold: float = 45.0,
                 inactivity_frames: int = 3,
                 inactivity_threshold: float = 15.0,
                 history_size: int = 10):
        """
        Args:
            ratio_threshold: bbox w/h ratio threshold for dynamic detection
            min_ratio_change: minimum ratio change between frames
            min_y_drop: minimum Y drop (px) between frames
            confirm_frames: frames needed to confirm fall
            cooldown: seconds between repeated alerts for same track
            min_hip_velocity: minimum hip center drop speed (px/frame) to
                              distinguish fall from bending
            spine_angle_threshold: spine angle with vertical (degrees) below
                                   which person is considered upright
            inactivity_frames: frames of inactivity after fall to confirm
            inactivity_threshold: max movement (px) to be considered inactive
            history_size: number of frames to keep in pose history buffer
        """
        super().__init__("fall", confirm_frames, cooldown)
        self.ratio_threshold = ratio_threshold
        self.min_ratio_change = min_ratio_change
        self.min_y_drop = min_y_drop
        self.min_hip_velocity = min_hip_velocity
        self.spine_angle_threshold = spine_angle_threshold
        self.inactivity_frames = inactivity_frames
        self.inactivity_threshold = inactivity_threshold
        self.history_size = history_size

        # Per-track state
        self._prev_ratios: Dict[int, float] = {}
        self._prev_centers: Dict[int, tuple] = {}
        # Pose history buffer: stores (hip_center_y, spine_angle, timestamp)
        self._pose_history: Dict[int, deque] = {}
        # Two-stage state: tracks that passed Stage 1 (falling detected)
        self._falling_detected: Dict[int, float] = {}  # track_id -> timestamp
        # Inactivity counter after falling detected
        self._inactivity_count: Dict[int, int] = {}

    def _get_hip_center(self, kp) -> Optional[tuple]:
        """Get hip center from keypoints."""
        hip_pts = []
        for idx in [11, 12]:  # left_hip, right_hip
            if kp[idx][2] > 0.3:
                hip_pts.append(kp[idx][:2])
        if not hip_pts:
            return None
        return (np.mean([p[0] for p in hip_pts]),
                np.mean([p[1] for p in hip_pts]))

    def _get_spine_angle(self, kp) -> Optional[float]:
        """
        Calculate spine angle with vertical axis (degrees).
        Spine = line from hip center to shoulder center.
        Returns 0° when perfectly upright, 90° when horizontal.
        """
        shoulder_pts = []
        for idx in [5, 6]:  # left_shoulder, right_shoulder
            if kp[idx][2] > 0.3:
                shoulder_pts.append(kp[idx][:2])
        hip_pts = []
        for idx in [11, 12]:
            if kp[idx][2] > 0.3:
                hip_pts.append(kp[idx][:2])

        if not shoulder_pts or not hip_pts:
            return None

        shoulder_x = np.mean([p[0] for p in shoulder_pts])
        shoulder_y = np.mean([p[1] for p in shoulder_pts])
        hip_x = np.mean([p[0] for p in hip_pts])
        hip_y = np.mean([p[1] for p in hip_pts])

        # Vector from hip to shoulder (in image coords, Y increases downward)
        dx = shoulder_x - hip_x
        dy = hip_y - shoulder_y  # flip Y so up is positive

        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return 0.0

        # Angle with vertical (Y-axis): 0° = upright, 90° = horizontal
        angle = np.degrees(np.arctan2(abs(dx), dy))
        return float(angle)

    def _is_upright(self, kp) -> bool:
        """Check if person is in upright posture (standing/walking)."""
        angle = self._get_spine_angle(kp)
        if angle is None:
            # Fallback: check if head is above hips
            head_pts = []
            for idx in [0, 1, 2]:
                if kp[idx][2] > 0.3:
                    head_pts.append(kp[idx][:2])
            hip_pts = []
            for idx in [11, 12]:
                if kp[idx][2] > 0.3:
                    hip_pts.append(kp[idx][:2])
            if head_pts and hip_pts:
                head_y = np.mean([p[1] for p in head_pts])
                hip_y = np.mean([p[1] for p in hip_pts])
                return head_y < hip_y  # head above hips in image coords
            return True  # assume upright if can't determine
        return angle < self.spine_angle_threshold

    def _compute_hip_velocity(self, track_id: int, current_hip_y: float) -> float:
        """
        Compute hip center downward velocity (px/frame).
        Positive = moving down (falling).
        """
        history = self._pose_history.get(track_id)
        if not history or len(history) < 2:
            return 0.0
        # Compare with the oldest entry in recent history
        prev_hip_y = history[-2][0]
        if prev_hip_y is None:
            return 0.0
        return current_hip_y - prev_hip_y  # positive = downward

    def _check_inactivity(self, track_id: int, current_center: tuple) -> bool:
        """
        Check if person is inactive (not moving) after falling.
        Returns True if person has been still for enough frames.
        """
        prev_center = self._prev_centers.get(track_id)
        if prev_center is None:
            return False

        movement = np.sqrt((current_center[0] - prev_center[0]) ** 2 +
                           (current_center[1] - prev_center[1]) ** 2)

        if movement < self.inactivity_threshold:
            self._inactivity_count[track_id] = \
                self._inactivity_count.get(track_id, 0) + 1
        else:
            self._inactivity_count[track_id] = 0

        return self._inactivity_count.get(track_id, 0) >= self.inactivity_frames

    @staticmethod
    def _pose_is_fallen(kp) -> bool:
        """
        Determine fall via keypoints: head Y > hip Y OR torso nearly horizontal.
        This is the static posture check (Stage 2 confirmation).
        """
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

        head_y = np.mean([p[1] for p in head_pts])
        hip_y = np.mean([p[1] for p in hip_pts])

        if head_y > hip_y:
            return True

        # Additional: torso nearly horizontal
        shoulder_pts = [kp[i][:2] for i in [5, 6] if kp[i][2] > 0.3]
        ankle_pts = [kp[i][:2] for i in [15, 16] if kp[i][2] > 0.3]

        if shoulder_pts and ankle_pts:
            shoulder_y = np.mean([p[1] for p in shoulder_pts])
            ankle_y = np.mean([p[1] for p in ankle_pts])
            shoulder_x = np.mean([p[0] for p in shoulder_pts])
            ankle_x = np.mean([p[0] for p in ankle_pts])
            dy = abs(ankle_y - shoulder_y)
            dx = abs(ankle_x - shoulder_x)
            if dx > 0 and dy / dx < 0.5:
                return True

        return False

    def _was_recently_upright(self, track_id: int) -> bool:
        """Check if person was upright in recent history."""
        history = self._pose_history.get(track_id)
        if not history:
            return False
        # Check if any of the recent frames had upright spine angle
        for _, angle, _ in history:
            if angle is not None and angle < self.spine_angle_threshold:
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
        # Cleanup stale tracks
        for tid in list(self._prev_ratios.keys()):
            if tid not in active_ids:
                self._prev_ratios.pop(tid, None)
                self._prev_centers.pop(tid, None)
                self._pose_history.pop(tid, None)
                self._falling_detected.pop(tid, None)
                self._inactivity_count.pop(tid, None)

        for det in person_dets:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            if h <= 0:
                continue
            ratio = w / h
            tid = det.track_id

            # Initialize pose history buffer
            if tid not in self._pose_history:
                self._pose_history[tid] = deque(maxlen=self.history_size)

            # Extract pose features
            hip_center = None
            spine_angle = None
            if det.keypoints is not None:
                hip_center = self._get_hip_center(det.keypoints)
                spine_angle = self._get_spine_angle(det.keypoints)

            # Record to history
            hip_y = hip_center[1] if hip_center else None
            self._pose_history[tid].append((hip_y, spine_angle, now))

            prev_ratio = self._prev_ratios.get(tid)
            prev_center = self._prev_centers.get(tid)
            self._prev_ratios[tid] = ratio
            self._prev_centers[tid] = det.center

            # === Two-Stage Fall Detection ===

            is_fall = False
            detail = ""

            # --- Stage 2 check: if already in "falling detected" state ---
            if tid in self._falling_detected:
                # Check if person remains in fallen posture + inactive
                pose_fallen = False
                if det.keypoints is not None:
                    pose_fallen = self._pose_is_fallen(det.keypoints)

                is_inactive = self._check_inactivity(tid, det.center)

                if pose_fallen and is_inactive:
                    # Confirmed fall: rapid descent + sustained fallen posture
                    is_fall = True
                    detail = (f"Fall confirmed: rapid descent detected, "
                              f"sustained fallen posture for "
                              f"{self._inactivity_count.get(tid, 0)} frames")
                    # Clear falling state after confirmation
                    del self._falling_detected[tid]
                    self._inactivity_count.pop(tid, None)
                elif not pose_fallen:
                    # Person recovered (stood back up) — false alarm
                    del self._falling_detected[tid]
                    self._inactivity_count.pop(tid, None)
                elif now - self._falling_detected[tid] > 5.0:
                    # Timeout: if still in fallen posture after 5s but moving,
                    # still confirm (person may be struggling)
                    if pose_fallen:
                        is_fall = True
                        detail = (f"Fall confirmed: sustained fallen posture "
                                  f"for >5s after rapid descent")
                        del self._falling_detected[tid]
                        self._inactivity_count.pop(tid, None)
                    else:
                        del self._falling_detected[tid]
                        self._inactivity_count.pop(tid, None)

            # --- Stage 1: Detect rapid falling transition ---
            elif det.keypoints is not None and prev_center is not None:
                pose_fallen = self._pose_is_fallen(det.keypoints)
                was_upright = self._was_recently_upright(tid)

                if pose_fallen and was_upright:
                    # Check velocity: was the transition fast?
                    hip_velocity = 0.0
                    if hip_y is not None:
                        hip_velocity = self._compute_hip_velocity(tid, hip_y)

                    # Check bbox ratio change
                    ratio_change = (ratio - prev_ratio) if prev_ratio else 0.0
                    y_drop = det.center[1] - prev_center[1]

                    # Condition: fast descent OR significant bbox change
                    fast_descent = hip_velocity > self.min_hip_velocity
                    bbox_change = (ratio > self.ratio_threshold
                                   and ratio_change > self.min_ratio_change
                                   and y_drop > self.min_y_drop)

                    if fast_descent or bbox_change:
                        # Enter Stage 2: wait for inactivity confirmation
                        self._falling_detected[tid] = now
                        self._inactivity_count[tid] = 0
                        logger.debug(
                            f"[Fall-Stage1] cam={camera_id} track={tid} "
                            f"hip_vel={hip_velocity:.1f} ratio_chg="
                            f"{ratio_change:.2f} y_drop={y_drop:.0f}")

                elif not pose_fallen and not was_upright:
                    # Person was not upright and is not in fallen pose
                    # (e.g., bending) — do nothing
                    pass

                elif ratio > 1.3 and was_upright:
                    # Static lying detection: very wide bbox + was upright
                    # Also requires velocity check
                    if hip_y is not None:
                        hip_velocity = self._compute_hip_velocity(tid, hip_y)
                        if hip_velocity > self.min_hip_velocity * 0.5:
                            self._falling_detected[tid] = now
                            self._inactivity_count[tid] = 0

            # Use confirm_frames + cooldown for final event emission
            key = f"fall_{tid}"
            if self._check_confirm_and_cooldown(key, is_fall, now=now):
                events.append({
                    "type": "anomaly",
                    "sub_type": "fall",
                    "camera_id": camera_id,
                    "track_id": tid,
                    "class_name": "person",
                    "confidence": det.confidence,
                    "bbox": det.bbox,
                    "detail": detail,
                    "timestamp": now,
                })
                logger.info(f"[Fall] cam={camera_id} track={tid} "
                            f"detail={detail}")

        return events
