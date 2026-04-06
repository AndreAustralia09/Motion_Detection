from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.utils.app_paths import app_data_dir, settings_path

DEFAULT_APP_SETTINGS = {
    "theme": "Light",
    "auto_load_last_project": True,
    "start_minimized": False,
    "show_fps_overlay": True,
}


class SettingsRepository:
    def __init__(self) -> None:
        self.base_dir = app_data_dir()
        self.settings_path = settings_path()

    def load(self) -> dict:
        if not self.settings_path.exists():
            return dict(DEFAULT_APP_SETTINGS)
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return dict(DEFAULT_APP_SETTINGS)
        if not isinstance(data, dict):
            return dict(DEFAULT_APP_SETTINGS)
        merged = dict(DEFAULT_APP_SETTINGS)
        merged.update(data)
        return merged

    def save(self, data: dict) -> None:
        with NamedTemporaryFile("w", delete=False, dir=self.base_dir, encoding="utf-8", suffix=".tmp") as handle:
            handle.write(json.dumps(data, indent=2))
            temp_path = Path(handle.name)
        temp_path.replace(self.settings_path)
