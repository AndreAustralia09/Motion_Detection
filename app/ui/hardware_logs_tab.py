from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.ui_metrics import Margins, Spacing, TabMetrics


class HardwareLogsTab(QWidget):
    STANDARD_BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]

    connection_toggle_requested = Signal()
    refresh_ports_requested = Signal()
    hardware_changed = Signal()
    test_selected_relay_on_requested = Signal()
    test_selected_relay_off_requested = Signal()
    test_all_zones_on_requested = Signal()
    test_all_zones_off_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.serial_card = QGroupBox("Serial Port")
        self.serial_card.setObjectName("SerialPortCard")
        serial_layout = QVBoxLayout(self.serial_card)
        serial_layout.setContentsMargins(*Margins.GROUP)
        serial_layout.setSpacing(Spacing.ROW)

        serial_header_row = QWidget()
        serial_header_row.setObjectName("SerialStatusRow")
        serial_header_layout = QHBoxLayout(serial_header_row)
        serial_header_layout.setContentsMargins(*Margins.ZERO)
        serial_header_layout.setSpacing(Spacing.LG)

        self.serial_status_indicator = QLabel("Simulation")
        self.serial_status_indicator.setObjectName("SerialStatusIndicator")

        self.com_port = QComboBox()
        self.com_port.setEditable(True)
        self.baud = QComboBox()
        self.baud.setEditable(False)
        self.baud.addItems(self.STANDARD_BAUD_RATES)
        self.baud.setCurrentText("9600")
        self.simulation_mode = QCheckBox("Simulation Mode")
        self.simulation_mode.setChecked(True)
        self.auto_connect_serial = QCheckBox("Auto-Connect")
        self.auto_connect_serial.setChecked(True)
        self.port_status = QLabel("Refresh the port list to check available COM ports.")
        self.port_status.setObjectName("SummaryLabel")
        self.port_status.setWordWrap(True)

        self.btn_refresh = QPushButton("Scan Ports")
        self.btn_connection_toggle = QPushButton("Connect")
        self.btn_connection_toggle.setProperty("accent", True)
        serial_header_layout.addWidget(self.serial_status_indicator, 1)
        serial_header_layout.addWidget(self.btn_refresh)
        serial_header_layout.addWidget(self.btn_connection_toggle)
        serial_layout.addWidget(serial_header_row)

        serial_form = QFormLayout()
        serial_form.setSpacing(Spacing.ROW)
        serial_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        serial_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        serial_connection_row = QWidget()
        serial_connection_row.setObjectName("SerialConnectionRow")
        serial_connection_layout = QHBoxLayout(serial_connection_row)
        serial_connection_layout.setContentsMargins(*Margins.ZERO)
        serial_connection_layout.setSpacing(Spacing.XL)

        port_group = QWidget()
        port_group.setObjectName("SerialPortFieldGroup")
        port_layout = QVBoxLayout(port_group)
        port_layout.setContentsMargins(*Margins.ZERO)
        port_layout.setSpacing(Spacing.XS)
        port_label = QLabel("COM Port")
        port_label.setObjectName("ValueLabel")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.com_port)

        baud_group = QWidget()
        baud_group.setObjectName("SerialBaudFieldGroup")
        baud_layout = QVBoxLayout(baud_group)
        baud_layout.setContentsMargins(*Margins.ZERO)
        baud_layout.setSpacing(Spacing.XS)
        baud_label = QLabel("Baud Rate")
        baud_label.setObjectName("ValueLabel")
        baud_layout.addWidget(baud_label)
        baud_layout.addWidget(self.baud)

        serial_connection_layout.addWidget(port_group, 1)
        serial_connection_layout.addWidget(baud_group, 1)

        serial_form.addRow(serial_connection_row)
        serial_options_row = QWidget()
        serial_options_row.setObjectName("SerialOptionsRow")
        serial_options_layout = QHBoxLayout(serial_options_row)
        serial_options_layout.setContentsMargins(*Margins.ZERO)
        serial_options_layout.setSpacing(Spacing.XL)
        serial_options_layout.addWidget(self.auto_connect_serial, 0)
        serial_options_layout.addWidget(self.simulation_mode, 0)
        serial_options_layout.addStretch(1)

        serial_form.addRow("", serial_options_row)
        serial_form.addRow("", self.port_status)
        serial_layout.addLayout(serial_form)

        self.relays_card = QGroupBox("Relays")
        relay_form = QFormLayout(self.relays_card)
        relay_form.setContentsMargins(*Margins.GROUP)
        relay_form.setSpacing(Spacing.ROW)
        relay_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        relay_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.board_count = QSpinBox()
        self.board_count.setRange(1, 16)
        self.board_count.setValue(1)
        self.board_count.setMaximumWidth(TabMetrics.HARDWARE_SPIN_MAX_WIDTH)
        self.relays_per_board = QSpinBox()
        self.relays_per_board.setRange(1, 64)
        self.relays_per_board.setValue(8)
        self.relays_per_board.setMaximumWidth(TabMetrics.HARDWARE_SPIN_MAX_WIDTH)

        relay_counts_row = QWidget()
        relay_counts_row.setObjectName("RelayCountsRow")
        relay_counts_layout = QHBoxLayout(relay_counts_row)
        relay_counts_layout.setContentsMargins(*Margins.ZERO)
        relay_counts_layout.setSpacing(Spacing.XL)

        boards_group = QWidget()
        boards_layout = QHBoxLayout(boards_group)
        boards_layout.setContentsMargins(*Margins.ZERO)
        boards_layout.setSpacing(Spacing.MD)
        boards_layout.addWidget(QLabel("Relay Boards"))
        boards_layout.addWidget(self.board_count)
        boards_layout.addStretch(1)

        relays_group = QWidget()
        relays_layout = QHBoxLayout(relays_group)
        relays_layout.setContentsMargins(*Margins.ZERO)
        relays_layout.setSpacing(Spacing.MD)
        relays_layout.addWidget(QLabel("Relays per Board"))
        relays_layout.addWidget(self.relays_per_board)
        relays_layout.addStretch(1)

        relay_counts_layout.addWidget(boards_group, 1)
        relay_counts_layout.addWidget(relays_group, 1)
        relay_form.addRow(relay_counts_row)
        relay_test_group = QGroupBox("Relay Testing")
        relay_test_layout = QVBoxLayout(relay_test_group)
        relay_test_layout.setContentsMargins(*Margins.GROUP)
        relay_test_layout.setSpacing(Spacing.ROW)

        single_relay_header = QHBoxLayout()
        single_relay_header.setSpacing(Spacing.LG)
        relay_test_label = QLabel("Single Relay Output")
        relay_test_label.setObjectName("ValueLabel")
        self.selected_relay_description = QLabel("Assigned to selected zone")
        self.selected_relay_description.setObjectName("SummaryLabel")
        self.selected_relay_description.setWordWrap(True)
        self.selected_relay_label = QLabel("No relay selected")
        self.selected_relay_label.setObjectName("SummaryLabel")
        single_relay_header.addWidget(relay_test_label)
        single_relay_header.addWidget(self.selected_relay_label, 1)
        relay_test_layout.addLayout(single_relay_header)
        relay_test_layout.addWidget(self.selected_relay_description)

        selected_relay_row = QHBoxLayout()
        selected_relay_row.setSpacing(Spacing.LG)
        self.btn_test_selected_on = QPushButton("Test Relay ON")
        self.btn_test_selected_off = QPushButton("Test Relay OFF")
        self.btn_test_selected_on.setEnabled(False)
        self.btn_test_selected_off.setEnabled(False)
        selected_relay_row.addWidget(self.btn_test_selected_on)
        selected_relay_row.addWidget(self.btn_test_selected_off)
        relay_test_layout.addLayout(selected_relay_row)

        all_relays_header = QHBoxLayout()
        all_relays_header.setSpacing(Spacing.LG)
        all_relays_label = QLabel("All Relay Outputs")
        all_relays_label.setObjectName("ValueLabel")
        all_relays_description = QLabel("Test all configured relay outputs")
        all_relays_description.setObjectName("SummaryLabel")
        all_relays_description.setWordWrap(True)
        all_relays_header.addWidget(all_relays_label)
        all_relays_header.addWidget(all_relays_description, 1)
        relay_test_layout.addLayout(all_relays_header)

        relay_button_row = QHBoxLayout()
        relay_button_row.setSpacing(Spacing.LG)
        self.btn_test_all_on = QPushButton("Test All Relays ON")
        self.btn_test_all_off = QPushButton("Test All Relays OFF")
        relay_button_row.addWidget(self.btn_test_all_on)
        relay_button_row.addWidget(self.btn_test_all_off)
        relay_test_layout.addLayout(relay_button_row)

        layout.addWidget(self.serial_card)
        layout.addWidget(self.relays_card)
        layout.addWidget(relay_test_group)
        layout.addStretch(1)

        self.btn_connection_toggle.clicked.connect(self.connection_toggle_requested)
        self.board_count.valueChanged.connect(self.hardware_changed)
        self.relays_per_board.valueChanged.connect(self.hardware_changed)
        self.baud.currentIndexChanged.connect(self.hardware_changed)
        self.com_port.currentIndexChanged.connect(self.hardware_changed)
        self.simulation_mode.toggled.connect(self.hardware_changed)
        self.auto_connect_serial.toggled.connect(self.hardware_changed)
        self.btn_refresh.clicked.connect(self.refresh_ports_requested)
        self.btn_test_selected_on.clicked.connect(self.test_selected_relay_on_requested)
        self.btn_test_selected_off.clicked.connect(self.test_selected_relay_off_requested)
        self.btn_test_all_on.clicked.connect(self.test_all_zones_on_requested)
        self.btn_test_all_off.clicked.connect(self.test_all_zones_off_requested)
        self.populate_ports()
        self.set_serial_connection_status(state="simulation", status_text="Simulation")

    def set_serial_mode_display(
        self,
        *,
        simulation_enabled: bool,
        port_text: str = "",
        baud_text: str = "9600",
        ports: list[str] | None = None,
    ) -> None:
        if simulation_enabled:
            self.com_port.blockSignals(True)
            self.com_port.clear()
            self.com_port.addItem("SIMULATION MODE", "SIMULATION MODE")
            self.com_port.setCurrentIndex(0)
            self.com_port.setCurrentText("SIMULATION MODE")
            self.com_port.setEnabled(False)
            self.com_port.blockSignals(False)

            self.baud.blockSignals(True)
            self.baud.clear()
            self.baud.addItem("SIMULATION MODE", "SIMULATION MODE")
            self.baud.setCurrentIndex(0)
            self.baud.setEnabled(False)
            self.baud.blockSignals(False)
            return

        self.com_port.setEnabled(True)
        self.baud.setEnabled(True)
        if not self.baud.count():
            self.baud.addItems(self.STANDARD_BAUD_RATES)
        elif self.baud.findText(self.STANDARD_BAUD_RATES[0]) < 0:
            self.baud.clear()
            self.baud.addItems(self.STANDARD_BAUD_RATES)
        self.com_port.blockSignals(True)
        self.com_port.clear()
        self.com_port.setCurrentText("")
        if self.com_port.lineEdit() is not None:
            self.com_port.lineEdit().clear()
        self.com_port.blockSignals(False)
        self.populate_ports(ports)
        if port_text:
            self.com_port.setCurrentText(str(port_text))
        elif self.com_port.count() > 0:
            first_value = self.com_port.itemText(0).strip()
            if first_value:
                self.com_port.setCurrentIndex(0)
                self.com_port.setCurrentText(first_value)
        self.baud.setCurrentText(str(baud_text or "9600"))

    def set_card_dirty(self, card_name: str, is_dirty: bool) -> None:
        card_map = {
            "serial": self.serial_card,
            "relays": self.relays_card,
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

    def populate_ports(self, ports: list[str] | None = None) -> None:
        self.populate_ports_with_message(ports)

    def set_serial_connection_status(self, *, state: str, status_text: str, action_text: str = "Connect") -> None:
        normalized_state = str(state or "disconnected").strip().lower()
        display_text = str(status_text or "Disconnected").strip() or "Disconnected"
        self.serial_status_indicator.setText(display_text)
        self.serial_status_indicator.setProperty("serialState", normalized_state)
        self.btn_connection_toggle.setText(str(action_text or "Connect"))
        style = self.serial_status_indicator.style()
        if style is not None:
            style.unpolish(self.serial_status_indicator)
            style.polish(self.serial_status_indicator)
        self.serial_status_indicator.update()

    def populate_ports_with_message(self, ports: list[str] | None = None, message: str | None = None) -> None:
        current = self.com_port.currentText().strip()
        if current.upper() == "SIMULATION MODE":
            current = ""
        values: list[str] = []

        for value in ports or []:
            normalized = str(value).strip()
            if normalized and normalized not in values:
                values.append(normalized)

        if current and current not in values:
            values.insert(0, current)

        if not values:
            values.append("")

        self.com_port.blockSignals(True)
        self.com_port.clear()
        self.com_port.addItems(values)
        if current:
            self.com_port.setCurrentText(current)
        self.com_port.blockSignals(False)

        available_values = [value for value in values if value]
        if message:
            self.port_status.setText(str(message))
            self.port_status.setVisible(True)
        elif available_values:
            self.port_status.setText("")
            self.port_status.setVisible(False)
        else:
            self.port_status.setText("")
            self.port_status.setVisible(False)
