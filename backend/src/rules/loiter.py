"""
Loitering detection — person stays in ROI for extended time with low displacement.

Algorithm (Intel Dwell Time + WACV 2024 Trajectory Analysis fusion):
  1. Track each person's entry time and initial position in ROI
  2. After min_duration, evaluate:
     - Euclidean distance from initial position <= max_distance
     - Displacement ratio (net/total path) <= max_displacement_ratio
     - Total path >= min_total_path (filters purely stationary)
  3. Inertia: require N consecutive frames in ROI before timer starts (Frigate-style)
  4. Uses bbox bottom-center as anchor point (more stable than center)

References:
  - Intel Metro AI Suite Loitering Detection (2025-2026)
  - Frigate NVR Zone Loitering (loitering_time + inertia)
  - WACV 2024: Identifying Loitering Behavior with Trajectory Analysis
  - Google Cloud Vision AI: DwellTimeInfo
"""

import math
import time
import logging
from typing import List, Dict, Any, Tuple
from collections import deque

from ..detection import Detection
from .base import BaseAnomalyRule

logger = logging.getLogger(__name__)


class LoiterRule(BaseAnomalyRule):
    """Loitering detection based on dwell time + spatial confinement."""

    def __init__(self, min_duration: float = 60.0,
                 max_distance: float = 150.0,
                 max_displacement_ratio: float = 0.3,
                 min_total_path: float = 50.0,
                 trajectory_window: float = 60.0,
                 inertia: int = 3,
                 confirm_frames: int = 5,
                 cooldown: float = 120.0):
        """
        Args:
            min_duration: seconds in ROI before evaluation begins
            max_distance: max displacement from initial position (px) to be loitering
            max_displacement_ratio: net_displacement / total_path threshold
            min_total_path: minimum total path length (px); filters stationary persons
            trajectory_window: sliding window (seconds) for trajectory analysis
            inertia: frames object must be in ROI before dwell timer starts
            confirm_frames: consecutive positive frames to confirm loitering
            cooldown: seconds between repeated alerts for same track
        """
        super().__init__("loiter", confirm_frames, cooldown)
        self.min_duration = min_duration
        self.max_distance = max_distance
        self.max_displacement_ratio = max_displacement_ratio
        self.min_total_path = min_total_path
        self.trajectory_window = trajectory_window
        self.inertia = inertia

        # Per-track state
        self._inertia_count: Dict[int, int] = {}      # frames in ROI
        self._first_seen: Dict[int, float] = {}       # timestamp when inertia passed
        self._initial_pos: Dict[int, Tuple[float, float]] = {}  # position at first_seen
        self._trajectories: Dict[int, deque] = {}     # (x, y, t) history
        self._miss_count: Dict[int, int] = {}         # frames absent from ROI (grace period)
        self._max_miss: int = 10  # allow up to 10 frames absence before full cleanup

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        if frame_ts <= 0:
            frame_ts = time.time()

        events: List[Dict[str, Any]] = []
        current_track_ids = set()

        for det in detections:
            if det.track_id < 0 or det.class_name != "person":
                continue

            tid = det.track_id
            current_track_ids.add(tid)

            # Use bottom-center as anchor (more stable, Frigate approach)
            x1, y1, x2, y2 = det.bbox
            anchor_x = (x1 + x2) / 2.0
            anchor_y = y2  # bottom center

            # ── Inertia check: require N consecutive frames in ROI ──
            self._inertia_count[tid] = self._inertia_count.get(tid, 0) + 1
            if self._inertia_count[tid] < self.inertia:
                continue

            # ── Record first-seen time and initial position ──
            if tid not in self._first_seen:
                self._first_seen[tid] = frame_ts
                self._initial_pos[tid] = (anchor_x, anchor_y)

            # ── Append to trajectory (sliding window) ──
            if tid not in self._trajectories:
                self._trajectories[tid] = deque()
            traj = self._trajectories[tid]
            traj.append((anchor_x, anchor_y, frame_ts))

            # Prune old points outside window
            while traj and (frame_ts - traj[0][2]) > self.trajectory_window:
                traj.popleft()

            # ── Check dwell time ──
            dwell_time = frame_ts - self._first_seen[tid]
            if dwell_time < self.min_duration:
                continue

            # ── Evaluate spatial metrics ──
            if len(traj) < 3:
                continue

            # Distance from initial position
            init_x, init_y = self._initial_pos[tid]
            distance = math.hypot(anchor_x - init_x, anchor_y - init_y)

            # Displacement ratio and total path
            disp_ratio, total_path = self._trajectory_metrics(traj)

            # ── Loitering condition ──
            condition = (
                distance <= self.max_distance
                and disp_ratio <= self.max_displacement_ratio
                and total_path >= self.min_total_path
            )

            key = f"loiter_{tid}"
            if self._check_confirm_and_cooldown(key, condition, frame_ts):
                # Build event
                bbox = [x1, y1, x2, y2]
                events.append({
                    "type": "anomaly",
                    "sub_type": "loiter",
                    "camera_id": camera_id,
                    "track_id": tid,
                    "track_ids": [tid],
                    "timestamp": frame_ts,
                    "bbox": bbox,
                    "detail": (
                        f"Loitering: person #{tid} in area for "
                        f"{dwell_time:.0f}s, displacement {distance:.0f}px, "
                        f"ratio {disp_ratio:.2f}"
                    ),
                    "data": {
                        "dwell_time": round(dwell_time, 1),
                        "distance": round(distance, 1),
                        "displacement_ratio": round(disp_ratio, 3),
                        "total_path": round(total_path, 1),
                    },
                })

        # ── Cleanup lost tracks ──
        self._cleanup_lost_tracks(current_track_ids)

        return events

    def reset_confirm(self):
        """Reset all state when schedule skips this rule."""
        super().reset_confirm()
        self._inertia_count.clear()
        self._first_seen.clear()
        self._initial_pos.clear()
        self._trajectories.clear()
        self._miss_count.clear()

    @staticmethod
    def _trajectory_metrics(traj: deque) -> Tuple[float, float]:
        """Calculate displacement_ratio and total_path from trajectory points.
        
        Returns:
            (displacement_ratio, total_path)
        """
        if len(traj) < 2:
            return 1.0, 0.0

        total_path = 0.0
        for i in range(1, len(traj)):
            dx = traj[i][0] - traj[i - 1][0]
            dy = traj[i][1] - traj[i - 1][1]
            total_path += math.hypot(dx, dy)

        if total_path < 1e-6:
            return 0.0, 0.0

        net = math.hypot(
            traj[-1][0] - traj[0][0],
            traj[-1][1] - traj[0][1],
        )
        return net / total_path, total_path

    def _cleanup_lost_tracks(self, current_track_ids: set):
        """Remove state for tracks no longer present, with grace period for ROI edge flicker."""
        # Tracks that are being tracked but not in current detections
        tracked_tids = set(self._first_seen.keys()) | set(self._inertia_count.keys())
        absent = tracked_tids - current_track_ids

        for tid in absent:
            self._miss_count[tid] = self._miss_count.get(tid, 0) + 1
            if self._miss_count[tid] >= self._max_miss:
                # Grace period exceeded — fully remove
                self._inertia_count.pop(tid, None)
                self._first_seen.pop(tid, None)
                self._initial_pos.pop(tid, None)
                self._trajectories.pop(tid, None)
                self._confirm_count.pop(f"loiter_{tid}", None)
                self._miss_count.pop(tid, None)

        # Reset miss count for tracks that reappeared
        for tid in current_track_ids:
            if tid in self._miss_count:
                del self._miss_count[tid]
