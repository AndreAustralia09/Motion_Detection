from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QStandardItem
from PySide6.QtWidgets import QFileDialog, QDialogButtonBox, QHBoxLayout, QLineEdit, QListWidgetItem, QMainWindow, QTabBar, QVBoxLayout, QWidget

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

try:
    import torch
except Exception:  # pragma: no cover
    torch = None

from app.core.camera_manager import CameraManager
from app.core.camera_pipeline import CameraPipeline
from app.core.camera_display_controller import CameraDisplayController, CameraDisplayViewState, CameraSelectionPlan
from app.core.detector_service import DetectorService
from app.core.log_manager import LogManager
from app.core.occupancy_engine import OccupancyEngine
from app.core.app_state_controller import AppStateController
from app.core.project_dirty_sync_controller import ProjectDirtySyncController, DirtySyncPlan
from app.core.project_load_controller import ProjectLoadController
from app.core.refresh_choreography_controller import RefreshChoreographyController, RefreshPlan
from app.core.project_session_controller import ProjectSessionController
from app.core.project_manager import ProjectManager
from app.core.relay_manager import RelayManager
from app.core.serial_manager import SerialManager
from app.core.serial_runtime_controller import SerialRuntimeController
from app.core.status_summary_controller import StatusSummaryController
from app.core.trigger_dispatch_controller import TriggerDispatchController
from app.core.trigger_engine import TriggerEngine
from app.core.zone_coordination_controller import ZoneCoordinationController
from app.core.zone_relay_policy import ZoneRelayPolicy
from app.models.project_model import CameraModel, IgnoreAreaModel, ZoneModel
from app.models.runtime_state import AppRuntimeState
from app.storage.settings_repository import DEFAULT_APP_SETTINGS
from app.ui.camera_view import CameraView
from app.ui.confirm_dialog import ConfirmDialog
from app.ui.detection_tab import DetectionTab
from app.ui.detection_setup_tab import DetectionSetupTab
from app.ui.hardware_logs_tab import HardwareLogsTab
from app.ui.main_window_hardware import HardwareUiCoordinator
from app.ui.main_window_layout import MainWindowLayoutCoordinator
from app.ui.main_window_refresh import MainWindowRefreshCoordinator
from app.ui.multi_row_tab_widget import MultiRowTabWidget
from app.ui.preferences_tab import PreferencesTab
from app.ui.project_tab import ProjectTab
from app.ui.status_bar import StatusBarWidget
from app.ui.system_resources_tab import SystemResourcesTab
from app.ui.theme import build_stylesheet
from app.ui.ui_metrics import (
    MainWindowMetrics,
    Margins,
    Spacing,
    UI_DENSITY_ENV_VAR,
    resolve_ui_density_for_screen,
    set_ui_density,
)
from app.ui.windows_theme import apply_native_title_bar_theme
from app.ui.zones_tab import ZonesTab
from app.utils.app_paths import APP_NAME, APP_VERSION, app_data_dir, resolve_model_path


class MainWindow(QMainWindow):
    detector_status_message_received = Signal(str)

    def __init__(
        self,
        project_manager: ProjectManager,
        camera_manager: CameraManager,
        relay_manager: RelayManager,
        serial_manager: SerialManager,
        log_manager: LogManager,
        runtime_state: AppRuntimeState,
        app_settings: dict | None = None,
    ) -> None:
        super().__init__()

        self.project_manager = project_manager
        self.camera_manager = camera_manager
        self.relay_manager = relay_manager
        self.serial_manager = serial_manager
        self.log_manager = log_manager
        self.runtime_state = runtime_state
        self._process = psutil.Process() if psutil is not None else None
        self._app_settings = dict(app_settings or {})
        self._theme_name = "Light"
        self._ui_density = self._select_ui_density()

        self.detector = DetectorService(
            person_model_path=resolve_model_path("yolov8n.pt"),
            face_model_path=resolve_model_path("yolov8-face.pt"),
            hand_model_path=resolve_model_path("yolov8-hand.pt"),
        )
        self.detector.set_status_callback(self._handle_detector_status_message)
        self.occupancy_engine = OccupancyEngine()
        self.trigger_engine = TriggerEngine(runtime_state=self.runtime_state)
        self.zone_relay_policy = ZoneRelayPolicy()
        self.camera_pipeline = CameraPipeline(
            camera_manager=self.camera_manager,
            detector=self.detector,
            occupancy_engine=self.occupancy_engine,
            trigger_engine=self.trigger_engine,
            runtime_state=self.runtime_state,
        )
        self.trigger_dispatch_controller = TriggerDispatchController(
            zone_relay_policy=self.zone_relay_policy,
            runtime_state=self.runtime_state,
            relay_manager=self.relay_manager,
            serial_manager=self.serial_manager,
            get_cameras=lambda: self.project_manager.current_project.cameras,
        )
        self.zone_coordination_controller = ZoneCoordinationController(
            zone_relay_policy=self.zone_relay_policy,
            runtime_state=self.runtime_state,
            get_cameras=lambda: self.project_manager.current_project.cameras,
            get_active_cameras=self.active_project_cameras,
            get_total_relays=lambda: self.project_manager.current_project.hardware.total_relays,
            display_camera_name=self._display_camera_name,
        )
        self.camera_display_controller = CameraDisplayController(
            camera_pipeline=self.camera_pipeline,
            runtime_state=self.runtime_state,
            get_active_cameras=self.active_project_cameras,
            find_zone_by_id=self.zone_coordination_controller.find_zone_by_id,
            display_camera_name=self._display_camera_name,
            get_serial_mode=lambda: self.project_manager.current_project.hardware.serial_mode,
        )
        self.project_session = ProjectSessionController(
            project_manager=self.project_manager,
            runtime_state=self.runtime_state,
            commit_pending_project_edits=self._commit_pending_project_edits,
            prompt_unsaved_changes=self._prompt_unsaved_changes,
            save_without_prompt=self._save_project_without_prompt,
            prepare_for_project_open=self._prepare_for_project_open,
            load_project_into_ui=self.load_project_into_ui,
            set_app_state=self._set_app_state,
            record_runtime_transition=self._record_runtime_transition,
            reset_project_dirty_state=self._reset_project_dirty_state,
            refresh_application_state=self._refresh_application_state,
        )
        self.project_dirty_sync_controller = ProjectDirtySyncController(
            app_name=APP_NAME,
            app_version=APP_VERSION,
        )
        self.app_state_controller = AppStateController()
        self.status_summary_controller = StatusSummaryController(
            runtime_state=self.runtime_state,
            serial_manager=self.serial_manager,
            relay_manager=self.relay_manager,
            camera_manager=self.camera_manager,
            get_project=lambda: self.project_manager.current_project,
            display_camera_name=self._display_camera_name,
        )
        self.project_load_controller = ProjectLoadController(
            set_loading_project_ui=self._set_loading_project_ui,
            set_app_state=self._set_app_state,
            prepare_for_project_load=self._prepare_for_project_load_application,
            apply_project_ui_state=self._apply_loaded_project_ui_state,
            apply_hardware_ui_state=self._apply_loaded_hardware_ui_state,
            refresh_post_load_state=self._refresh_after_project_load,
            schedule_auto_connect=lambda: QTimer.singleShot(0, self._auto_connect_serial_if_needed),
            finalize_successful_project_load=self._finalize_successful_project_load,
            handle_project_load_failure=self._handle_project_load_failure,
        )
        self.refresh_choreography_controller = RefreshChoreographyController()
        self.refresh_coordinator = MainWindowRefreshCoordinator(
            refresh_camera_selector=self.refresh_camera_selector,
            refresh_camera_tabs=self.refresh_camera_tabs,
            refresh_zone_list=self.refresh_zone_list,
            refresh_project_summary=self.refresh_project_summary,
            refresh_status_bar=self.refresh_status_bar,
            update_system_resources=self.update_system_resources,
            rebuild_zone_cache=self.rebuild_zone_cache,
            start_camera_workers=self.start_camera_workers,
            refresh_application_state=self._refresh_application_state,
            refresh_selected_camera_view=self.refresh_selected_camera_view,
            update_project_dirty_state=self._update_project_dirty_state,
            update_zone_shortcuts=self._update_zone_shortcuts,
            queue_layout_refresh=self._queue_layout_refresh,
        )
        self.current_camera_id: str | None = None
        self._updating_zone_ui = False
        self._previous_zone_ids_by_camera: dict[str, set[str]] = {}
        self._last_displayed_frame_version: dict[str, int] = {}
        self._last_logged_camera_state: dict[str, str] = {}
        self._last_logged_reconnect_attempt: dict[str, int] = {}
        self._last_detection_status_message = ""
        self._loading_project_ui = False
        self._detected_camera_sources: list[object] = []
        self._cpu_summary_text = "--"
        self.layout_coordinator = MainWindowLayoutCoordinator(self, self.log_manager)
        self._ui_scaling_diagnostics_enabled = self.layout_coordinator.diagnostics_enabled

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(self._initial_window_size())
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(*Margins.MAIN_WINDOW)
        root.setSpacing(Spacing.WINDOW)
        left = QVBoxLayout()
        left.setSpacing(Spacing.XL)
        right = QVBoxLayout()
        right.setSpacing(Spacing.LG)
        root.addLayout(left, MainWindowMetrics.LEFT_STRETCH)
        root.addLayout(right, MainWindowMetrics.RIGHT_STRETCH)

        self.camera_tabs = QTabBar(movable=False, tabsClosable=False)
        self.camera_tabs.setObjectName("CameraTabs")
        left.addWidget(self.camera_tabs)

        self.camera_view = CameraView()
        self.camera_view.setObjectName("CameraSurface")
        self.camera_view.set_all_cameras_provider(lambda: self.project_manager.current_project.cameras)
        self.camera_view.set_diagnostics_logger(self._log_ui_scaling_child_event)
        left.addWidget(self.camera_view, 1)

        self.status_widget = StatusBarWidget()
        left.addWidget(self.status_widget)

        self.right_tabs = MultiRowTabWidget()
        self.project_tab = ProjectTab()
        self.detection_tab = DetectionTab()
        self.zones_tab = ZonesTab()
        self.detection_setup_tab = DetectionSetupTab()
        self.hardware_tab = HardwareLogsTab()
        self.system_resources_tab = SystemResourcesTab()
        self.preferences_tab = PreferencesTab()

        self.right_tabs.addTab(self.project_tab, "Project")
        self.right_tabs.addTab(self.detection_tab, "Cameras")
        self.right_tabs.addTab(self.zones_tab, "Zones")
        self.right_tabs.addTab(self.detection_setup_tab, "Area Setup")
        self.right_tabs.addTab(self.hardware_tab, "Hardware")
        self.right_tabs.addTab(self.system_resources_tab, "Diagnostics")
        self.right_tabs.addTab(self.preferences_tab, "Preferences")
        right.addWidget(self.right_tabs)
        self._zones_tab_index = 2

        self.project_tab.open_requested.connect(self.open_project)
        self.project_tab.save_requested.connect(self.save_project)
        self.project_tab.save_as_requested.connect(self.save_project_as)
        self.project_tab.camera_selection_changed.connect(self.apply_camera_selection)
        self.project_tab.camera_mirror_changed.connect(self.apply_camera_orientation_settings)
        self.project_tab.camera_flip_changed.connect(self.apply_camera_orientation_settings)
        self.project_tab.remove_camera_requested.connect(self.remove_project_camera)

        self.zones_tab.add_zone_requested.connect(self.camera_view.begin_add_zone)
        self.zones_tab.delete_zone_requested.connect(self.delete_zone)
        self.zones_tab.zone_selection_changed.connect(self.select_zone_by_name)
        self.zones_tab.update_zone_requested.connect(self.apply_zone_properties)
        self.zones_tab.allow_shared_relay.stateChanged.connect(self.refresh_zone_relay_options)
        self.detection_setup_tab.add_detection_area_requested.connect(self.camera_view.begin_add_detection_area)
        self.detection_setup_tab.modify_detection_area_requested.connect(self.toggle_modify_detection_area)
        self.detection_setup_tab.clear_detection_area_requested.connect(self.delete_detection_area)
        self.detection_setup_tab.add_ignore_area_requested.connect(self.camera_view.begin_add_ignore_area)
        self.detection_setup_tab.modify_ignore_area_requested.connect(self.toggle_modify_ignore_area)
        self.detection_setup_tab.delete_ignore_area_requested.connect(self.delete_ignore_area)
        self.detection_setup_tab.ignore_area_selection_changed.connect(self.select_ignore_area_by_name)

        self.camera_view.zone_selected.connect(self.select_zone_by_id)
        self.camera_view.zones_changed.connect(self.on_zones_changed)
        self.camera_view.detection_area_changed.connect(self.on_detection_area_changed)
        self.camera_view.detection_area_mode_changed.connect(self.refresh_detection_area_editor)
        self.camera_view.detection_area_error.connect(self.on_detection_area_error)
        self.camera_view.ignore_area_mode_changed.connect(self.refresh_ignore_area_editor)
        self.camera_view.ignore_area_error.connect(self.on_ignore_area_error)
        self.camera_view.ignore_area_selected.connect(self.select_ignore_area_by_id)
        self.camera_view.ignore_areas_changed.connect(self.on_ignore_areas_changed)

        self.detection_tab.settings_changed.connect(self.apply_detection_settings)
        self.detection_tab.refresh_detected_cameras_requested.connect(self.refresh_detected_cameras)
        self.detection_tab.add_camera_requested.connect(self.add_project_camera)
        self.preferences_tab.theme_changed.connect(self.apply_theme)
        self.preferences_tab.preferences_changed.connect(self.sync_app_preferences_from_ui)
        self.preferences_tab.show_fps_overlay.toggled.connect(self.apply_display_preferences)
        self.system_resources_tab.debug_logging.stateChanged.connect(self.apply_debug_logging)
        self.system_resources_tab.clear_log_requested.connect(self.clear_log_view)
        self.detection_tab.performance_changed.connect(self.apply_performance_settings)
        self.detection_tab.preset_selected.connect(self.apply_performance_preset)
        self.detector_status_message_received.connect(self._handle_detector_status_message_on_ui)

        self.log_manager.subscribe(self.system_resources_tab.append_log)
        self.system_resources_tab.log_path = self.log_manager.get_log_file_path()

        self.camera_tabs.currentChanged.connect(self.on_camera_tab_changed)
        self.right_tabs.currentChanged.connect(self.on_right_tab_changed)

        self.shortcut_add_zone = QShortcut(QKeySequence("Z"), self)
        self.shortcut_add_zone.setContext(Qt.ShortcutContext.WindowShortcut)
        self.shortcut_add_zone.activated.connect(self._handle_add_zone_shortcut)

        self.shortcut_delete_zone = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self.shortcut_delete_zone.setContext(Qt.ShortcutContext.WindowShortcut)
        self.shortcut_delete_zone.activated.connect(self._handle_delete_zone_shortcut)
        self.shortcut_delete_zone.setEnabled(False)

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_runtime_ui)
        self.ui_timer.start(60)

        self.resources_timer = QTimer(self)
        self.resources_timer.timeout.connect(self.update_system_resources)
        self.resources_timer.start(1000)

        self.serial_retry_timer = QTimer(self)
        self.serial_retry_timer.setInterval(5000)
        self.serial_retry_timer.timeout.connect(self._retry_serial_connection)
        self.serial_runtime_controller = SerialRuntimeController(
            serial_manager=self.serial_manager,
            runtime_state=self.runtime_state,
            get_hardware=lambda: self.project_manager.current_project.hardware,
            record_runtime_transition=self._record_runtime_transition,
            refresh_status_bar=self.refresh_status_bar,
            refresh_application_state=self._refresh_application_state,
            start_retry_timer=self.serial_retry_timer.start,
            stop_retry_timer=self.serial_retry_timer.stop,
            is_retry_timer_active=self.serial_retry_timer.isActive,
            log_info=self.log_manager.info,
        )
        self.hardware_coordinator = HardwareUiCoordinator(
            parent_widget=self,
            hardware_tab=self.hardware_tab,
            serial_manager=self.serial_manager,
            serial_runtime_controller=self.serial_runtime_controller,
            relay_manager=self.relay_manager,
            log_manager=self.log_manager,
            get_project=lambda: self.project_manager.current_project,
            current_zone=self.current_zone,
            iter_zones=lambda: tuple(self.all_zones()),
            stop_serial_retry_timer=self.serial_retry_timer.stop,
            refresh_status_bar=self.refresh_status_bar,
            refresh_after_hardware_settings_change=self._refresh_after_hardware_settings_change,
        )
        self.hardware_coordinator.wire_signals()

        self._load_theme()
        self.camera_view.set_placeholder_text("Starting system...")
        self.log_manager.info(f"Data folder: {app_data_dir()}")
        self._refresh_serial_header_status()
        self._emit_ui_scaling_event("startup", force=True)
        self._log_ui_scaling_snapshot("startup", force=True)
        self._queue_layout_refresh(reason="startup")

    def closeEvent(self, event) -> None:
        if not self._confirm_safe_to_discard_changes(action_name="close the app"):
            event.ignore()
            return
        self.serial_retry_timer.stop()
        self.serial_manager.close()
        self.camera_pipeline.stop_all()
        self._set_app_state("stopped")
        super().closeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._emit_ui_scaling_event("show_event", extra={"spontaneous": event.spontaneous()})
        self._log_ui_scaling_snapshot("show_event", force=True)
        self._clamp_to_available_screen(reason="show_event")
        self._queue_layout_refresh(reason="show_event")

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in {
            QEvent.Type.WindowStateChange,
            QEvent.Type.StyleChange,
            QEvent.Type.FontChange,
            QEvent.Type.PaletteChange,
        }:
            event_type = self._safe_qt_value(event.type())
            self._emit_ui_scaling_event("change_event", extra={"type": event_type})
            self._log_ui_scaling_snapshot("change_event", force=True)
            self._queue_layout_refresh(reason=f"change_event:{event_type}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._emit_ui_scaling_event(
            "main_window_resize",
            force=True,
            extra={
                "old_size": {"w": event.oldSize().width(), "h": event.oldSize().height()},
                "new_size": {"w": event.size().width(), "h": event.size().height()},
            },
        )
        self._log_ui_scaling_snapshot("main_window_resize", force=True)

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._emit_ui_scaling_event(
            "main_window_move",
            extra={
                "old_pos": {"x": event.oldPos().x(), "y": event.oldPos().y()},
                "new_pos": {"x": event.pos().x(), "y": event.pos().y()},
            },
        )

    def load_project_into_ui(
        self,
        *,
        record_project_loaded: bool = True,
        reset_dirty_state: bool = True,
    ) -> None:
        self.project_load_controller.apply_loaded_project(
            record_project_loaded=record_project_loaded,
            reset_dirty_state=reset_dirty_state,
        )

    def begin_initial_load(self) -> None:
        self.camera_view.set_placeholder_text("Loading project...")
        self.status_widget.set_summary("Loading project...")
        self.load_project_into_ui()

    def _set_loading_project_ui(self, loading: bool) -> None:
        self._loading_project_ui = bool(loading)

    def _prepare_for_project_load_application(self) -> None:
        self.serial_retry_timer.stop()
        self.serial_manager.disconnect()
        self.serial_manager.reset_live_state()
        self._sync_serial_runtime_state(record_disconnect=False)
        self._load_performance_settings()
        self._load_theme()

    def _apply_loaded_project_ui_state(self) -> None:
        self.project_tab.project_name_value.setText(self._project_display_name())
        self._load_app_preferences_into_ui()
        self.refresh_camera_selector()
        self.refresh_camera_tabs()
        self.refresh_zone_list()
        self._queue_layout_refresh(reason="loaded_project_ui_state")

    def _apply_loaded_hardware_ui_state(self) -> None:
        project = self.project_manager.current_project
        self.hardware_coordinator.apply_loaded_hardware_ui_state(project)
        self.system_resources_tab.debug_logging.setChecked(project.debug_logging)
        self._queue_layout_refresh(reason="loaded_hardware_ui_state")

    def _refresh_after_project_load(self) -> None:
        self.refresh_project_summary()
        self.refresh_status_bar()
        self.rebuild_zone_cache()
        self.start_camera_workers()
        self.update_system_resources()

    def _finalize_successful_project_load(
        self,
        *,
        record_project_loaded: bool,
        reset_dirty_state: bool,
    ) -> None:
        if reset_dirty_state:
            self._reset_project_dirty_state()
        else:
            self._apply_dirty_sync_plan(
                self.project_dirty_sync_controller.build_restore_dirty_visuals(
                    project=self.project_manager.current_project,
                    runtime_state=self.runtime_state,
                    current_path=self.project_manager.current_path,
                    project_display_name=self._project_display_name(),
                )
            )
        if record_project_loaded:
            self._record_runtime_transition(
                "project_loaded",
                f"Project loaded: {self._project_display_name()}",
                log=True,
                path=self.project_manager.current_path or "",
            )
        self._refresh_application_state()
        self.refresh_selected_camera_view(force=True)
        self.camera_view.set_placeholder_text(None)
        self._queue_layout_refresh(reason="project_load_finalized")

    def _handle_project_load_failure(self) -> None:
        self._set_app_state("error")
        self.camera_view.set_placeholder_text("Project load failed")
        self.status_widget.set_summary("Project load failed")

    def start_camera_workers(self) -> None:
        self.camera_pipeline.sync_cameras(self.project_manager.current_project.cameras)

    def refresh_detected_cameras(self) -> None:
        self._detected_camera_sources = self.camera_manager.list_cameras(refresh=True)
        current_source = self.detection_tab.selected_detected_source()
        self.detection_tab.set_detected_sources(self._detected_camera_sources, current_source=current_source)
        if self._detected_camera_sources:
            detected_text = ", ".join(
                getattr(camera, "display_label", f"Source {getattr(camera, 'index', camera)}")
                for camera in self._detected_camera_sources
            )
            self.log_manager.info(f"Cameras detected: {detected_text}")
        else:
            self.log_manager.info("No cameras detected")
        self._apply_refresh_plan(self.refresh_choreography_controller.detected_cameras_refreshed())

    def populate_serial_ports(self) -> None:
        self.hardware_coordinator.populate_serial_ports()

    def _reset_project_dirty_state(self) -> None:
        self._apply_dirty_sync_plan(
            self.project_dirty_sync_controller.reset_dirty_state(
                project=self.project_manager.current_project,
                runtime_state=self.runtime_state,
                current_path=self.project_manager.current_path,
                project_display_name=self._project_display_name(),
            )
        )

    def _update_project_dirty_state(self, reason: str = "Project changed") -> None:
        plan = self.project_dirty_sync_controller.update_dirty_state(
            project=self.project_manager.current_project,
            runtime_state=self.runtime_state,
            current_path=self.project_manager.current_path,
            project_display_name=self._project_display_name(),
            reason=reason,
            loading_project_ui=self._loading_project_ui,
        )
        if plan is None:
            return
        if plan.should_record_dirty_event:
            self.runtime_state.record_runtime_event(
                "project_dirty",
                message=reason,
                metadata={"reason": reason},
            )
        self._apply_dirty_sync_plan(plan)

    def _refresh_dirty_card_highlights(self) -> None:
        self._apply_dirty_sync_plan(
            self.project_dirty_sync_controller.build_restore_dirty_visuals(
                project=self.project_manager.current_project,
                runtime_state=self.runtime_state,
                current_path=self.project_manager.current_path,
                project_display_name=self._project_display_name(),
            )
        )

    def _set_project_dirty(self, is_dirty: bool) -> None:
        self._apply_dirty_sync_plan(
            self.project_dirty_sync_controller.build_restore_dirty_visuals(
                project=self.project_manager.current_project,
                runtime_state=self.runtime_state,
                current_path=self.project_manager.current_path,
                project_display_name=self._project_display_name(),
            )
        )

    def _apply_dirty_sync_plan(self, plan: DirtySyncPlan) -> None:
        self.project_tab.btn_save.setEnabled(True)
        self.project_tab.project_name_value.setText(plan.visual_plan.project_display_name)
        self.setWindowTitle(plan.visual_plan.window_title)
        for card_id, dirty in plan.visual_plan.project_cards:
            self.project_tab.set_card_dirty(card_id, dirty)
        for card_id, dirty in plan.visual_plan.detection_cards:
            self.detection_tab.set_card_dirty(card_id, dirty)
        for card_id, dirty in plan.visual_plan.zone_cards:
            self.zones_tab.set_card_dirty(card_id, dirty)
        for card_id, dirty in plan.visual_plan.detection_setup_cards:
            self.detection_setup_tab.set_card_dirty(card_id, dirty)
        for card_id, dirty in plan.visual_plan.hardware_cards:
            self.hardware_tab.set_card_dirty(card_id, dirty)
        for card_id, dirty in plan.visual_plan.diagnostics_cards:
            self.system_resources_tab.set_card_dirty(card_id, dirty)
        for tab_index, dirty in plan.visual_plan.tab_states:
            self.right_tabs.setTabDirty(tab_index, dirty)

    def _apply_refresh_plan(self, plan: RefreshPlan) -> None:
        self.refresh_coordinator.apply_plan(plan)

    @staticmethod
    def _env_flag_enabled(name: str) -> bool:
        return MainWindowLayoutCoordinator.env_flag_enabled(name)

    @staticmethod
    def _safe_qt_value(value) -> object:
        return MainWindowLayoutCoordinator.safe_qt_value(value)

    @staticmethod
    def _initial_window_size() -> QSize:
        return MainWindowLayoutCoordinator.initial_window_size()

    @staticmethod
    def _select_ui_density() -> str:
        screen = QGuiApplication.primaryScreen()
        available_width = None
        available_height = None
        if screen is not None:
            available = screen.availableGeometry()
            available_width = available.width()
            available_height = available.height()
        return set_ui_density(
            resolve_ui_density_for_screen(
                available_width,
                available_height,
                requested_density=os.environ.get(UI_DENSITY_ENV_VAR),
            )
        )

    def _clamp_to_available_screen(self, *, reason: str) -> None:
        self.layout_coordinator.clamp_to_available_screen(reason=reason)

    @staticmethod
    def _widget_geometry_payload(widget: QWidget | None) -> dict[str, object] | None:
        return MainWindowLayoutCoordinator.widget_geometry_payload(widget)

    def _screen_geometry_payload(self) -> dict[str, object]:
        return self.layout_coordinator.screen_geometry_payload()

    def _collect_ui_scaling_snapshot(self) -> dict[str, object]:
        return self.layout_coordinator.collect_scaling_snapshot()

    def _safe_camera_view_diagnostic_state(self) -> dict[str, object]:
        return self.layout_coordinator.safe_camera_view_diagnostic_state()

    def _emit_ui_scaling_log(
        self,
        log_key: str,
        message_type: str,
        payload: dict[str, object],
        *,
        throttle_s: float,
        force: bool = False,
    ) -> None:
        self.layout_coordinator.emit_log(
            log_key,
            message_type,
            payload,
            throttle_s=throttle_s,
            force=force,
        )

    def _emit_ui_scaling_event(
        self,
        event_name: str,
        *,
        extra: dict[str, object] | None = None,
        throttle_s: float = 0.5,
        force: bool = False,
    ) -> None:
        self.layout_coordinator.emit_event(
            event_name,
            extra=extra,
            throttle_s=throttle_s,
            force=force,
        )

    def _log_ui_scaling_snapshot(self, reason: str, *, force: bool = False, throttle_s: float = 1.5) -> None:
        self.layout_coordinator.log_scaling_snapshot(reason, force=force, throttle_s=throttle_s)

    def _log_ui_scaling_child_event(self, source: str, event_name: str, payload: dict[str, object]) -> None:
        self.layout_coordinator.log_child_event(source, event_name, payload)

    def _queue_layout_refresh(self, *, reason: str) -> None:
        self.layout_coordinator.queue_layout_refresh(reason=reason)

    def _refresh_layout_now(self, *, reason: str) -> None:
        self.layout_coordinator.refresh_layout_now(reason=reason)

    def _prompt_unsaved_changes(self, action_name: str) -> str:
        message = f"You have unsaved project changes. Save before you {action_name}?"
        if action_name == "open another project":
            message = (
                "You have unsaved project changes. Opening another project will replace them unless you save first."
            )
        return ConfirmDialog.ask_save_discard_cancel(
            self,
            title="Unsaved Changes",
            message=message,
            save_text="Save",
            discard_text="Discard Changes",
            cancel_text="Cancel",
        )

    def _confirm_safe_to_discard_changes(self, *, action_name: str) -> bool:
        return self.project_session.confirm_safe_to_discard_changes(action_name=action_name)

    def _commit_pending_project_edits(self) -> bool:
        self.sync_project_from_ui()
        self.apply_hardware_settings()
        self.apply_debug_logging()
        self.apply_detection_settings()

        zone = self.current_zone()
        if zone is None:
            return True
        return self.apply_zone_properties()

    def _prepare_for_project_open(self) -> None:
        self.camera_pipeline.stop_all()
        self.current_camera_id = None
        self._last_displayed_frame_version.clear()
        self._last_logged_camera_state.clear()
        self._last_logged_reconnect_attempt.clear()

    def _save_project_without_prompt(self) -> bool:
        return self.save_project(prompt=False)

    def _set_app_state(self, state: str) -> None:
        previous = self.runtime_state.get_app_state()
        self.runtime_state.set_app_state(state)
        if previous != self.runtime_state.get_app_state():
            self.runtime_state.record_runtime_event(
                "app_state_changed",
                message=f"Application state changed to {self.runtime_state.get_app_state()}",
                metadata={"from": previous, "to": self.runtime_state.get_app_state()},
            )

    def _sync_serial_runtime_state(self, *, record_disconnect: bool = True) -> None:
        self.serial_runtime_controller.sync_runtime_state(record_disconnect=record_disconnect)

    def _record_runtime_transition(
        self,
        name: str,
        message: str,
        *,
        level: str = "INFO",
        log: bool = False,
        **metadata,
    ) -> None:
        self.runtime_state.record_runtime_event(
            name,
            level=level,
            message=message,
            metadata=metadata,
        )
        if not log:
            return
        if level == "ERROR":
            self.log_manager.error(message)
        elif level == "WARNING":
            self.log_manager.warning(message)
        elif level == "DEBUG":
            self.log_manager.debug(message)
        else:
            self.log_manager.info(message)

    def _refresh_application_state(self) -> None:
        self._set_app_state(
            self.app_state_controller.derive_app_state(
                project=self.project_manager.current_project,
                runtime_state=self.runtime_state,
            )
        )

    def _handle_detector_status_message(self, message: str) -> None:
        self.detector_status_message_received.emit(message)

    @Slot(str)
    def _handle_detector_status_message_on_ui(self, message: str) -> None:
        self._record_runtime_transition(
            "model_load_failed",
            f"[DETECTION] {message}",
            level="WARNING",
            log=True,
        )
        self._update_detection_status_label()

    def _update_detection_status_label(self) -> None:
        camera = self.current_camera()
        if camera is None:
            self.detection_tab.set_model_status("")
            self._last_detection_status_message = ""
            return
        status_message = self.detector.get_status(camera.detection.mode)
        self.detection_tab.set_model_status(status_message)
        if status_message and status_message != self._last_detection_status_message:
            self._record_runtime_transition(
                "model_load_failed",
                f"[DETECTION] {status_message}",
                level="WARNING",
                log=True,
                mode=camera.detection.mode,
            )
        self._last_detection_status_message = status_message

    def _load_performance_settings(self) -> None:
        performance = self.project_manager.current_project.performance
        show_fps_overlay = self._app_setting_bool("show_fps_overlay")
        self.runtime_state.update_performance_settings(
            inference_resolution=performance.inference_resolution,
            max_detection_fps=performance.max_detection_fps,
            background_camera_fps=performance.background_camera_fps,
            show_fps_overlay=show_fps_overlay,
            mirror_horizontal=performance.mirror_horizontal,
        )
        current = self.runtime_state.get_performance_settings()
        self.detection_tab.set_performance_values(
            inference_resolution=current.inference_resolution,
            max_detection_fps=current.max_detection_fps,
            background_camera_fps=current.background_camera_fps,
            show_fps_overlay=current.show_fps_overlay,
            mirror_horizontal=current.mirror_horizontal,
        )
        self.preferences_tab.show_fps_overlay.blockSignals(True)
        self.preferences_tab.show_fps_overlay.setChecked(show_fps_overlay)
        self.preferences_tab.show_fps_overlay.blockSignals(False)

    def _load_theme(self) -> None:
        theme_name = self._app_setting_theme()
        if theme_name not in {"Light", "Dark"}:
            theme_name = "Light"
        if self._theme_name == theme_name and bool(self.styleSheet()):
            return
        self._theme_name = theme_name
        self.setStyleSheet(build_stylesheet(self._theme_name))
        apply_native_title_bar_theme(self, self._theme_name)

    def _app_setting_bool(self, key: str) -> bool:
        return bool(self._app_settings.get(key, DEFAULT_APP_SETTINGS[key]))

    def _app_setting_theme(self) -> str:
        theme_name = str(self._app_settings.get("theme", DEFAULT_APP_SETTINGS["theme"]) or "Light").strip().title()
        return theme_name if theme_name in {"Light", "Dark"} else "Light"

    def _load_app_preferences_into_ui(self) -> None:
        blockers = [
            QSignalBlocker(self.preferences_tab.theme_combo),
            QSignalBlocker(self.preferences_tab.auto_load),
            QSignalBlocker(self.preferences_tab.start_minimized),
            QSignalBlocker(self.preferences_tab.show_fps_overlay),
        ]
        try:
            self.preferences_tab.theme_combo.setCurrentText(self._app_setting_theme())
            self.preferences_tab.auto_load.setChecked(self._app_setting_bool("auto_load_last_project"))
            self.preferences_tab.start_minimized.setChecked(self._app_setting_bool("start_minimized"))
            self.preferences_tab.show_fps_overlay.setChecked(self._app_setting_bool("show_fps_overlay"))
        finally:
            blockers.clear()

    def _project_display_name(self) -> str:
        current_path = self.project_manager.current_path
        if current_path:
            return Path(current_path).stem
        return "Unsaved Project"

    def _focus_widget_blocks_shortcuts(self) -> bool:
        widget = self.focusWidget()
        if widget is None:
            return False
        if isinstance(widget, QLineEdit):
            return True
        if hasattr(widget, "lineEdit") and callable(getattr(widget, "lineEdit")):
            line_edit = widget.lineEdit()
            if line_edit is not None and line_edit.hasFocus():
                return True
        return False

    def _handle_add_zone_shortcut(self) -> None:
        if self._focus_widget_blocks_shortcuts():
            return
        if self.current_camera() is None:
            return
        self.right_tabs.setCurrentIndex(self._zones_tab_index)
        self.camera_view.begin_add_zone()

    def _handle_delete_zone_shortcut(self) -> None:
        if self._focus_widget_blocks_shortcuts():
            return
        self.delete_zone()

    def _update_zone_shortcuts(self) -> None:
        has_selected_zone = self.current_zone() is not None
        self.shortcut_delete_zone.setEnabled(has_selected_zone)

    def sync_project_from_ui(self) -> None:
        self.refresh_project_summary()

    def sync_app_preferences_from_ui(self) -> None:
        self._app_settings["auto_load_last_project"] = self.preferences_tab.auto_load.isChecked()
        self._app_settings["start_minimized"] = self.preferences_tab.start_minimized.isChecked()

    def active_project_cameras(self) -> list[CameraModel]:
        return [camera for camera in self.project_manager.current_project.cameras if camera.enabled]

    def refresh_camera_selector(self) -> None:
        options = []
        detected_sources = {
            str(getattr(source, "index", source)).strip(): source
            for source in self._detected_camera_sources
        }
        for index, camera in enumerate(self.project_manager.current_project.cameras, start=1):
            display_name = self._display_camera_name(camera)
            options.append(
                {
                    "id": camera.id,
                    "label": display_name,
                    "enabled": camera.enabled,
                    "mirror_horizontal": camera.mirror_horizontal,
                    "flip_vertical": camera.flip_vertical,
                }
            )
        self.project_tab.set_camera_options(options)

    def apply_camera_selection(self) -> None:
        enabled_map = self.project_tab.camera_enabled_map()
        current_camera = self.current_camera()
        current_camera_id = current_camera.id if current_camera is not None else None
        changed = False

        for camera in self.project_manager.current_project.cameras:
            if camera.id in enabled_map and camera.enabled != enabled_map[camera.id]:
                camera.enabled = enabled_map[camera.id]
                changed = True

        if current_camera_id and not any(camera.id == current_camera_id for camera in self.active_project_cameras()):
            self.camera_view.selected_zone_id = None

        self._apply_refresh_plan(
            self.refresh_choreography_controller.camera_activation_applied(changed=changed)
        )
        if changed:
            self._record_runtime_transition(
                "camera_activation_changed",
                "Camera activation updated",
                active_cameras=len(self.active_project_cameras()),
            )

    def apply_camera_orientation_settings(self) -> None:
        mirror_map = self.project_tab.camera_mirror_map()
        flip_map = self.project_tab.camera_flip_map()
        changed = False

        for camera in self.project_manager.current_project.cameras:
            if camera.id in mirror_map and camera.mirror_horizontal != mirror_map[camera.id]:
                camera.mirror_horizontal = mirror_map[camera.id]
                changed = True
            if camera.id in flip_map and camera.flip_vertical != flip_map[camera.id]:
                camera.flip_vertical = flip_map[camera.id]
                changed = True

        if not changed:
            return

        self._apply_refresh_plan(self.refresh_choreography_controller.camera_display_settings_changed())

    def add_project_camera(self) -> None:
        source_text = self.detection_tab.selected_detected_source().strip()
        if not source_text:
            ConfirmDialog.inform(
                self,
                title="Add Camera",
                message="Select a camera source first.",
                button_text="OK",
            )
            return

        source: int | str = int(source_text) if source_text.isdigit() else source_text
        source_name = self.camera_manager.get_friendly_name(source) or f"Camera {len(self.project_manager.current_project.cameras) + 1}"
        if any(str(camera.source) == str(source) for camera in self.project_manager.current_project.cameras):
            ConfirmDialog.inform(
                self,
                title="Camera Already Added",
                message=f"{source_name} is already configured in this project.",
                button_text="OK",
            )
            return

        camera = self.project_manager.add_camera(
            name=source_name,
            source=source,
        )
        self._record_runtime_transition(
            "camera_added",
            f"{self._display_camera_name(camera)} added to the project",
            log=True,
            camera_id=camera.id,
            source=str(source),
        )
        self._apply_refresh_plan(self.refresh_choreography_controller.camera_added())

    def remove_project_camera(self, camera_id: str) -> None:
        camera = next((item for item in self.project_manager.current_project.cameras if item.id == camera_id), None)
        if camera is None:
            return

        action = ConfirmDialog.ask_choice(
            self,
            title="Remove Camera",
            message=(
                f"Removing {self._display_camera_name(camera)} also removes its zones.\n\n"
                "Disable instead to keep this camera and its zones saved while stopping it from running."
            ),
            choices=[
                ("disable", "Disable Instead", QDialogButtonBox.ButtonRole.ActionRole, False),
                ("remove", "Remove Camera", QDialogButtonBox.ButtonRole.DestructiveRole, True),
                ("cancel", "Cancel", QDialogButtonBox.ButtonRole.RejectRole, False),
            ],
            dialog_kind="warning",
        )
        if action == "disable":
            if camera.enabled:
                self.project_tab.set_camera_enabled(camera.id, False)
                self.apply_camera_selection()
            return
        if action != "remove":
            return

        was_selected = self.current_camera_id == camera.id
        self.project_manager.remove_camera(camera.id)
        if was_selected:
            self.camera_view.selected_zone_id = None
            self.current_camera_id = None
        self._record_runtime_transition(
            "camera_removed",
            f"{self._display_camera_name(camera)} removed from the project",
            log=True,
            camera_id=camera.id,
        )
        self._apply_refresh_plan(self.refresh_choreography_controller.camera_removed())

    def refresh_project_summary(self) -> None:
        plan = self.project_dirty_sync_controller.build_project_summary(self.project_manager.current_project)
        self.project_tab.set_summary_counts(cameras=plan.camera_count, zones=plan.zone_count)

    def rebuild_zone_cache(self) -> None:
        self._previous_zone_ids_by_camera = {
            camera.id: {zone.id for zone in camera.zones}
            for camera in self.project_manager.current_project.cameras
        }

    def refresh_camera_tabs(self) -> None:
        plan = self.camera_display_controller.build_tab_refresh_plan(self.current_camera_id)
        self.camera_tabs.blockSignals(True)
        while self.camera_tabs.count():
            self.camera_tabs.removeTab(0)

        for label in plan.tab_labels:
            self.camera_tabs.addTab(label)

        self.camera_tabs.blockSignals(False)

        if plan.selected_camera is not None:
            self.camera_tabs.setCurrentIndex(plan.selected_index)
            self._apply_camera_selection_plan(
                self.camera_display_controller.build_camera_selection_plan(
                    plan.selected_camera,
                    self.camera_view.selected_zone_id,
                )
            )
        else:
            self._clear_selected_camera_display()
        self._update_zone_shortcuts()

    def on_camera_tab_changed(self, index: int) -> None:
        plan = self.camera_display_controller.build_tab_change_selection(index, self.camera_view.selected_zone_id)
        if plan is not None:
            self._apply_camera_selection_plan(plan)

    def on_right_tab_changed(self, index: int) -> None:
        if index != 3 and self.camera_view.modifying_detection_area:
            self.camera_view.end_modify_detection_area()
            self.refresh_detection_area_editor()
        if index != 3 and self.camera_view.modifying_ignore_area:
            self.camera_view.end_modify_ignore_area()
            self.refresh_ignore_area_editor()

    def set_selected_camera(self, camera: CameraModel) -> None:
        self._apply_camera_selection_plan(
            self.camera_display_controller.build_camera_selection_plan(
                camera,
                self.camera_view.selected_zone_id,
            )
        )

    def _apply_camera_selection_plan(self, plan: CameraSelectionPlan) -> None:
        self.current_camera_id = plan.camera_id
        self.runtime_state.set_visible_camera(plan.camera_id)
        self.camera_view.set_camera(plan.camera)
        self.camera_view.selected_zone_id = plan.preserved_zone_id
        self.load_detection_for_camera(plan.camera)
        self._update_detection_status_label()
        self.refresh_zone_list()
        self.refresh_status_bar()
        self.refresh_selected_camera_view(force=True)
        self._update_zone_shortcuts()

    def _clear_selected_camera_display(self) -> None:
        self.current_camera_id = None
        self.runtime_state.set_visible_camera(None)
        self.camera_view.set_camera(None)

    def current_camera(self) -> CameraModel | None:
        return self.camera_display_controller.current_camera(self.current_camera_id)

    def current_zone(self) -> ZoneModel | None:
        return self.zone_coordination_controller.current_zone(self.camera_view.selected_zone_id)

    def current_ignore_area(self) -> IgnoreAreaModel | None:
        camera = self.current_camera()
        if camera is None or not self.camera_view.selected_ignore_area_id:
            return None
        return next(
            (area for area in camera.ignore_areas if area.id == self.camera_view.selected_ignore_area_id),
            None,
        )

    def find_zone_by_id(self, zone_id: str | None):
        return self.zone_coordination_controller.find_zone_by_id(zone_id)

    def refresh_runtime_ui(self) -> None:
        self._emit_ui_scaling_event("refresh_runtime_ui")
        self._apply_trigger_events(self.camera_pipeline.drain_trigger_events())
        self._log_camera_runtime_transitions()
        self._monitor_serial_connection()
        self._refresh_serial_header_status()
        self.refresh_selected_camera_view(force=False)
        self._log_ui_scaling_snapshot("refresh_runtime_ui")

    def refresh_selected_camera_view(self, force: bool) -> None:
        plan = self.camera_display_controller.build_display_refresh_plan(
            current_camera_id=self.current_camera_id,
            force=force,
            last_frame_version=(
                None if force or self.current_camera_id is None else self._last_displayed_frame_version.get(self.current_camera_id)
            ),
            view_state=CameraDisplayViewState(
                show_overlay=self.camera_view.show_overlay,
                mirror_horizontal=self.camera_view.mirror_horizontal,
                flip_vertical=self.camera_view.flip_vertical,
                simulation_notice=self.camera_view.simulation_notice_text,
            ),
        )
        if plan is None:
            return
        self._emit_ui_scaling_event(
            "refresh_selected_camera_view",
            extra={
                "force": force,
                "camera_id": plan.camera_id,
                "frame_updated": plan.frame_updated,
                "frame_version": plan.frame_version,
            },
            throttle_s=0.75,
        )
        self._last_displayed_frame_version[plan.camera_id] = plan.frame_version
        self.camera_view.set_display_data(
            frame=plan.frame,
            frame_updated=plan.frame_updated,
            detections=plan.detections,
            occupancy=plan.occupancy,
            camera_state=plan.camera_state,
            fps=plan.fps,
            inference_ms=plan.inference_ms,
            show_overlay=plan.show_overlay,
            mirror_horizontal=plan.mirror_horizontal,
            flip_vertical=plan.flip_vertical,
            simulation_notice=plan.simulation_notice,
        )
        if plan.frame_updated:
            self._log_ui_scaling_snapshot("refresh_selected_camera_view:frame_updated", throttle_s=0.75)

    def all_zones(self):
        return self.zone_relay_policy.iter_zones(self.project_manager.current_project.cameras)

    def populate_relay_combo(self, zone=None, *, allow_shared_relay_override: bool | None = None) -> None:
        combo = self.zones_tab.relay_combo
        editor_state = self.zone_coordination_controller.build_zone_editor_state(
            zone,
            allow_shared_relay_override=allow_shared_relay_override,
        )

        with QSignalBlocker(combo):
            combo.clear()
            for option in editor_state.relay_options:
                combo.addItem(option.label, option.relay_id)
                index = combo.count() - 1
                model = combo.model()
                item = model.item(index) if hasattr(model, "item") else None
                if isinstance(item, QStandardItem) and not option.selectable:
                    item.setEnabled(False)
                    item.setForeground(self.palette().mid())
                if option.selected:
                    combo.setCurrentIndex(index)
            if zone is None:
                combo.setCurrentIndex(-1)
            elif combo.count() > 0 and combo.currentIndex() < 0:
                combo.setCurrentIndex(0)

    def update_zone_editor(self, zone, *, allow_shared_relay_override: bool | None = None) -> None:
        editor_state = self.zone_coordination_controller.build_zone_editor_state(
            zone,
            allow_shared_relay_override=allow_shared_relay_override,
        )
        with QSignalBlocker(self.zones_tab.zone_name):
            self.zones_tab.zone_name.setText(editor_state.zone_name)
        self.populate_relay_combo(zone, allow_shared_relay_override=allow_shared_relay_override)
        with QSignalBlocker(self.zones_tab.allow_shared_relay):
            self.zones_tab.allow_shared_relay.setChecked(editor_state.allow_shared_relay)
        with QSignalBlocker(self.zones_tab.enabled):
            self.zones_tab.enabled.setChecked(editor_state.enabled)
        self.zones_tab.shared_relay_note.setText(editor_state.shared_relay_note_text)
        self.zones_tab.allow_shared_relay.setEnabled(editor_state.has_zone)
        self.zones_tab.shared_relay_note.setVisible(editor_state.has_zone and editor_state.allow_shared_relay)
        self.hardware_tab.selected_relay_label.setText(editor_state.relay_label_text)
        self.hardware_tab.selected_relay_description.setText(editor_state.relay_description_text)
        self.hardware_tab.btn_test_selected_on.setEnabled(editor_state.can_test_relay)
        self.hardware_tab.btn_test_selected_off.setEnabled(editor_state.can_test_relay)
        self._update_zone_shortcuts()

    def refresh_zone_relay_options(self, *_args) -> None:
        zone = self.current_zone()
        if zone is None or self._updating_zone_ui:
            return
        self.update_zone_editor(
            zone,
            allow_shared_relay_override=self.zones_tab.allow_shared_relay.isChecked(),
        )

    def select_ignore_area_in_list_by_id(self, ignore_area_id: str | None) -> None:
        ignore_list = self.detection_setup_tab.ignore_area_list
        with QSignalBlocker(ignore_list):
            ignore_list.clearSelection()
            if not ignore_area_id:
                return
            for row in range(ignore_list.count()):
                item = ignore_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == ignore_area_id:
                    ignore_list.setCurrentItem(item)
                    return

    def refresh_ignore_area_list(self) -> None:
        ignore_list = self.detection_setup_tab.ignore_area_list
        camera = self.current_camera()
        with QSignalBlocker(ignore_list):
            ignore_list.clear()
            if camera is not None:
                for ignore_area in camera.ignore_areas:
                    item = QListWidgetItem(ignore_area.name or "Ignore Area")
                    item.setData(Qt.ItemDataRole.UserRole, ignore_area.id)
                    ignore_list.addItem(item)
        self.select_ignore_area_in_list_by_id(self.camera_view.selected_ignore_area_id)
        self.refresh_ignore_area_editor()

    def refresh_ignore_area_editor(self) -> None:
        camera = self.current_camera()
        ignore_area = self.current_ignore_area()
        has_ignore_areas = bool(camera and camera.ignore_areas)
        has_selection = ignore_area is not None
        is_modifying = bool(self.camera_view.modifying_ignore_area)

        if not has_ignore_areas:
            self.detection_setup_tab.ignore_area_status.setText("No ignore areas configured")
        elif is_modifying and has_selection:
            self.detection_setup_tab.ignore_area_status.setText("Modify the selected ignore area shape for this camera.")
        elif has_selection:
            self.detection_setup_tab.ignore_area_status.setText("Ignored detections in this area will not drive zones.")
        else:
            self.detection_setup_tab.ignore_area_status.setText("Select an ignore area to modify or delete it.")

        self.detection_setup_tab.btn_add_ignore_area.setEnabled(camera is not None)
        self.detection_setup_tab.btn_modify_ignore_area.setEnabled(has_selection)
        self.detection_setup_tab.btn_modify_ignore_area.setText("Done Modifying" if is_modifying and has_selection else "Modify Ignore Area")
        self.detection_setup_tab.btn_delete_ignore_area.setEnabled(has_selection)

    def refresh_detection_area_editor(self) -> None:
        camera = self.current_camera()
        polygon = list(getattr(camera, "detection_area", ())) if camera is not None else []
        has_detection_area = len(polygon) >= 3
        is_modifying = bool(self.camera_view.modifying_detection_area)
        if has_detection_area:
            if is_modifying:
                self.detection_setup_tab.detection_area_status.setText("Modify the detection area shape for this camera.")
                self.detection_setup_tab.btn_modify_detection_area.setText("Done Modifying")
            else:
                self.detection_setup_tab.detection_area_status.setText(
                    "Only detections inside this area are analysed."
                )
                self.detection_setup_tab.btn_modify_detection_area.setText("Modify Area")
            self.detection_setup_tab.btn_add_detection_area.setText("Redraw Detection Area")
        else:
            self.detection_setup_tab.detection_area_status.setText("No detection area configured")
            self.detection_setup_tab.btn_add_detection_area.setText("Draw Detection Area")
            self.detection_setup_tab.btn_modify_detection_area.setText("Modify Area")
        self.detection_setup_tab.btn_add_detection_area.setEnabled(camera is not None)
        self.detection_setup_tab.btn_modify_detection_area.setEnabled(has_detection_area)
        self.detection_setup_tab.btn_clear_detection_area.setEnabled(has_detection_area)

    def select_zone_in_list_by_id(self, zone_id: str | None) -> None:
        zone_list = self.zones_tab.zone_list
        with QSignalBlocker(zone_list):
            zone_list.clearSelection()
            if not zone_id:
                return
            for row in range(zone_list.count()):
                item = zone_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == zone_id:
                    zone_list.setCurrentItem(item)
                    return

    def on_zones_changed(self) -> None:
        camera = self.current_camera()
        if camera is None:
            self.refresh_zone_list()
            return

        result = self.zone_coordination_controller.handle_zones_changed(
            current_camera=camera,
            selected_zone_id=self.camera_view.selected_zone_id,
            previous_zone_ids=self._previous_zone_ids_by_camera.get(camera.id, set()),
        )
        self._previous_zone_ids_by_camera[camera.id] = result.previous_zone_ids
        self.camera_view.selected_zone_id = result.selected_zone_id

        self._apply_refresh_plan(self.refresh_choreography_controller.zone_layout_changed())

    def on_ignore_areas_changed(self) -> None:
        self.refresh_ignore_area_list()
        self.camera_view.update()
        self._update_project_dirty_state("Ignore areas changed")

    def on_detection_area_changed(self) -> None:
        self.refresh_detection_area_editor()
        self.camera_view.update()
        self._update_project_dirty_state("Detection area changed")

    def on_detection_area_error(self, message: str) -> None:
        ConfirmDialog.inform(
            self,
            title="Detection Area",
            message=message,
            button_text="OK",
        )

    def on_ignore_area_error(self, message: str) -> None:
        ConfirmDialog.inform(
            self,
            title="Ignore Area",
            message=message,
            button_text="OK",
        )

    def refresh_zone_list(self) -> None:
        if self._updating_zone_ui:
            return

        self._updating_zone_ui = True
        try:
            zone_list = self.zones_tab.zone_list
            selected_zone = self.current_zone()
            with QSignalBlocker(zone_list):
                zone_list.clear()
                for item_data in self.zone_coordination_controller.build_zone_list_items():
                    item = QListWidgetItem(item_data.label)
                    item.setData(Qt.ItemDataRole.UserRole, item_data.zone_id)
                    zone_list.addItem(item)

            self.select_zone_in_list_by_id(self.camera_view.selected_zone_id)
            self.refresh_detection_area_editor()
            self.refresh_ignore_area_list()
            self.update_zone_editor(selected_zone)
            self.refresh_project_summary()
            self.refresh_status_bar()
        finally:
            self._updating_zone_ui = False

    def select_zone_by_id(self, zone_id: str) -> None:
        result = self.zone_coordination_controller.resolve_zone_selection(zone_id)
        plan = self.camera_display_controller.build_zone_camera_selection(
            result,
            current_tab_index=self.camera_tabs.currentIndex(),
        )
        if not plan.camera or not result.zone:
            self.camera_view.selected_zone_id = None
            self.camera_view.clear_ignore_area_selection()
            self.select_ignore_area_in_list_by_id(None)
            self.detection_setup_tab.btn_delete_ignore_area.setEnabled(False)
            self.update_zone_editor(None)
            self.refresh_zone_list()
            self.camera_view.update()
            return

        self.current_camera_id = plan.camera_id
        if plan.should_switch_tab:
            self.camera_tabs.setCurrentIndex(plan.camera_index)
        elif plan.should_apply_camera_selection:
            self._apply_camera_selection_plan(
                self.camera_display_controller.build_camera_selection_plan(
                    plan.camera,
                    self.camera_view.selected_zone_id,
                )
            )

        self.camera_view.selected_zone_id = plan.selected_zone_id
        self.camera_view.clear_ignore_area_selection()
        self.select_zone_in_list_by_id(plan.selected_zone_id)
        self.select_ignore_area_in_list_by_id(None)
        self.detection_setup_tab.btn_delete_ignore_area.setEnabled(False)
        self.update_zone_editor(result.zone)
        self.camera_view.update()
        self._update_zone_shortcuts()

    def select_zone_by_name(self, _zone_text: str) -> None:
        current_item = self.zones_tab.zone_list.currentItem()
        if current_item is None:
            self.camera_view.selected_zone_id = None
            self.update_zone_editor(None)
            self.camera_view.update()
            self._update_zone_shortcuts()
            return

        zone_id = current_item.data(Qt.ItemDataRole.UserRole)
        if zone_id:
            self.select_zone_by_id(zone_id)

    def select_ignore_area_by_id(self, ignore_area_id: str) -> None:
        camera = self.current_camera()
        normalized_id = str(ignore_area_id).strip() if ignore_area_id else ""
        ignore_area = None
        if camera is not None and normalized_id:
            ignore_area = next((area for area in camera.ignore_areas if area.id == normalized_id), None)
        self.camera_view.select_ignore_area(ignore_area.id if ignore_area else None)
        if ignore_area is not None:
            self.camera_view.selected_zone_id = None
            self.select_zone_in_list_by_id(None)
            self.update_zone_editor(None)
        self.select_ignore_area_in_list_by_id(ignore_area.id if ignore_area else None)
        self.refresh_ignore_area_editor()
        self.camera_view.update()

    def select_ignore_area_by_name(self, _ignore_area_text: str) -> None:
        current_item = self.detection_setup_tab.ignore_area_list.currentItem()
        if current_item is None:
            self.camera_view.clear_ignore_area_selection()
            self.refresh_ignore_area_editor()
            self.camera_view.update()
            return

        ignore_area_id = current_item.data(Qt.ItemDataRole.UserRole)
        if ignore_area_id:
            self.select_ignore_area_by_id(ignore_area_id)

    def apply_zone_properties(self) -> bool:
        zone = self.current_zone()
        if not zone:
            return True

        relay_value = self.zones_tab.relay_combo.currentData()
        new_relay_id = int(relay_value) if relay_value is not None else None
        decision = self.zone_coordination_controller.apply_zone_update(
            zone=zone,
            proposed_name=self.zones_tab.zone_name.text(),
            proposed_relay_id=new_relay_id,
            allow_shared_relay=self.zones_tab.allow_shared_relay.isChecked(),
            enabled=self.zones_tab.enabled.isChecked(),
        )
        if not decision.ok:
            ConfirmDialog.warn(self, title=decision.error_title, message=decision.error_message)
            return False

        self._apply_refresh_plan(self.refresh_choreography_controller.zone_settings_changed())
        return True

    def delete_zone(self) -> None:
        camera = self.current_camera()
        zone = self.current_zone()
        if camera is None or zone is None:
            return

        if not ConfirmDialog.ask(
            self,
            title="Delete Zone",
            message=f"Delete '{zone.name}' from {self._display_camera_name(camera)}?",
            confirm_text="Delete",
            cancel_text="Cancel",
        ):
            return

        deletion_plan = self.zone_coordination_controller.build_zone_deletion_plan(camera=camera, zone=zone)

        deleted = self.camera_view.delete_selected_zone()
        if not deleted:
            return

        self.camera_pipeline.remove_zone_runtime(camera.id, deletion_plan.zone_id)

        if deletion_plan.force_relay_off and deletion_plan.relay_id is not None:
            self.relay_manager.set_state(deletion_plan.relay_id, False)
            self.serial_manager.enqueue_zone_command(deletion_plan.relay_id, False)
            self.log_manager.info(f"Zone deleted and relay {deletion_plan.relay_id} forced OFF")

        self.zones_tab.zone_name.clear()
        self._apply_refresh_plan(self.refresh_choreography_controller.zone_deleted())

    def delete_ignore_area(self) -> None:
        camera = self.current_camera()
        ignore_area = self.current_ignore_area()
        if camera is None or ignore_area is None:
            return

        if not ConfirmDialog.ask(
            self,
            title="Delete Ignore Area",
            message=f"Delete '{ignore_area.name}' from {self._display_camera_name(camera)}?",
            confirm_text="Delete",
            cancel_text="Cancel",
        ):
            return

        if not self.camera_view.delete_selected_ignore_area():
            return

        self._update_project_dirty_state("Ignore area deleted")
        self.refresh_ignore_area_list()

    def delete_detection_area(self) -> None:
        camera = self.current_camera()
        if camera is None or len(getattr(camera, "detection_area", ())) < 3:
            return

        if not ConfirmDialog.ask(
            self,
            title="Clear Detection Area",
            message=f"Clear the detection area for {self._display_camera_name(camera)}?",
            confirm_text="Clear",
            cancel_text="Cancel",
        ):
            return

        if not self.camera_view.clear_detection_area():
            return

        self._update_project_dirty_state("Detection area cleared")
        self.refresh_detection_area_editor()

    def toggle_modify_detection_area(self) -> None:
        camera = self.current_camera()
        if camera is None or len(getattr(camera, "detection_area", ())) < 3:
            return
        if self.camera_view.modifying_detection_area:
            self.camera_view.end_modify_detection_area()
        else:
            self.camera_view.begin_modify_detection_area()
        self.refresh_detection_area_editor()

    def toggle_modify_ignore_area(self) -> None:
        ignore_area = self.current_ignore_area()
        if ignore_area is None or len(getattr(ignore_area, "polygon", ())) < 3:
            return
        if self.camera_view.modifying_ignore_area:
            self.camera_view.end_modify_ignore_area()
        else:
            self.camera_view.begin_modify_ignore_area()
        self.refresh_ignore_area_editor()

    def load_detection_for_camera(self, camera: CameraModel) -> None:
        detection = camera.detection
        self.detection_tab.set_values(
            mode=detection.mode,
            confidence=detection.confidence_threshold,
            min_size=detection.min_box_area,
            entry_delay=detection.entry_delay_ms,
            exit_delay=detection.exit_delay_ms,
            trigger_offset=detection.trigger_point_offset,
        )
        self._update_detection_status_label()

    def apply_detection_settings(self) -> None:
        camera = self.current_camera()
        if not camera:
            return

        camera.detection.mode = self.detection_tab.mode.currentText().lower()
        camera.detection.confidence_threshold = self.detection_tab.confidence.value() / 100.0
        camera.detection.min_box_area = self.detection_tab.min_size.value()
        camera.detection.entry_delay_ms = self.detection_tab.entry_delay.value()
        camera.detection.exit_delay_ms = self.detection_tab.exit_delay.value()
        camera.detection.trigger_point_offset = self.detection_tab.trigger_offset.value() / 100.0
        self._update_detection_status_label()
        self._update_project_dirty_state("Detection settings changed")

    def _refresh_after_hardware_settings_change(self) -> None:
        self._apply_refresh_plan(self.refresh_choreography_controller.hardware_settings_changed())

    def apply_hardware_settings(self) -> None:
        self.hardware_coordinator.apply_hardware_settings()

    def apply_debug_logging(self) -> None:
        enabled = self.system_resources_tab.debug_logging.isChecked()
        self.project_manager.current_project.debug_logging = enabled
        self.log_manager.set_debug(enabled or self._ui_scaling_diagnostics_enabled)
        self._update_project_dirty_state("Debug logging changed")

    def refresh_status_bar(self) -> None:
        plan = self.status_summary_controller.build_status_bar_plan(cpu_summary_text=self._cpu_summary_text)
        self.status_widget.set_summary(plan.summary_text)
        self.status_widget.set_relays(
            plan.relay_states,
            plan.relays_per_board,
        )

    def connect_serial(self) -> None:
        self.hardware_coordinator.connect_serial()

    def disconnect_serial(self) -> None:
        self.hardware_coordinator.disconnect_serial()

    def toggle_serial_connection(self) -> None:
        self.hardware_coordinator.toggle_serial_connection()

    def _attempt_serial_connect(self) -> None:
        self.hardware_coordinator.attempt_serial_connect()

    def _auto_connect_serial_if_needed(self) -> None:
        self.hardware_coordinator.auto_connect_serial_if_needed()

    def _retry_serial_connection(self) -> None:
        self.hardware_coordinator.retry_serial_connection()

    def _start_serial_retry_timer(self) -> None:
        self.hardware_coordinator.ensure_serial_retry_timer_running()

    def _monitor_serial_connection(self) -> None:
        self.hardware_coordinator.monitor_serial_connection()

    def _refresh_serial_header_status(self) -> None:
        self.hardware_coordinator.refresh_serial_header_status()

    def clear_log_view(self) -> None:
        self.system_resources_tab.clear_log_view()
        self.log_manager.info("Log cleared (UI)")

    def test_all_on(self) -> None:
        self.hardware_coordinator.test_all_on()

    def test_all_off(self) -> None:
        self.hardware_coordinator.test_all_off()

    def test_selected_relay_on(self) -> None:
        self.hardware_coordinator.test_selected_relay_on()

    def test_selected_relay_off(self) -> None:
        self.hardware_coordinator.test_selected_relay_off()

    def _apply_trigger_events(self, events) -> None:
        if self.trigger_dispatch_controller.apply_trigger_events(events):
            self.refresh_status_bar()

    def _log_camera_runtime_transitions(self) -> None:
        camera_status_changed = False
        selector_needs_refresh = False
        camera_ids = [camera.id for camera in self.project_manager.current_project.cameras]
        camera_states = self.runtime_state.get_camera_snapshots(camera_ids)
        for camera in self.project_manager.current_project.cameras:
            state = camera_states[camera.id]
            camera_name = self._display_camera_name(camera)
            previous_state = self._last_logged_camera_state.get(camera.id)
            if state.state != previous_state:
                if state.state == "live" and previous_state:
                    self._record_runtime_transition(
                        "camera_restored",
                        f"{camera_name} is live again",
                        log=True,
                        camera_id=camera.id,
                    )
                elif state.state in {"disconnected", "reconnecting"}:
                    message = (
                        f"{camera_name} connection lost"
                        if state.state == "disconnected"
                        else f"{camera_name} reconnecting"
                    )
                    self._record_runtime_transition(
                        "camera_lost" if state.state == "disconnected" else "camera_reconnecting",
                        message,
                        level="WARNING",
                        log=True,
                        camera_id=camera.id,
                    )
                elif state.state == "starting":
                    self._record_runtime_transition(
                        "camera_starting",
                        f"{camera_name} starting",
                        log=True,
                        camera_id=camera.id,
                    )
                self._last_logged_camera_state[camera.id] = state.state
                camera_status_changed = True
                selector_needs_refresh = True

            previous_attempt = self._last_logged_reconnect_attempt.get(camera.id, 0)
            if state.reconnect_attempts > previous_attempt:
                self._record_runtime_transition(
                    "camera_reconnect_attempt",
                    f"{camera_name} reconnect attempt {state.reconnect_attempts}",
                    level="WARNING",
                    log=True,
                    camera_id=camera.id,
                    attempts=state.reconnect_attempts,
                )
                self._last_logged_reconnect_attempt[camera.id] = state.reconnect_attempts
        if selector_needs_refresh:
            self.refresh_camera_selector()
        if camera_status_changed:
            self._refresh_application_state()

    def update_system_resources(self) -> None:
        self._emit_ui_scaling_event("update_system_resources")
        cpu_text = "Unavailable"
        memory_text = "Unavailable"

        if psutil is not None:
            try:
                cpu_text = f"{psutil.cpu_percent(interval=None):.1f}%"
                if self._process is not None:
                    memory_text = self._format_bytes(self._process.memory_info().rss)
            except Exception:
                cpu_text = "Unavailable"
                memory_text = "Unavailable"

        plan = self.status_summary_controller.build_system_resources_plan(
            cpu_percent=cpu_text,
            memory=memory_text,
            inference_device=self._inference_device_name(),
        )
        self._cpu_summary_text = plan.cpu_summary_text
        self.system_resources_tab.set_snapshot(
            cpu_percent=plan.cpu_percent,
            memory=plan.memory,
            app_state=plan.app_state,
            active_cameras=plan.active_cameras,
            active_zones=plan.active_zones,
            serial_state=plan.serial_state,
            inference_device=plan.inference_device,
            per_camera_lines=list(plan.per_camera_lines),
        )
        self.refresh_status_bar()
        self._log_ui_scaling_snapshot("update_system_resources")

    def _display_camera_name(self, camera: CameraModel) -> str:
        base_name = self._base_camera_name(camera)
        duplicate_count = sum(
            1
            for candidate in self.project_manager.current_project.cameras
            if self._base_camera_name(candidate) == base_name
        )
        if duplicate_count > 1:
            return f"{base_name} (Source {camera.source})"
        return base_name

    def _base_camera_name(self, camera: CameraModel) -> str:
        name = camera.name.strip()
        if name and not name.lower().startswith("cam ") and not name.lower().startswith("camera "):
            return name
        friendly_name = self.camera_manager.get_friendly_name(camera.source)
        if friendly_name:
            return friendly_name
        return f"Camera {self._camera_fallback_index(camera) + 1}"

    def _camera_fallback_index(self, camera: CameraModel) -> int:
        cameras = self.project_manager.current_project.cameras
        for index, candidate in enumerate(cameras):
            if candidate.id == camera.id:
                return index
        return 0

    def apply_performance_settings(self, values: dict) -> None:
        self.runtime_state.update_performance_settings(
            inference_resolution=values.get("inference_resolution"),
            max_detection_fps=values.get("max_detection_fps"),
            background_camera_fps=values.get("background_camera_fps"),
            show_fps_overlay=values.get("show_fps_overlay", self._app_setting_bool("show_fps_overlay")),
            mirror_horizontal=values.get("mirror_horizontal"),
        )
        current = self.runtime_state.get_performance_settings()
        performance = self.project_manager.current_project.performance
        performance.inference_resolution = current.inference_resolution
        performance.max_detection_fps = current.max_detection_fps
        performance.background_camera_fps = current.background_camera_fps
        performance.mirror_horizontal = current.mirror_horizontal
        self.preferences_tab.show_fps_overlay.blockSignals(True)
        self.preferences_tab.show_fps_overlay.setChecked(self._app_setting_bool("show_fps_overlay"))
        self.preferences_tab.show_fps_overlay.blockSignals(False)
        self.refresh_selected_camera_view(force=False)
        self._update_project_dirty_state("Performance settings changed")

    def apply_display_preferences(self) -> None:
        self._app_settings["show_fps_overlay"] = self.preferences_tab.show_fps_overlay.isChecked()
        self.runtime_state.update_performance_settings(show_fps_overlay=self._app_setting_bool("show_fps_overlay"))
        self.refresh_selected_camera_view(force=False)

    def apply_performance_preset(self, preset_name: str) -> None:
        values = self.detection_tab.PRESETS.get(preset_name)
        if not values:
            return

        self.detection_tab.set_performance_values(
            inference_resolution=values["inference_resolution"],
            max_detection_fps=values["max_detection_fps"],
            background_camera_fps=values["background_camera_fps"],
            show_fps_overlay=self._app_setting_bool("show_fps_overlay"),
            preset=preset_name,
        )
        self.apply_performance_settings(values)

    def get_app_settings(self) -> dict:
        settings = dict(DEFAULT_APP_SETTINGS)
        settings.update(self._app_settings)
        settings["theme"] = self._theme_name
        settings["auto_load_last_project"] = self.preferences_tab.auto_load.isChecked()
        settings["start_minimized"] = self.preferences_tab.start_minimized.isChecked()
        settings["show_fps_overlay"] = self.preferences_tab.show_fps_overlay.isChecked()
        return settings

    def apply_theme(self, theme_name: str) -> None:
        normalized = str(theme_name or "Light").strip().title()
        if normalized not in {"Light", "Dark"}:
            normalized = "Light"
        self._theme_name = normalized
        self._app_settings["theme"] = normalized
        self.setStyleSheet(build_stylesheet(normalized))
        apply_native_title_bar_theme(self, normalized)

    @staticmethod
    def _inference_device_name() -> str:
        if torch is None:
            return "CPU"
        try:
            return "CUDA (GPU)" if torch.cuda.is_available() else "CPU"
        except Exception:
            return "CPU"

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        value = float(num_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024.0 or unit == "TB":
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"

    def open_project(self) -> None:
        if not self._confirm_safe_to_discard_changes(action_name="open another project"):
            return

        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "JSON Files (*.json)")
        if not path:
            return

        result = self.project_session.open_project(path)
        if result.ok:
            self.project_tab.project_name_value.setText(self._project_display_name())
            return
        self.log_manager.error(f"Project open failed: {result.error}")
        ConfirmDialog.error(self, title="Open Project Failed", message=f"Could not open the project file.\n\n{result.error}")

    def save_project(self, *, prompt: bool = True) -> bool:
        if not self.project_manager.current_path:
            return self.save_project_as(prompt=prompt)
        if prompt and not ConfirmDialog.ask(
            self,
            title="Overwrite Current Project",
            message="Overwrite the current project file and its saved settings?",
            confirm_text="Overwrite",
            cancel_text="Cancel",
        ):
            return False

        result = self.project_session.save_project()
        if result.ok:
            self.project_tab.btn_save.clearFocus()
            if prompt:
                ConfirmDialog.inform(
                    self,
                    title="Project Saved",
                    message=f"Project '{self._project_display_name()}' was saved.",
                    button_text="OK",
                )
            return True
        if not result.cancelled:
            self.log_manager.error(f"Project save failed: {result.error}")
            ConfirmDialog.error(self, title="Save Failed", message=f"Could not save the project.\n\n{result.error}")
            return False
        return False

    def save_project_as(self, *, prompt: bool = True) -> bool:
        if not self._commit_pending_project_edits():
            return False
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "JSON Files (*.json)")
        if not path:
            return False

        result = self.project_session.save_project(path=path, commit_pending_edits=False)
        if result.ok:
            self.project_tab.btn_save_as.clearFocus()
            if prompt:
                ConfirmDialog.inform(
                    self,
                    title="Project Saved",
                    message=f"Project '{self._project_display_name()}' was saved.",
                    button_text="OK",
                )
            return True
        if not result.cancelled:
            self.log_manager.error(f"Project save failed: {result.error}")
            ConfirmDialog.error(self, title="Save Failed", message=f"Could not save the project.\n\n{result.error}")
            return False
        return False
