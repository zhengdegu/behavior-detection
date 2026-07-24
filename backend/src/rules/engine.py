"""
Behavior detection engine — aggregates crowd/fight/fall rules
"""

import logging
from typing import List, Dict, Any

from ..config import ZoneConfig
from ..detection import Detection
from ..geometry import point_in_polygon, point_in_any_polygon, Polygon, MultiPolygon
from .base import BaseAnomalyRule
from .crowd import CrowdRule
from .fight import FightRule
from .fall import FallRule
from .loiter import LoiterRule

logger = logging.getLogger(__name__)


def merge_zone_params(zone: ZoneConfig, defaults: dict) -> dict:
    """将 Zone 覆盖参数与规则默认参数合并。
    Zone 中非 None 的值优先，None 的使用 defaults 中的值。
    """
    merged = dict(defaults)
    for key, value in zone.model_dump(exclude={'roi', 'name'}, exclude_none=True).items():
        merged[key] = value
    return merged


class BehaviorEngine:
    """Behavior detection engine, aggregates all rules"""

    def __init__(self, config: dict, roi: list = None):
        self.rules: List[BaseAnomalyRule] = []
        self.roi: MultiPolygon = self._parse_roi(roi)
        config = config or {}

        crowd_cfg = config.get("crowd") or {}
        if crowd_cfg.get("enabled", False):
            crowd_defaults = {
                "max_count": crowd_cfg.get("max_count", 5),
                "radius": crowd_cfg.get("radius", 250),
                "confirm_frames": crowd_cfg.get("confirm_frames", 8),
                "cooldown": crowd_cfg.get("cooldown", 60),
            }
            zones = crowd_cfg.get("zones") or []
            if zones:
                for z in zones:
                    zone = ZoneConfig(**z) if isinstance(z, dict) else z
                    effective = merge_zone_params(zone, crowd_defaults)
                    rule = CrowdRule(**effective)
                    rule.multi_roi = self._parse_roi([zone.roi])
                    rule.zone_name = zone.name
                    self.rules.append(rule)
            else:
                rule = CrowdRule(**crowd_defaults)
                rule.multi_roi = self._parse_roi(crowd_cfg.get("roi", []))
                self.rules.append(rule)

        fight_cfg = config.get("fight") or {}
        if fight_cfg.get("enabled", False):
            fight_defaults = {
                "proximity_radius": fight_cfg.get("proximity_radius", 180),
                "min_speed": fight_cfg.get("min_speed", 120),
                "min_persons": fight_cfg.get("min_persons", 2),
                "confirm_frames": fight_cfg.get("confirm_frames", 8),
                "cooldown": fight_cfg.get("cooldown", 30),
                "co_move_cos_threshold": fight_cfg.get("co_move_cos_threshold", 0.7),
                "min_relative_speed": fight_cfg.get("min_relative_speed", 55.0),
                "min_distance_variance": fight_cfg.get("min_distance_variance", 18.0),
                "joint_overlap_threshold": fight_cfg.get("joint_overlap_threshold", 2),
            }
            zones = fight_cfg.get("zones") or []
            if zones:
                for z in zones:
                    zone = ZoneConfig(**z) if isinstance(z, dict) else z
                    effective = merge_zone_params(zone, fight_defaults)
                    rule = FightRule(**effective)
                    rule.multi_roi = self._parse_roi([zone.roi])
                    rule.zone_name = zone.name
                    self.rules.append(rule)
            else:
                rule = FightRule(**fight_defaults)
                rule.multi_roi = self._parse_roi(fight_cfg.get("roi", []))
                self.rules.append(rule)

        fall_cfg = config.get("fall") or {}
        if fall_cfg.get("enabled", False):
            fall_defaults = {
                "ratio_threshold": fall_cfg.get("ratio_threshold", 1.2),
                "min_ratio_change": fall_cfg.get("min_ratio_change", 0.4),
                "min_y_drop": fall_cfg.get("min_y_drop", 12),
                "confirm_frames": fall_cfg.get("confirm_frames", 2),
                "cooldown": fall_cfg.get("cooldown", 30),
                "min_hip_velocity": fall_cfg.get("min_hip_velocity", 20.0),
                "spine_angle_threshold": fall_cfg.get("spine_angle_threshold", 45.0),
                "inactivity_frames": fall_cfg.get("inactivity_frames", 3),
                "inactivity_threshold": fall_cfg.get("inactivity_threshold", 12.0),
                "history_size": fall_cfg.get("history_size", 10),
            }
            zones = fall_cfg.get("zones") or []
            if zones:
                for z in zones:
                    zone = ZoneConfig(**z) if isinstance(z, dict) else z
                    effective = merge_zone_params(zone, fall_defaults)
                    rule = FallRule(**effective)
                    rule.multi_roi = self._parse_roi([zone.roi])
                    rule.zone_name = zone.name
                    self.rules.append(rule)
            else:
                rule = FallRule(**fall_defaults)
                rule.multi_roi = self._parse_roi(fall_cfg.get("roi", []))
                self.rules.append(rule)

        loiter_cfg = config.get("loiter") or {}
        if loiter_cfg.get("enabled", False):
            loiter_defaults = {
                "min_duration": loiter_cfg.get("min_duration", 90.0),
                "max_distance": loiter_cfg.get("max_distance", 150.0),
                "max_displacement_ratio": loiter_cfg.get("max_displacement_ratio", 0.3),
                "min_total_path": loiter_cfg.get("min_total_path", 40.0),
                "trajectory_window": loiter_cfg.get("trajectory_window", 60.0),
                "inertia": loiter_cfg.get("inertia", 3),
                "confirm_frames": loiter_cfg.get("confirm_frames", 5),
                "cooldown": loiter_cfg.get("cooldown", 90.0),
            }
            zones = loiter_cfg.get("zones") or []
            if zones:
                for z in zones:
                    zone = ZoneConfig(**z) if isinstance(z, dict) else z
                    effective = merge_zone_params(zone, loiter_defaults)
                    rule = LoiterRule(**effective)
                    rule.multi_roi = self._parse_roi([zone.roi])
                    rule.zone_name = zone.name
                    self.rules.append(rule)
            else:
                rule = LoiterRule(**loiter_defaults)
                rule.multi_roi = self._parse_roi(loiter_cfg.get("roi", []))
                self.rules.append(rule)

    @staticmethod
    def _parse_roi(roi: list) -> MultiPolygon:
        """Parse ROI data into a list of polygons.
        
        Supports two formats:
        - Legacy single polygon: [[x1,y1], [x2,y2], ...] 
        - Multi-polygon: [[[x1,y1],[x2,y2],...], [[x1,y1],[x2,y2],...]]
        
        Detection: if first element is a 2-element list of numbers → single polygon.
        If first element is a list of lists → multi-polygon.
        """
        if not roi:
            return []
        # Check if this is a multi-polygon (list of polygons)
        # A polygon point is [float, float]. A polygon is [[float,float], ...].
        # Multi-polygon is [[[float,float],...], [[float,float],...]]
        first = roi[0]
        if not first:
            return []
        # If first element's first element is also a list → multi-polygon format
        if isinstance(first[0], (list, tuple)):
            # Multi-polygon: each item is a polygon (list of points)
            result = []
            for poly in roi:
                if len(poly) >= 3:
                    result.append([(float(p[0]), float(p[1])) for p in poly])
            return result
        else:
            # Legacy single polygon: roi = [[x,y], [x,y], ...]
            if len(roi) >= 3:
                return [[(float(p[0]), float(p[1])) for p in roi]]
            return []

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0,
               skip_rules: set = None,
               frame_size: tuple = None) -> List[Dict[str, Any]]:
        """Run all rules, return anomaly event list.
        
        Args:
            skip_rules: set of rule_name strings to skip (schedule-based)
            frame_size: (height, width) of the frame, used to normalize foot
                        coordinates for ROI comparison (ROI stored as 0~1).
        """
        all_events = []
        for rule in self.rules:
            if skip_rules and rule.rule_name in skip_rules:
                rule.reset_confirm()
                continue

            # Per-rule ROI filtering: rule.multi_roi > global self.roi > no filter
            effective_roi = rule.multi_roi if rule.multi_roi else self.roi
            if effective_roi:
                if frame_size:
                    fh, fw = frame_size
                    filtered = [
                        d for d in detections
                        if d.track_id < 0 or point_in_any_polygon(
                            (d.foot[0] / fw, d.foot[1] / fh), effective_roi)
                    ]
                else:
                    # Fallback: compare directly (legacy pixel-coord ROI)
                    filtered = [d for d in detections
                                if d.track_id < 0 or point_in_any_polygon(d.foot, effective_roi)]
            else:
                filtered = detections

            try:
                events = rule.update(filtered, camera_id, frame_ts=frame_ts)
                zone_name = getattr(rule, 'zone_name', None)
                if zone_name:
                    for event in events:
                        event['zone_name'] = zone_name
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Rule {rule.rule_name} error: {e}")
        return all_events
