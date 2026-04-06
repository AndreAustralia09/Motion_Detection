from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.ui.ui_metrics import Margins, Spacing


class PreferencesTab(QWidget):
    theme_changed = Signal(str)
    preferences_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.TAB_PAGE)
        layout.setSpacing(Spacing.LG)

        self.preferences_group = QGroupBox("Preferences")
        preferences_layout = QVBoxLayout(self.preferences_group)
        preferences_layout.setContentsMargins(*Margins.GROUP)
        preferences_layout.setSpacing(Spacing.ROW)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.auto_load = QCheckBox("Auto-load last project")
        self.start_minimized = QCheckBox("Start minimized")
        self.show_fps_overlay = QCheckBox("Show FPS / inference overlay")

        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(*Margins.ZERO)
        theme_row.setSpacing(Spacing.LG)
        theme_row.addWidget(QLabel("Theme"))
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch(1)

        preferences_layout.addLayout(theme_row)
        preferences_layout.addWidget(self.auto_load)
        preferences_layout.addWidget(self.start_minimized)
        preferences_layout.addWidget(self.show_fps_overlay)

        layout.addWidget(self.preferences_group)
        layout.addStretch(1)

        self.theme_combo.currentTextChanged.connect(self.theme_changed)
        self.auto_load.toggled.connect(self.preferences_changed)
        self.start_minimized.toggled.connect(self.preferences_changed)
        self.show_fps_overlay.toggled.connect(self.preferences_changed)
