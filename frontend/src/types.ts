// ── Detection Config ──

export interface DetectConfig {
  fps: number;
  confidence: number;
}

// ── Detection Schedule ──

export interface TimePeriod {
  start: string; // "HH:MM"
  end: string;   // "HH:MM"
  days: number[]; // 0=Monday, 6=Sunday
}

export interface ScheduleConfig {
  enabled: boolean;
  periods: TimePeriod[];
}

// ── Detection Rules ──

export interface CrowdConfig {
  enabled: boolean;
  max_count: number;
  radius: number;
  confirm_frames: number;
  cooldown: number;
  roi?: [number, number][];
  schedule?: ScheduleConfig;
}

export interface FightConfig {
  enabled: boolean;
  proximity_radius: number;
  min_speed: number;
  min_persons: number;
  confirm_frames: number;
  cooldown: number;
  co_move_cos_threshold?: number;
  min_relative_speed?: number;
  min_distance_variance?: number;
  joint_overlap_threshold?: number;
  roi?: [number, number][];
  schedule?: ScheduleConfig;
}

export interface FallConfig {
  enabled: boolean;
  ratio_threshold: number;
  min_ratio_change: number;
  min_y_drop: number;
  confirm_frames: number;
  cooldown: number;
  min_hip_velocity?: number;
  spine_angle_threshold?: number;
  inactivity_frames?: number;
  inactivity_threshold?: number;
  history_size?: number;
  roi?: [number, number][];
  schedule?: ScheduleConfig;
}

export interface LoiterConfig {
  enabled: boolean;
  min_duration: number;
  max_distance: number;
  max_displacement_ratio: number;
  min_total_path: number;
  trajectory_window: number;
  inertia: number;
  confirm_frames: number;
  cooldown: number;
  roi?: [number, number][];
  schedule?: ScheduleConfig;
}

export interface RulesConfig {
  crowd: CrowdConfig;
  fight: FightConfig;
  fall: FallConfig;
  loiter: LoiterConfig;
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
  timestamp: string | number;
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
  tls_enabled: boolean;
  tls_insecure: boolean;
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
  loiter: boolean;
}

// ── go2rtc Config ──

export interface Go2RTCConfig {
  webrtc_candidates: string;
}
