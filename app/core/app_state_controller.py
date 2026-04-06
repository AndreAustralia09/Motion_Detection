from __future__ import annotations

from typing import Iterable

from app.models.project_model import ProjectModel
from app.models.runtime_state import AppRuntimeState


class AppStateController:
    def derive_app_state(self, *, project: ProjectModel, runtime_state: AppRuntimeState) -> str:
        enabled_cameras = [camera for camera in project.cameras if camera.enabled]
        serial_state, serial_error = runtime_state.get_serial_state()

        if not project.cameras:
            next_state = "no_project_loaded"
        elif serial_state in {"reconnecting", "error"}:
            next_state = "degraded"
        elif self._has_camera_state(enabled_cameras, runtime_state, {"disconnected", "reconnecting", "error"}):
            next_state = "degraded"
        elif self._has_camera_state(enabled_cameras, runtime_state, {"live"}):
            next_state = "running"
        elif enabled_cameras:
            next_state = "starting"
        else:
            next_state = "project_loaded"

        if serial_error and serial_state == "error":
            return "degraded"
        return next_state

    @staticmethod
    def _has_camera_state(cameras: Iterable[object], runtime_state: AppRuntimeState, target_states: set[str]) -> bool:
        return any(runtime_state.get_camera_state(camera.id) in target_states for camera in cameras)
