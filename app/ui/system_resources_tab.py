from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.ui_metrics import Margins, Spacing, TabMetrics


class SystemResourcesTab(QWidget):
    MAX_LOG_LINES = 800

    clear_log_requested = Signal()
    log_append_requested = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.log_path: str = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        diagnostics_group = QGroupBox("Diagnostics")
        diagnostics_layout = QVBoxLayout(diagnostics_group)
        diagnostics_layout.setContentsMargins(*Margins.GROUP)
        diagnostics_layout.setSpacing(Spacing.ROW)

        diagnostics_form_container = QWidget()
        diagnostics_form = QFormLayout(diagnostics_form_container)
        diagnostics_form.setContentsMargins(*Margins.COMPACT_GROUP)
        diagnostics_form.setSpacing(Spacing.ROW)
        diagnostics_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        diagnostics_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.cpu_value = QLabel("--")
        self.memory_value = QLabel("--")
        self.app_state_value = QLabel("--")
        self.cameras_value = QLabel("--")
        self.zones_value = QLabel("--")
        self.serial_value = QLabel("--")
        self.inference_device_value = QLabel("--")
        self.camera_metrics_value = QLabel("--")
        self.camera_metrics_value.setWordWrap(True)
        self.camera_metrics_value.setObjectName("DiagnosticsBlock")

        for label_widget in [
            self.cpu_value,
            self.memory_value,
            self.app_state_value,
            self.cameras_value,
            self.zones_value,
            self.serial_value,
            self.inference_device_value,
        ]:
            label_widget.setObjectName("ValueLabel")

        diagnostics_form.addRow("CPU Usage", self.cpu_value)
        diagnostics_form.addRow("App Memory", self.memory_value)
        diagnostics_form.addRow("App State", self.app_state_value)
        diagnostics_form.addRow("Active Cameras", self.cameras_value)
        diagnostics_form.addRow("Active Zones", self.zones_value)
        diagnostics_form.addRow("Serial", self.serial_value)
        diagnostics_form.addRow("Inference Device", self.inference_device_value)
        diagnostics_layout.addWidget(diagnostics_form_container)

        self.camera_metrics_group = QGroupBox("Per-Camera")
        camera_metrics_layout = QVBoxLayout(self.camera_metrics_group)
        camera_metrics_layout.setContentsMargins(*Margins.COMPACT_GROUP)
        camera_metrics_layout.setSpacing(Spacing.NONE)
        self.camera_metrics_scroll = QScrollArea()
        self.camera_metrics_scroll.setObjectName("CardScrollArea")
        self.camera_metrics_scroll.setWidgetResizable(True)
        self.camera_metrics_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.camera_metrics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.camera_metrics_scroll.setMinimumHeight(TabMetrics.CAMERA_METRICS_MIN_HEIGHT)
        self.camera_metrics_scroll.setMaximumHeight(TabMetrics.CAMERA_METRICS_MAX_HEIGHT)
        self._camera_metrics_container = QWidget()
        self._camera_metrics_container.setObjectName("CardScrollContent")
        camera_metrics_container_layout = QVBoxLayout(self._camera_metrics_container)
        camera_metrics_container_layout.setContentsMargins(*Margins.ZERO)
        camera_metrics_container_layout.setSpacing(Spacing.NONE)
        camera_metrics_container_layout.addWidget(self.camera_metrics_value)
        self.camera_metrics_scroll.setWidget(self._camera_metrics_container)
        camera_metrics_layout.addWidget(self.camera_metrics_scroll)
        diagnostics_layout.addWidget(self.camera_metrics_group)
        layout.addWidget(diagnostics_group)

        self.log_card = QGroupBox("Live Log")
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(*Margins.GROUP)
        log_layout.setSpacing(Spacing.ROW)

        row3 = QGridLayout()
        row3.setSpacing(Spacing.LG)
        self.debug_logging = QCheckBox("Debug Logging")
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        self.btn_open_log = QPushButton("Open Log File")
        self.btn_clear_log = QPushButton("Clear Log")
        row3.addWidget(self.debug_logging, 0, 0)
        row3.addWidget(self.auto_scroll, 0, 1)
        row3.addWidget(self.btn_open_log, 1, 0)
        row3.addWidget(self.btn_clear_log, 1, 1)
        row3.setColumnStretch(0, 1)
        row3.setColumnStretch(1, 1)
        log_layout.addLayout(row3)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(TabMetrics.LIVE_LOG_MIN_HEIGHT)
        log_layout.addWidget(self.log_output, 1)
        layout.addWidget(self.log_card, 1)

        self.btn_clear_log.clicked.connect(self.clear_log_requested)
        self.btn_open_log.clicked.connect(self.open_log)
        self.log_append_requested.connect(self._append_log_on_ui)

    def set_snapshot(
        self,
        *,
        cpu_percent: str,
        memory: str,
        app_state: str,
        active_cameras: int,
        active_zones: int,
        serial_state: str,
        inference_device: str,
        per_camera_lines: list[str],
    ) -> None:
        self.cpu_value.setText(cpu_percent)
        self.memory_value.setText(memory)
        self.app_state_value.setText(app_state)
        self.cameras_value.setText(str(active_cameras))
        self.zones_value.setText(str(active_zones))
        self.serial_value.setText(serial_state)
        self.inference_device_value.setText(inference_device)
        self.camera_metrics_value.setText("\n\n".join(per_camera_lines) if per_camera_lines else "--")

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        if card_name != "logging":
            return
        self.log_card.setProperty("dirtyCard", bool(is_dirty))
        style = self.log_card.style()
        if style is not None:
            style.unpolish(self.log_card)
            style.polish(self.log_card)
        self.log_card.update()

    def append_log(self, timestamp: str, level: str, message: str) -> None:
        self.log_append_requested.emit(timestamp, level, message)

    @Slot(str, str, str)
    def _append_log_on_ui(self, timestamp: str, level: str, message: str) -> None:
        level_text = "WARN" if level == "WARNING" else level
        self.log_output.append(f"[{timestamp}] {level_text:<5} {message}")
        self._trim_log()
        if self.auto_scroll.isChecked():
            self.log_output.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log_view(self) -> None:
        self.log_output.clear()

    def open_log(self) -> None:
        if self.log_path and os.path.exists(self.log_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.log_path))

    def _trim_log(self) -> None:
        document = self.log_output.document()
        while document.blockCount() > self.MAX_LOG_LINES:
            cursor = self.log_output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
