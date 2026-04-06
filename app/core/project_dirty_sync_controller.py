from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.project_dirty_tracker import ProjectDirtyTracker
from app.models.project_model import ProjectModel
from app.models.runtime_state import AppRuntimeState


@dataclass(frozen=True)
class ProjectSummaryPlan:
    camera_count: int
    zone_count: int


@dataclass(frozen=True)
class DirtyVisualPlan:
    project_display_name: str
    window_title: str
    project_cards: tuple[tuple[str, bool], ...]
    detection_cards: tuple[tuple[str, bool], ...]
    zone_cards: tuple[tuple[str, bool], ...]
    detection_setup_cards: tuple[tuple[str, bool], ...]
    hardware_cards: tuple[tuple[str, bool], ...]
    diagnostics_cards: tuple[tuple[str, bool], ...]
    tab_states: tuple[tuple[int, bool], ...]


@dataclass(frozen=True)
class DirtySyncPlan:
    is_dirty: bool
    visual_plan: DirtyVisualPlan
    should_record_dirty_event: bool = False


class ProjectDirtySyncController:
    def __init__(self, *, app_name: str, app_version: str) -> None:
        self._app_name = app_name
        self._app_version = app_version

    def build_project_summary(self, project: ProjectModel) -> ProjectSummaryPlan:
        return ProjectSummaryPlan(
            camera_count=len(project.cameras),
            zone_count=sum(len(camera.zones) for camera in project.cameras),
        )

    def reset_dirty_state(
        self,
        *,
        project: ProjectModel,
        runtime_state: AppRuntimeState,
        current_path: str | None,
        project_display_name: str,
    ) -> DirtySyncPlan:
        snapshot = ProjectDirtyTracker.serialize(project)
        runtime_state.reset_project_dirty(snapshot)
        return DirtySyncPlan(
            is_dirty=False,
            visual_plan=self.build_dirty_visual_plan(
                project=project,
                baseline_snapshot=runtime_state.get_project_snapshot(),
                current_path=current_path,
                project_display_name=project_display_name,
                is_dirty=False,
            ),
        )

    def update_dirty_state(
        self,
        *,
        project: ProjectModel,
        runtime_state: AppRuntimeState,
        current_path: str | None,
        project_display_name: str,
        reason: str,
        loading_project_ui: bool,
    ) -> DirtySyncPlan | None:
        if loading_project_ui:
            return None
        was_dirty = runtime_state.is_project_dirty()
        snapshot = ProjectDirtyTracker.serialize(project)
        is_dirty = runtime_state.update_project_dirty(snapshot, reason=reason)
        return DirtySyncPlan(
            is_dirty=is_dirty,
            visual_plan=self.build_dirty_visual_plan(
                project=project,
                baseline_snapshot=runtime_state.get_project_snapshot(),
                current_path=current_path,
                project_display_name=project_display_name,
                is_dirty=is_dirty,
            ),
            should_record_dirty_event=is_dirty and not was_dirty,
        )

    def build_restore_dirty_visuals(
        self,
        *,
        project: ProjectModel,
        runtime_state: AppRuntimeState,
        current_path: str | None,
        project_display_name: str,
    ) -> DirtySyncPlan:
        is_dirty = runtime_state.is_project_dirty()
        return DirtySyncPlan(
            is_dirty=is_dirty,
            visual_plan=self.build_dirty_visual_plan(
                project=project,
                baseline_snapshot=runtime_state.get_project_snapshot(),
                current_path=current_path,
                project_display_name=project_display_name,
                is_dirty=is_dirty,
            ),
        )

    def build_dirty_visual_plan(
        self,
        *,
        project: ProjectModel,
        baseline_snapshot: str,
        current_path: str | None,
        project_display_name: str,
        is_dirty: bool,
    ) -> DirtyVisualPlan:
        dirty_state = ProjectDirtyTracker.build_state(project, baseline_snapshot)
        title = f"{self._app_name} {self._app_version}"
        if current_path:
            title = f"{title} - {Path(current_path).stem}"
        elif is_dirty:
            title = f"{title} - Unsaved Project"
        if is_dirty:
            title += " *"

        return DirtyVisualPlan(
            project_display_name=project_display_name,
            window_title=title,
            project_cards=(
                ("cameras", dirty_state.section("project_cameras")),
            ),
            detection_cards=(
                ("camera_detection", dirty_state.section("camera_detection")),
                ("detection_settings", dirty_state.section("detection_settings")),
                ("zone_timer_settings", dirty_state.section("zone_timer_settings")),
                ("performance", dirty_state.section("performance")),
            ),
            zone_cards=(
                ("zones", dirty_state.section("zones")),
                ("zone_settings", dirty_state.section("zone_settings")),
            ),
            detection_setup_cards=(
                ("detection_area", dirty_state.section("detection_area")),
                ("ignore_areas", dirty_state.section("ignore_areas")),
            ),
            hardware_cards=(
                ("serial", dirty_state.section("serial")),
                ("relays", dirty_state.section("relays")),
            ),
            diagnostics_cards=(
                ("logging", dirty_state.section("logging")),
            ),
            tab_states=(
                (0, dirty_state.tab_states().get("project", False)),
                (1, dirty_state.tab_states().get("cameras", False)),
                (2, dirty_state.tab_states().get("zones", False)),
                (3, dirty_state.tab_states().get("detection_setup", False)),
                (4, dirty_state.tab_states().get("serial", False)),
                (5, dirty_state.tab_states().get("system_resources", False)),
            ),
        )
