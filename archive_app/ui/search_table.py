from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QFileInfo
from PySide6.QtGui import QBrush, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QHeaderView, QTableWidget, QWidget
from PySide6.QtCore import Signal

from ..file_utils import format_modified, format_size
from ..search_utils import SearchResult
from .icons import IconFactory
from .table_delegates import (
    HOVER_ROLE,
    HOVER_ROW_COLOR,
    PATH_ROLE,
    SORT_ROLE,
    SortableTableWidgetItem,
    icon_provider,
    configure_table,
    set_header_alignments,
)


class SearchResultsTable(QTableWidget):
    open_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(0, 5, parent)
        self.icons = icons
        self.hovered_row = -1
        self.setHorizontalHeaderLabels(
            ["Результат", "Совпадение", "Тип", "Размер", "Дата изменения"]
        )
        configure_table(self, multi_select=False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        set_header_alignments(
            self,
            {
                0: Qt.AlignmentFlag.AlignLeft,
                1: Qt.AlignmentFlag.AlignLeft,
                2: Qt.AlignmentFlag.AlignLeft,
                3: Qt.AlignmentFlag.AlignLeft,
                4: Qt.AlignmentFlag.AlignLeft,
            },
        )
        self.viewport().installEventFilter(self)

        def on_search_cell_double_clicked(_row: int, _column: int) -> None:
            self.open_requested.emit()

        self.cellDoubleClicked.connect(on_search_cell_double_clicked)
        self.cellEntered.connect(self._on_cell_entered)

    def add_result(self, result: SearchResult) -> None:
        sorting = self.isSortingEnabled()
        self.setSortingEnabled(False)

        row = self.rowCount()
        self.insertRow(row)

        path_item = SortableTableWidgetItem(str(result.path))
        path_item.setIcon(icon_provider.icon(QFileInfo(str(result.path))))
        path_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        path_item.setData(SORT_ROLE, str(result.path).casefold())
        path_item.setData(PATH_ROLE, str(result.path))

        match_item = SortableTableWidgetItem(result.match_type)
        match_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        match_item.setData(SORT_ROLE, result.match_type)

        kind_item = SortableTableWidgetItem(result.kind)
        kind_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        kind_item.setData(SORT_ROLE, result.kind.casefold())

        size_item = SortableTableWidgetItem(format_size(result.size))
        size_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        size_item.setData(SORT_ROLE, -1 if result.size is None else result.size)

        modified_item = SortableTableWidgetItem(format_modified(result.modified))
        modified_item.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        modified_item.setData(
            SORT_ROLE, 0 if result.modified is None else result.modified.timestamp()
        )

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
        return Path(str(item.data(PATH_ROLE)))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_requested.emit()
            return
        super().keyPressEvent(event)

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
