"""
Configuration models — Pydantic v2
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CrowdConfig(BaseModel):
    enabled: bool = False
    max_count: int = 5
    radius: float = 200
    confirm_frames: int = 5
    cooldown: float = 60


class FightConfig(BaseModel):
    enabled: bool = False
    proximity_radius: float = 150
    min_speed: float = 60
    min_persons: int = 2
    confirm_frames: int = 3
    cooldown: float = 30


class FallConfig(BaseModel):
    enabled: bool = False
    ratio_threshold: float = 1.0
    min_ratio_change: float = 0.5
    min_y_drop: float = 20
    confirm_frames: int = 2
    cooldown: float = 30


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
