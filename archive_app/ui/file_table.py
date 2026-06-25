from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal, QFileInfo
from PySide6.QtGui import QBrush, QKeyEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import QFrame, QHeaderView, QTableWidget, QVBoxLayout, QWidget

from ..file_utils import FileEntry, format_modified, format_size
from .icons import IconFactory
from .table_delegates import (
    CALCULATED_SIZE_ROLE,
    HOVER_ROLE,
    HOVER_ROW_COLOR,
    PATH_ROLE,
    SIZE_BUTTON_ROLE,
    SIZE_PATH_ROLE,
    SORT_ROLE,
    SizeButtonDelegate,
    SortableTableWidgetItem,
    _icon_provider,
    configure_table,
    set_header_alignments,
)


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
    selection_changed = Signal()
    copy_requested = Signal()
    cut_requested = Signal()
    paste_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.icons = icons
        self.hovered_row = -1
        self.setObjectName("FileTable")
        self.setHorizontalHeaderLabels(["Имя", "Тип", "Размер", "Дата изменения"])
        configure_table(self, multi_select=True)
        self.setItemDelegateForColumn(2, SizeButtonDelegate(self))
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Interactive
        )
        self.setColumnWidth(2, 120)
        self.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        set_header_alignments(
            self,
            {
                0: Qt.AlignmentFlag.AlignLeft,
                1: Qt.AlignmentFlag.AlignLeft,
                2: Qt.AlignmentFlag.AlignLeft,
                3: Qt.AlignmentFlag.AlignLeft,
            },
        )
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.viewport().installEventFilter(self)

        def on_cell_double_clicked(_row: int, _column: int) -> None:
            self.open_requested.emit()

        self.cellDoubleClicked.connect(on_cell_double_clicked)
        self.cellEntered.connect(self._on_cell_entered)
        self.itemSelectionChanged.connect(self.selection_changed.emit)

    def set_entries(self, entries: list[FileEntry]) -> None:
        self.setUpdatesEnabled(False)
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for entry in entries:
            self._insert_entry(entry)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.setUpdatesEnabled(True)
        self.clearSelection()
        self.selection_changed.emit()

    def selected_paths(self) -> list[Path]:
        rows = sorted({index.row() for index in self.selectionModel().selectedRows()})
        paths: list[Path] = []
        for row in rows:
            item = self.item(row, 0)
            if item is not None:
                paths.append(Path(str(item.data(PATH_ROLE))))
        return paths

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_requested.emit()
            return
        if event.matches(QKeySequence.StandardKey.Cut):
            self.cut_requested.emit()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            self.paste_requested.emit()
            return
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
        name_item.setIcon(_icon_provider.icon(QFileInfo(str(entry.path))))
        name_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        name_item.setData(
            SORT_ROLE, f"{0 if entry.is_dir else 1}|{entry.name.casefold()}"
        )
        name_item.setData(PATH_ROLE, str(entry.path))

        kind_item = SortableTableWidgetItem(entry.kind)
        kind_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        kind_item.setData(SORT_ROLE, entry.kind.casefold())

        size_item = SortableTableWidgetItem(format_size(entry.size))
        size_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        size_item.setData(SORT_ROLE, -1 if entry.size is None else entry.size)
        size_item.setData(SIZE_BUTTON_ROLE, False)

        modified_item = SortableTableWidgetItem(format_modified(entry.modified))
        modified_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        modified_item.setData(
            SORT_ROLE, 0 if entry.modified is None else entry.modified.timestamp()
        )

        self.setItem(row, 0, name_item)
        self.setItem(row, 1, kind_item)
        self.setItem(row, 2, size_item)
        self.setItem(row, 3, modified_item)
        if entry.is_dir:
            size_item.setText("Посчитать")
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            size_item.setData(SIZE_BUTTON_ROLE, True)
            size_item.setData(SIZE_PATH_ROLE, str(entry.path))

    def set_folder_size(self, path: Path, total_size: int) -> None:
        normalized = str(Path(path).resolve())
        for row in range(self.rowCount()):
            item = self.item(row, 0)
            if item is not None and str(Path(str(item.data(PATH_ROLE))).resolve()) == normalized:
                size_item = self.item(row, 2)
                if size_item is None:
                    size_item = SortableTableWidgetItem()
                    self.setItem(row, 2, size_item)
                size_item.setData(SORT_ROLE, total_size)
                size_item.setData(CALCULATED_SIZE_ROLE, format_size(total_size))
                return

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.viewport():
            if isinstance(event, QMouseEvent) and event.type() in (
                QEvent.Type.MouseMove,
                QEvent.Type.HoverMove,
            ):
                self._set_hovered_row(self.rowAt(event.position().toPoint().y()))
            elif event.type() == QEvent.Type.Leave:
                self._set_hovered_row(-1)
        return super().eventFilter(watched, event)

    def _on_cell_entered(self, row: int, _column: int) -> None:
        self._set_hovered_row(row)

    def _set_hovered_row(self, row: int) -> None:
        if row == self.hovered_row:
            return
        old_row = self.hovered_row
        self.hovered_row = row
        if old_row >= 0:
            self._update_row_hover(old_row, False)
        if row >= 0:
            self._update_row_hover(row, True)

    def _update_row_hover(self, row: int, active: bool) -> None:
        if row < 0 or row >= self.rowCount():
            return
        brush = QBrush(HOVER_ROW_COLOR) if active else QBrush()
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if item is not None:
                item.setData(HOVER_ROLE, active)
                item.setBackground(brush)
        top_left = self.model().index(row, 0)
        bottom_right = self.model().index(row, self.columnCount() - 1)
        self.viewport().update(
            self.visualRect(top_left).united(self.visualRect(bottom_right))
        )

    def _show_context_menu(self, pos: QPoint) -> None:
        index = self.indexAt(pos)
        if index.isValid():
            selected_rows = {row.row() for row in self.selectionModel().selectedRows()}
            if index.row() not in selected_rows:
                self.selectRow(index.row())
        self.context_menu_requested.emit(self.viewport().mapToGlobal(pos))
