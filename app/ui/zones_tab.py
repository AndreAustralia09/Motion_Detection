from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QListWidget,
    QPushButton,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.ui_metrics import Margins, Spacing, TabMetrics


class ZonesTab(QWidget):
    add_zone_requested = Signal()
    delete_zone_requested = Signal()
    zone_selection_changed = Signal(str)
    update_zone_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.list_card = QGroupBox("Zones")
        list_layout = QVBoxLayout(self.list_card)
        list_layout.setContentsMargins(*Margins.GROUP)
        list_layout.setSpacing(Spacing.ROW)

        self.zone_list = QListWidget()
        self.zone_list.setObjectName("PrimaryList")
        self._set_zone_list_visible_rows(TabMetrics.ZONE_LIST_VISIBLE_ROWS)
        list_layout.addWidget(self.zone_list)

        button_row = QHBoxLayout()
        button_row.setSpacing(Spacing.LG)
        self.btn_add = QPushButton("Add Zone")
        self.btn_add.setProperty("accent", True)
        self.btn_delete = QPushButton("Delete Zone")
        button_row.addWidget(self.btn_add)
        button_row.addWidget(self.btn_delete)
        list_layout.addLayout(button_row)

        self.group = QGroupBox("Zone Settings")
        form_layout = QFormLayout(self.group)
        form_layout.setContentsMargins(*Margins.GROUP)
        form_layout.setSpacing(Spacing.ROW)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.zone_name = QLineEdit()
        self.relay_combo = QComboBox()
        self.allow_shared_relay = QCheckBox("Allow Shared Relay Assignment")
        self.enabled = QCheckBox("Enabled")
        self.shared_relay_note = QLabel()
        self.shared_relay_note.setObjectName("SummaryLabel")
        self.shared_relay_note.setWordWrap(True)

        form_layout.addRow("Name", self.zone_name)
        form_layout.addRow("Assigned Relay", self.relay_combo)
        form_layout.addRow("", self.allow_shared_relay)
        form_layout.addRow("", self.shared_relay_note)
        form_layout.addRow("", self.enabled)

        self.btn_update = QPushButton("Update Zone")
        self.btn_update.setProperty("accent", True)
        form_layout.addRow(self.btn_update)

        layout.addWidget(self.list_card)
        layout.addWidget(self.group)

        self.btn_add.clicked.connect(self.add_zone_requested)
        self.btn_delete.clicked.connect(self.delete_zone_requested)
        self.zone_list.currentTextChanged.connect(self.zone_selection_changed)
        self.btn_update.clicked.connect(self.update_zone_requested)

        layout.addStretch(1)

    def _set_zone_list_visible_rows(self, row_count: int) -> None:
        sample_size = self.zone_list.sizeHintForRow(0)
        if sample_size <= 0:
            sample_item = QListWidgetItem("Sample Zone")
            self.zone_list.addItem(sample_item)
            option = QStyleOptionViewItem()
            option.initFrom(self.zone_list)
            sample_index = self.zone_list.model().index(self.zone_list.row(sample_item), 0)
            sample_size = self.zone_list.itemDelegate().sizeHint(option, sample_index).height()
            self.zone_list.takeItem(self.zone_list.row(sample_item))
            if sample_size <= 0:
                sample_size = sample_item.sizeHint().height()
        sample_size = max(sample_size, self.fontMetrics().height() + TabMetrics.LIST_ROW_EXTRA_HEIGHT)

        frame = self.zone_list.frameWidth() * 2
        inset = self.zone_list.contentsMargins().top() + self.zone_list.contentsMargins().bottom()
        self.zone_list.setMinimumHeight((sample_size * int(row_count)) + frame + inset)

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        card_map = {
            "zones": self.list_card,
            "zone_settings": self.group,
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
