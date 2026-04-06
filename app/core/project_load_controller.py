from __future__ import annotations

from typing import Callable


class ProjectLoadController:
    def __init__(
        self,
        *,
        set_loading_project_ui: Callable[[bool], None],
        set_app_state: Callable[[str], None],
        prepare_for_project_load: Callable[[], None],
        apply_project_ui_state: Callable[[], None],
        apply_hardware_ui_state: Callable[[], None],
        refresh_post_load_state: Callable[[], None],
        schedule_auto_connect: Callable[[], None],
        finalize_successful_project_load: Callable[..., None],
        handle_project_load_failure: Callable[[], None],
    ) -> None:
        self._set_loading_project_ui = set_loading_project_ui
        self._set_app_state = set_app_state
        self._prepare_for_project_load = prepare_for_project_load
        self._apply_project_ui_state = apply_project_ui_state
        self._apply_hardware_ui_state = apply_hardware_ui_state
        self._refresh_post_load_state = refresh_post_load_state
        self._schedule_auto_connect = schedule_auto_connect
        self._finalize_successful_project_load = finalize_successful_project_load
        self._handle_project_load_failure = handle_project_load_failure

    def apply_loaded_project(
        self,
        *,
        record_project_loaded: bool = True,
        reset_dirty_state: bool = True,
    ) -> None:
        self._set_loading_project_ui(True)
        self._set_app_state("starting")
        self._prepare_for_project_load()

        try:
            self._apply_project_ui_state()
            self._apply_hardware_ui_state()
            self._refresh_post_load_state()
            self._schedule_auto_connect()
            self._finalize_successful_project_load(
                record_project_loaded=record_project_loaded,
                reset_dirty_state=reset_dirty_state,
            )
        except Exception:
            self._handle_project_load_failure()
            raise
        finally:
            self._set_loading_project_ui(False)
