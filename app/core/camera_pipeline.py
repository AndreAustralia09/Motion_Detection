from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from app.core.camera_manager import CameraManager
from app.core.detection_area_filter import (
    filter_detection_area_detections,
    prepare_detection_frame,
    remap_detection_to_frame,
)
from app.core.detector_service import DetectionResult, DetectorService
from app.core.ignore_area_filter import filter_ignored_detections
from app.core.occupancy_engine import OccupancyEngine
from app.core.trigger_engine import TriggerEngine
from app.models.events import TriggerEvent
from app.models.project_model import CameraModel
from app.models.runtime_state import AppRuntimeState


CAMERA_RETRY_INTERVAL_S = 2.0
IDLE_SLEEP_S = 0.01


@dataclass
class CameraSnapshot:
    frame: Any | None
    frame_updated: bool
    frame_version: int
    detections: tuple[DetectionResult, ...]
    occupancy: dict[str, bool]
    state: str
    fps: float
    processing_ms: float
    inference_ms: float
    reconnect_attempts: int
    active_zones: int


class _CameraWorker(threading.Thread):
    def __init__(
        self,
        camera: CameraModel,
        pipeline: "CameraPipeline",
    ) -> None:
        super().__init__(name=f"CameraWorker-{camera.id}", daemon=True)
        self.pipeline = pipeline
        self._camera = camera
        self._camera_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_retry_ts = 0.0
        self._was_live = False
        self._last_detection_ts = 0.0

    def update_camera(self, camera: CameraModel) -> None:
        with self._camera_lock:
            self._camera = camera

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            camera = self._get_camera()
            if not camera.enabled:
                self.pipeline._set_camera_disconnected(camera.id, "inactive")
                self.pipeline.camera_manager.release_source(camera.id)
                time.sleep(0.2)
                continue

            camera_state = self.pipeline.runtime_state.get_camera_snapshot(camera.id)
            if camera_state.state in {"inactive", "starting", "disconnected"}:
                self.pipeline._set_camera_state(camera.id, "starting")

            source = self.pipeline.camera_manager.ensure_source(camera.id, camera.source)
            frame = source.read()
            now = time.monotonic()

            if frame is None:
                next_state = "reconnecting" if self._was_live else "starting"
                self.pipeline._set_camera_disconnected(camera.id, next_state)
                self._process_empty_frame(camera, now)

                if now - self._last_retry_ts >= CAMERA_RETRY_INTERVAL_S:
                    self._last_retry_ts = now
                    self.pipeline._note_reconnect_attempt(camera.id)
                    self.pipeline.camera_manager.reopen_source(camera.id, camera.source)
                    if self.pipeline.camera_manager.ensure_source(camera.id, camera.source).is_open():
                        self.pipeline._set_camera_state(camera.id, "reconnecting")

                self._was_live = False
                time.sleep(0.1)
                continue

            detections, occupancy, events, processing_ms, inference_ms = self._run_frame_processing(
                camera=camera,
                frame=frame,
                current_time=now,
            )

            self.pipeline._commit_live_frame(
                camera=camera,
                frame=frame,
                detections=detections,
                occupancy=occupancy,
                trigger_events=events,
                frame_time=now,
                processing_ms=processing_ms,
                inference_ms=inference_ms,
            )
            self._last_retry_ts = 0.0
            self._was_live = True
            time.sleep(IDLE_SLEEP_S)

        camera = self._get_camera()
        self.pipeline.camera_manager.release_source(camera.id)

    def _get_camera(self) -> CameraModel:
        with self._camera_lock:
            return self._camera

    def _process_empty_frame(self, camera: CameraModel, current_time: float) -> None:
        occupancy = {zone.id: False for zone in camera.zones if zone.enabled}
        events = self.pipeline.trigger_engine.update(
            camera_id=camera.id,
            zones=camera.zones,
            occupancy=occupancy,
            current_time=current_time,
            detection_settings=camera.detection,
        )
        self.pipeline._commit_no_frame(camera=camera, occupancy=occupancy, trigger_events=events)

    def _run_frame_processing(
        self,
        *,
        camera: CameraModel,
        frame,
        current_time: float,
    ) -> tuple[list[DetectionResult], dict[str, bool], list[TriggerEvent], float, float]:
        visible_camera_id = self.pipeline.runtime_state.get_visible_camera()
        performance = self.pipeline.runtime_state.get_performance_settings()
        target_fps = (
            performance.max_detection_fps
            if camera.id == visible_camera_id
            else performance.background_camera_fps
        )
        min_interval = 1.0 / max(0.1, float(target_fps))

        camera_state = self.pipeline.runtime_state.get_camera_snapshot(camera.id)
        reuse_previous = (
            self._last_detection_ts > 0.0
            and (current_time - self._last_detection_ts) < min_interval
        )
        if reuse_previous:
            return (
                list(camera_state.latest_detections),
                dict(camera_state.zone_occupancy),
                [],
                0.0,
                camera_state.inference_ms,
            )

        started_at = time.perf_counter()
        inference_frame, detection_offset, detection_polygon = prepare_detection_frame(
            frame,
            getattr(camera, "detection_area", ()),
        )
        detections = self.pipeline.detector.detect(
            inference_frame,
            camera.detection,
            inference_resolution=performance.inference_resolution,
        )
        detections = [
            remap_detection_to_frame(detection, detection_offset)
            for detection in detections
        ]
        detections = filter_detection_area_detections(detections, detection_polygon or ())
        detections = filter_ignored_detections(
            detections,
            getattr(camera, "ignore_areas", ()),
        )
        inference_ms = (time.perf_counter() - started_at) * 1000.0

        occupancy = self.pipeline.occupancy_engine.evaluate(camera.zones, detections)
        events = self.pipeline.trigger_engine.update(
            camera_id=camera.id,
            zones=camera.zones,
            occupancy=occupancy,
            current_time=current_time,
            detection_settings=camera.detection,
        )
        processing_ms = (time.perf_counter() - started_at) * 1000.0
        self._last_detection_ts = current_time
        return detections, occupancy, events, processing_ms, inference_ms


class CameraPipeline:
    def __init__(
        self,
        camera_manager: CameraManager,
        detector: DetectorService,
        occupancy_engine: OccupancyEngine,
        trigger_engine: TriggerEngine,
        runtime_state: AppRuntimeState,
    ) -> None:
        self.camera_manager = camera_manager
        self.detector = detector
        self.occupancy_engine = occupancy_engine
        self.trigger_engine = trigger_engine
        self.runtime_state = runtime_state
        self._lock = threading.Lock()
        self._latest_frames: dict[str, Any | None] = {}
        self._pending_events: deque[TriggerEvent] = deque()
        self._workers: dict[str, _CameraWorker] = {}

    def sync_cameras(self, cameras: list[CameraModel]) -> None:
        valid_ids = {camera.id for camera in cameras}

        with self._lock:
            stale_ids = [camera_id for camera_id in self._workers if camera_id not in valid_ids]
            stale_workers = []
            for camera_id in stale_ids:
                worker = self._workers.pop(camera_id)
                worker.stop()
                stale_workers.append(worker)
                self._latest_frames.pop(camera_id, None)

        for camera_id in stale_ids:
            self.camera_manager.release_source(camera_id)
        for worker in stale_workers:
            worker.join(timeout=0.5)

        for camera in cameras:
            self.runtime_state.sync_camera_config(
                camera.id,
                camera_name=camera.name,
                enabled=camera.enabled,
                active_zones=sum(1 for zone in camera.zones if zone.enabled),
            )
            worker = self._workers.get(camera.id)
            if worker is None:
                self._set_camera_state(camera.id, "starting")
                worker = _CameraWorker(camera=camera, pipeline=self)
                with self._lock:
                    self._workers[camera.id] = worker
                worker.start()
            else:
                worker.update_camera(camera)

        self.runtime_state.prune_cameras(valid_ids)

    def stop_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop()
        for worker in workers:
            worker.join(timeout=1.0)
        self.camera_manager.release_all()

    def get_camera_snapshot(self, camera_id: str, last_frame_version: int | None = None) -> CameraSnapshot:
        with self._lock:
            state = self.runtime_state.get_camera_snapshot(camera_id)
            frame = None
            frame_updated = last_frame_version != state.frame_version
            if frame_updated:
                frame = self._latest_frames.get(camera_id)
            return CameraSnapshot(
                frame=frame,
                frame_updated=frame_updated,
                frame_version=state.frame_version,
                detections=tuple(state.latest_detections),
                occupancy=dict(state.zone_occupancy),
                state=state.state,
                fps=state.fps,
                processing_ms=state.processing_ms,
                inference_ms=state.inference_ms,
                reconnect_attempts=state.reconnect_attempts,
                active_zones=state.active_zones,
            )

    def drain_trigger_events(self) -> list[TriggerEvent]:
        with self._lock:
            events = list(self._pending_events)
            self._pending_events.clear()
            return events

    def remove_zone_runtime(self, camera_id: str, zone_id: str) -> None:
        with self._lock:
            def _remove_zone(state) -> None:
                state.zone_states.pop(zone_id, None)
                state.zone_occupancy.pop(zone_id, None)
                state.trigger_events = [
                    event for event in state.trigger_events if event.zone_id != zone_id
                ]

            self.runtime_state.update_camera_state(camera_id, _remove_zone)
            self._pending_events = deque(
                event for event in self._pending_events if event.zone_id != zone_id
            )

    def _commit_live_frame(
        self,
        camera: CameraModel,
        frame,
        detections: list[DetectionResult],
        occupancy: dict[str, bool],
        trigger_events: list[TriggerEvent],
        frame_time: float,
        processing_ms: float,
        inference_ms: float,
    ) -> None:
        with self._lock:
            def _update_state(state) -> None:
                previous_ts = state.last_frame_ts
                if previous_ts is not None and frame_time > previous_ts:
                    current_fps = 1.0 / max(1e-6, frame_time - previous_ts)
                    state.fps = current_fps if state.fps <= 0 else (state.fps * 0.8) + (current_fps * 0.2)
                state.last_frame_ts = frame_time
                state.latest_detections = list(detections)
                state.zone_occupancy = dict(occupancy)
                state.trigger_events = list(trigger_events)
                state.processing_ms = processing_ms
                state.inference_ms = inference_ms
                state.state = "live"
                state.enabled = camera.enabled
                state.camera_name = camera.name
                state.active_zones = sum(1 for zone in camera.zones if zone.enabled)
                state.frame_version += 1

            self.runtime_state.update_camera_state(camera.id, _update_state)
            self._latest_frames[camera.id] = frame
            self._pending_events.extend(trigger_events)

    def _commit_no_frame(
        self,
        camera: CameraModel,
        occupancy: dict[str, bool],
        trigger_events: list[TriggerEvent],
    ) -> None:
        with self._lock:
            state = self.runtime_state.get_camera_snapshot(camera.id)
            had_detections = bool(state.latest_detections)
            occupancy_changed = state.zone_occupancy != occupancy

            def _update_state(mutable_state) -> None:
                mutable_state.latest_detections = []
                mutable_state.zone_occupancy = dict(occupancy)
                mutable_state.trigger_events = list(trigger_events)
                mutable_state.processing_ms = 0.0
                mutable_state.inference_ms = 0.0
                mutable_state.enabled = camera.enabled
                mutable_state.camera_name = camera.name
                mutable_state.active_zones = sum(1 for zone in camera.zones if zone.enabled)
                if trigger_events or had_detections or occupancy_changed:
                    mutable_state.frame_version += 1

            self.runtime_state.update_camera_state(camera.id, _update_state)
            self._latest_frames[camera.id] = None
            self._pending_events.extend(trigger_events)

    def _set_camera_disconnected(self, camera_id: str, state_name: str) -> None:
        with self._lock:
            state = self.runtime_state.get_camera_snapshot(camera_id)
            previous_state = state.state
            had_frame = self._latest_frames.get(camera_id) is not None

            def _update_state(mutable_state) -> None:
                mutable_state.state = state_name
                mutable_state.last_frame_ts = None
                mutable_state.fps = 0.0
                mutable_state.processing_ms = 0.0
                mutable_state.inference_ms = 0.0
                if previous_state != state_name or had_frame:
                    mutable_state.frame_version += 1

            self.runtime_state.update_camera_state(camera_id, _update_state)
            self._latest_frames[camera_id] = None

    def _set_camera_state(self, camera_id: str, state_name: str) -> None:
        self.runtime_state.set_camera_state(camera_id, state_name)

    def _note_reconnect_attempt(self, camera_id: str) -> None:
        with self._lock:
            def _update_state(state) -> None:
                state.reconnect_attempts += 1
                if state.state != "starting":
                    state.state = "reconnecting"

            self.runtime_state.update_camera_state(camera_id, _update_state)
