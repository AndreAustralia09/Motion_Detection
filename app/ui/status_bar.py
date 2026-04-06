from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.ui.ui_metrics import Margins, Spacing, StatusBarMetrics


class RelayIndicator(QWidget):
    def __init__(self, relay_id: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RelayIndicator")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(*Margins.RELAY_INDICATOR)
        layout.setSpacing(Spacing.SM)

        self.label = QLabel(str(relay_id))
        self.label.setObjectName("RelayLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label.setFixedWidth(StatusBarMetrics.RELAY_LABEL_WIDTH)
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.dot = QFrame()
        self.dot.setObjectName("RelayLed")
        self.dot.setFixedSize(StatusBarMetrics.RELAY_LED_SIZE, StatusBarMetrics.RELAY_LED_SIZE)

        layout.addWidget(self.label)
        layout.addWidget(self.dot)

    def set_on(self, on: bool) -> None:
        self.dot.setProperty("on", bool(on))
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)


class StatusBarWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusBarWidget")
        root = QHBoxLayout(self)
        root.setContentsMargins(*Margins.STATUS_BAR)
        root.setSpacing(Spacing.XXL)

        self.summary_label = QLabel()
        self.summary_label.setObjectName("StatusSummary")
        self.summary_label.setMinimumWidth(0)
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        self.relays_container = QWidget()
        self.relays_container.setObjectName("RelaysContainer")
        self.relays_layout = QVBoxLayout(self.relays_container)
        self.relays_layout.setContentsMargins(*Margins.ZERO)
        self.relays_layout.setSpacing(Spacing.SM)

        root.addWidget(self.summary_label, 1)
        root.addWidget(self.relays_container, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_summary(self, text: str) -> None:
        self.summary_label.setText(text)

    def set_relays(self, relay_states, relays_per_board: int) -> None:
        while self.relays_layout.count():
            item = self.relays_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        relay_states = sorted(relay_states, key=lambda state: state.relay_id)
        if relays_per_board <= 0:
            relays_per_board = StatusBarMetrics.DEFAULT_RELAYS_PER_BOARD

        board_widgets: dict[int, QHBoxLayout] = {}
        for state in relay_states:
            board_index = (state.relay_id - 1) // relays_per_board
            board_layout = board_widgets.get(board_index)
            if board_layout is None:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(*Margins.ZERO)
                row_layout.setSpacing(Spacing.NONE)

                board_widget = QWidget()
                board_widget.setObjectName("RelayBoard")
                board_layout = QHBoxLayout(board_widget)
                board_layout.setContentsMargins(*Margins.RELAY_BOARD)
                board_layout.setSpacing(Spacing.XS)

                board_label = QLabel(f"Relay Board {board_index + 1}")
                board_label.setObjectName("BoardLabel")
                board_layout.addWidget(board_label)
                board_layout.addSpacing(Spacing.SM)

                row_layout.addWidget(board_widget)
                row_layout.addStretch(1)
                board_widgets[board_index] = board_layout
                self.relays_layout.addWidget(row_widget, 0, Qt.AlignmentFlag.AlignRight)

            indicator = RelayIndicator(state.relay_id)
            indicator.set_on(bool(state.commanded_on))
            board_layout.addWidget(indicator)
