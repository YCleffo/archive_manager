from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QPushButton,
    QWidget,
)

from .icons import IconFactory
from .theme import make_interactive


class ActionBar(QFrame):
    """Верхняя панель действий с адаптивным переносом в меню «Ещё»."""

    PRIMARY_ACTIONS: tuple[str, ...] = (
        "back",
        "forward",
        "up",
        "home",
        "refresh",
        "new_folder",
        "copy",
        "cut",
        "paste",
        "delete",
        "toggle_preview_panel",
        "search",
    )
    OVERFLOW_ORDER: tuple[str, ...] = (
        "search",
        "toggle_preview_panel",
        "delete",
        "paste",
        "cut",
        "copy",
        "new_folder",
        "refresh",
        "home",
        "forward",
        "up",
        "back",
    )
    ALWAYS_IN_MORE: tuple[str, ...] = (
        "undo",
        "system_open",
        "rename",
        "zip",
        "extract",
        "preview",
        "size",
    )

    def __init__(
        self,
        actions: Mapping[str, QAction],
        icons: IconFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SurfaceBar")
        self._actions = actions
        self._icons = icons
        self._buttons: dict[str, QPushButton] = {}
        self._hidden_action_keys: list[str] = []
        self._pending_overflow_update = False

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(7)

        for key in ("back", "forward", "up", "home", "refresh"):
            self._add_action_button(key)
        self._main_separator = self._separator()
        self._layout.addWidget(self._main_separator)
        for key in ("new_folder", "copy", "cut", "paste", "delete"):
            self._add_action_button(key)

        self._layout.addStretch(1)
        for key in ("toggle_preview_panel", "search"):
            self._add_action_button(key)
        self._more_button_widget = self._more_button(actions, icons)
        self._layout.addWidget(self._more_button_widget)

        self.schedule_overflow_update()

    def _add_action_button(self, key: str) -> None:
        button = self._button(self._actions[key])
        self._buttons[key] = button
        self._layout.addWidget(button)

    def _button(self, action: QAction) -> QPushButton:
        button = QPushButton(self)
        button.setMinimumHeight(32)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setIconSize(QSize(18, 18))
        button.clicked.connect(action.trigger)

        def sync_state(btn: QPushButton = button, act: QAction = action) -> None:
            btn.setEnabled(act.isEnabled())
            text = act.text().strip()
            btn.setText(text)
            btn.setIcon(act.icon())
            btn.setToolTip(act.toolTip())

        action.changed.connect(sync_state)
        sync_state()

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

    def _more_button(
        self, actions: Mapping[str, QAction], icons: IconFactory
    ) -> QPushButton:
        button = QPushButton(self)
        button.setMinimumHeight(32)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setText("Ещё")
        button.setIcon(icons.icon("more"))
        button.setIconSize(QSize(18, 18))
        make_interactive(button, "Показать больше действий")

        def show_menu(_checked: bool = False, owner: QPushButton = button) -> None:
            self._show_more_menu(owner, actions)

        button.clicked.connect(show_menu)
        return button

    def schedule_overflow_update(self) -> None:
        if self._pending_overflow_update:
            return
        self._pending_overflow_update = True
        QTimer.singleShot(0, self.update_overflow)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.schedule_overflow_update()

    def update_overflow(self) -> None:
        self._pending_overflow_update = False
        for button in self._buttons.values():
            button.setVisible(True)
        self._hidden_action_keys = []
        self._sync_separators()
        self._layout.activate()

        for key in self.OVERFLOW_ORDER:
            if self._required_width() <= max(0, self.contentsRect().width()):
                break
            button = self._buttons.get(key)
            if button is None or not button.isVisible():
                continue
            button.setVisible(False)
            self._hidden_action_keys.insert(0, key)
            self._sync_separators()
            self._layout.activate()

        self._more_button_widget.setVisible(True)
        hidden_count = len(self._hidden_action_keys)
        self._more_button_widget.setToolTip(
            f"Показать скрытые и дополнительные действия ({hidden_count})"
            if hidden_count
            else "Показать больше действий"
        )

    def _required_width(self) -> int:
        margins = self._layout.contentsMargins()
        spacing = self._layout.spacing()

        all_widgets: list[QWidget] = []

        for button in self._buttons.values():
            all_widgets.append(button)

        all_widgets.append(self._main_separator)
        all_widgets.append(self._more_button_widget)

        visible_widgets: list[QWidget] = []

        for item_widget in all_widgets:
            if item_widget.isVisible():
                visible_widgets.append(item_widget)

        width = margins.left() + margins.right()

        if visible_widgets:
            width += spacing * max(0, len(visible_widgets) - 1)

        for item_widget in visible_widgets:
            width += max(
                item_widget.minimumSizeHint().width(),
                item_widget.sizeHint().width(),
            )

        return width

    def _sync_separators(self) -> None:
        left_visible = any(
            self._buttons[key].isVisible()
            for key in ("back", "forward", "up", "home", "refresh")
        )
        middle_visible = any(
            self._buttons[key].isVisible()
            for key in ("new_folder", "copy", "cut", "paste", "delete")
        )
        right_visible = any(
            self._buttons[key].isVisible() for key in ("toggle_preview_panel", "search")
        )
        self._main_separator.setVisible(left_visible and middle_visible)

    def _show_more_menu(
        self, button: QPushButton, actions: Mapping[str, QAction]
    ) -> None:
        menu = QMenu(button)
        menu.setObjectName("MoreActionsMenu")
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        added: set[str] = set()
        for key in self._hidden_action_keys:
            menu.addAction(actions[key])
            added.add(key)

        if added:
            menu.addSeparator()

        for key in self.ALWAYS_IN_MORE:
            if key not in added:
                menu.addAction(actions[key])
                added.add(key)

        button.setDown(True)

        def release_button() -> None:
            button.setDown(False)

        menu.aboutToHide.connect(release_button)

        menu.adjustSize()
        position = button.mapToGlobal(button.rect().bottomRight())
        position.setX(position.x() - menu.width())

        menu.exec(position)
        button.setDown(False)
