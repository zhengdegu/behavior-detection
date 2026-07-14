"""
Property tests for ZoneConfig data model.
- Property 3: ROI polygon validation
- Property 7: Serialization round-trip

Feature: per-zone-roi-config
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.config import ZoneConfig, CrowdConfig, FightConfig, FallConfig, LoiterConfig
from pydantic import ValidationError


# ─── Strategies ───────────────────────────────────────────────────────────────

def roi_point():
    """Strategy for a single ROI point [x, y] with normalized coordinates."""
    return st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=2, max_size=2)


def valid_roi(min_vertices=3, max_vertices=10):
    """Strategy for a valid ROI polygon (>= 3 vertices)."""
    return st.lists(roi_point(), min_size=min_vertices, max_size=max_vertices)


def invalid_roi():
    """Strategy for an invalid ROI polygon (< 3 vertices)."""
    return st.lists(roi_point(), min_size=0, max_size=2)


def optional_zone_params():
    """Strategy for optional ZoneConfig parameters."""
    return st.fixed_dictionaries({}, optional={
        "name": st.one_of(st.none(), st.text(min_size=1, max_size=20)),
        "max_count": st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        "radius": st.one_of(st.none(), st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False)),
        "proximity_radius": st.one_of(st.none(), st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False)),
        "min_speed": st.one_of(st.none(), st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False)),
        "min_persons": st.one_of(st.none(), st.integers(min_value=2, max_value=50)),
        "confirm_frames": st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        "cooldown": st.one_of(st.none(), st.floats(min_value=0.0, max_value=3600, allow_nan=False, allow_infinity=False)),
        "min_duration": st.one_of(st.none(), st.floats(min_value=0.01, max_value=3600, allow_nan=False, allow_infinity=False)),
        "max_distance": st.one_of(st.none(), st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False)),
    })


# ─── Property 3: ROI polygon validation ──────────────────────────────────────
# **Validates: Requirements 1.1, 5.3**

class TestROIPolygonValidation:
    """Property 3: ROI polygon validation"""

    @given(roi=invalid_roi())
    @settings(max_examples=50)
    def test_1_or_2_vertices_raises_validation_error(self, roi):
        """For any list of coordinate pairs with 1-2 elements,
        constructing a ZoneConfig SHALL raise a validation error."""
        assume(1 <= len(roi) <= 2)
        with pytest.raises(ValidationError):
            ZoneConfig(roi=roi)

    def test_empty_roi_succeeds(self):
        """Empty roi (0 vertices) is valid — means full frame detection."""
        zone = ZoneConfig(roi=[])
        assert zone.roi == []

    @given(roi=valid_roi())
    @settings(max_examples=50)
    def test_3_or_more_vertices_succeeds(self, roi):
        """For any list of coordinate pairs with 3 or more elements,
        constructing a ZoneConfig SHALL succeed."""
        zone = ZoneConfig(roi=roi)
        assert zone.roi == roi
        assert len(zone.roi) >= 3


# ─── Property 7: Serialization round-trip ─────────────────────────────────────
# **Validates: Requirements 13.1, 13.2, 13.3**

class TestSerializationRoundTrip:
    """Property 7: Serialization round-trip"""

    @given(roi=valid_roi(), params=optional_zone_params())
    @settings(max_examples=50)
    def test_roundtrip_consistency(self, roi, params):
        """For any valid ZoneConfig object, serializing it to JSON
        (with exclude_none=True) then deserializing back SHALL produce
        an object equivalent to the original."""
        zone = ZoneConfig(roi=roi, **params)

        # Serialize with exclude_none
        serialized = zone.model_dump(exclude_none=True)

        # Deserialize back
        deserialized = ZoneConfig(**serialized)

        # Verify equivalence
        assert deserialized.roi == zone.roi
        assert deserialized.name == zone.name
        assert deserialized.model_dump() == zone.model_dump()

    @given(roi=valid_roi())
    @settings(max_examples=30)
    def test_none_fields_excluded_in_serialization(self, roi):
        """None fields SHALL be excluded from serialized output."""
        zone = ZoneConfig(roi=roi)  # all optional params are None
        serialized = zone.model_dump(exclude_none=True)
        assert "roi" in serialized
        # None fields should not appear
        assert "max_count" not in serialized
        assert "name" not in serialized
        assert "confirm_frames" not in serialized


# ─── Unit tests: zones field on rule configs ──────────────────────────────────

class TestRuleConfigZonesField:
    """Unit tests for zones field on rule configs (Requirements 2.1, 12.1, 12.2)"""

    def test_crowd_config_zones_default_empty(self):
        cfg = CrowdConfig()
        assert cfg.zones == []

    def test_fight_config_zones_default_empty(self):
        cfg = FightConfig()
        assert cfg.zones == []

    def test_fall_config_zones_default_empty(self):
        cfg = FallConfig()
        assert cfg.zones == []

    def test_loiter_config_zones_default_empty(self):
        cfg = LoiterConfig()
        assert cfg.zones == []

    def test_crowd_config_with_zones(self):
        zone_data = {"roi": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]], "max_count": 10}
        cfg = CrowdConfig(zones=[ZoneConfig(**zone_data)])
        assert len(cfg.zones) == 1
        assert cfg.zones[0].max_count == 10

    def test_backward_compat_no_zones_in_dict(self):
        """When zones field is not provided, it defaults to empty list."""
        cfg = CrowdConfig(**{"enabled": True, "max_count": 3})
        assert cfg.zones == []
