import type {
  Camera,
  CreateCameraRequest,
  UpdateCameraRequest,
  DetectionEvent,
  EventQueryParams,
  SystemStatus,
  AnalysisTask,
  MQTTConfig,
  MQTTStatus,
} from './types';

// ── Error class ──

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// ── Base URL ──

const BASE_URL = import.meta.env.VITE_API_BASE ?? '';

// ── Fetch wrapper ──

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const headers: Record<string, string> = {};
  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, {
    method,
    headers,
    body:
      body instanceof FormData
        ? body
        : body !== undefined
          ? JSON.stringify(body)
          : undefined,
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = await res.json();
      if (data.error) message = data.error;
      else if (data.detail) message = data.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, message);
  }

  // 204 No Content or empty body
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

async function get<T>(path: string): Promise<T> {
  return request<T>('GET', path);
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body);
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body);
}

async function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path);
}

// ── API methods ──

// Cameras
export function getCameras(): Promise<Camera[]> {
  return get<Camera[]>('/api/cameras');
}

export function createCamera(data: CreateCameraRequest): Promise<Camera> {
  return post<Camera>('/api/cameras', data);
}

export function updateCamera(
  id: string,
  data: UpdateCameraRequest,
): Promise<Camera> {
  return put<Camera>(`/api/cameras/${id}`, data);
}

export function deleteCamera(id: string): Promise<void> {
  return del<void>(`/api/cameras/${id}`);
}

export function getCameraSnapshot(id: string): string {
  return `${BASE_URL}/api/cameras/${id}/snapshot`;
}

// Events
export function getEvents(
  params?: EventQueryParams,
): Promise<DetectionEvent[]> {
  const searchParams = new URLSearchParams();
  if (params?.sub_type) searchParams.set('sub_type', params.sub_type);
  if (params?.camera_id) searchParams.set('camera_id', params.camera_id);
  if (params?.limit != null) searchParams.set('limit', String(params.limit));

  const qs = searchParams.toString();
  return get<DetectionEvent[]>(`/api/events${qs ? `?${qs}` : ''}`);
}

// System status
export function getStatus(): Promise<SystemStatus> {
  return get<SystemStatus>('/api/status');
}

// Video analysis
export function uploadVideo(file: File): Promise<AnalysisTask> {
  const formData = new FormData();
  formData.append('file', file);
  return post<AnalysisTask>('/api/video-analysis/upload', formData);
}

export function getAnalysisTasks(): Promise<AnalysisTask[]> {
  return get<AnalysisTask[]>('/api/video-analysis/tasks');
}

export function getAnalysisTask(id: string): Promise<AnalysisTask> {
  return get<AnalysisTask>(`/api/video-analysis/tasks/${id}`);
}

export function startAnalysis(id: string): Promise<void> {
  return post<void>(`/api/video-analysis/tasks/${id}/start`);
}

export function deleteAnalysisTask(id: string): Promise<void> {
  return del<void>(`/api/video-analysis/tasks/${id}`);
}

export function getTaskFirstFrameUrl(id: string): string {
  return `${BASE_URL}/api/video-analysis/tasks/${id}/first_frame`;
}

export function getTaskVideoUrl(id: string): string {
  return `${BASE_URL}/api/video-analysis/tasks/${id}/video`;
}

// go2rtc
export function getGo2RTCStreams(): Promise<Record<string, string>> {
  return get<Record<string, string>>('/api/go2rtc/streams');
}

export function getGo2RTCStatus(): Promise<{ running: boolean; pid: number | null }> {
  return get<{ running: boolean; pid: number | null }>('/api/go2rtc/status');
}

// MQTT config
export function getMQTTConfig(): Promise<MQTTConfig> {
  return get<MQTTConfig>('/api/mqtt/config');
}

export function updateMQTTConfig(data: MQTTConfig): Promise<MQTTConfig> {
  return put<MQTTConfig>('/api/mqtt/config', data);
}

export function getMQTTStatus(): Promise<MQTTStatus> {
  return get<MQTTStatus>('/api/mqtt/status');
}
