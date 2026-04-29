"""
数据库层 — SQLite 连接管理 + Repository 模式数据访问
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import CameraConfig, DetectConfig, ModelConfig, RulesConfig, MQTTConfig, CameraMQTTPublishConfig

logger = logging.getLogger(__name__)


# ── DatabaseManager ──


class DatabaseManager:
    """SQLite 数据库管理器，提供线程安全的连接"""

    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._connections: List[sqlite3.Connection] = []
        self._lock = threading.Lock()

        # 创建数据目录
        db_dir = os.path.dirname(db_path)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError as e:
                raise RuntimeError(
                    f"无法创建数据库目录 '{db_dir}': {e}"
                ) from e

        # 验证路径可写
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"数据库路径不可写 '{db_path}': {e}"
            ) from e

        # 初始化表结构
        self._init_tables()

    def get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（线程本地存储）"""
        conn = getattr(self._local, "connection", None)
        if conn is None:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.row_factory = sqlite3.Row
                self._local.connection = conn
                with self._lock:
                    self._connections.append(conn)
            except sqlite3.OperationalError as e:
                raise RuntimeError(
                    f"无法连接数据库 '{self.db_path}': {e}"
                ) from e
        return conn

    def close(self):
        """关闭所有连接"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()

    def _init_tables(self):
        """创建表结构（如不存在）"""
        conn = self.get_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                detect_config TEXT NOT NULL DEFAULT '{}',
                roi TEXT NOT NULL DEFAULT '[]',
                rules_config TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_config (
                id TEXT PRIMARY KEY,
                detector_path TEXT NOT NULL,
                confidence REAL NOT NULL,
                pose_path TEXT NOT NULL,
                pose_confidence REAL NOT NULL,
                tracker_config TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analysis_tasks (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'waiting_config',
                file_size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                duration REAL DEFAULT 0.0,
                progress INTEGER DEFAULT 0,
                events TEXT DEFAULT '[]',
                stats TEXT DEFAULT NULL,
                output_video TEXT DEFAULT NULL,
                roi TEXT DEFAULT '[]',
                rules TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS mqtt_config (
                id TEXT PRIMARY KEY,
                host TEXT NOT NULL DEFAULT '',
                port INTEGER NOT NULL DEFAULT 1883,
                username TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL DEFAULT '',
                topic TEXT NOT NULL DEFAULT 'behavior-detection/events',
                enabled INTEGER NOT NULL DEFAULT 0,
                update_interval INTEGER NOT NULL DEFAULT 30,
                updated_at TEXT NOT NULL
            );
            """
        )

        # 为已有 cameras 表添加 mqtt_publish_config 列（兼容已有数据库）
        try:
            conn.execute(
                "ALTER TABLE cameras ADD COLUMN mqtt_publish_config TEXT NOT NULL DEFAULT '{}'"
            )
        except Exception:
            pass  # 列已存在，忽略

        conn.commit()


# ── CameraRepository ──


class CameraRepository:
    """摄像头配置数据访问"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all(self) -> List[CameraConfig]:
        """获取所有摄像头配置"""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT id, name, url, detect_config, roi, rules_config, "
            "mqtt_publish_config, created_at, updated_at FROM cameras"
        ).fetchall()

        configs: List[CameraConfig] = []
        for row in rows:
            try:
                detect = DetectConfig(**json.loads(row["detect_config"]))
                roi = json.loads(row["roi"])
                rules = RulesConfig(**json.loads(row["rules_config"]))
                try:
                    mqtt_publish = CameraMQTTPublishConfig(**json.loads(row["mqtt_publish_config"]))
                except Exception:
                    mqtt_publish = CameraMQTTPublishConfig()
                configs.append(
                    CameraConfig(
                        id=row["id"],
                        name=row["name"],
                        url=row["url"],
                        detect=detect,
                        roi=roi,
                        rules=rules,
                        mqtt_publish=mqtt_publish,
                    )
                )
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(
                    f"摄像头配置反序列化失败 (id={row['id']}): {e}，跳过该记录"
                )
        return configs

    def get_by_id(self, camera_id: str) -> Optional[CameraConfig]:
        """按 ID 获取单个摄像头配置"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT id, name, url, detect_config, roi, rules_config, "
            "mqtt_publish_config, created_at, updated_at FROM cameras WHERE id = ?",
            (camera_id,),
        ).fetchone()

        if row is None:
            return None

        try:
            detect = DetectConfig(**json.loads(row["detect_config"]))
            roi = json.loads(row["roi"])
            rules = RulesConfig(**json.loads(row["rules_config"]))
            try:
                mqtt_publish = CameraMQTTPublishConfig(**json.loads(row["mqtt_publish_config"]))
            except Exception:
                mqtt_publish = CameraMQTTPublishConfig()
            return CameraConfig(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                detect=detect,
                roi=roi,
                rules=rules,
                mqtt_publish=mqtt_publish,
            )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"摄像头配置反序列化失败 (id={row['id']}): {e}"
            )
            return None

    def create(self, config: CameraConfig) -> None:
        """创建摄像头配置"""
        conn = self.db.get_connection()
        data = config.model_dump()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO cameras (id, name, url, detect_config, roi, "
            "rules_config, mqtt_publish_config, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["id"],
                data["name"],
                data["url"],
                json.dumps(data["detect"]),
                json.dumps(data["roi"]),
                json.dumps(data["rules"]),
                json.dumps(data["mqtt_publish"]),
                now,
                now,
            ),
        )
        conn.commit()

    def update(self, config: CameraConfig) -> None:
        """更新摄像头配置"""
        conn = self.db.get_connection()
        data = config.model_dump()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE cameras SET name = ?, url = ?, detect_config = ?, "
            "roi = ?, rules_config = ?, mqtt_publish_config = ?, "
            "updated_at = ? WHERE id = ?",
            (
                data["name"],
                data["url"],
                json.dumps(data["detect"]),
                json.dumps(data["roi"]),
                json.dumps(data["rules"]),
                json.dumps(data["mqtt_publish"]),
                now,
                data["id"],
            ),
        )
        conn.commit()

    def delete(self, camera_id: str) -> None:
        """删除摄像头配置"""
        conn = self.db.get_connection()
        conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        conn.commit()

    def count(self) -> int:
        """返回摄像头配置总数"""
        conn = self.db.get_connection()
        row = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()
        return row[0]


# ── ModelRepository ──


class ModelRepository:
    """模型配置数据访问"""

    _DEFAULT_ID = "default"

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self) -> ModelConfig:
        """获取模型配置，不存在则插入默认值并返回"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT detector_path, confidence, pose_path, pose_confidence, "
            "tracker_config FROM model_config WHERE id = ?",
            (self._DEFAULT_ID,),
        ).fetchone()

        if row is not None:
            return ModelConfig(
                detector_path=row["detector_path"],
                confidence=row["confidence"],
                pose_path=row["pose_path"],
                pose_confidence=row["pose_confidence"],
                tracker_config=row["tracker_config"],
            )

        # 不存在 → 插入默认值
        default = ModelConfig()
        self.save(default)
        return default

    def save(self, config: ModelConfig) -> None:
        """保存模型配置（INSERT OR REPLACE）"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO model_config "
            "(id, detector_path, confidence, pose_path, pose_confidence, "
            "tracker_config, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self._DEFAULT_ID,
                config.detector_path,
                config.confidence,
                config.pose_path,
                config.pose_confidence,
                config.tracker_config,
                now,
            ),
        )
        conn.commit()


# ── MQTTConfigRepository ──


class MQTTConfigRepository:
    """MQTT 全局配置数据访问"""

    _DEFAULT_ID = "default"

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self) -> MQTTConfig:
        """获取 MQTT 配置，不存在则返回默认值"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT host, port, username, password, topic, enabled, "
            "update_interval FROM mqtt_config WHERE id = ?",
            (self._DEFAULT_ID,),
        ).fetchone()

        if row is not None:
            return MQTTConfig(
                host=row["host"],
                port=row["port"],
                username=row["username"],
                password=row["password"],
                topic=row["topic"],
                enabled=bool(row["enabled"]),
                update_interval=row["update_interval"],
            )

        return MQTTConfig()

    def save(self, config: MQTTConfig) -> None:
        """保存 MQTT 配置（INSERT OR REPLACE）"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO mqtt_config "
            "(id, host, port, username, password, topic, enabled, "
            "update_interval, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self._DEFAULT_ID,
                config.host,
                config.port,
                config.username,
                config.password,
                config.topic,
                1 if config.enabled else 0,
                config.update_interval,
                now,
            ),
        )
        conn.commit()


# ── TaskRepository ──


class TaskRepository:
    """视频分析任务数据访问"""

    # 需要 JSON 序列化/反序列化的字段
    _JSON_FIELDS = ("events", "stats", "roi", "rules")

    def __init__(self, db: DatabaseManager):
        self.db = db

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """将数据库行转换为 dict，反序列化 JSON 字段"""
        d = dict(row)
        for field in self._JSON_FIELDS:
            val = d.get(field)
            if val is not None:
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"任务字段 '{field}' JSON 反序列化失败，使用原始值")
            else:
                # events 和 roi 默认为空列表，stats 和 rules 默认为 None
                if field in ("events", "roi"):
                    d[field] = []
                else:
                    d[field] = None
        return d

    def get_all(self) -> List[dict]:
        """获取所有任务"""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT id, filename, original_filename, status, file_size, "
            "created_at, duration, progress, events, stats, output_video, "
            "roi, rules FROM analysis_tasks"
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, task_id: str) -> Optional[dict]:
        """按 ID 获取任务"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT id, filename, original_filename, status, file_size, "
            "created_at, duration, progress, events, stats, output_video, "
            "roi, rules FROM analysis_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            return None
        return self._row_to_dict(row)

    def create(self, task: dict) -> None:
        """创建任务记录"""
        conn = self.db.get_connection()
        conn.execute(
            "INSERT INTO analysis_tasks "
            "(id, filename, original_filename, status, file_size, created_at, "
            "duration, progress, events, stats, output_video, roi, rules) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task["id"],
                task["filename"],
                task["original_filename"],
                task.get("status", "waiting_config"),
                task["file_size"],
                task["created_at"],
                task.get("duration", 0.0),
                task.get("progress", 0),
                json.dumps(task.get("events", [])),
                json.dumps(task["stats"]) if task.get("stats") is not None else None,
                task.get("output_video"),
                json.dumps(task.get("roi", [])),
                json.dumps(task["rules"]) if task.get("rules") is not None else None,
            ),
        )
        conn.commit()

    def update_status(self, task_id: str, status: str, progress: int) -> None:
        """更新任务状态和进度"""
        conn = self.db.get_connection()
        conn.execute(
            "UPDATE analysis_tasks SET status = ?, progress = ? WHERE id = ?",
            (status, progress, task_id),
        )
        conn.commit()

    def update_result(
        self,
        task_id: str,
        events: list,
        stats: dict,
        output_video: str,
    ) -> None:
        """更新任务分析结果"""
        conn = self.db.get_connection()
        conn.execute(
            "UPDATE analysis_tasks SET events = ?, stats = ?, output_video = ? "
            "WHERE id = ?",
            (
                json.dumps(events),
                json.dumps(stats) if stats is not None else None,
                output_video,
                task_id,
            ),
        )
        conn.commit()

    def delete(self, task_id: str) -> None:
        """删除任务记录"""
        conn = self.db.get_connection()
        conn.execute("DELETE FROM analysis_tasks WHERE id = ?", (task_id,))
        conn.commit()


# ── YAML 迁移工具 ──


def migrate_from_yaml(db: DatabaseManager, yaml_path: str = "configs/default.yaml") -> None:
    """
    从 YAML 配置文件迁移数据到数据库。
    仅在数据库为空时执行，跳过无效条目并记录警告。
    """
    camera_repo = CameraRepository(db)
    model_repo = ModelRepository(db)

    # 检查数据库是否已有数据
    conn = db.get_connection()
    camera_count = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    model_count = conn.execute("SELECT COUNT(*) FROM model_config").fetchone()[0]

    if camera_count > 0 or model_count > 0:
        logger.info("数据库已有数据，跳过 YAML 迁移")
        return

    # 检查 YAML 文件是否存在
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        logger.info(f"YAML 配置文件不存在: {yaml_path}，跳过迁移")
        return

    # 读取 YAML 文件
    try:
        import yaml as yaml_lib

        with open(yaml_file, "r", encoding="utf-8") as f:
            config = yaml_lib.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"YAML 配置文件格式错误: {e}，跳过迁移")
        return

    # 迁移摄像头配置
    cameras_data = config.get("cameras", [])
    migrated_cameras = 0
    for cam_data in cameras_data:
        try:
            cam_config = CameraConfig(**cam_data)
            camera_repo.create(cam_config)
            migrated_cameras += 1
        except Exception as e:
            logger.warning(f"摄像头配置迁移失败: {e}，跳过该条目")

    # 迁移模型配置
    model_migrated = False
    model_data = config.get("model")
    if model_data:
        try:
            model_config = ModelConfig(**model_data)
            model_repo.save(model_config)
            model_migrated = True
        except Exception as e:
            logger.warning(f"模型配置迁移失败: {e}")

    logger.info(
        f"YAML 迁移完成: {migrated_cameras} 个摄像头配置, "
        f"模型配置 {'已迁移' if model_migrated else '未迁移'}"
    )
