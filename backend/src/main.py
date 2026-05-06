"""
Main entry — database → go2rtc → analyzers → web server
"""

import atexit
import logging
import os

import uvicorn

from .analyzer import CameraAnalyzer
from .database import DatabaseManager, CameraRepository, ModelRepository, TaskRepository, MQTTConfigRepository, Go2RTCConfigRepository, migrate_from_yaml
from .event_session import EventSessionManager
from .go2rtc import Go2RTCManager
from .mqtt_publisher import MQTTPublisher
from .server import (
    app,
    register_analyzers,
    register_repositories,
    register_go2rtc,
    register_go2rtc_config,
    register_mqtt,
    push_event,
    push_detections,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    os.makedirs("data/models", exist_ok=True)

    # ── 1. Initialize database ──
    db = DatabaseManager(db_path="data/app.db")
    migrate_from_yaml(db, "configs/default.yaml")

    camera_repo = CameraRepository(db)
    model_repo = ModelRepository(db)
    task_repo = TaskRepository(db)
    mqtt_config_repo = MQTTConfigRepository(db)
    go2rtc_config_repo = Go2RTCConfigRepository(db)

    model_config = model_repo.get()
    model_cfg = model_config.model_dump()
    camera_configs = camera_repo.get_all()

    if not camera_configs:
        logger.warning("No cameras configured, starting web server only")

    # ── 2. Start go2rtc ──
    go2rtc_mgr = Go2RTCManager()

    # Write all RTSP streams to go2rtc config file before starting (go2rtc loads them on startup)
    for cam in camera_configs:
        url = cam.url
        if url and (url.startswith("rtsp://") or url.startswith("rtmp://")):
            go2rtc_mgr._update_config_file(cam.id, url)
            go2rtc_mgr._registered_streams[cam.id] = url

    go2rtc_started = go2rtc_mgr.start()

    if go2rtc_started:
        ready = go2rtc_mgr.wait_ready()
        if not ready:
            logger.error("go2rtc API not ready after startup, continuing without go2rtc")

        # Start health check
        go2rtc_mgr.start_health_check()

        # Apply webrtc candidates from database (overrides env var if set)
        go2rtc_cfg = go2rtc_config_repo.get()
        if go2rtc_cfg.webrtc_candidates:
            go2rtc_mgr.update_webrtc_candidates(go2rtc_cfg.webrtc_candidates)
            logger.info(f"Applied WebRTC candidates from database: {go2rtc_cfg.webrtc_candidates}")
    else:
        logger.warning("go2rtc not started, running without go2rtc (Analyzer direct RTSP connection)")

    # ── 3. Initialize MQTT ──
    mqtt_publisher = MQTTPublisher()
    mqtt_config = mqtt_config_repo.get()
    if mqtt_config.enabled and mqtt_config.host:
        mqtt_publisher.connect(mqtt_config)
        logger.info(f"MQTT enabled, connecting to {mqtt_config.host}:{mqtt_config.port}")
    else:
        logger.info("MQTT not enabled")

    event_session_mgr = EventSessionManager(
        mqtt_publisher=mqtt_publisher,
        mqtt_config_repo=mqtt_config_repo,
        camera_repo=camera_repo,
    )

    # ── 5. Start camera analyzers (using restream_url and on_detections) ──
    analyzers = {}
    for cam in camera_configs:
        cam_id = cam.id
        if not cam_id:
            continue

        restream_url = go2rtc_mgr.get_restream_url(cam_id) if go2rtc_mgr.available else None

        analyzer = CameraAnalyzer(
            camera_config=cam.model_dump(),
            model_config=model_cfg,
            on_event=push_event,
            on_detections=push_detections,
            restream_url=restream_url,
            event_session_mgr=event_session_mgr,
        )
        analyzers[cam_id] = analyzer
        analyzer.start()

    # ── 6. Inject into server module ──
    register_analyzers(analyzers)
    register_repositories(camera_repo, model_repo, task_repo)
    register_go2rtc(go2rtc_mgr)
    register_go2rtc_config(go2rtc_config_repo)
    register_mqtt(mqtt_config_repo, mqtt_publisher, event_session_mgr)
    logger.info(f"Started {len(analyzers)} camera analyzers")

    # ── 7. Register exit cleanup ──
    atexit.register(mqtt_publisher.disconnect)
    atexit.register(go2rtc_mgr.stop)

    # ── 8. Start FastAPI ──
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
