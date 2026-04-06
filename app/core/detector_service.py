from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import cv2

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover
    YOLO = None

from app.models.project_model import DetectionSettings
from app.utils.app_paths import resolve_model_path


BBox = Tuple[int, int, int, int]
Point = Tuple[int, int]


@dataclass(frozen=True)
class DetectionResult:
    bbox: BBox
    confidence: float
    label: str
    trigger_point: Point


class DetectorService:
    """YOLOv8 detector wrapper for person, face, and hand modes."""

    def __init__(
        self,
        person_model_path: str | Path = "yolov8n.pt",
        face_model_path: str | Path = "models/yolov8-face.pt",
        hand_model_path: str | Path = "models/yolov8-hand.pt",
    ) -> None:
        # Person uses the Ultralytics model name so it can auto-download.
        # Face and hands remain optional local model files.
        self.person_model_path = self._resolve_model_path(person_model_path)
        self.face_model_path = Path(self._resolve_model_path(face_model_path))
        self.hand_model_path = Path(self._resolve_model_path(hand_model_path))
        self._models: Dict[str, object] = {}
        self._last_warning: str | None = None
        self._status_messages: Dict[str, str] = {}
        self._status_callback: Callable[[str], None] | None = None

    def detect(
        self,
        frame,
        settings: DetectionSettings,
        inference_resolution: int | None = None,
    ) -> List[DetectionResult]:
        model = self._get_model(settings.mode)
        if model is None:
            return []

        inference_frame, scale_x, scale_y = self._prepare_inference_frame(frame, inference_resolution)
        mode_key = str(settings.mode).lower().strip()

        try:
            predict_kwargs = {
                "source": inference_frame,
                "verbose": False,
                "conf": float(settings.confidence_threshold),
            }
            if mode_key == "person":
                predict_kwargs["classes"] = [0]
            results = model.predict(
                **predict_kwargs,
            )
        except Exception:
            return []

        detections: List[DetectionResult] = []

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue

            names = getattr(result, "names", {}) or {}
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                x1 = int(round(x1 * scale_x))
                y1 = int(round(y1 * scale_y))
                x2 = int(round(x2 * scale_x))
                y2 = int(round(y2 * scale_y))
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = max(x1, x2)
                y2 = max(y1, y2)

                area = max(0, x2 - x1) * max(0, y2 - y1)
                if area < int(settings.min_box_area):
                    continue

                cls_id = int(box.cls[0].item()) if box.cls is not None else -1
                confidence = float(box.conf[0].item()) if box.conf is not None else 0.0
                label = str(names.get(cls_id, mode_key))

                # Generic YOLO model: only keep person detections in person mode.
                if mode_key == "person" and label.lower() != "person":
                    continue

                trigger_point = self._compute_trigger_point(
                    (x1, y1, x2, y2),
                    settings.trigger_point_offset,
                )
                detections.append(
                    DetectionResult(
                        bbox=(x1, y1, x2, y2),
                        confidence=confidence,
                        label=label,
                        trigger_point=trigger_point,
                    )
                )

        return detections

    @staticmethod
    def _resolve_model_path(path_value: str | Path) -> Path | str:
        value = Path(path_value) if not isinstance(path_value, Path) else path_value
        if value.is_absolute():
            return value

        text_value = str(path_value)
        if text_value in {"yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"}:
            local_candidate = resolve_model_path(text_value)
            return local_candidate if local_candidate.exists() else text_value

        return resolve_model_path(*value.parts)

    def set_status_callback(self, callback: Callable[[str], None] | None) -> None:
        self._status_callback = callback

    def get_status(self, mode: str) -> str:
        mode_key = str(mode).lower().strip()
        if YOLO is None:
            return "Ultralytics is not installed. Add 'ultralytics>=8' to requirements."
        if mode_key == "face" and not self.face_model_path.exists():
            return f"Face model not found: {self.face_model_path}"
        if mode_key == "hands" and not self.hand_model_path.exists():
            return f"Hand model not found: {self.hand_model_path}"
        return self._status_messages.get(mode_key, "")

    def annotate_frame(self, frame, detections: List[DetectionResult]):
        annotated = frame.copy()
        for detection in detections:
            x1, y1, x2, y2 = detection.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 0), 2)
            label = f"{detection.label} {detection.confidence:.2f}"
            cv2.putText(
                annotated,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 200, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.circle(annotated, detection.trigger_point, 4, (0, 0, 255), -1)
        return annotated

    def _get_model(self, mode: str):
        mode_key = str(mode).lower().strip()

        if YOLO is None:
            self._warn_once(
                mode_key,
                "Ultralytics is not installed. Add 'ultralytics>=8' to requirements.",
            )
            return None

        if mode_key in self._models:
            return self._models[mode_key]

        if mode_key == "person":
            try:
                model = YOLO(self.person_model_path)
            except Exception as exc:
                self._warn_once(
                    mode_key,
                    f"Failed to load person model '{self.person_model_path}': {exc}",
                )
                return None

            self._models[mode_key] = model
            self._status_messages[mode_key] = ""
            return model

        if mode_key == "face":
            if not self.face_model_path.exists():
                self._warn_once(mode_key, f"Face model not found: {self.face_model_path}")
                return None

            try:
                model = YOLO(str(self.face_model_path))
            except Exception as exc:
                self._warn_once(
                    mode_key,
                    f"Failed to load face model '{self.face_model_path}': {exc}",
                )
                return None

            self._models[mode_key] = model
            self._status_messages[mode_key] = ""
            return model

        if mode_key == "hands":
            if not self.hand_model_path.exists():
                self._warn_once(mode_key, f"Hand model not found: {self.hand_model_path}")
                return None

            try:
                model = YOLO(str(self.hand_model_path))
            except Exception as exc:
                self._warn_once(
                    mode_key,
                    f"Failed to load hand model '{self.hand_model_path}': {exc}",
                )
                return None

            self._models[mode_key] = model
            self._status_messages[mode_key] = ""
            return model

        self._warn_once(mode_key, f"Unknown detection mode: {mode_key}")
        return None

    @staticmethod
    def _compute_trigger_point(bbox: BBox, trigger_point_offset: float) -> Point:
        x1, y1, x2, y2 = bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        offset = min(1.0, max(0.0, float(trigger_point_offset)))
        cx = x1 + width // 2
        ty = y1 + int(round((height - 1) * offset))
        ty = max(y1, min(y2 - 1, ty))
        return cx, ty

    def _prepare_inference_frame(
        self,
        frame,
        inference_resolution: int | None,
    ) -> tuple[object, float, float]:
        height, width = frame.shape[:2]
        target_dim = max(1, int(inference_resolution or max(width, height)))
        max_dim = max(width, height)
        if max_dim <= target_dim:
            return frame, 1.0, 1.0

        scale = target_dim / float(max_dim)
        resized_width = max(1, int(round(width * scale)))
        resized_height = max(1, int(round(height * scale)))
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        return resized, width / float(resized_width), height / float(resized_height)

    def _warn_once(self, mode: str, message: str) -> None:
        self._status_messages[str(mode).lower().strip()] = message
        if self._last_warning == message:
            return
        self._last_warning = message
        if self._status_callback is not None:
            self._status_callback(message)
