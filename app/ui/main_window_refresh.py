from __future__ import annotations

from collections.abc import Callable

from app.core.refresh_choreography_controller import RefreshPlan, RefreshStep, RefreshStepName


class MainWindowRefreshCoordinator:
    """Applies refresh choreography plans to MainWindow UI callbacks."""

    def __init__(
        self,
        *,
        refresh_camera_selector: Callable[[], None],
        refresh_camera_tabs: Callable[[], None],
        refresh_zone_list: Callable[[], None],
        refresh_project_summary: Callable[[], None],
        refresh_status_bar: Callable[[], None],
        update_system_resources: Callable[[], None],
        rebuild_zone_cache: Callable[[], None],
        start_camera_workers: Callable[[], None],
        refresh_application_state: Callable[[], None],
        refresh_selected_camera_view: Callable[..., None],
        update_project_dirty_state: Callable[[str], None],
        update_zone_shortcuts: Callable[[], None],
        queue_layout_refresh: Callable[..., None],
    ) -> None:
        self._refresh_selected_camera_view = refresh_selected_camera_view
        self._update_project_dirty_state = update_project_dirty_state
        self._queue_layout_refresh = queue_layout_refresh
        self._handlers: dict[RefreshStepName, Callable[[RefreshStep], None]] = {
            RefreshStepName.REFRESH_CAMERA_SELECTOR: lambda step: refresh_camera_selector(),
            RefreshStepName.REFRESH_CAMERA_TABS: lambda step: refresh_camera_tabs(),
            RefreshStepName.REFRESH_ZONE_LIST: lambda step: refresh_zone_list(),
            RefreshStepName.REFRESH_PROJECT_SUMMARY: lambda step: refresh_project_summary(),
            RefreshStepName.REFRESH_STATUS_BAR: lambda step: refresh_status_bar(),
            RefreshStepName.UPDATE_SYSTEM_RESOURCES: lambda step: update_system_resources(),
            RefreshStepName.REBUILD_ZONE_CACHE: lambda step: rebuild_zone_cache(),
            RefreshStepName.START_CAMERA_WORKERS: lambda step: start_camera_workers(),
            RefreshStepName.REFRESH_APPLICATION_STATE: lambda step: refresh_application_state(),
            RefreshStepName.REFRESH_SELECTED_CAMERA_VIEW: self._refresh_selected_camera_step,
            RefreshStepName.UPDATE_PROJECT_DIRTY: self._update_project_dirty_step,
            RefreshStepName.UPDATE_ZONE_SHORTCUTS: lambda step: update_zone_shortcuts(),
        }

    def apply_plan(self, plan: RefreshPlan) -> None:
        for step in plan.steps:
            step_name = self._step_name(step)
            handler = self._handlers.get(step_name)
            if handler is None:
                raise ValueError(f"Unknown refresh step: {step.name}")
            handler(step)
        self._queue_layout_refresh(reason="refresh_plan:" + ",".join(self._step_name(step).value for step in plan.steps))

    @staticmethod
    def _step_name(step: RefreshStep) -> RefreshStepName:
        if isinstance(step.name, RefreshStepName):
            return step.name
        return RefreshStepName(step.name)

    def _refresh_selected_camera_step(self, step: RefreshStep) -> None:
        self._refresh_selected_camera_view(force=bool(step.value))

    def _update_project_dirty_step(self, step: RefreshStep) -> None:
        self._update_project_dirty_state(str(step.value or "Project changed"))
