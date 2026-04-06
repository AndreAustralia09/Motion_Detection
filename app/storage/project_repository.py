from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from app.models.project_model import (
    CameraModel,
    DetectionSettings,
    HardwareModel,
    IgnoreAreaModel,
    PerformanceModel,
    ProjectModel,
    ZoneModel,
)
from app.utils.geometry import polygon_is_simple


class ProjectRepository:
    CURRENT_SCHEMA_VERSION = 1
    _MISSING = object()

    def load(self, path: str | Path) -> ProjectModel:
        file_path = Path(path)
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid project file: {file_path.name}") from exc

        if not isinstance(data, dict):
            raise ValueError(f"Invalid project file structure: {file_path.name}")

        performance_data = data.get("performance", {})
        legacy_mirror_horizontal = False
        if isinstance(performance_data, dict):
            legacy_mirror_horizontal = self._coerce_bool(performance_data.get("mirror_horizontal"), False)

        project = ProjectModel(
            schema_version=self._coerce_int(data.get("schema_version"), self.CURRENT_SCHEMA_VERSION, minimum=1),
            project_name=self._coerce_str(data.get("project_name"), "Untitled Project"),
            debug_logging=self._coerce_bool(data.get("debug_logging"), False),
            hardware=self._load_hardware(data.get("hardware", {})),
            performance=self._load_performance(performance_data),
            cameras=[],
        )
        cameras_data = data.get("cameras", [])
        if not isinstance(cameras_data, list):
            cameras_data = []
        for cam in cameras_data:
            if not isinstance(cam, dict):
                continue
            camera = CameraModel(
                id=self._coerce_str(cam.get("id"), ""),
                name=self._coerce_str(cam.get("name"), "Camera"),
                source=cam.get("source", 0),
                enabled=self._coerce_bool(cam.get("enabled"), True),
                mirror_horizontal=self._coerce_bool(cam.get("mirror_horizontal"), legacy_mirror_horizontal),
                flip_vertical=self._coerce_bool(cam.get("flip_vertical"), False),
                detection=self._load_detection(cam.get("detection", {})),
                zones=[],
                ignore_areas=[],
                detection_area=self._load_detection_area(cam.get("detection_area", [])),
            )
            if not camera.id:
                continue
            seen_zone_ids: set[str] = set()
            seen_ignore_area_ids: set[str] = set()
            zones_data = cam.get("zones", [])
            if not isinstance(zones_data, list):
                zones_data = []
            for zone in zones_data:
                if not isinstance(zone, dict):
                    continue
                zone_id = self._coerce_str(zone.get("id"), "")
                if not zone_id or zone_id in seen_zone_ids:
                    zone_id = self._generate_zone_id(camera.id, seen_zone_ids)
                seen_zone_ids.add(zone_id)
                camera.zones.append(
                    ZoneModel(
                        id=zone_id,
                        name=self._coerce_str(zone.get("name"), "Zone"),
                        polygon=self._load_polygon(zone.get("polygon", [])),
                        relay_id=self._coerce_optional_relay_id(zone.get("relay_id", self._MISSING), default=1),
                        allow_shared_relay=self._coerce_bool(zone.get("allow_shared_relay"), False),
                        enabled=self._coerce_bool(zone.get("enabled"), True),
                        trigger_mode=self._coerce_str(zone.get("trigger_mode"), "while_occupied"),
                    )
                )
            camera.zones = [zone for zone in camera.zones if zone.id]
            ignore_areas_data = cam.get("ignore_areas", [])
            if not isinstance(ignore_areas_data, list):
                ignore_areas_data = []
            for ignore_area in ignore_areas_data:
                if not isinstance(ignore_area, dict):
                    continue
                ignore_area_id = self._coerce_str(ignore_area.get("id"), "")
                if not ignore_area_id or ignore_area_id in seen_ignore_area_ids:
                    ignore_area_id = self._generate_ignore_area_id(camera.id, seen_ignore_area_ids)
                seen_ignore_area_ids.add(ignore_area_id)
                camera.ignore_areas.append(
                    IgnoreAreaModel(
                        id=ignore_area_id,
                        name=self._coerce_str(ignore_area.get("name"), "Ignore Area"),
                        polygon=self._load_ignore_area_polygon(ignore_area.get("polygon", [])),
                    )
                )
            camera.ignore_areas = [ignore_area for ignore_area in camera.ignore_areas if ignore_area.id]
            project.cameras.append(camera)
        return project

    def save(self, project: ProjectModel, path: str | Path) -> None:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = project.to_dict()
        payload["schema_version"] = self.CURRENT_SCHEMA_VERSION
        payload.pop("theme", None)
        payload.pop("start_minimized", None)
        payload.pop("auto_load_last_project", None)
        performance = payload.get("performance")
        if isinstance(performance, dict):
            performance.pop("show_fps_overlay", None)
        serialized = json.dumps(payload, indent=2)
        with NamedTemporaryFile("w", delete=False, dir=file_path.parent, encoding="utf-8", suffix=".tmp") as handle:
            handle.write(serialized)
            temp_path = Path(handle.name)
        temp_path.replace(file_path)

    def _load_hardware(self, data: object) -> HardwareModel:
        values = data if isinstance(data, dict) else {}
        return HardwareModel(
            com_port=self._coerce_str(values.get("com_port"), ""),
            serial_mode=self._coerce_serial_mode(values.get("serial_mode")),
            auto_connect_serial=self._coerce_bool(values.get("auto_connect_serial"), True),
            baud_rate=self._coerce_int(values.get("baud_rate"), 9600, minimum=1),
            timeout_ms=self._coerce_int(values.get("timeout_ms"), 200, minimum=1),
            retry_count=self._coerce_int(values.get("retry_count"), 3, minimum=0),
            mock_response_delay_ms=self._coerce_int(values.get("mock_response_delay_ms"), 75, minimum=0),
            mock_drop_rate=self._coerce_float(values.get("mock_drop_rate"), 0.0, minimum=0.0, maximum=1.0),
            mock_corruption_rate=self._coerce_float(values.get("mock_corruption_rate"), 0.0, minimum=0.0, maximum=1.0),
            relay_board_count=self._coerce_int(values.get("relay_board_count"), 1, minimum=1),
            relays_per_board=self._coerce_int(values.get("relays_per_board"), 8, minimum=1),
            connected=self._coerce_bool(values.get("connected"), False),
        )

    def _load_detection(self, data: object) -> DetectionSettings:
        values = data if isinstance(data, dict) else {}
        return DetectionSettings(
            mode=self._coerce_detection_mode(values.get("mode")),
            confidence_threshold=self._coerce_float(values.get("confidence_threshold"), 0.5, minimum=0.0, maximum=1.0),
            min_box_area=self._coerce_int(values.get("min_box_area"), 1200, minimum=0),
            entry_delay_ms=self._coerce_int(values.get("entry_delay_ms"), 200, minimum=0),
            exit_delay_ms=self._coerce_int(values.get("exit_delay_ms"), 300, minimum=0),
            trigger_point_offset=self._coerce_float(values.get("trigger_point_offset"), 0.95, minimum=0.0, maximum=1.0),
        )

    def _load_performance(self, data: object) -> PerformanceModel:
        values = data if isinstance(data, dict) else {}
        return PerformanceModel(
            inference_resolution=self._coerce_int(values.get("inference_resolution"), 640, minimum=1),
            max_detection_fps=self._coerce_float(values.get("max_detection_fps"), 5.0, minimum=0.1),
            background_camera_fps=self._coerce_float(values.get("background_camera_fps"), 1.0, minimum=0.1),
            mirror_horizontal=self._coerce_bool(values.get("mirror_horizontal"), False),
        )

    @staticmethod
    def _load_polygon(value: object) -> list[tuple[int, int]]:
        if not isinstance(value, list):
            return []
        points: list[tuple[int, int]] = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    points.append((int(item[0]), int(item[1])))
                except (TypeError, ValueError):
                    continue
        return points

    @classmethod
    def _load_detection_area(cls, value: object) -> list[tuple[int, int]]:
        polygon = cls._load_polygon(value)
        if len(polygon) < 3 or len(polygon) > 20 or not polygon_is_simple(polygon):
            return []
        return polygon

    @classmethod
    def _load_ignore_area_polygon(cls, value: object) -> list[tuple[int, int]]:
        polygon = cls._load_polygon(value)
        if len(polygon) < 3 or len(polygon) > 20 or not polygon_is_simple(polygon):
            return []
        return polygon

    @staticmethod
    def _coerce_str(value: object, default: str) -> str:
        text = str(value).strip() if value is not None else ""
        return text or default

    @staticmethod
    def _coerce_bool(value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(default)

    @staticmethod
    def _coerce_int(value: object, default: int, minimum: int | None = None) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError):
            result = int(default)
        if minimum is not None:
            result = max(minimum, result)
        return result

    @staticmethod
    def _coerce_optional_relay_id(value: object, *, default: int | None = 1) -> int | None:
        if value is ProjectRepository._MISSING:
            return default
        if value is None:
            return None
        try:
            relay_id = int(value)
        except (TypeError, ValueError):
            return default
        return relay_id if relay_id >= 1 else None

    @staticmethod
    def _coerce_float(
        value: object,
        default: float,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            result = float(default)
        if minimum is not None:
            result = max(minimum, result)
        if maximum is not None:
            result = min(maximum, result)
        return result

    @staticmethod
    def _coerce_serial_mode(value: object) -> str:
        mode = str(value or "mock").strip().lower()
        return mode if mode in {"mock", "real"} else "mock"

    @staticmethod
    def _coerce_detection_mode(value: object) -> str:
        mode = str(value or "person").strip().lower()
        return mode if mode in {"person", "face", "hands"} else "person"

    @staticmethod
    def _generate_zone_id(camera_id: str, existing_ids: set[str]) -> str:
        zone_id = f"{camera_id}_zone_{uuid4().hex[:8]}"
        while zone_id in existing_ids:
            zone_id = f"{camera_id}_zone_{uuid4().hex[:8]}"
        return zone_id

    @staticmethod
    def _generate_ignore_area_id(camera_id: str, existing_ids: set[str]) -> str:
        ignore_area_id = f"{camera_id}_ignore_{uuid4().hex[:8]}"
        while ignore_area_id in existing_ids:
            ignore_area_id = f"{camera_id}_ignore_{uuid4().hex[:8]}"
        return ignore_area_id
