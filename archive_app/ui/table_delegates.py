from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileIconProvider,
    QFrame,
    QProxyStyle,
    QStyle,
    QStyleOption,
    QStyleOptionHeader,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from .icons import IconFactory

icon_provider = QFileIconProvider()

SORT_ROLE = Qt.ItemDataRole.UserRole
PATH_ROLE = Qt.ItemDataRole.UserRole + 1
HOVER_ROLE = Qt.ItemDataRole.UserRole + 2
SIZE_BUTTON_ROLE = Qt.ItemDataRole.UserRole + 3
SIZE_PATH_ROLE = Qt.ItemDataRole.UserRole + 4
CALCULATED_SIZE_ROLE = Qt.ItemDataRole.UserRole + 5
HOVER_ROW_COLOR = QColor("#e6f0ff")
BUTTON_BG_COLOR = QColor("#ffffff")
BUTTON_HOVER_BG_COLOR = QColor("#ffffff")
BUTTON_BORDER_COLOR = QColor("#cfd8e3")
BUTTON_TEXT_COLOR = QColor("#425466")


class SortArrowStyle(QProxyStyle):
    def __init__(self, icons: IconFactory) -> None:
        super().__init__()
        self.icons = icons

    def sizeFromContents(
        self,
        contentsType: QStyle.ContentsType,
        option: QStyleOption,
        size: QSize,
        widget: QWidget | None = None,
    ) -> QSize:
        base_size = super().sizeFromContents(
            contentsType, option, size, cast(QWidget, widget)
        )
        if contentsType == QStyle.ContentsType.CT_HeaderSection:
            if isinstance(option, QStyleOptionHeader):
                if option.sortIndicator != QStyleOptionHeader.SortIndicator.None_:
                    base_size.setWidth(base_size.width() + 18 + 12 + 12)
        return base_size

    def subElementRect(
        self,
        element: QStyle.SubElement,
        option: QStyleOption,
        widget: QWidget | None = None,
    ) -> QRect:
        if element == QStyle.SubElement.SE_HeaderArrow:
            if isinstance(option, QStyleOptionHeader):
                label_rect = super().subElementRect(
                    QStyle.SubElement.SE_HeaderLabel, option, cast(QWidget, widget)
                )
                text_width = option.fontMetrics.horizontalAdvance(option.text)
                arrow_width = 18
                arrow_height = 18
                padding_left = label_rect.left() - option.rect.left()
                if padding_left < 0:
                    padding_left = 6
                x = label_rect.left() + text_width + 12
                if x + arrow_width > option.rect.right() - padding_left:
                    x = option.rect.right() - padding_left - arrow_width
                y = label_rect.center().y() - arrow_height // 2
                return QRect(x, y, arrow_width, arrow_height)
        return super().subElementRect(element, option, cast(QWidget, widget))

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        if element == QStyle.PrimitiveElement.PE_IndicatorHeaderArrow:
            if isinstance(option, QStyleOptionHeader):
                if option.sortIndicator == QStyleOptionHeader.SortIndicator.SortUp:
                    icon = self.icons.icon("sort-up")
                elif option.sortIndicator == QStyleOptionHeader.SortIndicator.SortDown:
                    icon = self.icons.icon("sort-down")
                else:
                    return
                icon.paint(painter, option.rect, Qt.AlignmentFlag.AlignCenter)
            return
        super().drawPrimitive(element, option, painter, widget)


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

        painter.save()
        painter.setPen(QColor("#152033"))
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

        calculated_size = index.data(CALCULATED_SIZE_ROLE)
        button_text = (
            str(calculated_size)
            if calculated_size
            else str(index.data(Qt.ItemDataRole.DisplayRole) or "Посчитать")
        )
        painter.drawText(button_rect, Qt.AlignmentFlag.AlignCenter, button_text)
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
                    from typing import Any, cast

                    parent_table = cast(Any, self.parent())
                    if hasattr(parent_table, "size_requested"):
                        parent_table.size_requested.emit(Path(str(path_raw)))
                        return True
        return super().editorEvent(event, model, option, index)

    @staticmethod
    def _button_rect(cell_rect: QRect) -> QRect:
        height = max(26, cell_rect.height() - 10)
        width = min(110, max(60, cell_rect.width() - 16))
        x = cell_rect.x() + (cell_rect.width() - width) // 2
        y = cell_rect.y() + (cell_rect.height() - height) // 2
        return QRect(x, y, width, height)


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
    table.horizontalHeader().setSortIndicatorShown(True)
    if hasattr(table, "icons"):
        icons = cast(IconFactory, getattr(table, "icons"))
        table.horizontalHeader().setStyle(SortArrowStyle(icons))
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
