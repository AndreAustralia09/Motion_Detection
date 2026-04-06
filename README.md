# Interactive Zone Trigger

Desktop monitoring application for multi-camera video with real-time detection, configurable trigger zones, and hardware relay control.

## Features

* Multi-camera monitoring (USB/IP cameras via OpenCV)
* YOLO-based detection:

  * Person detection
  * Face detection
  * Hand detection
* Polygon-based trigger zones
* Ignore zones (filter unwanted areas)
* Delayed relay triggering
* Serial hardware integration (Arduino relay control)
* Runtime diagnostics and logging
* Project-based configuration (save/load setups)

---

## Project Structure

```
Motion_Detection/
├── app/                          # Application source code
│   ├── core/                    # Core logic and controllers
│   ├── models/                  # Data models
│   ├── storage/                 # Persistence (projects/settings)
│   ├── ui/                      # UI components
│   └── utils/                   # Utility functions
│
├── build/
│   └── pyinstaller/             # Packaging configuration
│       └── interactive_zone_trigger.spec
│
├── docs/                        # Documentation
│   └── status.md
│
├── examples/
│   └── projects/                # Example project configurations
│       └── test.json
│
├── hardware/
│   └── arduino/
│       └── relay_serial_bridge/ # Arduino relay firmware
│
├── models/                      # Local ML model files
│   ├── yolov8n.pt              # Person detection
│   ├── yolov8-face.pt          # Face detection
│   └── yolov8-hand.pt          # Hand detection
│
├── tests/                       # Test scaffolding (future)
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Requirements

* Python 3.12 (recommended)
* Windows (primary target)
* USB or IP cameras
* Optional: Arduino relay hardware

---

## Installation

Clone the repository:

```
git clone https://github.com/AndreAustralia09/Motion_Detection.git
cd Motion_Detection
```

Create and activate a virtual environment:

```
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```
pip install -r requirements.txt
```

---

## Running the Application

Run in development mode:

```
python -m app.main
```

---

## Models

Models are stored locally in the `models/` folder.

### Available models

* `yolov8n.pt` → person detection
* `yolov8-face.pt` → face detection
* `yolov8-hand.pt` → hand detection

These are selectable in the application UI.

---

## Example Projects

Example configurations are located in:

```
examples/projects/
```

Load these from the UI to test detection, zones, and triggers.

---

## Hardware Integration

Arduino relay firmware is located in:

```
hardware/arduino/relay_serial_bridge/
```

This enables:

* Serial communication from the app
* Relay triggering based on detection events

---

## Packaging (Executable Build)

PyInstaller configuration:

```
build/pyinstaller/interactive_zone_trigger.spec
```

To build:

```
pyinstaller build/pyinstaller/interactive_zone_trigger.spec
```

Output will be in:

```
dist/
```

---

## Known Limitations

* Camera discovery currently uses simple OpenCV source probing
* Camera index ordering may change between restarts
* Limited hot-plug support for cameras
* Performance depends on hardware (CPU/GPU)

---

## Future Improvements

* Proper camera device enumeration (replace index probing)
* Improved hardware abstraction layer
* Configurable detection pipelines
* Better packaging and installer support
* Logging and diagnostics improvements

---

## License

Add your license here (e.g. MIT, proprietary, etc.)
