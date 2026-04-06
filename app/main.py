from __future__ import annotations

import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from app.core.camera_manager import CameraManager
from app.core.log_manager import LogManager
from app.core.project_manager import ProjectManager
from app.core.relay_manager import RelayManager
from app.core.serial_manager import SerialManager
from app.models.runtime_state import AppRuntimeState
from app.storage.project_repository import ProjectRepository
from app.storage.settings_repository import DEFAULT_APP_SETTINGS, SettingsRepository
from app.ui.main_window import MainWindow


def _activate_startup_window(window: MainWindow) -> None:
    window.showNormal()
    window.raise_()
    window.activateWindow()


def _show_startup_window(window: MainWindow, *, start_minimized: bool) -> None:
    if start_minimized:
        window.showMinimized()
        QTimer.singleShot(75, window.begin_initial_load)
        return

    window.show()
    QTimer.singleShot(0, lambda: _activate_startup_window(window))
    QTimer.singleShot(75, window.begin_initial_load)
    QTimer.singleShot(150, lambda: _activate_startup_window(window))


def _configure_high_dpi() -> None:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)


def main() -> int:
    _configure_high_dpi()
    app = QApplication(sys.argv)

    settings_repo = SettingsRepository()
    log_manager = LogManager()
    project_manager = ProjectManager(ProjectRepository())
    camera_manager = CameraManager()
    runtime_state = AppRuntimeState()
    relay_manager = RelayManager()
    serial_manager = SerialManager(log_manager)

    def _log_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        log_manager.error(f"Unhandled exception:\n{message}")

    sys.excepthook = _log_uncaught_exception

    settings = settings_repo.load()
    last_project = settings.get("last_project")
    auto_load_last_project = bool(settings.get("auto_load_last_project", DEFAULT_APP_SETTINGS["auto_load_last_project"]))
    if auto_load_last_project and last_project and Path(last_project).exists():
        try:
            project_manager.open_project(last_project)
        except Exception as exc:
            log_manager.error(f"Failed to auto-load project: {exc}")

    if not project_manager.current_project.cameras:
        project_manager.add_camera("Camera 1", 0)

    window = MainWindow(
        project_manager=project_manager,
        camera_manager=camera_manager,
        relay_manager=relay_manager,
        serial_manager=serial_manager,
        log_manager=log_manager,
        runtime_state=runtime_state,
        app_settings=settings,
    )
    start_minimized = bool(settings.get("start_minimized", DEFAULT_APP_SETTINGS["start_minimized"]))
    _show_startup_window(window, start_minimized=start_minimized)

    try:
        result = app.exec()
    finally:
        save_data = window.get_app_settings()
        save_data["last_project"] = project_manager.current_path
        settings_repo.save(save_data)
        serial_manager.close()
        camera_manager.release_all()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
