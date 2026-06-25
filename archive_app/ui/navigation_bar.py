from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

from .icons import IconFactory
from .theme import make_interactive


import os
from PySide6.QtCore import QStringListModel

class PathCompleter(QCompleter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.string_list_model = QStringListModel()
        self.setModel(self.string_list_model)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setMaxVisibleItems(10)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def update_suggestions(self, text: str) -> None:
        if not text:
            self.string_list_model.setStringList([])
            return
            
        text = text.replace("/", "\\")
        if text.endswith("\\"):
            dir_path = text
        else:
            dir_path = os.path.dirname(text)
            if not dir_path.endswith("\\") and dir_path:
                dir_path += "\\"
                
        if not dir_path or not os.path.isdir(dir_path):
            self.string_list_model.setStringList([])
            return

        try:
            suggestions = []
            with os.scandir(dir_path) as it:
                for entry in it:
                    if entry.is_dir():
                        suggestions.append(os.path.join(dir_path, entry.name) + "\\")
                    else:
                        suggestions.append(os.path.join(dir_path, entry.name))
            self.string_list_model.setStringList(suggestions)
        except OSError:
            self.string_list_model.setStringList([])

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

        self.completer = PathCompleter(self)
        self.path_edit.setCompleter(self.completer)
        self.path_edit.textEdited.connect(self.completer.update_suggestions)

        layout.addWidget(self.path_edit, 1)

        go_button = QToolButton(self)
        go_button.setObjectName("PathButton")
        go_button.setText("Перейти")
        go_button.setFixedSize(84, 28)
        go_button.setIcon(icons.icon("open"))
        go_button.setIconSize(QSize(14, 14))
        go_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        go_button.clicked.connect(self._emit_navigate)
        make_interactive(go_button, "Открыть папку из строки пути")

        browse_button = QToolButton(self)
        browse_button.setObjectName("PathButton")
        browse_button.setText("Обзор")
        browse_button.setFixedSize(78, 28)
        browse_button.setIcon(icons.icon("folder"))
        browse_button.setIconSize(QSize(14, 14))
        browse_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        browse_button.clicked.connect(self.browse_requested.emit)
        make_interactive(browse_button, "Выбрать папку через системный диалог")

        buttons_wrap = QWidget(self)
        buttons_layout = QHBoxLayout(buttons_wrap)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(6)
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
