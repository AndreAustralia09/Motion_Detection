from __future__ import annotations

import threading
from typing import List

from app.models.events import TriggerEvent
from app.models.project_model import DetectionSettings, ZoneModel
from app.models.runtime_state import AppRuntimeState, ZoneRuntimeState


class TriggerEngine:
    def __init__(self, runtime_state: AppRuntimeState) -> None:
        self.runtime_state = runtime_state
        self._lock = threading.Lock()

    def update(
        self,
        camera_id: str,
        zones: List[ZoneModel],
        occupancy: dict[str, bool],
        current_time: float,
        detection_settings: DetectionSettings,
    ) -> List[TriggerEvent]:
        with self._lock:
            entry_delay_s = max(0.0, float(detection_settings.entry_delay_ms) / 1000.0)
            exit_delay_s = max(0.0, float(detection_settings.exit_delay_ms) / 1000.0)

            def _update_camera(camera_state) -> List[TriggerEvent]:
                valid_zone_ids = {zone.id for zone in zones}
                stale_zone_ids = [
                    zone_id for zone_id in camera_state.zone_states
                    if zone_id not in valid_zone_ids
                ]
                for zone_id in stale_zone_ids:
                    camera_state.zone_states.pop(zone_id, None)

                events: List[TriggerEvent] = []

                for zone in zones:
                    runtime = camera_state.zone_states.setdefault(zone.id, ZoneRuntimeState())
                    desired = bool(zone.enabled and occupancy.get(zone.id, False))
                    relay_id = getattr(zone, "relay_id", None)
                    runtime.desired_occupied = desired

                    if not zone.enabled:
                        runtime.pending_entry_since = None
                        runtime.pending_exit_since = None
                        if runtime.actual_occupied:
                            runtime.actual_occupied = False
                            if isinstance(relay_id, int):
                                events.append(
                                    TriggerEvent(
                                        zone_id=zone.id,
                                        relay_id=relay_id,
                                        active=False,
                                        timestamp=current_time,
                                    )
                                )
                        continue

                    if desired:
                        runtime.pending_exit_since = None

                        if runtime.actual_occupied:
                            runtime.pending_entry_since = None
                            continue

                        if runtime.pending_entry_since is None:
                            runtime.pending_entry_since = current_time
                            continue

                        if (current_time - runtime.pending_entry_since) >= entry_delay_s:
                            runtime.pending_entry_since = None
                            runtime.actual_occupied = True
                            if isinstance(relay_id, int):
                                events.append(
                                    TriggerEvent(
                                        zone_id=zone.id,
                                        relay_id=relay_id,
                                        active=True,
                                        timestamp=current_time,
                                    )
                                )

                        continue

                    runtime.pending_entry_since = None

                    if not runtime.actual_occupied:
                        runtime.pending_exit_since = None
                        continue

                    if runtime.pending_exit_since is None:
                        runtime.pending_exit_since = current_time
                        continue

                    if (current_time - runtime.pending_exit_since) >= exit_delay_s:
                        runtime.pending_exit_since = None
                        runtime.actual_occupied = False
                        if isinstance(relay_id, int):
                            events.append(
                                TriggerEvent(
                                    zone_id=zone.id,
                                    relay_id=relay_id,
                                    active=False,
                                    timestamp=current_time,
                                )
                            )

                camera_state.trigger_events = list(events)
                return events

            return self.runtime_state.update_camera_state(camera_id, _update_camera)
