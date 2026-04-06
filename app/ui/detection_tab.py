from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from app.ui.ui_metrics import Margins, Spacing


class DetectionTab(QWidget):
    settings_changed = Signal()
    refresh_detected_cameras_requested = Signal()
    add_camera_requested = Signal()
    performance_changed = Signal(dict)
    preset_selected = Signal(str)
    PRESETS = {
        "Performance": {
            "inference_resolution": 320,
            "max_detection_fps": 2.0,
            "background_camera_fps": 0.5,
        },
        "Balanced": {
            "inference_resolution": 416,
            "max_detection_fps": 5.0,
            "background_camera_fps": 2.0,
        },
        "Accuracy": {
            "inference_resolution": 640,
            "max_detection_fps": 8.0,
            "background_camera_fps": 3.0,
        },
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.camera_detection_group = QGroupBox("Camera Detection")
        camera_detection_layout = QVBoxLayout(self.camera_detection_group)
        camera_detection_layout.setContentsMargins(*Margins.GROUP)
        camera_detection_layout.setSpacing(Spacing.ROW)

        self.detected_summary = QLabel("Click Scan to search for cameras.")
        self.detected_summary.setObjectName("SummaryLabel")
        self.detected_summary.setWordWrap(True)

        self.detected_sources = QComboBox()
        self.detected_sources.setEditable(True)

        detection_actions = QHBoxLayout()
        detection_actions.setSpacing(Spacing.LG)
        self.btn_refresh_detected = QPushButton("Scan")
        self.btn_add_camera = QPushButton("Add Camera")
        self.btn_add_camera.setProperty("accent", True)
        detection_actions.addWidget(self.btn_refresh_detected)
        detection_actions.addWidget(self.detected_sources, 1)
        detection_actions.addWidget(self.btn_add_camera)

        camera_detection_layout.addWidget(self.detected_summary)
        camera_detection_layout.addLayout(detection_actions)
        layout.addWidget(self.camera_detection_group)

        self.settings_group = QGroupBox("Detection Settings")
        form = QFormLayout(self.settings_group)
        form.setContentsMargins(*Margins.GROUP)
        form.setSpacing(Spacing.ROW)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.mode = QComboBox()
        self.mode.addItems(["Person", "Face", "Hands"])
        self.mode.setToolTip(
            "Choose which object type the detector looks for.\n"
            "Person is broader; Face and Hands use dedicated models and may need a clearer image."
        )

        self.confidence = QSpinBox()
        self.confidence.setRange(1, 100)
        self.confidence.setValue(50)
        self.confidence.setSuffix(" %")
        self.confidence.setToolTip(
            "Minimum confidence needed before a detection is accepted.\n"
            "Higher values reduce false positives but may miss weaker detections."
        )

        self.min_size = QSpinBox()
        self.min_size.setRange(0, 100000)
        self.min_size.setValue(1000)
        self.min_size.setToolTip(
            "Ignore detections smaller than this area in pixels.\n"
            "Higher values reduce noise and extra work on tiny objects."
        )

        self.trigger_offset = QSpinBox()
        self.trigger_offset.setRange(1, 100)
        self.trigger_offset.setValue(95)
        self.trigger_offset.setSuffix(" %")
        self.trigger_offset.setToolTip(
            "Sets where the trigger point sits inside each detection box.\n"
            "Higher values move it lower, which is useful for floor-based zones."
        )

        form.addRow("Detection Mode", self.mode)
        form.addRow("Confidence Threshold", self.confidence)
        form.addRow("Minimum Size", self.min_size)
        form.addRow("Trigger Point Offset", self.trigger_offset)

        layout.addWidget(self.settings_group)

        self.zone_timer_group = QGroupBox("Zone Timer Settings")
        timer_form = QFormLayout(self.zone_timer_group)
        timer_form.setContentsMargins(*Margins.GROUP)
        timer_form.setSpacing(Spacing.ROW)
        timer_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        timer_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.entry_delay = QSpinBox()
        self.entry_delay.setRange(0, 10000)
        self.entry_delay.setValue(200)
        self.entry_delay.setSuffix(" ms")
        self.entry_delay.setToolTip(
            "How long a zone must stay occupied before it turns ON.\n"
            "Higher values make triggering steadier but slower to react."
        )

        self.exit_delay = QSpinBox()
        self.exit_delay.setRange(0, 10000)
        self.exit_delay.setValue(300)
        self.exit_delay.setSuffix(" ms")
        self.exit_delay.setToolTip(
            "How long a zone must stay clear before it turns OFF.\n"
            "Higher values reduce flicker but keep outputs active longer."
        )

        timer_form.addRow("Entry Delay", self.entry_delay)
        timer_form.addRow("Exit Delay", self.exit_delay)
        layout.addWidget(self.zone_timer_group)

        self.performance_group = QGroupBox("Performance")
        performance_form = QFormLayout(self.performance_group)
        performance_form.setContentsMargins(*Margins.GROUP)
        performance_form.setSpacing(Spacing.ROW)
        performance_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        performance_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Custom", "Performance", "Balanced", "Accuracy"])

        self.inference_resolution = QComboBox()
        self.inference_resolution.addItems(["320", "416", "640"])

        self.max_detection_fps = QComboBox()
        self.max_detection_fps.addItems(["2", "3", "5", "8"])

        self.background_camera_fps = QComboBox()
        self.background_camera_fps.addItems(["0.5", "1", "2", "3"])

        performance_form.addRow("Preset", self.preset_combo)
        performance_form.addRow("Inference Resolution", self.inference_resolution)
        performance_form.addRow("Visible Camera FPS", self.max_detection_fps)
        performance_form.addRow("Background Camera FPS", self.background_camera_fps)
        layout.addWidget(self.performance_group)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        layout.addStretch(1)

        self.mode.currentIndexChanged.connect(self.settings_changed)
        self.confidence.valueChanged.connect(self.settings_changed)
        self.min_size.valueChanged.connect(self.settings_changed)
        self.entry_delay.valueChanged.connect(self.settings_changed)
        self.exit_delay.valueChanged.connect(self.settings_changed)
        self.trigger_offset.valueChanged.connect(self.settings_changed)
        self.btn_refresh_detected.clicked.connect(self.refresh_detected_cameras_requested)
        self.btn_add_camera.clicked.connect(self.add_camera_requested)
        self.inference_resolution.currentTextChanged.connect(self._emit_performance_changed)
        self.max_detection_fps.currentTextChanged.connect(self._emit_performance_changed)
        self.background_camera_fps.currentTextChanged.connect(self._emit_performance_changed)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

    def set_detected_sources(self, sources: list[object], *, current_source: str = "") -> None:
        current_text = str(current_source or self.selected_detected_source()).strip()
        entries: list[tuple[str, str]] = []
        summary_labels: list[str] = []
        seen_values: set[str] = set()
        for source in sources:
            if hasattr(source, "index"):
                value = str(getattr(source, "index", "")).strip()
                friendly_name = str(getattr(source, "friendly_name", "") or "").strip()
                source_label = f"Source {value}" if value.isdigit() else value
                label = f"{friendly_name} ({source_label})" if friendly_name else source_label
                summary_label = label
            else:
                value = str(source).strip()
                source_label = f"Source {value}" if value.isdigit() else value
                label = source_label
                summary_label = source_label
            if not value or value in seen_values:
                continue
            seen_values.add(value)
            entries.append((label, value))
            summary_labels.append(summary_label)
        if current_text and current_text not in seen_values:
            label = f"Source {current_text}" if current_text.isdigit() else current_text
            entries.insert(0, (label, current_text))
        if not entries:
            entries.append(("", ""))

        self.detected_sources.blockSignals(True)
        self.detected_sources.clear()
        for label, value in entries:
            self.detected_sources.addItem(label, value)
        if current_text:
            index = self.detected_sources.findData(current_text)
            if index >= 0:
                self.detected_sources.setCurrentIndex(index)
        self.detected_sources.blockSignals(False)

        if summary_labels:
            count = len(summary_labels)
            camera_word = "camera" if count == 1 else "cameras"
            self.detected_summary.setText(f"{count} {camera_word} detected.")
        else:
            self.detected_summary.setText("Click Scan to search for cameras.")

    def selected_detected_source(self) -> str:
        data = self.detected_sources.currentData()
        if data is not None:
            return str(data).strip()
        return self.detected_sources.currentText().replace("Source ", "", 1).strip()

    def set_values(
        self,
        mode: str,
        confidence: float,
        min_size: int,
        entry_delay: int,
        exit_delay: int,
        trigger_offset: float,
    ) -> None:
        self.mode.blockSignals(True)
        self.confidence.blockSignals(True)
        self.min_size.blockSignals(True)
        self.entry_delay.blockSignals(True)
        self.exit_delay.blockSignals(True)
        self.trigger_offset.blockSignals(True)

        mode_key = str(mode).lower()
        mode_map = {
            "person": "Person",
            "face": "Face",
            "hands": "Hands",
        }
        mode_text = mode_map.get(mode_key, "Person")
        self.mode.setCurrentText(mode_text)
        self.confidence.setValue(int(confidence * 100))
        self.min_size.setValue(int(min_size))
        self.entry_delay.setValue(int(entry_delay))
        self.exit_delay.setValue(int(exit_delay))
        self.trigger_offset.setValue(int(trigger_offset * 100))

        self.mode.blockSignals(False)
        self.confidence.blockSignals(False)
        self.min_size.blockSignals(False)
        self.entry_delay.blockSignals(False)
        self.exit_delay.blockSignals(False)
        self.trigger_offset.blockSignals(False)

    def set_model_status(self, message: str) -> None:
        text = str(message or "").strip()
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def set_performance_values(
        self,
        *,
        inference_resolution: int,
        max_detection_fps: float,
        background_camera_fps: float,
        show_fps_overlay: bool,
        mirror_horizontal: bool = False,
        preset: str | None = None,
    ) -> None:
        resolved_preset = preset or self.infer_preset(
            inference_resolution=inference_resolution,
            max_detection_fps=max_detection_fps,
            background_camera_fps=background_camera_fps,
        )
        widgets = [
            self.preset_combo,
            self.inference_resolution,
            self.max_detection_fps,
            self.background_camera_fps,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        self._set_combo_text(self.preset_combo, resolved_preset)
        self._set_combo_text(self.inference_resolution, str(int(inference_resolution)))
        self._set_combo_text(self.max_detection_fps, self._format_number(max_detection_fps))
        self._set_combo_text(self.background_camera_fps, self._format_number(background_camera_fps))
        for widget in widgets:
            widget.blockSignals(False)

    @classmethod
    def infer_preset(
        cls,
        *,
        inference_resolution: int,
        max_detection_fps: float,
        background_camera_fps: float,
    ) -> str:
        current = {
            "inference_resolution": int(inference_resolution),
            "max_detection_fps": float(max_detection_fps),
            "background_camera_fps": float(background_camera_fps),
        }
        for name, preset in cls.PRESETS.items():
            if current == preset:
                return name
        return "Custom"

    def _on_preset_changed(self, preset_name: str) -> None:
        if preset_name and preset_name != "Custom":
            self.preset_selected.emit(preset_name)

    def _emit_performance_changed(self, *_args) -> None:
        inferred_preset = self.infer_preset(
            inference_resolution=int(self.inference_resolution.currentText()),
            max_detection_fps=float(self.max_detection_fps.currentText()),
            background_camera_fps=float(self.background_camera_fps.currentText()),
        )
        self._set_combo_text(self.preset_combo, inferred_preset)
        self.performance_changed.emit(
            {
                "inference_resolution": int(self.inference_resolution.currentText()),
                "max_detection_fps": float(self.max_detection_fps.currentText()),
                "background_camera_fps": float(self.background_camera_fps.currentText()),
            }
        )

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        combo.blockSignals(True)
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        combo.blockSignals(False)

    @staticmethod
    def _format_number(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return str(float(value))

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        card_map = {
            "camera_detection": self.camera_detection_group,
            "detection_settings": self.settings_group,
            "zone_timer_settings": self.zone_timer_group,
            "performance": self.performance_group,
        }
        card = card_map.get(card_name)
        if card is None:
            return
        card.setProperty("dirtyCard", bool(is_dirty))
        style = card.style()
        if style is not None:
            style.unpolish(card)
            style.polish(card)
        card.update()
