from __future__ import annotations

from typing import Dict, List

from app.core.detector_service import DetectionResult
from app.models.project_model import ZoneModel
from app.utils.geometry import point_in_polygon


def evaluate(
    zones: List[ZoneModel],
    detections: List[DetectionResult],
) -> Dict[str, bool]:
    results: Dict[str, bool] = {}

    for zone in zones:
        if not zone.enabled:
            continue

        occupied = False
        if len(zone.polygon) >= 3:
            for detection in detections:
                trigger_point = getattr(detection, "trigger_point", None)
                if trigger_point and point_in_polygon(trigger_point, zone.polygon):
                    occupied = True
                    break

        results[zone.id] = occupied

    return results


class OccupancyEngine:
    def evaluate(
        self,
        zones: List[ZoneModel],
        detections: List[DetectionResult],
    ) -> Dict[str, bool]:
        return evaluate(zones, detections)
