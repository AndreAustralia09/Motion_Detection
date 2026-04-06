from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from app.models.events import TriggerEvent
from app.models.project_model import CameraModel, ZoneModel
from app.models.runtime_state import AppRuntimeState


@dataclass(frozen=True)
class RelayOption:
    relay_id: int | None
    label: str
    in_use: bool
    selectable: bool


@dataclass(frozen=True)
class ZoneUpdateDecision:
    ok: bool
    zone_name: str
    relay_id: int | None
    allow_shared_relay: bool
    error_title: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class TriggerRelayDecision:
    event: TriggerEvent
    relay_id: int
    zone_id: str
    desired_state: bool


class ZoneRelayPolicy:
    @staticmethod
    def _zone_display_name(zone: ZoneModel, relay_id: int) -> str:
        return (zone.name or "").strip() or f"Zone {relay_id}"

    def relay_assignment_summary(
        self,
        cameras: Sequence[CameraModel],
        *,
        relay_id: int,
        exclude_zone_id: str | None = None,
    ) -> str:
        assigned_zones = self.zones_for_relay(cameras, relay_id, exclude_zone_id=exclude_zone_id)
        zone_names = [self._zone_display_name(zone, relay_id) for zone in assigned_zones]
        if not zone_names:
            return f"Relay {relay_id:02d}"
        if len(zone_names) == 1:
            return f"Relay {relay_id:02d} - assigned to {zone_names[0]}"
        preview_names = ", ".join(zone_names[:2])
        remaining = len(zone_names) - 2
        extra_text = f" +{remaining} more" if remaining > 0 else ""
        return f"Relay {relay_id:02d} - Shared by {preview_names}{extra_text}"

    @staticmethod
    def default_zone_name(cameras: Sequence[CameraModel], *, exclude_zone_id: str | None = None) -> str:
        used_indexes: set[int] = set()
        for _camera, zone in ZoneRelayPolicy().iter_zones(cameras):
            if zone.id == exclude_zone_id:
                continue
            name = (zone.name or "").strip()
            match = re.fullmatch(r"Zone(\d{2})", name, flags=re.IGNORECASE)
            if match:
                used_indexes.add(int(match.group(1)))

        index = 1
        while index in used_indexes:
            index += 1
        return f"Zone{index:02d}"

    def iter_zones(self, cameras: Sequence[CameraModel]) -> Iterable[tuple[CameraModel, ZoneModel]]:
        for camera in cameras:
            for zone in camera.zones:
                yield camera, zone

    def used_relay_ids(
        self,
        cameras: Sequence[CameraModel],
        *,
        exclude_zone_id: str | None = None,
    ) -> set[int]:
        used: set[int] = set()
        for _camera, zone in self.iter_zones(cameras):
            if exclude_zone_id is not None and zone.id == exclude_zone_id:
                continue
            relay_id = getattr(zone, "relay_id", None)
            if isinstance(relay_id, int):
                used.add(relay_id)
        return used

    def zones_for_relay(
        self,
        cameras: Sequence[CameraModel],
        relay_id: int,
        *,
        exclude_zone_id: str | None = None,
    ) -> tuple[ZoneModel, ...]:
        matching: list[ZoneModel] = []
        for _camera, zone in self.iter_zones(cameras):
            if exclude_zone_id is not None and zone.id == exclude_zone_id:
                continue
            zone_relay_id = getattr(zone, "relay_id", None)
            if isinstance(zone_relay_id, int) and zone_relay_id == int(relay_id):
                matching.append(zone)
        return tuple(matching)

    def relay_is_shareable(
        self,
        cameras: Sequence[CameraModel],
        *,
        relay_id: int,
        exclude_zone_id: str | None = None,
    ) -> bool:
        assigned_zones = self.zones_for_relay(cameras, relay_id, exclude_zone_id=exclude_zone_id)
        return bool(assigned_zones) and all(bool(getattr(zone, "allow_shared_relay", False)) for zone in assigned_zones)

    def next_zone_name(
        self,
        cameras: Sequence[CameraModel],
        *,
        exclude_zone_id: str | None = None,
    ) -> str:
        return self.default_zone_name(cameras, exclude_zone_id=exclude_zone_id)

    def first_available_relay(
        self,
        cameras: Sequence[CameraModel],
        *,
        total_relays: int,
        exclude_zone_id: str | None = None,
    ) -> int | None:
        used_relays = self.used_relay_ids(cameras, exclude_zone_id=exclude_zone_id)
        for relay_id in range(1, int(total_relays) + 1):
            if relay_id not in used_relays:
                return relay_id
        return None

    def initialize_new_zone_defaults(
        self,
        zone: ZoneModel,
        *,
        cameras: Sequence[CameraModel],
        total_relays: int,
    ) -> None:
        if not (zone.name or "").strip():
            zone.name = self.next_zone_name(cameras, exclude_zone_id=zone.id)
        relay_id = getattr(zone, "relay_id", None)
        relay_in_range = isinstance(relay_id, int) and 1 <= relay_id <= int(total_relays)
        if relay_in_range and relay_id not in self.used_relay_ids(cameras, exclude_zone_id=zone.id):
            return
        if getattr(zone, "allow_shared_relay", False) and relay_in_range:
            return
        fallback_relay = self.first_available_relay(
            cameras,
            total_relays=total_relays,
            exclude_zone_id=zone.id,
        )
        zone.relay_id = fallback_relay

    def build_relay_options(
        self,
        cameras: Sequence[CameraModel],
        *,
        total_relays: int,
        exclude_zone_id: str | None = None,
        allow_shared_relay: bool = False,
    ) -> list[RelayOption]:
        used_relays = self.used_relay_ids(cameras, exclude_zone_id=exclude_zone_id)

        options: list[RelayOption] = [
            RelayOption(
                relay_id=None,
                label="Unassigned",
                in_use=False,
                selectable=True,
            )
        ]
        for relay_id in range(1, int(total_relays) + 1):
            in_use = relay_id in used_relays
            label = self.relay_assignment_summary(
                cameras,
                relay_id=relay_id,
                exclude_zone_id=exclude_zone_id,
            )
            shareable = in_use and self.relay_is_shareable(
                cameras,
                relay_id=relay_id,
                exclude_zone_id=exclude_zone_id,
            )
            options.append(
                RelayOption(
                    relay_id=relay_id,
                    label=label,
                    in_use=in_use,
                    selectable=(allow_shared_relay and shareable) or not in_use,
                )
            )
        return options

    def validate_zone_update(
        self,
        zone: ZoneModel,
        cameras: Sequence[CameraModel],
        *,
        proposed_name: str,
        proposed_relay_id: int | None,
        total_relays: int,
        allow_shared_relay: bool,
    ) -> ZoneUpdateDecision:
        normalized_name = proposed_name.strip()
        if normalized_name:
            duplicate = any(
                existing_zone.id != zone.id
                and (existing_zone.name or "").strip().lower() == normalized_name.lower()
                for _camera, existing_zone in self.iter_zones(cameras)
            )
            if duplicate:
                return ZoneUpdateDecision(
                    ok=False,
                    zone_name=zone.name,
                    relay_id=zone.relay_id,
                    allow_shared_relay=zone.allow_shared_relay,
                    error_title="Zone Name Already In Use",
                    error_message=f"The name '{normalized_name}' is already used by another zone.",
                )
        else:
            normalized_name = self.next_zone_name(cameras, exclude_zone_id=zone.id)

        if proposed_relay_id is not None and not (1 <= int(proposed_relay_id) <= int(total_relays)):
            return ZoneUpdateDecision(
                ok=False,
                zone_name=normalized_name,
                relay_id=zone.relay_id,
                allow_shared_relay=zone.allow_shared_relay,
                error_title="Invalid Relay Assignment",
                error_message=f"Relay {proposed_relay_id} is outside the configured hardware range.",
            )

        if proposed_relay_id is not None and proposed_relay_id in self.used_relay_ids(cameras, exclude_zone_id=zone.id):
            if not allow_shared_relay:
                return ZoneUpdateDecision(
                    ok=False,
                    zone_name=normalized_name,
                    relay_id=zone.relay_id,
                    allow_shared_relay=zone.allow_shared_relay,
                    error_title="Relay Already In Use",
                    error_message=f"Relay {proposed_relay_id} is already assigned to another zone.",
                )
            if not self.relay_is_shareable(cameras, relay_id=proposed_relay_id, exclude_zone_id=zone.id):
                return ZoneUpdateDecision(
                    ok=False,
                    zone_name=normalized_name,
                    relay_id=zone.relay_id,
                    allow_shared_relay=zone.allow_shared_relay,
                    error_title="Shared Relay Requires Mutual Opt-In",
                    error_message=(
                        f"Relay {proposed_relay_id} is assigned to a zone that does not allow shared relay assignment."
                    ),
                )

        return ZoneUpdateDecision(
            ok=True,
            zone_name=normalized_name,
            relay_id=proposed_relay_id,
            allow_shared_relay=bool(allow_shared_relay),
        )

    def zone_is_actively_driving(
        self,
        runtime_state: AppRuntimeState,
        *,
        camera_id: str,
        zone_id: str,
    ) -> bool:
        camera_state = runtime_state.get_camera_snapshot(camera_id)
        zone_state = camera_state.zone_states.get(zone_id)
        return bool(zone_state and zone_state.actual_occupied)

    def relay_has_other_active_driver(
        self,
        cameras: Sequence[CameraModel],
        runtime_state: AppRuntimeState,
        *,
        relay_id: int,
        exclude_zone_id: str | None = None,
    ) -> bool:
        for camera in cameras:
            camera_state = runtime_state.get_camera_snapshot(camera.id)
            for zone in camera.zones:
                zone_relay_id = getattr(zone, "relay_id", None)
                if zone.id == exclude_zone_id or not isinstance(zone_relay_id, int) or zone_relay_id != int(relay_id):
                    continue
                zone_state = camera_state.zone_states.get(zone.id)
                if zone_state and zone_state.actual_occupied:
                    return True
        return False

    def filter_trigger_events(
        self,
        events: Sequence[TriggerEvent],
        *,
        cameras: Sequence[CameraModel],
        runtime_state: AppRuntimeState,
    ) -> list[TriggerRelayDecision]:
        valid_zone_ids = {zone.id for _camera, zone in self.iter_zones(cameras)}
        decisions: list[TriggerRelayDecision] = []
        for event in events:
            relay_id = getattr(event, "relay_id", None)
            zone_id = getattr(event, "zone_id", None)
            if not isinstance(relay_id, int) or zone_id not in valid_zone_ids:
                continue

            desired_state = bool(getattr(event, "active", False))
            if not desired_state and self.relay_has_other_active_driver(
                cameras,
                runtime_state,
                relay_id=relay_id,
                exclude_zone_id=zone_id,
            ):
                continue

            decisions.append(
                TriggerRelayDecision(
                    event=event,
                    relay_id=relay_id,
                    zone_id=zone_id,
                    desired_state=desired_state,
                )
            )
        return decisions
