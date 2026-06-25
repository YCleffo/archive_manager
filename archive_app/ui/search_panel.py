from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..search_utils import SearchResult
from .icons import IconFactory
from .tables import SearchResultsTable, TableCard
from .theme import make_interactive


class SearchPanel(QFrame):
    start_requested = Signal()
    stop_requested = Signal()
    reset_requested = Signal()
    close_requested = Signal()
    open_result_requested = Signal()

    def __init__(self, icons: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self.setMinimumHeight(270)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("Поиск файлов", self)
        title.setStyleSheet("font-weight: 600; color: #273548;")
        header.addWidget(title)
        header.addStretch(1)

        reset_button = QToolButton(self)
        reset_button.setText("Сброс")
        reset_button.setMinimumHeight(32)
        reset_button.setIcon(icons.icon("reset"))
        reset_button.setIconSize(QSize(18, 18))
        reset_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        reset_button.clicked.connect(self.reset_requested.emit)
        make_interactive(reset_button, "Очистить запрос, фильтры и результаты поиска")
        header.addWidget(reset_button)

        close_button = QToolButton(self)
        close_button.setText("Закрыть")
        close_button.setMinimumHeight(32)
        close_button.setIcon(icons.icon("close"))
        close_button.setIconSize(QSize(18, 18))
        close_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        close_button.clicked.connect(self.close_requested.emit)
        make_interactive(close_button, "Скрыть панель поиска")
        header.addWidget(close_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        self.query_edit = QLineEdit(self)
        self.query_edit.setMinimumHeight(34)
        self.query_edit.setPlaceholderText("Имя файла или текст внутри файла")
        self.query_edit.setToolTip("Введите запрос для поиска в текущей папке")
        self.query_edit.returnPressed.connect(self.start_requested.emit)
        controls.addWidget(self.query_edit, 1)

        self.extensions_edit = QLineEdit(self)
        self.extensions_edit.setMinimumHeight(34)
        self.extensions_edit.setPlaceholderText("py, txt, md")
        self.extensions_edit.setMaximumWidth(180)
        self.extensions_edit.setToolTip("Ограничить поиск расширениями через запятую")
        controls.addWidget(self.extensions_edit)

        self.content_checkbox = QCheckBox("Внутри файлов", self)
        self.content_checkbox.setToolTip("Искать совпадения внутри текстовых файлов")
        self.content_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        controls.addWidget(self.content_checkbox)

        find_button = QToolButton(self)
        find_button.setText("Найти")
        find_button.setMinimumHeight(32)
        find_button.setIcon(icons.icon("search"))
        find_button.setIconSize(QSize(18, 18))
        find_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        find_button.clicked.connect(self.start_requested.emit)
        make_interactive(find_button, "Запустить поиск")
        controls.addWidget(find_button)

        stop_button = QToolButton(self)
        stop_button.setText("Стоп")
        stop_button.setMinimumHeight(32)
        stop_button.setIcon(icons.icon("stop"))
        stop_button.setIconSize(QSize(18, 18))
        stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        stop_button.clicked.connect(self.stop_requested.emit)
        make_interactive(stop_button, "Остановить текущий поиск")
        controls.addWidget(stop_button)
        layout.addLayout(controls)

        self.results_table = SearchResultsTable(icons, self)
        self.results_table.open_requested.connect(self.open_result_requested.emit)
        layout.addWidget(TableCard(self.results_table, self), 1)

    def query(self) -> str:
        return self.query_edit.text().strip()

    def extensions(self) -> str:
        return self.extensions_edit.text().strip()

    def include_content(self) -> bool:
        return self.content_checkbox.isChecked()

    def focus_query(self) -> None:
        self.query_edit.setFocus()
        self.query_edit.selectAll()

    def clear_results(self) -> None:
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        self.results_table.setSortingEnabled(True)

    def add_result(self, result: SearchResult) -> None:
        self.results_table.add_result(result)

    def selected_path(self) -> Path | None:
        return self.results_table.selected_path()

    def result_count(self) -> int:
        return self.results_table.rowCount()

    def reset(self) -> None:
        self.query_edit.clear()
        self.extensions_edit.clear()
        self.content_checkbox.setChecked(False)
        self.clear_results()
