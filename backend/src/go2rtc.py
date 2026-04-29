"""
go2rtc 流管理模块 — 管理 RTSP 流代理

通过 go2rtc REST API 动态管理 RTSP 流：
- 添加/更新摄像头时自动注册 go2rtc stream
- 删除摄像头时自动移除 go2rtc stream
- 自动启动/停止 go2rtc 进程
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import requests
import yaml

logger = logging.getLogger(__name__)

# go2rtc 默认配置
DEFAULT_GO2RTC_API = "http://127.0.0.1:1984"
DEFAULT_GO2RTC_RTSP_PORT = 8555
DEFAULT_GO2RTC_CONFIG = "data/go2rtc.yaml"


def _find_go2rtc_binary() -> Optional[str]:
    """查找 go2rtc 可执行文件"""
    # 优先查找 data/ 目录下的
    local_path = Path("data/go2rtc.exe")
    if local_path.exists():
        return str(local_path)
    local_path = Path("data/go2rtc")
    if local_path.exists():
        return str(local_path)
    # 查找 PATH 中的
    import shutil
    path = shutil.which("go2rtc")
    if path:
        return path
    return None


class Go2RTCManager:
    """go2rtc 流管理器 — 通过 REST API + 配置文件双写"""

    def __init__(self, api_url: str = DEFAULT_GO2RTC_API,
                 rtsp_port: int = DEFAULT_GO2RTC_RTSP_PORT,
                 config_path: str = DEFAULT_GO2RTC_CONFIG):
        self.api_url = api_url
        self.rtsp_port = rtsp_port
        self.config_path = config_path
        self._process: Optional[subprocess.Popen] = None
        self._registered_streams: dict[str, str] = {}
        self._health_check_running: bool = False
        self._health_thread: Optional[threading.Thread] = None

    def get_restream_url(self, stream_name: str) -> str:
        """获取 go2rtc restream 地址（供 ffmpeg/OpenCV 拉流）"""
        return f"rtsp://127.0.0.1:{self.rtsp_port}/{stream_name}"

    def wait_ready(self, timeout: float = 10.0) -> bool:
        """等待 go2rtc API 端口可达，用于启动后确认就绪"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = requests.get(f"{self.api_url}/api/streams", timeout=2)
                if r.ok:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        logger.error(f"go2rtc API 在 {timeout}s 内未就绪")
        return False

    def start(self) -> bool:
        """启动 go2rtc 进程"""
        binary = _find_go2rtc_binary()
        if not binary:
            logger.warning("go2rtc 未找到，RTSP 代理不可用。"
                           "请将 go2rtc 放在 data/ 目录下")
            return False

        # 确保配置文件存在
        self._ensure_config()

        try:
            self._process = subprocess.Popen(
                [binary, "-config", self.config_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # 等待启动
            time.sleep(1)
            if self._process.poll() is not None:
                logger.error("go2rtc 启动失败")
                return False
            logger.info(f"go2rtc 已启动 (PID={self._process.pid}), "
                        f"API={self.api_url}, RTSP=:{self.rtsp_port}")
            return True
        except Exception as e:
            logger.error(f"go2rtc 启动异常: {e}")
            return False

    def stop(self):
        """停止 go2rtc 进程"""
        self.stop_health_check()
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._registered_streams.clear()
        logger.info("go2rtc 已停止")

    def start_health_check(self):
        """启动后台健康检查线程（每 30 秒检查一次）"""
        if self._health_check_running:
            return
        self._health_check_running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop, daemon=True
        )
        self._health_thread.start()
        logger.info("go2rtc 健康检查线程已启动")

    def stop_health_check(self):
        """停止健康检查线程"""
        self._health_check_running = False
        if self._health_thread:
            self._health_thread.join(timeout=5)
            self._health_thread = None

    def _health_check_loop(self):
        """健康检查循环：每 30 秒检查进程存活，意外退出时自动重启"""
        while self._health_check_running:
            time.sleep(30)
            if not self._health_check_running:
                break
            if self._process and self._process.poll() is not None:
                logger.warning("go2rtc 进程意外退出，3 秒后自动重启...")
                time.sleep(3)
                if not self._health_check_running:
                    break
                if self.start():
                    # 重新注册所有已记录的流
                    for name, url in self._registered_streams.items():
                        self.add_stream(name, url)
                    logger.info("go2rtc 已重启并重新注册所有流")

    def register_all_streams(self, cameras: list[dict]):
        """批量注册所有摄像头流到 go2rtc"""
        for cam in cameras:
            cam_id = cam.get("id", "")
            rtsp_url = cam.get("url", "")
            if cam_id and rtsp_url:
                self.add_stream(cam_id, rtsp_url)
                self._registered_streams[cam_id] = rtsp_url

    def get_player_url(self, stream_name: str) -> str:
        """获取 go2rtc WebSocket 播放器 URL"""
        return f"/go2rtc/ws?src={stream_name}"

    def get_all_player_urls(self) -> dict[str, str]:
        """获取所有已注册流的播放器 URL 映射"""
        return {
            name: self.get_player_url(name)
            for name in self._registered_streams
        }

    @property
    def available(self) -> bool:
        """go2rtc 是否可用（二进制存在且进程运行中）"""
        binary_exists = _find_go2rtc_binary() is not None
        process_running = self._process is not None and self._process.poll() is None
        return binary_exists and process_running

    def is_running(self) -> bool:
        """检查 go2rtc 是否在运行"""
        if self._process and self._process.poll() is None:
            return True
        # 也检查 API 是否可达（可能是外部启动的）
        try:
            r = requests.get(f"{self.api_url}/api/streams", timeout=2)
            return r.ok
        except Exception:
            return False

    def add_stream(self, stream_name: str, rtsp_url: str) -> bool:
        """添加或更新 go2rtc 流"""
        self._registered_streams[stream_name] = rtsp_url

        # 含 URL 编码字符的 RTSP URL 需要用 ffmpeg 源，只写配置文件（API 会破坏编码）
        use_ffmpeg = "%" in rtsp_url and rtsp_url.startswith("rtsp://")

        if not use_ffmpeg:
            # 普通 URL 通过 API 热更新
            try:
                api_url = f"{self.api_url}/api/streams?name={stream_name}&src={rtsp_url}"
                r = requests.put(api_url, timeout=10)
                if not r.ok:
                    logger.error(f"go2rtc 添加流失败 {stream_name}: {r.status_code} {r.text}")
                else:
                    logger.info(f"go2rtc 流已添加: {stream_name}")
            except requests.RequestException as e:
                logger.warning(f"go2rtc API 不可用，仅写入配置文件: {e}")

        # 写入配置文件持久化（含 ffmpeg 前缀处理）
        self._update_config_file(stream_name, rtsp_url)

        if use_ffmpeg:
            logger.info(f"go2rtc 流已写入配置 (ffmpeg 源): {stream_name}")

        return True

    def remove_stream(self, stream_name: str) -> bool:
        """删除 go2rtc 流"""
        self._registered_streams.pop(stream_name, None)

        try:
            r = requests.delete(
                f"{self.api_url}/api/streams",
                params={"src": stream_name},
                timeout=10,
            )
            if r.ok:
                logger.info(f"go2rtc 流已删除: {stream_name}")
        except requests.RequestException as e:
            logger.warning(f"go2rtc API 不可用: {e}")

        self._remove_from_config_file(stream_name)
        return True

    def _ensure_config(self):
        """确保 go2rtc 配置文件存在"""
        if os.path.isfile(self.config_path):
            # 确保已有配置包含 origin 设置
            config = self._load_config()
            api_cfg = config.get("api", {})
            if "origin" not in api_cfg:
                api_cfg["origin"] = "*"
                config["api"] = api_cfg
                self._save_config(config)
            return
        config = {
            "streams": {},
            "rtsp": {"listen": f":{self.rtsp_port}"},
            "api": {"listen": ":1984", "origin": "*"},
            "log": {"level": "info"},
        }
        self._save_config(config)

    def _update_config_file(self, stream_name: str, rtsp_url: str):
        """更新 go2rtc.yaml 配置文件"""
        config = self._load_config()
        if "streams" not in config:
            config["streams"] = {}
        # 对含 URL 编码字符的 RTSP URL 使用 ffmpeg 源（go2rtc 内置 RTSP 客户端对编码 URL 兼容性差）
        if "%" in rtsp_url and rtsp_url.startswith("rtsp://"):
            stream_value = (
                f"exec:ffmpeg -hide_banner -rtsp_transport tcp -timeout 10000000 "
                f"-i {rtsp_url} -c:v libx264 -preset ultrafast -tune zerolatency "
                f"-rtsp_transport tcp -f rtsp {{output}}"
            )
        else:
            stream_value = rtsp_url
        config["streams"][stream_name] = stream_value
        self._save_config(config)

    def _remove_from_config_file(self, stream_name: str):
        """从 go2rtc.yaml 移除流"""
        config = self._load_config()
        streams = config.get("streams", {})
        if stream_name in streams:
            del streams[stream_name]
            self._save_config(config)

    def _load_config(self) -> dict:
        """加载 go2rtc.yaml"""
        if os.path.isfile(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {
            "streams": {},
            "rtsp": {"listen": f":{self.rtsp_port}"},
            "api": {"listen": ":1984"},
            "log": {"level": "info"},
        }

    def _save_config(self, config: dict):
        """保存 go2rtc.yaml"""
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
