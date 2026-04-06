from __future__ import annotations

from abc import ABC, abstractmethod


class SerialTransport(ABC):
    @abstractmethod
    def connect(self, *args, **kwargs) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send(self, data: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def read(self) -> bytes | None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError
