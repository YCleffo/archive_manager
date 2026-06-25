from __future__ import annotations

from pathlib import Path
from typing import cast


from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QObject,
    QRect,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QBrush, QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..file_utils import FileEntry, format_modified, format_size
from ..search_utils import SearchResult
from .icons import IconFactory

SORT_ROLE = Qt.ItemDataRole.UserRole
PATH_ROLE = Qt.ItemDataRole.UserRole + 1
HOVER_ROLE = Qt.ItemDataRole.UserRole + 2
SIZE_BUTTON_ROLE = Qt.ItemDataRole.UserRole + 3
SIZE_PATH_ROLE = Qt.ItemDataRole.UserRole + 4
HOVER_ROW_COLOR = QColor("#e6f0ff")
BUTTON_BG_COLOR = QColor("#ffffff")
BUTTON_HOVER_BG_COLOR = QColor("#ffffff")
BUTTON_BORDER_COLOR = QColor("#cfd8e3")
BUTTON_TEXT_COLOR = QColor("#425466")


class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(SORT_ROLE)
        right = other.data(SORT_ROLE)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return (
            str(left if left is not None else self.text()).casefold()
            < str(right if right is not None else other.text()).casefold()
        )


class NoFocusDelegate(QStyledItemDelegate):
    def _is_hovered(
        self,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        parent_table = self.parent()
        return index.row() == getattr(parent_table, "hovered_row", -1)

    def _prepare_option(self, option: QStyleOptionViewItem) -> QStyleOptionViewItem:
        clean_option = QStyleOptionViewItem(option)
        clean_option.state &= ~QStyle.StateFlag.State_HasFocus
        clean_option.state &= ~QStyle.StateFlag.State_MouseOver
        return clean_option

    def _paint_hover_background(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if self._is_hovered(index) and not is_selected:
            painter.fillRect(option.rect, HOVER_ROW_COLOR)
            return True
        return False

    def _paint_hover_cell(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if not self._paint_hover_background(painter, option, index):
            return False

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if alignment is None:
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        text_rect = option.rect.adjusted(10, 0, -10, 0)
        if icon is not None and hasattr(icon, "paint"):
            icon_rect = QRect(
                text_rect.left(),
                text_rect.top() + (text_rect.height() - 18) // 2,
                18,
                18,
            )
            icon.paint(painter, icon_rect)
            text_rect.setLeft(icon_rect.right() + 10)

        painter.save()
        painter.setPen(QColor("#152033"))
        painter.drawText(text_rect, alignment, text)
        painter.restore()
        return True

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        clean_option = self._prepare_option(option)
        is_selected = bool(clean_option.state & QStyle.StateFlag.State_Selected)
        is_hovered = self._is_hovered(index) and not is_selected
        has_icon = index.data(Qt.ItemDataRole.DecorationRole) is not None

        if has_icon:
            # We ALWAYS manually draw cells with icons to keep icon size and text 
            # position completely stable, avoiding Qt's native resize on hover.
            if is_hovered:
                painter.fillRect(clean_option.rect, HOVER_ROW_COLOR)
            elif is_selected:
                painter.fillRect(clean_option.rect, QColor("#e6f0ff"))
            elif clean_option.features & QStyleOptionViewItem.ViewItemFeature.Alternate:
                painter.fillRect(clean_option.rect, QColor("#fafbfc"))
            else:
                painter.fillRect(clean_option.rect, QColor("#ffffff"))
                
            self._paint_content(painter, clean_option, index)
        else:
            if is_hovered:
                painter.fillRect(clean_option.rect, HOVER_ROW_COLOR)
            super().paint(painter, clean_option, index)


    def _paint_content(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if alignment is None:
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        text_rect = option.rect.adjusted(10, 0, -10, 0)
        if icon is not None and hasattr(icon, "paint"):
            icon_rect = QRect(
                text_rect.left(),
                text_rect.top() + (text_rect.height() - 18) // 2,
                18,
                18,
            )
            icon.paint(painter, icon_rect)
            text_rect.setLeft(icon_rect.right() + 10)

        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setPen(QColor("#152033") if not is_selected else QColor("#152033"))
        painter.drawText(text_rect, alignment, text)
        painter.restore()


class SizeButtonDelegate(NoFocusDelegate):
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if not bool(index.data(SIZE_BUTTON_ROLE)):
            super().paint(painter, option, index)
            return

        clean_option = self._prepare_option(option)
        clean_option.text = ""
        QStyledItemDelegate.paint(self, painter, clean_option, index)
        self._paint_hover_background(painter, clean_option, index)

        button_rect = self._button_rect(clean_option.rect)
        is_selected = bool(clean_option.state & QStyle.StateFlag.State_Selected)
        row_hovered = self._is_hovered(index) and not is_selected

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(BUTTON_BORDER_COLOR, 1))
        painter.setBrush(BUTTON_HOVER_BG_COLOR if row_hovered else BUTTON_BG_COLOR)
        painter.drawRoundedRect(button_rect, 6, 6)
        painter.setPen(BUTTON_TEXT_COLOR)
        painter.drawText(
            button_rect,
            Qt.AlignmentFlag.AlignCenter,
            str(index.data(Qt.ItemDataRole.DisplayRole) or "Посчитать"),
        )
        painter.restore()

    def editorEvent(
        self,
        event: QEvent,
        model: QAbstractItemModel,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        if not bool(index.data(SIZE_BUTTON_ROLE)):
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.Type.MouseButtonRelease and isinstance(
            event, QMouseEvent
        ):
            if self._button_rect(option.rect).contains(event.position().toPoint()):
                path_raw = index.data(SIZE_PATH_ROLE)
                if path_raw:
                    parent_table = cast("FileTable", self.parent())
                    parent_table.size_requested.emit(Path(str(path_raw)))
                    return True
        return super().editorEvent(event, model, option, index)

    @staticmethod
    def _button_rect(cell_rect: QRect) -> QRect:
        height = max(26, cell_rect.height() - 10)
        width = min(88, max(40, cell_rect.width() - 16))
        x = cell_rect.x() + (cell_rect.width() - width) // 2
        y = cell_rect.y() + (cell_rect.height() - height) // 2
        return QRect(x, y, width, height)


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
        self.hovered_row = -1
        self.setObjectName("FileTable")
        self.setHorizontalHeaderLabels(["Имя", "Тип", "Размер", "Изменён"])
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
            if (
                item is not None
                and str(Path(item.data(PATH_ROLE)).resolve()) == normalized
            ):
                size_item = self.item(row, 2)
                if size_item is None:
                    size_item = SortableTableWidgetItem()
                    self.setItem(row, 2, size_item)
                size_item.setText(format_size(total_size))
                size_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                size_item.setData(SORT_ROLE, total_size)
                size_item.setData(SIZE_BUTTON_ROLE, False)
                size_item.setData(SIZE_PATH_ROLE, None)
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


class SearchResultsTable(QTableWidget):
    open_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(0, 5, parent)
        self.icons = icons
        self.hovered_row = -1
        self.setHorizontalHeaderLabels(
            ["Результат", "Совпадение", "Тип", "Размер", "Изменён"]
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
        path_item.setIcon(self.icons.icon("folder" if result.path.is_dir() else "file"))
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
        return Path(item.data(PATH_ROLE))

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


def configure_table(table: QTableWidget, multi_select: bool) -> None:
    table.setFrameShape(QFrame.Shape.NoFrame)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
        if multi_select
        else QAbstractItemView.SelectionMode.SingleSelection
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
    table.horizontalHeader().setDefaultAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    table.setItemDelegate(NoFocusDelegate(table))
    table.setMouseTracking(True)
    table.viewport().setMouseTracking(True)
    table.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)


def set_header_alignments(
    table: QTableWidget, alignments: dict[int, Qt.AlignmentFlag]
) -> None:
    for column, alignment in alignments.items():
        item = table.horizontalHeaderItem(column)
        if item is not None:
            item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
