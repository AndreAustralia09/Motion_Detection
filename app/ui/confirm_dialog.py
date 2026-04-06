from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QStyle, QVBoxLayout

from app.ui.theme import build_stylesheet
from app.ui.ui_metrics import DialogMetrics, Margins, Spacing
from app.ui.windows_theme import apply_native_title_bar_theme


class ConfirmDialog(QDialog):
    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str | None = "Cancel",
        dialog_kind: str = "question",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setObjectName("ConfirmDialog")
        self.setMinimumWidth(DialogMetrics.MINIMUM_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*Margins.DIALOG)
        layout.setSpacing(Spacing.WINDOW)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(*Margins.ZERO)
        header_row.setSpacing(Spacing.XXL)

        icon_label = QLabel()
        icon_label.setObjectName("DialogIcon")
        icon_label.setPixmap(self._dialog_icon(dialog_kind))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        header_row.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(*Margins.ZERO)
        text_column.setSpacing(Spacing.LG)

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")

        message_label = QLabel(message)
        message_label.setObjectName("DialogMessage")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        message_label.setMinimumWidth(DialogMetrics.MESSAGE_MINIMUM_WIDTH)

        buttons = QDialogButtonBox(self)
        confirm_button = buttons.addButton(confirm_text, QDialogButtonBox.ButtonRole.AcceptRole)
        confirm_button.setProperty("accent", True)
        confirm_button.setAutoDefault(False)
        confirm_button.setDefault(False)
        if cancel_text is not None:
            cancel_button = buttons.addButton(cancel_text, QDialogButtonBox.ButtonRole.RejectRole)
            cancel_button.setAutoDefault(False)
            cancel_button.setDefault(False)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        text_column.addWidget(title_label)
        text_column.addWidget(message_label)
        header_row.addLayout(text_column, 1)

        layout.addLayout(header_row)
        layout.addWidget(buttons)

        theme_name = getattr(parent, "_theme_name", "Light") if parent is not None else "Light"
        self.setStyleSheet(build_stylesheet(theme_name))
        apply_native_title_bar_theme(self, theme_name)

    def _dialog_icon(self, dialog_kind: str) -> QPixmap:
        icon_map = {
            "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "warning": QStyle.StandardPixmap.SP_MessageBoxWarning,
            "error": QStyle.StandardPixmap.SP_MessageBoxCritical,
            "question": QStyle.StandardPixmap.SP_MessageBoxQuestion,
        }
        standard_icon = self.style().standardIcon(icon_map.get(dialog_kind, QStyle.StandardPixmap.SP_MessageBoxQuestion))
        return standard_icon.pixmap(DialogMetrics.ICON_SIZE, DialogMetrics.ICON_SIZE)

    @classmethod
    def ask(
        cls,
        parent,
        title: str,
        message: str,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
    ) -> bool:
        dialog = cls(
            title=title,
            message=message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            dialog_kind="question",
            parent=parent,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    @classmethod
    def ask_save_discard_cancel(
        cls,
        parent,
        *,
        title: str,
        message: str,
        save_text: str = "Save",
        discard_text: str = "Discard",
        cancel_text: str = "Cancel",
    ) -> str:
        dialog = cls(
            title=title,
            message=message,
            confirm_text=save_text,
            cancel_text=cancel_text,
            dialog_kind="question",
            parent=parent,
        )
        buttons = dialog.findChild(QDialogButtonBox)
        if buttons is None:
            return "cancel"

        save_button = buttons.buttons()[0] if buttons.buttons() else None
        discard_button = QPushButton(discard_text, dialog)
        discard_button.clicked.connect(lambda: dialog.done(2))
        buttons.addButton(discard_button, QDialogButtonBox.ButtonRole.DestructiveRole)
        if save_button is not None:
            buttons.removeButton(save_button)
            buttons.addButton(save_button, QDialogButtonBox.ButtonRole.AcceptRole)
            save_button.setProperty("accent", True)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            return "save"
        if result == 2:
            return "discard"
        return "cancel"

    @classmethod
    def ask_choice(
        cls,
        parent,
        *,
        title: str,
        message: str,
        choices: list[tuple[str, str, QDialogButtonBox.ButtonRole, bool]],
        dialog_kind: str = "question",
    ) -> str:
        dialog = cls(
            title=title,
            message=message,
            confirm_text="OK",
            cancel_text=None,
            dialog_kind=dialog_kind,
            parent=parent,
        )
        buttons = dialog.findChild(QDialogButtonBox)
        if buttons is None:
            return "cancel"

        for button in list(buttons.buttons()):
            buttons.removeButton(button)
            button.deleteLater()

        result_map: dict[int, str] = {}
        for index, (key, label, role, accent) in enumerate(choices, start=1):
            button = QPushButton(label, dialog)
            if accent:
                button.setProperty("accent", True)
            button.setAutoDefault(False)
            button.setDefault(False)
            result_code = index + 10
            result_map[result_code] = key
            button.clicked.connect(lambda _checked=False, code=result_code: dialog.done(code))
            buttons.addButton(button, role)

        result = dialog.exec()
        return result_map.get(result, "cancel")

    @classmethod
    def inform(
        cls,
        parent,
        *,
        title: str,
        message: str,
        button_text: str = "OK",
    ) -> None:
        dialog = cls(
            title=title,
            message=message,
            confirm_text=button_text,
            cancel_text=None,
            dialog_kind="info",
            parent=parent,
        )
        dialog.exec()

    @classmethod
    def warn(
        cls,
        parent,
        *,
        title: str,
        message: str,
        button_text: str = "OK",
    ) -> None:
        dialog = cls(
            title=title,
            message=message,
            confirm_text=button_text,
            cancel_text=None,
            dialog_kind="warning",
            parent=parent,
        )
        dialog.exec()

    @classmethod
    def error(
        cls,
        parent,
        *,
        title: str,
        message: str,
        button_text: str = "OK",
    ) -> None:
        dialog = cls(
            title=title,
            message=message,
            confirm_text=button_text,
            cancel_text=None,
            dialog_kind="error",
            parent=parent,
        )
        dialog.exec()
