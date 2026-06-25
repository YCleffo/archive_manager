from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from .icons import IconFactory
from .theme import make_interactive


class PathBar(QFrame):
    navigate_requested = Signal(str)
    browse_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PathBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        label = QLabel("Путь", self)
        layout.addWidget(label)

        self.path_edit = QLineEdit(self)
        self.path_edit.setMinimumHeight(34)
        self.path_edit.setToolTip("Введите путь к папке и нажмите Enter")
        self.path_edit.returnPressed.connect(self._emit_navigate)
        layout.addWidget(self.path_edit, 1)

        go_button = QPushButton("Перейти", self)
        go_button.setMinimumHeight(32)
        go_button.setIcon(icons.icon("open"))
        go_button.clicked.connect(self._emit_navigate)
        make_interactive(go_button, "Открыть папку из строки пути")
        layout.addWidget(go_button)

        browse_button = QPushButton("Обзор", self)
        browse_button.setMinimumHeight(32)
        browse_button.setIcon(icons.icon("folder"))
        browse_button.clicked.connect(self.browse_requested.emit)
        make_interactive(browse_button, "Выбрать папку через системный диалог")
        layout.addWidget(browse_button)

    def set_path(self, path: str) -> None:
        self.path_edit.setText(path)

    def focus_path(self) -> None:
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _emit_navigate(self) -> None:
        self.navigate_requested.emit(self.path_edit.text().strip())
