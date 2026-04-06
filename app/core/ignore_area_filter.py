from __future__ import annotations

from collections.abc import Sequence

from app.core.detector_service import DetectionResult
from app.models.project_model import IgnoreAreaModel
from app.utils.geometry import point_in_polygon


def filter_ignored_detections(
    detections: Sequence[DetectionResult],
    ignore_areas: Sequence[IgnoreAreaModel],
) -> list[DetectionResult]:
    active_ignore_polygons = [
        tuple(area.polygon)
        for area in ignore_areas
        if len(area.polygon) >= 3
    ]
    if not active_ignore_polygons:
        return list(detections)

    filtered: list[DetectionResult] = []
    for detection in detections:
        trigger_point = getattr(detection, "trigger_point", None)
        if trigger_point and any(point_in_polygon(trigger_point, polygon) for polygon in active_ignore_polygons):
            continue
        filtered.append(detection)
    return filtered
