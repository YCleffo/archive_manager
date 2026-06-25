from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QSizePolicy, QToolButton, QWidget

from .icons import IconFactory
from .theme import make_interactive


class ActionBar(QFrame):
    def __init__(self, actions: Mapping[str, QAction], icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SurfaceBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        for key in ("back", "up", "home", "refresh"):
            layout.addWidget(self._button(actions[key]))
        layout.addWidget(self._separator())
        for key in ("new_folder", "copy", "move", "delete"):
            layout.addWidget(self._button(actions[key]))

        layout.addStretch(1)
        layout.addWidget(self._button(actions["search"]))
        layout.addWidget(self._more_button(actions, icons))

    def _button(self, action: QAction) -> QToolButton:
        button = QToolButton(self)
        button.setMinimumHeight(32)
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setIconSize(QSize(18, 18))
        make_interactive(button, action.toolTip())
        return button

    def _separator(self) -> QFrame:
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setFixedWidth(1)
        line.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        line.setStyleSheet("background: #e3e9f0; margin: 4px 4px;")
        return line

    def _more_button(self, actions: Mapping[str, QAction], icons: IconFactory) -> QToolButton:
        menu = QMenu(self)
        for key in ("rename", "zip", "extract", "preview", "size"):
            menu.addAction(actions[key])

        button = QToolButton(self)
        button.setMinimumHeight(32)
        button.setText("Ещё")
        button.setIcon(icons.icon("more"))
        button.setIconSize(QSize(18, 18))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        make_interactive(button, "Показать больше действий")
        return button
