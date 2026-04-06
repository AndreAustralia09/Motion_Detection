from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.core.camera_manager import CameraManager
from app.core.relay_manager import RelayManager, RelayState
from app.core.serial_manager import SerialManager
from app.models.project_model import CameraModel, ProjectModel
from app.models.runtime_state import AppRuntimeState


@dataclass(frozen=True)
class StatusBarPlan:
    summary_text: str
    relay_states: tuple[RelayState, ...]
    relays_per_board: int


@dataclass(frozen=True)
class SystemResourcesPlan:
    cpu_percent: str
    cpu_summary_text: str
    memory: str
    app_state: str
    active_cameras: int
    active_zones: int
    serial_state: str
    inference_device: str
    per_camera_lines: tuple[str, ...]


class StatusSummaryController:
    def __init__(
        self,
        *,
        runtime_state: AppRuntimeState,
        serial_manager: SerialManager,
        relay_manager: RelayManager,
        camera_manager: CameraManager,
        get_project: Callable[[], ProjectModel],
        display_camera_name: Callable[[CameraModel], str],
    ) -> None:
        self.runtime_state = runtime_state
        self.serial_manager = serial_manager
        self.relay_manager = relay_manager
        self.camera_manager = camera_manager
        self._get_project = get_project
        self._display_camera_name = display_camera_name

    def build_status_bar_plan(self, *, cpu_summary_text: str) -> StatusBarPlan:
        project = self._get_project()
        active_cameras = [camera for camera in project.cameras if camera.enabled]
        camera_count = len(active_cameras)
        active_zones = sum(1 for camera in active_cameras for zone in camera.zones if zone.enabled)
        app_state_text = self.runtime_state.get_app_state().title()
        app_state_note = self._build_app_state_note(active_cameras)
        if app_state_note:
            app_state_text = f"{app_state_text} ({app_state_note})"
        return StatusBarPlan(
            summary_text=(
                f"State {app_state_text} | CPU {cpu_summary_text} | "
                f"Active Cameras {camera_count} | Active Zones {active_zones} | "
                f"Serial {self.serial_manager.get_live_state().status_text}"
            ),
            relay_states=tuple(self.relay_manager.get_states()),
            relays_per_board=project.hardware.relays_per_board,
        )

    def build_system_resources_plan(
        self,
        *,
        cpu_percent: str,
        memory: str,
        inference_device: str,
    ) -> SystemResourcesPlan:
        project = self._get_project()
        cameras = project.cameras
        active_project_cameras = [camera for camera in cameras if camera.enabled]
        camera_states = self.runtime_state.get_camera_snapshots([camera.id for camera in cameras])
        per_camera_lines = []
        for camera in cameras:
            state = camera_states[camera.id]
            frame_size = self.camera_manager.get_frame_size(camera.id)
            resolution_text = (
                f"{frame_size[0]} x {frame_size[1]}"
                if frame_size is not None
                else "Resolution unavailable"
            )
            source_text = self.camera_manager.describe_source(camera.source)
            mode_text = camera.detection.mode.title()
            state_text = "Inactive" if not camera.enabled else state.state.title()
            per_camera_lines.append(
                f"{self._display_camera_name(camera)}\n"
                f"{resolution_text} | {state_text} | {mode_text}\n"
                f"FPS: {state.fps:.1f} | Infer: {state.inference_ms:.0f} ms | {source_text}"
            )

        return SystemResourcesPlan(
            cpu_percent=cpu_percent,
            cpu_summary_text=cpu_percent,
            memory=memory,
            app_state=self.runtime_state.get_app_state().title(),
            active_cameras=len(active_project_cameras),
            active_zones=sum(1 for camera in active_project_cameras for zone in camera.zones if zone.enabled),
            serial_state=self.serial_manager.get_live_state().status_text,
            inference_device=inference_device,
            per_camera_lines=tuple(per_camera_lines),
        )

    def _build_app_state_note(self, active_cameras: Sequence[CameraModel]) -> str:
        app_state = self.runtime_state.get_app_state()
        serial_state, _serial_error = self.runtime_state.get_serial_state()
        if app_state == "starting" and active_cameras:
            return "warming up detector"
        if app_state != "degraded":
            return ""
        if serial_state == "reconnecting":
            return "serial reconnecting"
        if serial_state == "error":
            return "serial error"

        camera_states = self.runtime_state.get_camera_snapshots([camera.id for camera in active_cameras])
        reconnecting_count = sum(
            1
            for camera in active_cameras
            if camera_states[camera.id].state == "reconnecting"
        )
        if reconnecting_count == 1:
            return "camera reconnecting"
        if reconnecting_count > 1:
            return "cameras reconnecting"

        disconnected_count = sum(
            1
            for camera in active_cameras
            if camera_states[camera.id].state in {"disconnected", "error"}
        )
        if disconnected_count == 1:
            return "camera unavailable"
        if disconnected_count > 1:
            return "cameras unavailable"
        return ""
