from __future__ import annotations

import cv2
import time
from uuid import uuid4

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.models.project_model import CameraModel, IgnoreAreaModel, ZoneModel
from app.core.zone_relay_policy import ZoneRelayPolicy
from app.ui.ui_metrics import CameraViewMetrics, FontSize, Radius
from app.utils.geometry import distance_sq, point_in_polygon, point_to_segment_distance_sq, polygon_is_simple


class CameraView(QWidget):
    zone_selected = Signal(str)
    zones_changed = Signal()
    detection_area_changed = Signal()
    detection_area_mode_changed = Signal()
    detection_area_error = Signal(str)
    ignore_area_mode_changed = Signal()
    ignore_area_error = Signal(str)
    ignore_area_selected = Signal(str)
    ignore_areas_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.camera: CameraModel | None = None
        self._all_cameras_provider = lambda: [self.camera] if self.camera is not None else []
        self.frame_image: QImage | None = None
        self._frame_rgb = None
        self.frame_size: tuple[int, int] = (1280, 720)
        self._display_rect = QRectF()

        self.creating_zone = False
        self.new_zone_points: list[tuple[int, int]] = []
        self.hover_point: tuple[int, int] | None = None
        self.creating_detection_area = False
        self.modifying_detection_area = False
        self.new_detection_area_points: list[tuple[int, int]] = []
        self.detection_area_hover_point: tuple[int, int] | None = None
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_ignore_area_points: list[tuple[int, int]] = []
        self.ignore_hover_point: tuple[int, int] | None = None

        self.selected_zone_id: str | None = None
        self.dragging_handle: tuple[str, int] | None = None
        self.dragging_detection_area_handle: int | None = None
        self.selected_detection_area_handle: int | None = None
        self.selected_ignore_area_id: str | None = None
        self.dragging_ignore_handle: tuple[str, int] | None = None
        self.selected_ignore_area_handle: int | None = None
        self.detections: tuple[object, ...] = ()
        self.zone_occupancy: dict[str, bool] = {}
        self.camera_state_text = "Starting"
        self.metrics_text = ""
        self.show_overlay = True
        self.mirror_horizontal = False
        self.flip_vertical = False
        self.simulation_notice_text = ""
        self.placeholder_text: str | None = "Starting system..."
        self._diagnostics_logger = None
        self._last_diagnostics_signature: dict[str, str] = {}
        self._last_diagnostics_time: dict[str, float] = {}

    def minimumSizeHint(self) -> QSize:
        aspect_width, aspect_height = self.frame_size
        if aspect_width <= 0 or aspect_height <= 0:
            aspect_width, aspect_height = 16, 9
        minimum_height = max(CameraViewMetrics.MINIMUM_HEIGHT, self.fontMetrics().height() * CameraViewMetrics.MINIMUM_FONT_ROWS)
        minimum_width = max(CameraViewMetrics.MINIMUM_WIDTH, int(minimum_height * aspect_width / aspect_height))
        return QSize(minimum_width, minimum_height)

    def sizeHint(self) -> QSize:
        return self.minimumSizeHint()

    def set_camera(self, camera: CameraModel | None) -> None:
        self.camera = camera
        self.selected_zone_id = None
        self.creating_zone = False
        self.new_zone_points.clear()
        self.hover_point = None
        self.creating_detection_area = False
        self.modifying_detection_area = False
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.dragging_handle = None
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.selected_ignore_area_id = None
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_ignore_area_points.clear()
        self.ignore_hover_point = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.detections = ()
        self.zone_occupancy = {}
        self.frame_image = None
        self._frame_rgb = None
        self._display_rect = QRectF()
        self.camera_state_text = "Starting" if camera else "Disconnected"
        self.metrics_text = ""
        self.detection_area_mode_changed.emit()
        self.ignore_area_mode_changed.emit()
        self.update()

    def set_all_cameras_provider(self, provider) -> None:
        self._all_cameras_provider = provider

    def set_diagnostics_logger(self, logger) -> None:
        self._diagnostics_logger = logger

    def diagnostic_state(self) -> dict[str, object]:
        rect = self._image_rect()
        return {
            "widget_size": {"w": self.width(), "h": self.height()},
            "minimum_size_hint": {"w": self.minimumSizeHint().width(), "h": self.minimumSizeHint().height()},
            "size_hint": {"w": self.sizeHint().width(), "h": self.sizeHint().height()},
            "frame_size": {"w": int(self.frame_size[0]), "h": int(self.frame_size[1])},
            "display_rect": {
                "x": round(rect.x(), 2),
                "y": round(rect.y(), 2),
                "w": round(rect.width(), 2),
                "h": round(rect.height(), 2),
            },
            "display_bottom_gap": round(self.height() - rect.bottom(), 2),
            "display_right_gap": round(self.width() - rect.right(), 2),
            "has_frame": self.frame_image is not None,
            "camera_state_text": self.camera_state_text,
            "placeholder_text": self.placeholder_text,
            "show_overlay": self.show_overlay,
            "mirror_horizontal": self.mirror_horizontal,
            "flip_vertical": self.flip_vertical,
        }

    def _emit_diagnostics(
        self,
        event_name: str,
        *,
        throttle_s: float = 1.0,
        force: bool = False,
        extra: dict[str, object] | None = None,
    ) -> None:
        if self._diagnostics_logger is None:
            return
        try:
            payload = self.diagnostic_state()
            if extra:
                payload.update(extra)
            signature = repr(payload)
            now = time.monotonic()
            previous_signature = self._last_diagnostics_signature.get(event_name)
            previous_time = self._last_diagnostics_time.get(event_name, 0.0)
            if not force and signature == previous_signature and (now - previous_time) < throttle_s:
                return
            self._last_diagnostics_signature[event_name] = signature
            self._last_diagnostics_time[event_name] = now
            self._diagnostics_logger("camera_view", event_name, payload)
        except Exception:
            return

    def set_placeholder_text(self, message: str | None) -> None:
        normalized = str(message).strip() if message else None
        if self.placeholder_text == normalized:
            return
        self.placeholder_text = normalized
        if self.frame_image is None:
            self.update()

    def set_display_data(
        self,
        *,
        frame,
        frame_updated: bool,
        detections,
        occupancy,
        camera_state: str,
        fps: float,
        inference_ms: float,
        show_overlay: bool,
        mirror_horizontal: bool,
        flip_vertical: bool,
        simulation_notice: str = "",
    ) -> None:
        needs_update = False
        if frame_updated:
            self._set_frame(frame)
            needs_update = True

        detections = tuple(detections or ())
        occupancy = occupancy or {}
        camera_state_text = self._format_camera_state(camera_state)
        metrics_text = self._format_metrics(fps=fps, inference_ms=inference_ms)
        overlay_enabled = bool(show_overlay)
        simulation_notice_text = str(simulation_notice or "").strip()

        if self.detections is not detections:
            self.detections = detections
            needs_update = True
        if self.zone_occupancy is not occupancy:
            self.zone_occupancy = occupancy
            needs_update = True
        if self.camera_state_text != camera_state_text:
            self.camera_state_text = camera_state_text
            needs_update = True
        if self.metrics_text != metrics_text:
            self.metrics_text = metrics_text
            needs_update = True
        if self.show_overlay != overlay_enabled:
            self.show_overlay = overlay_enabled
            needs_update = True
        if self.mirror_horizontal != bool(mirror_horizontal):
            self.mirror_horizontal = bool(mirror_horizontal)
            needs_update = True
        if self.flip_vertical != bool(flip_vertical):
            self.flip_vertical = bool(flip_vertical)
            needs_update = True
        if self.simulation_notice_text != simulation_notice_text:
            self.simulation_notice_text = simulation_notice_text
            needs_update = True

        if needs_update:
            if frame_updated:
                self._emit_diagnostics(
                    "set_display_data",
                    throttle_s=0.75,
                    extra={"frame_updated": True},
                )
            self.update()

    def begin_add_zone(self) -> None:
        if not self.camera or self.frame_image is None:
            return
        self.creating_zone = True
        self.creating_detection_area = False
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_zone_points.clear()
        self.hover_point = None
        self.selected_zone_id = None
        self.selected_ignore_area_id = None
        self.dragging_handle = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.ignore_area_mode_changed.emit()
        self.update()

    def begin_add_detection_area(self) -> None:
        if not self.camera or self.frame_image is None:
            return
        self.creating_detection_area = True
        self.modifying_detection_area = False
        self.creating_zone = False
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.selected_zone_id = None
        self.selected_ignore_area_id = None
        self.dragging_handle = None
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.setFocus()
        self.detection_area_mode_changed.emit()
        self.ignore_area_mode_changed.emit()
        self.update()

    def begin_modify_detection_area(self) -> None:
        if not self.camera or self.frame_image is None or len(self.camera.detection_area) < 3:
            return
        self.creating_detection_area = False
        self.modifying_detection_area = True
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.setFocus()
        self.detection_area_mode_changed.emit()
        self.update()

    def end_modify_detection_area(self) -> None:
        if not self.modifying_detection_area:
            return
        self.modifying_detection_area = False
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.detection_area_mode_changed.emit()
        self.update()

    def begin_add_ignore_area(self) -> None:
        if not self.camera or self.frame_image is None:
            return
        self.creating_ignore_area = True
        self.modifying_ignore_area = False
        self.creating_zone = False
        self.creating_detection_area = False
        self.new_ignore_area_points.clear()
        self.ignore_hover_point = None
        self.selected_ignore_area_id = None
        self.selected_zone_id = None
        self.dragging_handle = None
        self.selected_detection_area_handle = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.setFocus()
        self.ignore_area_mode_changed.emit()
        self.update()

    def begin_modify_ignore_area(self) -> None:
        ignore_area = self._get_selected_ignore_area()
        if ignore_area is None or self.frame_image is None or len(ignore_area.polygon) < 3:
            return
        self.creating_ignore_area = False
        self.modifying_ignore_area = True
        self.new_ignore_area_points.clear()
        self.ignore_hover_point = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.setFocus()
        self.ignore_area_mode_changed.emit()
        self.update()

    def end_modify_ignore_area(self) -> None:
        if not self.modifying_ignore_area:
            return
        self.modifying_ignore_area = False
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.ignore_area_mode_changed.emit()
        self.update()

    def delete_selected_zone(self) -> bool:
        if not self.camera or not self.selected_zone_id:
            return False

        zone = self._get_selected_zone()
        if zone is None:
            return False

        self.camera.zones = [z for z in self.camera.zones if z.id != zone.id]
        self.selected_zone_id = None
        self.zones_changed.emit()
        self.update()
        return True

    def delete_selected_ignore_area(self) -> bool:
        if not self.camera or not self.selected_ignore_area_id:
            return False

        ignore_area = self._get_selected_ignore_area()
        if ignore_area is None:
            return False

        self.camera.ignore_areas = [area for area in self.camera.ignore_areas if area.id != ignore_area.id]
        self.selected_ignore_area_id = None
        self.modifying_ignore_area = False
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.ignore_area_mode_changed.emit()
        self.ignore_areas_changed.emit()
        self.update()
        return True

    def clear_detection_area(self) -> bool:
        if not self.camera or not self.camera.detection_area:
            return False
        self.camera.detection_area = []
        self.creating_detection_area = False
        self.modifying_detection_area = False
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.detection_area_mode_changed.emit()
        self.detection_area_changed.emit()
        self.update()
        return True

    def _set_frame(self, frame) -> None:
        if frame is None:
            self.frame_image = None
            self._frame_rgb = None
            self._display_rect = QRectF()
            return
        self._frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = self._frame_rgb.shape
        bytes_per_line = channels * width
        self.frame_image = QImage(
            self._frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        )
        self.frame_size = (width, height)
        self._display_rect = QRectF()

    def _get_selected_zone(self) -> ZoneModel | None:
        if not self.camera or not self.selected_zone_id:
            return None
        return next((z for z in self.camera.zones if z.id == self.selected_zone_id), None)

    def _all_project_cameras(self) -> list[CameraModel]:
        cameras = list(self._all_cameras_provider() or ())
        if cameras:
            return cameras
        return [self.camera] if self.camera is not None else []

    def _get_selected_ignore_area(self) -> IgnoreAreaModel | None:
        if not self.camera or not self.selected_ignore_area_id:
            return None
        return next((area for area in self.camera.ignore_areas if area.id == self.selected_ignore_area_id), None)

    def select_ignore_area(self, ignore_area_id: str | None) -> None:
        normalized = str(ignore_area_id).strip() if ignore_area_id else None
        if normalized == self.selected_ignore_area_id:
            return
        self.selected_ignore_area_id = normalized
        if normalized:
            self.selected_zone_id = None
            self.creating_zone = False
            self.dragging_handle = None
        else:
            self.modifying_ignore_area = False
            self.dragging_ignore_handle = None
            self.selected_ignore_area_handle = None
            self.ignore_area_mode_changed.emit()
        self.update()

    def clear_ignore_area_selection(self) -> None:
        self.select_ignore_area(None)

    def _image_rect(self) -> QRectF:
        if not self._display_rect.isNull():
            return QRectF(self._display_rect)
        if self.frame_image:
            content_width = self.frame_image.width()
            content_height = self.frame_image.height()
        else:
            content_width, content_height = self.frame_size
        self._display_rect = self._fit_rect(content_width, content_height)
        return QRectF(self._display_rect)

    def _fit_rect(self, content_width: int, content_height: int) -> QRectF:
        if content_width <= 0 or content_height <= 0 or self.width() <= 0 or self.height() <= 0:
            return QRectF(0, 0, self.width(), self.height())

        scale = min(self.width() / content_width, self.height() / content_height)
        display_width = content_width * scale
        display_height = content_height * scale
        x = (self.width() - display_width) / 2
        y = (self.height() - display_height) / 2
        return QRectF(x, y, display_width, display_height)

    def _widget_to_image(self, pos: QPoint) -> tuple[int, int] | None:
        if self.frame_image is None:
            return None
        rect = self._image_rect()
        if not rect.contains(pos):
            return None
        x = int((pos.x() - rect.x()) * self.frame_size[0] / rect.width())
        y = int((pos.y() - rect.y()) * self.frame_size[1] / rect.height())
        if self.mirror_horizontal:
            x = self.frame_size[0] - 1 - x
        if self.flip_vertical:
            y = self.frame_size[1] - 1 - y
        return x, y

    def _image_to_widget(self, point: tuple[int, int]) -> QPoint:
        rect = self._image_rect()
        image_x = point[0]
        image_y = point[1]
        if self.mirror_horizontal:
            image_x = self.frame_size[0] - point[0]
        if self.flip_vertical:
            image_y = self.frame_size[1] - point[1]
        x = rect.x() + image_x * rect.width() / self.frame_size[0]
        y = rect.y() + image_y * rect.height() / self.frame_size[1]
        return QPoint(int(x), int(y))

    def _find_zone_at(self, image_point: tuple[int, int]) -> ZoneModel | None:
        if not self.camera:
            return None
        for zone in reversed(self.camera.zones):
            if point_in_polygon(image_point, zone.polygon):
                return zone
        return None

    def _find_ignore_area_at(self, image_point: tuple[int, int]) -> IgnoreAreaModel | None:
        if not self.camera:
            return None
        for ignore_area in reversed(self.camera.ignore_areas):
            if point_in_polygon(image_point, ignore_area.polygon):
                return ignore_area
        return None

    def _find_handle_at(self, image_point: tuple[int, int]) -> tuple[str, int] | None:
        zone = self._get_selected_zone()
        if not zone:
            return None
        for idx, point in enumerate(zone.polygon):
            if distance_sq(image_point, point) <= 16 * 16:
                return zone.id, idx
        return None

    def _find_ignore_handle_at(self, image_point: tuple[int, int]) -> tuple[str, int] | None:
        ignore_area = self._get_selected_ignore_area()
        if not ignore_area:
            return None
        for idx, point in enumerate(ignore_area.polygon):
            if distance_sq(image_point, point) <= 16 * 16:
                return ignore_area.id, idx
        return None

    def _find_ignore_area_edge_at(self, image_point: tuple[int, int]) -> int | None:
        ignore_area = self._get_selected_ignore_area()
        if ignore_area is None or len(ignore_area.polygon) < 2:
            return None
        polygon = list(ignore_area.polygon)
        threshold_sq = 16.0 * 16.0
        best_index = None
        best_distance = None
        for index in range(len(polygon)):
            a = polygon[index]
            b = polygon[(index + 1) % len(polygon)]
            distance = point_to_segment_distance_sq(image_point, a, b)
            if distance > threshold_sq:
                continue
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = index + 1
        return best_index

    def _find_detection_area_handle_at(self, image_point: tuple[int, int]) -> int | None:
        if not self.camera:
            return None
        for idx, point in enumerate(self.camera.detection_area):
            if distance_sq(image_point, point) <= 16 * 16:
                return idx
        return None

    def _find_detection_area_edge_at(self, image_point: tuple[int, int]) -> int | None:
        if not self.camera or len(self.camera.detection_area) < 2:
            return None
        polygon = list(self.camera.detection_area)
        threshold_sq = 16.0 * 16.0
        best_index = None
        best_distance = None
        for index in range(len(polygon)):
            a = polygon[index]
            b = polygon[(index + 1) % len(polygon)]
            distance = point_to_segment_distance_sq(image_point, a, b)
            if distance > threshold_sq:
                continue
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = index + 1
        return best_index

    def _finalize_new_zone(self) -> None:
        if not self.camera or len(self.new_zone_points) != 4:
            return

        used_zone_ids = {zone.id for zone in self.camera.zones}
        zone_id = f"{self.camera.id}_zone_{uuid4().hex[:8]}"
        while zone_id in used_zone_ids:
            zone_id = f"{self.camera.id}_zone_{uuid4().hex[:8]}"
        zone = ZoneModel(
            id=zone_id,
            name=ZoneRelayPolicy.default_zone_name(self._all_project_cameras(), exclude_zone_id=zone_id),
            polygon=list(self.new_zone_points),
            relay_id=None,
        )
        self.camera.zones.append(zone)
        self.selected_zone_id = zone.id
        self.creating_zone = False
        self.new_zone_points.clear()
        self.hover_point = None
        self.zones_changed.emit()
        self.zone_selected.emit(zone.id)
        self.update()

    def _finalize_new_ignore_area(self) -> None:
        if not self.camera:
            return
        polygon = list(self.new_ignore_area_points)
        if len(polygon) < 3:
            self.ignore_area_error.emit("Ignore area needs at least 3 points.")
            return
        if len(polygon) > 20:
            self.ignore_area_error.emit("Ignore area cannot have more than 20 points.")
            return
        if not polygon_is_simple(polygon):
            self.ignore_area_error.emit("Ignore area cannot self-intersect.")
            return

        area_num = len(self.camera.ignore_areas) + 1
        used_ids = {ignore_area.id for ignore_area in self.camera.ignore_areas}
        ignore_area_id = f"{self.camera.id}_ignore_{uuid4().hex[:8]}"
        while ignore_area_id in used_ids:
            ignore_area_id = f"{self.camera.id}_ignore_{uuid4().hex[:8]}"
        ignore_area = IgnoreAreaModel(
            id=ignore_area_id,
            name=f"Ignore Area {area_num}",
            polygon=polygon,
        )
        self.camera.ignore_areas.append(ignore_area)
        self.selected_ignore_area_id = ignore_area.id
        self.selected_zone_id = None
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_ignore_area_points.clear()
        self.ignore_hover_point = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.ignore_area_mode_changed.emit()
        self.ignore_areas_changed.emit()
        self.ignore_area_selected.emit(ignore_area.id)
        self.update()

    def _finalize_detection_area(self) -> None:
        if not self.camera:
            return
        polygon = list(self.new_detection_area_points)
        if len(polygon) < 3:
            self.detection_area_error.emit("Detection area needs at least 3 points.")
            return
        if len(polygon) > 20:
            self.detection_area_error.emit("Detection area cannot have more than 20 points.")
            return
        if not polygon_is_simple(polygon):
            self.detection_area_error.emit("Detection area cannot self-intersect.")
            return
        self.camera.detection_area = polygon
        self.creating_detection_area = False
        self.modifying_detection_area = False
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.dragging_detection_area_handle = None
        self.selected_detection_area_handle = None
        self.detection_area_mode_changed.emit()
        self.detection_area_changed.emit()
        self.update()

    def _cancel_detection_area_creation(self) -> None:
        self.creating_detection_area = False
        self.modifying_detection_area = False
        self.new_detection_area_points.clear()
        self.detection_area_hover_point = None
        self.selected_detection_area_handle = None
        self.detection_area_mode_changed.emit()
        self.update()

    def _cancel_ignore_area_creation(self) -> None:
        self.creating_ignore_area = False
        self.modifying_ignore_area = False
        self.new_ignore_area_points.clear()
        self.ignore_hover_point = None
        self.dragging_ignore_handle = None
        self.selected_ignore_area_handle = None
        self.ignore_area_mode_changed.emit()
        self.update()

    def _remove_detection_area_point(self, index: int) -> bool:
        if not self.camera or len(self.camera.detection_area) <= 3:
            self.detection_area_error.emit("Detection area needs at least 3 points.")
            return False
        if index < 0 or index >= len(self.camera.detection_area):
            return False
        updated_polygon = list(self.camera.detection_area)
        updated_polygon.pop(index)
        if not polygon_is_simple(updated_polygon):
            self.detection_area_error.emit("Detection area cannot self-intersect.")
            return False
        self.camera.detection_area = updated_polygon
        if self.selected_detection_area_handle == index:
            self.selected_detection_area_handle = None
        elif self.selected_detection_area_handle is not None and self.selected_detection_area_handle > index:
            self.selected_detection_area_handle -= 1
        self.detection_area_changed.emit()
        self.update()
        return True

    def _insert_detection_area_point(self, index: int, image_point: tuple[int, int]) -> bool:
        if not self.camera:
            return False
        if len(self.camera.detection_area) >= 20:
            self.detection_area_error.emit("Detection area cannot have more than 20 points.")
            return False
        updated_polygon = list(self.camera.detection_area)
        updated_polygon.insert(index, image_point)
        if not polygon_is_simple(updated_polygon):
            self.detection_area_error.emit("Detection area cannot self-intersect.")
            return False
        self.camera.detection_area = updated_polygon
        self.selected_detection_area_handle = index
        self.detection_area_changed.emit()
        self.update()
        return True

    def _remove_ignore_area_point(self, index: int) -> bool:
        ignore_area = self._get_selected_ignore_area()
        if ignore_area is None or len(ignore_area.polygon) <= 3:
            self.ignore_area_error.emit("Ignore area needs at least 3 points.")
            return False
        if index < 0 or index >= len(ignore_area.polygon):
            return False
        updated_polygon = list(ignore_area.polygon)
        updated_polygon.pop(index)
        if not polygon_is_simple(updated_polygon):
            self.ignore_area_error.emit("Ignore area cannot self-intersect.")
            return False
        ignore_area.polygon = updated_polygon
        if self.selected_ignore_area_handle == index:
            self.selected_ignore_area_handle = None
        elif self.selected_ignore_area_handle is not None and self.selected_ignore_area_handle > index:
            self.selected_ignore_area_handle -= 1
        self.ignore_areas_changed.emit()
        self.update()
        return True

    def _insert_ignore_area_point(self, index: int, image_point: tuple[int, int]) -> bool:
        ignore_area = self._get_selected_ignore_area()
        if ignore_area is None:
            return False
        if len(ignore_area.polygon) >= 20:
            self.ignore_area_error.emit("Ignore area cannot have more than 20 points.")
            return False
        updated_polygon = list(ignore_area.polygon)
        updated_polygon.insert(index, image_point)
        if not polygon_is_simple(updated_polygon):
            self.ignore_area_error.emit("Ignore area cannot self-intersect.")
            return False
        ignore_area.polygon = updated_polygon
        self.selected_ignore_area_handle = index
        self.ignore_areas_changed.emit()
        self.update()
        return True

    def mousePressEvent(self, event) -> None:
        image_point = self._widget_to_image(event.position().toPoint())
        if not image_point or not self.camera:
            return
        self.setFocus()

        if self.creating_detection_area:
            if (
                len(self.new_detection_area_points) >= 3
                and distance_sq(image_point, self.new_detection_area_points[0]) <= 18 * 18
            ):
                self._finalize_detection_area()
                return
            if len(self.new_detection_area_points) >= 20:
                self.detection_area_error.emit("Detection area cannot have more than 20 points.")
                return
            self.new_detection_area_points.append(image_point)
            self.detection_area_hover_point = image_point
            self.update()
            return

        if self.creating_ignore_area:
            if (
                len(self.new_ignore_area_points) >= 3
                and distance_sq(image_point, self.new_ignore_area_points[0]) <= 18 * 18
            ):
                self._finalize_new_ignore_area()
                return
            if len(self.new_ignore_area_points) >= 20:
                self.ignore_area_error.emit("Ignore area cannot have more than 20 points.")
                return
            self.new_ignore_area_points.append(image_point)
            self.ignore_hover_point = image_point
            self.update()
            return

        if self.creating_zone:
            self.new_zone_points.append(image_point)
            self.hover_point = image_point
            if len(self.new_zone_points) == 4:
                self._finalize_new_zone()
            else:
                self.update()
            return

        if self.modifying_detection_area:
            detection_area_handle = self._find_detection_area_handle_at(image_point)
            if detection_area_handle is not None:
                self.selected_detection_area_handle = detection_area_handle
                if event.button() == Qt.MouseButton.RightButton:
                    self._remove_detection_area_point(detection_area_handle)
                    return
                self.dragging_detection_area_handle = detection_area_handle
                self.selected_zone_id = None
                self.selected_ignore_area_id = None
                return

            detection_area_edge = self._find_detection_area_edge_at(image_point)
            if detection_area_edge is not None and event.button() == Qt.MouseButton.LeftButton:
                if self._insert_detection_area_point(detection_area_edge, image_point):
                    self.dragging_detection_area_handle = detection_area_edge
                self.selected_zone_id = None
                self.selected_ignore_area_id = None
                return

        if self.modifying_ignore_area:
            ignore_handle = self._find_ignore_handle_at(image_point)
            if ignore_handle:
                _, index = ignore_handle
                self.selected_ignore_area_handle = index
                if event.button() == Qt.MouseButton.RightButton:
                    self._remove_ignore_area_point(index)
                    return
                self.dragging_ignore_handle = ignore_handle
                self.selected_zone_id = None
                return

            ignore_edge = self._find_ignore_area_edge_at(image_point)
            if ignore_edge is not None and event.button() == Qt.MouseButton.LeftButton:
                if self._insert_ignore_area_point(ignore_edge, image_point):
                    ignore_area = self._get_selected_ignore_area()
                    if ignore_area is not None:
                        self.dragging_ignore_handle = (ignore_area.id, ignore_edge)
                self.selected_zone_id = None
                return

        ignore_handle = self._find_ignore_handle_at(image_point)
        if ignore_handle and self.modifying_ignore_area:
            self.dragging_ignore_handle = ignore_handle
            return

        if self.selected_ignore_area_id or self.modifying_ignore_area:
            ignore_area = self._find_ignore_area_at(image_point)
            self.selected_ignore_area_id = ignore_area.id if ignore_area else None
            if ignore_area:
                self.selected_zone_id = None
                self.ignore_area_selected.emit(ignore_area.id)
            else:
                self.ignore_area_selected.emit("")
            self.update()
            return

        handle = self._find_handle_at(image_point)
        if handle:
            self.dragging_handle = handle
            return

        zone = self._find_zone_at(image_point)
        self.selected_zone_id = zone.id if zone else None
        if zone:
            self.selected_ignore_area_id = None
            self.zone_selected.emit(zone.id)
        else:
            self.zone_selected.emit("")
        self.update()

    def mouseMoveEvent(self, event) -> None:
        image_point = self._widget_to_image(event.position().toPoint())
        if not image_point or not self.camera:
            return

        if self.creating_detection_area:
            self.detection_area_hover_point = image_point
            self.update()
            return

        if self.creating_ignore_area:
            self.ignore_hover_point = image_point
            self.update()
            return

        if self.creating_zone:
            self.hover_point = image_point
            self.update()
            return

        if self.modifying_ignore_area and self.dragging_ignore_handle:
            ignore_area = self._get_selected_ignore_area()
            if ignore_area:
                _, idx = self.dragging_ignore_handle
                updated_polygon = list(ignore_area.polygon)
                updated_polygon[idx] = image_point
                if polygon_is_simple(updated_polygon):
                    ignore_area.polygon = updated_polygon
                    self.selected_ignore_area_handle = idx
                    self.ignore_areas_changed.emit()
                    self.update()
            return

        if self.dragging_handle:
            zone = self._get_selected_zone()
            if zone:
                _, idx = self.dragging_handle
                zone.polygon[idx] = image_point
                self.zones_changed.emit()
                self.update()
            return

        if self.modifying_detection_area and self.dragging_detection_area_handle is not None:
            if self.camera.detection_area:
                updated_polygon = list(self.camera.detection_area)
                updated_polygon[self.dragging_detection_area_handle] = image_point
                if polygon_is_simple(updated_polygon):
                    self.camera.detection_area = updated_polygon
                    self.selected_detection_area_handle = self.dragging_detection_area_handle
                    self.detection_area_changed.emit()
                    self.update()

    def mouseReleaseEvent(self, event) -> None:
        self.dragging_handle = None
        self.dragging_detection_area_handle = None
        self.dragging_ignore_handle = None

    def keyPressEvent(self, event) -> None:
        if self.creating_detection_area:
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                self._finalize_detection_area()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_detection_area_creation()
                return
            super().keyPressEvent(event)
            return

        if self.creating_ignore_area:
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                self._finalize_new_ignore_area()
                return
            if event.key() == Qt.Key.Key_Escape:
                self._cancel_ignore_area_creation()
                return
            super().keyPressEvent(event)
            return

        if (
            self.modifying_detection_area
            and event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}
            and self.selected_detection_area_handle is not None
        ):
            self._remove_detection_area_point(self.selected_detection_area_handle)
            return
        if self.modifying_detection_area and event.key() == Qt.Key.Key_Escape:
            self.end_modify_detection_area()
            return
        if (
            self.modifying_ignore_area
            and event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}
            and self.selected_ignore_area_handle is not None
        ):
            self._remove_ignore_area_point(self.selected_ignore_area_handle)
            return
        if self.modifying_ignore_area and event.key() == Qt.Key.Key_Escape:
            self.end_modify_ignore_area()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#11161C"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._emit_diagnostics("paint_event", throttle_s=2.0)

        if self.frame_image is None:
            self._paint_empty_state(painter)
            return

        rect = self._image_rect()
        if self.mirror_horizontal or self.flip_vertical:
            painter.save()
            translate_x = rect.x() + rect.width() if self.mirror_horizontal else rect.x()
            translate_y = rect.y() + rect.height() if self.flip_vertical else rect.y()
            scale_x = -1.0 if self.mirror_horizontal else 1.0
            scale_y = -1.0 if self.flip_vertical else 1.0
            painter.translate(translate_x, translate_y)
            painter.scale(scale_x, scale_y)
            painter.drawImage(QRectF(0, 0, rect.width(), rect.height()), self.frame_image)
            painter.restore()
        else:
            painter.drawImage(rect, self.frame_image)
        self._paint_detection_area_mask(painter)
        self._paint_detections(painter)

        if self.camera:
            self._paint_detection_area(painter)
            for ignore_area in self.camera.ignore_areas:
                self._paint_ignore_area(painter, ignore_area)
            for zone in self.camera.zones:
                self._paint_zone(painter, zone)

        self._paint_in_progress_zone(painter)
        self._paint_in_progress_detection_area(painter)
        self._paint_in_progress_ignore_area(painter)
        if self.show_overlay:
            self._paint_metrics_overlay(painter)
        if self.simulation_notice_text:
            self._paint_simulation_notice(painter)

    def _paint_empty_state(self, painter: QPainter) -> None:
        painter.setPen(QColor("#EAF0F6"))
        font = painter.font()
        font.setPointSize(FontSize.CAMERA_EMPTY)
        font.setBold(True)
        painter.setFont(font)
        text = self.placeholder_text or self.camera_state_text
        painter.drawText(self._image_rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_zone(self, painter: QPainter, zone: ZoneModel) -> None:
        points = [self._image_to_widget(pt) for pt in zone.polygon]
        if len(points) < 2:
            return

        selected = zone.id == self.selected_zone_id
        occupied = bool(self.zone_occupancy.get(zone.id, False))
        outline = QColor("#4FC3F7")
        fill = None

        if occupied:
            outline = QColor("#E53935")
            fill = QColor("#E53935")
        if selected:
            outline = QColor("#FFB74D")
            if not occupied:
                fill = QColor("#FFB74D")

        painter.setPen(QPen(outline, CameraViewMetrics.SELECTED_OUTLINE_WIDTH if selected else CameraViewMetrics.OUTLINE_WIDTH))
        if fill is not None:
            fill.setAlpha(80)
            painter.setBrush(QBrush(fill))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawPolygon(QPolygonF(points))

        if points:
            label_pen = QColor("#E53935") if occupied else outline
            label_pos = points[0] + QPoint(CameraViewMetrics.LABEL_OFFSET_X, -CameraViewMetrics.LABEL_OFFSET_Y)
            if label_pos.y() < CameraViewMetrics.LABEL_MIN_Y:
                label_pos = points[0] + QPoint(CameraViewMetrics.LABEL_OFFSET_X, CameraViewMetrics.LABEL_MIN_Y)
            self._draw_overlay_label(painter, label_pos, zone.name, label_pen)

        if selected:
            painter.setBrush(QBrush(QColor("#FFB74D")))
            for pt in points:
                painter.drawEllipse(pt, CameraViewMetrics.SELECTED_HANDLE_RADIUS, CameraViewMetrics.SELECTED_HANDLE_RADIUS)

    def _paint_ignore_area(self, painter: QPainter, ignore_area: IgnoreAreaModel) -> None:
        points = [self._image_to_widget(pt) for pt in ignore_area.polygon]
        if len(points) < 2:
            return

        selected = ignore_area.id == self.selected_ignore_area_id
        outline = QColor("#D8B4FE") if selected else QColor("#A78BFA")
        fill = QColor("#4B5563")
        fill.setAlpha(90 if selected else 60)

        line_style = Qt.PenStyle.SolidLine if (selected and self.modifying_ignore_area) else Qt.PenStyle.DashLine
        pen = QPen(outline, CameraViewMetrics.SELECTED_OUTLINE_WIDTH if selected else CameraViewMetrics.OUTLINE_WIDTH, line_style)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawPolygon(QPolygonF(points))

        if points:
            label_pos = points[0] + QPoint(CameraViewMetrics.LABEL_OFFSET_X, -CameraViewMetrics.LABEL_OFFSET_Y)
            if label_pos.y() < CameraViewMetrics.LABEL_MIN_Y:
                label_pos = points[0] + QPoint(CameraViewMetrics.LABEL_OFFSET_X, CameraViewMetrics.LABEL_MIN_Y)
            label_text = f"Ignore: {ignore_area.name}"
            if selected and self.modifying_ignore_area:
                label_text = f"{label_text} (Modify Mode)"
            self._draw_overlay_label(painter, label_pos, label_text, outline)

        if selected and self.modifying_ignore_area:
            painter.setBrush(QBrush(outline))
            for index, pt in enumerate(points):
                radius = CameraViewMetrics.SELECTED_HANDLE_RADIUS if index == self.selected_ignore_area_handle else CameraViewMetrics.HANDLE_RADIUS
                painter.drawEllipse(pt, radius, radius)

    def _paint_detection_area_mask(self, painter: QPainter) -> None:
        if not self.camera or not self._should_show_committed_detection_area():
            return
        rect = self._image_rect()
        polygon_points = [self._image_to_widget(pt) for pt in self.camera.detection_area]
        if len(polygon_points) < 3:
            return
        outer = QPainterPath()
        outer.addRect(rect)
        inner = QPainterPath()
        inner.addPolygon(QPolygonF(polygon_points))
        masked = outer.subtracted(inner)
        painter.fillPath(masked, QColor(0, 0, 0, 115))

    def _paint_detection_area(self, painter: QPainter) -> None:
        if not self.camera or not self._should_show_committed_detection_area():
            return
        points = [self._image_to_widget(pt) for pt in self.camera.detection_area]
        outline = QColor("#F59E0B")
        fill = QColor(245, 158, 11, 20)
        line_style = Qt.PenStyle.SolidLine if self.modifying_detection_area else Qt.PenStyle.DashLine
        painter.setPen(QPen(outline, CameraViewMetrics.OUTLINE_WIDTH, line_style))
        painter.setBrush(QBrush(fill))
        painter.drawPolygon(QPolygonF(points))
        label_text = "Detection Area (Modify Mode)" if self.modifying_detection_area else "Detection Area"
        label_pos = self._detection_area_label_position(label_text)
        self._draw_overlay_label(painter, label_pos, label_text, outline)
        if self.modifying_detection_area:
            painter.setBrush(QBrush(outline))
            for index, pt in enumerate(points):
                radius = CameraViewMetrics.SELECTED_HANDLE_RADIUS if index == self.selected_detection_area_handle else CameraViewMetrics.HANDLE_RADIUS
                painter.drawEllipse(pt, radius, radius)

    def _paint_detections(self, painter: QPainter) -> None:
        if not self.detections:
            return

        detection_color = QColor("#3FB950")
        box_pen = QPen(detection_color, CameraViewMetrics.OUTLINE_WIDTH)
        box_pen.setCosmetic(True)
        trigger_brush = QBrush(detection_color)

        painter.setPen(box_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        font = painter.font()
        font.setPointSize(FontSize.CAMERA_OVERLAY)
        font.setBold(True)
        painter.setFont(font)

        for detection in self.detections:
            bbox = getattr(detection, "bbox", None)
            if not bbox or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox
            top_left = self._image_to_widget((x1, y1))
            bottom_right = self._image_to_widget((x2, y2))
            box_rect = QRectF(top_left, bottom_right).normalized()
            painter.drawRect(box_rect)

            label = getattr(detection, "label", "detection")
            confidence = getattr(detection, "confidence", None)
            label_text = str(label).title()
            if confidence is not None:
                label_text = f"{label_text} {float(confidence):.2f}"

            label_pos = box_rect.topLeft().toPoint() + QPoint(0, -CameraViewMetrics.LABEL_OFFSET_Y)
            if label_pos.y() < CameraViewMetrics.LABEL_MIN_Y:
                label_pos = box_rect.topLeft().toPoint() + QPoint(0, CameraViewMetrics.LABEL_MIN_Y)
            self._draw_overlay_label(painter, label_pos, label_text, detection_color)

            trigger_point = getattr(detection, "trigger_point", None)
            if trigger_point and len(trigger_point) == 2:
                trigger_widget = self._image_to_widget(trigger_point)
                painter.setBrush(trigger_brush)
                painter.drawEllipse(trigger_widget, CameraViewMetrics.HANDLE_RADIUS, CameraViewMetrics.HANDLE_RADIUS)
                painter.setBrush(Qt.BrushStyle.NoBrush)

    @staticmethod
    def _draw_overlay_label(painter: QPainter, position: QPoint, text: str, color: QColor) -> None:
        painter.setPen(QColor("#111111"))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            painter.drawText(position + QPoint(dx, dy), text)
        painter.setPen(color)
        painter.drawText(position, text)

    def _paint_metrics_overlay(self, painter: QPainter) -> None:
        lines = [self.camera_state_text]
        if self.metrics_text:
            lines.append(self.metrics_text)

        font = painter.font()
        font.setPointSize(FontSize.CAMERA_OVERLAY)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        text = " | ".join(line for line in lines if line)
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        rect = QRectF(
            CameraViewMetrics.OVERLAY_MARGIN,
            CameraViewMetrics.OVERLAY_MARGIN,
            text_width + (CameraViewMetrics.OVERLAY_TEXT_PADDING_X * 2),
            text_height + (CameraViewMetrics.OVERLAY_TEXT_PADDING_Y * 2),
        )

        background = QColor(10, 16, 22, 190)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(background))
        painter.drawRoundedRect(rect, Radius.OVERLAY, Radius.OVERLAY)

        painter.setPen(QColor("#F7FAFC"))
        painter.drawText(
            rect.adjusted(CameraViewMetrics.OVERLAY_TEXT_PADDING_X, 0, -CameraViewMetrics.OVERLAY_TEXT_PADDING_X, 0),
            Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        self._paint_area_guidance(painter, below_y=rect.bottom() + Radius.OVERLAY)

    def _paint_simulation_notice(self, painter: QPainter) -> None:
        font = painter.font()
        font.setPointSize(FontSize.CAMERA_OVERLAY)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        text = self.simulation_notice_text
        text_width = metrics.horizontalAdvance(text)
        text_height = metrics.height()
        rect = QRectF(
            self.width() - text_width - ((CameraViewMetrics.OVERLAY_TEXT_PADDING_X * 2) + CameraViewMetrics.OVERLAY_MARGIN),
            CameraViewMetrics.OVERLAY_MARGIN,
            text_width + (CameraViewMetrics.OVERLAY_TEXT_PADDING_X * 2),
            text_height + (CameraViewMetrics.OVERLAY_TEXT_PADDING_Y * 2),
        )

        background = QColor(138, 34, 34, 220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(background))
        painter.drawRoundedRect(rect, Radius.OVERLAY, Radius.OVERLAY)

        painter.setPen(QColor("#FFE8E8"))
        painter.drawText(
            rect.adjusted(CameraViewMetrics.OVERLAY_TEXT_PADDING_X, 0, -CameraViewMetrics.OVERLAY_TEXT_PADDING_X, 0),
            Qt.AlignmentFlag.AlignVCenter,
            text,
        )

    def _paint_area_guidance(self, painter: QPainter, *, below_y: float) -> None:
        guidance_lines = self._area_guidance_lines()
        if not guidance_lines:
            return

        font = painter.font()
        font.setPointSize(FontSize.CAMERA_OVERLAY)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = max(metrics.horizontalAdvance(line) for line in guidance_lines)
        line_height = metrics.height()
        padding_x = CameraViewMetrics.GUIDANCE_PADDING_X
        padding_y = CameraViewMetrics.GUIDANCE_PADDING_Y
        rect = QRectF(
            CameraViewMetrics.OVERLAY_MARGIN,
            below_y,
            text_width + (padding_x * 2),
            (line_height * len(guidance_lines)) + (padding_y * 2),
        )
        accent = QColor(245, 158, 11, 220)
        panel = QColor(32, 24, 10, 225)
        if self.creating_ignore_area or self.modifying_ignore_area:
            accent = QColor(192, 132, 252, 220)
            panel = QColor(28, 21, 40, 225)
        painter.setPen(QPen(accent, CameraViewMetrics.THIN_OUTLINE_WIDTH))
        painter.setBrush(QBrush(panel))
        painter.drawRoundedRect(rect, Radius.OVERLAY, Radius.OVERLAY)

        painter.setPen(QColor("#FFF3D6"))
        for index, line in enumerate(guidance_lines):
            top = rect.top() + padding_y + (index * line_height)
            line_rect = QRectF(rect.left() + padding_x, top, rect.width() - (padding_x * 2), line_height)
            painter.drawText(line_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)

    def _area_guidance_lines(self) -> list[str]:
        if self.creating_detection_area:
            lines = ["Click to add points. Enter to finish. Esc to cancel."]
            if self.new_detection_area_points:
                lines.append("Click near the first point to close the shape.")
            return lines
        if self.modifying_detection_area:
            return [
                "Drag points to move them. Click near an edge to insert.",
                "Right-click a point or press Delete to remove. Esc to finish.",
            ]
        if self.creating_ignore_area:
            lines = ["Click to add ignore-area points. Enter to finish. Esc to cancel."]
            if self.new_ignore_area_points:
                lines.append("Click near the first point to close the shape.")
            return lines
        if self.modifying_ignore_area:
            return [
                "Drag ignore-area points to move them. Click near an edge to insert.",
                "Right-click a point or press Delete to remove. Esc to finish.",
            ]
        return []

    def _detection_area_guidance_lines(self) -> list[str]:
        return self._area_guidance_lines()

    def _should_show_committed_detection_area(self) -> bool:
        return bool(self.camera and not self.creating_detection_area and len(self.camera.detection_area) >= 3)

    def _detection_area_label_position(self, text: str) -> QPoint:
        if not self.camera or len(self.camera.detection_area) < 3:
            return QPoint(CameraViewMetrics.FALLBACK_LABEL_POSITION, CameraViewMetrics.FALLBACK_LABEL_POSITION)

        points = [self._image_to_widget(pt) for pt in self.camera.detection_area]
        metrics = self.fontMetrics()
        label_width = metrics.horizontalAdvance(text)
        label_height = metrics.height()
        bounds = QPolygonF(points).boundingRect()
        candidate = QPoint(
            int(bounds.left()),
            int(bounds.bottom()) + label_height + CameraViewMetrics.LABEL_OFFSET_Y,
        )
        return self._clamp_overlay_position(candidate, label_width, label_height)

    def _clamp_overlay_position(self, position: QPoint, width: int, height: int) -> QPoint:
        min_x = CameraViewMetrics.OVERLAY_MARGIN
        min_y = CameraViewMetrics.OVERLAY_MARGIN
        max_x = max(min_x, self.width() - width - CameraViewMetrics.OVERLAY_MARGIN)
        max_y = max(min_y, self.height() - height - CameraViewMetrics.OVERLAY_MARGIN)
        return QPoint(
            max(min_x, min(position.x(), max_x)),
            max(min_y, min(position.y(), max_y)),
        )

    def resizeEvent(self, event) -> None:
        self._display_rect = QRectF()
        self._emit_diagnostics(
            "resize_event",
            force=True,
            extra={
                "old_size": {"w": event.oldSize().width(), "h": event.oldSize().height()},
                "new_size": {"w": event.size().width(), "h": event.size().height()},
            },
        )
        super().resizeEvent(event)

    def _paint_in_progress_zone(self, painter: QPainter) -> None:
        if not self.creating_zone or not self.new_zone_points:
            return

        painter.setPen(QPen(QColor("#00FFFF"), CameraViewMetrics.OUTLINE_WIDTH))
        points = [self._image_to_widget(pt) for pt in self.new_zone_points]
        painter.setBrush(QBrush(QColor("#00FFFF")))

        for pt in points:
            painter.drawEllipse(pt, CameraViewMetrics.HANDLE_RADIUS, CameraViewMetrics.HANDLE_RADIUS)

        if len(points) >= 2:
            painter.drawPolyline(QPolygonF(points))

        if self.hover_point:
            hover = self._image_to_widget(self.hover_point)
            painter.drawLine(points[-1], hover)
            if len(points) >= 3:
                painter.setPen(QPen(QColor("#00AAAA"), CameraViewMetrics.THIN_OUTLINE_WIDTH, Qt.PenStyle.DashLine))
                painter.drawLine(hover, points[0])

    def _paint_in_progress_detection_area(self, painter: QPainter) -> None:
        if not self.creating_detection_area or not self.new_detection_area_points:
            return

        painter.setPen(QPen(QColor("#F59E0B"), CameraViewMetrics.OUTLINE_WIDTH, Qt.PenStyle.DashLine))
        painter.setBrush(QBrush(QColor(245, 158, 11, 60)))
        points = [self._image_to_widget(pt) for pt in self.new_detection_area_points]

        for pt in points:
            painter.drawEllipse(pt, CameraViewMetrics.HANDLE_RADIUS, CameraViewMetrics.HANDLE_RADIUS)

        if len(points) >= 2:
            painter.drawPolyline(QPolygonF(points))

        if self.detection_area_hover_point:
            hover = self._image_to_widget(self.detection_area_hover_point)
            painter.drawLine(points[-1], hover)
            if len(points) >= 3:
                painter.drawLine(hover, points[0])

    def _paint_in_progress_ignore_area(self, painter: QPainter) -> None:
        if not self.creating_ignore_area or not self.new_ignore_area_points:
            return

        painter.setPen(QPen(QColor("#C084FC"), CameraViewMetrics.OUTLINE_WIDTH, Qt.PenStyle.DashLine))
        points = [self._image_to_widget(pt) for pt in self.new_ignore_area_points]
        painter.setBrush(QBrush(QColor(107, 114, 128, 90)))

        for pt in points:
            painter.drawEllipse(pt, CameraViewMetrics.HANDLE_RADIUS, CameraViewMetrics.HANDLE_RADIUS)

        if len(points) >= 2:
            painter.drawPolyline(QPolygonF(points))

        if self.ignore_hover_point:
            hover = self._image_to_widget(self.ignore_hover_point)
            painter.drawLine(points[-1], hover)
            if len(points) >= 3:
                painter.drawLine(hover, points[0])

    @staticmethod
    def _format_camera_state(state: str) -> str:
        value = (state or "disconnected").strip().replace("_", " ")
        if value.lower() == "inactive":
            return "Starting"
        return value.title()

    @staticmethod
    def _format_metrics(*, fps: float, inference_ms: float) -> str:
        parts: list[str] = []
        if fps > 0:
            parts.append(f"FPS: {fps:.1f}")
        if inference_ms > 0:
            parts.append(f"Infer: {inference_ms:.0f} ms")
        return " | ".join(parts)
