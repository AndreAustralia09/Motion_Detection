from __future__ import annotations

from typing import Callable, Sequence

from app.core.relay_manager import RelayManager
from app.core.serial_manager import SerialManager
from app.core.zone_relay_policy import ZoneRelayPolicy
from app.models.events import TriggerEvent
from app.models.project_model import CameraModel
from app.models.runtime_state import AppRuntimeState


class TriggerDispatchController:
    def __init__(
        self,
        *,
        zone_relay_policy: ZoneRelayPolicy,
        runtime_state: AppRuntimeState,
        relay_manager: RelayManager,
        serial_manager: SerialManager,
        get_cameras: Callable[[], Sequence[CameraModel]],
    ) -> None:
        self.zone_relay_policy = zone_relay_policy
        self.runtime_state = runtime_state
        self.relay_manager = relay_manager
        self.serial_manager = serial_manager
        self._get_cameras = get_cameras

    def apply_trigger_events(self, events: Sequence[TriggerEvent]) -> bool:
        if not events:
            return False

        cameras = tuple(self._get_cameras())
        decisions = self.zone_relay_policy.filter_trigger_events(
            events,
            cameras=cameras,
            runtime_state=self.runtime_state,
        )

        changed = False
        for decision in decisions:
            event = decision.event
            relay_id = decision.relay_id
            zone_id = decision.zone_id
            desired_state = decision.desired_state

            self.runtime_state.record_runtime_event(
                event.transition_name,
                message=f"{event.transition_name} for zone {zone_id}",
                metadata={"zone_id": zone_id, "relay_id": relay_id, "active": desired_state},
            )
            self.runtime_state.record_runtime_event(
                event.trigger_name,
                message=f"{event.trigger_name} for relay {relay_id}",
                metadata={"zone_id": zone_id, "relay_id": relay_id, "active": desired_state},
            )

            self.relay_manager.set_state(relay_id, desired_state)
            self.serial_manager.enqueue_zone_command(relay_id, desired_state)
            self.runtime_state.record_runtime_event(
                "relay_on_applied" if desired_state else "relay_off_applied",
                message=f"Relay {relay_id} {'ON' if desired_state else 'OFF'} applied",
                metadata={"zone_id": zone_id, "relay_id": relay_id, "active": desired_state},
            )
            changed = True

        return changed
