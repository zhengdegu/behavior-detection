"""
异常规则基类 — confirm_frames + cooldown 防抖机制
"""

import time
from typing import List, Dict, Any
from ..detection import Detection


class BaseAnomalyRule:
    """异常规则基类"""

    def __init__(self, rule_name: str, confirm_frames: int = 5,
                 cooldown: float = 60.0):
        self.rule_name = rule_name
        self.confirm_frames = confirm_frames
        self.cooldown = cooldown
        self._confirm_count: Dict[str, int] = {}
        self._last_trigger: Dict[str, float] = {}

    def _check_confirm_and_cooldown(self, key: str, condition: bool,
                                     now: float = 0.0) -> bool:
        """通用的确认帧 + 冷却检查"""
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

    def update(self, detections: List[Detection],
               camera_id: str = "",
               frame_ts: float = 0.0) -> List[Dict[str, Any]]:
        raise NotImplementedError
