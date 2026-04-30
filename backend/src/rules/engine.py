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

logger = logging.getLogger(__name__)


class BehaviorEngine:
    """Behavior detection engine, aggregates all rules"""

    def __init__(self, config: dict, roi: Polygon = None):
        self.rules: List[BaseAnomalyRule] = []
        self.roi = [(float(p[0]), float(p[1])) for p in roi] if roi else None
        config = config or {}

        crowd_cfg = config.get("crowd") or {}
        if crowd_cfg.get("enabled", False):
            self.rules.append(CrowdRule(
                max_count=crowd_cfg.get("max_count", 5),
                radius=crowd_cfg.get("radius", 200),
                confirm_frames=crowd_cfg.get("confirm_frames", 5),
                cooldown=crowd_cfg.get("cooldown", 60),
            ))

        fight_cfg = config.get("fight") or {}
        if fight_cfg.get("enabled", False):
            self.rules.append(FightRule(
                proximity_radius=fight_cfg.get("proximity_radius", 150),
                min_speed=fight_cfg.get("min_speed", 60),
                min_persons=fight_cfg.get("min_persons", 2),
                confirm_frames=fight_cfg.get("confirm_frames", 3),
                cooldown=fight_cfg.get("cooldown", 30),
            ))

        fall_cfg = config.get("fall") or {}
        if fall_cfg.get("enabled", False):
            self.rules.append(FallRule(
                ratio_threshold=fall_cfg.get("ratio_threshold", 1.0),
                min_ratio_change=fall_cfg.get("min_ratio_change", 0.5),
                min_y_drop=fall_cfg.get("min_y_drop", 20),
                confirm_frames=fall_cfg.get("confirm_frames", 2),
                cooldown=fall_cfg.get("cooldown", 30),
            ))

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        """Run all rules, return anomaly event list"""
        if self.roi:
            detections = [d for d in detections
                          if d.track_id < 0 or point_in_polygon(d.foot, self.roi)]
        all_events = []
        for rule in self.rules:
            try:
                events = rule.update(detections, camera_id, frame_ts=frame_ts)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Rule {rule.rule_name} error: {e}")
        return all_events
