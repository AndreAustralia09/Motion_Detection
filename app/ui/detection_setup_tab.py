from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QListWidget, QListWidgetItem, QPushButton, QStyleOptionViewItem, QVBoxLayout, QWidget

from app.ui.ui_metrics import Margins, Spacing, TabMetrics


class DetectionSetupTab(QWidget):
    add_detection_area_requested = Signal()
    modify_detection_area_requested = Signal()
    clear_detection_area_requested = Signal()
    add_ignore_area_requested = Signal()
    modify_ignore_area_requested = Signal()
    delete_ignore_area_requested = Signal()
    ignore_area_selection_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.detection_area_group = QGroupBox("Detection Area")
        detection_area_layout = QVBoxLayout(self.detection_area_group)
        detection_area_layout.setContentsMargins(*Margins.GROUP)
        detection_area_layout.setSpacing(Spacing.ROW)

        self.detection_area_description = QLabel(
            "Draw one per-camera detection polygon to limit where inference results can drive the system."
        )
        self.detection_area_description.setObjectName("SummaryLabel")
        self.detection_area_description.setWordWrap(True)
        detection_area_layout.addWidget(self.detection_area_description)

        self.detection_area_status = QLabel("No detection area configured")
        self.detection_area_status.setObjectName("SummaryLabel")
        self.detection_area_status.setWordWrap(True)
        detection_area_layout.addWidget(self.detection_area_status)

        detection_area_button_row = QGridLayout()
        detection_area_button_row.setSpacing(Spacing.LG)
        self.btn_add_detection_area = QPushButton("Draw Detection Area")
        self.btn_modify_detection_area = QPushButton("Modify Area")
        self.btn_modify_detection_area.setEnabled(False)
        self.btn_clear_detection_area = QPushButton("Clear Detection Area")
        self.btn_clear_detection_area.setEnabled(False)
        detection_area_button_row.addWidget(self.btn_add_detection_area, 0, 0)
        detection_area_button_row.addWidget(self.btn_modify_detection_area, 1, 0)
        detection_area_button_row.addWidget(self.btn_clear_detection_area, 2, 0)
        detection_area_layout.addLayout(detection_area_button_row)

        self.ignore_area_group = QGroupBox("Ignore Areas")
        ignore_layout = QVBoxLayout(self.ignore_area_group)
        ignore_layout.setContentsMargins(*Margins.GROUP)
        ignore_layout.setSpacing(Spacing.ROW)

        self.ignore_area_description = QLabel(
            "Draw per-camera ignore polygons for noisy regions. Detections inside ignore areas will not drive zones."
        )
        self.ignore_area_description.setObjectName("SummaryLabel")
        self.ignore_area_description.setWordWrap(True)
        ignore_layout.addWidget(self.ignore_area_description)

        self.ignore_area_status = QLabel("No ignore areas configured")
        self.ignore_area_status.setObjectName("SummaryLabel")
        self.ignore_area_status.setWordWrap(True)
        ignore_layout.addWidget(self.ignore_area_status)

        self.ignore_area_list = QListWidget()
        self.ignore_area_list.setObjectName("SecondaryList")
        self._set_ignore_area_list_visible_rows(TabMetrics.IGNORE_AREA_LIST_VISIBLE_ROWS)
        ignore_layout.addWidget(self.ignore_area_list)

        ignore_button_row = QGridLayout()
        ignore_button_row.setSpacing(Spacing.LG)
        self.btn_add_ignore_area = QPushButton("Add Ignore Area")
        self.btn_modify_ignore_area = QPushButton("Modify Ignore Area")
        self.btn_modify_ignore_area.setEnabled(False)
        self.btn_delete_ignore_area = QPushButton("Delete Ignore Area")
        self.btn_delete_ignore_area.setEnabled(False)
        ignore_button_row.addWidget(self.btn_add_ignore_area, 0, 0)
        ignore_button_row.addWidget(self.btn_modify_ignore_area, 1, 0)
        ignore_button_row.addWidget(self.btn_delete_ignore_area, 2, 0)
        ignore_layout.addLayout(ignore_button_row)

        layout.addWidget(self.detection_area_group)
        layout.addWidget(self.ignore_area_group)
        layout.addStretch(1)

        self.btn_add_detection_area.clicked.connect(self.add_detection_area_requested)
        self.btn_modify_detection_area.clicked.connect(self.modify_detection_area_requested)
        self.btn_clear_detection_area.clicked.connect(self.clear_detection_area_requested)
        self.btn_add_ignore_area.clicked.connect(self.add_ignore_area_requested)
        self.btn_modify_ignore_area.clicked.connect(self.modify_ignore_area_requested)
        self.btn_delete_ignore_area.clicked.connect(self.delete_ignore_area_requested)
        self.ignore_area_list.currentTextChanged.connect(self.ignore_area_selection_changed)

    def _set_ignore_area_list_visible_rows(self, row_count: int) -> None:
        sample_size = self.ignore_area_list.sizeHintForRow(0)
        if sample_size <= 0:
            sample_item = QListWidgetItem("Sample Ignore Area")
            self.ignore_area_list.addItem(sample_item)
            option = QStyleOptionViewItem()
            option.initFrom(self.ignore_area_list)
            sample_index = self.ignore_area_list.model().index(self.ignore_area_list.row(sample_item), 0)
            sample_size = self.ignore_area_list.itemDelegate().sizeHint(option, sample_index).height()
            self.ignore_area_list.takeItem(self.ignore_area_list.row(sample_item))
            if sample_size <= 0:
                sample_size = sample_item.sizeHint().height()
        sample_size = max(sample_size, self.fontMetrics().height() + TabMetrics.LIST_ROW_EXTRA_HEIGHT)
        frame = self.ignore_area_list.frameWidth() * 2
        inset = self.ignore_area_list.contentsMargins().top() + self.ignore_area_list.contentsMargins().bottom()
        self.ignore_area_list.setMaximumHeight((sample_size * int(row_count)) + frame + inset)

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        card_map = {
            "detection_area": self.detection_area_group,
            "ignore_areas": self.ignore_area_group,
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
