from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_event_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_event_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_event_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_event_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_event_value(item) for item in value)
    return value


@dataclass
class LogEvent:
    level: str
    message: str


@dataclass(frozen=True)
class TriggerEvent:
    zone_id: str
    relay_id: int
    active: bool
    timestamp: float

    @property
    def transition_name(self) -> str:
        return "zone_entered" if self.active else "zone_exited"

    @property
    def trigger_name(self) -> str:
        return "trigger_on_requested" if self.active else "trigger_off_requested"


@dataclass(frozen=True)
class RuntimeEvent:
    name: str
    level: str
    message: str
    timestamp: float
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_event_value(dict(self.metadata)))
