from __future__ import annotations

from pathlib import Path

from app.ui.ui_metrics import FontSize, LineHeight, Padding, Radius, Spacing


_CHECKMARK_PATH = Path(__file__).with_name("assets").joinpath("checkmark.svg").as_posix()


def build_stylesheet(theme: str) -> str:
    theme_key = str(theme or "Light").strip().lower()
    if theme_key == "dark":
        return _dark_stylesheet()
    return _light_stylesheet()


def _light_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#CentralWidget, QWidget#MultiRowTabWidget, QWidget#TabBarContainer,
    QScrollArea#TabPageScrollArea, QScrollArea#TabPageScrollArea > QWidget,
    QScrollArea#TabPageScrollArea > QWidget > QWidget {{
        background: #EEF2F6;
        color: #17212B;
    }}
    QLabel {{
        color: #17212B;
        font-size: {FontSize.SMALL}px;
    }}
    QLabel#ValueLabel {{
        color: #0F1720;
        font-size: {FontSize.BODY}px;
        font-weight: 600;
    }}
    QLabel#SummaryLabel {{
        color: #334155;
        font-size: {FontSize.BODY}px;
        line-height: {LineHeight.NORMAL};
    }}
    QLabel#SerialStatusIndicator {{
        font-size: {FontSize.SMALL}px;
        font-weight: 700;
        color: #4D6F90;
    }}
    QLabel#SerialStatusIndicator[serialState="connected"] {{
        color: #2F8B54;
    }}
    QLabel#SerialStatusIndicator[serialState="connecting"] {{
        color: #315D8F;
    }}
    QLabel#SerialStatusIndicator[serialState="reconnecting"] {{
        color: #B26A00;
    }}
    QLabel#SerialStatusIndicator[serialState="error"] {{
        color: #C83A3A;
    }}
    QLabel#SerialStatusIndicator[serialState="disconnected"] {{
        color: #C83A3A;
    }}
    QLabel#SerialStatusIndicator[serialState="simulation"] {{
        color: #4D6F90;
    }}
    QLabel#DiagnosticsBlock {{
        color: #243241;
        font-size: {FontSize.SMALL}px;
        line-height: {LineHeight.DIAGNOSTICS_LIGHT};
    }}
    QScrollArea#CardScrollArea {{
        background: #F8FBFD;
        border: 1px solid #D8E0E8;
        border-radius: {Radius.MD}px;
    }}
    QScrollArea#CardScrollArea > QWidget > QWidget#CardScrollContent {{
        background: #F8FBFD;
    }}
    QGroupBox {{
        background: #F8FBFD;
        border: 1px solid #D8E0E8;
        border-radius: {Radius.XL}px;
        margin-top: {Spacing.LG}px;
        font-size: {FontSize.HEADING}px;
        font-weight: 700;
        color: #223041;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {Spacing.XXL}px;
        top: -{Spacing.XS}px;
        padding: {Padding.GROUP_TITLE[0]}px {Padding.GROUP_TITLE[1]}px {Padding.GROUP_TITLE[2]}px {Padding.GROUP_TITLE[3]}px;
    }}
    QGroupBox[dirtyCard="true"] {{
        border: 2px solid #C83A3A;
    }}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QListView, QTreeWidget {{
        background: #F9FBFC;
        border: 1px solid #CAD5E0;
        border-radius: {Radius.MD}px;
        padding: {Padding.INPUT[0]}px {Padding.INPUT[1]}px;
        color: #17212B;
        selection-background-color: #D7E7F7;
        selection-color: #102030;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QListWidget:focus, QListView:focus, QTreeWidget:focus {{
        border: 1px solid #6B94BE;
        background: #FFFFFF;
    }}
    QAbstractItemView {{
        outline: 0;
        show-decoration-selected: 1;
    }}
    QListWidget#PrimaryList {{
        padding: {Padding.LIST}px;
    }}
    QListWidget::item, QListView::item, QTreeWidget::item {{
        padding: {Padding.LIST_ITEM[0]}px {Padding.LIST_ITEM[1]}px;
        border-radius: {Radius.SM}px;
        margin: {Spacing.XXS}px 0;
        outline: none;
    }}
    QListWidget::item:selected, QListView::item:selected, QTreeWidget::item:selected {{
        background: #DCEAF8;
        color: #102030;
    }}
    QListWidget::item:focus, QListView::item:focus, QTreeWidget::item:focus {{
        outline: none;
        border: none;
    }}
    QListWidget:focus, QListView:focus, QTreeWidget:focus {{
        outline: none;
        border-color: #6B94BE;
    }}
    QPushButton {{
        background: #F4F7FA;
        border: 1px solid #C9D4DE;
        border-radius: {Radius.MD}px;
        padding: {Padding.BUTTON[0]}px {Padding.BUTTON[1]}px;
        color: #17212B;
        font-weight: 600;
        outline: none;
    }}
    QPushButton:hover {{
        background: #E8EFF5;
        border-color: #AEBECD;
    }}
    QPushButton:focus {{
        border-color: #6B94BE;
        outline: none;
    }}
    QPushButton:pressed {{
        background: #D8E4EF;
    }}
    QPushButton[accent="true"] {{
        background: #274C77;
        color: #FFFFFF;
        border: 1px solid #274C77;
    }}
    QPushButton[accent="true"]:hover {{
        background: #315D8F;
        border-color: #315D8F;
    }}
    QCheckBox {{
        spacing: {Spacing.LG}px;
        color: #223041;
        font-weight: 500;
    }}
    QCheckBox::indicator {{
        width: {Spacing.GROUP_TOP}px;
        height: {Spacing.GROUP_TOP}px;
        border-radius: {Radius.XS}px;
        border: 1px solid #8FA4B7;
        background: #FFFFFF;
    }}
    QCheckBox::indicator:hover {{
        border-color: #6B94BE;
        background: #F4F8FC;
    }}
    QCheckBox::indicator:checked {{
        background: #2B5F91;
        border-color: #234E77;
        image: url("{_CHECKMARK_PATH}");
    }}
    QCheckBox::indicator:disabled {{
        background: #E6ECF1;
        border-color: #C4D0DB;
    }}
    QTabBar#CameraTabs {{
        background: #E4EAF0;
    }}
    QTabBar#CameraTabs::tab {{
        background: #D4DEE7;
        color: #3D4E60;
        padding: {Padding.TAB[0]}px {Padding.TAB[1]}px;
        margin-right: {Radius.SM}px;
        border-top-left-radius: {Radius.MD}px;
        border-top-right-radius: {Radius.MD}px;
    }}
    QTabBar#CameraTabs::tab:selected {{
        background: #3E6A95;
        color: #FFFFFF;
        font-weight: 700;
    }}
    QWidget#CameraSurface {{
        border: 1px solid #25313D;
        border-radius: {Radius.XL}px;
        background: #11161C;
    }}
    QWidget#StatusBarWidget {{
        background: #F8FBFD;
        border: 1px solid #D8E0E8;
        border-radius: {Radius.XL}px;
    }}
    QLabel#StatusSummary {{
        color: #17212B;
        font-size: {FontSize.BODY}px;
        font-weight: 600;
    }}
    QWidget#RelaysContainer {{
        background: transparent;
    }}
    QWidget#RelayBoard {{
        background: #FBFDFF;
        border: 1px solid #D6E0E8;
        border-radius: {Radius.MD}px;
    }}
    QWidget#RelayIndicator {{
        background: transparent;
    }}
    QFrame#RelayLed {{
        background: #818A94;
        border: 1px solid #58616B;
    }}
    QFrame#RelayLed[on="true"] {{
        background: #45C97A;
        border: 1px solid #2F8B54;
    }}
    QLabel#RelayLabel, QLabel#BoardLabel {{
        color: #17212B;
        font-size: {FontSize.SMALL}px;
        font-weight: 600;
    }}
    QLabel#BoardLabel {{
        padding-right: {Padding.BOARD_LABEL_RIGHT}px;
    }}
    QStackedWidget#TabStack {{
        background: #EEF2F6;
        border: none;
        border-radius: {Radius.XL}px;
    }}
    QPushButton#TopTabButton {{
        background: #DDE6EE;
        border: 1px solid #CBD6E0;
        border-radius: {Radius.LG}px;
        padding: {Padding.TOP_TAB[0]}px {Padding.TOP_TAB[1]}px;
        color: #334557;
        font-weight: 600;
        outline: none;
    }}
    QPushButton#TopTabButton:hover {{
        background: #D2DFEA;
    }}
    QPushButton#TopTabButton:focus {{
        border-color: #6B94BE;
        outline: none;
    }}
    QPushButton#TopTabButton:checked {{
        background: #3E6A95;
        border: 1px solid #3E6A95;
        color: #FFFFFF;
    }}
    QPushButton#TopTabButton[dirtyTab="true"] {{
        border: 2px solid #C83A3A;
    }}
    QPushButton#TopTabButton[dirtyTab="true"]:checked {{
        border: 2px solid #C83A3A;
    }}
    QDialog#ConfirmDialog {{
        background: #F8FBFD;
        border: 1px solid #D8E0E8;
        border-radius: {Radius.XL}px;
    }}
    QLabel#DialogTitle {{
        color: #0F1720;
        font-size: {FontSize.HEADING}px;
        font-weight: 700;
    }}
    QLabel#DialogMessage {{
        color: #17212B;
        font-size: {FontSize.BODY}px;
        font-weight: 500;
    }}
    QTextEdit#LogOutput {{
        font-family: Consolas, "Courier New", monospace;
        font-size: {FontSize.SMALL}px;
        line-height: {LineHeight.NORMAL};
        background: #0F1720;
        color: #DBE7F3;
        border: 1px solid #243241;
        border-radius: {Radius.MD}px;
    }}
    """


def _dark_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget#CentralWidget, QWidget#MultiRowTabWidget, QWidget#TabBarContainer,
    QScrollArea#TabPageScrollArea, QScrollArea#TabPageScrollArea > QWidget,
    QScrollArea#TabPageScrollArea > QWidget > QWidget {{
        background: #0E1318;
        color: #E6EDF3;
    }}
    QLabel {{
        color: #E6EDF3;
        font-size: {FontSize.SMALL}px;
    }}
    QLabel#ValueLabel {{
        color: #F5F8FB;
        font-size: {FontSize.BODY}px;
        font-weight: 600;
    }}
    QLabel#SummaryLabel {{
        color: #B4C0CC;
        font-size: {FontSize.BODY}px;
        line-height: {LineHeight.NORMAL};
    }}
    QLabel#SerialStatusIndicator {{
        font-size: {FontSize.SMALL}px;
        font-weight: 700;
        color: #8EAED0;
    }}
    QLabel#SerialStatusIndicator[serialState="connected"] {{
        color: #47D17F;
    }}
    QLabel#SerialStatusIndicator[serialState="connecting"] {{
        color: #6DA6D8;
    }}
    QLabel#SerialStatusIndicator[serialState="reconnecting"] {{
        color: #D6A24C;
    }}
    QLabel#SerialStatusIndicator[serialState="error"] {{
        color: #E97451;
    }}
    QLabel#SerialStatusIndicator[serialState="disconnected"] {{
        color: #E97451;
    }}
    QLabel#SerialStatusIndicator[serialState="simulation"] {{
        color: #8EAED0;
    }}
    QLabel#DiagnosticsBlock {{
        color: #D5DFE8;
        font-size: {FontSize.SMALL}px;
        line-height: {LineHeight.DIAGNOSTICS_DARK};
    }}
    QScrollArea#CardScrollArea {{
        background: #212B35;
        border: 1px solid #28313B;
        border-radius: {Radius.MD}px;
    }}
    QScrollArea#CardScrollArea > QWidget > QWidget#CardScrollContent {{
        background: #212B35;
    }}
    QGroupBox {{
        background: #212B35;
        border: 1px solid #28313B;
        border-radius: {Radius.XL}px;
        margin-top: {Spacing.LG}px;
        font-size: {FontSize.HEADING}px;
        font-weight: 700;
        color: #E3EAF1;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {Spacing.XXL}px;
        top: -{Spacing.XS}px;
        padding: {Padding.GROUP_TITLE[0]}px {Padding.GROUP_TITLE[1]}px {Padding.GROUP_TITLE[2]}px {Padding.GROUP_TITLE[3]}px;
    }}
    QGroupBox[dirtyCard="true"] {{
        border: 2px solid #D14A4A;
    }}
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QListWidget, QListView, QTreeWidget {{
        background: #10161C;
        border: 1px solid #33414F;
        border-radius: {Radius.MD}px;
        padding: {Padding.INPUT[0]}px {Padding.INPUT[1]}px;
        color: #E6EDF3;
        selection-background-color: #2D5B86;
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QListWidget:focus, QListView:focus, QTreeWidget:focus {{
        border: 1px solid #6DA6D8;
        background: #131A21;
    }}
    QAbstractItemView {{
        outline: 0;
        show-decoration-selected: 1;
    }}
    QListWidget#PrimaryList {{
        padding: {Padding.LIST}px;
    }}
    QListWidget::item, QListView::item, QTreeWidget::item {{
        padding: {Padding.LIST_ITEM[0]}px {Padding.LIST_ITEM[1]}px;
        border-radius: {Radius.SM}px;
        margin: {Spacing.XXS}px 0;
        outline: none;
    }}
    QListWidget::item:selected, QListView::item:selected, QTreeWidget::item:selected {{
        background: #203B53;
        color: #FFFFFF;
    }}
    QListWidget::item:focus, QListView::item:focus, QTreeWidget::item:focus {{
        outline: none;
        border: none;
    }}
    QListWidget:focus, QListView:focus, QTreeWidget:focus {{
        outline: none;
        border-color: #6DA6D8;
    }}
    QPushButton {{
        background: #182029;
        border: 1px solid #33414F;
        border-radius: {Radius.MD}px;
        padding: {Padding.BUTTON[0]}px {Padding.BUTTON[1]}px;
        color: #E6EDF3;
        font-weight: 600;
        outline: none;
    }}
    QPushButton:hover {{
        background: #1E2933;
        border-color: #475767;
    }}
    QPushButton:focus {{
        border-color: #6DA6D8;
        outline: none;
    }}
    QPushButton:pressed {{
        background: #24313E;
    }}
    QPushButton[accent="true"] {{
        background: #3E74A6;
        color: #FFFFFF;
        border: 1px solid #3E74A6;
    }}
    QPushButton[accent="true"]:hover {{
        background: #4A82B5;
        border-color: #4A82B5;
    }}
    QCheckBox {{
        spacing: {Spacing.LG}px;
        color: #DDE6EE;
        font-weight: 500;
    }}
    QCheckBox::indicator {{
        width: {Spacing.GROUP_TOP}px;
        height: {Spacing.GROUP_TOP}px;
        border-radius: {Radius.XS}px;
        border: 1px solid #6C7F91;
        background: #0B1015;
    }}
    QCheckBox::indicator:hover {{
        border-color: #8EAED0;
        background: #10171E;
    }}
    QCheckBox::indicator:checked {{
        background: #4A82B5;
        border-color: #5B94C9;
        image: url("{_CHECKMARK_PATH}");
    }}
    QCheckBox::indicator:disabled {{
        background: #151C23;
        border-color: #3C4854;
    }}
    QTabBar#CameraTabs {{
        background: #10161C;
    }}
    QTabBar#CameraTabs::tab {{
        background: #1A222A;
        color: #AEBCC9;
        padding: {Padding.TAB[0]}px {Padding.TAB[1]}px;
        margin-right: {Radius.SM}px;
        border-top-left-radius: {Radius.MD}px;
        border-top-right-radius: {Radius.MD}px;
    }}
    QTabBar#CameraTabs::tab:selected {{
        background: #2E5E8A;
        color: #FFFFFF;
        font-weight: 700;
    }}
    QWidget#CameraSurface {{
        border: 1px solid #2B3743;
        border-radius: {Radius.XL}px;
        background: #0C1117;
    }}
    QWidget#StatusBarWidget {{
        background: #192029;
        border: 1px solid #28313B;
        border-radius: {Radius.XL}px;
    }}
    QLabel#StatusSummary {{
        color: #E8EEF4;
        font-size: {FontSize.BODY}px;
        font-weight: 600;
    }}
    QWidget#RelaysContainer {{
        background: transparent;
    }}
    QWidget#RelayBoard {{
        background: #1C232C;
        border: 1px solid #2B3742;
        border-radius: {Radius.MD}px;
    }}
    QWidget#RelayIndicator {{
        background: transparent;
    }}
    QFrame#RelayLed {{
        background: #4B5560;
        border: 1px solid #6B7682;
    }}
    QFrame#RelayLed[on="true"] {{
        background: #47D17F;
        border: 1px solid #2D9C5A;
    }}
    QLabel#RelayLabel, QLabel#BoardLabel {{
        color: #E6EDF3;
        font-size: {FontSize.SMALL}px;
        font-weight: 600;
    }}
    QLabel#BoardLabel {{
        padding-right: {Padding.BOARD_LABEL_RIGHT}px;
    }}
    QStackedWidget#TabStack {{
        background: #0E1318;
        border: none;
        border-radius: {Radius.XL}px;
    }}
    QPushButton#TopTabButton {{
        background: #151D24;
        border: 1px solid #33414F;
        border-radius: {Radius.LG}px;
        padding: {Padding.TOP_TAB[0]}px {Padding.TOP_TAB[1]}px;
        color: #C5D0DA;
        font-weight: 600;
        outline: none;
    }}
    QPushButton#TopTabButton:hover {{
        background: #1C2731;
    }}
    QPushButton#TopTabButton:focus {{
        border-color: #6DA6D8;
        outline: none;
    }}
    QPushButton#TopTabButton:checked {{
        background: #2E5E8A;
        border: 1px solid #3E74A6;
        color: #FFFFFF;
    }}
    QPushButton#TopTabButton[dirtyTab="true"] {{
        border: 2px solid #D14A4A;
    }}
    QPushButton#TopTabButton[dirtyTab="true"]:checked {{
        border: 2px solid #D14A4A;
    }}
    QDialog#ConfirmDialog {{
        background: #192029;
        border: 1px solid #28313B;
        border-radius: {Radius.XL}px;
    }}
    QLabel#DialogTitle {{
        color: #F3F7FB;
        font-size: {FontSize.HEADING}px;
        font-weight: 700;
    }}
    QLabel#DialogMessage {{
        color: #E6EDF3;
        font-size: {FontSize.BODY}px;
        font-weight: 500;
    }}
    QTextEdit#LogOutput {{
        font-family: Consolas, "Courier New", monospace;
        font-size: {FontSize.SMALL}px;
        line-height: {LineHeight.NORMAL};
        background: #0B1015;
        color: #D7E0E8;
        border: 1px solid #24303B;
        border-radius: {Radius.MD}px;
    }}
    """
