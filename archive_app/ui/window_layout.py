from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .action_bar import ActionBar
from .file_table import FileTable, TableCard
from .icons import IconFactory
from .navigation_bar import PathBar
from .preview_panel import PreviewPanel
from .search_panel import SearchPanel


@dataclass(frozen=True)
class MainWindowWidgets:
    action_bar: ActionBar
    path_bar: PathBar
    file_table: FileTable
    file_table_card: TableCard
    preview_panel: PreviewPanel
    content_splitter: QSplitter
    search_panel: SearchPanel
    main_stack: QStackedWidget
    status_label: QLabel


class WindowLayoutBuilder:
    """Создаёт виджеты главного окна без бизнес-логики и файловых операций."""

    def __init__(
        self,
        window: QMainWindow,
        actions: dict[str, QAction],
        icons: IconFactory,
    ) -> None:
        self.window = window
        self.actions = actions
        self.icons = icons

    def build(self) -> MainWindowWidgets:
        central = QWidget(self.window)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(12)

        action_bar = ActionBar(self.actions, self.icons, central)
        layout.addWidget(action_bar)

        path_bar = PathBar(self.icons, central)
        layout.addWidget(path_bar)

        file_table = FileTable(self.icons, central)
        file_table_card = TableCard(file_table, central)
        preview_panel = PreviewPanel(central)

        content_splitter = QSplitter(Qt.Orientation.Horizontal, central)
        content_splitter.setObjectName("ContentSplitter")
        content_splitter.setHandleWidth(8)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.addWidget(file_table_card)
        content_splitter.addWidget(preview_panel)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 0)
        content_splitter.setSizes([920, 340])

        search_panel = SearchPanel(self.icons, central)
        main_stack = QStackedWidget(central)
        main_stack.addWidget(content_splitter)
        main_stack.addWidget(search_panel)
        layout.addWidget(main_stack, 1)

        self.window.setCentralWidget(central)

        status_label = QLabel(self.window)
        status_label.setStyleSheet("color: #4b5563; font-size: 13px;")
        self.window.statusBar().addWidget(status_label)

        return MainWindowWidgets(
            action_bar=action_bar,
            path_bar=path_bar,
            file_table=file_table,
            file_table_card=file_table_card,
            preview_panel=preview_panel,
            content_splitter=content_splitter,
            search_panel=search_panel,
            main_stack=main_stack,
            status_label=status_label,
        )
