from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout, QWidget

from .theme import make_interactive


class ArchivePreviewDialog(QDialog):
    def __init__(self, parent: QWidget, archive_name: str, text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Содержимое архива - {archive_name}")
        self.resize(820, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        preview = QTextEdit(self)
        preview.setReadOnly(True)
        preview.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        preview.setPlainText(text)
        layout.addWidget(preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        make_interactive(close_button, "Закрыть окно просмотра содержимого архива")
        layout.addWidget(buttons)
