"""
FastAPI Web server — REST API + go2rtc reverse proxy + WebSocket event/detection push
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
from pydantic import BaseModel, ConfigDict, Field

from .config import CameraConfig, RulesConfig, DetectConfig, AppConfig, MQTTConfig, CameraMQTTPublishConfig, Go2RTCConfig
from .analyzer import CameraAnalyzer

logger = logging.getLogger(__name__)

app = FastAPI(title="Behavior Detection System", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── SPA Route Fallback Middleware ──

# Frontend static assets directory (copied by multi-stage Docker build)
FRONTEND_DIR = Path(__file__).parent.parent / "static" / "frontend"


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    """SPA route fallback: return index.html for non-API/WS/static 404 requests"""

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
        """Check if path is an API/resource path (should not fall back to index.html)"""
        api_prefixes = ("/api/", "/ws/", "/go2rtc/", "/events/")
        return any(path.startswith(p) for p in api_prefixes)


# Only register SPA fallback middleware when frontend directory exists
if FRONTEND_DIR.exists():
    app.add_middleware(SPAFallbackMiddleware)
    logger.info(f"Frontend directory found: {FRONTEND_DIR}")
else:
    logger.warning(f"Frontend directory not found: {FRONTEND_DIR}, running backend API only")

# Event screenshot directory — static file serving
import os
EVENTS_DIR = Path(__file__).parent.parent / "data" / "events"
os.makedirs(str(EVENTS_DIR), exist_ok=True)
app.mount("/events", StaticFiles(directory=str(EVENTS_DIR)), name="events")

# Video upload / annotated output directories
UPLOADS_DIR = Path(__file__).parent.parent / "data" / "uploads"
OUTPUTS_DIR = Path(__file__).parent.parent / "data" / "outputs"
os.makedirs(str(UPLOADS_DIR), exist_ok=True)
os.makedirs(str(OUTPUTS_DIR), exist_ok=True)

# Global state (injected by main.py)
_analyzers: Dict[str, Any] = {}
_model_config: dict = {}  # Model config (loaded from ModelRepository)
_camera_time_sync = None  # CameraTimeSync instance
_events: List[Dict[str, Any]] = []
_events_max = 1000
_ws_clients: List[WebSocket] = []
_event_loop = None

# Detection WebSocket clients (grouped by camera_id)
_detection_ws_clients: Dict[str, List[WebSocket]] = {}

# go2rtc manager instance (injected by main.py via register_go2rtc)
_go2rtc_mgr = None

# go2rtc reverse proxy target address
_GO2RTC_BASE_URL = "http://127.0.0.1:1984"
_GO2RTC_WS_URL = "ws://127.0.0.1:1984"

# Database Repository instances (injected by main.py via register_repositories)
_camera_repo = None
_model_repo = None
_task_repo = None
_event_repo = None

# MQTT component instances (injected by main.py via register_mqtt)
_mqtt_config_repo = None
_mqtt_publisher = None
_event_session_mgr = None

# go2rtc config repository (injected by main.py via register_go2rtc_config)
_go2rtc_config_repo = None


@app.on_event("startup")
async def _on_startup():
    global _event_loop
    _event_loop = asyncio.get_running_loop()


def register_analyzers(analyzers: dict):
    global _analyzers
    _analyzers = analyzers


def register_camera_time_sync(sync):
    """Inject CameraTimeSync instance (called by main.py)"""
    global _camera_time_sync
    _camera_time_sync = sync


def register_repositories(camera_repo, model_repo, task_repo, event_repo=None):
    """Inject database Repository instances and model config (called by main.py)"""
    global _camera_repo, _model_repo, _task_repo, _model_config, _event_repo
    _camera_repo = camera_repo
    _model_repo = model_repo
    _task_repo = task_repo
    _event_repo = event_repo
    # Load model config from ModelRepository into memory dict (for _run_video_analysis)
    _model_config = model_repo.get().model_dump()


def push_event(event: dict):
    """Receive event, store in memory + database, and broadcast to WebSocket"""
    _events.append(event)
    if len(_events) > _events_max:
        _events.pop(0)
    # Persist to database
    if _event_repo:
        try:
            _event_repo.save(event)
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")
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
    """Inject Go2RTCManager instance (called by main.py)"""
    global _go2rtc_mgr
    _go2rtc_mgr = mgr


def register_mqtt(mqtt_config_repo, mqtt_publisher, event_session_mgr):
    """Inject MQTT component instances (called by main.py)"""
    global _mqtt_config_repo, _mqtt_publisher, _event_session_mgr
    _mqtt_config_repo = mqtt_config_repo
    _mqtt_publisher = mqtt_publisher
    _event_session_mgr = event_session_mgr


def register_go2rtc_config(go2rtc_config_repo):
    """Inject Go2RTCConfigRepository instance (called by main.py)"""
    global _go2rtc_config_repo
    _go2rtc_config_repo = go2rtc_config_repo


def push_detections(camera_id: str, timestamp: float, detections: list):
    """Push detection data to all WebSocket clients subscribed to this camera_id"""
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
            # Send failed, remove this client
            if ws in clients:
                clients.remove(ws)


# ── Authentication ──

from .auth import hash_password, verify_password, create_token, decode_token

_user_repo = None


def register_user_repo(user_repo):
    """Inject UserRepository instance (called by main.py)"""
    global _user_repo
    _user_repo = user_repo


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Login and return JWT token"""
    if not _user_repo:
        return JSONResponse({"error": "Auth not configured"}, status_code=503)

    user = _user_repo.get_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        return JSONResponse({"error": "Invalid username or password"}, status_code=401)

    token = create_token(user["username"])
    return {"token": token, "username": user["username"]}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """Get current user info (requires valid token)"""
    username = _get_current_user(request)
    if not username:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return {"username": username}


@app.put("/api/auth/password")
async def auth_change_password(req: ChangePasswordRequest, request: Request):
    """Change current user's password"""
    username = _get_current_user(request)
    if not username:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if not _user_repo:
        return JSONResponse({"error": "Auth not configured"}, status_code=503)

    user = _user_repo.get_by_username(username)
    if not user or not verify_password(req.old_password, user["password_hash"]):
        return JSONResponse({"error": "Current password is incorrect"}, status_code=400)

    _user_repo.update_password(username, hash_password(req.new_password))
    return {"message": "Password updated"}


def _get_current_user(request: Request) -> Optional[str]:
    """Extract and validate JWT token from request Authorization header"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return decode_token(token)


# ── Auth Middleware ──

# Paths that do NOT require authentication
_PUBLIC_PATH_PREFIXES = (
    "/api/auth/login",
    "/events/",        # Event screenshots — public access
    "/go2rtc/",        # go2rtc proxy (used by video player)
)

# Path suffixes that do NOT require authentication (media resources loaded by <img>/<video>)
_PUBLIC_PATH_SUFFIXES = (
    "/snapshot",
    "/first_frame",
    "/video",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware — protects /api/* routes, allows public paths"""

    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip non-API paths (frontend static files, etc.)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip public path prefixes
        for prefix in _PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip media resource paths (snapshot, video, first_frame)
        for suffix in _PUBLIC_PATH_SUFFIXES:
            if path.endswith(suffix) or (suffix + "?") in path:
                return await call_next(request)

        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Validate token
        username = _get_current_user(request)
        if not username:
            return JSONResponse(
                {"error": "Unauthorized", "detail": "Missing or invalid token"},
                status_code=401,
            )

        return await call_next(request)


app.add_middleware(AuthMiddleware)


# ── REST API ──

# ── Request Models ──

class CreateCameraRequest(BaseModel):
    id: str
    name: str
    url: str


class UpdateCameraRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    detect: Optional[DetectConfig] = None
    roi: Optional[list] = None
    rules: Optional[RulesConfig] = None
    mqtt_publish: Optional[CameraMQTTPublishConfig] = None
    timezone: Optional[str] = None


@app.get("/api/cameras")
async def list_cameras():
    cameras = []
    # Load all camera configs from database
    db_configs = {cfg.id: cfg for cfg in _camera_repo.get_all()} if _camera_repo else {}

    for cid, analyzer in _analyzers.items():
        cfg = db_configs.get(cid)
        online = analyzer.get_frame() is not None if analyzer else False
        enabled = cfg.enabled if cfg else True
        camera_info: Dict[str, Any] = {
            "id": cid,
            "name": cfg.name if cfg else (analyzer.camera_name if analyzer else cid),
            "url": cfg.url if cfg else (analyzer.url if analyzer else ""),
            "enabled": enabled,
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

    # Also include disabled cameras that have no analyzer running
    for cid, cfg in db_configs.items():
        if cid not in _analyzers:
            cameras.append({
                "id": cid,
                "name": cfg.name,
                "url": cfg.url,
                "enabled": cfg.enabled,
                "online": False,
                "detect": cfg.detect.model_dump(),
                "roi": cfg.roi,
                "rules": cfg.rules.model_dump(),
                "mqtt_publish": cfg.mqtt_publish.model_dump(),
            })

    return cameras


@app.post("/api/cameras")
async def create_camera(req: CreateCameraRequest):
    if req.id in _analyzers:
        return JSONResponse({"error": f"Camera '{req.id}' already exists"}, status_code=409)

    # Create config
    cam_cfg = CameraConfig(id=req.id, name=req.name, url=req.url)

    # Persist to database
    _camera_repo.create(cam_cfg)

    # Register stream to go2rtc
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.add_stream(req.id, req.url)

    # Register to camera time sync
    if _camera_time_sync:
        _camera_time_sync.register_camera(req.id, req.url, camera_timezone=None)

    # Start analyzer
    cam_dict = cam_cfg.model_dump()
    restream_url = _go2rtc_mgr.get_restream_url(req.id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

    analyzer = CameraAnalyzer(
        camera_config=cam_dict,
        model_config=_model_config,
        on_event=push_event,
        on_detections=push_detections,
        restream_url=restream_url,
        event_session_mgr=_event_session_mgr,
        camera_time_sync=_camera_time_sync,
    )
    _analyzers[req.id] = analyzer
    analyzer.start()

    return {
        "id": req.id,
        "name": req.name,
        "url": req.url,
        "enabled": True,
        "online": False,
        "detect": cam_cfg.detect.model_dump(),
        "roi": cam_cfg.roi,
        "rules": cam_cfg.rules.model_dump(),
        "mqtt_publish": cam_cfg.mqtt_publish.model_dump(),
    }


@app.put("/api/cameras/{camera_id}")
async def update_camera(camera_id: str, req: UpdateCameraRequest):
    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    if not cfg:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    # Update config fields
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
    if req.timezone is not None:
        cfg.timezone = req.timezone if req.timezone != "" else None

    # Persist to database
    _camera_repo.update(cfg)

    # Update time sync timezone
    if _camera_time_sync and req.timezone is not None:
        tz_value = req.timezone if req.timezone != "" else None
        _camera_time_sync.update_timezone(camera_id, tz_value)

    # Update go2rtc stream (when URL changes)
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.add_stream(camera_id, cfg.url)

    # Stop old analyzer, start new analyzer (with updated config)
    old_analyzer = _analyzers.get(camera_id)
    if old_analyzer:
        old_analyzer.stop()

    # Only restart analyzer if camera is enabled
    if cfg.enabled:
        cam_dict = cfg.model_dump()
        restream_url = _go2rtc_mgr.get_restream_url(camera_id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

        new_analyzer = CameraAnalyzer(
            camera_config=cam_dict,
            model_config=_model_config,
            on_event=push_event,
            on_detections=push_detections,
            restream_url=restream_url,
            event_session_mgr=_event_session_mgr,
            camera_time_sync=_camera_time_sync,
        )
        _analyzers[camera_id] = new_analyzer
        new_analyzer.start()
    else:
        # Camera is disabled — remove from analyzers dict
        _analyzers.pop(camera_id, None)

    return {
        "id": camera_id,
        "name": cfg.name,
        "url": cfg.url,
        "enabled": cfg.enabled,
        "online": False,
        "detect": cfg.detect.model_dump(),
        "roi": cfg.roi,
        "rules": cfg.rules.model_dump(),
        "mqtt_publish": cfg.mqtt_publish.model_dump(),
        "timezone": cfg.timezone,
    }


@app.delete("/api/cameras/{camera_id}")
async def delete_camera(camera_id: str):
    if camera_id not in _analyzers:
        # Check if it exists in database (could be a disabled camera)
        cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
        if not cfg:
            return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    # Stop analyzer if running
    analyzer = _analyzers.pop(camera_id, None)
    if analyzer:
        analyzer.stop()

    # Remove stream from go2rtc
    if _go2rtc_mgr and _go2rtc_mgr.available:
        _go2rtc_mgr.remove_stream(camera_id)

    # Delete config from database
    _camera_repo.delete(camera_id)

    return {"message": f"Camera '{camera_id}' deleted"}


# ── Save Rule Config by Camera + Algorithm ──

class SaveRuleConfigRequest(BaseModel):
    """Save specific rule configuration for a camera by algorithm type"""
    enabled: Optional[bool] = None
    schedule: Optional[dict] = None
    zones: Optional[list] = None
    # Allow any additional rule-specific parameters
    model_config = ConfigDict(extra="allow")


@app.put("/api/cameras/{camera_id}/rules/{rule_type}")
async def save_rule_config(camera_id: str, rule_type: str, request: Request):
    """
    Save configuration for a specific algorithm rule on a specific camera.
    
    Supported rule_type: crowd, fight, fall, loiter
    Only the provided fields will be updated; unspecified fields keep their current values.
    After saving, the analyzer is restarted to apply the new configuration.
    """
    # Validate rule_type
    valid_rule_types = ("crowd", "fight", "fall", "loiter")
    if rule_type not in valid_rule_types:
        return JSONResponse(
            {"error": f"Invalid rule_type '{rule_type}'. Must be one of: {', '.join(valid_rule_types)}"},
            status_code=400,
        )

    # Get camera config from database
    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    if not cfg:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    # Parse request body
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if not isinstance(body, dict):
        return JSONResponse({"error": "Request body must be a JSON object"}, status_code=400)

    # Get current rule config
    current_rule = getattr(cfg.rules, rule_type)
    current_dict = current_rule.model_dump()

    # Merge: only update provided fields
    for key, value in body.items():
        if key in current_dict:
            current_dict[key] = value
        else:
            return JSONResponse(
                {"error": f"Unknown parameter '{key}' for rule type '{rule_type}'"},
                status_code=422,
            )

    # Validate and rebuild the rule config object
    try:
        from .config import CrowdConfig, FightConfig, FallConfig, LoiterConfig
        rule_classes = {
            "crowd": CrowdConfig,
            "fight": FightConfig,
            "fall": FallConfig,
            "loiter": LoiterConfig,
        }
        new_rule = rule_classes[rule_type](**current_dict)
    except Exception as e:
        return JSONResponse(
            {"error": f"Parameter validation failed: {str(e)}"},
            status_code=422,
        )

    # Apply to camera config
    setattr(cfg.rules, rule_type, new_rule)

    # Persist to database
    _camera_repo.update(cfg)

    # Restart analyzer to apply new config
    old_analyzer = _analyzers.get(camera_id)
    if old_analyzer:
        old_analyzer.stop()

    if cfg.enabled:
        cam_dict = cfg.model_dump()
        restream_url = _go2rtc_mgr.get_restream_url(camera_id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

        new_analyzer = CameraAnalyzer(
            camera_config=cam_dict,
            model_config=_model_config,
            on_event=push_event,
            on_detections=push_detections,
            restream_url=restream_url,
            event_session_mgr=_event_session_mgr,
            camera_time_sync=_camera_time_sync,
        )
        _analyzers[camera_id] = new_analyzer
        new_analyzer.start()
    else:
        _analyzers.pop(camera_id, None)

    return {
        "message": f"Rule '{rule_type}' updated for camera '{camera_id}'",
        "camera_id": camera_id,
        "rule_type": rule_type,
        "config": new_rule.model_dump(),
    }


# ── Toggle Rule Enabled/Disabled ──

class ToggleRuleRequest(BaseModel):
    enabled: bool


@app.put("/api/cameras/{camera_id}/rules/{rule_type}/toggle")
async def toggle_rule(camera_id: str, rule_type: str, req: ToggleRuleRequest):
    """
    Toggle a specific detection rule on/off for a camera.
    
    Supported rule_type: crowd, fight, fall, loiter
    Only changes the 'enabled' field, all other parameters remain unchanged.
    After toggling, the analyzer is restarted to apply the change.
    """
    valid_rule_types = ("crowd", "fight", "fall", "loiter")
    if rule_type not in valid_rule_types:
        return JSONResponse(
            {"error": f"Invalid rule_type '{rule_type}'. Must be one of: {', '.join(valid_rule_types)}"},
            status_code=400,
        )

    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    if not cfg:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    # Update the enabled field for the specific rule
    rule = getattr(cfg.rules, rule_type)
    rule.enabled = req.enabled

    # Persist to database
    _camera_repo.update(cfg)

    # Restart analyzer to apply change
    old_analyzer = _analyzers.get(camera_id)
    if old_analyzer:
        old_analyzer.stop()

    if cfg.enabled:
        cam_dict = cfg.model_dump()
        restream_url = _go2rtc_mgr.get_restream_url(camera_id) if (_go2rtc_mgr and _go2rtc_mgr.available) else None

        new_analyzer = CameraAnalyzer(
            camera_config=cam_dict,
            model_config=_model_config,
            on_event=push_event,
            on_detections=push_detections,
            restream_url=restream_url,
            event_session_mgr=_event_session_mgr,
            camera_time_sync=_camera_time_sync,
        )
        _analyzers[camera_id] = new_analyzer
        new_analyzer.start()
    else:
        _analyzers.pop(camera_id, None)

    return {
        "message": f"Rule '{rule_type}' {'enabled' if req.enabled else 'disabled'} for camera '{camera_id}'",
        "camera_id": camera_id,
        "rule_type": rule_type,
        "enabled": req.enabled,
    }


class ToggleCameraRequest(BaseModel):
    enabled: bool


@app.post("/api/cameras/{camera_id}/toggle")
async def toggle_camera(camera_id: str, req: ToggleCameraRequest):
    """Toggle camera detection on/off"""
    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    if not cfg:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    cfg.enabled = req.enabled
    _camera_repo.update(cfg)

    if req.enabled:
        # Start detection: create and start analyzer
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
            camera_time_sync=_camera_time_sync,
        )
        _analyzers[camera_id] = new_analyzer
        new_analyzer.start()
        logger.info(f"[{camera_id}] Detection enabled")
    else:
        # Stop detection: stop and remove analyzer
        analyzer = _analyzers.pop(camera_id, None)
        if analyzer:
            analyzer.stop()
        logger.info(f"[{camera_id}] Detection disabled")

    return {
        "id": camera_id,
        "enabled": req.enabled,
        "message": f"Detection {'enabled' if req.enabled else 'disabled'} for camera '{camera_id}'",
    }


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
    sub_type: str = Query(None, description="Filter event sub_type: crowd/fight/fall"),
    camera_id: str = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    # Read from database (persisted across restarts)
    if _event_repo:
        return _event_repo.query(sub_type=sub_type, camera_id=camera_id, limit=limit)
    # Fallback to in-memory (if event_repo not available)
    filtered = _events
    if sub_type:
        filtered = [e for e in filtered if e.get("sub_type") == sub_type]
    if camera_id:
        filtered = [e for e in filtered if e.get("camera_id") == camera_id]
    result = filtered[-limit:]
    result = sorted(result, key=lambda e: e.get("timestamp", 0), reverse=True)
    return result


@app.get("/api/status")
async def system_status():
    total_events = _event_repo.count() if _event_repo else len(_events)
    return {
        "cameras": len(_analyzers),
        "total_events": total_events,
        "uptime": time.time(),
    }


@app.get("/api/time-sync")
async def time_sync_status():
    """Return time synchronization status for all cameras"""
    if not _camera_time_sync:
        return {"enabled": False, "cameras": []}

    return {"enabled": True, "cameras": _camera_time_sync.get_all_status()}


# ── Model Configuration API ──

class UpdateModelConfigRequest(BaseModel):
    detector_path: Optional[str] = None
    confidence: Optional[float] = None
    pose_path: Optional[str] = None
    pose_confidence: Optional[float] = None
    tracker_config: Optional[str] = None


@app.get("/api/model/config")
async def get_model_config():
    """Get current model configuration"""
    if not _model_repo:
        return JSONResponse({"error": "Model repository not available"}, status_code=500)
    config = _model_repo.get()
    return config.model_dump()


@app.put("/api/model/config")
async def update_model_config(req: UpdateModelConfigRequest):
    """Update model configuration (requires restart to take effect)"""
    if not _model_repo:
        return JSONResponse({"error": "Model repository not available"}, status_code=500)

    config = _model_repo.get()
    if req.detector_path is not None:
        config.detector_path = req.detector_path
    if req.confidence is not None:
        config.confidence = req.confidence
    if req.pose_path is not None:
        config.pose_path = req.pose_path
    if req.pose_confidence is not None:
        config.pose_confidence = req.pose_confidence
    if req.tracker_config is not None:
        config.tracker_config = req.tracker_config

    _model_repo.save(config)
    return config.model_dump()


class ManualEventRequest(BaseModel):
    sub_type: str = Field("crowd", description="Event type: crowd/fight/fall")
    detail: str = Field("", description="Custom detail message (optional)")


@app.post("/api/cameras/{camera_id}/trigger")
async def trigger_manual_event(camera_id: str, req: ManualEventRequest):
    """Manually trigger a test event for a camera — takes snapshot, pushes to MQTT, and adds to event list"""
    analyzer = _analyzers.get(camera_id)
    if not analyzer:
        return JSONResponse({"error": f"Camera '{camera_id}' not found"}, status_code=404)

    frame = analyzer.get_frame()
    if frame is None:
        return JSONResponse({"error": "No frame available (camera offline?)"}, status_code=503)

    # Validate sub_type
    if req.sub_type not in ("crowd", "fight", "fall"):
        return JSONResponse({"error": "sub_type must be one of: crowd, fight, fall"}, status_code=400)

    now = time.time()

    # Save screenshot
    ts_str = time.strftime("%Y%m%d_%H%M%S")
    ms = int((now % 1) * 1000)
    filename = f"{camera_id}_{req.sub_type}_manual_{ts_str}_{ms:03d}.jpg"
    filepath = os.path.join(str(EVENTS_DIR), filename)
    cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # Build event
    cfg = _camera_repo.get_by_id(camera_id) if _camera_repo else None
    camera_name = cfg.name if cfg else camera_id
    detail = req.detail or f"Manual test event ({req.sub_type}) triggered for debugging"

    event = {
        "type": "anomaly",
        "sub_type": req.sub_type,
        "camera_id": camera_id,
        "camera_name": camera_name,
        "timestamp": now,
        "detail": detail,
        "track_ids": [],
        "bbox": [],
        "image": filename,
        "manual": True,
    }

    # Push to event list + WebSocket broadcast
    push_event(event)

    # Push to MQTT (bypass event session lifecycle — send immediately as triggered+resolved)
    if _mqtt_publisher and _mqtt_publisher.is_connected() and _event_session_mgr:
        mqtt_config = None
        if _mqtt_config_repo:
            mqtt_config = _mqtt_config_repo.get()
        if mqtt_config and mqtt_config.enabled and mqtt_config.topic:
            # Format timestamp in camera timezone
            if _camera_time_sync:
                timestamp_str = _camera_time_sync.format_timestamp(camera_id, now)
            else:
                timestamp_str = datetime.fromtimestamp(now).astimezone().isoformat()

            mqtt_message = {
                "event_id": f"evt_{camera_id}_{req.sub_type}_manual_{ts_str}_{ms:03d}",
                "status": "triggered",
                "type": req.sub_type,
                "camera_id": camera_id,
                "camera_name": camera_name,
                "timestamp": timestamp_str,
                "detail": detail,
                "data": {"manual": True},
                "image_url": f"/events/{filename}" if filename else "",
                "duration": 0.0,
            }
            _mqtt_publisher.publish(mqtt_config.topic, mqtt_message)

    return {
        "message": "Event triggered successfully",
        "event": event,
    }


# ── Video Analysis API ──

def _get_video_duration(filepath: str) -> float:
    """Get video duration (seconds)"""
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
    """Convert mp4v encoding to H.264 using ffmpeg (browser compatible)"""
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
            logger.info(f"[VideoAnalysis] H.264 transcoding complete: {filepath}")
        else:
            logger.warning("[VideoAnalysis] ffmpeg transcoding output is empty, keeping original mp4v encoding")
    except FileNotFoundError:
        logger.warning("[VideoAnalysis] ffmpeg not installed, browser may not be able to play video")
    except Exception as e:
        logger.warning(f"[VideoAnalysis] ffmpeg transcoding failed: {e}, keeping original mp4v encoding")


def _run_video_analysis(task_id: str):
    """Run video analysis in background thread"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return

    _task_repo.update_status(task_id, "processing", 0)

    input_path = str(UPLOADS_DIR / task["filename"])
    output_path = str(OUTPUTS_DIR / f"{task_id}_annotated.mp4")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        _task_repo.update_status(task_id, "failed", 0)
        logger.error(f"[VideoAnalysis] Unable to open video: {input_path}")
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
            confidence=mc.get("confidence", 0.3),
            tracker_config=mc.get("tracker_config", "bytetrack.yaml"),
        )

        # Use ROI and default rules config saved in task
        roi = task.get("roi") or []
        rules_cfg = task.get("rules") or {
            "crowd": {"enabled": True, "max_count": 3, "radius": 300,
                      "confirm_frames": 3, "cooldown": 10},
            "fight": {"enabled": True, "proximity_radius": 300, "min_speed": 15,
                      "min_persons": 2, "confirm_frames": 1, "cooldown": 5},
            "fall": {"enabled": True, "ratio_threshold": 0.6, "min_ratio_change": 0.15,
                     "min_y_drop": 5, "confirm_frames": 1, "cooldown": 5},
        }
        engine = BehaviorEngine(rules_cfg, roi=roi if roi else None)
        logger.info(f"[VideoAnalysis] Task {task_id} rules config: {rules_cfg}")
        logger.info(f"[VideoAnalysis] Engine loaded {len(engine.rules)} rules")

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

            # Statistics
            person_count = len([d for d in detections if d.track_id >= 0])
            person_counts.append(person_count)
            stats["total_detections"] += person_count
            if person_count > stats["max_persons"]:
                stats["max_persons"] = person_count
            for d in detections:
                if d.confidence > stats["max_confidence"]:
                    stats["max_confidence"] = d.confidence

            # Behavior detection
            events = engine.update(detections, camera_id=f"video_{task_id}", frame_ts=frame_ts)
            for evt in events:
                evt["timestamp"] = frame_ts
                evt["frame_index"] = frame_idx
                all_events.append(evt)
                logger.info(f"[VideoAnalysis] Event: {evt.get('sub_type')} @ frame {frame_idx}")

            # Log stats every 100 frames
            if frame_idx % 100 == 0:
                logger.info(f"[VideoAnalysis] frame={frame_idx}/{total_frames}, persons={person_count}, events_so_far={len(all_events)}")

            # Draw annotated frame
            annotated = frame.copy()
            for det in detections:
                if det.track_id < 0:
                    continue
                x1, y1, x2, y2 = [int(v) for v in det.bbox]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 1)
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
                    cv2.rectangle(annotated, (ex1, ey1), (ex2, ey2), color, 1)
                    cv2.putText(annotated, sub.upper(), (ex1, max(ey1 - 10, 16)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1)

            writer.write(annotated)
            frame_idx += 1

            # Periodically update progress to database (every 30 frames)
            if total_frames > 0 and frame_idx % 30 == 0:
                progress = int((frame_idx / total_frames) * 100)
                _task_repo.update_status(task_id, "processing", progress)

        # Complete statistics
        stats["duration"] = frame_idx / fps if fps > 0 else 0.0
        stats["avg_persons"] = (
            sum(person_counts) / len(person_counts) if person_counts else 0.0
        )
        stats["total_frames"] = frame_idx

        # Save results to database
        output_video = f"{task_id}_annotated.mp4"
        _task_repo.update_result(task_id, all_events, stats, output_video)
        _task_repo.update_status(task_id, "completed", 100)
        logger.info(f"[VideoAnalysis] Task {task_id} completed, {len(all_events)} events")

    except Exception as e:
        _task_repo.update_status(task_id, "failed", 0)
        logger.error(f"[VideoAnalysis] Task {task_id} failed: {e}")
    finally:
        cap.release()
        writer.release()

        # Convert to H.264 for browser playback
        _convert_to_h264(output_path)


@app.post("/api/video-analysis/upload")
async def upload_video(file: UploadFile = File(...)):
    """Upload video file, create analysis task"""
    task_id = str(uuid.uuid4())
    filename = f"{task_id}_{file.filename}"
    filepath = UPLOADS_DIR / filename

    # Save uploaded file
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    file_size = len(content)

    # Get video duration
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
    """Get all analysis task list"""
    tasks = _task_repo.get_all() if _task_repo else []
    return [_serialize_task(t) for t in tasks]


@app.get("/api/video-analysis/tasks/{task_id}")
async def get_analysis_task(task_id: str):
    """Get analysis task details"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)
    return _serialize_task(task)


class StartAnalysisRequest(BaseModel):
    rules: Optional[Dict[str, Any]] = None


@app.post("/api/video-analysis/tasks/{task_id}/start")
async def start_analysis_task(task_id: str, body: Optional[StartAnalysisRequest] = None):
    """Start analysis task, optionally with custom rules config"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    if task["status"] not in ("waiting_config", "failed"):
        return JSONResponse(
            {"error": f"Task is in '{task['status']}' state, cannot start"},
            status_code=400,
        )

    # Save rules config to task if provided
    if body and body.rules and _task_repo:
        _task_repo.update_config(task_id, rules=body.rules)

    # Start background analysis thread
    thread = threading.Thread(target=_run_video_analysis, args=(task_id,), daemon=True)
    thread.start()

    return {"message": "Analysis started", "task_id": task_id}


@app.delete("/api/video-analysis/tasks/{task_id}")
async def delete_analysis_task(task_id: str):
    """Delete analysis task and related files"""
    task = _task_repo.get_by_id(task_id) if _task_repo else None
    if not task:
        return JSONResponse({"error": f"Task '{task_id}' not found"}, status_code=404)

    # Delete uploaded video file
    upload_path = UPLOADS_DIR / task["filename"]
    if upload_path.exists():
        upload_path.unlink()

    # Delete annotated video file
    if task.get("output_video"):
        output_path = OUTPUTS_DIR / task["output_video"]
        if output_path.exists():
            output_path.unlink()

    _task_repo.delete(task_id)
    return {"message": f"Task '{task_id}' deleted"}


@app.get("/api/video-analysis/tasks/{task_id}/first_frame")
async def get_task_first_frame(task_id: str):
    """Get video first frame image"""
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
    """Download annotated video"""
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
    """Serialize task data for API response"""
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


# ── MQTT Configuration API ──

class UpdateMQTTConfigRequest(BaseModel):
    host: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    topic: str = "behavior-detection/events"
    enabled: bool = False
    update_interval: int = 30
    tls_enabled: bool = False
    tls_insecure: bool = False


@app.get("/api/mqtt/config")
async def get_mqtt_config():
    """Get MQTT global configuration (password field returns empty string)"""
    if not _mqtt_config_repo:
        return JSONResponse({"error": "MQTT not configured"}, status_code=503)
    config = _mqtt_config_repo.get()
    return {
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password": "",  # Don't return password in plaintext
        "topic": config.topic,
        "enabled": config.enabled,
        "update_interval": config.update_interval,
        "tls_enabled": config.tls_enabled,
        "tls_insecure": config.tls_insecure,
    }


@app.put("/api/mqtt/config")
async def update_mqtt_config(req: UpdateMQTTConfigRequest):
    """Update MQTT global configuration"""
    if not _mqtt_config_repo:
        return JSONResponse({"error": "MQTT not configured"}, status_code=503)

    # If password is empty string, keep original password
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
        tls_enabled=req.tls_enabled,
        tls_insecure=req.tls_insecure,
    )
    _mqtt_config_repo.save(config)

    # Sync update MQTTPublisher connection
    if _mqtt_publisher:
        _mqtt_publisher.update_config(config)

        # Wait briefly for async connection to establish (up to 2 seconds)
        if config.enabled and config.host:
            import asyncio
            for _ in range(20):
                if _mqtt_publisher.is_connected():
                    break
                await asyncio.sleep(0.1)

    # Invalidate cached MQTT config in event session manager
    if _event_session_mgr:
        _event_session_mgr.invalidate_mqtt_config_cache()

    return {
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password": "",
        "topic": config.topic,
        "enabled": config.enabled,
        "update_interval": config.update_interval,
        "tls_enabled": config.tls_enabled,
        "tls_insecure": config.tls_insecure,
    }


@app.get("/api/mqtt/status")
async def get_mqtt_status():
    """Get MQTT connection status"""
    connected = _mqtt_publisher.is_connected() if _mqtt_publisher else False
    active_sessions = _event_session_mgr.get_active_session_count() if _event_session_mgr else 0
    return {
        "connected": connected,
        "active_sessions": active_sessions,
    }


# ── go2rtc Configuration API ──

class UpdateGo2RTCConfigRequest(BaseModel):
    webrtc_candidates: str = ""


@app.get("/api/go2rtc/config")
async def get_go2rtc_config():
    """Get go2rtc configuration"""
    if not _go2rtc_config_repo:
        return JSONResponse({"error": "go2rtc config not configured"}, status_code=503)
    config = _go2rtc_config_repo.get()
    return {
        "webrtc_candidates": config.webrtc_candidates,
    }


@app.put("/api/go2rtc/config")
async def update_go2rtc_config(req: UpdateGo2RTCConfigRequest):
    """Update go2rtc configuration and rewrite go2rtc.yaml"""
    if not _go2rtc_config_repo:
        return JSONResponse({"error": "go2rtc config not configured"}, status_code=503)

    config = Go2RTCConfig(
        webrtc_candidates=req.webrtc_candidates,
    )
    _go2rtc_config_repo.save(config)

    # Update go2rtc.yaml webrtc candidates section
    if _go2rtc_mgr:
        _go2rtc_mgr.update_webrtc_candidates(req.webrtc_candidates)

    return {
        "webrtc_candidates": config.webrtc_candidates,
    }


# ── go2rtc REST API ──

@app.get("/api/go2rtc/streams")
async def go2rtc_streams():
    """Return go2rtc player URL mapping for all registered streams"""
    if not _go2rtc_mgr or not _go2rtc_mgr.available:
        return JSONResponse({"error": "go2rtc not running"}, status_code=503)
    return _go2rtc_mgr.get_all_player_urls()


@app.get("/api/go2rtc/status")
async def go2rtc_status():
    """Return go2rtc running status"""
    if not _go2rtc_mgr:
        return {"running": False, "pid": None}
    running = _go2rtc_mgr.is_running()
    pid = _go2rtc_mgr._process.pid if (_go2rtc_mgr._process and _go2rtc_mgr._process.poll() is None) else None
    return {"running": running, "pid": pid}


# ── go2rtc Reverse Proxy ──

# go2rtc's video-rtc.js imports video-stream.js with a relative path.
# When loaded from /go2rtc/video-rtc.js, the browser resolves it as /video-stream.js (root).
# This route proxies root-level go2rtc JS files to the internal go2rtc server.
@app.api_route("/video-stream.js", methods=["GET"])
@app.api_route("/video-rtc.js", methods=["GET"])
async def go2rtc_root_js(request: Request):
    """Proxy go2rtc JS files requested at root level (relative import resolution)"""
    path = request.url.path.lstrip("/")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{_GO2RTC_BASE_URL}/{path}", timeout=10.0)
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/javascript"),
            )
        except httpx.ConnectError:
            return JSONResponse({"error": "go2rtc not running"}, status_code=503)


@app.websocket("/go2rtc/api/ws")
async def go2rtc_ws_proxy(websocket: WebSocket):
    """WebSocket reverse proxy to go2rtc /api/ws (bidirectional relay)
    
    Uses aiohttp instead of websockets library to avoid the legacy protocol
    keepalive ping AssertionError that occurs under high-throughput video streams.
    """
    await websocket.accept()

    # Build target URL (preserve query parameters)
    query_string = str(websocket.scope.get("query_string", b""), "utf-8")
    target_url = f"{_GO2RTC_WS_URL}/api/ws"
    if query_string:
        target_url += f"?{query_string}"

    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                target_url,
                heartbeat=None,  # Disable heartbeat to avoid ping/pong issues
                max_msg_size=0,  # No message size limit for video streams
            ) as upstream:
                async def client_to_upstream():
                    try:
                        while True:
                            data = await websocket.receive()
                            if "text" in data:
                                await upstream.send_str(data["text"])
                            elif "bytes" in data:
                                await upstream.send_bytes(data["bytes"])
                    except (WebSocketDisconnect, Exception):
                        pass

                async def upstream_to_client():
                    try:
                        async for msg in upstream:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await websocket.send_text(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await websocket.send_bytes(msg.data)
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                    except (WebSocketDisconnect, Exception):
                        pass

                # Bidirectional relay: run both directions simultaneously
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
        logger.warning(f"go2rtc WebSocket proxy connection failed: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.api_route("/go2rtc/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def go2rtc_http_proxy(path: str, request: Request):
    """HTTP reverse proxy to go2rtc (static assets + REST API)"""
    from starlette.requests import ClientDisconnect
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
            return JSONResponse({"error": "go2rtc not running"}, status_code=503)
        except ClientDisconnect:
            return Response(status_code=499)


# ── Detection WebSocket Endpoint ──

@app.websocket("/ws/detections/{camera_id}")
async def ws_detections(websocket: WebSocket, camera_id: str):
    """Push detection box data for specified camera in real-time"""
    await websocket.accept()
    # Add to client list for this camera_id
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


# ── WebSocket Event Push ──

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


# ── Frontend Static Asset Hosting ──
# Must be mounted after all API routes and WebSocket endpoints to ensure API route priority
# Uses custom wrapper to filter WebSocket requests, preventing StaticFiles from receiving WS protocol errors
if FRONTEND_DIR.exists():
    _frontend_static = StaticFiles(directory=str(FRONTEND_DIR), html=True)

    async def _frontend_app(scope, receive, send):
        if scope["type"] != "http":
            # Non-HTTP requests (WebSocket etc.) return 404 directly, not passed to StaticFiles
            from starlette.responses import Response as _Resp
            response = _Resp(status_code=404)
            await response(scope, receive, send)
            return
        await _frontend_static(scope, receive, send)

    app.mount("/", _frontend_app, name="frontend")
