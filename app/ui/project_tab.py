from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.ui_metrics import Margins, Spacing, TabMetrics


class ProjectTab(QWidget):
    open_requested = Signal()
    save_requested = Signal()
    save_as_requested = Signal()
    camera_selection_changed = Signal()
    remove_camera_requested = Signal(str)
    camera_mirror_changed = Signal()
    camera_flip_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.project_card = QGroupBox("Project")
        project_form = QFormLayout(self.project_card)
        project_form.setContentsMargins(*Margins.GROUP)
        project_form.setSpacing(Spacing.ROW)
        project_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        project_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        project_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.project_name_value = QLabel("Unsaved Project")
        self.project_name_value.setObjectName("ValueLabel")
        self.project_name_value.setWordWrap(True)

        self.cameras_value = QLabel("0")
        self.cameras_value.setObjectName("ValueLabel")
        self.zones_value = QLabel("0")
        self.zones_value.setObjectName("ValueLabel")

        project_form.addRow("Project Name", self.project_name_value)
        project_form.addRow("Configured Cameras", self.cameras_value)
        project_form.addRow("Configured Zones", self.zones_value)

        self.actions_card = QGroupBox("Actions")
        actions_layout = QVBoxLayout(self.actions_card)
        actions_layout.setContentsMargins(*Margins.GROUP)
        actions_layout.setSpacing(Spacing.ROW)

        self.btn_open = QPushButton("Open Project")
        self.btn_save = QPushButton("Save Current Project")
        self.btn_save_as = QPushButton("Save As New Project")
        self.btn_open.setProperty("accent", True)
        self.btn_open.setAutoDefault(False)
        self.btn_save.setAutoDefault(False)
        self.btn_save_as.setAutoDefault(False)
        self.btn_open.setDefault(False)
        self.btn_save.setDefault(False)
        self.btn_save_as.setDefault(False)

        actions_layout.addWidget(self.btn_open)
        actions_layout.addWidget(self.btn_save)
        actions_layout.addWidget(self.btn_save_as)

        self.camera_card = QGroupBox("Configured Cameras")
        self.camera_list_layout = QVBoxLayout(self.camera_card)
        self.camera_list_layout.setContentsMargins(*Margins.GROUP)
        self.camera_list_layout.setSpacing(Spacing.ROW)

        configured_hint = QLabel("Enabled cameras run in the project. Disabled cameras stay saved but do not run.")
        configured_hint.setObjectName("SummaryLabel")
        configured_hint.setWordWrap(True)
        self.camera_list_layout.addWidget(configured_hint)
        self._camera_items_container = QWidget()
        self._camera_items_container.setObjectName("CardScrollContent")
        self._camera_items_layout = QVBoxLayout(self._camera_items_container)
        self._camera_items_layout.setContentsMargins(*Margins.ZERO)
        self._camera_items_layout.setSpacing(Spacing.MD)
        self.camera_list_scroll = QScrollArea()
        self.camera_list_scroll.setObjectName("CardScrollArea")
        self.camera_list_scroll.setWidgetResizable(True)
        self.camera_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.camera_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.camera_list_scroll.setWidget(self._camera_items_container)
        self.camera_list_scroll.setMinimumHeight(TabMetrics.CAMERA_LIST_MIN_HEIGHT)
        self.camera_list_scroll.setMaximumHeight(TabMetrics.CAMERA_LIST_MAX_HEIGHT)
        self.camera_list_layout.addWidget(self.camera_list_scroll)
        self._camera_checkboxes: dict[str, QCheckBox] = {}
        self._camera_mirror_checkboxes: dict[str, QCheckBox] = {}
        self._camera_flip_checkboxes: dict[str, QCheckBox] = {}

        layout.addWidget(self.project_card)
        layout.addWidget(self.actions_card)
        layout.addWidget(self.camera_card)
        layout.addStretch(1)

        self.btn_open.clicked.connect(self.open_requested)
        self.btn_save.clicked.connect(self.save_requested)
        self.btn_save_as.clicked.connect(self.save_as_requested)

    def set_summary_counts(self, cameras: int, zones: int) -> None:
        self.cameras_value.setText(str(cameras))
        self.zones_value.setText(str(zones))

    def set_camera_options(self, cameras: list[dict[str, str | bool]]) -> None:
        while self._camera_items_layout.count():
            item = self._camera_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._camera_checkboxes.clear()
        self._camera_mirror_checkboxes.clear()
        self._camera_flip_checkboxes.clear()

        if not cameras:
            label = QLabel("No cameras configured.")
            self._camera_items_layout.addWidget(label)
            return

        for camera in cameras:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(*Margins.CAMERA_ROW)
            row_layout.setSpacing(Spacing.LG)

            checkbox = QCheckBox(str(camera["label"]))
            checkbox.setChecked(bool(camera["enabled"]))
            checkbox.toggled.connect(self.camera_selection_changed)
            self._camera_checkboxes[str(camera["id"])] = checkbox
            row_layout.addWidget(checkbox, 1)

            mirror_checkbox = QCheckBox("Mirror")
            mirror_checkbox.setChecked(bool(camera.get("mirror_horizontal", False)))
            mirror_checkbox.toggled.connect(self.camera_mirror_changed)
            self._camera_mirror_checkboxes[str(camera["id"])] = mirror_checkbox
            row_layout.addWidget(mirror_checkbox)

            flip_checkbox = QCheckBox("Flip")
            flip_checkbox.setChecked(bool(camera.get("flip_vertical", False)))
            flip_checkbox.toggled.connect(self.camera_flip_changed)
            self._camera_flip_checkboxes[str(camera["id"])] = flip_checkbox
            row_layout.addWidget(flip_checkbox)

            remove_button = QPushButton("Remove")
            remove_button.setMinimumHeight(TabMetrics.CAMERA_REMOVE_BUTTON_MIN_HEIGHT)
            remove_button.clicked.connect(
                lambda _checked=False, camera_id=str(camera["id"]): self.remove_camera_requested.emit(camera_id)
            )
            row_layout.addWidget(remove_button)

            self._camera_items_layout.addWidget(row)

            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setFrameShadow(QFrame.Shadow.Plain)
            self._camera_items_layout.addWidget(divider)

        if self._camera_items_layout.count() > 0:
            last_item = self._camera_items_layout.takeAt(self._camera_items_layout.count() - 1)
            widget = last_item.widget()
            if widget is not None:
                widget.deleteLater()
        self._camera_items_layout.addStretch(1)

    def camera_enabled_map(self) -> dict[str, bool]:
        return {
            camera_id: checkbox.isChecked()
            for camera_id, checkbox in self._camera_checkboxes.items()
        }

    def set_camera_enabled(self, camera_id: str, enabled: bool) -> None:
        checkbox = self._camera_checkboxes.get(camera_id)
        if checkbox is None:
            return
        checkbox.setChecked(bool(enabled))

    def camera_mirror_map(self) -> dict[str, bool]:
        return {
            camera_id: checkbox.isChecked()
            for camera_id, checkbox in self._camera_mirror_checkboxes.items()
        }

    def camera_flip_map(self) -> dict[str, bool]:
        return {
            camera_id: checkbox.isChecked()
            for camera_id, checkbox in self._camera_flip_checkboxes.items()
        }

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        card_map = {
            "cameras": self.camera_card,
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
