"""
Configuration models — Pydantic v2
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TimePeriod(BaseModel):
    """A time period within a day when detection is active"""
    start: str = "00:00"  # HH:MM format
    end: str = "23:59"    # HH:MM format, supports cross-midnight e.g. "22:00"-"06:00"
    days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # 0=Monday, 6=Sunday (ISO weekday)


class ScheduleConfig(BaseModel):
    """Detection schedule — only detect during specified periods"""
    enabled: bool = False  # False = detect 24/7 (backward compatible)
    periods: List[TimePeriod] = Field(default_factory=list)


class CrowdConfig(BaseModel):
    enabled: bool = False
    max_count: int = 5
    radius: float = 200
    confirm_frames: int = 5
    cooldown: float = 60
    schedule: ScheduleConfig = ScheduleConfig()


class FightConfig(BaseModel):
    enabled: bool = False
    proximity_radius: float = 150
    min_speed: float = 80  # raised from 60 to avoid normal walking triggers
    min_persons: int = 2
    confirm_frames: int = 6  # raised from 3 for more robust confirmation
    cooldown: float = 30
    # Co-moving filter: direction cosine > threshold + low relative speed = walking together
    co_move_cos_threshold: float = 0.7
    min_relative_speed: float = 40.0  # px/s, below this = not adversarial
    # Distance stability: low variance in inter-person distance = co-walking
    min_distance_variance: float = 10.0  # px², below this = stable distance
    # Joint overlap: limbs entering opponent's bbox
    joint_overlap_threshold: int = 1
    schedule: ScheduleConfig = ScheduleConfig()


class FallConfig(BaseModel):
    enabled: bool = False
    ratio_threshold: float = 1.0
    min_ratio_change: float = 0.5
    min_y_drop: float = 20
    confirm_frames: int = 5
    cooldown: float = 30
    # Enhanced detection parameters
    min_hip_velocity: float = 30.0  # min hip drop speed (px/frame) to distinguish fall from bending
    spine_angle_threshold: float = 45.0  # angle (deg) below which person is upright
    inactivity_frames: int = 3  # frames of stillness after fall to confirm
    inactivity_threshold: float = 15.0  # max movement (px) to count as inactive
    history_size: int = 10  # pose history buffer size
    schedule: ScheduleConfig = ScheduleConfig()


class RulesConfig(BaseModel):
    crowd: CrowdConfig = CrowdConfig()
    fight: FightConfig = FightConfig()
    fall: FallConfig = FallConfig()


class DetectConfig(BaseModel):
    fps: int = Field(5, ge=1, le=30)
    confidence: float = Field(0.5, ge=0.1, le=1.0)


class MQTTConfig(BaseModel):
    host: str = ""
    port: int = Field(1883, ge=1, le=65535)
    username: str = ""
    password: str = ""
    topic: str = "behavior-detection/events"
    enabled: bool = False
    update_interval: int = Field(30, ge=5, le=3600)


class CameraMQTTPublishConfig(BaseModel):
    enabled: bool = False
    crowd: bool = True
    fight: bool = True
    fall: bool = True


class CameraConfig(BaseModel):
    id: str = ""
    name: str = ""
    url: str = ""
    detect: DetectConfig = DetectConfig()
    roi: List[List[float]] = Field(default_factory=list)
    rules: RulesConfig = RulesConfig()
    mqtt_publish: CameraMQTTPublishConfig = CameraMQTTPublishConfig()
    timezone: Optional[str] = Field(None, description="Camera timezone (IANA format, e.g. 'Asia/Shanghai', 'America/New_York'). Used to calculate time offset between camera and server.")


class ModelConfig(BaseModel):
    detector_path: str = "data/models/yolo26m.pt"
    confidence: float = 0.5
    pose_path: str = "data/models/yolo26m-pose.pt"
    pose_confidence: float = 0.3
    tracker_config: str = "bytetrack.yaml"


class Go2RTCConfig(BaseModel):
    webrtc_candidates: str = ""  # Comma-separated IP:port list, e.g. "192.168.104.48:1988"


class AppConfig(BaseModel):
    model: ModelConfig = ModelConfig()
    cameras: List[CameraConfig] = Field(default_factory=list)
