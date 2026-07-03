"""
Behavior detection engine — aggregates crowd/fight/fall rules
"""

import logging
from typing import List, Dict, Any

from ..detection import Detection
from ..geometry import point_in_polygon, Polygon
from .base import BaseAnomalyRule
from .crowd import CrowdRule
from .fight import FightRule
from .fall import FallRule
from .loiter import LoiterRule

logger = logging.getLogger(__name__)


class BehaviorEngine:
    """Behavior detection engine, aggregates all rules"""

    def __init__(self, config: dict, roi: Polygon = None):
        self.rules: List[BaseAnomalyRule] = []
        self.roi = [(float(p[0]), float(p[1])) for p in roi] if roi else None
        config = config or {}

        crowd_cfg = config.get("crowd") or {}
        if crowd_cfg.get("enabled", False):
            rule = CrowdRule(
                max_count=crowd_cfg.get("max_count", 5),
                radius=crowd_cfg.get("radius", 200),
                confirm_frames=crowd_cfg.get("confirm_frames", 5),
                cooldown=crowd_cfg.get("cooldown", 60),
            )
            rule_roi = crowd_cfg.get("roi", [])
            if rule_roi:
                rule.roi = [(float(p[0]), float(p[1])) for p in rule_roi]
            self.rules.append(rule)

        fight_cfg = config.get("fight") or {}
        if fight_cfg.get("enabled", False):
            rule = FightRule(
                proximity_radius=fight_cfg.get("proximity_radius", 150),
                min_speed=fight_cfg.get("min_speed", 80),
                min_persons=fight_cfg.get("min_persons", 2),
                confirm_frames=fight_cfg.get("confirm_frames", 6),
                cooldown=fight_cfg.get("cooldown", 30),
                co_move_cos_threshold=fight_cfg.get("co_move_cos_threshold", 0.7),
                min_relative_speed=fight_cfg.get("min_relative_speed", 40.0),
                min_distance_variance=fight_cfg.get("min_distance_variance", 10.0),
                joint_overlap_threshold=fight_cfg.get("joint_overlap_threshold", 1),
            )
            rule_roi = fight_cfg.get("roi", [])
            if rule_roi:
                rule.roi = [(float(p[0]), float(p[1])) for p in rule_roi]
            self.rules.append(rule)

        fall_cfg = config.get("fall") or {}
        if fall_cfg.get("enabled", False):
            rule = FallRule(
                ratio_threshold=fall_cfg.get("ratio_threshold", 1.0),
                min_ratio_change=fall_cfg.get("min_ratio_change", 0.5),
                min_y_drop=fall_cfg.get("min_y_drop", 20),
                confirm_frames=fall_cfg.get("confirm_frames", 5),
                cooldown=fall_cfg.get("cooldown", 30),
                min_hip_velocity=fall_cfg.get("min_hip_velocity", 30.0),
                spine_angle_threshold=fall_cfg.get("spine_angle_threshold", 45.0),
                inactivity_frames=fall_cfg.get("inactivity_frames", 3),
                inactivity_threshold=fall_cfg.get("inactivity_threshold", 15.0),
                history_size=fall_cfg.get("history_size", 10),
            )
            rule_roi = fall_cfg.get("roi", [])
            if rule_roi:
                rule.roi = [(float(p[0]), float(p[1])) for p in rule_roi]
            self.rules.append(rule)

        loiter_cfg = config.get("loiter") or {}
        if loiter_cfg.get("enabled", False):
            rule = LoiterRule(
                min_duration=loiter_cfg.get("min_duration", 60.0),
                max_distance=loiter_cfg.get("max_distance", 150.0),
                max_displacement_ratio=loiter_cfg.get("max_displacement_ratio", 0.3),
                min_total_path=loiter_cfg.get("min_total_path", 50.0),
                trajectory_window=loiter_cfg.get("trajectory_window", 60.0),
                inertia=loiter_cfg.get("inertia", 3),
                confirm_frames=loiter_cfg.get("confirm_frames", 5),
                cooldown=loiter_cfg.get("cooldown", 120.0),
            )
            rule_roi = loiter_cfg.get("roi", [])
            if rule_roi:
                rule.roi = [(float(p[0]), float(p[1])) for p in rule_roi]
            self.rules.append(rule)

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0,
               skip_rules: set = None) -> List[Dict[str, Any]]:
        """Run all rules, return anomaly event list.
        
        Args:
            skip_rules: set of rule_name strings to skip (schedule-based)
        """
        all_events = []
        for rule in self.rules:
            if skip_rules and rule.rule_name in skip_rules:
                rule.reset_confirm()
                continue

            # Per-rule ROI filtering: rule.roi > global self.roi > no filter
            effective_roi = rule.roi if rule.roi else self.roi
            if effective_roi:
                filtered = [d for d in detections
                            if d.track_id < 0 or point_in_polygon(d.foot, effective_roi)]
            else:
                filtered = detections

            try:
                events = rule.update(filtered, camera_id, frame_ts=frame_ts)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Rule {rule.rule_name} error: {e}")
        return all_events
