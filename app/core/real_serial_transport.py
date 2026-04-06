from __future__ import annotations

from app.core.serial_transport import SerialTransport

try:
    import serial
    from serial import SerialException
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    serial = None
    SerialException = Exception
    list_ports = None


class RealSerialTransport(SerialTransport):
    @staticmethod
    def dependency_error() -> str:
        if serial is None:
            return "pyserial is not installed"
        if list_ports is None:
            return "pyserial port enumeration is unavailable"
        return ""

    @staticmethod
    def available_ports() -> list[str]:
        if list_ports is None:
            return []
        try:
            ports = list(list_ports.comports())
        except Exception:
            return []
        return sorted({str(port.device) for port in ports if getattr(port, "device", "")})

    def __init__(self) -> None:
        self._serial = None
        self.port = ""
        self.baud_rate = 9600
        self.timeout_ms = 200

    def connect(self, *, port: str, baud_rate: int, timeout_ms: int = 200, **_kwargs) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed")

        self.close()
        self.port = str(port or "")
        self.baud_rate = int(baud_rate)
        self.timeout_ms = max(1, int(timeout_ms))

        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout_ms / 1000.0,
                write_timeout=self.timeout_ms / 1000.0,
            )
        except SerialException as exc:
            self._serial = None
            raise RuntimeError(str(exc)) from exc

    def disconnect(self) -> None:
        self.close()

    def is_connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def send(self, data: bytes) -> None:
        if not self.is_connected():
            raise RuntimeError("Serial port is not connected")
        assert self._serial is not None
        try:
            reset_input_buffer = getattr(self._serial, "reset_input_buffer", None)
            if callable(reset_input_buffer):
                reset_input_buffer()
            self._serial.write(data)
            self._serial.flush()
        except SerialException as exc:
            raise RuntimeError(str(exc)) from exc

    def read(self) -> bytes | None:
        if not self.is_connected():
            return None
        assert self._serial is not None
        try:
            data = self._serial.readline()
        except SerialException as exc:
            raise RuntimeError(str(exc)) from exc
        return data or None

    def close(self) -> None:
        if self._serial is None:
            return
        try:
            if self._serial.is_open:
                self._serial.close()
        finally:
            self._serial = None
