from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RelayState:
    relay_id: int
    commanded_on: bool = False


class RelayManager:
    def __init__(self) -> None:
        self._states: dict[int, RelayState] = {}

    def configure(self, total_relays: int) -> None:
        total_relays = max(0, int(total_relays))

        new_states: dict[int, RelayState] = {}
        for relay_id in range(1, total_relays + 1):
            if relay_id in self._states:
                new_states[relay_id] = self._states[relay_id]
            else:
                new_states[relay_id] = RelayState(relay_id=relay_id, commanded_on=False)

        self._states = new_states

    def set_state(self, relay_id: int, on: bool) -> None:
        relay_id = int(relay_id)
        if relay_id not in self._states:
            self._states[relay_id] = RelayState(relay_id=relay_id, commanded_on=bool(on))
        else:
            self._states[relay_id].commanded_on = bool(on)

    def get_state(self, relay_id: int) -> RelayState | None:
        return self._states.get(int(relay_id))

    def get_states(self) -> list[RelayState]:
        return [self._states[key] for key in sorted(self._states.keys())]
