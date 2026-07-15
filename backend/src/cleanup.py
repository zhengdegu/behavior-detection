"""
Periodic cleanup — removes old event screenshots to prevent disk exhaustion.
Runs as a background daemon thread, checks once per hour.
"""

import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# Default: keep screenshots for 7 days
DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_CHECK_INTERVAL_SECONDS = 3600  # 1 hour


class EventCleanup:
    """Background cleanup for event screenshot files"""

    def __init__(self, events_dir: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS,
                 check_interval: float = DEFAULT_CHECK_INTERVAL_SECONDS):
        self._events_dir = Path(events_dir)
        self._max_age_seconds = max_age_days * 86400
        self._check_interval = check_interval
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        """Start background cleanup thread"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Event cleanup started: max_age={self._max_age_seconds // 86400}d, "
                    f"dir={self._events_dir}")

    def stop(self):
        """Stop cleanup thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        """Main loop: run cleanup immediately, then every check_interval"""
        # Run once at startup
        self._cleanup()
        while self._running:
            time.sleep(self._check_interval)
            if self._running:
                self._cleanup()

    def _cleanup(self):
        """Delete event screenshot files older than max_age"""
        if not self._events_dir.exists():
            return

        now = time.time()
        cutoff = now - self._max_age_seconds
        removed = 0

        try:
            for f in self._events_dir.iterdir():
                if not f.is_file():
                    continue
                # Only clean .jpg files (event screenshots)
                if f.suffix.lower() != ".jpg":
                    continue
                try:
                    mtime = f.stat().st_mtime
                    if mtime < cutoff:
                        f.unlink()
                        removed += 1
                except OSError:
                    pass  # File may have been deleted by another process
        except OSError as e:
            logger.warning(f"Event cleanup scan error: {e}")

        if removed > 0:
            logger.info(f"Event cleanup: removed {removed} screenshots older than "
                        f"{self._max_age_seconds // 86400} days")
