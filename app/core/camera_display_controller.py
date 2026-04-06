from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from app.core.camera_pipeline import CameraPipeline
from app.core.zone_coordination_controller import ZoneSelectionResult
from app.models.project_model import CameraModel, ZoneModel
from app.models.runtime_state import AppRuntimeState


@dataclass(frozen=True)
class CameraTabRefreshPlan:
    tab_labels: tuple[str, ...]
    selected_camera: CameraModel | None
    selected_index: int


@dataclass(frozen=True)
class CameraSelectionPlan:
    camera: CameraModel
    camera_id: str
    preserved_zone_id: str | None


@dataclass(frozen=True)
class ZoneCameraSelectionPlan:
    camera: CameraModel | None
    camera_id: str | None
    camera_index: int
    selected_zone_id: str | None
    should_switch_tab: bool
    should_apply_camera_selection: bool


@dataclass(frozen=True)
class CameraDisplayViewState:
    show_overlay: bool
    mirror_horizontal: bool
    flip_vertical: bool
    simulation_notice: str


@dataclass(frozen=True)
class CameraDisplayRefreshPlan:
    camera_id: str
    frame: Any | None
    frame_updated: bool
    frame_version: int
    detections: tuple[Any, ...]
    occupancy: dict[str, bool]
    camera_state: str
    fps: float
    inference_ms: float
    show_overlay: bool
    mirror_horizontal: bool
    flip_vertical: bool
    simulation_notice: str


class CameraDisplayController:
    def __init__(
        self,
        *,
        camera_pipeline: CameraPipeline,
        runtime_state: AppRuntimeState,
        get_active_cameras: Callable[[], Sequence[CameraModel]],
        find_zone_by_id: Callable[[str | None], tuple[CameraModel | None, ZoneModel | None]],
        display_camera_name: Callable[[CameraModel], str],
        get_serial_mode: Callable[[], str],
    ) -> None:
        self.camera_pipeline = camera_pipeline
        self.runtime_state = runtime_state
        self._get_active_cameras = get_active_cameras
        self._find_zone_by_id = find_zone_by_id
        self._display_camera_name = display_camera_name
        self._get_serial_mode = get_serial_mode

    def build_tab_refresh_plan(self, current_camera_id: str | None) -> CameraTabRefreshPlan:
        active_cameras = tuple(self._get_active_cameras())
        if not active_cameras:
            return CameraTabRefreshPlan(tab_labels=(), selected_camera=None, selected_index=-1)

        selected_camera = next(
            (camera for camera in active_cameras if camera.id == current_camera_id),
            active_cameras[0],
        )
        selected_index = next(
            (index for index, camera in enumerate(active_cameras) if camera.id == selected_camera.id),
            0,
        )
        return CameraTabRefreshPlan(
            tab_labels=tuple(self._display_camera_name(camera) for camera in active_cameras),
            selected_camera=selected_camera,
            selected_index=selected_index,
        )

    def build_tab_change_selection(self, index: int, selected_zone_id: str | None) -> CameraSelectionPlan | None:
        active_cameras = tuple(self._get_active_cameras())
        if not (0 <= index < len(active_cameras)):
            return None
        return self.build_camera_selection_plan(active_cameras[index], selected_zone_id)

    def build_camera_selection_plan(
        self,
        camera: CameraModel,
        selected_zone_id: str | None,
    ) -> CameraSelectionPlan:
        preserved_zone_id = None
        if selected_zone_id:
            selected_camera, selected_zone = self._find_zone_by_id(selected_zone_id)
            if selected_camera and selected_zone and selected_camera.id == camera.id:
                preserved_zone_id = selected_zone.id
        return CameraSelectionPlan(
            camera=camera,
            camera_id=camera.id,
            preserved_zone_id=preserved_zone_id,
        )

    def current_camera(self, current_camera_id: str | None) -> CameraModel | None:
        return next(
            (camera for camera in self._get_active_cameras() if camera.id == current_camera_id),
            None,
        )

    def build_zone_camera_selection(
        self,
        selection: ZoneSelectionResult,
        *,
        current_tab_index: int,
    ) -> ZoneCameraSelectionPlan:
        if selection.camera is None or selection.zone is None:
            return ZoneCameraSelectionPlan(
                camera=None,
                camera_id=None,
                camera_index=-1,
                selected_zone_id=None,
                should_switch_tab=False,
                should_apply_camera_selection=False,
            )

        should_switch_tab = selection.camera_index >= 0 and selection.camera_index != current_tab_index
        return ZoneCameraSelectionPlan(
            camera=selection.camera,
            camera_id=selection.camera.id,
            camera_index=selection.camera_index,
            selected_zone_id=selection.selected_zone_id,
            should_switch_tab=should_switch_tab,
            should_apply_camera_selection=selection.camera_index >= 0 and not should_switch_tab,
        )

    def build_display_refresh_plan(
        self,
        *,
        current_camera_id: str | None,
        force: bool,
        last_frame_version: int | None,
        view_state: CameraDisplayViewState,
    ) -> CameraDisplayRefreshPlan | None:
        camera = self.current_camera(current_camera_id)
        if camera is None:
            return None

        snapshot = self.camera_pipeline.get_camera_snapshot(
            camera.id,
            last_frame_version=None if force else last_frame_version,
        )
        performance_settings = self.runtime_state.get_performance_settings()
        show_overlay = performance_settings.show_fps_overlay
        mirror_horizontal = bool(camera.mirror_horizontal)
        flip_vertical = bool(getattr(camera, "flip_vertical", False))
        simulation_notice = ""
        if self._get_serial_mode() == "mock":
            simulation_notice = "COM Port - Simulation Mode (No Hardware Connected)"

        if (
            not force
            and not snapshot.frame_updated
            and view_state.show_overlay == show_overlay
            and view_state.mirror_horizontal == mirror_horizontal
            and view_state.flip_vertical == flip_vertical
            and view_state.simulation_notice == simulation_notice
        ):
            return None

        return CameraDisplayRefreshPlan(
            camera_id=camera.id,
            frame=snapshot.frame if snapshot.frame_updated else None,
            frame_updated=snapshot.frame_updated,
            frame_version=snapshot.frame_version,
            detections=snapshot.detections,
            occupancy=snapshot.occupancy,
            camera_state=snapshot.state,
            fps=snapshot.fps,
            inference_ms=snapshot.inference_ms,
            show_overlay=show_overlay,
            mirror_horizontal=mirror_horizontal,
            flip_vertical=flip_vertical,
            simulation_notice=simulation_notice,
        )
