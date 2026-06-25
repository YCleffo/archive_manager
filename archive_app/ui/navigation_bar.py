from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

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

        go_button = QToolButton(self)
        go_button.setObjectName("PathButton")
        go_button.setText("Перейти")
        go_button.setFixedHeight(28)
        go_button.setMinimumWidth(96)
        go_button.setIcon(icons.icon("open"))
        go_button.setIconSize(QSize(16, 16))
        go_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        go_button.clicked.connect(self._emit_navigate)
        make_interactive(go_button, "Открыть папку из строки пути")

        browse_button = QToolButton(self)
        browse_button.setObjectName("PathButton")
        browse_button.setText("Обзор")
        browse_button.setFixedHeight(28)
        browse_button.setMinimumWidth(86)
        browse_button.setIcon(icons.icon("folder"))
        browse_button.setIconSize(QSize(16, 16))
        browse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        browse_button.clicked.connect(self.browse_requested.emit)
        make_interactive(browse_button, "Выбрать папку через системный диалог")

        buttons_wrap = QWidget(self)
        buttons_layout = QHBoxLayout(buttons_wrap)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(8)
        buttons_layout.addWidget(go_button)
        buttons_layout.addWidget(browse_button)
        layout.addWidget(buttons_wrap, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_path(self, path: str) -> None:
        self.path_edit.setText(path)

    def focus_path(self) -> None:
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _emit_navigate(self) -> None:
        self.navigate_requested.emit(self.path_edit.text().strip())
