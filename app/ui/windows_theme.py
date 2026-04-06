from __future__ import annotations

import sys
from ctypes import byref, c_int, sizeof, windll


def apply_native_title_bar_theme(window, theme_name: str) -> None:
    if not sys.platform.startswith("win"):
        return

    dark = str(theme_name or "").strip().lower() == "dark"
    try:
        hwnd = int(window.winId())
        set_window_attribute = windll.dwmapi.DwmSetWindowAttribute
    except Exception:
        return

    value = c_int(1 if dark else 0)
    for attribute in (20, 19):
        try:
            result = set_window_attribute(hwnd, attribute, byref(value), sizeof(value))
            if result == 0:
                break
        except Exception:
            return
