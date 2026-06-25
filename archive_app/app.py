from __future__ import annotations

import atexit
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRunnable, Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QMouseEvent, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QLabel,
    QDialog,
    QSplitter,
)

from .archive_utils import (
    create_zip_archive,
    extract_archive,
    is_supported_archive,
    list_archive_members,
)
from .file_utils import (
    FileEntry,
    calculate_folder_size,
    copy_items,
    create_folder,
    delete_items,
    format_size,
    list_directory,
    move_items,
    open_in_system,
    rename_item,
)
from .preview_utils import PreviewResult, build_preview
from .search_utils import SearchResult, search_files
from .ui.action_bar import ActionBar
from .ui.dialogs import ArchivePreviewDialog
from .ui.folder_picker import FolderPickerDialog
from .ui.preview_panel import PreviewPanel
from .ui.icons import IconFactory
from .ui.navigation_bar import PathBar
from .ui.search_panel import SearchPanel
from .ui.tables import FileTable, TableCard, PATH_ROLE
from .ui.theme import APP_STYLESHEET
from .ui.workers import OperationWorker, SearchWorker

PID_FILE = Path(__file__).resolve().parent.parent / ".archive_manager.pid"

DirectorySignature = tuple[tuple[str, bool, int, int], ...]


class ArchiveManagerApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Файловый менеджер (Архиватор)")
        self.resize(1360, 820)
        self.setMinimumSize(1040, 780)

        self.icons = IconFactory()
        self.current_path = Path.home().resolve()
        self.history: list[Path] = []
        self.forward_history: list[Path] = []
        self._clipboard_paths: list[Path] = []
        self._clipboard_is_cut: bool = False
        self.undo_stack: list[tuple[str, Callable[[], None]]] = []
        self.search_cancel_event: threading.Event | None = None
        self.search_generation = 0
        self.load_generation = 0
        self.preview_generation = 0
        self._last_directory_signature: DirectorySignature | None = None
        self._auto_refresh_enabled = True
        self._auto_refresh_busy = False
        self.thread_pool = QThreadPool.globalInstance()
        self.workers: list[QRunnable] = []

        self.setStyleSheet(APP_STYLESHEET)
        self.app_actions = self._create_actions()
        self.app_actions["paste"].setEnabled(False)
        self._build_layout()
        application = QApplication.instance()
        if application is not None:
            application.installEventFilter(self)

        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(1000)
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_current_directory)
        self._auto_refresh_timer.start()

        self.load_directory(self.current_path, add_history=False)

    def _create_actions(self) -> dict[str, QAction]:
        specs: list[tuple[str, str, str, str, Callable[[], None], str | None]] = [
            (
                "open",
                "Открыть",
                "open",
                "Открыть папку внутри программы или файл в стандартной программе",
                self.open_selected,
                None,
            ),
            (
                "back",
                "Назад",
                "back",
                "Вернуться к предыдущей папке (Alt+Left)",
                self.go_back,
                "Alt+Left",
            ),
            (
                "forward",
                "Вперёд",
                "forward",
                "Перейти к следующей папке в истории (Alt+Right)",
                self.go_forward,
                "Alt+Right",
            ),
            (
                "up",
                "Вверх",
                "up",
                "Перейти на уровень выше (Alt+Up)",
                self.go_up,
                "Alt+Up",
            ),
            (
                "home",
                "Домой",
                "home",
                "Открыть домашнюю папку (Alt+Home)",
                self.go_home,
                "Alt+Home",
            ),
            (
                "refresh",
                "Обновить",
                "refresh",
                "Перезагрузить список файлов (F5)",
                self.refresh,
                "F5",
            ),
            (
                "search",
                "Поиск",
                "search",
                "Показать или скрыть панель поиска файлов (Ctrl+F)",
                self.toggle_search_panel,
                "Ctrl+F",
            ),
            (
                "toggle_preview_panel",
                "Скрыть превью",
                "preview",
                "Показать или скрыть панель предпросмотра",
                self.toggle_preview_panel,
                None,
            ),
            (
                "undo",
                "Отменить",
                "undo",
                "Отменить последнее файловое действие (Ctrl+Z)",
                self.undo_last_operation,
                "Ctrl+Z",
            ),
            (
                "new_folder",
                "Новая папка",
                "new-folder",
                "Создать новую папку в текущем каталоге",
                self.new_folder,
                None,
            ),
            (
                "copy",
                "Копировать",
                "copy",
                "Скопировать выбранные объекты в буфер",
                self.copy_selected,
                "Ctrl+C",
            ),
            (
                "cut",
                "Вырезать",
                "cut",
                "Вырезать выбранные объекты в буфер",
                self.cut_selected,
                "Ctrl+X",
            ),
            (
                "paste",
                "Вставить",
                "paste",
                "Вставить объекты из буфера",
                self.paste_clipboard,
                "Ctrl+V",
            ),
            (
                "delete",
                "Удалить",
                "delete",
                "Удалить выбранные объекты в корзину (Delete в таблице)",
                self.delete_selected,
                None,
            ),
            (
                "rename",
                "Переименовать",
                "rename",
                "Переименовать выбранный объект (F2 в таблице)",
                self.rename_selected,
                None,
            ),
            (
                "zip",
                "Создать ZIP",
                "zip",
                "Создать ZIP-архив из выбранных объектов",
                self.create_zip_from_selection,
                None,
            ),
            (
                "extract",
                "Распаковать",
                "extract",
                "Распаковать выбранный архив",
                self.extract_selected_archive,
                None,
            ),
            (
                "preview",
                "Содержимое",
                "preview",
                "Показать содержимое выбранного архива",
                self.show_archive_contents,
                None,
            ),
            (
                "size",
                "Размер папки",
                "size",
                "Посчитать размер выбранной папки",
                self.calculate_selected_size,
                None,
            ),
            (
                "system_open",
                "Открыть в системе",
                "open",
                "Открыть файл через системное приложение",
                self.open_in_system_selected,
                None,
            ),
        ]

        actions: dict[str, QAction] = {}
        for key, text, icon_name, tooltip, callback, shortcut in specs:
            action = QAction(self.icons.icon(icon_name), text, self)
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))

            def on_triggered(
                _checked: bool = False, cb: Callable[[], None] = callback
            ) -> None:
                cb()

            action.triggered.connect(on_triggered)
            self.addAction(action)
            actions[key] = action

        preview_action = actions["toggle_preview_panel"]
        preview_action.setCheckable(True)
        preview_action.setChecked(True)
        return actions

    def _build_layout(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(12)

        self.action_bar = ActionBar(self.app_actions, self.icons, central)
        layout.addWidget(self.action_bar)

        self.path_bar = PathBar(self.icons, central)

        def on_navigate_requested(path_str: str) -> None:
            self.load_directory(Path(path_str))

        self.path_bar.navigate_requested.connect(on_navigate_requested)
        self.path_bar.browse_requested.connect(self.choose_directory)
        layout.addWidget(self.path_bar)

        self.file_table = FileTable(self.icons, central)
        self.file_table.open_requested.connect(self.open_selected)
        self.file_table.delete_requested.connect(self.delete_selected)
        self.file_table.rename_requested.connect(self.rename_selected)
        self.file_table.copy_requested.connect(self.copy_selected)
        self.file_table.cut_requested.connect(self.cut_selected)
        self.file_table.paste_requested.connect(self.paste_clipboard)
        self.file_table.selection_changed.connect(self.on_file_selection_changed)
        self.file_table.context_menu_requested.connect(self.show_file_context_menu)
        self.file_table.size_requested.connect(self.calculate_folder_size_from_button)
        self.file_table_card = TableCard(self.file_table, central)
        self.preview_panel = PreviewPanel(central)
        self.preview_panel.open_requested.connect(self.open_in_system_selected)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self.content_splitter.setObjectName("ContentSplitter")
        self.content_splitter.setHandleWidth(8)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(self.file_table_card)
        self.content_splitter.addWidget(self.preview_panel)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 0)
        self.content_splitter.setSizes([920, 340])
        layout.addWidget(self.content_splitter, 1)

        self.search_panel = SearchPanel(self.icons, central)
        self.search_panel.start_requested.connect(self.start_search)
        self.search_panel.stop_requested.connect(self.stop_search)
        self.search_panel.reset_requested.connect(self.reset_search_panel)
        self.search_panel.close_requested.connect(self.hide_search_panel)
        self.search_panel.open_result_requested.connect(self.open_search_result)
        self.search_panel.hide()
        layout.addWidget(self.search_panel)

        self.setCentralWidget(central)

        self.status_label = QLabel(self)
        self.status_label.setStyleSheet("color: #4b5563; font-size: 13px;")
        self.statusBar().addWidget(self.status_label)

    def _count_paths(self, paths: list[Path]) -> tuple[int, int, int]:
        files = 0
        folders = 0
        for path in paths:
            try:
                if path.is_dir():
                    folders += 1
                else:
                    files += 1
            except OSError:
                files += 1
        return len(paths), files, folders

    def _selection_text(self) -> str:
        paths = self.get_selected_paths()
        total, files, folders = self._count_paths(paths)
        if total == 0:
            return "Ничего не выбрано"
        return f"Выбрано: {total} | файлов: {files} | папок: {folders}"

    def _clipboard_text(self) -> str:
        count = len(self._clipboard_paths)
        if count == 0:
            return "Буфер пуст"
        mode = "вырезано" if self._clipboard_is_cut else "скопировано"
        return f"В буфере: {mode} {count} | можно вставить: {count}"

    def update_selection_status(self) -> None:
        self.set_status(f"{self._selection_text()} | {self._clipboard_text()}")
        self.update_action_counts()

    def on_file_selection_changed(self) -> None:
        self.update_selection_status()
        self.update_preview_for_selection()

    def update_preview_for_selection(self) -> None:
        if not self.preview_panel.isVisible():
            self.preview_generation += 1
            return

        paths = self.get_selected_paths()
        total, files, folders = self._count_paths(paths)

        self.preview_generation += 1
        generation = self.preview_generation

        if total == 0:
            self.preview_panel.set_empty()
            return

        if total > 1:
            self.preview_panel.set_multiple(total, files, folders)
            return

        path = paths[0]
        self.preview_panel.set_loading(path.name)

        def task(status: Callable[[str], None]) -> PreviewResult:
            status(f"Готовлю превью: {path.name}...")
            return build_preview(path)

        def on_result(result: PreviewResult, gen: int = generation) -> None:
            if gen != self.preview_generation:
                return
            self.preview_panel.set_result(result)
            self.update_selection_status()

        def on_error(
            error: str, gen: int = generation, preview_path: Path = path
        ) -> None:
            if gen != self.preview_generation:
                return
            fallback = PreviewResult(
                path=preview_path,
                title=preview_path.name,
                details=f"Путь: {preview_path}",
                error=error,
            )
            self.preview_panel.set_result(fallback)

        worker = OperationWorker(task)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        self._track_worker(worker)
        self.thread_pool.start(worker)

    def set_status_with_context(self, message: str) -> None:
        self.set_status(
            f"{message} | {self._selection_text()} | {self._clipboard_text()}"
        )

    def update_action_counts(self) -> None:
        selected_count = len(self.get_selected_paths())
        clipboard_count = len(self._clipboard_paths)

        self.app_actions["copy"].setText(
            f"Копировать ({selected_count})" if selected_count else "Копировать"
        )
        self.app_actions["cut"].setText(
            f"Вырезать ({selected_count})" if selected_count else "Вырезать"
        )
        self.app_actions["delete"].setText(
            f"Удалить ({selected_count})" if selected_count else "Удалить"
        )

        if clipboard_count:
            self.app_actions["paste"].setText(f"Вставить ({clipboard_count})")
            self.app_actions["paste"].setToolTip(
                f"Можно вставить объектов: {clipboard_count}"
            )
            self.app_actions["paste"].setStatusTip(
                f"Можно вставить объектов: {clipboard_count}"
            )
            self.app_actions["paste"].setEnabled(True)
        else:
            self.app_actions["paste"].setText("Вставить")
            self.app_actions["paste"].setToolTip("Вставить объекты из буфера")
            self.app_actions["paste"].setStatusTip("Вставить объекты из буфера")
            self.app_actions["paste"].setEnabled(False)

        self.app_actions["back"].setEnabled(bool(self.history))
        self.app_actions["forward"].setEnabled(bool(self.forward_history))
        self.app_actions["up"].setEnabled(self.current_path.parent != self.current_path)

        if hasattr(self, "action_bar"):
            self.action_bar.schedule_overflow_update()

    def set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and isinstance(
            event, QMouseEvent
        ):
            button = event.button()
            if button == Qt.MouseButton.BackButton:
                self.go_back()
                return True
            if button == Qt.MouseButton.ForwardButton:
                self.go_forward()
                return True

        return super().eventFilter(watched, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.thread_pool.activeThreadCount() > 0:
            answer = QMessageBox.question(
                self,
                "Выход",
                "Выполняются фоновые операции.\nВы уверены, что хотите закрыть программу?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        self.stop_search(silent=True)
        self.thread_pool.clear()
        self.thread_pool.waitForDone(1000)
        _remove_pid_file()
        event.accept()

    def load_directory(
        self,
        path: Path,
        add_history: bool = True,
        clear_forward: bool = True,
        preserve_view: bool = False,
    ) -> None:
        try:
            path = Path(path).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise NotADirectoryError(str(path))

            self.load_generation += 1
            generation = self.load_generation
            selected_before: set[str] = (
                self._selected_path_strings() if preserve_view else set()
            )
            scroll_before = (
                self.file_table.verticalScrollBar().value() if preserve_view else 0
            )

            def task(
                status: Callable[[str], None],
            ) -> tuple[list[FileEntry], DirectorySignature]:
                status(f"Чтение директории: {path.name}...")
                entries = list_directory(path)
                return entries, self._signature_from_entries(entries)

            def on_result(result: tuple[list[FileEntry], DirectorySignature]) -> None:
                if generation != self.load_generation:
                    return

                entries, signature = result
                if add_history and path != self.current_path:
                    self.history.append(self.current_path)
                    if clear_forward:
                        self.forward_history.clear()

                self.current_path = path
                self._last_directory_signature = signature
                self.path_bar.set_path(str(path))
                self.file_table.set_entries(entries)

                if preserve_view:
                    self._restore_table_view(selected_before, scroll_before)

                self.update_action_counts()
                self.update_selection_status()

            self._start_operation(task, "Ошибка загрузки", on_result)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть папку:\n{exc}")
            self.set_status("Ошибка открытия папки")

    def _signature_from_entries(self, entries: list[FileEntry]) -> DirectorySignature:
        signature: list[tuple[str, bool, int, int]] = []
        for entry in entries:
            modified_ns = 0
            try:
                modified_ns = entry.path.stat(follow_symlinks=False).st_mtime_ns
            except OSError:
                if entry.modified is not None:
                    modified_ns = int(entry.modified.timestamp() * 1_000_000_000)
            signature.append(
                (
                    entry.name,
                    entry.is_dir,
                    -1 if entry.size is None else entry.size,
                    modified_ns,
                )
            )
        return tuple(sorted(signature))

    def _read_current_directory_signature(self) -> DirectorySignature | None:
        try:
            return self._signature_from_entries(list_directory(self.current_path))
        except OSError:
            return None

    def _selected_path_strings(self) -> set[str]:
        return {str(path) for path in self.file_table.selected_paths()}

    def _restore_table_view(self, selected_paths: set[str], scroll_value: int) -> None:
        if selected_paths:
            self.file_table.setUpdatesEnabled(False)
            try:
                for row in range(self.file_table.rowCount()):
                    item = self.file_table.item(row, 0)
                    if item is None:
                        continue
                    raw_path = item.data(PATH_ROLE)
                    try:
                        item_path = str(Path(str(raw_path)).resolve())
                    except OSError:
                        item_path = str(raw_path)
                    if item_path in selected_paths:
                        self.file_table.selectRow(row)
            finally:
                self.file_table.setUpdatesEnabled(True)

        self.file_table.verticalScrollBar().setValue(scroll_value)

    def _auto_refresh_current_directory(self) -> None:
        if not self._auto_refresh_enabled or self._auto_refresh_busy:
            return
        if self.thread_pool.activeThreadCount() > 0:
            return
        if not self.current_path.exists() or not self.current_path.is_dir():
            return

        self._auto_refresh_busy = True
        try:
            signature = self._read_current_directory_signature()
            if signature is None:
                return
            if self._last_directory_signature is None:
                self._last_directory_signature = signature
                return
            if signature != self._last_directory_signature:
                self.load_directory(
                    self.current_path,
                    add_history=False,
                    clear_forward=False,
                    preserve_view=True,
                )
        finally:
            self._auto_refresh_busy = False

    def refresh(self) -> None:
        self.load_directory(self.current_path, add_history=False, preserve_view=True)

    def choose_directory(self) -> None:
        dialog = FolderPickerDialog(self.current_path, self.icons, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_directory(dialog.get_result_path())

    def go_up(self) -> None:
        parent = self.current_path.parent
        if parent != self.current_path:
            self.load_directory(parent)

    def go_home(self) -> None:
        self.load_directory(Path.home())

    def go_back(self) -> None:
        if not self.history:
            self.set_status("История пуста")
            return
        self.forward_history.append(self.current_path)
        previous = self.history.pop()
        self.load_directory(previous, add_history=False, clear_forward=False)

    def go_forward(self) -> None:
        if not self.forward_history:
            self.set_status("История вперёд пуста")
            return
        self.history.append(self.current_path)
        next_path = self.forward_history.pop()
        self.load_directory(next_path, add_history=False, clear_forward=False)

    def get_selected_paths(self) -> list[Path]:
        return self.file_table.selected_paths()

    def get_selected_path(self) -> Path | None:
        paths = self.get_selected_paths()
        return paths[0] if paths else None

    def open_selected(self) -> None:
        path = self.get_selected_path()
        if path is None:
            return
        try:
            if path.is_dir():
                self.load_directory(path)
                return

            open_in_system(path)
            self.set_status_with_context(
                f"Открыто в стандартной программе: {path.name}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть:\n{exc}")

    def open_in_system_selected(self) -> None:
        path = self.get_selected_path()
        if path is None:
            return
        try:
            open_in_system(path)
            self.set_status_with_context(f"Открыто в системе: {path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть:\n{exc}")

    def new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая папка", "Введите имя папки:")
        if not ok or not name:
            return
        try:
            created = create_folder(self.current_path, name)
            self._push_undo(
                f"создание папки {created.name}",
                lambda created_path=created: delete_items([created_path]),
            )
            self.refresh()
            self.set_status(f"Создана папка: {created.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def rename_selected(self) -> None:
        path = self.get_selected_path()
        if path is None:
            QMessageBox.information(
                self, "Переименование", "Выберите один файл или папку"
            )
            return
        new_name, ok = QInputDialog.getText(
            self, "Переименовать", "Новое имя:", text=path.name
        )
        if not ok or not new_name or new_name == path.name:
            return
        try:
            renamed = rename_item(path, new_name)

            def make_undo(source: Path, target: Path) -> Callable[[], None]:
                def undo() -> None:
                    source.rename(target)

                return undo

            self._push_undo(f"переименование {renamed.name}", make_undo(renamed, path))
            self.refresh()
            self.set_status(f"Переименовано: {renamed.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def delete_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Удаление", "Выберите файлы или папки")
            return
        names = "\n".join(path.name for path in paths[:10])
        if len(paths) > 10:
            names += f"\n...и ещё {len(paths) - 10}"
        answer = QMessageBox.question(
            self,
            "Удаление",
            f"Переместить выбранные объекты в корзину?\n\n{names}\n\nЭто действие не удаляет файлы безвозвратно, но Ctrl+Z внутри программы не восстанавливает удаление из корзины.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_items(paths)
            self.refresh()
            self.set_status_with_context(f"Перемещено в корзину: {len(paths)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{exc}")

    def copy_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Копирование", "Выберите файлы или папки")
            return
        self._clipboard_paths = paths
        self._clipboard_is_cut = False
        self.update_action_counts()
        self.set_status_with_context(
            f"Скопировано в буфер: {len(paths)} | можно вставить: {len(paths)}"
        )

    def cut_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Вырезание", "Выберите файлы или папки")
            return
        self._clipboard_paths = paths
        self._clipboard_is_cut = True
        self.update_action_counts()
        self.set_status_with_context(
            f"Вырезано в буфер: {len(paths)} | можно вставить: {len(paths)}"
        )

    def paste_clipboard(self) -> None:
        if not self._clipboard_paths:
            return

        is_cut = self._clipboard_is_cut
        paths = self._clipboard_paths
        dest = self.current_path

        def task(status: Callable[[str], None]) -> int:
            if is_cut:
                status("Перемещение...")
                moved = move_items(paths, dest)
                return len(moved)
            else:
                status("Копирование...")
                copied = copy_items(paths, dest)
                return len(copied)

        def on_success(count: int) -> None:
            if is_cut:
                self._clipboard_paths = []
                self._clipboard_is_cut = False
                self.update_action_counts()
                self.set_status_with_context(
                    f"Перемещено объектов: {count} | буфер очищен"
                )
            else:
                self.update_action_counts()
                self.set_status_with_context(
                    f"Скопировано объектов: {count} | можно вставить ещё: {len(self._clipboard_paths)}"
                )
            self.refresh()

        self._start_operation(task, "Ошибка вставки", on_success)

    def create_zip_from_selection(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(
                self, "Создать ZIP", "Выберите файлы или папки для архивации"
            )
            return

        from archive_app.file_utils import ensure_unique_path

        default_name = "архив.zip" if len(paths) != 1 else f"{paths[0].stem}.zip"
        output_path = ensure_unique_path(self.current_path / default_name)

        def task(status: Callable[[str], None]) -> Path:
            status("Создание архива...")
            return create_zip_archive(
                output_path,
                paths,
                progress=lambda name: status(f"Архивирую: {Path(name).name}"),
            )

        self._start_operation(
            task,
            "Ошибка создания архива",
            lambda created: self._zip_created(Path(created)),
        )

    def _zip_created(self, created: Path) -> None:
        self._push_undo(
            f"создание архива {created.name}",
            lambda created_path=created: delete_items([created_path]),
        )
        self.refresh()
        QMessageBox.information(self, "Готово", f"Архив создан:\n{created}")
        self.set_status_with_context(f"Архив создан: {created.name}")

    def show_archive_contents(self) -> None:
        path = self.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            QMessageBox.information(self, "Содержимое", "Выберите архив для просмотра")
            return
        self.show_archive_contents_for_path(path)

    def show_archive_contents_for_path(self, path: Path) -> None:
        def task(status: Callable[[str], None]) -> str:
            status("Чтение архива...")
            members = list_archive_members(path)
            return "\n".join(members[:200]) + (
                f"\n...и ещё {len(members) - 200} элементов"
                if len(members) > 200
                else ""
            )

        def on_result(preview: str) -> None:
            ArchivePreviewDialog(self, path.name, preview or "Архив пуст").exec()

        self._start_operation(
            task,
            "Ошибка чтения архива",
            on_result,
        )

    def extract_selected_archive(self) -> None:
        path = self.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            QMessageBox.information(self, "Распаковка", "Выберите архив для распаковки")
            return

        from archive_app.file_utils import ensure_unique_path

        destination_path = ensure_unique_path(self.current_path / path.stem)

        def task(status: Callable[[str], None]) -> tuple[Path, Path]:
            status("Распаковка архива...")
            extract_archive(
                path,
                destination_path,
                progress=lambda name: status(f"Распаковываю: {name}"),
            )
            return path, destination_path

        self._start_operation(
            task,
            "Ошибка распаковки",
            lambda result: self._archive_extracted(result[0], result[1]),
        )

    def _archive_extracted(self, archive_path: Path, destination: Path) -> None:
        self.load_directory(destination)
        QMessageBox.information(self, "Готово", f"Архив распакован в:\n{destination}")
        self.set_status_with_context(f"Распаковано: {archive_path.name}")

    def calculate_selected_size(self) -> None:
        path = self.get_selected_path()
        if not path or not path.is_dir():
            QMessageBox.information(
                self, "Размер", "Выберите папку для подсчёта размера"
            )
            return
        self.calculate_folder_size_for_path(path, show_dialog=True)

    def calculate_folder_size_from_button(self, path: Path) -> None:
        self.calculate_folder_size_for_path(path, show_dialog=False)

    def calculate_folder_size_for_path(self, path: Path, show_dialog: bool) -> None:
        def task(status: Callable[[str], None]) -> tuple[Path, int, int]:
            status(f"Вычисление размера: {path.name}...")
            total_size, total_files = calculate_folder_size(path)
            return path, total_size, total_files

        self._start_operation(
            task,
            "Ошибка подсчёта размера",
            lambda result: self._folder_size_ready(
                result[0], result[1], result[2], show_dialog
            ),
        )

    def _folder_size_ready(
        self, path: Path, total_size: int, total_files: int, show_dialog: bool = True
    ) -> None:
        self.file_table.set_folder_size(path, total_size)
        if show_dialog:
            QMessageBox.information(
                self,
                "Размер папки",
                f"Папка: {path.name}\nРазмер: {format_size(total_size)}\nФайлов: {total_files}",
            )
        self.set_status(f"Размер {path.name}: {format_size(total_size)}")

    def toggle_preview_panel(self) -> None:
        action = self.app_actions["toggle_preview_panel"]
        is_visible = action.isChecked()
        self.preview_panel.setVisible(is_visible)
        if is_visible:
            action.setText("Скрыть превью")
            action.setToolTip("Скрыть панель предпросмотра")
            action.setStatusTip("Скрыть панель предпросмотра")
            if hasattr(self, "content_splitter"):
                sizes = self.content_splitter.sizes()
                if len(sizes) == 2 and sizes[1] <= 0:
                    self.content_splitter.setSizes([920, 340])
            self.update_preview_for_selection()
            if hasattr(self, "action_bar"):
                self.action_bar.schedule_overflow_update()
            self.set_status_with_context("Панель превью показана")
        else:
            action.setText("Показать превью")
            action.setToolTip("Показать панель предпросмотра")
            action.setStatusTip("Показать панель предпросмотра")
            self.preview_generation += 1
            if hasattr(self, "action_bar"):
                self.action_bar.schedule_overflow_update()
            self.set_status_with_context("Панель превью скрыта")

    def toggle_search_panel(self) -> None:
        if self.search_panel.isVisible():
            self.hide_search_panel()
        else:
            self.search_panel.show()
            self.search_panel.focus_query()
            self.set_status("Панель поиска открыта")

    def hide_search_panel(self) -> None:
        self.stop_search(silent=True)
        self.search_panel.hide()
        self.set_status("Панель поиска скрыта")

    def reset_search_panel(self) -> None:
        self.stop_search(silent=True)
        self.search_panel.reset()
        self.set_status("Поиск сброшен")

    def start_search(self) -> None:
        query = self.search_panel.query()
        if not query:
            QMessageBox.information(self, "Поиск", "Введите запрос")
            return
        self.stop_search(silent=True)
        self.search_panel.clear_results()

        self.search_generation += 1
        generation = self.search_generation

        self.search_cancel_event = threading.Event()
        worker = SearchWorker(
            search_function=search_files,
            root=self.current_path,
            query=query,
            extensions_raw=self.search_panel.extensions(),
            include_content=self.search_panel.include_content(),
            cancel_event=self.search_cancel_event,
        )

        def on_result(result: SearchResult, gen: int = generation) -> None:
            self.insert_search_result(result, gen)

        def on_error(error: str, gen: int = generation) -> None:
            self._show_search_error(error, gen)

        def on_finished(cancelled: bool, gen: int = generation) -> None:
            self._search_finished(cancelled, gen)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self._track_worker(worker)
        self.thread_pool.start(worker)
        self.set_status("Поиск запущен...")

    def stop_search(self, silent: bool = False) -> None:
        if self.search_cancel_event is not None:
            self.search_cancel_event.set()
            if not silent:
                self.set_status("Поиск остановлен")

    def insert_search_result(self, result: SearchResult, generation: int) -> None:
        if generation != self.search_generation:
            return
        self.search_panel.add_result(result)

    def _search_finished(self, cancelled: bool, generation: int) -> None:
        if generation != self.search_generation:
            return
        if cancelled:
            self.set_status("Поиск остановлен")
        else:
            self.set_status(
                f"Поиск завершён. Найдено: {self.search_panel.result_count()}"
            )
        self.search_cancel_event = None

    def _show_search_error(self, error: str, generation: int) -> None:
        if generation != self.search_generation:
            return
        QMessageBox.critical(self, "Ошибка поиска", error)
        self.set_status("Ошибка поиска")
        self.search_cancel_event = None

    def open_search_result(self) -> None:
        path = self.search_panel.selected_path()
        if path is None:
            return
        try:
            if path.is_dir():
                self.load_directory(path)
            elif path.exists():
                open_in_system(path)
            else:
                QMessageBox.warning(self, "Поиск", "Файл уже не существует")
        except Exception as exc:
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось открыть результат:\n{exc}"
            )

    def show_file_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setWindowFlags(
            menu.windowFlags()
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        shadow = QGraphicsDropShadowEffect(menu)
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        menu.setGraphicsEffect(shadow)

        for key in ("open", "preview"):
            menu.addAction(self.app_actions[key])
        menu.addSeparator()
        for key in ("zip", "extract"):
            menu.addAction(self.app_actions[key])
        menu.addSeparator()
        for key in ("copy", "cut", "paste", "rename", "delete"):
            action = self.app_actions[key]
            if key == "paste":
                action.setEnabled(bool(self._clipboard_paths))
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.app_actions["size"])
        menu.exec(pos)

    def _start_operation(
        self,
        callback: Callable[[Callable[[str], None]], Any],
        error_status: str,
        on_result: Callable[[Any], None],
    ) -> OperationWorker:
        worker = OperationWorker(callback)
        worker.signals.status.connect(self.set_status)
        worker.signals.result.connect(on_result)

        def on_op_error(error_msg: str) -> None:
            self._show_operation_error(error_status, error_msg)

        worker.signals.error.connect(on_op_error)
        self._track_worker(worker)
        self.thread_pool.start(worker)
        return worker

    def _track_worker(self, worker: QRunnable) -> None:
        self.workers.append(worker)
        signals = getattr(worker, "signals", None)
        if signals is not None and hasattr(signals, "finished"):

            def on_finished(*args: Any, task: QRunnable = worker) -> None:
                self._untrack_worker(task)

            signals.finished.connect(on_finished)
        if signals is not None and hasattr(signals, "error"):

            def on_error(*args: Any, task: QRunnable = worker) -> None:
                self._untrack_worker(task)

            signals.error.connect(on_error)

    def _untrack_worker(self, worker: QRunnable) -> None:
        if worker in self.workers:
            self.workers.remove(worker)

    def _show_operation_error(self, status: str, error: str) -> None:
        QMessageBox.critical(self, "Ошибка", error)
        self.set_status(status)

    def _push_undo(self, description: str, callback: Callable[[], None]) -> None:
        self.undo_stack.append((description, callback))
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)

    def undo_last_operation(self) -> None:
        if not self.undo_stack:
            self.set_status("Нет действий для отмены")
            return
        description, callback = self.undo_stack.pop()
        try:
            callback()
            self.refresh()
            self.set_status(f"Отменено: {description}")
        except Exception as exc:
            QMessageBox.critical(
                self, "Отмена действия", f"Не удалось отменить действие:\n{exc}"
            )
            self.set_status("Ошибка отмены действия")

    def _undo_move_items(self, moved_pairs: list[tuple[Path, Path]]) -> None:
        for original, moved in reversed(moved_pairs):
            if original.exists():
                raise FileExistsError(
                    f"Нельзя вернуть объект, путь уже занят: {original}"
                )
            shutil.move(str(moved), str(original))


def main() -> None:
    _write_pid_file()

    os.environ["QT_LOGGING_RULES"] = "*.debug=false;*.warning=false"

    app = QApplication(sys.argv)

    from PySide6.QtCore import QTranslator, QLibraryInfo

    translator = QTranslator(app)
    path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load("qtbase_ru.qm", path) or translator.load("qt_ru.qm", path):
        app.installTranslator(translator)

    app.setApplicationName("Менеджер архивов")

    icon_path = Path(__file__).parent.parent / "assets" / "app.ico"
    app.setWindowIcon(QIcon(str(icon_path)))

    window = ArchiveManagerApp()
    window.show()
    sys.exit(app.exec())


def _write_pid_file() -> None:
    PID_FILE.write_text(str(os.getpid()), encoding="ascii")
    atexit.register(_remove_pid_file)


def _remove_pid_file() -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text(encoding="ascii").strip() == str(
            os.getpid()
        ):
            PID_FILE.unlink()
    except OSError:
        pass
