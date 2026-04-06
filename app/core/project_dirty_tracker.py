from __future__ import annotations

import json
from dataclasses import dataclass

from app.models.project_model import ProjectModel


@dataclass(frozen=True)
class ProjectDirtyState:
    sections: dict[str, bool]

    def section(self, name: str) -> bool:
        return bool(self.sections.get(name, False))

    def tab_states(self) -> dict[str, bool]:
        return {
            "project": self.section("project_cameras"),
            "zones": self.section("zones"),
            "detection_setup": any(
                self.section(name)
                for name in ("detection_area", "ignore_areas")
            ),
            "cameras": any(
                self.section(name)
                for name in ("camera_detection", "detection_settings", "zone_timer_settings", "performance")
            ),
            "serial": any(
                self.section(name)
                for name in ("serial", "relays", "logging")
            ),
            "system_resources": False,
        }


class ProjectDirtyTracker:
    @staticmethod
    def serialize(project: ProjectModel) -> str:
        return json.dumps(project.to_dict(), sort_keys=True)

    @classmethod
    def build_state(cls, project: ProjectModel, baseline_snapshot: str) -> ProjectDirtyState:
        current_project = json.loads(cls.serialize(project))
        try:
            baseline_project = json.loads(baseline_snapshot) if baseline_snapshot else {}
        except json.JSONDecodeError:
            baseline_project = {}
        if not isinstance(baseline_project, dict):
            baseline_project = {}

        current_hardware = current_project.get("hardware", {}) if isinstance(current_project.get("hardware"), dict) else {}
        baseline_hardware = baseline_project.get("hardware", {}) if isinstance(baseline_project.get("hardware"), dict) else {}

        current_logging = {"debug_logging": bool(current_project.get("debug_logging", False))}
        baseline_logging = {"debug_logging": bool(baseline_project.get("debug_logging", False))}

        current_serial = {
            "com_port": current_hardware.get("com_port", ""),
            "serial_mode": current_hardware.get("serial_mode", "mock"),
            "auto_connect_serial": bool(current_hardware.get("auto_connect_serial", True)),
            "baud_rate": current_hardware.get("baud_rate", 9600),
            "timeout_ms": current_hardware.get("timeout_ms", 200),
            "retry_count": current_hardware.get("retry_count", 3),
            "mock_response_delay_ms": current_hardware.get("mock_response_delay_ms", 75),
            "mock_drop_rate": current_hardware.get("mock_drop_rate", 0.0),
            "mock_corruption_rate": current_hardware.get("mock_corruption_rate", 0.0),
        }
        baseline_serial = {
            "com_port": baseline_hardware.get("com_port", ""),
            "serial_mode": baseline_hardware.get("serial_mode", "mock"),
            "auto_connect_serial": bool(baseline_hardware.get("auto_connect_serial", True)),
            "baud_rate": baseline_hardware.get("baud_rate", 9600),
            "timeout_ms": baseline_hardware.get("timeout_ms", 200),
            "retry_count": baseline_hardware.get("retry_count", 3),
            "mock_response_delay_ms": baseline_hardware.get("mock_response_delay_ms", 75),
            "mock_drop_rate": baseline_hardware.get("mock_drop_rate", 0.0),
            "mock_corruption_rate": baseline_hardware.get("mock_corruption_rate", 0.0),
        }

        current_relays = {
            "relay_board_count": current_hardware.get("relay_board_count", 1),
            "relays_per_board": current_hardware.get("relays_per_board", 8),
        }
        baseline_relays = {
            "relay_board_count": baseline_hardware.get("relay_board_count", 1),
            "relays_per_board": baseline_hardware.get("relays_per_board", 8),
        }

        current_cameras = current_project.get("cameras", [])
        baseline_cameras = baseline_project.get("cameras", [])
        if not isinstance(current_cameras, list):
            current_cameras = []
        if not isinstance(baseline_cameras, list):
            baseline_cameras = []

        current_camera_detection = {
            str(camera.get("id", "")): {
                key: value
                for key, value in (camera.get("detection", {}) or {}).items()
                if key not in {"entry_delay_ms", "exit_delay_ms"}
            }
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_camera_detection = {
            str(camera.get("id", "")): {
                key: value
                for key, value in (camera.get("detection", {}) or {}).items()
                if key not in {"entry_delay_ms", "exit_delay_ms"}
            }
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }
        common_detection_ids = set(current_camera_detection) & set(baseline_camera_detection)
        detection_settings_dirty = any(
            current_camera_detection[camera_id] != baseline_camera_detection[camera_id]
            for camera_id in common_detection_ids
        )

        current_timer_settings = {
            str(camera.get("id", "")): {
                "entry_delay_ms": (camera.get("detection", {}) or {}).get("entry_delay_ms"),
                "exit_delay_ms": (camera.get("detection", {}) or {}).get("exit_delay_ms"),
            }
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_timer_settings = {
            str(camera.get("id", "")): {
                "entry_delay_ms": (camera.get("detection", {}) or {}).get("entry_delay_ms"),
                "exit_delay_ms": (camera.get("detection", {}) or {}).get("exit_delay_ms"),
            }
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }
        common_timer_ids = set(current_timer_settings) & set(baseline_timer_settings)
        timer_settings_dirty = any(
            current_timer_settings[camera_id] != baseline_timer_settings[camera_id]
            for camera_id in common_timer_ids
        )

        current_camera_zones = {
            str(camera.get("id", "")): camera.get("zones", [])
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_camera_zones = {
            str(camera.get("id", "")): camera.get("zones", [])
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }
        common_zone_ids = set(current_camera_zones) & set(baseline_camera_zones)
        zones_dirty = any(
            current_camera_zones[camera_id] != baseline_camera_zones[camera_id]
            for camera_id in common_zone_ids
        )

        current_camera_detection_areas = {
            str(camera.get("id", "")): camera.get("detection_area", [])
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_camera_detection_areas = {
            str(camera.get("id", "")): camera.get("detection_area", [])
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }
        common_detection_area_ids = set(current_camera_detection_areas) & set(baseline_camera_detection_areas)
        detection_area_dirty = any(
            current_camera_detection_areas[camera_id] != baseline_camera_detection_areas[camera_id]
            for camera_id in common_detection_area_ids
        )

        current_camera_ignore_areas = {
            str(camera.get("id", "")): camera.get("ignore_areas", [])
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_camera_ignore_areas = {
            str(camera.get("id", "")): camera.get("ignore_areas", [])
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }
        common_ignore_area_ids = set(current_camera_ignore_areas) & set(baseline_camera_ignore_areas)
        ignore_areas_dirty = any(
            current_camera_ignore_areas[camera_id] != baseline_camera_ignore_areas[camera_id]
            for camera_id in common_ignore_area_ids
        )

        current_camera_display = {
            str(camera.get("id", "")): {
                "id": camera.get("id", ""),
                "name": camera.get("name", ""),
                "source": camera.get("source", ""),
                "enabled": bool(camera.get("enabled", True)),
                "mirror_horizontal": bool(camera.get("mirror_horizontal", False)),
                "flip_vertical": bool(camera.get("flip_vertical", False)),
            }
            for camera in current_cameras
            if isinstance(camera, dict)
        }
        baseline_camera_display = {
            str(camera.get("id", "")): {
                "id": camera.get("id", ""),
                "name": camera.get("name", ""),
                "source": camera.get("source", ""),
                "enabled": bool(camera.get("enabled", True)),
                "mirror_horizontal": bool(camera.get("mirror_horizontal", False)),
                "flip_vertical": bool(camera.get("flip_vertical", False)),
            }
            for camera in baseline_cameras
            if isinstance(camera, dict)
        }

        return ProjectDirtyState(
            sections={
                "project_cameras": current_camera_display != baseline_camera_display,
                "camera_detection": current_camera_display != baseline_camera_display,
                "detection_settings": detection_settings_dirty,
                "zone_timer_settings": timer_settings_dirty,
                "performance": current_project.get("performance", {}) != baseline_project.get("performance", {}),
                "zones": zones_dirty,
                "zone_settings": False,
                "detection_area": detection_area_dirty,
                "ignore_areas": ignore_areas_dirty,
                "serial": current_serial != baseline_serial,
                "relays": current_relays != baseline_relays,
                "logging": current_logging != baseline_logging,
            }
        )

    @classmethod
    def section_states(cls, project: ProjectModel, baseline_snapshot: str) -> dict[str, bool]:
        return cls.build_state(project, baseline_snapshot).sections
