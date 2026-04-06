from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RefreshStepName(str, Enum):
    REFRESH_CAMERA_SELECTOR = "refresh_camera_selector"
    REFRESH_CAMERA_TABS = "refresh_camera_tabs"
    REFRESH_ZONE_LIST = "refresh_zone_list"
    REFRESH_PROJECT_SUMMARY = "refresh_project_summary"
    REFRESH_STATUS_BAR = "refresh_status_bar"
    UPDATE_SYSTEM_RESOURCES = "update_system_resources"
    REBUILD_ZONE_CACHE = "rebuild_zone_cache"
    START_CAMERA_WORKERS = "start_camera_workers"
    REFRESH_APPLICATION_STATE = "refresh_application_state"
    REFRESH_SELECTED_CAMERA_VIEW = "refresh_selected_camera_view"
    UPDATE_PROJECT_DIRTY = "update_project_dirty"
    UPDATE_ZONE_SHORTCUTS = "update_zone_shortcuts"


@dataclass(frozen=True)
class RefreshStep:
    name: RefreshStepName | str
    value: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, RefreshStepName):
            object.__setattr__(self, "name", RefreshStepName(self.name))


@dataclass(frozen=True)
class RefreshPlan:
    steps: tuple[RefreshStep, ...]


class RefreshChoreographyController:
    def detected_cameras_refreshed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_CAMERA_SELECTOR),
                RefreshStep(RefreshStepName.UPDATE_SYSTEM_RESOURCES),
            )
        )

    def camera_activation_applied(self, *, changed: bool) -> RefreshPlan:
        steps = [
            RefreshStep(RefreshStepName.REFRESH_CAMERA_TABS),
            RefreshStep(RefreshStepName.UPDATE_SYSTEM_RESOURCES),
        ]
        if changed:
            steps.extend(
                [
                    RefreshStep(RefreshStepName.START_CAMERA_WORKERS),
                    RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Camera activation changed"),
                    RefreshStep(RefreshStepName.REFRESH_APPLICATION_STATE),
                ]
            )
        return RefreshPlan(steps=tuple(steps))

    def camera_display_settings_changed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_CAMERA_SELECTOR),
                RefreshStep(RefreshStepName.REFRESH_SELECTED_CAMERA_VIEW, True),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Camera display settings changed"),
            )
        )

    def camera_added(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_CAMERA_SELECTOR),
                RefreshStep(RefreshStepName.REFRESH_CAMERA_TABS),
                RefreshStep(RefreshStepName.REFRESH_PROJECT_SUMMARY),
                RefreshStep(RefreshStepName.REBUILD_ZONE_CACHE),
                RefreshStep(RefreshStepName.START_CAMERA_WORKERS),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Camera added"),
                RefreshStep(RefreshStepName.REFRESH_APPLICATION_STATE),
                RefreshStep(RefreshStepName.UPDATE_SYSTEM_RESOURCES),
            )
        )

    def camera_removed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_CAMERA_SELECTOR),
                RefreshStep(RefreshStepName.REFRESH_CAMERA_TABS),
                RefreshStep(RefreshStepName.REFRESH_ZONE_LIST),
                RefreshStep(RefreshStepName.REBUILD_ZONE_CACHE),
                RefreshStep(RefreshStepName.START_CAMERA_WORKERS),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Camera removed"),
                RefreshStep(RefreshStepName.REFRESH_APPLICATION_STATE),
                RefreshStep(RefreshStepName.UPDATE_SYSTEM_RESOURCES),
            )
        )

    def zone_layout_changed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_ZONE_LIST),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Zone layout changed"),
            )
        )

    def zone_settings_changed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_ZONE_LIST),
                RefreshStep(RefreshStepName.REFRESH_SELECTED_CAMERA_VIEW, True),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Zone settings changed"),
            )
        )

    def zone_deleted(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_ZONE_LIST),
                RefreshStep(RefreshStepName.REBUILD_ZONE_CACHE),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Zone deleted"),
                RefreshStep(RefreshStepName.UPDATE_ZONE_SHORTCUTS),
            )
        )

    def hardware_settings_changed(self) -> RefreshPlan:
        return RefreshPlan(
            steps=(
                RefreshStep(RefreshStepName.REFRESH_ZONE_LIST),
                RefreshStep(RefreshStepName.UPDATE_SYSTEM_RESOURCES),
                RefreshStep(RefreshStepName.REFRESH_SELECTED_CAMERA_VIEW, True),
                RefreshStep(RefreshStepName.UPDATE_PROJECT_DIRTY, "Hardware settings changed"),
            )
        )
