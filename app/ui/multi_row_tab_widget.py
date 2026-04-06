from __future__ import annotations

import math

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QGridLayout, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from app.ui.ui_metrics import Margins, RightPanelMetrics, Spacing


class MultiRowTabWidget(QWidget):
    currentChanged = Signal(int)
    MINIMUM_CONTENT_HEIGHT = RightPanelMetrics.MINIMUM_CONTENT_HEIGHT
    PREFERRED_CONTENT_HEIGHT = RightPanelMetrics.PREFERRED_CONTENT_HEIGHT
    MINIMUM_WIDTH_CAP = RightPanelMetrics.MINIMUM_WIDTH_CAP
    PREFERRED_WIDTH_CAP = RightPanelMetrics.PREFERRED_WIDTH_CAP
    MEDIUM_SCREEN_WIDTH = RightPanelMetrics.MEDIUM_SCREEN_WIDTH
    NARROW_SCREEN_WIDTH = RightPanelMetrics.NARROW_SCREEN_WIDTH
    MEDIUM_MINIMUM_WIDTH_CAP = RightPanelMetrics.MEDIUM_MINIMUM_WIDTH_CAP
    MEDIUM_PREFERRED_WIDTH_CAP = RightPanelMetrics.MEDIUM_PREFERRED_WIDTH_CAP
    NARROW_MINIMUM_WIDTH_CAP = RightPanelMetrics.NARROW_MINIMUM_WIDTH_CAP
    NARROW_PREFERRED_WIDTH_CAP = RightPanelMetrics.NARROW_PREFERRED_WIDTH_CAP

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._sync_metric_aliases()
        self.setObjectName("MultiRowTabWidget")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        root = QVBoxLayout(self)
        root.setContentsMargins(*Margins.ZERO)
        root.setSpacing(Spacing.MD)

        self.tab_bar_container = QWidget()
        self.tab_bar_container.setObjectName("TabBarContainer")
        self.tab_layout = QGridLayout(self.tab_bar_container)
        self.tab_layout.setContentsMargins(*Margins.ZERO)
        self.tab_layout.setHorizontalSpacing(Spacing.MD)
        self.tab_layout.setVerticalSpacing(Spacing.MD)

        self.stack = QStackedWidget()
        self.stack.setObjectName("TabStack")
        self.stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        root.addWidget(self.tab_bar_container)
        root.addWidget(self.stack, 1)

        self._buttons: list[QPushButton] = []
        self._pages: list[QWidget] = []
        self._scroll_areas: list[QScrollArea] = []
        self._current_index = -1

    def addTab(self, widget: QWidget, title: str) -> int:
        scroll_area = self._wrap_page(widget)
        index = self.stack.addWidget(scroll_area)
        self._pages.append(widget)
        self._scroll_areas.append(scroll_area)
        button = QPushButton(title)
        button.setObjectName("TopTabButton")
        button.setCheckable(True)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(lambda _checked=False, idx=index: self.setCurrentIndex(idx))
        self._buttons.append(button)
        self._relayout_buttons()
        if self._current_index < 0:
            self.setCurrentIndex(0)
        return index

    def setCurrentIndex(self, index: int) -> None:
        if not (0 <= index < self.stack.count()) or index == self._current_index:
            return
        self._current_index = index
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self._buttons):
            button.setChecked(button_index == index)
        self.currentChanged.emit(index)

    def currentIndex(self) -> int:
        return self._current_index

    def widget(self, index: int) -> QWidget | None:
        if 0 <= index < len(self._pages):
            return self._pages[index]
        return None

    def count(self) -> int:
        return self.stack.count()

    def setTabDirty(self, index: int, is_dirty: bool) -> None:
        if not (0 <= index < len(self._buttons)):
            return
        button = self._buttons[index]
        button.setProperty("dirtyTab", bool(is_dirty))
        style = button.style()
        if style is not None:
            style.unpolish(button)
            style.polish(button)
        button.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_buttons()

    def minimumSizeHint(self) -> QSize:
        chrome = self._chrome_height()
        return QSize(self._minimum_width_hint(), chrome + RightPanelMetrics.MINIMUM_CONTENT_HEIGHT)

    def sizeHint(self) -> QSize:
        chrome = self._chrome_height()
        content_hint = RightPanelMetrics.PREFERRED_CONTENT_HEIGHT
        current_page = self.widget(self._current_index)
        if current_page is not None:
            content_hint = min(max(current_page.sizeHint().height(), RightPanelMetrics.MINIMUM_CONTENT_HEIGHT), content_hint)
        return QSize(self._preferred_width_hint(), chrome + content_hint)

    def _wrap_page(self, widget: QWidget) -> QScrollArea:
        widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        scroll_area = QScrollArea()
        scroll_area.setObjectName("TabPageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll_area.setMinimumHeight(Spacing.NONE)
        scroll_area.setWidget(widget)
        return scroll_area

    def _chrome_height(self) -> int:
        return self.tab_bar_container.sizeHint().height() + self.layout().spacing()

    def _minimum_width_hint(self) -> int:
        minimum_cap, _preferred_cap = self._responsive_width_caps()
        button_width = max((button.minimumSizeHint().width() for button in self._buttons), default=0)
        page_width = max((page.minimumSizeHint().width() for page in self._pages), default=0)
        return max(button_width, min(page_width, minimum_cap))

    def _preferred_width_hint(self) -> int:
        _minimum_cap, preferred_cap = self._responsive_width_caps()
        button_width = max((button.sizeHint().width() for button in self._buttons), default=0)
        page_width = max((page.sizeHint().width() for page in self._pages), default=0)
        return max(button_width, min(page_width, preferred_cap))

    def _responsive_width_caps(self, available_width: int | None = None) -> tuple[int, int]:
        if available_width is None:
            available_width = self._available_screen_width()
        if available_width is None:
            return RightPanelMetrics.MINIMUM_WIDTH_CAP, RightPanelMetrics.PREFERRED_WIDTH_CAP
        if available_width <= RightPanelMetrics.NARROW_SCREEN_WIDTH:
            return RightPanelMetrics.NARROW_MINIMUM_WIDTH_CAP, RightPanelMetrics.NARROW_PREFERRED_WIDTH_CAP
        if available_width <= RightPanelMetrics.MEDIUM_SCREEN_WIDTH:
            return RightPanelMetrics.MEDIUM_MINIMUM_WIDTH_CAP, RightPanelMetrics.MEDIUM_PREFERRED_WIDTH_CAP
        return RightPanelMetrics.MINIMUM_WIDTH_CAP, RightPanelMetrics.PREFERRED_WIDTH_CAP

    @classmethod
    def _sync_metric_aliases(cls) -> None:
        cls.MINIMUM_CONTENT_HEIGHT = RightPanelMetrics.MINIMUM_CONTENT_HEIGHT
        cls.PREFERRED_CONTENT_HEIGHT = RightPanelMetrics.PREFERRED_CONTENT_HEIGHT
        cls.MINIMUM_WIDTH_CAP = RightPanelMetrics.MINIMUM_WIDTH_CAP
        cls.PREFERRED_WIDTH_CAP = RightPanelMetrics.PREFERRED_WIDTH_CAP
        cls.MEDIUM_SCREEN_WIDTH = RightPanelMetrics.MEDIUM_SCREEN_WIDTH
        cls.NARROW_SCREEN_WIDTH = RightPanelMetrics.NARROW_SCREEN_WIDTH
        cls.MEDIUM_MINIMUM_WIDTH_CAP = RightPanelMetrics.MEDIUM_MINIMUM_WIDTH_CAP
        cls.MEDIUM_PREFERRED_WIDTH_CAP = RightPanelMetrics.MEDIUM_PREFERRED_WIDTH_CAP
        cls.NARROW_MINIMUM_WIDTH_CAP = RightPanelMetrics.NARROW_MINIMUM_WIDTH_CAP
        cls.NARROW_PREFERRED_WIDTH_CAP = RightPanelMetrics.NARROW_PREFERRED_WIDTH_CAP

    def _available_screen_width(self) -> int | None:
        screen = self.screen()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None
        return screen.availableGeometry().width()

    def _relayout_buttons(self) -> None:
        while self.tab_layout.count():
            item = self.tab_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self.tab_bar_container)

        button_count = len(self._buttons)
        if button_count == 0:
            return

        available_width = max(1, self.tab_bar_container.width())
        max_button_width = max(button.sizeHint().width() for button in self._buttons)
        single_row_width = button_count * (max_button_width + self.tab_layout.horizontalSpacing())
        rows = 1 if single_row_width <= available_width else 2
        columns = math.ceil(button_count / rows)

        for index, button in enumerate(self._buttons):
            row = index // columns
            column = index % columns
            self.tab_layout.addWidget(button, row, column)
