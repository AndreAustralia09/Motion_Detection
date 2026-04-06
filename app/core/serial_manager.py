from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from app.core.log_manager import LogManager
from app.core.mock_serial_transport import MockSerialTransport
from app.core.real_serial_transport import RealSerialTransport
from app.core.serial_transport import SerialTransport


POLL_INTERVAL_S = 0.01


@dataclass(frozen=True)
class SerialCommand:
    relay_id: int
    is_on: bool

    @property
    def command_text(self) -> str:
        return f"ZONE {self.relay_id} {'ON' if self.is_on else 'OFF'}"

    @property
    def expected_ack_text(self) -> str:
        return f"ACK {self.relay_id} {'ON' if self.is_on else 'OFF'}"


@dataclass(frozen=True)
class SerialLiveState:
    connected: bool
    state: str
    status_text: str
    port: str
    baud: int
    serial_mode: str
    last_error: str
    busy: bool
    manual_disconnect: bool
    retry_enabled: bool


class SerialManager:
    def __init__(
        self,
        log_manager: LogManager,
        transport: SerialTransport | None = None,
    ) -> None:
        self.log_manager = log_manager
        self._transport = transport or MockSerialTransport()
        self._queue: queue.Queue[SerialCommand] = queue.Queue()
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._worker = threading.Thread(target=self._worker_loop, name="SerialWorker", daemon=True)
        self._worker.start()

        self.connected = False
        self.port = ""
        self.baud = 115200
        self.serial_mode = "mock"
        self.timeout_ms = 200
        self.retry_count = 3
        self.last_error = ""
        self.busy = False
        self._connection_state = "disconnected"
        self._manual_disconnect = False
        self._retry_enabled = False

    def available_ports(self) -> list[str]:
        return RealSerialTransport.available_ports()

    def serial_dependency_error(self) -> str:
        return RealSerialTransport.dependency_error()

    def configure(
        self,
        *,
        serial_mode: str = "mock",
        port: str = "",
        baud_rate: int = 9600,
        timeout_ms: int = 200,
        retry_count: int = 3,
        mock_response_delay_ms: int = 75,
        mock_drop_rate: float = 0.0,
        mock_corruption_rate: float = 0.0,
    ) -> None:
        normalized_mode = str(serial_mode or "mock").strip().lower()
        if normalized_mode not in {"mock", "real"}:
            normalized_mode = "mock"

        self.serial_mode = normalized_mode
        self.port = str(port or "")
        self.baud = int(baud_rate)
        self.timeout_ms = max(1, int(timeout_ms))
        self.retry_count = max(0, int(retry_count))
        self._transport = self._build_transport(
            serial_mode=normalized_mode,
            mock_response_delay_ms=mock_response_delay_ms,
            mock_drop_rate=mock_drop_rate,
            mock_corruption_rate=mock_corruption_rate,
        )

    def get_live_state(self) -> SerialLiveState:
        with self._state_lock:
            return SerialLiveState(
                connected=bool(self.connected),
                state=str(self._connection_state),
                status_text=self._status_text_for_state(self._connection_state),
                port=str(self.port),
                baud=int(self.baud),
                serial_mode=str(self.serial_mode),
                last_error=str(self.last_error),
                busy=bool(self.busy),
                manual_disconnect=bool(self._manual_disconnect),
                retry_enabled=bool(self._retry_enabled),
            )

    def request_user_connect(self) -> None:
        self._set_live_flags(
            state="connecting",
            manual_disconnect=False,
            retry_enabled=True,
            clear_error=True,
        )

    def request_auto_connect(self) -> None:
        self._set_live_flags(
            state="connecting",
            manual_disconnect=False,
            retry_enabled=True,
            clear_error=True,
        )

    def request_retry(self) -> None:
        self._set_live_flags(state="reconnecting")

    def clear_retry(self) -> None:
        self._set_live_flags(retry_enabled=False)

    def should_retry(self) -> bool:
        with self._state_lock:
            return bool(self._retry_enabled and not self._manual_disconnect and not self.connected)

    def request_manual_disconnect(self) -> None:
        self._set_live_flags(
            state="disconnected",
            manual_disconnect=True,
            retry_enabled=False,
        )
        self.disconnect()

    def reset_live_state(self) -> None:
        self._set_live_flags(
            state="disconnected",
            connected=False,
            manual_disconnect=False,
            retry_enabled=False,
            clear_error=True,
        )

    def connect(
        self,
        port: str,
        baud: int,
        *,
        serial_mode: str = "mock",
        timeout_ms: int = 200,
        retry_count: int = 3,
        mock_response_delay_ms: int = 75,
        mock_drop_rate: float = 0.0,
        mock_corruption_rate: float = 0.0,
    ) -> None:
        self._disconnect_transport()
        self.configure(
            serial_mode=serial_mode,
            port=port,
            baud_rate=baud,
            timeout_ms=timeout_ms,
            retry_count=retry_count,
            mock_response_delay_ms=mock_response_delay_ms,
            mock_drop_rate=mock_drop_rate,
            mock_corruption_rate=mock_corruption_rate,
        )

        if self.serial_mode == "real":
            if not self.port:
                self._set_live_flags(state="error", connected=False, last_error="No serial port selected")
                self.log_manager.error("[SERIAL ERROR] No serial port selected")
                return

            available_ports = self.available_ports()
            if available_ports and self.port not in available_ports:
                self._set_live_flags(
                    state="error",
                    connected=False,
                    last_error=f"Serial port unavailable: {self.port}",
                )
                self.log_manager.error(f"[SERIAL ERROR] {self.last_error}")
                return

        try:
            self._transport.connect(
                port=self.port,
                baud_rate=self.baud,
                timeout_ms=self.timeout_ms,
            )
        except Exception as exc:
            self._set_live_flags(state="error", connected=False, last_error=str(exc))
            self.log_manager.error(f"[SERIAL ERROR] Failed to connect: {exc}")
            return

        connected = self._transport.is_connected()
        self._set_live_flags(
            state="connected" if connected else "error",
            connected=connected,
            clear_error=connected,
            last_error="" if connected else self.last_error,
        )
        if self.connected:
            self.log_manager.info(
                f"[SERIAL RX] Connected ({self.serial_mode}) {self.port or 'mock'} @ {self.baud}"
            )

    def disconnect(self) -> None:
        self._disconnect_transport()
        self._set_live_flags(state="disconnected", connected=False)

    def _disconnect_transport(self) -> None:
        was_connected = self.connected
        self._clear_queue()
        try:
            self._transport.disconnect()
        except Exception as exc:
            self._set_live_flags(last_error=str(exc))
            self.log_manager.error(f"[SERIAL ERROR] Disconnect failed: {exc}")
        finally:
            self._set_live_flags(connected=False, busy=False)
            if was_connected:
                self.log_manager.info("[SERIAL RX] Disconnected")

    def enqueue_zone_command(self, relay_id: int, is_on: bool) -> bool:
        if not self.connected or not self._transport.is_connected():
            self._set_live_flags(last_error="No serial connection")
            self.log_manager.warning("[SERIAL ERROR] No serial connection")
            return False

        self._queue.put(SerialCommand(relay_id=int(relay_id), is_on=bool(is_on)))
        return True

    def close(self) -> None:
        self._stop_event.set()
        self.disconnect()
        self._worker.join(timeout=1.0)

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                command = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self._set_live_flags(busy=True)
                self._send_with_retry(command)
            finally:
                self._set_live_flags(busy=False)
                self._queue.task_done()

    def _send_with_retry(self, command: SerialCommand) -> bool:
        max_attempts = self.retry_count + 1
        for attempt in range(1, max_attempts + 1):
            if not self.connected or not self._transport.is_connected():
                self._set_live_flags(state="error", connected=False, last_error="No serial connection")
                self.log_manager.warning("[SERIAL ERROR] No serial connection")
                return False

            self.log_manager.info(f"[SERIAL TX] {command.command_text}")

            try:
                self._transport.send(f"{command.command_text}\n".encode("utf-8"))
            except Exception as exc:
                self._set_live_flags(state="error", connected=False, last_error=str(exc))
                self.log_manager.error(f"[SERIAL ERROR] Send failed: {exc}")
                return False

            response_text = self._wait_for_response()
            if response_text == command.expected_ack_text:
                self._set_live_flags(state="connected", connected=True, clear_error=True)
                self.log_manager.info(f"[SERIAL RX] {response_text}")
                return True

            if response_text is None:
                if attempt < max_attempts:
                    self.log_manager.warning(
                        f"[SERIAL TIMEOUT] ACK not received after {self.timeout_ms} ms"
                    )
                    self.log_manager.warning(
                        f"[SERIAL RETRY] Attempt {attempt + 1} of {max_attempts}"
                    )
                    continue
                self._set_live_flags(state="error", last_error="ACK timeout")
                self.log_manager.error(f"[SERIAL ERROR] Command failed after {max_attempts} attempts")
                return False

            if attempt < max_attempts:
                self.log_manager.error(f"[SERIAL ERROR] Malformed response: {response_text}")
                self.log_manager.warning(f"[SERIAL RETRY] Attempt {attempt + 1} of {max_attempts}")
                continue

            self._set_live_flags(state="error", last_error=f"Malformed response: {response_text}")
            self.log_manager.error(f"[SERIAL ERROR] {self.last_error}")
            return False

        return False

    def _wait_for_response(self) -> str | None:
        deadline = time.monotonic() + (self.timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            try:
                response = self._transport.read()
            except Exception as exc:
                self._set_live_flags(state="error", connected=False, last_error=str(exc))
                self.log_manager.error(f"[SERIAL ERROR] Read failed: {exc}")
                return None

            if response is not None:
                text = response.decode("utf-8", errors="replace").strip()
                return text or None

            time.sleep(POLL_INTERVAL_S)
        return None

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    @staticmethod
    def _build_transport(
        *,
        serial_mode: str,
        mock_response_delay_ms: int,
        mock_drop_rate: float,
        mock_corruption_rate: float,
    ) -> SerialTransport:
        if serial_mode == "real":
            return RealSerialTransport()
        return MockSerialTransport(
            response_delay_ms=mock_response_delay_ms,
            drop_rate=mock_drop_rate,
            corruption_rate=mock_corruption_rate,
        )

    def _set_live_flags(
        self,
        *,
        state: str | None = None,
        connected: bool | None = None,
        last_error: str | None = None,
        busy: bool | None = None,
        manual_disconnect: bool | None = None,
        retry_enabled: bool | None = None,
        clear_error: bool = False,
    ) -> None:
        with self._state_lock:
            if state is not None:
                self._connection_state = str(state)
            if connected is not None:
                self.connected = bool(connected)
            if clear_error:
                self.last_error = ""
            elif last_error is not None:
                self.last_error = str(last_error)
            if busy is not None:
                self.busy = bool(busy)
            if manual_disconnect is not None:
                self._manual_disconnect = bool(manual_disconnect)
            if retry_enabled is not None:
                self._retry_enabled = bool(retry_enabled)

    @staticmethod
    def _status_text_for_state(state: str) -> str:
        return {
            "connecting": "Connecting",
            "connected": "Connected",
            "reconnecting": "Reconnecting",
            "error": "Connect Failed",
            "disconnected": "Disconnected",
        }.get(str(state), "Disconnected")
