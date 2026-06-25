from __future__ import annotations

from pathlib import Path


from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..file_utils import FileEntry, format_modified, format_size
from ..search_utils import SearchResult
from .icons import IconFactory
from .theme import make_interactive

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


class TableCard(QFrame):
    def __init__(self, table: QTableWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TableCard")
        self.table = table

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(0)
        layout.addWidget(table)


class FileTable(QTableWidget):
    open_requested = Signal()
    delete_requested = Signal()
    rename_requested = Signal()
    context_menu_requested = Signal(QPoint)
    size_requested = Signal(Path)

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.icons = icons
        self.setObjectName("FileTable")
        self.setHorizontalHeaderLabels(["Имя", "Тип", "Размер", "Изменён"])
        configure_table(self, multi_select=True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.setColumnWidth(2, 120)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        set_header_alignments(
            self,
            {
                0: Qt.AlignmentFlag.AlignLeft,
                1: Qt.AlignmentFlag.AlignLeft,
                2: Qt.AlignmentFlag.AlignRight,
                3: Qt.AlignmentFlag.AlignLeft,
            },
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        def on_cell_double_clicked(_row: int, _column: int) -> None:
            self.open_requested.emit()
        self.cellDoubleClicked.connect(on_cell_double_clicked)

    def set_entries(self, entries: list[FileEntry]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for entry in entries:
            self._insert_entry(entry)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)

    def selected_paths(self) -> list[Path]:
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        paths: list[Path] = []
        for row in rows:
            item = self.item(row, 0)
            if item is not None:
                paths.append(Path(item.data(PATH_ROLE)))
        return paths

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_requested.emit()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.delete_requested.emit()
            return
        if event.key() == Qt.Key.Key_F2:
            self.rename_requested.emit()
            return
        super().keyPressEvent(event)

    def _insert_entry(self, entry: FileEntry) -> None:
        row = self.rowCount()
        self.insertRow(row)

        name_item = SortableTableWidgetItem(entry.name)
        name_item.setIcon(self.icons.icon("folder" if entry.is_dir else "file"))
        name_item.setData(SORT_ROLE, f"{0 if entry.is_dir else 1}|{entry.name.casefold()}")
        name_item.setData(PATH_ROLE, str(entry.path))

        kind_item = SortableTableWidgetItem(entry.kind)
        kind_item.setData(SORT_ROLE, entry.kind.casefold())

        size_item = SortableTableWidgetItem(format_size(entry.size))
        size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        size_item.setData(SORT_ROLE, -1 if entry.size is None else entry.size)

        modified_item = SortableTableWidgetItem(format_modified(entry.modified))
        modified_item.setData(SORT_ROLE, 0 if entry.modified is None else entry.modified.timestamp())

        self.setItem(row, 0, name_item)
        self.setItem(row, 1, kind_item)
        self.setItem(row, 2, size_item)
        self.setItem(row, 3, modified_item)
        if entry.is_dir:
            self._set_size_button(row, entry.path)

    def set_folder_size(self, path: Path, total_size: int) -> None:
        normalized = str(Path(path).resolve())
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None and str(Path(item.data(PATH_ROLE)).resolve()) == normalized:
                self.removeCellWidget(row, 2)
                size_item = self.item(row, 2)
                if size_item is None:
                    size_item = SortableTableWidgetItem()
                    self.setItem(row, 2, size_item)
                size_item.setText(format_size(total_size))
                size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                size_item.setData(SORT_ROLE, total_size)
                return

    def _set_size_button(self, row: int, path: Path) -> None:
        wrapper = QWidget(self)
        wrapper.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)
        layout.addStretch(1)

        button = QPushButton("Посчитать", wrapper)
        button.setObjectName("SizeButton")
        button.setFixedHeight(26)
        button.setMaximumWidth(96)
        make_interactive(button, "Посчитать размер этой папки")

        def on_clicked(_checked: bool = False, requested_path: Path = path) -> None:
            self.size_requested.emit(requested_path)

        button.clicked.connect(on_clicked)
        layout.addWidget(button)
        self.setCellWidget(row, 2, wrapper)

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if index.isValid():
            selected_rows = {row.row() for row in self.selectionModel().selectedRows()}
            if index.row() not in selected_rows:
                self.selectRow(index.row())
        self.context_menu_requested.emit(pos)


class SearchResultsTable(QTableWidget):
    open_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(0, 5, parent)
        self.icons = icons
        self.setHorizontalHeaderLabels(["Результат", "Совпадение", "Тип", "Размер", "Изменён"])
        configure_table(self, multi_select=False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        set_header_alignments(
            self,
            {
                0: Qt.AlignmentFlag.AlignLeft,
                1: Qt.AlignmentFlag.AlignLeft,
                2: Qt.AlignmentFlag.AlignLeft,
                3: Qt.AlignmentFlag.AlignRight,
                4: Qt.AlignmentFlag.AlignLeft,
            },
        )
        def on_search_cell_double_clicked(_row: int, _column: int) -> None:
            self.open_requested.emit()
        self.cellDoubleClicked.connect(on_search_cell_double_clicked)

    def add_result(self, result: SearchResult) -> None:
        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)

        path_item = SortableTableWidgetItem(str(result.path))
        path_item.setIcon(self.icons.icon("folder" if result.path.is_dir() else "file"))
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

        self.setItem(row, 0, path_item)
        self.setItem(row, 1, match_item)
        self.setItem(row, 2, kind_item)
        self.setItem(row, 3, size_item)
        self.setItem(row, 4, modified_item)
        self.setSortingEnabled(sorting)

    def selected_path(self) -> Path | None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.item(rows[0].row(), 0)
        if item is None:
            return None
        return Path(item.data(PATH_ROLE))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_requested.emit()
            return
        super().keyPressEvent(event)


def configure_table(table: QTableWidget, multi_select: bool) -> None:
    table.setFrameShape(QFrame.Shape.NoFrame)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection if multi_select else QAbstractItemView.SelectionMode.SingleSelection
    )
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.verticalScrollBar().setCursor(Qt.CursorShape.PointingHandCursor)
    table.horizontalScrollBar().setCursor(Qt.CursorShape.PointingHandCursor)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(36)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    table.setMouseTracking(True)


def set_header_alignments(table: QTableWidget, alignments: dict[int, Qt.AlignmentFlag]) -> None:
    for column, alignment in alignments.items():
        item = table.horizontalHeaderItem(column)
        if item is not None:
            item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
