from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from app.core.project_manager import ProjectManager
from app.models.project_model import ProjectModel
from app.models.runtime_state import AppRuntimeState, ProjectDirtySnapshot


UnsavedDecision = Literal["save", "discard", "cancel"]


@dataclass(frozen=True)
class SessionActionResult:
    ok: bool
    cancelled: bool = False
    path: str = ""
    error: str = ""


class ProjectSessionController:
    def __init__(
        self,
        *,
        project_manager: ProjectManager,
        runtime_state: AppRuntimeState,
        commit_pending_project_edits: Callable[[], bool],
        prompt_unsaved_changes: Callable[[str], UnsavedDecision],
        save_without_prompt: Callable[[], bool],
        prepare_for_project_open: Callable[[], None],
        load_project_into_ui: Callable[..., None],
        set_app_state: Callable[[str], None],
        record_runtime_transition: Callable[..., None],
        reset_project_dirty_state: Callable[[], None],
        refresh_application_state: Callable[[], None],
    ) -> None:
        self.project_manager = project_manager
        self.runtime_state = runtime_state
        self._commit_pending_project_edits = commit_pending_project_edits
        self._prompt_unsaved_changes = prompt_unsaved_changes
        self._save_without_prompt = save_without_prompt
        self._prepare_for_project_open = prepare_for_project_open
        self._load_project_into_ui = load_project_into_ui
        self._set_app_state = set_app_state
        self._record_runtime_transition = record_runtime_transition
        self._reset_project_dirty_state = reset_project_dirty_state
        self._refresh_application_state = refresh_application_state

    def confirm_safe_to_discard_changes(self, *, action_name: str) -> bool:
        if not self.runtime_state.is_project_dirty():
            return True

        result = self._prompt_unsaved_changes(action_name)
        if result == "cancel":
            return False
        if result == "discard":
            return True
        return self._save_without_prompt()

    def open_project(self, path: str) -> SessionActionResult:
        previous_project = self.project_manager.current_project
        previous_path = self.project_manager.current_path
        previous_dirty_state = self.runtime_state.get_project_dirty_state()

        try:
            self._set_app_state("starting")
            self._prepare_for_project_open()
            next_project = self.project_manager.load_project(path)
            self.project_manager.set_current_project(next_project, path)
            self._load_project_into_ui()
            return SessionActionResult(ok=True, path=path)
        except Exception as exc:
            rollback_error = self._rollback_failed_open(
                previous_project=previous_project,
                previous_path=previous_path,
                previous_dirty_state=previous_dirty_state,
            )
            if rollback_error is not None:
                self._set_app_state("error")
                return SessionActionResult(
                    ok=False,
                    error=f"{exc} (rollback failed: {rollback_error})",
                )
            return SessionActionResult(ok=False, error=str(exc))

    def _rollback_failed_open(
        self,
        *,
        previous_project: ProjectModel,
        previous_path: str | None,
        previous_dirty_state: ProjectDirtySnapshot,
    ) -> str | None:
        try:
            self.project_manager.set_current_project(previous_project, previous_path)
            self.runtime_state.restore_project_dirty_state(previous_dirty_state)
            self._prepare_for_project_open()
            self._load_project_into_ui(
                record_project_loaded=False,
                reset_dirty_state=False,
            )
        except Exception as exc:
            return str(exc)
        return None

    def save_project(
        self,
        *,
        path: str | None = None,
        commit_pending_edits: bool = True,
    ) -> SessionActionResult:
        if commit_pending_edits and not self._commit_pending_project_edits():
            return SessionActionResult(ok=False, cancelled=True)

        try:
            self._set_app_state("saving")
            saved_path = self.project_manager.save_project(path)
            self._record_runtime_transition(
                "project_saved",
                f"Project saved: {saved_path.split('\\')[-1].split('/')[-1]}",
                log=True,
                path=saved_path,
            )
            self._reset_project_dirty_state()
            self._refresh_application_state()
            return SessionActionResult(ok=True, path=saved_path)
        except Exception as exc:
            self._set_app_state("error")
            return SessionActionResult(ok=False, error=str(exc))
