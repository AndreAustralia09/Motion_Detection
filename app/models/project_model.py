from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Tuple


Point = Tuple[int, int]


@dataclass
class DetectionSettings:
    mode: str = "person"
    confidence_threshold: float = 0.5
    min_box_area: int = 1200
    entry_delay_ms: int = 200
    exit_delay_ms: int = 300
    trigger_point_offset: float = 0.95


@dataclass
class ZoneModel:
    id: str
    name: str
    polygon: List[Point] = field(default_factory=list)
    relay_id: int | None = 1
    allow_shared_relay: bool = False
    enabled: bool = True
    trigger_mode: str = "while_occupied"


@dataclass
class IgnoreAreaModel:
    id: str
    name: str
    polygon: List[Point] = field(default_factory=list)


@dataclass
class CameraModel:
    id: str
    name: str
    source: int | str
    enabled: bool = True
    mirror_horizontal: bool = False
    flip_vertical: bool = False
    detection: DetectionSettings = field(default_factory=DetectionSettings)
    zones: List[ZoneModel] = field(default_factory=list)
    ignore_areas: List[IgnoreAreaModel] = field(default_factory=list)
    detection_area: List[Point] = field(default_factory=list)


@dataclass
class HardwareModel:
    com_port: str = ""
    serial_mode: str = "mock"
    auto_connect_serial: bool = True
    baud_rate: int = 9600
    timeout_ms: int = 200
    retry_count: int = 3
    mock_response_delay_ms: int = 75
    mock_drop_rate: float = 0.0
    mock_corruption_rate: float = 0.0
    relay_board_count: int = 1
    relays_per_board: int = 8
    connected: bool = False

    @property
    def total_relays(self) -> int:
        return max(1, self.relay_board_count) * max(1, self.relays_per_board)


@dataclass
class PerformanceModel:
    inference_resolution: int = 416
    max_detection_fps: float = 5.0
    background_camera_fps: float = 2.0
    mirror_horizontal: bool = False


@dataclass
class ProjectModel:
    schema_version: int = 1
    project_name: str = "Untitled Project"
    debug_logging: bool = False
    cameras: List[CameraModel] = field(default_factory=list)
    hardware: HardwareModel = field(default_factory=HardwareModel)
    performance: PerformanceModel = field(default_factory=PerformanceModel)

    def to_dict(self) -> dict:
        return asdict(self)
