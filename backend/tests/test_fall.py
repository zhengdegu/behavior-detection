"""Regression tests for fall confirmation state."""

from src.detection import Detection
from src.rules.fall import FallRule


def _person(track_id=1, bbox=None, center=None):
    bbox = bbox or [0, 0, 100, 100]
    center = center or ((bbox[0] + bbox[2]) / 2,
                        (bbox[1] + bbox[3]) / 2)
    return Detection(
        track_id=track_id,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bbox=bbox,
        center=center,
        foot=(center[0], bbox[3]),
    )


def test_static_fall_survives_final_confirm_frames():
    rule = FallRule(
        confirm_frames=2,
        cooldown=30,
        inactivity_frames=1,
        inactivity_threshold=8,
        static_fall_frames=3,
        lying_ratio_threshold=0.6,
    )
    lying = _person()

    events = []
    for frame in range(1, 6):
        events.extend(rule.update([lying], "cam-1", frame_ts=100.0 + frame))

    assert len(events) == 1
    assert events[0]["sub_type"] == "fall"
    assert "Static fall" in events[0]["detail"]


def test_dynamic_fall_survives_final_confirm_frames():
    rule = FallRule(
        confirm_frames=2,
        cooldown=30,
        min_ratio_change=0.2,
        inactivity_frames=1,
        inactivity_threshold=8,
        static_fall_frames=20,
    )
    standing = _person(bbox=[30, 0, 70, 100], center=(50, 50))
    lying = _person(bbox=[0, 0, 100, 100], center=(50, 50))

    assert rule.update([standing], "cam-1", frame_ts=101.0) == []
    assert rule.update([lying], "cam-1", frame_ts=102.0) == []
    assert rule.update([lying], "cam-1", frame_ts=103.0) == []

    events = rule.update([lying], "cam-1", frame_ts=104.0)

    assert len(events) == 1
    assert events[0]["sub_type"] == "fall"
    assert "Fall confirmed" in events[0]["detail"]


def test_movement_resets_inactivity_counter():
    rule = FallRule(
        confirm_frames=1,
        inactivity_frames=2,
        inactivity_threshold=8,
        static_fall_frames=2,
        lying_ratio_threshold=0.6,
    )

    rule.update([_person(center=(50, 50))], frame_ts=101.0)
    rule.update([_person(center=(50, 50))], frame_ts=102.0)
    rule.update([_person(center=(70, 50))], frame_ts=103.0)

    assert rule._inactivity_count[1] == 0
    assert rule._static_lying_count[1] == 0
