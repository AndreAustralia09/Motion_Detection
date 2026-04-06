from __future__ import annotations

import json
import os
import time

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from app.core.log_manager import LogManager
from app.ui.ui_metrics import MainWindowMetrics, current_ui_density


class MainWindowLayoutCoordinator:
    """Owns MainWindow layout clamping and opt-in scaling diagnostics."""

    def __init__(self, window, log_manager: LogManager) -> None:
        self.window = window
        self.log_manager = log_manager
        self.layout_refresh_queued = False
        self.diagnostics_enabled = self.env_flag_enabled("IZT_UI_SCALING_DIAGNOSTICS")
        self.diagnostics_started_at = time.monotonic()
        self.diagnostics_last_log: dict[str, tuple[str, float]] = {}
        if self.diagnostics_enabled:
            self.log_manager.set_debug(True)

    @staticmethod
    def env_flag_enabled(name: str) -> bool:
        value = os.environ.get(name, "")
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def safe_qt_value(value) -> object:
        try:
            if hasattr(value, "value"):
                raw_value = value.value
                if isinstance(raw_value, int):
                    return raw_value
                return str(raw_value)
            return int(value)
        except Exception:
            return str(value)

    @staticmethod
    def initial_window_size() -> QSize:
        preferred = QSize(MainWindowMetrics.PREFERRED_WIDTH, MainWindowMetrics.PREFERRED_HEIGHT)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return preferred
        available = screen.availableGeometry()
        usable_width = max(1, available.width() - MainWindowMetrics.AVAILABLE_SCREEN_MARGIN)
        usable_height = max(1, available.height() - MainWindowMetrics.AVAILABLE_SCREEN_MARGIN)
        return QSize(min(preferred.width(), usable_width), min(preferred.height(), usable_height))

    def clamp_to_available_screen(self, *, reason: str) -> None:
        window = self.window
        if window.isMaximized() or window.isMinimized() or window.isFullScreen():
            return
        screen = window.screen()
        if screen is None and window.windowHandle() is not None:
            screen = window.windowHandle().screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        frame_geometry = window.frameGeometry()
        geometry = window.geometry()
        frame_extra_width = max(0, frame_geometry.width() - geometry.width())
        frame_extra_height = max(0, frame_geometry.height() - geometry.height())
        max_client_width = max(1, available.width() - frame_extra_width)
        max_client_height = max(1, available.height() - frame_extra_height)

        next_width = min(geometry.width(), max_client_width)
        next_height = min(geometry.height(), max_client_height)
        resized = next_width != geometry.width() or next_height != geometry.height()
        if resized:
            window.resize(next_width, next_height)
            frame_geometry = window.frameGeometry()

        next_x = min(max(frame_geometry.x(), available.left()), max(available.left(), available.right() - frame_geometry.width() + 1))
        next_y = min(max(frame_geometry.y(), available.top()), max(available.top(), available.bottom() - frame_geometry.height() + 1))
        moved = next_x != frame_geometry.x() or next_y != frame_geometry.y()
        if moved:
            client_offset = geometry.topLeft() - frame_geometry.topLeft()
            window.move(next_x + client_offset.x(), next_y + client_offset.y())

        if resized or moved:
            self.emit_event(
                "clamp_to_available_screen",
                force=True,
                extra={
                    "reason": reason,
                    "resized": resized,
                    "moved": moved,
                    "available": {"w": available.width(), "h": available.height()},
                    "client": {"w": next_width, "h": next_height},
                },
            )

    @staticmethod
    def widget_geometry_payload(widget: QWidget | None) -> dict[str, object] | None:
        if widget is None:
            return None
        try:
            geometry = widget.geometry()
            contents = widget.contentsRect()
            minimum = widget.minimumSizeHint()
            preferred = widget.sizeHint()
            return {
                "visible": widget.isVisible(),
                "x": geometry.x(),
                "y": geometry.y(),
                "w": geometry.width(),
                "h": geometry.height(),
                "contents_w": contents.width(),
                "contents_h": contents.height(),
                "min_hint_w": minimum.width(),
                "min_hint_h": minimum.height(),
                "size_hint_w": preferred.width(),
                "size_hint_h": preferred.height(),
            }
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def screen_geometry_payload(self) -> dict[str, object]:
        try:
            screen = self.window.screen()
            if screen is None and self.window.windowHandle() is not None:
                screen = self.window.windowHandle().screen()
            if screen is None:
                return {}
            geometry = screen.geometry()
            available = screen.availableGeometry()
            return {
                "name": screen.name(),
                "geometry": {"w": geometry.width(), "h": geometry.height()},
                "available": {"w": available.width(), "h": available.height()},
                "dpr": round(screen.devicePixelRatio(), 3),
                "logical_dpi_x": round(screen.logicalDotsPerInchX(), 3),
                "logical_dpi_y": round(screen.logicalDotsPerInchY(), 3),
            }
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def collect_scaling_snapshot(self) -> dict[str, object]:
        window = self.window
        central = window.centralWidget()
        return {
            "t_ms": int((time.monotonic() - self.diagnostics_started_at) * 1000),
            "window_state": self.safe_qt_value(window.windowState()),
            "current_camera_id": window.current_camera_id,
            "loading_project_ui": window._loading_project_ui,
            "ui_density": current_ui_density(),
            "screen": self.screen_geometry_payload(),
            "window": {
                "geometry": {
                    "x": window.geometry().x(),
                    "y": window.geometry().y(),
                    "w": window.geometry().width(),
                    "h": window.geometry().height(),
                },
                "frame_geometry": {
                    "x": window.frameGeometry().x(),
                    "y": window.frameGeometry().y(),
                    "w": window.frameGeometry().width(),
                    "h": window.frameGeometry().height(),
                },
            },
            "central": self.widget_geometry_payload(central),
            "camera_tabs": self.widget_geometry_payload(getattr(window, "camera_tabs", None)),
            "camera_view": self.safe_camera_view_diagnostic_state(),
            "status_widget": self.widget_geometry_payload(getattr(window, "status_widget", None)),
            "right_tabs": self.widget_geometry_payload(getattr(window, "right_tabs", None)),
        }

    def safe_camera_view_diagnostic_state(self) -> dict[str, object]:
        try:
            return self.window.camera_view.diagnostic_state()
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}

    def emit_log(
        self,
        log_key: str,
        message_type: str,
        payload: dict[str, object],
        *,
        throttle_s: float,
        force: bool = False,
    ) -> None:
        if not self.diagnostics_enabled:
            return
        try:
            signature = json.dumps(payload, sort_keys=True, default=str)
            previous_signature, previous_time = self.diagnostics_last_log.get(log_key, ("", 0.0))
            now = time.monotonic()
            if not force and signature == previous_signature and (now - previous_time) < throttle_s:
                return
            self.diagnostics_last_log[log_key] = (signature, now)
            self.log_manager.debug(f"[UI-SCALING-DIAG] {message_type} {signature}")
        except Exception as exc:
            try:
                self.log_manager.debug(f"[UI-SCALING-DIAG] diagnostics_error {type(exc).__name__}: {exc}")
            except Exception:
                pass

    def emit_event(
        self,
        event_name: str,
        *,
        extra: dict[str, object] | None = None,
        throttle_s: float = 0.5,
        force: bool = False,
    ) -> None:
        payload = {
            "t_ms": int((time.monotonic() - self.diagnostics_started_at) * 1000),
            "event": event_name,
        }
        if extra:
            payload.update(extra)
        try:
            self.emit_log(f"event:{event_name}", "event", payload, throttle_s=throttle_s, force=force)
        except Exception:
            pass

    def log_scaling_snapshot(self, reason: str, *, force: bool = False, throttle_s: float = 1.5) -> None:
        try:
            snapshot = self.collect_scaling_snapshot()
            snapshot["reason"] = reason
            self.emit_log("snapshot", "snapshot", snapshot, throttle_s=throttle_s, force=force)
        except Exception as exc:
            self.emit_log(
                "snapshot_error",
                "snapshot_error",
                {"reason": reason, "error": f"{type(exc).__name__}: {exc}"},
                throttle_s=throttle_s,
                force=force,
            )

    def log_child_event(self, source: str, event_name: str, payload: dict[str, object]) -> None:
        event_payload = {
            "t_ms": int((time.monotonic() - self.diagnostics_started_at) * 1000),
            "source": source,
            "event": event_name,
            "payload": payload,
        }
        try:
            self.emit_log(f"child:{source}:{event_name}", "child", event_payload, throttle_s=1.0)
        except Exception:
            pass

    def queue_layout_refresh(self, *, reason: str) -> None:
        self.emit_event("queue_layout_refresh", extra={"reason": reason})
        if self.layout_refresh_queued:
            return
        self.layout_refresh_queued = True
        QTimer.singleShot(0, lambda: self.refresh_layout_now(reason=reason))

    def refresh_layout_now(self, *, reason: str) -> None:
        self.layout_refresh_queued = False
        central = self.window.centralWidget()
        if central is None:
            return
        self.emit_event("refresh_layout_now", force=True, extra={"reason": reason})
        for widget in (self.window.camera_tabs, self.window.camera_view, self.window.status_widget, self.window.right_tabs):
            widget.updateGeometry()
        layout = central.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        central.updateGeometry()
        central.update()
        self.clamp_to_available_screen(reason=f"refresh_layout_now:{reason}")
        QTimer.singleShot(0, lambda: self.clamp_to_available_screen(reason=f"post_refresh_layout_now:{reason}"))
        self.log_scaling_snapshot(f"refresh_layout_now:{reason}", force=True)
