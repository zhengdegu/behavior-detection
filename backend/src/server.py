"""
FastAPI Web 服务 — REST API + go2rtc 反向代理 + WebSocket 事件/检测推送
"""

import asyncio
import json
import time
import logging
import uuid
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone

import cv2
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse as StarletteFileResponse
from pydantic import BaseModel, Field

from .config import CameraConfig, RulesConfig, DetectConfig, AppConfig, MQTTConfig, CameraMQTTPublishConfig
from .analyzer import CameraAnalyzer

logger = logging.getLogger(__name__)

app = FastAPI(title="行为异常检测系统", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── SPA 路由回退中间件 ──

# 前端静态资源目录（由多阶段 Docker 构建复制）
FRONTEND_DIR = Path(__file__).parent.parent / "static" / "frontend"


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    """SPA 路由回退：非 API/WS/静态文件的 404 请求返回 index.html"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if (response.status_code == 404
                and request.method == "GET"
                and not self._is_api_path(request.url.path)):
            index_file = FRONTEND_DIR / "index.html"
            if index_file.exists():
                return StarletteFileResponse(str(index_file), media_type="text/html")

        return response

    @staticmethod
    def _is_api_path(path: str) -> bool:
        """判断是否为 API/资源路径（不应回退到 index.html）"""
        api_prefixes = ("/api/", "/ws/", "/go2rtc/", "/events/")
        return any(path.startswith(p) for p in api_prefixes)


# 仅在前端目录存在时注册 SPA 回退中间件
if FRONTEND_DIR.exists():
    app.add_middleware(SPAFallbackMiddleware)
    logger.info(f"前端目录已找到: {FRONTEND_DIR}")
else:
    logger.warning(f"前端目录未找到: {FRONTEND_DIR}，仅运行后端 API")

# 事件截图目录 — 静态文件服务
import os
EVENTS_DIR = Path(__file__).parent.parent / "data" / "events"
os.makedirs(str(EVENTS_DIR), exist_ok=True)
app.mount("/events", StaticFiles(directory=str(EVENTS_DIR)), name="events")

# 视频上传 / 标注输出目录
UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
OUTPUTS_DIR = Path(__file__).parent.parent / "data" / "outputs"
os.makedirs(str(UPLOADS_DIR), exist_ok=True)
os.makedirs(str(OUTPUTS_DIR), exist_ok=True)

# 全局状态（由 main.py 注入）
_analyzers: Dict[str, Any] = {}
_model_config: dict = {}  # 模型配置（从 ModelRepository 加载）
_events: List[Dict[str, Any]] = []
_events_max = 1000
_ws_clients: List[WebSocket] = []
_event_loop = None

# Detection WebSocket 客户端（按 camera_id 分组）
_detection_ws_clients: Dict[str, List[WebSocket]] = {}

# go2rtc 管理器实例（由 main.py 通过 register_go2rtc 注入）
_go2rtc_mgr = None

# go2rtc 反向代理目标地址
_GO2RTC_BASE_URL = "http://127.0.0.1:1984"
_GO2RTC_WS_URL = "ws://127.0.0.1:1984"

# 数据库 Repository 实例（由 main.py 通过 register_repositories 注入）
_camera_repo = None
_model_repo = None
_task_repo = None

# MQTT 组件实例（由 main.py 通过 register_mqtt 注入）
_mqtt_config_repo = None
_mqtt_publisher = None
_event_session_mgr = None


@app.on_event("startup")
async def _on_startup():
    global _event_loop
    _event_loop = asyncio.get_running_loop()


def register_analyzers(analyzers: dict):
    global _analyzers
    _analyzers = analyzers


def register_repositories(camera_repo, model_repo, task_repo):
    """注入数据库 Repository 实例和模型配置（由 main.py 调用）"""
    global _camera_repo, _model_repo, _task_repo, _model_config
    _camera_repo = camera_repo
    _model_repo = model_repo
    _task_repo = task_repo
    # 从 ModelRepository 加载模型配置到内存 dict（供 _run_video_analysis 使用）
    _model_config = model_repo.get().model_dump()


def push_event(event: dict):
    """接收事件，存储并广播到 WebSocket"""
    _events.append(event)
    if len(_events) > _events_max:
        _events.pop(0)
    _broadcast_ws(event)


def _broadcast_ws(event: dict):
    if not _ws_clients or _event_loop is None:
        return
    msg = json.dumps(event, ensure_ascii=False, default=str)
    for ws in list(_ws_clients):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), _event_loop)
        except Exception:
            pass


def register_go2rtc(mgr):
    """注入 Go2RTCManager 实例（由 main.py 调用）"""
    global _go2rtc_mgr
    _go2rtc_mgr = mgr


def register_mqtt(mqtt_config_repo, mqtt_publisher, event_session_mgr):
    """注入 MQTT 组件实例（由 main.py 调用）"""
    global _mqtt_config_repo, _mqtt_publisher, _event_session_mgr
    _mqtt_config_repo = mqtt_config_repo
    _mqtt_publisher = mqtt_publisher
    _event_session_mgr = event_session_mgr


def push_detections(camera_id: str, timestamp: float, detections: list):
    """推送检测数据到所有订阅该 camera_id 的 WebSocket 客户端"""
    clients = _detection_ws_clients.get(camera_id)
    if not clients or _event_loop is None:
        return
    msg = json.dumps({
        "camera_id": camera_id,
        "timestamp": timestamp,
        "detections": detections,
    }, ensure_ascii=False)
    for ws in list(clients):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), _event_loop)
        except Exception:
            # 发送失败，移除该客户端
            if ws in clients:
                clients.remove(ws)


# ── REST API ──

# ── 请求模型 ──

class CreateCameraRequest(BaseModel):
    id: str
    name: str
    url: str


class UpdateCameraRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    detect: Optional[DetectConfig] = None
    roi: Optional[List[List[float]]] = None
    rules: Optional[RulesConfig] = None
    mqtt_publish: Optional[CameraMQTTPublishConfig] = None


@app.get("/api/cameras")
async def list_cameras():
    cameras = []
    # 从数据库加载所有摄像头配置
    db_configs = {cfg.id: cfg for cfg in _camera_repo.get_all()} if _camera_repo else {}

    for cid, analyzer in _analyzers.items():
        cfg = db_configs.get(cid)
        online = analyzer.get_frame() is not None
        camera_info: Dict[str, Any] = {
            "id": cid,
            "name": analyzer.camera_name,
            "url": analyzer.url,
            "online": online,
        }
        if cfg:
            camera_info["detect"] = cfg.detect.model_dump()
            camera_info["roi"] = cfg.roi
            camera_info["rules"] = cfg.rules.model_dump()
            camera_info["mqtt_publish"] = cfg.mqtt_publish.model_dump()
        else:
            camera_info["detect"] = DetectConfig().model_dump()
            camera_info["roi"] = []
            camera_info["rules"] = RulesConfig().model_dump()
            camera_info["mqtt_publish"] = CameraMQTTPublishConfig().model_dump()
        cameras.append(camera_info)
    return cameras


@app.post("/api/cameras")
async def create_camera(req: CreateCameraRequest):
    if req.id in _analyzers:
        return JSONResponse({"error": f"Camera '{req.id}' already exists"}, status_code=409)

    # 创建配置
    cam_cfg = CameraConfig(id=req.id, name=req.name, url=req.url)

    # 持久化到数据库
    _camera_repo.create(cam_cfg)

    # 注册流到 go2rtc
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.add_stream(req.id, req.url)

    # 启动分析器
    cam_dict = cam_cfg.model_dump()
    restream_url = _go2rtc_mgr.get_restream_url(req.id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

    analyzer = CameraAnalyzer(
        camera_config=cam_dict,
        model_config=_model_config,
        on_event=push_event,
        on_detections=push_detections,
        restream_url=restream_url,
        event_session_mgr=_event_session_mgr,
    )
    _analyzers[req.id] = analyzer
    analyzer.start()

    return {
        "id": req.id,
        "name": req.name,
        "url": req.url,
        "online": False,
        "detect": cam_cfg.detect.model_dump(),
        "roi": cam_cfg.roi,
        "rules": cam_cfg.rules.model_dump(),
        "mqtt_publish": cam_cfg.mqtt_publish.model_dump(),
    }


@app.put("/api/cameras/{camera_id}")
async def update_camera(camera_id: str, req: UpdateCameraRequest):
    if camera_id not in _analyzers:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    if not cfg:
        return JSONResponse({"error": f"Camera config for '{camera_id}' not found"}, status_code=404)

    # 更新配置字段
    if req.name is not None:
        cfg.name = req.name
    if req.url is not None:
        cfg.url = req.url
    if req.detect is not None:
        cfg.detect = req.detect
    if req.roi is not None:
        cfg.roi = req.roi
    if req.rules is not None:
        cfg.rules = req.rules
    if req.mqtt_publish is not None:
        cfg.mqtt_publish = req.mqtt_publish

    # 持久化到数据库
    _camera_repo.update(cfg)

    # 更新 go2rtc 流（URL 变更时）
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.add_stream(camera_id, cfg.url)

    # 停止旧分析器，启动新分析器（使用更新后的配置）
    old_analyzer = _analyzers.get(camera_id)
    if old_analyzer:
        old_analyzer.stop()

    cam_dict = cfg.model_dump()
    restream_url = _go2rtc_mgr.get_restream_url(camera_id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

    new_analyzer = CameraAnalyzer(
        camera_config=cam_dict,
        model_config=_model_config,
        on_event=push_event,
        on_detections=push_detections,
        restream_url=restream_url,
        event_session_mgr=_event_session_mgr,
    )
    _analyzers[camera_id] = new_analyzer
    new_analyzer.start()

    return {
        "id": camera_id,
        "name": cfg.name,
        "url": cfg.url,
        "online": False,
        "detect": cfg.detect.model_dump(),
        "roi": cfg.roi,
        "rules": cfg.rules.model_dump(),
        "mqtt_publish": cfg.mqtt_publish.model_dump(),
    }


@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    if camera_id not in _analyzers:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    # 停止分析器
    analyzer = _analyzers.pop(camera_id)
    analyzer.stop()

    # 从 go2rtc 移除流
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.remove_stream(camera_id)

    # 从数据库删除配置
    _camera_repo.delete(camera_id)

    return {"message": f"Camera '{camera_id}' deleted"}


@app.get("/api/cameras/{camera_id}/snapshot")
async def camera_snapshot(camera_id: str):
    analyzer = _analyzers.get(camera_id)
    if not analyzer:
        return JSONResponse({"error": "Camera not found"}, status_code=404)

    frame = analyzer.get_frame()
    if frame is None:
        return JSONResponse({"error": "No frame available"}, status_code=503)

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.get("/api/events")
async def list_events(
    sub_type: str = Query(None, description="过滤事件子类型: crowd/fight/fall"),
    camera_id: str = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    filtered = _events
    if sub_type:
        filtered = [e for e in filtered if e.get("sub_type") == sub_type]
    if camera_id:
        filtered = [e for e in filtered if e.get("camera_id") == camera_id]
    return filtered[-limit:]


@app.get("/api/status")
async def system_status():
    return {
        "cameras": len(_analyzers),
        "total_events": len(_events),
        "uptime": time.time(),
    }


# ── 视频分析 API ──

def _get_video_duration(filepath: str) -> float:
    """获取视频时长（秒）"""
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps > 0:
        return frame_count / fps
    return 0.0


def _convert_to_h264(filepath: str):
    """用 ffmpeg 将 mp4v 编码转为 H.264（浏览器兼容）"""
    import subprocess
    h264_path = filepath.replace(".mp4", "_h264.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c:v", "libx264", "-preset", "fast",
             "-crf", "23", "-c:a", "copy", "-movflags", "+faststart", h264_path],
            capture_output=True, timeout=300,
        )
        if os.path.exists(h264_path) and os.path.getsize(h264_path) > 0:
            os.replace(h264_path, filepath)
            logger.info(f"[VideoAnalysis] H.264 转码完成: {filepath}")
        else:
            logger.warning("[VideoAnalysis] ffmpeg 转码输出为空，保留原始 mp4v 编码")
    except FileNotFoundError:
        logger.warning("[VideoAnalysis] ffmpeg 未安装，浏览器可能无法播放视频")
    except Exception as e:
        logger.warning(f"[VideoAnalysis] ffmpeg 转码失败: {e}，保留原始 mp4v 编码")


def _run_video_analysis(task_id: str):
    """在后台线程中运行视频分析"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return

    _task_repo.update_status(task_id, "processing", 0)

    input_path = str(UPLOADS_DIR / task["filename"])
    output_path = str(OUTPUTS_DIR / f"{task_id}_annotated.mp4")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        _task_repo.update_status(task_id, "failed", 0)
        logger.error(f"[VideoAnalysis] 无法打开视频: {input_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    try:
        from .detector import YOLODetector
        from .rules.engine import BehaviorEngine

        mc = _model_config or {}
        detector = YOLODetector(
            model_path=mc.get("detector_path", "data/models/yolo26m.pt"),
            confidence=mc.get("confidence", 0.5),
            tracker_config=mc.get("tracker_config", "bytetrack.yaml"),
        )

        # 使用任务中保存的 ROI 和默认规则配置
        roi = task.get("roi") or []
        rules_cfg = task.get("rules") or {
            "crowd": {"enabled": True, "max_count": 3, "radius": 300,
                      "confirm_frames": 3, "cooldown": 10},
            "fight": {"enabled": True, "proximity_radius": 200, "min_speed": 30,
                      "min_persons": 2, "confirm_frames": 2, "cooldown": 10},
            "fall": {"enabled": True, "ratio_threshold": 0.8, "min_ratio_change": 0.3,
                     "min_y_drop": 10, "confirm_frames": 2, "cooldown": 10},
        }
        engine = BehaviorEngine(rules_cfg, roi=roi if roi else None)
        logger.info(f"[VideoAnalysis] 任务 {task_id} 规则配置: {rules_cfg}")
        logger.info(f"[VideoAnalysis] 引擎已加载 {len(engine.rules)} 条规则")

        all_events = []
        stats = {
            "max_persons": 0,
            "avg_persons": 0.0,
            "total_detections": 0,
            "max_confidence": 0.0,
            "duration": 0.0,
            "total_frames": total_frames,
        }
        person_counts = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_ts = frame_idx / fps
            detections = detector.track(frame)

            # 统计
            person_count = len([d for d in detections if d.track_id >= 0])
            person_counts.append(person_count)
            stats["total_detections"] += person_count
            if person_count > stats["max_persons"]:
                stats["max_persons"] = person_count
            for d in detections:
                if d.confidence > stats["max_confidence"]:
                    stats["max_confidence"] = d.confidence

            # 行为检测
            events = engine.update(detections, camera_id=f"video_{task_id}", frame_ts=frame_ts)
            for evt in events:
                evt["timestamp"] = frame_ts
                evt["frame_index"] = frame_idx
                all_events.append(evt)
                logger.info(f"[VideoAnalysis] 事件: {evt.get('sub_type')} @ frame {frame_idx}")

            # 每100帧输出一次统计
            if frame_idx % 100 == 0:
                logger.info(f"[VideoAnalysis] frame={frame_idx}/{total_frames}, persons={person_count}, events_so_far={len(all_events)}")

            # 绘制标注帧
            annotated = frame.copy()
            for det in detections:
                if det.track_id < 0:
                    continue
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{det.class_name} #{det.track_id}"
                cv2.putText(annotated, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            for evt in events:
                sub = evt.get("sub_type", "")
                bbox = evt.get("bbox")
                if bbox:
                    ex1, ey1, ex2, ey2 = [int(v) for v in bbox]
                    color = {"crowd": (0, 0, 255), "fight": (0, 0, 255),
                             "fall": (0, 165, 255)}.get(sub, (0, 0, 255))
                    cv2.rectangle(annotated, (ex1, ey1), (ex2, ey2), color, 3)
                    cv2.putText(annotated, sub.upper(), (ex1, max(ey1 - 10, 16)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            writer.write(annotated)
            frame_idx += 1

            # 定期更新进度到数据库（每 30 帧）
            if total_frames > 0 and frame_idx % 30 == 0:
                progress = int((frame_idx / total_frames) * 100)
                _task_repo.update_status(task_id, "processing", progress)

        # 完成统计
        stats["duration"] = frame_idx / fps if fps > 0 else 0.0
        stats["avg_persons"] = (
            sum(person_counts) / len(person_counts) if person_counts else 0.0
        )
        stats["total_frames"] = frame_idx

        # 保存结果到数据库
        output_video = f"{task_id}_annotated.mp4"
        _task_repo.update_result(task_id, all_events, stats, output_video)
        _task_repo.update_status(task_id, "completed", 100)
        logger.info(f"[VideoAnalysis] 任务 {task_id} 完成, {len(all_events)} 个事件")

    except Exception as e:
        _task_repo.update_status(task_id, "failed", 0)
        logger.error(f"[VideoAnalysis] 任务 {task_id} 失败: {e}")
    finally:
        cap.release()
        writer.release()

        # 转码为 H.264 以便浏览器播放
        _convert_to_h264(output_path)


@app.post("/api/video-analysis/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传视频文件，创建分析任务"""
    task_id = str(uuid.uuid4())
    filename = f"{task_id}_{file.filename}"
    filepath = UPLOADS_DIR / filename

    # 保存上传文件
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    file_size = len(content)

    # 获取视频时长
    duration = _get_video_duration(str(filepath))

    task = {
        "id": task_id,
        "filename": filename,
        "original_filename": file.filename,
        "status": "waiting_config",
        "file_size": file_size,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duration": duration,
        "progress": 0,
        "events": [],
        "stats": None,
        "roi": [],
        "rules": None,
        "output_video": None,
    }
    _task_repo.create(task)

    return _serialize_task(task)


@app.get("/api/video-analysis/tasks")
async def list_analysis_tasks():
    """获取所有分析任务列表"""
    tasks = _task_repo.get_all() if _task_repo else []
    return [_serialize_task(t) for t in tasks]


@app.get("/api/video-analysis/tasks/{task_id}")
async def get_analysis_task(task_id: str):
    """获取分析任务详情"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)
    return _serialize_task(task)


@app.post("/api/video-analysis/tasks/{task_id}/start")
async def start_analysis_task(task_id: str):
    """启动分析任务"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    if task["status"] not in ("waiting_config", "failed"):
        return JSONResponse(
            {"error": f"Task is in '{task['status']}' state, cannot start"},
            status_code=400,
        )

    # 启动后台分析线程
    thread = threading.Thread(target=_run_video_analysis, args=(task_id,), daemon=True)
    thread.start()

    return {"message": "Analysis started", "task_id": task_id}


@app.delete("/api/video-analysis/tasks/{task_id}")
async def delete_analysis_task(task_id: str):
    """删除分析任务及相关文件"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    # 删除上传的视频文件
    upload_path = UPLOADS_DIR / task["filename"]
    if upload_path.exists():
        upload_path.unlink()

    # 删除标注视频文件
    if task.get("output_video"):
        output_path = OUTPUTS_DIR / task["output_video"]
        if output_path.exists():
            output_path.unlink()

    _task_repo.delete(task_id)
    return {"message": f"Task '{task_id}' deleted"}


@app.get("/api/video-analysis/tasks/{task_id}/first_frame")
async def get_task_first_frame(task_id: str):
    """获取视频首帧图片"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    filepath = str(UPLOADS_DIR / task["filename"])
    cap = cv2.VideoCapture(filepath)
    if not cap.isOpened():
        return JSONResponse({"error": "Cannot open video file"}, status_code=500)

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return JSONResponse({"error": "Cannot read first frame"}, status_code=500)

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.get("/api/video-analysis/tasks/{task_id}/video")
async def get_task_video(task_id: str):
    """下载标注视频"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    if not task.get("output_video"):
        return JSONResponse({"error": "Annotated video not available"}, status_code=404)

    output_path = OUTPUTS_DIR / task["output_video"]
    if not output_path.exists():
        return JSONResponse({"error": "Video file not found"}, status_code=404)

    return FileResponse(
        path=str(output_path),
        media_type="video/mp4",
        filename=f"annotated_{task.get('original_filename', 'video.mp4')}",
    )


def _serialize_task(task: dict) -> dict:
    """序列化任务数据用于 API 响应"""
    return {
        "id": task["id"],
        "filename": task.get("original_filename", task["filename"]),
        "status": task["status"],
        "file_size": task["file_size"],
        "created_at": task["created_at"],
        "duration": task.get("duration"),
        "progress": task.get("progress", 0),
        "events": task.get("events", []),
        "stats": task.get("stats"),
    }


# ── MQTT 配置 API ──

class UpdateMQTTConfigRequest(BaseModel):
    host: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    topic: str = "behavior-detection/events"
    enabled: bool = False
    update_interval: int = 30


@app.get("/api/mqtt/config")
async def get_mqtt_config():
    """获取 MQTT 全局配置（密码字段返回空字符串）"""
    if not _mqtt_config_repo:
        return JSONResponse({"error": "MQTT not configured"}, status_code=503)
    config = _mqtt_config_repo.get()
    return {
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password": "",  # 不返回密码明文
        "topic": config.topic,
        "enabled": config.enabled,
        "update_interval": config.update_interval,
    }


@app.put("/api/mqtt/config")
async def update_mqtt_config(req: UpdateMQTTConfigRequest):
    """更新 MQTT 全局配置"""
    if not _mqtt_config_repo:
        return JSONResponse({"error": "MQTT not configured"}, status_code=503)

    # 如果密码为空字符串，保留原密码
    current = _mqtt_config_repo.get()
    password = req.password if req.password else current.password

    config = MQTTConfig(
        host=req.host,
        port=req.port,
        username=req.username,
        password=password,
        topic=req.topic,
        enabled=req.enabled,
        update_interval=req.update_interval,
    )
    _mqtt_config_repo.save(config)

    # 同步更新 MQTTPublisher 连接
    if _mqtt_publisher:
        _mqtt_publisher.update_config(config)

    return {
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password": "",
        "topic": config.topic,
        "enabled": config.enabled,
        "update_interval": config.update_interval,
    }


@app.get("/api/mqtt/status")
async def get_mqtt_status():
    """获取 MQTT 连接状态"""
    connected = _mqtt_publisher.is_connected() if _mqtt_publisher else False
    active_sessions = _event_session_mgr.get_active_session_count() if _event_session_mgr else 0
    return {
        "connected": connected,
        "active_sessions": active_sessions,
    }


# ── go2rtc REST API ──

@app.get("/api/go2rtc/streams")
async def go2rtc_streams():
    """返回所有已注册流的 go2rtc 播放器 URL 映射"""
    if not _go2rtc_mgr or not _go2rtc_mgr.available:
        return JSONResponse({"error": "go2rtc 未运行"}, status_code=503)
    return _go2rtc_mgr.get_all_player_urls()


@app.get("/api/go2rtc/status")
async def go2rtc_status():
    """返回 go2rtc 运行状态"""
    if not _go2rtc_mgr:
        return {"running": False, "pid": None}
    running = _go2rtc_mgr.is_running()
    pid = _go2rtc_mgr._process.pid if (_go2rtc_mgr._process and _go2rtc_mgr._process.poll() is None) else None
    return {"running": running, "pid": pid}


# ── go2rtc 反向代理 ──

@app.api_route("/go2rtc/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def go2rtc_http_proxy(path: str, request: Request):
    """HTTP 反向代理到 go2rtc（静态资源 + REST API）"""
    target_url = f"{_GO2RTC_BASE_URL}/{path}"
    async with httpx.AsyncClient() as client:
        try:
            body = await request.body()
            resp = await client.request(
                method=request.method,
                url=target_url,
                params=dict(request.query_params),
                content=body if body else None,
                headers={k: v for k, v in request.headers.items()
                         if k.lower() not in ("host", "connection")},
                timeout=10.0,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type"),
            )
        except httpx.ConnectError:
            return JSONResponse({"error": "go2rtc 未运行"}, status_code=503)


@app.websocket("/go2rtc/ws")
async def go2rtc_ws_proxy(websocket: WebSocket):
    """WebSocket 反向代理到 go2rtc /api/ws（双向中继）"""
    await websocket.accept()

    # 构建目标 URL（保留查询参数）
    query_string = str(websocket.scope.get("query_string", b""), "utf-8")
    target_url = f"{_GO2RTC_WS_URL}/api/ws"
    if query_string:
        target_url += f"?{query_string}"

    import websockets as ws_lib

    try:
        async with ws_lib.connect(target_url) as upstream:
            async def client_to_upstream():
                try:
                    while True:
                        data = await websocket.receive()
                        if "text" in data:
                            await upstream.send(data["text"])
                        elif "bytes" in data:
                            await upstream.send(data["bytes"])
                except (WebSocketDisconnect, Exception):
                    pass

            async def upstream_to_client():
                try:
                    async for message in upstream:
                        if isinstance(message, str):
                            await websocket.send_text(message)
                        else:
                            await websocket.send_bytes(message)
                except (WebSocketDisconnect, Exception):
                    pass

            # 双向中继：同时运行两个方向的转发
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except Exception as e:
        logger.warning(f"go2rtc WebSocket 代理连接失败: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Detection WebSocket 端点 ──

@app.websocket("/ws/detections/{camera_id}")
async def ws_detections(websocket: WebSocket, camera_id: str):
    """实时推送指定摄像头的检测框数据"""
    await websocket.accept()
    # 添加到该 camera_id 的客户端列表
    if camera_id not in _detection_ws_clients:
        _detection_ws_clients[camera_id] = []
    _detection_ws_clients[camera_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients = _detection_ws_clients.get(camera_id, [])
        if websocket in clients:
            clients.remove(websocket)


# ── WebSocket 事件推送 ──

@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ── 前端静态资源托管 ──
# 必须在所有 API 路由和 WebSocket 端点之后挂载，确保 API 路由优先级更高
# 使用自定义包装器过滤 WebSocket 请求，避免 StaticFiles 收到 WS 协议报错
if FRONTEND_DIR.exists():
    _frontend_static = StaticFiles(directory=str(FRONTEND_DIR), html=True)

    async def _frontend_app(scope, receive, send):
        if scope["type"] != "http":
            # WebSocket 等非 HTTP 请求直接返回 404，不传给 StaticFiles
            from starlette.responses import Response as _Resp
            response = _Resp(status_code=404)
            await response(scope, receive, send)
            return
        await _frontend_static(scope, receive, send)

    app.mount("/", _frontend_app, name="frontend")
