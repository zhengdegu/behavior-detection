"""
Unit tests for BehaviorEngine zone routing.
Tests backward compatibility (empty zones) and zone-based routing.

Feature: per-zone-roi-config
"""
import pytest

from src.config import ZoneConfig
from src.rules.engine import BehaviorEngine


class TestEngineBackwardCompat:
    """Verify backward compatibility when zones is empty (Requirements 2.2, 12.1)"""

    def test_no_zones_uses_toplevel_roi(self):
        """When zones is empty, engine uses rule's top-level roi."""
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "roi": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                "zones": [],
            }
        }
        engine = BehaviorEngine(config)
        assert len(engine.rules) == 1
        assert engine.rules[0].multi_roi != []
        assert not hasattr(engine.rules[0], 'zone_name') or engine.rules[0].zone_name is None

    def test_no_zones_field_at_all(self):
        """When zones field is absent, engine uses rule's top-level roi (backward compat)."""
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "roi": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]],
            }
        }
        engine = BehaviorEngine(config)
        assert len(engine.rules) == 1


class TestEngineZoneRouting:
    """Verify zone-based routing when zones is non-empty (Requirements 2.3, 4.1)"""

    def test_zones_creates_per_zone_rules(self):
        """When zones is non-empty, engine creates one rule per zone."""
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "roi": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],  # should be ignored
                "zones": [
                    {"roi": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]], "name": "Zone A", "max_count": 3},
                    {"roi": [[0.5, 0.5], [0.9, 0.5], [0.9, 0.9]], "name": "Zone B", "max_count": 8},
                ],
            }
        }
        engine = BehaviorEngine(config)
        assert len(engine.rules) == 2
        assert engine.rules[0].zone_name == "Zone A"
        assert engine.rules[1].zone_name == "Zone B"

    def test_zone_params_merged_correctly(self):
        """Zone overrides are merged with rule defaults."""
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "radius": 200,
                "confirm_frames": 5,
                "cooldown": 60,
                "zones": [
                    {"roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], "max_count": 10},
                ],
            }
        }
        engine = BehaviorEngine(config)
        rule = engine.rules[0]
        # max_count overridden by zone
        assert rule.max_count == 10
        # confirm_frames inherited from rule default
        assert rule.confirm_frames == 5

    def test_zone_roi_used_for_rule(self):
        """Each rule instance uses the zone's ROI, not the rule-level ROI."""
        zone_roi = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4]]
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "roi": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
                "zones": [
                    {"roi": zone_roi, "name": "TestZone"},
                ],
            }
        }
        engine = BehaviorEngine(config)
        rule = engine.rules[0]
        # Rule's multi_roi should be the zone's roi, not the rule-level roi
        assert len(rule.multi_roi) == 1
        # Verify points match the zone roi (converted to tuples)
        expected_poly = [(0.2, 0.2), (0.4, 0.2), (0.4, 0.4)]
        assert rule.multi_roi[0] == expected_poly

    def test_multiple_rule_types_with_zones(self):
        """Multiple rule types can each have their own zones."""
        config = {
            "crowd": {
                "enabled": True,
                "max_count": 5,
                "zones": [
                    {"roi": [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]], "name": "Crowd Zone"},
                ],
            },
            "fight": {
                "enabled": True,
                "zones": [
                    {"roi": [[0.5, 0.5], [0.8, 0.5], [0.8, 0.8]], "name": "Fight Zone"},
                ],
            },
        }
        engine = BehaviorEngine(config)
        assert len(engine.rules) == 2
        assert engine.rules[0].zone_name == "Crowd Zone"
        assert engine.rules[1].zone_name == "Fight Zone"


class TestEngineZoneEvents:
    """Verify zone_name is included in events (Requirement 4.4)"""

    def test_zone_name_attribute_set(self):
        """Rule instances from zones have zone_name attribute set."""
        config = {
            "loiter": {
                "enabled": True,
                "zones": [
                    {"roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], "name": "Entrance"},
                ],
            }
        }
        engine = BehaviorEngine(config)
        assert engine.rules[0].zone_name == "Entrance"

    def test_zone_name_none_when_not_set(self):
        """Rule instances from zones without name have zone_name=None."""
        config = {
            "crowd": {
                "enabled": True,
                "zones": [
                    {"roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]},
                ],
            }
        }
        engine = BehaviorEngine(config)
        assert engine.rules[0].zone_name is None
