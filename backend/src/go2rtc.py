"""
go2rtc stream management module — manages RTSP stream proxy

Dynamically manages RTSP streams via go2rtc REST API:
- Automatically registers go2rtc stream when adding/updating cameras
- Automatically removes go2rtc stream when deleting cameras
- Automatically starts/stops go2rtc process
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

# go2rtc default configuration
DEFAULT_GO2RTC_API = "http://127.0.0.1:1984"
DEFAULT_GO2RTC_RTSP_PORT = 8555
DEFAULT_GO2RTC_CONFIG = "data/go2rtc.yaml"


def _find_go2rtc_binary() -> Optional[str]:
    """Find go2rtc executable"""
    # Look for go2rtc in data/ directory first
    local_path = Path("data/go2rtc.exe")
    if local_path.exists():
        return str(local_path)
    local_path = Path("data/go2rtc")
    if local_path.exists():
        return str(local_path)
    # Look in PATH
    import shutil
    path = shutil.which("go2rtc")
    if path:
        return path
    return None


class Go2RTCManager:
    """go2rtc stream manager — via REST API + config file dual-write"""

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
        """Get go2rtc restream URL (for ffmpeg/OpenCV to pull stream)"""
        return f"rtsp://127.0.0.1:{self.rtsp_port}/{stream_name}"

    def wait_ready(self, timeout: float = 10.0) -> bool:
        """Wait for go2rtc API port to be reachable, used to confirm readiness after startup"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = requests.get(f"{self.api_url}/api/streams", timeout=2)
                if r.ok:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        logger.error(f"go2rtc API not ready within {timeout}s")
        return False

    def start(self) -> bool:
        """Start go2rtc process"""
        binary = _find_go2rtc_binary()
        if not binary:
            logger.warning("go2rtc not found, RTSP proxy unavailable. "
                           "Please place go2rtc in the data/ directory")
            return False

        # Ensure config file exists
        self._ensure_config()

        try:
            self._process = subprocess.Popen(
                [binary, "-config", self.config_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for startup
            time.sleep(1)
            if self._process.poll() is not None:
                logger.error("go2rtc failed to start")
                return False
            logger.info(f"go2rtc started (PID={self._process.pid}), "
                        f"API={self.api_url}, RTSP=:{self.rtsp_port}")
            return True
        except Exception as e:
            logger.error(f"go2rtc startup error: {e}")
            return False

    def stop(self):
        """Stop go2rtc process"""
        self.stop_health_check()
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._registered_streams.clear()
        logger.info("go2rtc stopped")

    def start_health_check(self):
        """Start background health check thread (checks every 30 seconds)"""
        if self._health_check_running:
            return
        self._health_check_running = True
        self._health_thread = threading.Thread(
            target=self._health_check_loop, daemon=True
        )
        self._health_thread.start()
        logger.info("go2rtc health check thread started")

    def stop_health_check(self):
        """Stop health check thread"""
        self._health_check_running = False
        if self._health_thread:
            self._health_thread.join(timeout=5)
            self._health_thread = None

    def _health_check_loop(self):
        """Health check loop: checks process alive every 30 seconds, auto-restarts on unexpected exit"""
        while self._health_check_running:
            time.sleep(30)
            if not self._health_check_running:
                break
            if self._process and self._process.poll() is not None:
                logger.warning("go2rtc process exited unexpectedly, auto-restarting in 3 seconds...")
                time.sleep(3)
                if not self._health_check_running:
                    break
                if self.start():
                    # Re-register all recorded streams
                    for name, url in self._registered_streams.items():
                        self.add_stream(name, url)
                    logger.info("go2rtc restarted and re-registered all streams")

    def register_all_streams(self, cameras: list[dict]):
        """Batch register all camera streams to go2rtc"""
        for cam in cameras:
            cam_id = cam.get("id", "")
            rtsp_url = cam.get("url", "")
            if cam_id and rtsp_url:
                self.add_stream(cam_id, rtsp_url)
                self._registered_streams[cam_id] = rtsp_url

    def get_player_url(self, stream_name: str) -> str:
        """Get go2rtc WebSocket player URL"""
        return f"/go2rtc/ws?src={stream_name}"

    def get_all_player_urls(self) -> dict[str, str]:
        """Get player URL mapping for all registered streams"""
        return {
            name: self.get_player_url(name)
            for name in self._registered_streams
        }

    @property
    def available(self) -> bool:
        """Whether go2rtc is available (binary exists and process is running)"""
        binary_exists = _find_go2rtc_binary() is not None
        process_running = self._process is not None and self._process.poll() is None
        return binary_exists and process_running

    def is_running(self) -> bool:
        """Check if go2rtc is running"""
        if self._process and self._process.poll() is None:
            return True
        # Also check if API is reachable (may have been started externally)
        try:
            r = requests.get(f"{self.api_url}/api/streams", timeout=2)
            return r.ok
        except Exception:
            return False

    def add_stream(self, stream_name: str, rtsp_url: str) -> bool:
        """Add or update go2rtc stream"""
        self._registered_streams[stream_name] = rtsp_url

        # URLs with encoded characters need ffmpeg source, only write config file (API breaks encoding)
        use_ffmpeg = "%" in rtsp_url and rtsp_url.startswith("rtsp://")

        if not use_ffmpeg:
            # Normal URLs updated via API hot-reload
            try:
                api_url = f"{self.api_url}/api/streams?name={stream_name}&src={rtsp_url}"
                r = requests.put(api_url, timeout=10)
                if not r.ok:
                    logger.error(f"go2rtc add stream failed {stream_name}: {r.status_code} {r.text}")
                else:
                    logger.info(f"go2rtc stream added: {stream_name}")
            except requests.RequestException as e:
                logger.warning(f"go2rtc API unavailable, writing to config file only: {e}")

        # Write to config file for persistence (with ffmpeg prefix handling)
        self._update_config_file(stream_name, rtsp_url)

        if use_ffmpeg:
            logger.info(f"go2rtc stream written to config (ffmpeg source): {stream_name}")

        return True

    def remove_stream(self, stream_name: str) -> bool:
        """Delete go2rtc stream"""
        self._registered_streams.pop(stream_name, None)

        try:
            r = requests.delete(
                f"{self.api_url}/api/streams",
                params={"src": stream_name},
                timeout=10,
            )
            if r.ok:
                logger.info(f"go2rtc stream deleted: {stream_name}")
        except requests.RequestException as e:
            logger.warning(f"go2rtc API unavailable: {e}")

        self._remove_from_config_file(stream_name)
        return True

    def _ensure_config(self):
        """Ensure go2rtc config file exists"""
        if os.path.isfile(self.config_path):
            # Ensure existing config includes origin setting
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
        """Update go2rtc.yaml config file"""
        config = self._load_config()
        if "streams" not in config:
            config["streams"] = {}
        # For RTSP URLs with encoded characters, use ffmpeg source (go2rtc's built-in RTSP client has poor compatibility with encoded URLs)
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
        """Remove stream from go2rtc.yaml"""
        config = self._load_config()
        streams = config.get("streams", {})
        if stream_name in streams:
            del streams[stream_name]
            self._save_config(config)

    def _load_config(self) -> dict:
        """Load go2rtc.yaml"""
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
        """Save go2rtc.yaml"""
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
