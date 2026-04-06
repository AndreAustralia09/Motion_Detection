from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from app.core.zone_relay_policy import RelayOption, ZoneRelayPolicy, ZoneUpdateDecision
from app.models.project_model import CameraModel, ZoneModel
from app.models.runtime_state import AppRuntimeState


@dataclass(frozen=True)
class ZoneListItemData:
    zone_id: str
    label: str


@dataclass(frozen=True)
class RelayOptionView:
    relay_id: int | None
    label: str
    in_use: bool
    selectable: bool
    selected: bool


@dataclass(frozen=True)
class ZoneEditorState:
    zone_name: str
    relay_options: tuple[RelayOptionView, ...]
    selected_relay_id: int | None
    allow_shared_relay: bool
    enabled: bool
    relay_label_text: str
    relay_description_text: str
    shared_relay_note_text: str
    has_zone: bool
    can_test_relay: bool


@dataclass(frozen=True)
class ZoneChangeResult:
    selected_zone_id: str | None
    previous_zone_ids: set[str]


@dataclass(frozen=True)
class ZoneSelectionResult:
    camera: CameraModel | None
    zone: ZoneModel | None
    camera_index: int
    selected_zone_id: str | None


@dataclass(frozen=True)
class ZoneDeletionPlan:
    relay_id: int | None
    zone_id: str
    force_relay_off: bool


class ZoneCoordinationController:
    def __init__(
        self,
        *,
        zone_relay_policy: ZoneRelayPolicy,
        runtime_state: AppRuntimeState,
        get_cameras: Callable[[], Sequence[CameraModel]],
        get_active_cameras: Callable[[], Sequence[CameraModel]],
        get_total_relays: Callable[[], int],
        display_camera_name: Callable[[CameraModel], str],
    ) -> None:
        self.zone_relay_policy = zone_relay_policy
        self.runtime_state = runtime_state
        self._get_cameras = get_cameras
        self._get_active_cameras = get_active_cameras
        self._get_total_relays = get_total_relays
        self._display_camera_name = display_camera_name

    def find_zone_by_id(self, zone_id: str | None) -> tuple[CameraModel | None, ZoneModel | None]:
        if not zone_id:
            return None, None
        for camera in self._get_cameras():
            for zone in camera.zones:
                if zone.id == zone_id:
                    return camera, zone
        return None, None

    def current_zone(self, selected_zone_id: str | None) -> ZoneModel | None:
        _camera, zone = self.find_zone_by_id(selected_zone_id)
        return zone

    def build_zone_list_items(self) -> tuple[ZoneListItemData, ...]:
        items: list[ZoneListItemData] = []
        for camera in self._get_active_cameras():
            for zone in camera.zones:
                zone_name = (zone.name or "").strip() or "Unnamed Zone"
                relay_text = (
                    f"Relay {zone.relay_id}"
                    if isinstance(getattr(zone, "relay_id", None), int)
                    else "Unassigned"
                )
                enabled_text = "Enabled" if getattr(zone, "enabled", False) else "Disabled"
                items.append(
                    ZoneListItemData(
                        zone_id=zone.id,
                        label=f"{zone_name} -- {relay_text} -- {enabled_text} -- {self._display_camera_name(camera)}",
                    )
                )
        return tuple(items)

    def build_zone_editor_state(self, zone: ZoneModel | None, *, allow_shared_relay_override: bool | None = None) -> ZoneEditorState:
        allow_shared_relay = (
            bool(allow_shared_relay_override)
            if allow_shared_relay_override is not None
            else bool(getattr(zone, "allow_shared_relay", False)) if zone else False
        )
        relay_options = self.zone_relay_policy.build_relay_options(
            self._get_cameras(),
            total_relays=self._get_total_relays(),
            exclude_zone_id=getattr(zone, "id", None),
            allow_shared_relay=allow_shared_relay,
        )
        selected_relay_id = getattr(zone, "relay_id", None)
        options = tuple(
            RelayOptionView(
                relay_id=option.relay_id,
                label=option.label,
                in_use=option.in_use,
                selectable=option.selectable,
                selected=selected_relay_id == option.relay_id,
            )
            for option in relay_options
        )
        if zone and isinstance(zone.relay_id, int):
            relay_label_text = f"{(zone.name or 'Zone').strip()} Assigned to Relay: {zone.relay_id}"
            relay_description_text = "Ready to test selected zone relay"
            can_test_relay = True
        elif zone:
            relay_label_text = f"{(zone.name or 'Zone').strip()} Relay: Unassigned"
            relay_description_text = "Assign a relay before testing zone output"
            can_test_relay = False
        else:
            relay_label_text = "No relay selected"
            relay_description_text = "Select a zone to test its assigned relay"
            can_test_relay = False
        return ZoneEditorState(
            zone_name=zone.name if zone else "",
            relay_options=options,
            selected_relay_id=selected_relay_id,
            allow_shared_relay=allow_shared_relay,
            enabled=zone.enabled if zone else False,
            relay_label_text=relay_label_text,
            relay_description_text=relay_description_text,
            shared_relay_note_text="Multiple zones may drive the same relay. Relay OFF waits until all linked active zones clear.",
            has_zone=zone is not None,
            can_test_relay=can_test_relay,
        )

    def handle_zones_changed(
        self,
        *,
        current_camera: CameraModel | None,
        selected_zone_id: str | None,
        previous_zone_ids: set[str],
    ) -> ZoneChangeResult:
        if current_camera is None:
            return ZoneChangeResult(selected_zone_id=selected_zone_id, previous_zone_ids=set())

        current_ids = {zone.id for zone in current_camera.zones}
        new_ids = [zone_id for zone_id in current_ids if zone_id not in previous_zone_ids]
        for zone_id in new_ids:
            zone = next((candidate for candidate in current_camera.zones if candidate.id == zone_id), None)
            if zone is None:
                continue
            self.zone_relay_policy.initialize_new_zone_defaults(
                zone,
                cameras=self._get_cameras(),
                total_relays=self._get_total_relays(),
            )

        selected_camera, selected_zone = self.find_zone_by_id(selected_zone_id)
        normalized_selected_zone_id = selected_zone_id
        if selected_zone_id and (not selected_camera or not selected_zone):
            normalized_selected_zone_id = None

        return ZoneChangeResult(
            selected_zone_id=normalized_selected_zone_id,
            previous_zone_ids={zone.id for zone in current_camera.zones},
        )

    def resolve_zone_selection(self, zone_id: str | None) -> ZoneSelectionResult:
        camera, zone = self.find_zone_by_id(zone_id)
        if not camera or not zone:
            return ZoneSelectionResult(camera=None, zone=None, camera_index=-1, selected_zone_id=None)
        active_cameras = list(self._get_active_cameras())
        index = next((i for i, candidate in enumerate(active_cameras) if candidate.id == camera.id), -1)
        return ZoneSelectionResult(
            camera=camera,
            zone=zone,
            camera_index=index,
            selected_zone_id=zone.id,
        )

    def apply_zone_update(
        self,
        *,
        zone: ZoneModel,
        proposed_name: str,
        proposed_relay_id: int | None,
        allow_shared_relay: bool,
        enabled: bool,
    ) -> ZoneUpdateDecision:
        decision = self.zone_relay_policy.validate_zone_update(
            zone,
            self._get_cameras(),
            proposed_name=proposed_name,
            proposed_relay_id=proposed_relay_id,
            total_relays=self._get_total_relays(),
            allow_shared_relay=allow_shared_relay,
        )
        if not decision.ok:
            return decision
        zone.name = decision.zone_name
        zone.relay_id = decision.relay_id
        zone.allow_shared_relay = decision.allow_shared_relay
        zone.enabled = bool(enabled)
        return decision

    def build_zone_deletion_plan(self, *, camera: CameraModel, zone: ZoneModel) -> ZoneDeletionPlan:
        relay_id = getattr(zone, "relay_id", None)
        if not isinstance(relay_id, int):
            return ZoneDeletionPlan(relay_id=None, zone_id=zone.id, force_relay_off=False)
        zone_id = zone.id
        was_driving_relay = self.zone_relay_policy.zone_is_actively_driving(
            self.runtime_state,
            camera_id=camera.id,
            zone_id=zone_id,
        )
        force_relay_off = was_driving_relay and not self.zone_relay_policy.relay_has_other_active_driver(
            self._get_cameras(),
            self.runtime_state,
            relay_id=relay_id,
            exclude_zone_id=zone_id,
        )
        return ZoneDeletionPlan(relay_id=relay_id, zone_id=zone_id, force_relay_off=force_relay_off)
