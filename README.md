# Interactive Zone Trigger

Desktop monitoring app for multi-camera video, YOLO person/face detection, polygon trigger zones, delayed relay triggering, serial hardware control, and runtime diagnostics.

## Quick Start

### Windows operator launch
- Double-click `run_app.bat`
- If a local virtual environment exists, it will be used automatically
- If not, the script falls back to `py -3` or `python`

### Development launch
```powershell
python -m app.main
```

## Requirements

- Python 3.12 recommended
- Windows desktop environment for the current deployment target
- USB/IP cameras supported by OpenCV
- Optional serial hardware using a simple Arduino-style text protocol

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Models

The app looks for model files in these locations:

- `Models\yolov8n.pt`
- `Models\yolov8-face.pt`
- root-level `yolov8n.pt`

Current repo layout already includes:

- [Models\yolov8n.pt](/C:/Users/Australia/Desktop/interactive-zone-trigger-starter/starter_app/Models/yolov8n.pt)
- [Models\yolov8-face.pt](/C:/Users/Australia/Desktop/interactive-zone-trigger-starter/starter_app/Models/yolov8-face.pt)

Notes:
- Person detection can also fall back to the Ultralytics model name if a local file is not packaged.
- Face detection expects a local face model file.

## App Data Locations

The app stores operator data in:

- `C:\Users\<User>\.interactive_zone_trigger\app_settings.json`
- `C:\Users\<User>\.interactive_zone_trigger\app.log`
- rotated logs: `app.log.1`, `app.log.2`, `app.log.3`

The live log tab can open the current log file directly.

## Project Workflow

1. Launch the app
2. Create or open a project
3. Add/configure cameras in the `Project` tab
4. Draw and edit zones in the camera view
5. Configure detection in the `Detection` tab
6. Configure serial hardware in `Serial Communication`
7. Save the project

Saved projects restore on next launch if:

- `Auto-load last project` is enabled in the saved project
- the last project path still exists

## Cameras

- `Detected Cameras` are sources available right now
- `Configured Cameras` are stored in the project
- Enabled configured cameras become active at runtime
- Disabled configured cameras stay in the project but do not run

## Serial Hardware

For hardware-free testing:

- enable `Simulation Mode (No Hardware)`

For real serial hardware:

1. Refresh ports
2. Select the COM port
3. Select the baud rate
4. Disable simulation mode
5. Click `Connect`

If `Auto-connect serial on startup` is enabled, the app will reconnect automatically after project load and retry every 5 seconds if the device is unavailable.

## First Run / Defaults

- If no project is loaded, the app starts with a default `Camera 1`
- No zones are created automatically
- Serial defaults to simulation mode
- Start minimized is off by default

## Included Example Projects

This repo currently includes example project files in the root:

- `Test.json`
- `Test Zone.json`
- `Test Multiple Zones and Faces.json`

Treat them as examples only. Save production projects under your own site/customer naming.

## Common Checks

### No video
- Confirm the camera is enabled in the project
- Check that the source appears in `Detected Cameras`
- Check System Resources for camera state: `Starting`, `Live`, `Reconnecting`, `Disconnected`

### Face detection not working
- Confirm the face model file exists in `Models\yolov8-face.pt`
- Check the Detection tab status message
- Check the log for `[DETECTION]` warnings

### Serial not connecting
- Confirm simulation mode is off
- Confirm the correct COM port and baud rate
- Check the live log for `[SERIAL ERROR]` messages

### Project changes not restored after restart
- The project must be saved explicitly
- Unsaved changes are intentionally not auto-persisted

## Packaging Notes

The app now resolves resource paths more safely for packaged/frozen execution:

- local runtime bundle directory first
- project root fallback for development

This is intended to make PyInstaller-style packaging easier, but a full installer/build pipeline is not included in this phase.

## Known Limits

- Camera discovery still uses simple OpenCV source probing
- Face model must be supplied locally
- No full installer or updater is included yet
- GUI automation tests are intentionally limited; coverage focuses on logic and persistence
