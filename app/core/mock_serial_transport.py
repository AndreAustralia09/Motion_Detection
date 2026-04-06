from __future__ import annotations

import random
import time

from app.core.serial_transport import SerialTransport


class MockSerialTransport(SerialTransport):
    def __init__(
        self,
        *,
        response_delay_ms: int = 75,
        drop_rate: float = 0.0,
        corruption_rate: float = 0.0,
    ) -> None:
        self.response_delay_ms = max(0, int(response_delay_ms))
        self.drop_rate = min(1.0, max(0.0, float(drop_rate)))
        self.corruption_rate = min(1.0, max(0.0, float(corruption_rate)))
        self._connected = False
        self._pending_response: bytes | None = None
        self._pending_ready_at = 0.0
        self._random = random.Random()

    def connect(self, **_kwargs) -> None:
        self._connected = True
        self._pending_response = None
        self._pending_ready_at = 0.0

    def disconnect(self) -> None:
        self.close()

    def is_connected(self) -> bool:
        return self._connected

    def send(self, data: bytes) -> None:
        if not self._connected:
            raise RuntimeError("Mock transport is not connected")

        if self._random.random() < self.drop_rate:
            self._pending_response = None
            self._pending_ready_at = 0.0
            return

        self._pending_response = self._build_response(data)
        self._pending_ready_at = time.monotonic() + (self.response_delay_ms / 1000.0)

    def read(self) -> bytes | None:
        if not self._connected or self._pending_response is None:
            return None
        if time.monotonic() < self._pending_ready_at:
            return None
        response = self._pending_response
        self._pending_response = None
        self._pending_ready_at = 0.0
        return response

    def close(self) -> None:
        self._connected = False
        self._pending_response = None
        self._pending_ready_at = 0.0

    def _build_response(self, data: bytes) -> bytes:
        if self._random.random() < self.corruption_rate:
            return b"?? MALFORMED ??\n"

        text = data.decode("utf-8", errors="ignore").strip()
        if text.startswith("ZONE "):
            return f"ACK {text[5:]}\n".encode("utf-8")
        return b"ACK\n"
