// ── Detection Config ──

export interface DetectConfig {
  fps: number;
  confidence: number;
}

// ── Detection Rules ──

export interface CrowdConfig {
  enabled: boolean;
  max_count: number;
  radius: number;
  confirm_frames: number;
  cooldown: number;
}

export interface FightConfig {
  enabled: boolean;
  proximity_radius: number;
  min_speed: number;
  min_persons: number;
  confirm_frames: number;
  cooldown: number;
}

export interface FallConfig {
  enabled: boolean;
  ratio_threshold: number;
  min_ratio_change: number;
  min_y_drop: number;
  confirm_frames: number;
  cooldown: number;
}

export interface RulesConfig {
  crowd: CrowdConfig;
  fight: FightConfig;
  fall: FallConfig;
}

// ── Camera ──

export interface Camera {
  id: string;
  name: string;
  url: string;
  online?: boolean;
  detect?: DetectConfig;
  roi?: [number, number][];
  rules?: RulesConfig;
  mqtt_publish?: CameraMQTTPublishConfig;
}

export interface CreateCameraRequest {
  id: string;
  name: string;
  url: string;
}

export interface UpdateCameraRequest {
  name?: string;
  url?: string;
  detect?: DetectConfig;
  roi?: [number, number][];
  rules?: RulesConfig;
  mqtt_publish?: CameraMQTTPublishConfig;
}

// ── Detection Events ──

export interface DetectionEvent {
  type: string;
  sub_type: string;
  camera_id: string;
  camera_name: string;
  timestamp: string;
  detail: string;
  track_ids: number[];
  image?: string;
  bbox?: number[][];
}

// ── System Status ──

export interface SystemStatus {
  cameras: number;
  total_events: number;
  uptime: number;
}

// ── Event Query Params ──

export interface EventQueryParams {
  sub_type?: string;
  camera_id?: string;
  limit?: number;
}

// ── Video Analysis ──

export type AnalysisTaskStatus =
  | 'waiting_config'
  | 'processing'
  | 'completed'
  | 'failed';

export interface AnalysisStats {
  max_persons: number;
  avg_persons: number;
  total_detections: number;
  max_confidence: number;
  duration: number;
  total_frames: number;
}

export interface AnalysisTask {
  id: string;
  filename: string;
  status: AnalysisTaskStatus;
  file_size: number;
  created_at: string;
  duration?: number;
  progress?: number;
  events?: DetectionEvent[];
  stats?: AnalysisStats;
}

// ── MQTT Config ──

export interface MQTTConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  topic: string;
  enabled: boolean;
  update_interval: number;
}

export interface MQTTStatus {
  connected: boolean;
  active_sessions: number;
}

export interface CameraMQTTPublishConfig {
  enabled: boolean;
  crowd: boolean;
  fight: boolean;
  fall: boolean;
}
