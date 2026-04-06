from __future__ import annotations

import sys
from pathlib import Path


APP_NAME = "Interactive Zone Trigger"
APP_VERSION = "1.0.0"
APP_DATA_DIRNAME = ".interactive_zone_trigger"


def app_data_dir() -> Path:
    path = Path.home() / APP_DATA_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "app_settings.json"


def log_path() -> Path:
    return app_data_dir() / "app.log"


def runtime_base_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def project_root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_resource(*relative_parts: str) -> Path:
    candidates = [runtime_base_dir(), project_root_dir()]
    for base in candidates:
        candidate = base.joinpath(*relative_parts)
        if candidate.exists():
            return candidate
    return candidates[0].joinpath(*relative_parts)


def resolve_model_path(*parts: str) -> Path:
    filename = parts[-1]
    if len(parts) > 1:
        return resolve_resource(*parts)
    candidates = [
        ("Models", filename),
        ("models", filename),
        (filename,),
        ("app", filename),
    ]
    for parts in candidates:
        candidate = resolve_resource(*parts)
        if candidate.exists():
            return candidate
    return resolve_resource("Models", filename)
