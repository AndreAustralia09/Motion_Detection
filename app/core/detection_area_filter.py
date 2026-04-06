from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.core.detector_service import DetectionResult
from app.utils.geometry import point_in_polygon, polygon_bounds, polygon_is_simple

Point = tuple[int, int]
BBox = tuple[int, int, int, int]


def detection_area_is_valid(polygon: Sequence[Point]) -> bool:
    return 3 <= len(polygon) <= 20 and polygon_is_simple(polygon)


def prepare_detection_frame(frame, polygon: Sequence[Point]):
    if not detection_area_is_valid(polygon):
        return frame, (0, 0), None

    height, width = frame.shape[:2]
    bounds = polygon_bounds(polygon)
    if bounds is None:
        return frame, (0, 0), None

    x1, y1, x2, y2 = bounds
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2 + 1))
    y2 = max(y1 + 1, min(height, y2 + 1))
    if x1 == 0 and y1 == 0 and x2 == width and y2 == height:
        return frame, (0, 0), tuple(polygon)
    return frame[y1:y2, x1:x2], (x1, y1), tuple(polygon)


def remap_detection_to_frame(
    detection: DetectionResult,
    offset: tuple[int, int],
) -> DetectionResult:
    if offset == (0, 0):
        return detection
    dx, dy = offset
    x1, y1, x2, y2 = detection.bbox
    tx, ty = detection.trigger_point
    return replace(
        detection,
        bbox=(x1 + dx, y1 + dy, x2 + dx, y2 + dy),
        trigger_point=(tx + dx, ty + dy),
    )


def filter_detection_area_detections(
    detections: Sequence[DetectionResult],
    polygon: Sequence[Point],
) -> list[DetectionResult]:
    if not detection_area_is_valid(polygon):
        return list(detections)

    area = tuple(polygon)
    filtered: list[DetectionResult] = []
    for detection in detections:
        trigger_point = getattr(detection, "trigger_point", None)
        if trigger_point and point_in_polygon(trigger_point, area):
            filtered.append(detection)
    return filtered
