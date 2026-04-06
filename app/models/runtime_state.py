from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
import threading
from typing import TYPE_CHECKING, Callable, Dict, TypeVar

if TYPE_CHECKING:
    from app.core.detector_service import DetectionResult
    from app.models.events import RuntimeEvent, TriggerEvent


APP_STATES = {
    "no_project_loaded",
    "project_loaded",
    "starting",
    "running",
    "degraded",
    "stopped",
    "saving",
    "error",
}
CAMERA_STATES = {
    "inactive",
    "starting",
    "live",
    "reconnecting",
    "disconnected",
    "error",
}
SERIAL_STATES = {
    "disconnected",
    "connecting",
    "connected",
    "reconnecting",
    "error",
}


@dataclass
class PerformanceSettings:
    inference_resolution: int = 416
    max_detection_fps: float = 5.0
    background_camera_fps: float = 2.0
    show_fps_overlay: bool = True
    mirror_horizontal: bool = False

    def to_dict(self) -> dict:
        return {
            "inference_resolution": int(self.inference_resolution),
            "max_detection_fps": float(self.max_detection_fps),
            "background_camera_fps": float(self.background_camera_fps),
            "show_fps_overlay": bool(self.show_fps_overlay),
            "mirror_horizontal": bool(self.mirror_horizontal),
        }


@dataclass
class ZoneRuntimeState:
    desired_occupied: bool = False
    actual_occupied: bool = False
    pending_entry_since: float | None = None
    pending_exit_since: float | None = None


@dataclass(frozen=True)
class ZoneRuntimeSnapshot:
    desired_occupied: bool = False
    actual_occupied: bool = False
    pending_entry_since: float | None = None
    pending_exit_since: float | None = None


@dataclass
class CameraRuntimeState:
    camera_name: str = ""
    enabled: bool = True
    state: str = "inactive"
    frame_version: int = 0
    last_frame_ts: float | None = None
    fps: float = 0.0
    processing_ms: float = 0.0
    inference_ms: float = 0.0
    reconnect_attempts: int = 0
    active_zones: int = 0
    latest_detections: list["DetectionResult"] = field(default_factory=list)
    zone_occupancy: Dict[str, bool] = field(default_factory=dict)
    trigger_events: list["TriggerEvent"] = field(default_factory=list)
    zone_states: Dict[str, ZoneRuntimeState] = field(default_factory=dict)


@dataclass(frozen=True)
class CameraRuntimeSnapshot:
    camera_name: str = ""
    enabled: bool = True
    state: str = "inactive"
    frame_version: int = 0
    last_frame_ts: float | None = None
    fps: float = 0.0
    processing_ms: float = 0.0
    inference_ms: float = 0.0
    reconnect_attempts: int = 0
    active_zones: int = 0
    latest_detections: tuple["DetectionResult", ...] = ()
    zone_occupancy: dict[str, bool] = field(default_factory=dict)
    trigger_events: tuple["TriggerEvent", ...] = ()
    zone_states: dict[str, ZoneRuntimeSnapshot] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectDirtySnapshot:
    snapshot: str = ""
    is_dirty: bool = False
    reason: str = ""


_CameraUpdateResult = TypeVar("_CameraUpdateResult")
_DEFAULT_CAMERA_RUNTIME_SNAPSHOT = CameraRuntimeSnapshot()


@dataclass
class AppRuntimeState:
    camera_states: Dict[str, CameraRuntimeState] = field(default_factory=dict)
    performance_settings: PerformanceSettings = field(default_factory=PerformanceSettings)
    visible_camera_id: str | None = None
    app_state: str = "no_project_loaded"
    serial_state: str = "disconnected"
    serial_error: str = ""
    project_dirty: bool = False
    project_snapshot: str = ""
    project_dirty_reason: str = ""
    runtime_events: deque["RuntimeEvent"] = field(default_factory=lambda: deque(maxlen=200))
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def _ensure_camera_locked(self, camera_id: str) -> CameraRuntimeState:
        return self.camera_states.setdefault(camera_id, CameraRuntimeState())

    def _get_camera_locked(self, camera_id: str) -> CameraRuntimeState | None:
        return self.camera_states.get(camera_id)

    def update_camera_state(
        self,
        camera_id: str,
        updater: Callable[[CameraRuntimeState], _CameraUpdateResult],
    ) -> _CameraUpdateResult:
        with self._lock:
            return updater(self._ensure_camera_locked(camera_id))

    def get_camera_snapshot(self, camera_id: str) -> CameraRuntimeSnapshot:
        with self._lock:
            state = self._get_camera_locked(camera_id)
            if state is None:
                return _DEFAULT_CAMERA_RUNTIME_SNAPSHOT
            return self._camera_snapshot(state)

    def get_camera_snapshots(self, camera_ids: list[str]) -> dict[str, CameraRuntimeSnapshot]:
        with self._lock:
            return {
                camera_id: (
                    self._camera_snapshot(state)
                    if (state := self._get_camera_locked(camera_id)) is not None
                    else _DEFAULT_CAMERA_RUNTIME_SNAPSHOT
                )
                for camera_id in camera_ids
            }

    def get_camera_state(self, camera_id: str) -> str:
        with self._lock:
            state = self._get_camera_locked(camera_id)
            return state.state if state is not None else _DEFAULT_CAMERA_RUNTIME_SNAPSHOT.state

    def sync_camera_config(
        self,
        camera_id: str,
        *,
        camera_name: str,
        enabled: bool,
        active_zones: int,
    ) -> None:
        with self._lock:
            state = self._ensure_camera_locked(camera_id)
            state.camera_name = str(camera_name)
            state.enabled = bool(enabled)
            state.active_zones = int(active_zones)

    def prune_cameras(self, valid_camera_ids: set[str]) -> None:
        with self._lock:
            stale = [camera_id for camera_id in self.camera_states if camera_id not in valid_camera_ids]
            for camera_id in stale:
                self.camera_states.pop(camera_id, None)

    def update_performance_settings(
        self,
        *,
        inference_resolution: int | None = None,
        max_detection_fps: float | None = None,
        background_camera_fps: float | None = None,
        show_fps_overlay: bool | None = None,
        mirror_horizontal: bool | None = None,
    ) -> None:
        with self._lock:
            if inference_resolution is not None:
                self.performance_settings.inference_resolution = max(1, int(inference_resolution))
            if max_detection_fps is not None:
                self.performance_settings.max_detection_fps = max(0.1, float(max_detection_fps))
            if background_camera_fps is not None:
                self.performance_settings.background_camera_fps = max(0.1, float(background_camera_fps))
            if show_fps_overlay is not None:
                self.performance_settings.show_fps_overlay = bool(show_fps_overlay)
            if mirror_horizontal is not None:
                self.performance_settings.mirror_horizontal = bool(mirror_horizontal)

    def get_performance_settings(self) -> PerformanceSettings:
        with self._lock:
            return PerformanceSettings(**self.performance_settings.to_dict())

    def set_visible_camera(self, camera_id: str | None) -> None:
        with self._lock:
            self.visible_camera_id = camera_id

    def get_visible_camera(self) -> str | None:
        with self._lock:
            return self.visible_camera_id

    def set_app_state(self, state: str) -> None:
        normalized = str(state or "error").strip().lower()
        if normalized not in APP_STATES:
            normalized = "error"
        with self._lock:
            self.app_state = normalized

    def get_app_state(self) -> str:
        with self._lock:
            return self.app_state

    def set_serial_state(self, state: str, error: str = "") -> None:
        normalized = str(state or "error").strip().lower()
        if normalized not in SERIAL_STATES:
            normalized = "error"
        with self._lock:
            self.serial_state = normalized
            self.serial_error = str(error or "")

    def get_serial_state(self) -> tuple[str, str]:
        with self._lock:
            return self.serial_state, self.serial_error

    def set_camera_state(self, camera_id: str, state: str) -> None:
        normalized = str(state or "error").strip().lower()
        if normalized not in CAMERA_STATES:
            normalized = "error"
        with self._lock:
            self._ensure_camera_locked(camera_id).state = normalized

    def reset_project_dirty(self, snapshot: str) -> None:
        with self._lock:
            self.project_snapshot = str(snapshot or "")
            self.project_dirty = False
            self.project_dirty_reason = ""

    def get_project_snapshot(self) -> str:
        with self._lock:
            return self.project_snapshot

    def update_project_dirty(self, snapshot: str, *, reason: str = "") -> bool:
        with self._lock:
            normalized_snapshot = str(snapshot or "")
            self.project_dirty = normalized_snapshot != self.project_snapshot
            if self.project_dirty:
                self.project_dirty_reason = str(reason or self.project_dirty_reason or "Project changed")
            else:
                self.project_dirty_reason = ""
            return self.project_dirty

    def is_project_dirty(self) -> bool:
        with self._lock:
            return self.project_dirty

    def get_project_dirty_reason(self) -> str:
        with self._lock:
            return self.project_dirty_reason

    def get_project_dirty_state(self) -> ProjectDirtySnapshot:
        with self._lock:
            return ProjectDirtySnapshot(
                snapshot=str(self.project_snapshot),
                is_dirty=bool(self.project_dirty),
                reason=str(self.project_dirty_reason),
            )

    def restore_project_dirty_state(self, state: ProjectDirtySnapshot) -> None:
        with self._lock:
            self.project_snapshot = str(state.snapshot)
            self.project_dirty = bool(state.is_dirty)
            self.project_dirty_reason = str(state.reason)

    def record_runtime_event(
        self,
        name: str,
        *,
        level: str = "INFO",
        message: str = "",
        timestamp: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        from app.models.events import RuntimeEvent

        event = RuntimeEvent(
            name=str(name),
            level=str(level or "INFO"),
            message=str(message or name),
            timestamp=float(timestamp if timestamp is not None else time.time()),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self.runtime_events.append(event)

    def get_runtime_events(self) -> tuple["RuntimeEvent", ...]:
        with self._lock:
            return tuple(self.runtime_events)

    @staticmethod
    def _camera_snapshot(state: CameraRuntimeState) -> CameraRuntimeSnapshot:
        return CameraRuntimeSnapshot(
            camera_name=str(state.camera_name),
            enabled=bool(state.enabled),
            state=str(state.state),
            frame_version=int(state.frame_version),
            last_frame_ts=state.last_frame_ts,
            fps=float(state.fps),
            processing_ms=float(state.processing_ms),
            inference_ms=float(state.inference_ms),
            reconnect_attempts=int(state.reconnect_attempts),
            active_zones=int(state.active_zones),
            latest_detections=tuple(state.latest_detections),
            zone_occupancy=dict(state.zone_occupancy),
            trigger_events=tuple(state.trigger_events),
            zone_states={
                zone_id: ZoneRuntimeSnapshot(
                    desired_occupied=bool(zone_state.desired_occupied),
                    actual_occupied=bool(zone_state.actual_occupied),
                    pending_entry_since=zone_state.pending_entry_since,
                    pending_exit_since=zone_state.pending_exit_since,
                )
                for zone_id, zone_state in state.zone_states.items()
            },
        )
