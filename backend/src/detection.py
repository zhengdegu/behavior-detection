"""
Detection result data class — standalone module, no torch dependency.
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class Detection:
    """Detection result data class"""
    track_id: int = -1
    class_id: int = 0
    class_name: str = ""
    confidence: float = 0.0
    bbox: list = field(default_factory=lambda: [0, 0, 0, 0])
    center: tuple = (0, 0)
    foot: tuple = (0, 0)
    keypoints: Optional[np.ndarray] = None  # Pose keypoints (17, 3) [x, y, conf]
