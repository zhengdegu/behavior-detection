"""
主入口 — 数据库 → go2rtc → 分析器 → Web 服务
"""

import atexit
import logging
import os

import uvicorn

from .analyzer import CameraAnalyzer
from .database import DatabaseManager, CameraRepository, ModelRepository, TaskRepository, MQTTConfigRepository, migrate_from_yaml
from .event_session import EventSessionManager
from .go2rtc import Go2RTCManager
from .mqtt_publisher import MQTTPublisher
from .server import (
    app,
    register_analyzers,
    register_repositories,
    register_go2rtc,
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

    # ── 1. 初始化数据库 ──
    db = DatabaseManager(db_path="data/app.db")
    migrate_from_yaml(db, "configs/default.yaml")

    camera_repo = CameraRepository(db)
    model_repo = ModelRepository(db)
    task_repo = TaskRepository(db)
    mqtt_config_repo = MQTTConfigRepository(db)

    model_config = model_repo.get()
    model_cfg = model_config.model_dump()
    camera_configs = camera_repo.get_all()

    if not camera_configs:
        logger.warning("未配置摄像头，仅启动 Web 服务")

    # ── 2. 启动 go2rtc ──
    go2rtc_mgr = Go2RTCManager()

    # 先将所有 RTSP 流写入 go2rtc 配置文件（启动前写入，go2rtc 启动时自动加载）
    for cam in camera_configs:
        url = cam.url
        if url and (url.startswith("rtsp://") or url.startswith("rtmp://")):
            go2rtc_mgr._update_config_file(cam.id, url)
            go2rtc_mgr._registered_streams[cam.id] = url

    go2rtc_started = go2rtc_mgr.start()

    if go2rtc_started:
        ready = go2rtc_mgr.wait_ready()
        if not ready:
            logger.error("go2rtc 启动后 API 未就绪，以无 go2rtc 模式继续")

        # 启动健康检查
        go2rtc_mgr.start_health_check()
    else:
        logger.warning("go2rtc 未启动，以无 go2rtc 模式运行（Analyzer 直连 RTSP）")

    # ── 3. 初始化 MQTT ──
    mqtt_publisher = MQTTPublisher()
    mqtt_config = mqtt_config_repo.get()
    if mqtt_config.enabled and mqtt_config.host:
        mqtt_publisher.connect(mqtt_config)
        logger.info(f"MQTT 已启用，连接到 {mqtt_config.host}:{mqtt_config.port}")
    else:
        logger.info("MQTT 未启用")

    event_session_mgr = EventSessionManager(
        mqtt_publisher=mqtt_publisher,
        mqtt_config_repo=mqtt_config_repo,
        camera_repo=camera_repo,
    )

    # ── 5. 启动摄像头分析器（使用 restream_url 和 on_detections）──
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

    # ── 6. 注入到 server 模块 ──
    register_analyzers(analyzers)
    register_repositories(camera_repo, model_repo, task_repo)
    register_go2rtc(go2rtc_mgr)
    register_mqtt(mqtt_config_repo, mqtt_publisher, event_session_mgr)
    logger.info(f"已启动 {len(analyzers)} 路摄像头分析器")

    # ── 7. 注册退出清理 ──
    atexit.register(mqtt_publisher.disconnect)
    atexit.register(go2rtc_mgr.stop)

    # ── 8. 启动 FastAPI ──
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
