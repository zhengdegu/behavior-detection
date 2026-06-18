"""
Database layer — SQLite connection management + Repository pattern data access
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .config import CameraConfig, DetectConfig, ModelConfig, RulesConfig, MQTTConfig, CameraMQTTPublishConfig, Go2RTCConfig

logger = logging.getLogger(__name__)


# ── DatabaseManager ──


class DatabaseManager:
    """SQLite database manager providing thread-safe connections"""

    def __init__(self, db_path: str = "data/app.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._connections: List[sqlite3.Connection] = []
        self._lock = threading.Lock()

        # Create data directory
        db_dir = os.path.dirname(db_path)
        if db_dir:
            try:
                os.makedirs(db_dir, exist_ok=True)
            except OSError as e:
                raise RuntimeError(
                    f"Unable to create database directory '{db_dir}': {e}"
                ) from e

        # Verify path is writable
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"Database path not writable '{db_path}': {e}"
            ) from e

        # Initialize table schema
        self._init_tables()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection for current thread (thread-local storage)"""
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
                    f"Unable to connect to database '{self.db_path}': {e}"
                ) from e
        return conn

    def close(self):
        """Close all connections"""
        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception:
                    pass
            self._connections.clear()

    def _init_tables(self):
        """Create table schema (if not exists)"""
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
                tls_enabled INTEGER NOT NULL DEFAULT 0,
                tls_insecure INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS go2rtc_config (
                id TEXT PRIMARY KEY,
                webrtc_candidates TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # Add mqtt_publish_config column to existing cameras table (backward compatible)
        try:
            conn.execute(
                "ALTER TABLE cameras ADD COLUMN mqtt_publish_config TEXT NOT NULL DEFAULT '{}'"
            )
        except Exception:
            pass  # Column already exists, ignore

        # Add time_offset column (backward compatible) — deprecated, replaced by timezone
        try:
            conn.execute(
                "ALTER TABLE cameras ADD COLUMN time_offset REAL DEFAULT NULL"
            )
        except Exception:
            pass  # Column already exists, ignore

        # Add timezone column (replaces time_offset)
        try:
            conn.execute(
                "ALTER TABLE cameras ADD COLUMN timezone TEXT DEFAULT NULL"
            )
        except Exception:
            pass  # Column already exists, ignore

        # Add TLS columns to mqtt_config (backward compatible)
        for col, default in [("tls_enabled", 0), ("tls_insecure", 0)]:
            try:
                conn.execute(
                    f"ALTER TABLE mqtt_config ADD COLUMN {col} INTEGER NOT NULL DEFAULT {default}"
                )
            except Exception:
                pass  # Column already exists, ignore

        conn.commit()


# ── CameraRepository ──


class CameraRepository:
    """Camera configuration data access"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all(self) -> List[CameraConfig]:
        """Get all camera configurations"""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT id, name, url, detect_config, roi, rules_config, "
            "mqtt_publish_config, timezone, created_at, updated_at FROM cameras"
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
                        timezone=row["timezone"],
                    )
                )
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(
                    f"Camera config deserialization failed (id={row['id']}): {e}, skipping record"
                )
        return configs

    def get_by_id(self, camera_id: str) -> Optional[CameraConfig]:
        """Get single camera configuration by ID"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT id, name, url, detect_config, roi, rules_config, "
            "mqtt_publish_config, timezone, created_at, updated_at FROM cameras WHERE id = ?",
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
                timezone=row["timezone"],
            )
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"Camera config deserialization failed (id={row['id']}): {e}"
            )
            return None

    def create(self, config: CameraConfig) -> None:
        """Create camera configuration"""
        conn = self.db.get_connection()
        data = config.model_dump()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO cameras (id, name, url, detect_config, roi, "
            "rules_config, mqtt_publish_config, timezone, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["id"],
                data["name"],
                data["url"],
                json.dumps(data["detect"]),
                json.dumps(data["roi"]),
                json.dumps(data["rules"]),
                json.dumps(data["mqtt_publish"]),
                data["timezone"],
                now,
                now,
            ),
        )
        conn.commit()

    def update(self, config: CameraConfig) -> None:
        """Update camera configuration"""
        conn = self.db.get_connection()
        data = config.model_dump()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE cameras SET name = ?, url = ?, detect_config = ?, "
            "roi = ?, rules_config = ?, mqtt_publish_config = ?, "
            "timezone = ?, updated_at = ? WHERE id = ?",
            (
                data["name"],
                data["url"],
                json.dumps(data["detect"]),
                json.dumps(data["roi"]),
                json.dumps(data["rules"]),
                json.dumps(data["mqtt_publish"]),
                data["timezone"],
                now,
                data["id"],
            ),
        )
        conn.commit()

    def delete(self, camera_id: str) -> None:
        """Delete camera configuration"""
        conn = self.db.get_connection()
        conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
        conn.commit()

    def count(self) -> int:
        """Return total camera configuration count"""
        conn = self.db.get_connection()
        row = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()
        return row[0]


# ── ModelRepository ──


class ModelRepository:
    """Model configuration data access"""

    _DEFAULT_ID = "default"

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self) -> ModelConfig:
        """Get model configuration, insert default values if not exists"""
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

        # Not exists → insert default values
        default = ModelConfig()
        self.save(default)
        return default

    def save(self, config: ModelConfig) -> None:
        """Save model configuration (INSERT OR REPLACE)"""
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
    """MQTT global configuration data access"""

    _DEFAULT_ID = "default"

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self) -> MQTTConfig:
        """Get MQTT configuration, return default values if not exists"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT host, port, username, password, topic, enabled, "
            "update_interval, tls_enabled, tls_insecure FROM mqtt_config WHERE id = ?",
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
                tls_enabled=bool(row["tls_enabled"]),
                tls_insecure=bool(row["tls_insecure"]),
            )

        return MQTTConfig()

    def save(self, config: MQTTConfig) -> None:
        """Save MQTT configuration (INSERT OR REPLACE)"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO mqtt_config "
            "(id, host, port, username, password, topic, enabled, "
            "update_interval, tls_enabled, tls_insecure, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self._DEFAULT_ID,
                config.host,
                config.port,
                config.username,
                config.password,
                config.topic,
                1 if config.enabled else 0,
                config.update_interval,
                1 if config.tls_enabled else 0,
                1 if config.tls_insecure else 0,
                now,
            ),
        )
        conn.commit()


# ── Go2RTCConfigRepository ──


class Go2RTCConfigRepository:
    """go2rtc global configuration data access"""

    _DEFAULT_ID = "default"

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get(self) -> Go2RTCConfig:
        """Get go2rtc configuration, return default values if not exists"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT webrtc_candidates FROM go2rtc_config WHERE id = ?",
            (self._DEFAULT_ID,),
        ).fetchone()

        if row is not None:
            return Go2RTCConfig(
                webrtc_candidates=row["webrtc_candidates"],
            )

        return Go2RTCConfig()

    def save(self, config: Go2RTCConfig) -> None:
        """Save go2rtc configuration (INSERT OR REPLACE)"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO go2rtc_config "
            "(id, webrtc_candidates, updated_at) VALUES (?, ?, ?)",
            (
                self._DEFAULT_ID,
                config.webrtc_candidates,
                now,
            ),
        )
        conn.commit()


# ── TaskRepository ──


class TaskRepository:
    """Video analysis task data access"""

    # Fields requiring JSON serialization/deserialization
    _JSON_FIELDS = ("events", "stats", "roi", "rules")

    def __init__(self, db: DatabaseManager):
        self.db = db

    def _row_to_dict(self, row: sqlite3.Row) -> dict:
        """Convert database row to dict, deserializing JSON fields"""
        d = dict(row)
        for field in self._JSON_FIELDS:
            val = d.get(field)
            if val is not None:
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Task field '{field}' JSON deserialization failed, using raw value")
            else:
                # events and roi default to empty list, stats and rules default to None
                if field in ("events", "roi"):
                    d[field] = []
                else:
                    d[field] = None
        return d

    def get_all(self) -> List[dict]:
        """Get all tasks"""
        conn = self.db.get_connection()
        rows = conn.execute(
            "SELECT id, filename, original_filename, status, file_size, "
            "created_at, duration, progress, events, stats, output_video, "
            "roi, rules FROM analysis_tasks"
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_by_id(self, task_id: str) -> Optional[dict]:
        """Get task by ID"""
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
        """Create task record"""
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
        """Update task status and progress"""
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
        """Update task analysis results"""
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
        """Delete task record"""
        conn = self.db.get_connection()
        conn.execute("DELETE FROM analysis_tasks WHERE id = ?", (task_id,))
        conn.commit()


# ── UserRepository ──


class UserRepository:
    """User data access for authentication"""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_by_username(self, username: str) -> Optional[dict]:
        """Get user by username, return dict or None"""
        conn = self.db.get_connection()
        row = conn.execute(
            "SELECT id, username, password_hash, created_at, updated_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row:
            return dict(row)
        return None

    def create(self, username: str, password_hash: str) -> dict:
        """Create a new user"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, now, now),
        )
        conn.commit()
        return self.get_by_username(username)  # type: ignore

    def update_password(self, username: str, password_hash: str) -> None:
        """Update user password"""
        conn = self.db.get_connection()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
            (password_hash, now, username),
        )
        conn.commit()

    def count(self) -> int:
        """Get total user count"""
        conn = self.db.get_connection()
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        return row["cnt"] if row else 0


# ── YAML Migration Tool ──


def migrate_from_yaml(db: DatabaseManager, yaml_path: str = "configs/default.yaml") -> None:
    """
    Migrate data from YAML configuration file to database.
    Only executes when database is empty, skips invalid entries and logs warnings.
    """
    camera_repo = CameraRepository(db)
    model_repo = ModelRepository(db)

    # Check if database already has data
    conn = db.get_connection()
    camera_count = conn.execute("SELECT COUNT(*) FROM cameras").fetchone()[0]
    model_count = conn.execute("SELECT COUNT(*) FROM model_config").fetchone()[0]

    if camera_count > 0 or model_count > 0:
        logger.info("Database already has data, skipping YAML migration")
        return

    # Check if YAML file exists
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        logger.info(f"YAML config file not found: {yaml_path}, skipping migration")
        return

    # Read YAML file
    try:
        import yaml as yaml_lib

        with open(yaml_file, "r", encoding="utf-8") as f:
            config = yaml_lib.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"YAML config file format error: {e}, skipping migration")
        return

    # Migrate camera configurations
    cameras_data = config.get("cameras", [])
    migrated_cameras = 0
    for cam_data in cameras_data:
        try:
            cam_config = CameraConfig(**cam_data)
            camera_repo.create(cam_config)
            migrated_cameras += 1
        except Exception as e:
            logger.warning(f"Camera config migration failed: {e}, skipping entry")

    # Migrate model configuration
    model_migrated = False
    model_data = config.get("model")
    if model_data:
        try:
            model_config = ModelConfig(**model_data)
            model_repo.save(model_config)
            model_migrated = True
        except Exception as e:
            logger.warning(f"Model config migration failed: {e}")

    logger.info(
        f"YAML migration complete: {migrated_cameras} camera configs, "
        f"model config {'migrated' if model_migrated else 'not migrated'}"
    )
