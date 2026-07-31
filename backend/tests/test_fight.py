"""Regression tests for fight participant grouping and false-positive filters."""

import numpy as np

from src.detection import Detection
from src.rules.engine import BehaviorEngine
from src.rules.fight import FightRule


def _person(track_id, bbox, center=None, keypoints=None):
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
        keypoints=keypoints,
    )


def _stationary_pose(left_wrist, right_wrist):
    keypoints = np.zeros((17, 3), dtype=float)
    keypoints[9] = [*left_wrist, 0.9]
    keypoints[10] = [*right_wrist, 0.9]
    return keypoints


def test_fast_walker_next_to_stationary_person_is_not_fight():
    rule = FightRule(
        proximity_radius=200,
        min_speed=10,
        confirm_frames=1,
        normalized_proximity_threshold=2.0,
        secondary_speed_ratio=0.35,
    )

    frames = [
        [_person(1, [0, 0, 40, 100]),
         _person(2, [80, 0, 120, 100])],
        [_person(1, [30, 0, 70, 100]),
         _person(2, [80, 0, 120, 100])],
        [_person(1, [50, 0, 90, 100]),
         _person(2, [80, 0, 120, 100])],
    ]

    events = []
    for index, detections in enumerate(frames, start=1):
        events.extend(rule.update(detections, frame_ts=100.0 + index))

    assert events == []


def test_stationary_wrists_are_not_cross_matched_as_motion():
    rule = FightRule(
        proximity_radius=200,
        min_speed=10,
        confirm_frames=1,
        normalized_proximity_threshold=2.0,
        secondary_speed_ratio=0.35,
    )
    detections = [
        _person(1, [0, 0, 100, 100],
                keypoints=_stationary_pose((20, 50), (80, 50))),
        _person(2, [80, 0, 180, 100],
                keypoints=_stationary_pose((100, 50), (160, 50))),
    ]

    assert rule.update(detections, frame_ts=101.0) == []
    assert rule.update(detections, frame_ts=102.0) == []


def test_perspective_only_proximity_is_rejected():
    rule = FightRule(
        proximity_radius=200,
        min_speed=10,
        confirm_frames=1,
        normalized_proximity_threshold=1.2,
        secondary_speed_ratio=0.35,
    )

    first = [
        _person(1, [0, 0, 100, 300], center=(50, 150)),
        _person(2, [100, 80, 130, 120], center=(115, 100)),
    ]
    second = [
        _person(1, [20, 0, 120, 300], center=(70, 150)),
        _person(2, [80, 80, 110, 120], center=(95, 100)),
    ]

    assert rule.update(first, frame_ts=101.0) == []
    assert rule.update(second, frame_ts=102.0) == []


def test_mutual_motion_emits_all_participants_and_union_bbox():
    rule = FightRule(
        proximity_radius=200,
        min_speed=10,
        confirm_frames=2,
        normalized_proximity_threshold=1.2,
        secondary_speed_ratio=0.35,
    )

    frame_1 = [
        _person(1, [0, 0, 40, 100]),
        _person(2, [80, 0, 120, 100]),
    ]
    frame_2 = [
        _person(1, [15, 0, 55, 100]),
        _person(2, [65, 0, 105, 100]),
    ]
    frame_3 = [
        _person(1, [30, 0, 70, 100]),
        _person(2, [50, 0, 90, 100]),
    ]

    assert rule.update(frame_1, frame_ts=101.0) == []
    assert rule.update(frame_2, frame_ts=102.0) == []
    events = rule.update(frame_3, "cam-1", frame_ts=103.0)

    assert len(events) == 1
    event = events[0]
    assert event["track_id"] == 1
    assert event["track_ids"] == [1, 2]
    assert event["involved_track_ids"] == [1, 2]
    assert event["involved_count"] == 2
    assert event["bbox"] == [30, 0, 90, 100]


def test_confirmation_resets_when_pair_motion_breaks():
    rule = FightRule(
        proximity_radius=200,
        min_speed=10,
        confirm_frames=2,
        normalized_proximity_threshold=1.2,
        secondary_speed_ratio=0.35,
    )

    rule.update([
        _person(1, [0, 0, 40, 100]),
        _person(2, [80, 0, 120, 100]),
    ], frame_ts=101.0)
    assert rule.update([
        _person(1, [15, 0, 55, 100]),
        _person(2, [65, 0, 105, 100]),
    ], frame_ts=102.0) == []

    assert rule.update([
        _person(1, [30, 0, 70, 100]),
        _person(2, [65, 0, 105, 100]),
    ], frame_ts=103.0) == []
    assert rule._confirm_count["fight_1_2"] == 0


def test_engine_passes_new_fight_thresholds():
    engine = BehaviorEngine({
        "fight": {
            "enabled": True,
            "normalized_proximity_threshold": 0.9,
            "secondary_speed_ratio": 0.5,
        },
    })

    rule = engine.rules[0]
    assert isinstance(rule, FightRule)
    assert rule.normalized_proximity_threshold == 0.9
    assert rule.secondary_speed_ratio == 0.5
