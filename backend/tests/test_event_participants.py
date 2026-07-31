"""Tests for consistent participant IDs across event consumers."""

from src.database import DatabaseManager, EventRepository
from src.event_utils import extract_track_ids


def test_extract_track_ids_merges_current_and_legacy_fields():
    event = {
        "track_id": 3,
        "track_ids": [2, 3],
        "involved_track_ids": [1, 2],
    }

    assert extract_track_ids(event) == [1, 2, 3]


def test_event_repository_persists_legacy_fight_participants(tmp_path):
    database = DatabaseManager(str(tmp_path / "events.db"))
    repository = EventRepository(database)
    try:
        repository.save({
            "type": "anomaly",
            "sub_type": "fight",
            "camera_id": "cam-1",
            "timestamp": 100.0,
            "track_id": 1,
            "involved_track_ids": [1, 2],
        })

        events = repository.query(sub_type="fight")
        assert len(events) == 1
        assert events[0]["track_ids"] == [1, 2]
        assert events[0]["involved_track_ids"] == [1, 2]
    finally:
        database.close()
