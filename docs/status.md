# Project Status

## 1. Overview
- The application is a PySide6 desktop control app for multi-camera video monitoring with YOLO-based person/face detection, polygon zone editing, occupancy evaluation, delayed trigger state changes, relay state management, and operator diagnostics.
- Intended use case: define polygon trigger zones on live camera feeds, detect people or faces entering/leaving those zones, and drive relay-style outputs with configurable delays while monitoring logs, serial state, and runtime performance.

## 2. Architecture
- `app/main.py`
  - Application bootstrap. Loads app settings, optionally auto-loads the last project, creates service objects, opens `MainWindow`, and saves app settings on exit.
- `app/models/`
  - `project_model.py`: persistent project config models: `ProjectModel`, `CameraModel`, `ZoneModel`, `DetectionSettings`, `HardwareModel`.
  - `runtime_state.py`: non-persistent runtime state: per-camera runtime metrics/state, per-zone trigger state, relay runtime state, and performance settings.
  - `events.py`: `TriggerEvent`.
- `app/storage/`
  - `project_repository.py`: JSON project load/save.
  - `settings_repository.py`: app-level settings load/save in `~/.interactive_zone_trigger/app_settings.json`.
- `app/core/`
  - `camera_manager.py`: OpenCV capture lifecycle, Windows backend selection (`CAP_DSHOW`, fallback `CAP_MSMF`, then default), source reopen/release, frame size lookup.
  - `camera_pipeline.py`: background worker thread per configured camera, frame capture, detection throttling, occupancy evaluation, trigger updates, reconnect handling, frame snapshots.
  - `detector_service.py`: Ultralytics YOLO wrapper, person/face model loading, inference-frame resizing, coordinate mapping back to original frame.
  - `occupancy_engine.py`: polygon occupancy based on detection `trigger_point`.
  - `trigger_engine.py`: delayed ON/OFF state machine per zone using runtime state.
  - `relay_manager.py`: in-memory relay commanded state table.
  - `serial_manager.py`: simulated serial transport and log output.
  - `log_manager.py`: file logging plus UI subscriber fanout and warning rate limiting.
  - `project_manager.py`: current project lifecycle and camera creation.
- `app/ui/`
  - `main_window.py`: main coordinator between UI and runtime services.
  - `camera_view.py`: video display, zone drawing/editing, overlay rendering.
  - `project_tab.py`, `zones_tab.py`, `detection_tab.py`, `hardware_logs_tab.py`, `system_resources_tab.py`: operator controls.
  - `status_bar.py`: system summary plus grouped relay-board indicators.
  - `multi_row_tab_widget.py`, `theme.py`, `confirm_dialog.py`, `windows_theme.py`: UI presentation helpers.
- Data flow
  - Camera frame capture: `CameraManager` / `CameraSource`
  - Detection: `DetectorService.detect(...)`
  - Zone occupancy: `OccupancyEngine.evaluate(...)`
  - Trigger transition logic: `TriggerEngine.update(...)`
  - Relay/serial handling: `MainWindow._apply_trigger_events(...)` -> `RelayManager` + `SerialManager`
  - UI refresh: `CameraPipeline.get_camera_snapshot(...)` -> `MainWindow.refresh_selected_camera_view(...)` -> `CameraView`

## 3. Implemented Features
- Multi-camera project model with per-camera `enabled` state persisted in project JSON via `CameraModel.enabled`.
- Background camera worker threads with reconnect handling in `app/core/camera_pipeline.py`.
- Windows camera backend hardening in `app/core/camera_manager.py`.
- Person and face detection using YOLO in `app/core/detector_service.py`.
- Detection throttling and operator-adjustable performance settings in `AppRuntimeState.performance_settings` and `SystemResourcesTab`.
- Polygon zone creation, selection, vertex editing, and deletion in `app/ui/camera_view.py`.
- Proper point-in-polygon occupancy using `app/utils/geometry.py` and `app/core/occupancy_engine.py`.
- Entry/exit delay trigger state logic with non-repeating ON/OFF events in `app/core/trigger_engine.py`.
- Relay state management and serial command logging/ACK simulation in `app/core/relay_manager.py` and `app/core/serial_manager.py`.
- Relay cleanup when a zone is deleted in `MainWindow.delete_zone(...)`.
- Live camera overlays: boxes, trigger points, labels, occupied-zone fill, selected-zone handles, FPS/state overlay.
- No overlay rendering when there is no valid current frame in `CameraView.paintEvent(...)`.
- Project open/save/save-as and app settings persistence.
- Themed UI with Light/Dark styles, custom confirmation dialog, optional Windows dark title-bar attempt.
- System diagnostics tab with CPU, memory, serial state, active camera/zone counts, inference device, per-camera metrics, and performance controls.
- Serial/log UI with live log view, clear-log UI action, open-log-file action, relay test buttons, and standard baud-rate dropdown.
- Camera activation UI in `app/ui/project_tab.py`: configured cameras can be marked active/inactive and only active cameras appear as usable cameras in the main UI.

## 4. Incomplete / In Progress
- Serial I/O is not real hardware integration. `app/core/serial_manager.py` only simulates TX/ACK and connection state.
- Camera discovery is minimal. The app can probe indices in `CameraManager.detect_available_sources(...)`, but the current Project tab camera activation UI only manages cameras already stored in the project; it does not discover/add cameras dynamically.
- Friendly camera naming is not implemented reliably; fallback naming is `Camera N`.
- `app/ui/help_tab.py` still exists on disk but is no longer used by `MainWindow`.
- `DetectorService.annotate_frame(...)` exists but is not used by the current UI path.
- Face detection depends on `models/yolov8-face.pt`; if that file is missing, face mode silently yields no detections except for a one-time console warning.

## 5. Known Issues
- `DetectorService._compute_trigger_point(...)` ignores `DetectionSettings.trigger_point_offset` and always returns the bottom-center point of the box. The UI exposes the setting, but current logic does not use it.
- `ProjectTab` shows camera activation for configured project cameras only. There is no full camera inventory/discovery workflow in the UI.
- In `MainWindow.refresh_project_summary(...)`, the Project tab camera count is total configured cameras, not active cameras. This may be intentional, but it differs from runtime diagnostics/status summaries.
- `SerialManager.send_zone(...)` logs an ACK immediately when connected; there is no timeout, retry, port validation, or parsing of device responses.
- `HardwareLogsTab.populate_ports(...)` uses a static fallback list (`COM3`, `COM4`, `/dev/ttyUSB0`) rather than enumerating actual serial ports.
- `MainWindow.start_camera_workers()` is called frequently from UI refresh paths; workers are reused, but camera sync is still repeatedly invoked from the UI timer.
- Zone deletion confirmation in `CameraView.delete_selected_zone(...)` still uses `QMessageBox`, while save confirmation uses the themed custom dialog.

## 6. Current State Assessment
- Estimated completion: 80-85%.
- MVP readiness: close to MVP for a demo/operator workflow if simulated serial output is acceptable and YOLO dependencies/models are present.
- Not production-ready for real deployment because hardware serial transport, camera discovery/management, error recovery UX, and configuration edge cases are still lightweight.

## 7. Next Steps (Prioritised)
1. Implement real serial communication in `app/core/serial_manager.py` with actual port open/write/read, error handling, and ACK timeout behaviour.
2. Fix `DetectionSettings.trigger_point_offset` so the configured offset actually affects trigger-point placement in `DetectorService._compute_trigger_point(...)`.
3. Add a proper configured-camera management workflow: discover available camera indices, add/remove cameras from the project, and distinguish configured vs merely available devices.
4. Replace static serial-port placeholders in `HardwareLogsTab.populate_ports(...)` with actual port enumeration.
5. Consolidate confirmation dialogs so zone deletion uses the same readable themed dialog path as project save.
6. Review UI/runtime coupling in `MainWindow`; reduce repeated `start_camera_workers()` calls if they are not needed on every UI refresh.
7. Add targeted tests for occupancy geometry, trigger delays, relay-sharing edge cases, and project persistence.
