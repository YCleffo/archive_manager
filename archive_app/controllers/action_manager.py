from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

from archive_app.ui.icons import IconFactory


class ActionManager(QObject):
    """Отвечает за создание и настройку действий (QAction) приложения."""

    def __init__(self, parent: QObject, icons: IconFactory) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.icons = icons
        self.actions: dict[str, QAction] = {}

    def setup_actions(
        self, specs: list[tuple[str, str, str, str, Callable[[], None], str | None]]
    ) -> dict[str, QAction]:
        """
        Создает действия по списку спецификаций.
        Спецификация: (key, text, icon_name, tooltip, callback, shortcut)
        """
        for key, text, icon_name, tooltip, callback, shortcut in specs:
            action = QAction(self.icons.icon(icon_name), text, self.parent_widget)
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))

            # Используем замыкание для корректной привязки callback
            def on_triggered(
                _checked: bool = False, cb: Callable[[], None] = callback
            ) -> None:
                cb()

            action.triggered.connect(on_triggered)
            self.actions[key] = action

        return self.actions

    def get_action(self, key: str) -> QAction | None:
        return self.actions.get(key)
