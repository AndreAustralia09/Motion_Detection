from __future__ import annotations


UI_DENSITY_NORMAL = "normal"
UI_DENSITY_COMPACT = "compact"
UI_DENSITY_ENV_VAR = "IZT_UI_DENSITY"
COMPACT_SCREEN_WIDTH = 1366
COMPACT_SCREEN_HEIGHT = 800


class Spacing:
    NONE = 0
    XXS = 1
    XS = 2
    SM = 4
    MD = 6
    ROW = 7
    LG = 8
    XL = 10
    XXL = 12
    WINDOW = 14
    GROUP_TOP = 16
    DIALOG = 18
    DIALOG_MARGIN = 20


class Margins:
    ZERO = (0, 0, 0, 0)
    MAIN_WINDOW = (14, 14, 14, 14)
    TAB_PAGE = (10, 10, 10, 10)
    GROUP = (12, 16, 12, 12)
    COMPACT_GROUP = (10, 12, 10, 10)
    STATUS_BAR = (10, 8, 10, 8)
    RELAY_INDICATOR = (4, 2, 4, 2)
    RELAY_BOARD = (8, 4, 8, 4)
    CAMERA_ROW = (0, 2, 0, 2)
    DIALOG = (20, 18, 20, 18)


class Padding:
    INPUT = (5, 8)
    BUTTON = (6, 10)
    TAB = (6, 10)
    TOP_TAB = (5, 8)
    LIST = 4
    LIST_ITEM = (5, 8)
    GROUP_TITLE = (0, 6, 1, 6)
    BOARD_LABEL_RIGHT = 6


class FontSize:
    SMALL = 12
    BODY = 13
    HEADING = 14
    CAMERA_OVERLAY = 10
    CAMERA_EMPTY = 15


class LineHeight:
    NORMAL = 1.4
    DIAGNOSTICS_LIGHT = 1.45
    DIAGNOSTICS_DARK = 1.5


class Radius:
    XS = 2
    SM = 3
    MD = 4
    LG = 5
    XL = 6
    OVERLAY = 8


class MainWindowMetrics:
    PREFERRED_WIDTH = 1500
    PREFERRED_HEIGHT = 900
    AVAILABLE_SCREEN_MARGIN = 48
    LEFT_STRETCH = 4
    RIGHT_STRETCH = 1


class RightPanelMetrics:
    MINIMUM_CONTENT_HEIGHT = 180
    PREFERRED_CONTENT_HEIGHT = 520
    MINIMUM_WIDTH_CAP = 360
    PREFERRED_WIDTH_CAP = 410
    MEDIUM_SCREEN_WIDTH = 1540
    NARROW_SCREEN_WIDTH = 1320
    MEDIUM_MINIMUM_WIDTH_CAP = 340
    MEDIUM_PREFERRED_WIDTH_CAP = 380
    NARROW_MINIMUM_WIDTH_CAP = 330
    NARROW_PREFERRED_WIDTH_CAP = 360


class CameraViewMetrics:
    MINIMUM_HEIGHT = 180
    MINIMUM_WIDTH = 320
    MINIMUM_FONT_ROWS = 8
    OVERLAY_MARGIN = 12
    OVERLAY_TEXT_PADDING_X = 9
    OVERLAY_TEXT_PADDING_Y = 7
    GUIDANCE_PADDING_X = 12
    GUIDANCE_PADDING_Y = 9
    LABEL_OFFSET_X = 6
    LABEL_OFFSET_Y = 6
    FALLBACK_LABEL_POSITION = 16
    LABEL_MIN_Y = 18
    SELECTED_HANDLE_RADIUS = 5
    HANDLE_RADIUS = 4
    SELECTED_OUTLINE_WIDTH = 3
    OUTLINE_WIDTH = 2
    THIN_OUTLINE_WIDTH = 1


class StatusBarMetrics:
    RELAY_LABEL_WIDTH = 18
    RELAY_LED_SIZE = 10
    DEFAULT_RELAYS_PER_BOARD = 8


class TabMetrics:
    CAMERA_LIST_MIN_HEIGHT = 180
    CAMERA_LIST_MAX_HEIGHT = 280
    CAMERA_REMOVE_BUTTON_MIN_HEIGHT = 26
    CAMERA_METRICS_MIN_HEIGHT = 110
    CAMERA_METRICS_MAX_HEIGHT = 200
    LIVE_LOG_MIN_HEIGHT = 220
    HARDWARE_SPIN_MAX_WIDTH = 84
    ZONE_LIST_VISIBLE_ROWS = 10
    IGNORE_AREA_LIST_VISIBLE_ROWS = 5
    LIST_ROW_EXTRA_HEIGHT = 18


class DialogMetrics:
    MINIMUM_WIDTH = 360
    MESSAGE_MINIMUM_WIDTH = 280
    ICON_SIZE = 24


_NORMAL_METRICS = {
    Spacing: {
        "NONE": 0,
        "XXS": 1,
        "XS": 2,
        "SM": 4,
        "MD": 6,
        "ROW": 7,
        "LG": 8,
        "XL": 10,
        "XXL": 12,
        "WINDOW": 14,
        "GROUP_TOP": 16,
        "DIALOG": 18,
        "DIALOG_MARGIN": 20,
    },
    Margins: {
        "ZERO": (0, 0, 0, 0),
        "MAIN_WINDOW": (14, 14, 14, 14),
        "TAB_PAGE": (10, 10, 10, 10),
        "GROUP": (12, 16, 12, 12),
        "COMPACT_GROUP": (10, 12, 10, 10),
        "STATUS_BAR": (10, 8, 10, 8),
        "RELAY_INDICATOR": (4, 2, 4, 2),
        "RELAY_BOARD": (8, 4, 8, 4),
        "CAMERA_ROW": (0, 2, 0, 2),
        "DIALOG": (20, 18, 20, 18),
    },
    Padding: {
        "INPUT": (5, 8),
        "BUTTON": (6, 10),
        "TAB": (6, 10),
        "TOP_TAB": (5, 8),
        "LIST": 4,
        "LIST_ITEM": (5, 8),
        "GROUP_TITLE": (0, 6, 1, 6),
        "BOARD_LABEL_RIGHT": 6,
    },
    RightPanelMetrics: {
        "MINIMUM_CONTENT_HEIGHT": 180,
        "PREFERRED_CONTENT_HEIGHT": 520,
        "MINIMUM_WIDTH_CAP": 360,
        "PREFERRED_WIDTH_CAP": 410,
        "MEDIUM_SCREEN_WIDTH": 1540,
        "NARROW_SCREEN_WIDTH": 1320,
        "MEDIUM_MINIMUM_WIDTH_CAP": 340,
        "MEDIUM_PREFERRED_WIDTH_CAP": 380,
        "NARROW_MINIMUM_WIDTH_CAP": 330,
        "NARROW_PREFERRED_WIDTH_CAP": 360,
    },
    CameraViewMetrics: {
        "MINIMUM_HEIGHT": 180,
        "MINIMUM_WIDTH": 320,
        "MINIMUM_FONT_ROWS": 8,
        "OVERLAY_MARGIN": 12,
        "OVERLAY_TEXT_PADDING_X": 9,
        "OVERLAY_TEXT_PADDING_Y": 7,
        "GUIDANCE_PADDING_X": 12,
        "GUIDANCE_PADDING_Y": 9,
    },
    StatusBarMetrics: {
        "RELAY_LABEL_WIDTH": 18,
        "RELAY_LED_SIZE": 10,
        "DEFAULT_RELAYS_PER_BOARD": 8,
    },
    TabMetrics: {
        "CAMERA_LIST_MIN_HEIGHT": 180,
        "CAMERA_LIST_MAX_HEIGHT": 280,
        "CAMERA_REMOVE_BUTTON_MIN_HEIGHT": 26,
        "CAMERA_METRICS_MIN_HEIGHT": 110,
        "CAMERA_METRICS_MAX_HEIGHT": 200,
        "LIVE_LOG_MIN_HEIGHT": 220,
        "HARDWARE_SPIN_MAX_WIDTH": 84,
        "ZONE_LIST_VISIBLE_ROWS": 10,
        "IGNORE_AREA_LIST_VISIBLE_ROWS": 5,
        "LIST_ROW_EXTRA_HEIGHT": 18,
    },
    DialogMetrics: {
        "MINIMUM_WIDTH": 360,
        "MESSAGE_MINIMUM_WIDTH": 280,
        "ICON_SIZE": 24,
    },
}

_COMPACT_OVERRIDES = {
    Spacing: {
        "MD": 5,
        "ROW": 5,
        "LG": 6,
        "XL": 8,
        "XXL": 9,
        "WINDOW": 10,
        "GROUP_TOP": 14,
        "DIALOG": 14,
        "DIALOG_MARGIN": 16,
    },
    Margins: {
        "MAIN_WINDOW": (10, 10, 10, 10),
        "TAB_PAGE": (7, 7, 7, 7),
        "GROUP": (9, 12, 9, 9),
        "COMPACT_GROUP": (7, 9, 7, 7),
        "STATUS_BAR": (8, 6, 8, 6),
        "RELAY_INDICATOR": (3, 1, 3, 1),
        "RELAY_BOARD": (6, 3, 6, 3),
        "DIALOG": (16, 14, 16, 14),
    },
    Padding: {
        "INPUT": (4, 6),
        "BUTTON": (4, 8),
        "TAB": (4, 8),
        "TOP_TAB": (4, 6),
        "LIST": 3,
        "LIST_ITEM": (4, 6),
        "GROUP_TITLE": (0, 5, 1, 5),
        "BOARD_LABEL_RIGHT": 4,
    },
    RightPanelMetrics: {
        "MINIMUM_CONTENT_HEIGHT": 160,
        "PREFERRED_CONTENT_HEIGHT": 480,
        "MINIMUM_WIDTH_CAP": 340,
        "PREFERRED_WIDTH_CAP": 380,
        "MEDIUM_MINIMUM_WIDTH_CAP": 325,
        "MEDIUM_PREFERRED_WIDTH_CAP": 360,
        "NARROW_MINIMUM_WIDTH_CAP": 310,
        "NARROW_PREFERRED_WIDTH_CAP": 340,
    },
    CameraViewMetrics: {
        "MINIMUM_HEIGHT": 160,
        "MINIMUM_WIDTH": 284,
        "OVERLAY_MARGIN": 9,
        "OVERLAY_TEXT_PADDING_X": 7,
        "OVERLAY_TEXT_PADDING_Y": 5,
        "GUIDANCE_PADDING_X": 9,
        "GUIDANCE_PADDING_Y": 7,
    },
    StatusBarMetrics: {
        "RELAY_LABEL_WIDTH": 16,
        "RELAY_LED_SIZE": 9,
    },
    TabMetrics: {
        "CAMERA_LIST_MIN_HEIGHT": 150,
        "CAMERA_LIST_MAX_HEIGHT": 240,
        "CAMERA_REMOVE_BUTTON_MIN_HEIGHT": 24,
        "CAMERA_METRICS_MIN_HEIGHT": 90,
        "CAMERA_METRICS_MAX_HEIGHT": 170,
        "LIVE_LOG_MIN_HEIGHT": 180,
        "HARDWARE_SPIN_MAX_WIDTH": 76,
        "ZONE_LIST_VISIBLE_ROWS": 8,
        "IGNORE_AREA_LIST_VISIBLE_ROWS": 4,
        "LIST_ROW_EXTRA_HEIGHT": 14,
    },
    DialogMetrics: {
        "MINIMUM_WIDTH": 330,
        "MESSAGE_MINIMUM_WIDTH": 240,
        "ICON_SIZE": 22,
    },
}

_DENSITY_OVERRIDES = {
    UI_DENSITY_NORMAL: {},
    UI_DENSITY_COMPACT: _COMPACT_OVERRIDES,
}

_current_ui_density = UI_DENSITY_NORMAL


def available_ui_densities() -> tuple[str, ...]:
    return UI_DENSITY_NORMAL, UI_DENSITY_COMPACT


def normalize_ui_density(density: str | None) -> str | None:
    normalized = str(density or "").strip().lower().replace("_", "-")
    if normalized in {"", "auto", "default"}:
        return None
    if normalized in {"normal", "regular"}:
        return UI_DENSITY_NORMAL
    if normalized in {"compact", "dense"}:
        return UI_DENSITY_COMPACT
    return None


def current_ui_density() -> str:
    return _current_ui_density


def set_ui_density(density: str | None) -> str:
    global _current_ui_density
    resolved_density = normalize_ui_density(density) or UI_DENSITY_NORMAL
    for namespace, values in _resolved_metrics(resolved_density).items():
        for name, value in values.items():
            setattr(namespace, name, value)
    _current_ui_density = resolved_density
    return resolved_density


def resolve_ui_density_for_screen(
    available_width: int | None = None,
    available_height: int | None = None,
    *,
    requested_density: str | None = None,
) -> str:
    manual_density = normalize_ui_density(requested_density)
    if manual_density is not None:
        return manual_density
    if available_width is not None and available_width <= COMPACT_SCREEN_WIDTH:
        return UI_DENSITY_COMPACT
    if available_height is not None and available_height <= COMPACT_SCREEN_HEIGHT:
        return UI_DENSITY_COMPACT
    return UI_DENSITY_NORMAL


def _resolved_metrics(density: str) -> dict[type, dict[str, object]]:
    values = {namespace: dict(metrics) for namespace, metrics in _NORMAL_METRICS.items()}
    for namespace, overrides in _DENSITY_OVERRIDES.get(density, {}).items():
        values[namespace].update(overrides)
    return values


set_ui_density(UI_DENSITY_NORMAL)
