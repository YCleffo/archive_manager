from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QFileInfo, QObject, QRunnable, QSize, Qt, QThreadPool, Signal, Slot, QPoint
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .archive_utils import create_zip_archive, extract_archive, is_supported_archive, list_archive_members
from .file_utils import (
    calculate_folder_size,
    copy_items,
    create_folder,
    delete_items,
    format_modified,
    format_size,
    list_directory,
    move_items,
    open_in_system,
    rename_item,
)
from .search_utils import SearchResult, search_files

SORT_ROLE = Qt.ItemDataRole.UserRole
PATH_ROLE = Qt.ItemDataRole.UserRole + 1


class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(SORT_ROLE)
        right = other.data(SORT_ROLE)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return str(left if left is not None else self.text()).casefold() < str(
            right if right is not None else other.text()
        ).casefold()


class OperationSignals(QObject):
    status = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class OperationWorker(QRunnable):
    def __init__(self, callback: Callable[[Callable[[str], None]], Any]) -> None:
        super().__init__()
        self.callback = callback
        self.signals = OperationSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.callback(self.signals.status.emit)
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class SearchSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal(bool)


class SearchWorker(QRunnable):
    def __init__(
        self,
        root: Path,
        query: str,
        extensions_raw: str,
        include_content: bool,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self.root = root
        self.query = query
        self.extensions_raw = extensions_raw
        self.include_content = include_content
        self.cancel_event = cancel_event
        self.signals = SearchSignals()

    @Slot()
    def run(self) -> None:
        try:
            for result in search_files(
                self.root,
                query=self.query,
                extensions_raw=self.extensions_raw,
                include_content=self.include_content,
                cancel_event=self.cancel_event,
            ):
                self.signals.result.emit(result)
            self.signals.finished.emit(self.cancel_event.is_set())
        except Exception as exc:
            self.signals.error.emit(str(exc))


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
        layout.addWidget(buttons)


class ArchiveManagerApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Archive Manager")
        self.resize(1440, 900)
        self.setMinimumSize(1024, 720)

        self.current_path = Path.home().resolve()
        self.history: list[Path] = []
        self.search_cancel_event: threading.Event | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self.workers: list[QRunnable] = []
        self.icon_provider = QFileIconProvider()

        self._apply_style()
        self._build_toolbar()
        self._build_central_area()
        self._bind_shortcuts()

        self.load_directory(self.current_path, add_history=False)

    def _standard_icon(self, icon: QStyle.StandardPixmap) -> Any:
        return self.style().standardIcon(icon)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f9;
                color: #1f2933;
                font-family: "Segoe UI";
                font-size: 10pt;
            }

            QToolBar {
                background: #ffffff;
                border: 0;
                border-bottom: 1px solid #d7dde6;
                padding: 6px;
                spacing: 5px;
            }

            QToolButton, QPushButton {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
            }

            QToolButton:hover, QPushButton:hover {
                background: #eef6ff;
                border-color: #7aa7da;
            }

            QToolButton:pressed, QPushButton:pressed {
                background: #dbeafe;
            }

            QLineEdit {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 7px 9px;
                selection-background-color: #2563eb;
            }

            QCheckBox {
                spacing: 7px;
            }

            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f7f9fc;
                border: 1px solid #d7dde6;
                border-radius: 6px;
                gridline-color: #e7ebf0;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
            }

            QHeaderView::section {
                background: #edf2f7;
                border: 0;
                border-right: 1px solid #d7dde6;
                border-bottom: 1px solid #d7dde6;
                padding: 7px 8px;
                font-weight: 600;
            }

            QSplitter::handle {
                background: #d7dde6;
                height: 6px;
            }

            QStatusBar {
                background: #ffffff;
                border-top: 1px solid #d7dde6;
            }

            QFrame#PathBar, QFrame#SearchPanel {
                background: #f4f6f9;
                border: 0;
            }
            """
        )

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Действия")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._add_toolbar_action(
            toolbar,
            "Назад",
            QStyle.StandardPixmap.SP_ArrowBack,
            self.go_back,
            "Alt+Left",
        )
        self._add_toolbar_action(
            toolbar,
            "Вверх",
            QStyle.StandardPixmap.SP_FileDialogToParent,
            self.go_up,
            "Alt+Up",
        )
        self._add_toolbar_action(
            toolbar,
            "Домой",
            QStyle.StandardPixmap.SP_DirHomeIcon,
            self.go_home,
            "Alt+Home",
        )
        self._add_toolbar_action(
            toolbar,
            "Обновить",
            QStyle.StandardPixmap.SP_BrowserReload,
            self.refresh,
            "F5",
        )
        toolbar.addSeparator()
        self._add_toolbar_action(
            toolbar,
            "Новая папка",
            QStyle.StandardPixmap.SP_FileDialogNewFolder,
            self.new_folder,
        )
        self._add_toolbar_action(
            toolbar,
            "Переименовать",
            QStyle.StandardPixmap.SP_FileDialogDetailedView,
            self.rename_selected,
            "F2",
        )
        self._add_toolbar_action(
            toolbar,
            "Удалить",
            QStyle.StandardPixmap.SP_TrashIcon,
            self.delete_selected,
            "Delete",
        )
        self._add_toolbar_action(
            toolbar,
            "Копировать",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            self.copy_selected,
            "Ctrl+C",
        )
        self._add_toolbar_action(
            toolbar,
            "Переместить",
            QStyle.StandardPixmap.SP_ArrowForward,
            self.move_selected,
            "Ctrl+X",
        )
        toolbar.addSeparator()
        self._add_toolbar_action(
            toolbar,
            "Создать ZIP",
            QStyle.StandardPixmap.SP_DriveHDIcon,
            self.create_zip_from_selection,
        )
        self._add_toolbar_action(
            toolbar,
            "Распаковать",
            QStyle.StandardPixmap.SP_DialogOpenButton,
            self.extract_selected_archive,
        )
        self._add_toolbar_action(
            toolbar,
            "Размер папки",
            QStyle.StandardPixmap.SP_FileDialogInfoView,
            self.calculate_selected_size,
        )

    def _add_toolbar_action(
        self,
        toolbar: Any,
        text: str,
        icon: QStyle.StandardPixmap,
        callback: Callable[[], None],
        shortcut: str | None = None,
    ) -> QAction:
        action = QAction(self._standard_icon(icon), text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(f"{text} ({shortcut})")
        else:
            action.setToolTip(text)
        def on_triggered(_checked: bool = False, cb: Callable[[], None] = callback) -> None:
            cb()
        action.triggered.connect(on_triggered)
        toolbar.addAction(action)
        return action

    def _build_central_area(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        path_bar = QFrame(central)
        path_bar.setObjectName("PathBar")
        path_layout = QHBoxLayout(path_bar)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)

        path_layout.addWidget(QLabel("Путь:", path_bar))
        self.path_edit = QLineEdit(path_bar)
        self.path_edit.returnPressed.connect(self.navigate_from_entry)
        path_layout.addWidget(self.path_edit, 1)

        go_button = QPushButton("Перейти", path_bar)
        go_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        go_button.clicked.connect(self.navigate_from_entry)
        path_layout.addWidget(go_button)

        choose_button = QPushButton("Обзор", path_bar)
        choose_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DirOpenIcon))
        choose_button.clicked.connect(self.choose_directory)
        path_layout.addWidget(choose_button)
        layout.addWidget(path_bar)

        splitter = QSplitter(Qt.Orientation.Vertical, central)
        splitter.addWidget(self._build_file_table())
        splitter.addWidget(self._build_search_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([560, 260])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Готово")

    def _build_file_table(self) -> QTableWidget:
        self.file_table = QTableWidget(0, 4, self)
        self.file_table.setHorizontalHeaderLabels(["Имя", "Тип", "Размер", "Изменён"])
        self.file_table.setAlternatingRowColors(True)
        self.file_table.setSortingEnabled(True)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.file_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_table.setShowGrid(False)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.verticalHeader().setDefaultSectionSize(34)
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.file_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self.show_file_context_menu)
        def on_file_double_clicked(_row: int, _column: int) -> None:
            self.open_selected()
        self.file_table.cellDoubleClicked.connect(on_file_double_clicked)
        return self.file_table

    def _build_search_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("SearchPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        search_bar.addWidget(QLabel("Поиск:", panel))
        self.search_edit = QLineEdit(panel)
        self.search_edit.setPlaceholderText("Имя файла или текст внутри файла")
        self.search_edit.returnPressed.connect(self.start_search)
        search_bar.addWidget(self.search_edit, 1)

        search_bar.addWidget(QLabel("Расширения:", panel))
        self.extensions_edit = QLineEdit(panel)
        self.extensions_edit.setPlaceholderText("py, txt, md")
        self.extensions_edit.setMaximumWidth(170)
        search_bar.addWidget(self.extensions_edit)

        self.content_checkbox = QCheckBox("Искать внутри файлов", panel)
        search_bar.addWidget(self.content_checkbox)

        find_button = QPushButton("Найти", panel)
        find_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DialogOkButton))
        find_button.clicked.connect(self.start_search)
        search_bar.addWidget(find_button)

        stop_button = QPushButton("Стоп", panel)
        stop_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_BrowserStop))
        stop_button.clicked.connect(self.stop_search)
        search_bar.addWidget(stop_button)
        layout.addLayout(search_bar)

        self.search_table = QTableWidget(0, 5, panel)
        self.search_table.setHorizontalHeaderLabels(["Результат", "Совпадение", "Тип", "Размер", "Изменён"])
        self.search_table.setAlternatingRowColors(True)
        self.search_table.setSortingEnabled(True)
        self.search_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.search_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.search_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.search_table.setShowGrid(False)
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.verticalHeader().setDefaultSectionSize(32)
        self.search_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.search_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        def on_search_double_clicked(_row: int, _column: int) -> None:
            self.open_search_result()
        self.search_table.cellDoubleClicked.connect(on_search_double_clicked)
        layout.addWidget(self.search_table, 1)

        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return panel

    def _bind_shortcuts(self) -> None:
        open_action = QAction(self)
        open_action.setShortcut(QKeySequence("Return"))
        open_action.triggered.connect(self.open_selected)
        self.addAction(open_action)

    def set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def load_directory(self, path: Path, add_history: bool = True) -> None:
        try:
            path = Path(path).expanduser().resolve()
            if not path.exists() or not path.is_dir():
                raise NotADirectoryError(str(path))
            if add_history and path != self.current_path:
                self.history.append(self.current_path)
            self.current_path = path
            self.path_edit.setText(str(path))
            entries = list_directory(path)

            self.file_table.setSortingEnabled(False)
            self.file_table.setRowCount(0)
            for entry in entries:
                self.insert_file_entry(entry)
            self.file_table.setSortingEnabled(True)
            self.file_table.sortItems(0, Qt.SortOrder.AscendingOrder)
            self.set_status(f"Открыто: {path} | объектов: {len(entries)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть папку:\n{exc}")
            self.set_status("Ошибка открытия папки")

    def insert_file_entry(self, entry: Any) -> None:
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)

        name_item = SortableTableWidgetItem(entry.name)
        name_item.setIcon(self.icon_provider.icon(QFileInfo(str(entry.path))))
        name_item.setData(SORT_ROLE, f"{0 if entry.is_dir else 1}|{entry.name.casefold()}")
        name_item.setData(PATH_ROLE, str(entry.path))

        kind_item = SortableTableWidgetItem(entry.kind)
        kind_item.setData(SORT_ROLE, entry.kind.casefold())

        size_item = SortableTableWidgetItem(format_size(entry.size))
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_item.setData(SORT_ROLE, -1 if entry.size is None else entry.size)

        modified_item = SortableTableWidgetItem(format_modified(entry.modified))
        modified_item.setData(SORT_ROLE, 0 if entry.modified is None else entry.modified.timestamp())

        self.file_table.setItem(row, 0, name_item)
        self.file_table.setItem(row, 1, kind_item)
        self.file_table.setItem(row, 2, size_item)
        self.file_table.setItem(row, 3, modified_item)

    def refresh(self) -> None:
        self.load_directory(self.current_path, add_history=False)

    def navigate_from_entry(self) -> None:
        self.load_directory(Path(self.path_edit.text()))

    def choose_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Выберите папку", str(self.current_path))
        if selected:
            self.load_directory(Path(selected))

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
        previous = self.history.pop()
        self.load_directory(previous, add_history=False)

    def get_selected_paths(self) -> list[Path]:
        rows = sorted({index.row() for index in self.file_table.selectionModel().selectedRows()})
        paths: list[Path] = []
        for row in rows:
            item = self.file_table.item(row, 0)
            if item is not None:
                paths.append(Path(item.data(PATH_ROLE)))
        return paths

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
            else:
                open_in_system(path)
                self.set_status(f"Открыто: {path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть:\n{exc}")

    def new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "Новая папка", "Введите имя папки:")
        if not ok or not name:
            return
        try:
            created = create_folder(self.current_path, name)
            self.refresh()
            self.set_status(f"Создана папка: {created.name}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def rename_selected(self) -> None:
        path = self.get_selected_path()
        if path is None:
            QMessageBox.information(self, "Переименование", "Выберите один файл или папку")
            return
        new_name, ok = QInputDialog.getText(self, "Переименовать", "Новое имя:", text=path.name)
        if not ok or not new_name or new_name == path.name:
            return
        try:
            renamed = rename_item(path, new_name)
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
            "Удалить",
            f"Удалить выбранные объекты без корзины?\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_items(paths)
            self.refresh()
            self.set_status(f"Удалено объектов: {len(paths)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить:\n{exc}")

    def copy_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Копирование", "Выберите файлы или папки")
            return
        destination = QFileDialog.getExistingDirectory(self, "Куда копировать?", str(self.current_path))
        if not destination:
            return
        try:
            copied = copy_items(paths, Path(destination))
            self.refresh()
            self.set_status(f"Скопировано объектов: {len(copied)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скопировать:\n{exc}")

    def move_selected(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Перемещение", "Выберите файлы или папки")
            return
        destination = QFileDialog.getExistingDirectory(self, "Куда переместить?", str(self.current_path))
        if not destination:
            return
        try:
            moved = move_items(paths, Path(destination))
            self.refresh()
            self.set_status(f"Перемещено объектов: {len(moved)}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось переместить:\n{exc}")

    def create_zip_from_selection(self) -> None:
        paths = self.get_selected_paths()
        if not paths:
            QMessageBox.information(self, "Создать ZIP", "Выберите файлы или папки для архивации")
            return

        default_name = "archive.zip" if len(paths) != 1 else f"{paths[0].stem}.zip"
        output, _filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить ZIP",
            str(self.current_path / default_name),
            "ZIP archive (*.zip)",
        )
        if not output:
            return
        output_path = Path(output)
        if output_path.suffix.lower() != ".zip":
            output_path = output_path.with_suffix(".zip")

        def task(status: Callable[[str], None]) -> Path:
            status("Создание архива...")
            return create_zip_archive(
                output_path,
                paths,
                progress=lambda name: status(f"Архивирую: {Path(name).name}"),
            )

        self._start_operation(task, "Ошибка создания архива", lambda created: self._zip_created(Path(created)))

    def _zip_created(self, created: Path) -> None:
        self.refresh()
        QMessageBox.information(self, "Готово", f"Архив создан:\n{created}")
        self.set_status(f"Архив создан: {created.name}")

    def extract_selected_archive(self) -> None:
        path = self.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            selected, _filter = QFileDialog.getOpenFileName(
                self,
                "Выберите архив",
                str(self.current_path),
                "Archives (*.zip *.tar *.tar.gz *.tgz *.tar.bz2);;All files (*.*)",
            )
            if not selected:
                return
            path = Path(selected)

        destination = QFileDialog.getExistingDirectory(self, "Куда распаковать?", str(path.parent))
        if not destination:
            return
        destination_path = Path(destination)

        def task(status: Callable[[str], None]) -> tuple[Path, Path]:
            status("Распаковка архива...")
            extract_archive(path, destination_path, progress=lambda name: status(f"Распаковываю: {name}"))
            return path, destination_path

        self._start_operation(task, "Ошибка распаковки", lambda result: self._archive_extracted(result[0], result[1]))

    def _archive_extracted(self, archive_path: Path, destination: Path) -> None:
        self.load_directory(destination)
        QMessageBox.information(self, "Готово", f"Архив распакован в:\n{destination}")
        self.set_status(f"Распаковано: {archive_path.name}")

    def calculate_selected_size(self) -> None:
        path = self.get_selected_path()
        if not path or not path.is_dir():
            QMessageBox.information(self, "Размер", "Выберите папку для подсчёта размера")
            return

        def task(status: Callable[[str], None]) -> tuple[Path, int, int]:
            status(f"Вычисление размера: {path.name}...")
            total_size, total_files = calculate_folder_size(path)
            return path, total_size, total_files

        self._start_operation(task, "Ошибка подсчёта размера", lambda result: self._folder_size_ready(result[0], result[1], result[2]))

    def _folder_size_ready(self, path: Path, total_size: int, total_files: int) -> None:
        QMessageBox.information(
            self,
            "Размер папки",
            f"Папка: {path.name}\nРазмер: {format_size(total_size)}\nФайлов: {total_files}",
        )
        self.set_status(f"Размер {path.name}: {format_size(total_size)}")

    def show_archive_contents(self) -> None:
        path = self.get_selected_path()
        if path is None or not path.is_file() or not is_supported_archive(path):
            QMessageBox.information(self, "Архив", "Выберите ZIP/TAR-архив")
            return
        try:
            members = list_archive_members(path)
            preview = "\n".join(members[:200])
            if len(members) > 200:
                preview += f"\n...и ещё {len(members) - 200} элементов"
            ArchivePreviewDialog(self, path.name, preview or "Архив пуст").exec()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать архив:\n{exc}")

    def start_search(self) -> None:
        query = self.search_edit.text().strip()
        if not query:
            QMessageBox.information(self, "Поиск", "Введите запрос")
            return
        self.stop_search(silent=True)
        self.search_table.setSortingEnabled(False)
        self.search_table.setRowCount(0)
        self.search_table.setSortingEnabled(True)

        self.search_cancel_event = threading.Event()
        worker = SearchWorker(
            self.current_path,
            query=query,
            extensions_raw=self.extensions_edit.text(),
            include_content=self.content_checkbox.isChecked(),
            cancel_event=self.search_cancel_event,
        )
        worker.signals.result.connect(self.insert_search_result)
        def on_search_error(error_msg: str) -> None:
            self._show_search_error(error_msg)
        worker.signals.error.connect(on_search_error)
        worker.signals.finished.connect(self._search_finished)
        self._track_worker(worker)
        self.thread_pool.start(worker)
        self.set_status("Поиск запущен...")

    def stop_search(self, silent: bool = False) -> None:
        if self.search_cancel_event is not None:
            self.search_cancel_event.set()
            if not silent:
                self.set_status("Поиск остановлен")

    def insert_search_result(self, result: SearchResult) -> None:
        sorting = self.search_table.isSortingEnabled()
        self.search_table.setSortingEnabled(False)

        row = self.search_table.rowCount()
        self.search_table.insertRow(row)

        path_item = SortableTableWidgetItem(str(result.path))
        path_item.setIcon(self.icon_provider.icon(QFileInfo(str(result.path))))
        path_item.setData(SORT_ROLE, str(result.path).casefold())
        path_item.setData(PATH_ROLE, str(result.path))

        match_item = SortableTableWidgetItem(result.match_type)
        match_item.setData(SORT_ROLE, result.match_type)

        kind_item = SortableTableWidgetItem(result.kind)
        kind_item.setData(SORT_ROLE, result.kind.casefold())

        size_item = SortableTableWidgetItem(format_size(result.size))
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_item.setData(SORT_ROLE, -1 if result.size is None else result.size)

        modified_item = SortableTableWidgetItem(format_modified(result.modified))
        modified_item.setData(SORT_ROLE, 0 if result.modified is None else result.modified.timestamp())

        self.search_table.setItem(row, 0, path_item)
        self.search_table.setItem(row, 1, match_item)
        self.search_table.setItem(row, 2, kind_item)
        self.search_table.setItem(row, 3, size_item)
        self.search_table.setItem(row, 4, modified_item)
        self.search_table.setSortingEnabled(sorting)

    def _search_finished(self, cancelled: bool) -> None:
        if cancelled:
            self.set_status("Поиск остановлен")
        else:
            self.set_status(f"Поиск завершён. Найдено: {self.search_table.rowCount()}")
        self.search_cancel_event = None

    def _show_search_error(self, error: str) -> None:
        QMessageBox.critical(self, "Ошибка поиска", error)
        self.set_status("Ошибка поиска")
        self.search_cancel_event = None

    def open_search_result(self) -> None:
        rows = self.search_table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.search_table.item(rows[0].row(), 0)
        if item is None:
            return
        path = Path(item.data(PATH_ROLE))
        try:
            if path.is_dir():
                self.load_directory(path)
            elif path.exists():
                open_in_system(path)
            else:
                QMessageBox.warning(self, "Поиск", "Файл уже не существует")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть результат:\n{exc}")

    def show_file_context_menu(self, pos: QPoint) -> None:
        index = self.file_table.indexAt(pos)
        if index.isValid():
            selected_rows = {row.row() for row in self.file_table.selectionModel().selectedRows()}
            if index.row() not in selected_rows:
                self.file_table.selectRow(index.row())

        menu = QMenu(self)
        self._add_menu_action(menu, "Открыть", QStyle.StandardPixmap.SP_DialogOpenButton, self.open_selected)
        self._add_menu_action(
            menu,
            "Показать содержимое архива",
            QStyle.StandardPixmap.SP_FileDialogInfoView,
            self.show_archive_contents,
        )
        menu.addSeparator()
        self._add_menu_action(menu, "Создать ZIP", QStyle.StandardPixmap.SP_DriveHDIcon, self.create_zip_from_selection)
        self._add_menu_action(menu, "Распаковать", QStyle.StandardPixmap.SP_DialogOpenButton, self.extract_selected_archive)
        menu.addSeparator()
        self._add_menu_action(menu, "Копировать", QStyle.StandardPixmap.SP_DialogSaveButton, self.copy_selected)
        self._add_menu_action(menu, "Переместить", QStyle.StandardPixmap.SP_ArrowForward, self.move_selected)
        self._add_menu_action(menu, "Переименовать", QStyle.StandardPixmap.SP_FileDialogDetailedView, self.rename_selected)
        self._add_menu_action(menu, "Удалить", QStyle.StandardPixmap.SP_TrashIcon, self.delete_selected)
        menu.addSeparator()
        self._add_menu_action(menu, "Размер папки", QStyle.StandardPixmap.SP_FileDialogInfoView, self.calculate_selected_size)
        menu.exec(self.file_table.viewport().mapToGlobal(pos))

    def _add_menu_action(
        self,
        menu: QMenu,
        text: str,
        icon: QStyle.StandardPixmap,
        callback: Callable[[], None],
    ) -> QAction:
        action = QAction(self._standard_icon(icon), text, self)
        def on_menu_triggered(_checked: bool = False, cb: Callable[[], None] = callback) -> None:
            cb()
        action.triggered.connect(on_menu_triggered)
        menu.addAction(action)
        return action

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


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Archive Manager")
    window = ArchiveManagerApp()
    window.show()
    sys.exit(app.exec())
