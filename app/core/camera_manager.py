from __future__ import annotations

import cv2
import platform
import threading
from dataclasses import dataclass

try:
    from cv2_enumerate_cameras import enumerate_cameras
except Exception:  # pragma: no cover - optional dependency
    enumerate_cameras = None


@dataclass(frozen=True)
class CameraInfo:
    index: int
    friendly_name: str
    device_path: str = ""
    vid: str = ""
    pid: str = ""
    backend: int | None = None

    @property
    def source_label(self) -> str:
        return f"Source {self.index}"

    @property
    def display_label(self) -> str:
        name = self.friendly_name.strip()
        if name:
            return f"{name} ({self.source_label})"
        return self.source_label


class CameraSource:
    def __init__(self, source: int | str):
        self.source = source
        self.cap = None
        self.lock = threading.Lock()
        self._backend_name = "default"
        self.open()

    def open(self) -> bool:
        with self.lock:
            self._release_locked()
            for backend, backend_name in self._candidate_backends():
                cap = self._open_capture(backend)
                if cap is None:
                    continue
                self.cap = cap
                self._backend_name = backend_name
                return True
            self.cap = None
            self._backend_name = "unavailable"
            return False

    def read(self):
        with self.lock:
            if self.cap is None or not self.cap.isOpened():
                return None
            ret, frame = self.cap.read()
            if not ret:
                return None
            return frame

    def is_open(self) -> bool:
        with self.lock:
            return bool(self.cap and self.cap.isOpened())

    def reopen(self, source: int | str | None = None) -> bool:
        if source is not None:
            self.source = source
        return self.open()

    def get_frame_size(self) -> tuple[int, int] | None:
        with self.lock:
            if self.cap is None or not self.cap.isOpened():
                return None
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if width <= 0 or height <= 0:
                return None
            return width, height

    def release(self):
        with self.lock:
            self._release_locked()

    def _open_capture(self, backend: int | None):
        try:
            if backend is None:
                cap = cv2.VideoCapture(self.source)
            else:
                cap = cv2.VideoCapture(self.source, backend)
        except Exception:
            return None

        if not cap or not cap.isOpened():
            if cap:
                cap.release()
            return None

        ret, _frame = cap.read()
        if not ret:
            cap.release()
            return None
        return cap

    def _candidate_backends(self) -> list[tuple[int | None, str]]:
        if isinstance(self.source, int):
            if self.source < 0:
                return []
            if platform.system() == "Windows":
                # DSHOW is typically more stable for USB webcams on Windows.
                # If unavailable, fall back to MSMF and then OpenCV default.
                return [
                    (cv2.CAP_DSHOW, "dshow"),
                    (cv2.CAP_MSMF, "msmf"),
                    (None, "default"),
                ]
        return [(None, "default")]

    def _release_locked(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None


class CameraManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.sources: dict[str, CameraSource] = {}
        self._camera_info_cache: list[CameraInfo] = []
        self._camera_info_by_index: dict[str, CameraInfo] = {}
        self._configure_opencv_logging()

    def ensure_source(self, camera_id: str, source: int | str) -> CameraSource:
        with self._lock:
            camera_source = self.sources.get(camera_id)
            if camera_source is None:
                camera_source = CameraSource(source)
                self.sources[camera_id] = camera_source
            elif camera_source.source != source:
                camera_source.reopen(source)
            return camera_source

    def reopen_source(self, camera_id: str, source: int | str) -> bool:
        camera_source = self.ensure_source(camera_id, source)
        return camera_source.reopen(source)

    def release_source(self, camera_id: str) -> None:
        with self._lock:
            source = self.sources.pop(camera_id, None)
        if source is not None:
            source.release()

    def list_cameras(self, refresh: bool = False, max_tested: int = 5) -> list[CameraInfo]:
        with self._lock:
            if self._camera_info_cache and not refresh:
                return list(self._camera_info_cache)

        cameras = self._enumerate_cameras()
        if not cameras:
            cameras = self._probe_generic_cameras(max_tested=max_tested)

        with self._lock:
            self._camera_info_cache = list(cameras)
            self._camera_info_by_index = {str(camera.index): camera for camera in cameras}
            return list(self._camera_info_cache)

    def detect_available_sources(self, max_tested: int = 5) -> list[int]:
        return [camera.index for camera in self.list_cameras(refresh=True, max_tested=max_tested)]

    def get_camera_info(self, source: int | str, *, refresh: bool = False) -> CameraInfo | None:
        source_key = str(source).strip()
        if not source_key:
            return None
        with self._lock:
            if not refresh:
                cached = self._camera_info_by_index.get(source_key)
                if cached is not None:
                    return cached
        for camera in self.list_cameras(refresh=refresh):
            if str(camera.index) == source_key:
                return camera
        return None

    def get_friendly_name(self, source: int | str, *, refresh: bool = False) -> str | None:
        info = self.get_camera_info(source, refresh=refresh)
        if info is None:
            return None
        return info.friendly_name.strip() or None

    def describe_source(self, source: int | str, *, refresh: bool = False) -> str:
        info = self.get_camera_info(source, refresh=refresh)
        source_label = f"Source {source}"
        if info is None:
            return source_label
        friendly_name = info.friendly_name.strip()
        if friendly_name:
            return f"{friendly_name} | {source_label}"
        return source_label

    def _probe_generic_cameras(self, max_tested: int = 5) -> list[CameraInfo]:
        available: list[int] = []
        for i in range(max_tested):
            probe = CameraSource(i)
            try:
                if probe.is_open():
                    available.append(i)
            finally:
                probe.release()
        return [
            CameraInfo(
                index=index,
                friendly_name=f"Camera {index + 1}",
            )
            for index in available
        ]

    def _enumerate_cameras(self) -> list[CameraInfo]:
        if platform.system() != "Windows" or enumerate_cameras is None:
            return []

        candidates: list[CameraInfo] = []
        seen_indices: set[int] = set()
        for backend in (cv2.CAP_MSMF, cv2.CAP_DSHOW):
            try:
                enumerated = enumerate_cameras(backend)
            except Exception:
                continue
            for item in enumerated:
                index = getattr(item, "index", None)
                if not isinstance(index, int) or index < 0 or index in seen_indices:
                    continue
                seen_indices.add(index)
                vid = getattr(item, "vid", "")
                pid = getattr(item, "pid", "")
                candidates.append(
                    CameraInfo(
                        index=index,
                        friendly_name=str(getattr(item, "name", "") or "").strip(),
                        device_path=str(getattr(item, "path", "") or "").strip(),
                        vid=f"{int(vid):04X}" if isinstance(vid, int) else str(vid or "").strip(),
                        pid=f"{int(pid):04X}" if isinstance(pid, int) else str(pid or "").strip(),
                        backend=int(getattr(item, "backend", backend)),
                    )
                )
        return candidates

    def get_frame_size(self, camera_id: str) -> tuple[int, int] | None:
        with self._lock:
            source = self.sources.get(camera_id)
        if source is None:
            return None
        return source.get_frame_size()

    def release_all(self) -> None:
        with self._lock:
            sources = list(self.sources.values())
            self.sources.clear()
        for source in sources:
            source.release()

    def _configure_opencv_logging(self) -> None:
        if platform.system() != "Windows":
            return
        set_log_level = getattr(cv2, "setLogLevel", None)
        log_level_error = getattr(cv2, "LOG_LEVEL_ERROR", None)
        if callable(set_log_level) and log_level_error is not None:
            try:
                set_log_level(log_level_error)
            except Exception:
                pass
