from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, NamedTuple

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QKeySequence

from archive_app.ui.icons import IconFactory

ActionCallback = Callable[[], None]


class ActionSpec(NamedTuple):
    key: str
    text: str
    icon_name: str
    tooltip: str
    callback: ActionCallback
    shortcut: str | None = None


@dataclass(frozen=True)
class AppActionCallbacks:
    open_selected: ActionCallback
    go_back: ActionCallback
    go_forward: ActionCallback
    go_up: ActionCallback
    go_home: ActionCallback
    refresh: ActionCallback
    toggle_search_panel: ActionCallback
    toggle_preview_panel: ActionCallback
    undo_last_operation: ActionCallback
    create_folder: ActionCallback
    copy_selected: ActionCallback
    cut_selected: ActionCallback
    paste_clipboard: ActionCallback
    delete_selected: ActionCallback
    rename_selected: ActionCallback
    create_zip_from_selection: ActionCallback
    extract_selected_archive: ActionCallback
    show_archive_contents: ActionCallback
    calculate_selected_size: ActionCallback
    open_in_system_selected: ActionCallback


class ActionManager(QObject):
    """Создаёт QAction и хранит все горячие клавиши приложения."""

    def __init__(self, parent: QObject, icons: IconFactory) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.icons = icons
        self.actions: dict[str, QAction] = {}

    def create_application_actions(
        self, callbacks: AppActionCallbacks
    ) -> dict[str, QAction]:
        actions = self.setup_actions(_build_action_specs(callbacks))
        preview_action = actions["toggle_preview_panel"]
        preview_action.setCheckable(True)
        preview_action.setChecked(True)
        actions["paste"].setEnabled(False)
        return actions

    def setup_actions(self, specs: list[ActionSpec]) -> dict[str, QAction]:
        self.actions.clear()
        for spec in specs:
            action = QAction(
                self.icons.icon(spec.icon_name),
                spec.text,
                self.parent_widget,
            )
            action.setToolTip(spec.tooltip)
            action.setStatusTip(spec.tooltip)
            if spec.shortcut:
                action.setShortcut(QKeySequence(spec.shortcut))

            def on_triggered(
                _checked: bool = False, cb: ActionCallback = spec.callback
            ) -> None:
                cb()

            action.triggered.connect(on_triggered)
            self.actions[spec.key] = action

        return self.actions

    def get_action(self, key: str) -> QAction | None:
        return self.actions.get(key)


def _build_action_specs(callbacks: AppActionCallbacks) -> list[ActionSpec]:
    return [
        ActionSpec(
            "open",
            "Открыть",
            "open",
            "Открыть папку внутри программы или файл в стандартной программе",
            callbacks.open_selected,
        ),
        ActionSpec(
            "back",
            "Назад",
            "back",
            "Вернуться к предыдущей папке (Alt+Left)",
            callbacks.go_back,
            "Alt+Left",
        ),
        ActionSpec(
            "forward",
            "Вперёд",
            "forward",
            "Перейти к следующей папке в истории (Alt+Right)",
            callbacks.go_forward,
            "Alt+Right",
        ),
        ActionSpec(
            "up",
            "Вверх",
            "up",
            "Перейти на уровень выше (Alt+Up)",
            callbacks.go_up,
            "Alt+Up",
        ),
        ActionSpec(
            "home",
            "Домой",
            "home",
            "Открыть домашнюю папку (Alt+Home)",
            callbacks.go_home,
            "Alt+Home",
        ),
        ActionSpec(
            "refresh",
            "Обновить",
            "refresh",
            "Перезагрузить список файлов (F5)",
            callbacks.refresh,
            "F5",
        ),
        ActionSpec(
            "search",
            "Поиск",
            "search",
            "Показать или скрыть панель поиска файлов (Ctrl+F)",
            callbacks.toggle_search_panel,
            "Ctrl+F",
        ),
        ActionSpec(
            "toggle_preview_panel",
            "Скрыть превью",
            "preview",
            "Показать или скрыть панель предпросмотра",
            callbacks.toggle_preview_panel,
        ),
        ActionSpec(
            "undo",
            "Отменить",
            "undo",
            "Отменить последнее файловое действие (Ctrl+Z)",
            callbacks.undo_last_operation,
            "Ctrl+Z",
        ),
        ActionSpec(
            "new_folder",
            "Новая папка",
            "new-folder",
            "Создать новую папку в текущем каталоге",
            callbacks.create_folder,
        ),
        ActionSpec(
            "copy",
            "Копировать",
            "copy",
            "Скопировать выбранные объекты в буфер",
            callbacks.copy_selected,
            "Ctrl+C",
        ),
        ActionSpec(
            "cut",
            "Вырезать",
            "cut",
            "Вырезать выбранные объекты в буфер",
            callbacks.cut_selected,
            "Ctrl+X",
        ),
        ActionSpec(
            "paste",
            "Вставить",
            "paste",
            "Вставить объекты из буфера",
            callbacks.paste_clipboard,
            "Ctrl+V",
        ),
        ActionSpec(
            "delete",
            "Удалить",
            "delete",
            "Удалить выбранные объекты в корзину (Delete в таблице)",
            callbacks.delete_selected,
        ),
        ActionSpec(
            "rename",
            "Переименовать",
            "rename",
            "Переименовать выбранный объект (F2 в таблице)",
            callbacks.rename_selected,
        ),
        ActionSpec(
            "zip",
            "Создать ZIP",
            "zip",
            "Создать ZIP-архив из выбранных объектов",
            callbacks.create_zip_from_selection,
        ),
        ActionSpec(
            "extract",
            "Распаковать",
            "extract",
            "Распаковать выбранный архив",
            callbacks.extract_selected_archive,
        ),
        ActionSpec(
            "preview",
            "Содержимое",
            "preview",
            "Показать содержимое выбранного архива",
            callbacks.show_archive_contents,
        ),
        ActionSpec(
            "size",
            "Размер папки",
            "size",
            "Посчитать размер выбранной папки",
            callbacks.calculate_selected_size,
        ),
        ActionSpec(
            "system_open",
            "Открыть в системе",
            "open",
            "Открыть файл через системное приложение",
            callbacks.open_in_system_selected,
        ),
    ]
