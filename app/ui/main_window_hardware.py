from __future__ import annotations

from typing import Callable, Sequence

from PySide6.QtWidgets import QWidget

from app.core.log_manager import LogManager
from app.core.relay_manager import RelayManager
from app.core.serial_manager import SerialManager
from app.core.serial_runtime_controller import SerialRuntimeController
from app.models.project_model import ProjectModel, ZoneModel
from app.ui.confirm_dialog import ConfirmDialog
from app.ui.hardware_logs_tab import HardwareLogsTab


class HardwareUiCoordinator:
    """Coordinates Hardware tab UI state with serial and relay services."""

    def __init__(
        self,
        *,
        parent_widget: QWidget,
        hardware_tab: HardwareLogsTab,
        serial_manager: SerialManager,
        serial_runtime_controller: SerialRuntimeController,
        relay_manager: RelayManager,
        log_manager: LogManager,
        get_project: Callable[[], ProjectModel],
        current_zone: Callable[[], ZoneModel | None],
        iter_zones: Callable[[], Sequence[tuple[object, ZoneModel]]],
        stop_serial_retry_timer: Callable[[], None],
        refresh_status_bar: Callable[[], None],
        refresh_after_hardware_settings_change: Callable[[], None],
    ) -> None:
        self.parent_widget = parent_widget
        self.hardware_tab = hardware_tab
        self.serial_manager = serial_manager
        self.serial_runtime_controller = serial_runtime_controller
        self.relay_manager = relay_manager
        self.log_manager = log_manager
        self._get_project = get_project
        self._current_zone = current_zone
        self._iter_zones = iter_zones
        self._stop_serial_retry_timer = stop_serial_retry_timer
        self._refresh_status_bar = refresh_status_bar
        self._refresh_after_hardware_settings_change = refresh_after_hardware_settings_change

    def wire_signals(self) -> None:
        self.hardware_tab.connection_toggle_requested.connect(self.toggle_serial_connection)
        self.hardware_tab.refresh_ports_requested.connect(self.populate_serial_ports)
        self.hardware_tab.hardware_changed.connect(self.apply_hardware_settings)
        self.hardware_tab.test_selected_relay_on_requested.connect(self.test_selected_relay_on)
        self.hardware_tab.test_selected_relay_off_requested.connect(self.test_selected_relay_off)
        self.hardware_tab.test_all_zones_on_requested.connect(self.test_all_on)
        self.hardware_tab.test_all_zones_off_requested.connect(self.test_all_off)

    def apply_loaded_hardware_ui_state(self, project: ProjectModel) -> None:
        self.hardware_tab.simulation_mode.setChecked(project.hardware.serial_mode != "real")
        self.populate_serial_ports()
        self.hardware_tab.set_serial_mode_display(
            simulation_enabled=project.hardware.serial_mode == "mock",
            port_text=project.hardware.com_port,
            baud_text=str(project.hardware.baud_rate),
            ports=self.serial_manager.available_ports(),
        )
        self.hardware_tab.auto_connect_serial.setChecked(project.hardware.auto_connect_serial)
        self.hardware_tab.board_count.setValue(project.hardware.relay_board_count)
        self.hardware_tab.relays_per_board.setValue(project.hardware.relays_per_board)
        self.apply_hardware_settings()

    def populate_serial_ports(self) -> None:
        ports = self.serial_manager.available_ports()
        dependency_error = self.serial_manager.serial_dependency_error()
        if dependency_error:
            message = "Serial support is unavailable. Install pyserial to detect COM ports."
            self.hardware_tab.populate_ports_with_message(ports, message)
            self.log_manager.error(f"[SERIAL ERROR] {dependency_error}")
            self.refresh_serial_header_status()
            return

        if not self.hardware_tab.simulation_mode.isChecked():
            self.hardware_tab.populate_ports(ports)
        if ports:
            self.log_manager.info(f"Serial ports detected: {', '.join(ports)}")
        else:
            self.log_manager.warning("No COM ports detected")
        self.refresh_serial_header_status()

    def apply_hardware_settings(self) -> None:
        hardware, simulation_enabled = self.sync_hardware_config_from_ui()
        self.sync_hardware_ui_mode_display(
            simulation_enabled=simulation_enabled,
            port_text=hardware.com_port,
            baud_text=str(hardware.baud_rate),
        )
        if not hardware.auto_connect_serial:
            self._stop_serial_retry_timer()
        self.relay_manager.configure(hardware.total_relays)
        self.warn_if_zone_relays_out_of_range(hardware.total_relays)
        self._refresh_after_hardware_settings_change()

    def sync_hardware_config_from_ui(self) -> tuple[object, bool]:
        project = self._get_project()
        hardware = project.hardware
        simulation_enabled = self.hardware_tab.simulation_mode.isChecked()
        if not simulation_enabled:
            port_text = self.hardware_tab.com_port.currentText().strip()
            if port_text and port_text.upper() != "SIMULATION MODE":
                hardware.com_port = port_text

            baud_text = self.hardware_tab.baud.currentText().strip()
            if baud_text.isdigit():
                hardware.baud_rate = int(baud_text)

        # Serial mode is persisted with the project only. Unsaved project changes
        # to this toggle will not survive an app restart.
        hardware.serial_mode = "mock" if simulation_enabled else "real"
        hardware.auto_connect_serial = self.hardware_tab.auto_connect_serial.isChecked()
        hardware.relay_board_count = self.hardware_tab.board_count.value()
        hardware.relays_per_board = self.hardware_tab.relays_per_board.value()
        return hardware, simulation_enabled

    def sync_hardware_ui_mode_display(self, *, simulation_enabled: bool, port_text: str, baud_text: str) -> None:
        self.hardware_tab.set_serial_mode_display(
            simulation_enabled=simulation_enabled,
            port_text=port_text,
            baud_text=baud_text,
            ports=self.serial_manager.available_ports(),
        )
        if not simulation_enabled:
            self.populate_serial_ports()
        else:
            self.refresh_serial_header_status()

    def warn_if_zone_relays_out_of_range(self, total_relays: int) -> None:
        invalid_assignments = []
        for _camera, zone in self._iter_zones():
            relay_id = getattr(zone, "relay_id", None)
            if isinstance(relay_id, int) and relay_id > total_relays:
                invalid_assignments.append(zone.name)

        if invalid_assignments:
            ConfirmDialog.warn(
                self.parent_widget,
                title="Relay Configuration Changed",
                message="Some zones are assigned to relays outside the configured range. Review zone relay assignments.",
            )

    def connect_serial(self) -> None:
        self.apply_hardware_settings()
        self.serial_runtime_controller.connect_requested()
        self.refresh_serial_header_status()

    def disconnect_serial(self) -> None:
        self.serial_runtime_controller.disconnect_requested()
        self.refresh_serial_header_status()

    def toggle_serial_connection(self) -> None:
        live_state = self.serial_manager.get_live_state()
        if live_state.state in {"connected", "reconnecting"}:
            self.disconnect_serial()
            return
        self.connect_serial()

    def attempt_serial_connect(self) -> None:
        self.serial_runtime_controller.attempt_connect()

    def auto_connect_serial_if_needed(self) -> None:
        self.serial_runtime_controller.auto_connect_if_needed()

    def retry_serial_connection(self) -> None:
        self.serial_runtime_controller.retry_connection()

    def ensure_serial_retry_timer_running(self) -> None:
        self.serial_runtime_controller.ensure_retry_timer_running()

    def monitor_serial_connection(self) -> None:
        self.serial_runtime_controller.monitor_connection()

    def refresh_serial_header_status(self) -> None:
        live_state = self.serial_manager.get_live_state()
        if self._get_project().hardware.serial_mode != "real" and live_state.state != "error":
            state = "simulation"
            status_text = "Simulation"
        elif live_state.state == "error":
            state = "error"
            status_text = "Error"
        else:
            state = live_state.state
            status_text = live_state.status_text
        action_text = "Disconnect" if live_state.state in {"connected", "reconnecting"} else "Connect"
        self.hardware_tab.set_serial_connection_status(state=state, status_text=status_text, action_text=action_text)

    def test_all_on(self) -> None:
        for state in self.relay_manager.get_states():
            self.relay_manager.set_state(state.relay_id, True)
            self.serial_manager.enqueue_zone_command(state.relay_id, True)
        self._refresh_status_bar()

    def test_all_off(self) -> None:
        for state in self.relay_manager.get_states():
            self.relay_manager.set_state(state.relay_id, False)
            self.serial_manager.enqueue_zone_command(state.relay_id, False)
        self._refresh_status_bar()

    def test_selected_relay_on(self) -> None:
        self._test_selected_relay(True)

    def test_selected_relay_off(self) -> None:
        self._test_selected_relay(False)

    def _test_selected_relay(self, is_on: bool) -> None:
        zone = self._current_zone()
        if zone is None:
            ConfirmDialog.inform(
                self.parent_widget,
                title="No Zone Selected",
                message="Select a zone first to test its assigned relay.",
                button_text="OK",
            )
            return
        if not isinstance(zone.relay_id, int):
            ConfirmDialog.inform(
                self.parent_widget,
                title="Relay Not Assigned",
                message="Assign a relay to this zone before testing output.",
                button_text="OK",
            )
            return
        relay_id = int(zone.relay_id)
        self.relay_manager.set_state(relay_id, is_on)
        self.serial_manager.enqueue_zone_command(relay_id, is_on)
        self._refresh_status_bar()
