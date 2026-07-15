"""
Configuration models — Pydantic v2
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimePeriod(BaseModel):
    """A time period within a day when detection is active"""
    start: str = "00:00"  # HH:MM format
    end: str = "23:59"    # HH:MM format, supports cross-midnight e.g. "22:00"-"06:00"
    days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # 0=Monday, 6=Sunday (ISO weekday)


class ScheduleConfig(BaseModel):
    """Detection schedule — only detect during specified periods"""
    enabled: bool = False  # False = detect 24/7 (backward compatible)
    periods: List[TimePeriod] = Field(default_factory=list)


class ZoneConfig(BaseModel):
    """单个检测区域配置"""
    model_config = ConfigDict(extra="forbid")

    roi: List[List[float]] = Field(default_factory=list)  # 空=全画面，≥3顶点=有效多边形
    name: Optional[str] = None  # 区域名称标识

    @field_validator('roi')
    @classmethod
    def roi_empty_or_valid_polygon(cls, v: List[List[float]]) -> List[List[float]]:
        """roi 要么为空（全画面），要么至少 3 个顶点（有效多边形）。1-2 点无意义。"""
        if len(v) != 0 and len(v) < 3:
            raise ValueError('roi must be empty (full frame) or have at least 3 vertices')
        return v
    # Crowd 参数
    max_count: Optional[int] = Field(None, ge=1)
    radius: Optional[float] = Field(None, gt=0)
    # Fight 参数
    proximity_radius: Optional[float] = Field(None, gt=0)
    min_speed: Optional[float] = Field(None, gt=0)
    min_persons: Optional[int] = Field(None, ge=2)
    co_move_cos_threshold: Optional[float] = Field(None, ge=0, le=1)
    min_relative_speed: Optional[float] = Field(None, ge=0)
    min_distance_variance: Optional[float] = Field(None, ge=0)
    joint_overlap_threshold: Optional[int] = Field(None, ge=0)
    # Fall 参数
    ratio_threshold: Optional[float] = Field(None, gt=0)
    min_ratio_change: Optional[float] = Field(None, gt=0)
    min_y_drop: Optional[float] = Field(None, gt=0)
    min_hip_velocity: Optional[float] = Field(None, ge=0)
    spine_angle_threshold: Optional[float] = Field(None, gt=0)
    inactivity_frames: Optional[int] = Field(None, ge=1)
    inactivity_threshold: Optional[float] = Field(None, ge=0)
    history_size: Optional[int] = Field(None, ge=1)
    # Loiter 参数
    min_duration: Optional[float] = Field(None, gt=0)
    max_distance: Optional[float] = Field(None, gt=0)
    max_displacement_ratio: Optional[float] = Field(None, gt=0, le=1)
    min_total_path: Optional[float] = Field(None, ge=0)
    trajectory_window: Optional[float] = Field(None, gt=0)
    inertia: Optional[int] = Field(None, ge=0)
    # 通用参数
    confirm_frames: Optional[int] = Field(None, ge=1)
    cooldown: Optional[float] = Field(None, ge=0)


class CrowdConfig(BaseModel):
    enabled: bool = False
    max_count: int = 5
    radius: float = 250
    confirm_frames: int = 8
    cooldown: float = 60
    roi: list = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()


class FightConfig(BaseModel):
    enabled: bool = False
    proximity_radius: float = 180
    min_speed: float = 120  # based on production configs with Pose model
    min_persons: int = 2
    confirm_frames: int = 8
    cooldown: float = 30
    co_move_cos_threshold: float = 0.7
    min_relative_speed: float = 55.0  # px/s, below this = not adversarial
    min_distance_variance: float = 18.0  # px², below this = stable distance
    joint_overlap_threshold: int = 2
    roi: list = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()


class FallConfig(BaseModel):
    enabled: bool = False
    ratio_threshold: float = 1.2
    min_ratio_change: float = 0.4
    min_y_drop: float = 12
    confirm_frames: int = 2
    cooldown: float = 30
    min_hip_velocity: float = 20.0  # min hip drop speed (px/frame)
    spine_angle_threshold: float = 45.0  # angle (deg) below which person is upright
    inactivity_frames: int = 3  # frames of stillness after fall to confirm
    inactivity_threshold: float = 12.0  # max movement (px) to count as inactive
    history_size: int = 10  # pose history buffer size
    roi: list = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()


class LoiterConfig(BaseModel):
    enabled: bool = False
    min_duration: float = 90.0       # Minimum dwell time in ROI (seconds) before evaluating
    max_distance: float = 150.0      # Max displacement from initial position (pixels)
    max_displacement_ratio: float = 0.3  # Net displacement / total path length threshold
    min_total_path: float = 40.0     # Minimum total path (pixels), filters out purely stationary persons
    trajectory_window: float = 60.0  # Sliding window for trajectory analysis (seconds)
    inertia: int = 3                 # Consecutive frames in ROI before counting starts
    confirm_frames: int = 5
    cooldown: float = 90.0
    roi: list = Field(default_factory=list)
    zones: List[ZoneConfig] = Field(default_factory=list)
    schedule: ScheduleConfig = ScheduleConfig()


class RulesConfig(BaseModel):
    crowd: CrowdConfig = CrowdConfig()
    fight: FightConfig = FightConfig()
    fall: FallConfig = FallConfig()
    loiter: LoiterConfig = LoiterConfig()


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
    tls_enabled: bool = False
    tls_insecure: bool = False  # Skip server certificate verification (for self-signed certs)


class CameraMQTTPublishConfig(BaseModel):
    enabled: bool = False
    crowd: bool = True
    fight: bool = True
    fall: bool = True
    loiter: bool = True


class CameraConfig(BaseModel):
    id: str = ""
    name: str = ""
    url: str = ""
    enabled: bool = True  # Whether detection is active for this camera
    detect: DetectConfig = DetectConfig()
    roi: List = Field(default_factory=list)  # Multi-polygon: [[[x,y],...], [[x,y],...]] or legacy single polygon [[x,y],...]
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
