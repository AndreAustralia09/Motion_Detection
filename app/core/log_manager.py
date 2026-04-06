from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import time
from typing import Callable

from app.utils.app_paths import APP_VERSION, app_data_dir, log_path


class LogManager:
    WARNING_RATE_LIMIT_S = 5.0
    MAX_LOG_BYTES = 1_000_000
    BACKUP_COUNT = 3

    def __init__(self) -> None:
        self.base_dir = app_data_dir()
        self.log_path = log_path()
        self.logger = logging.getLogger("interactive_zone_trigger")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        formatter = logging.Formatter("[%(asctime)s] %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
        file_handler = RotatingFileHandler(
            self.log_path,
            encoding="utf-8",
            maxBytes=self.MAX_LOG_BYTES,
            backupCount=self.BACKUP_COUNT,
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.subscribers: list[Callable[[str, str], None]] = []
        self._last_warning_times: dict[str, float] = {}
        self.info(f"Starting {APP_VERSION}")

    def set_debug(self, enabled: bool) -> None:
        self.logger.setLevel(logging.DEBUG if enabled else logging.INFO)

    def subscribe(self, callback: Callable[[str, str], None]) -> None:
        self.subscribers.append(callback)

    def _emit(self, level: str, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        for callback in self.subscribers:
            try:
                callback(timestamp, level, message)
            except TypeError:
                callback(level, message)

    def info(self, message: str) -> None:
        self.logger.info(message)
        self._emit("INFO", message)

    def debug(self, message: str) -> None:
        self.logger.debug(message)
        self._emit("DEBUG", message)

    def warning(self, message: str) -> None:
        if self._is_rate_limited(message):
            return
        self.logger.warning(message)
        self._emit("WARNING", message)

    def error(self, message: str) -> None:
        self.logger.error(message)
        self._emit("ERROR", message)

    def exception(self, message: str) -> None:
        self.logger.exception(message)
        self._emit("ERROR", message)

    def get_log_file_path(self) -> str:
        return str(self.log_path)

    def _is_rate_limited(self, message: str) -> bool:
        now = time.monotonic()
        previous = self._last_warning_times.get(message)
        if previous is not None and (now - previous) < self.WARNING_RATE_LIMIT_S:
            return True
        self._last_warning_times[message] = now
        return False
