"""
Anomaly rule base class — confirm_frames + cooldown debounce mechanism
"""

import time
from typing import List, Dict, Any
from ..detection import Detection


class BaseAnomalyRule:
    """Anomaly rule base class"""

    def __init__(self, rule_name: str, confirm_frames: int = 5,
                 cooldown: float = 60.0):
        self.rule_name = rule_name
        self.confirm_frames = confirm_frames
        self.cooldown = cooldown
        self._confirm_count: Dict[str, int] = {}
        self._last_trigger: Dict[str, float] = {}

    def _check_confirm_and_cooldown(self, key: str, condition: bool,
                                     now: float = 0.0) -> bool:
        """Generic confirm frames + cooldown check"""
        if now <= 0:
            now = time.time()
        if condition:
            self._confirm_count[key] = self._confirm_count.get(key, 0) + 1
        else:
            self._confirm_count[key] = 0
            return False

        if self._confirm_count[key] < self.confirm_frames:
            return False

        last = self._last_trigger.get(key, 0)
        if now - last < self.cooldown:
            return False

        self._last_trigger[key] = now
        return True

    def reset_confirm(self):
        """Reset confirm counters — called when schedule skips this rule to prevent cross-period accumulation"""
        self._confirm_count.clear()

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        raise NotImplementedError
