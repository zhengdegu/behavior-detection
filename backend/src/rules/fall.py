"""
Fall detection — Two-stage approach:
  Stage 1 (Falling): Rapid posture change from upright state (velocity + angle)
  Stage 2 (Fallen): Sustained abnormal posture confirmation (inactivity)

References:
  - OpenPose fall detection (hip velocity + body angle + aspect ratio)
  - Dual-Channel Feature Integration (falling-state + fallen-state)
  - Two-Stage Fall Recognition (deflection angle + spine ratio)

Enhanced for top-down camera views:
  - Combined torso angle + body extension evidence
  - Configurable bbox area-change evidence
  - Moving-candidate rejection to reduce walking false positives
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

    def __init__(self, ratio_threshold: float = 0.9,
                 min_ratio_change: float = 0.2,
                 min_y_drop: float = 5.0,
                 confirm_frames: int = 2,
                 cooldown: float = 30.0,
                 min_hip_velocity: float = 8.0,
                 spine_angle_threshold: float = 55.0,
                 inactivity_frames: int = 2,
                 inactivity_threshold: float = 8.0,
                 history_size: int = 15,
                 static_fall_frames: int = 10,
                 lying_ratio_threshold: float = 1.0,
                 torso_horizontal_threshold: float = 35.0,
                 min_area_change: float = 0.35,
                 candidate_timeout: float = 3.0):
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
            static_fall_frames: frames person must be lying (ratio>threshold)
                                + inactive to trigger static fall detection
            lying_ratio_threshold: lower bbox w/h ratio for static lying
                                   detection (for top-down cameras)
            torso_horizontal_threshold: torso angle (degrees from horizontal)
                                        below which person is considered lying
            min_area_change: minimum relative bbox area increase required by
                             bbox-only dynamic detection
            candidate_timeout: seconds before an unconfirmed moving fall
                               candidate is discarded
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
        self.static_fall_frames = static_fall_frames
        self.lying_ratio_threshold = lying_ratio_threshold
        self.torso_horizontal_threshold = torso_horizontal_threshold
        self.min_area_change = min_area_change
        self.candidate_timeout = candidate_timeout

        # Per-track state
        self._prev_ratios: Dict[int, float] = {}
        self._prev_centers: Dict[int, tuple] = {}
        self._prev_areas: Dict[int, float] = {}
        # Pose history buffer: stores (hip_center_y, spine_angle, timestamp)
        self._pose_history: Dict[int, deque] = {}
        # Two-stage state: tracks that passed Stage 1 (falling detected)
        self._falling_detected: Dict[int, float] = {}  # track_id -> timestamp
        # Inactivity counter after falling detected
        self._inactivity_count: Dict[int, int] = {}
        # Static lying counter: consecutive frames with wide ratio + inactive
        self._static_lying_count: Dict[int, int] = {}
        # Pose-based lying counter (for top-down cameras)
        self._pose_lying_count: Dict[int, int] = {}

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

    def _get_torso_horizontal_angle(self, kp) -> Optional[float]:
        """
        Calculate torso angle from horizontal plane (degrees).
        Uses shoulder-hip line. Returns 0° when lying flat, 90° when standing.
        This works better for top-down camera views than head/hip Y comparison.
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

        shoulder_center = (np.mean([p[0] for p in shoulder_pts]),
                          np.mean([p[1] for p in shoulder_pts]))
        hip_center = (np.mean([p[0] for p in hip_pts]),
                     np.mean([p[1] for p in hip_pts]))

        dx = abs(shoulder_center[0] - hip_center[0])
        dy = abs(shoulder_center[1] - hip_center[1])

        if dx < 1e-6 and dy < 1e-6:
            return 90.0  # No movement, assume standing

        # Angle from horizontal: 0° = horizontal (lying), 90° = vertical (standing)
        angle = np.degrees(np.arctan2(dy, dx))
        return float(angle)

    def _get_body_extension(self, kp) -> Optional[float]:
        """
        Calculate body extension ratio for top-down view.
        Measures how "spread out" the body is by comparing limb distances.
        Higher values indicate lying posture.
        """
        # Get available keypoints
        points = {}
        keypoint_names = {
            0: 'nose', 5: 'l_shoulder', 6: 'r_shoulder',
            11: 'l_hip', 12: 'r_hip', 15: 'l_ankle', 16: 'r_ankle',
            9: 'l_wrist', 10: 'r_wrist'
        }
        for idx, name in keypoint_names.items():
            if kp[idx][2] > 0.3:
                points[name] = kp[idx][:2]

        if len(points) < 4:
            return None

        # Calculate bounding box of all visible keypoints
        xs = [p[0] for p in points.values()]
        ys = [p[1] for p in points.values()]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        if height < 1e-6:
            return 999.0  # Very horizontal

        return width / height

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

    def _pose_is_lying_topdown(self, kp) -> bool:
        """
        Determine if person is lying down for top-down camera view.
        Uses torso horizontal angle and body extension ratio.
        """
        torso_angle = self._get_torso_horizontal_angle(kp)
        extension = self._get_body_extension(kp)

        # A top-view standing person can also have a horizontal-looking torso.
        # Require both torso orientation and an extended body shape.
        return (torso_angle is not None
                and torso_angle < self.torso_horizontal_threshold
                and extension is not None
                and extension > 1.2)

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

    def _clear_fall_candidate(self, track_id: int) -> None:
        """Clear transient state after recovery or a confirmed event."""
        self._falling_detected.pop(track_id, None)
        self._inactivity_count.pop(track_id, None)
        self._static_lying_count.pop(track_id, None)
        self._pose_lying_count.pop(track_id, None)
        self._confirm_count.pop(f"fall_{track_id}", None)

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
                self._prev_areas.pop(tid, None)
                self._pose_history.pop(tid, None)
                self._clear_fall_candidate(tid)

        for det in person_dets:
            x1, y1, x2, y2 = det.bbox
            w = x2 - x1
            h = y2 - y1
            if h <= 0:
                continue
            ratio = w / h
            area = w * h
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
            prev_area = self._prev_areas.get(tid)

            # === Two-Stage Fall Detection ===

            is_fall = False
            detail = ""

            # --- Stage 2 check: if already in "falling detected" state ---
            if tid in self._falling_detected:
                # Check if person remains in fallen posture + inactive
                pose_fallen = False
                if det.keypoints is not None:
                    pose_fallen = self._pose_is_fallen(det.keypoints)

                bbox_fallen = ratio > self.ratio_threshold

                is_inactive = self._check_inactivity(tid, det.center)

                if (pose_fallen or bbox_fallen) and is_inactive:
                    # Confirmed fall: rapid descent + sustained fallen posture
                    is_fall = True
                    detail = (f"Fall confirmed: sustained fallen posture for "
                              f"{self._inactivity_count.get(tid, 0)} frames"
                              f" (bbox_ratio={ratio:.2f})")
                elif not pose_fallen and not bbox_fallen:
                    # Person recovered (stood back up) — false alarm
                    self._clear_fall_candidate(tid)
                elif now - self._falling_detected[tid] > self.candidate_timeout:
                    # A person who keeps moving is not a confirmed fall. This
                    # rejects walking/turning boxes that briefly become square.
                    logger.debug(
                        f"[Fall-Rejected-Moving] cam={camera_id} track={tid} "
                        f"ratio={ratio:.2f} timeout={self.candidate_timeout:.1f}s")
                    self._clear_fall_candidate(tid)

            # --- Stage 1: Detect rapid falling transition ---
            elif prev_center is not None and prev_ratio is not None:
                # Pose-based detection (when keypoints available)
                pose_fallen = False
                was_upright = False
                if det.keypoints is not None:
                    pose_fallen = self._pose_is_fallen(det.keypoints)
                    was_upright = self._was_recently_upright(tid)

                # Bbox-based detection (always available)
                ratio_change = ratio - prev_ratio
                y_drop = det.center[1] - prev_center[1]
                area_change = 0.0
                if prev_area is not None and prev_area > 0:
                    area_change = (area - prev_area) / prev_area

                # --- Path A: Pose-based (original logic) ---
                if det.keypoints is not None and pose_fallen and was_upright:
                    hip_velocity = 0.0
                    if hip_y is not None:
                        hip_velocity = self._compute_hip_velocity(tid, hip_y)

                    fast_descent = hip_velocity > self.min_hip_velocity
                    bbox_change = (ratio > self.ratio_threshold
                                   and ratio_change > self.min_ratio_change
                                   and y_drop > self.min_y_drop
                                   and area_change > self.min_area_change)

                    if fast_descent or bbox_change:
                        self._falling_detected[tid] = now
                        self._inactivity_count[tid] = 0
                        logger.debug(
                            f"[Fall-Stage1-Pose] cam={camera_id} track={tid} "
                            f"hip_vel={hip_velocity:.1f} ratio_chg="
                            f"{ratio_change:.2f} area_chg={area_change:.2f} "
                            f"y_drop={y_drop:.0f}")

                # --- Path B: Bbox-only (no pose required) ---
                # Detect fall by: ratio significantly increased (person went
                # from tall/narrow standing bbox to squarer/wider fallen bbox)
                # OR bbox height dropped significantly (person collapsed)
                elif (ratio_change > self.min_ratio_change
                      and ratio > self.ratio_threshold
                      and prev_ratio < self.ratio_threshold
                      and y_drop > self.min_y_drop
                      and area_change > self.min_area_change):
                    self._falling_detected[tid] = now
                    self._inactivity_count[tid] = 0
                    logger.debug(
                        f"[Fall-Stage1-Bbox] cam={camera_id} track={tid} "
                        f"ratio={ratio:.2f} prev_ratio={prev_ratio:.2f} "
                        f"ratio_chg={ratio_change:.2f} "
                        f"area_chg={area_change:.2f} y_drop={y_drop:.0f}")

                # --- Path C: Static lying (wide bbox + was upright) ---
                elif ratio > 1.3 and was_upright:
                    if hip_y is not None:
                        hip_velocity = self._compute_hip_velocity(tid, hip_y)
                        if hip_velocity > self.min_hip_velocity * 0.5:
                            self._falling_detected[tid] = now
                            self._inactivity_count[tid] = 0

            # --- Path D: Static fall (person already lying + inactive) ---
            # Catches cases where the fall transition was missed but person
            # is clearly lying on the ground (wide bbox + not moving).
            # Keep a safety floor for legacy configs whose 0.6 threshold also
            # classifies square-ish standing boxes as lying.
            if not is_fall and tid not in self._falling_detected:
                is_inactive = self._check_inactivity(tid, det.center)

                # Method 1: Bbox-based (original)
                static_ratio_threshold = max(self.lying_ratio_threshold, 1.0)
                if ratio > static_ratio_threshold and is_inactive:
                    self._static_lying_count[tid] = \
                        self._static_lying_count.get(tid, 0) + 1
                else:
                    self._static_lying_count[tid] = 0

                # Method 2: Pose-based for top-down cameras
                pose_lying = False
                if det.keypoints is not None:
                    pose_lying = self._pose_is_lying_topdown(det.keypoints)

                if pose_lying and is_inactive:
                    self._pose_lying_count[tid] = \
                        self._pose_lying_count.get(tid, 0) + 1
                else:
                    self._pose_lying_count[tid] = 0

                # Trigger if either method reaches threshold
                bbox_static_triggered = (
                    self._static_lying_count.get(tid, 0) >= self.static_fall_frames
                )
                pose_static_triggered = (
                    self._pose_lying_count.get(tid, 0) >= self.static_fall_frames
                )

                if bbox_static_triggered or pose_static_triggered:
                    is_fall = True
                    if pose_static_triggered and not bbox_static_triggered:
                        torso_angle = self._get_torso_horizontal_angle(det.keypoints) if det.keypoints is not None else None
                        torso_detail = (f"{torso_angle:.1f}° from horizontal"
                                        if torso_angle is not None else "unavailable")
                        detail = (f"Static fall (pose): person lying "
                                  f"(torso_angle={torso_detail}) "
                                  f"and inactive for {self._pose_lying_count.get(tid, 0)} frames")
                    else:
                        detail = (f"Static fall: person lying (ratio={ratio:.2f}) "
                                  f"and inactive for {self._static_lying_count.get(tid, 0)} frames")
                    logger.debug(
                        f"[Fall-Static] cam={camera_id} track={tid} "
                        f"ratio={ratio:.2f} pose_lying={pose_lying}")

            # Use confirm_frames + cooldown for final event emission
            key = f"fall_{tid}"
            if self._check_confirm_and_cooldown(key, is_fall, now=now):
                events.append({
                    "type": "anomaly",
                    "sub_type": "fall",
                    "camera_id": camera_id,
                    "track_id": tid,
                    "track_ids": [tid],
                    "class_name": "person",
                    "confidence": det.confidence,
                    "bbox": det.bbox,
                    "detail": detail,
                    "timestamp": now,
                })
                logger.info(f"[Fall] cam={camera_id} track={tid} "
                            f"detail={detail}")
                self._clear_fall_candidate(tid)

            # Keep the previous-frame values intact until all movement checks
            # for the current frame have completed.
            self._prev_ratios[tid] = ratio
            self._prev_centers[tid] = det.center
            self._prev_areas[tid] = area

        return events
