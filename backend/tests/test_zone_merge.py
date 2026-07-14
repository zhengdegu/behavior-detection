"""
Property tests for parameter merge logic.
- Property 1: Parameter merge correctness
- Property 2: Zone independence (isolation)

Feature: per-zone-roi-config
"""
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.config import ZoneConfig
from src.rules.engine import merge_zone_params


# ─── Strategies ───────────────────────────────────────────────────────────────

def valid_roi():
    """Strategy for a valid ROI polygon."""
    point = st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False), min_size=2, max_size=2)
    return st.lists(point, min_size=3, max_size=6)


def crowd_defaults():
    """Strategy for crowd rule default parameters."""
    return st.fixed_dictionaries({
        "max_count": st.integers(min_value=1, max_value=100),
        "radius": st.floats(min_value=1.0, max_value=1000, allow_nan=False, allow_infinity=False),
        "confirm_frames": st.integers(min_value=1, max_value=100),
        "cooldown": st.floats(min_value=0.0, max_value=3600, allow_nan=False, allow_infinity=False),
    })


def zone_with_optional_crowd_params(roi):
    """Strategy for ZoneConfig with optional crowd params."""
    return st.builds(
        ZoneConfig,
        roi=st.just(roi),
        max_count=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        radius=st.one_of(st.none(), st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False)),
        confirm_frames=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        cooldown=st.one_of(st.none(), st.floats(min_value=0.0, max_value=3600, allow_nan=False, allow_infinity=False)),
    )


# ─── Property 1: Parameter merge correctness ─────────────────────────────────
# **Validates: Requirements 1.4, 2.4, 3.1, 3.3**

class TestParameterMergeCorrectness:
    """Property 1: Parameter merge correctness"""

    @given(roi=valid_roi(), defaults=crowd_defaults())
    @settings(max_examples=100)
    def test_merge_preserves_zone_overrides(self, roi, defaults):
        """Non-None zone parameter values SHALL appear in merged result."""
        zone = ZoneConfig(roi=roi, max_count=99, confirm_frames=7)
        merged = merge_zone_params(zone, defaults)
        assert merged["max_count"] == 99
        assert merged["confirm_frames"] == 7

    @given(roi=valid_roi(), defaults=crowd_defaults())
    @settings(max_examples=100)
    def test_merge_fills_none_from_defaults(self, roi, defaults):
        """None zone parameter values SHALL use rule default values."""
        zone = ZoneConfig(roi=roi)  # all params None
        merged = merge_zone_params(zone, defaults)
        for key, value in defaults.items():
            assert merged[key] == value

    @given(
        roi=valid_roi(),
        defaults=crowd_defaults(),
        override_max_count=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        override_radius=st.one_of(st.none(), st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False)),
        override_confirm=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
        override_cooldown=st.one_of(st.none(), st.floats(min_value=0.0, max_value=3600, allow_nan=False, allow_infinity=False)),
    )
    @settings(max_examples=100)
    def test_merge_arbitrary_combination(self, roi, defaults, override_max_count, override_radius, override_confirm, override_cooldown):
        """For any combination of None and non-None fields, merge SHALL produce
        correct results: zone value when non-None, default value when None."""
        zone = ZoneConfig(
            roi=roi,
            max_count=override_max_count,
            radius=override_radius,
            confirm_frames=override_confirm,
            cooldown=override_cooldown,
        )
        merged = merge_zone_params(zone, defaults)

        # Check each field
        if override_max_count is not None:
            assert merged["max_count"] == override_max_count
        else:
            assert merged["max_count"] == defaults["max_count"]

        if override_radius is not None:
            assert merged["radius"] == override_radius
        else:
            assert merged["radius"] == defaults["radius"]

        if override_confirm is not None:
            assert merged["confirm_frames"] == override_confirm
        else:
            assert merged["confirm_frames"] == defaults["confirm_frames"]

        if override_cooldown is not None:
            assert merged["cooldown"] == override_cooldown
        else:
            assert merged["cooldown"] == defaults["cooldown"]


# ─── Property 2: Zone independence (isolation) ────────────────────────────────
# **Validates: Requirements 3.2, 4.1, 4.5**

class TestZoneIndependence:
    """Property 2: Zone independence (isolation)"""

    @given(roi=valid_roi(), defaults=crowd_defaults())
    @settings(max_examples=50)
    def test_zones_independent_merge(self, roi, defaults):
        """Merging each zone independently with the same rule defaults SHALL
        produce results that depend only on that zone's own overrides."""
        zone_a = ZoneConfig(roi=roi, max_count=10)
        zone_b = ZoneConfig(roi=roi, max_count=20, confirm_frames=3)

        merged_a = merge_zone_params(zone_a, defaults)
        merged_b = merge_zone_params(zone_b, defaults)

        # Zone A merge should not be affected by Zone B
        assert merged_a["max_count"] == 10
        assert merged_a["confirm_frames"] == defaults["confirm_frames"]

        # Zone B merge should not be affected by Zone A
        assert merged_b["max_count"] == 20
        assert merged_b["confirm_frames"] == 3

    @given(roi=valid_roi(), defaults=crowd_defaults())
    @settings(max_examples=50)
    def test_changing_zone_a_does_not_affect_zone_b(self, roi, defaults):
        """Changing zone A's overrides SHALL NOT alter zone B's merged result."""
        zone_b = ZoneConfig(roi=roi, radius=500.0)
        merged_b_before = merge_zone_params(zone_b, defaults)

        # Create zone A with different overrides — should not affect B
        zone_a = ZoneConfig(roi=roi, radius=100.0, max_count=50)
        merge_zone_params(zone_a, defaults)

        merged_b_after = merge_zone_params(zone_b, defaults)
        assert merged_b_before == merged_b_after
