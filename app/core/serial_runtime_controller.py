from __future__ import annotations

from typing import Callable

from app.core.serial_manager import SerialManager
from app.models.runtime_state import AppRuntimeState


class SerialRuntimeController:
    def __init__(
        self,
        *,
        serial_manager: SerialManager,
        runtime_state: AppRuntimeState,
        get_hardware: Callable[[], object],
        record_runtime_transition: Callable[..., None],
        refresh_status_bar: Callable[[], None],
        refresh_application_state: Callable[[], None],
        start_retry_timer: Callable[[], None],
        stop_retry_timer: Callable[[], None],
        is_retry_timer_active: Callable[[], bool],
        log_info: Callable[[str], None],
    ) -> None:
        self.serial_manager = serial_manager
        self.runtime_state = runtime_state
        self._get_hardware = get_hardware
        self._record_runtime_transition = record_runtime_transition
        self._refresh_status_bar = refresh_status_bar
        self._refresh_application_state = refresh_application_state
        self._start_retry_timer = start_retry_timer
        self._stop_retry_timer = stop_retry_timer
        self._is_retry_timer_active = is_retry_timer_active
        self._log_info = log_info

    def sync_runtime_state(self, *, record_disconnect: bool = True) -> None:
        live_state = self.serial_manager.get_live_state()
        previous_state, _previous_error = self.runtime_state.get_serial_state()
        hardware = self._get_hardware()
        hardware.connected = live_state.connected
        self._set_serial_runtime_state(live_state.state, live_state.last_error)
        if record_disconnect and previous_state == "connected" and live_state.state in {"disconnected", "error", "reconnecting"}:
            self._record_runtime_transition(
                "serial_disconnected",
                "[SERIAL ERROR] Serial disconnected",
                level="WARNING",
                log=True,
            )

    def connect_requested(self) -> None:
        self.serial_manager.request_user_connect()
        self.sync_runtime_state(record_disconnect=False)
        self.attempt_connect()

    def disconnect_requested(self) -> None:
        self._stop_retry_timer()
        self.serial_manager.request_manual_disconnect()
        self.sync_runtime_state(record_disconnect=False)
        self._refresh_status_bar()
        self._refresh_application_state()

    def auto_connect_if_needed(self) -> None:
        hardware = self._get_hardware()
        if not hardware.auto_connect_serial:
            return
        self.serial_manager.request_auto_connect()
        self.sync_runtime_state(record_disconnect=False)
        self.attempt_connect()

    def retry_connection(self) -> None:
        if self.serial_manager.get_live_state().connected or not self.serial_manager.should_retry():
            self._stop_retry_timer()
            return
        self.serial_manager.request_retry()
        self.sync_runtime_state()
        self._refresh_status_bar()
        self._log_info("[SERIAL RETRY] Automatic reconnect attempt")
        self.attempt_connect()

    def ensure_retry_timer_running(self) -> None:
        if not self._is_retry_timer_active() and self.serial_manager.should_retry():
            self.serial_manager.request_retry()
            self.sync_runtime_state()
            self._refresh_status_bar()
            self._start_retry_timer()

    def monitor_connection(self) -> None:
        live_state = self.serial_manager.get_live_state()
        self.sync_runtime_state()
        if live_state.connected:
            if self._is_retry_timer_active():
                self._stop_retry_timer()
            self._refresh_application_state()
            return

        if self.serial_manager.should_retry():
            self.ensure_retry_timer_running()
        elif self._is_retry_timer_active():
            self._stop_retry_timer()
        self._refresh_application_state()

    def attempt_connect(self) -> None:
        hardware = self._get_hardware()
        self.serial_manager.connect(
            hardware.com_port,
            hardware.baud_rate,
            serial_mode=hardware.serial_mode,
            timeout_ms=hardware.timeout_ms,
            retry_count=hardware.retry_count,
            mock_response_delay_ms=hardware.mock_response_delay_ms,
            mock_drop_rate=hardware.mock_drop_rate,
            mock_corruption_rate=hardware.mock_corruption_rate,
        )
        live_state = self.serial_manager.get_live_state()
        if live_state.connected:
            self._stop_retry_timer()
        elif self.serial_manager.should_retry():
            self.ensure_retry_timer_running()
        self.sync_runtime_state(record_disconnect=False)
        self._refresh_status_bar()
        self._refresh_application_state()

    def _set_serial_runtime_state(self, state: str, error: str = "") -> None:
        previous_state, previous_error = self.runtime_state.get_serial_state()
        self.runtime_state.set_serial_state(state, error)
        current_state, current_error = self.runtime_state.get_serial_state()
        if (previous_state, previous_error) != (current_state, current_error):
            self.runtime_state.record_runtime_event(
                f"serial_{current_state}",
                level="ERROR" if current_state == "error" else "INFO",
                message=f"Serial state changed to {current_state}",
                metadata={"from": previous_state, "to": current_state, "error": current_error},
            )
