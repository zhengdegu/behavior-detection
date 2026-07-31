"""Helpers shared by event persistence, rendering, and publishing."""

from typing import List


def extract_track_ids(event: dict) -> List[int]:
    """Return every participant ID from legacy and current event fields."""
    track_ids = set()
    for field in ("track_ids", "involved_track_ids"):
        values = event.get(field) or []
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        for value in values:
            try:
                track_ids.add(int(value))
            except (TypeError, ValueError):
                continue

    primary = event.get("track_id")
    if primary is not None:
        try:
            track_ids.add(int(primary))
        except (TypeError, ValueError):
            pass

    return sorted(track_ids)
