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
        lying_ratio_threshold=1.0,
    )
    lying = _person(bbox=[0, 0, 110, 100])

    events = []
    for frame in range(1, 6):
        events.extend(rule.update([lying], "cam-1", frame_ts=100.0 + frame))

    assert len(events) == 1
    assert events[0]["sub_type"] == "fall"
    assert events[0]["track_id"] == 1
    assert events[0]["track_ids"] == [1]
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
    lying = _person(bbox=[0, 30, 100, 100], center=(50, 65))

    assert rule.update([standing], "cam-1", frame_ts=101.0) == []
    assert rule.update([lying], "cam-1", frame_ts=102.0) == []
    assert rule.update([lying], "cam-1", frame_ts=103.0) == []

    events = rule.update([lying], "cam-1", frame_ts=104.0)

    assert len(events) == 1
    assert events[0]["sub_type"] == "fall"
    assert events[0]["track_id"] == 1
    assert events[0]["track_ids"] == [1]
    assert "Fall confirmed" in events[0]["detail"]


def test_walking_shape_change_does_not_start_fall():
    rule = FallRule(
        confirm_frames=1,
        inactivity_frames=1,
        static_fall_frames=3,
        ratio_threshold=0.9,
        # Legacy saved configs used 0.6; the rule applies a safe static floor.
        lying_ratio_threshold=0.6,
        min_ratio_change=0.2,
        min_y_drop=5,
        min_area_change=0.35,
    )
    standing = _person(bbox=[30, 0, 70, 100], center=(50, 50))
    walking = _person(bbox=[2, 0, 97, 100], center=(49.5, 50))

    assert rule.update([standing], frame_ts=101.0) == []
    assert rule.update([walking], frame_ts=102.0) == []
    assert 1 not in rule._falling_detected

    for frame in range(103, 110):
        assert rule.update([walking], frame_ts=float(frame)) == []


def test_moving_candidate_times_out_without_alert():
    rule = FallRule(
        confirm_frames=1,
        inactivity_frames=2,
        inactivity_threshold=8,
        static_fall_frames=20,
        ratio_threshold=0.9,
        lying_ratio_threshold=1.5,
        min_ratio_change=0.2,
        min_y_drop=5,
        min_area_change=0.35,
        candidate_timeout=3.0,
    )
    standing = _person(bbox=[30, 0, 70, 100], center=(50, 50))
    candidate = _person(bbox=[0, 20, 100, 100], center=(50, 60))

    assert rule.update([standing], frame_ts=101.0) == []
    assert rule.update([candidate], frame_ts=102.0) == []
    assert 1 in rule._falling_detected

    for offset, frame in enumerate(range(103, 107), start=1):
        moving = _person(
            bbox=[offset * 20, 20, 100 + offset * 20, 100],
            center=(50 + offset * 20, 60),
        )
        assert rule.update([moving], frame_ts=float(frame)) == []

    assert 1 not in rule._falling_detected


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
