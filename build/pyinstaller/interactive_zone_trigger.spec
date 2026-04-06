from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


project_root = Path(SPECPATH)

datas = []
datas += [(str(project_root / "app" / "ui" / "assets" / "checkmark.svg"), "app/ui/assets")]
datas += [(str(project_root / "Models"), "Models")]

binaries = []
binaries += collect_dynamic_libs("torch")

hiddenimports = []
hiddenimports += collect_submodules("cv2_enumerate_cameras")

excludes = [
    "polars",
    "matplotlib",
    "tensorflow",
    "tensorboard",
    "tkinter",
]

for package_name in ("ultralytics", "torch", "opencv-python", "pyserial", "PySide6"):
    try:
        datas += copy_metadata(package_name)
    except Exception:
        pass


a = Analysis(
    ["app/main.py"],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InteractiveZoneTrigger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="InteractiveZoneTrigger",
)
