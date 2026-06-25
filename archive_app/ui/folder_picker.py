from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import IconFactory
from .tables import FileTable
from .theme import make_interactive


class FolderPickerDialog(QDialog):
    def __init__(
        self, start_path: Path, icons: IconFactory, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.icons = icons
        self.selected_path = Path(start_path).expanduser().resolve()
        self.setWindowTitle("Выберите папку")
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.up_button = QPushButton("Вверх", self)
        self.up_button.setIcon(icons.icon("up"))
        make_interactive(self.up_button, "На уровень вверх")
        self.up_button.clicked.connect(self._go_up)
        top_layout.addWidget(self.up_button)

        self.home_button = QPushButton("Домой", self)
        self.home_button.setIcon(icons.icon("home"))
        make_interactive(self.home_button, "Домашняя директория")
        self.home_button.clicked.connect(self._go_home)
        top_layout.addWidget(self.home_button)

        self.path_label = QLabel(str(self.selected_path), self)
        self.path_label.setStyleSheet("font-weight: bold; color: #1d2733;")
        top_layout.addWidget(self.path_label, 1)

        layout.addLayout(top_layout)

        self.table = FileTable(self.icons, self)
        self.table.open_requested.connect(self._on_table_open_requested)
        self.table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch(1)

        self.cancel_button = QPushButton("Отмена", self)
        make_interactive(self.cancel_button, "Отменить выбор")
        self.cancel_button.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_button)

        self.select_button = QPushButton("Выбрать эту папку", self)
        self.select_button.setStyleSheet(
            "background: #0078d4; color: white; border-color: #0078d4;"
        )
        make_interactive(self.select_button, "Выбрать текущую директорию")
        self.select_button.clicked.connect(self.accept)
        bottom_layout.addWidget(self.select_button)

        layout.addLayout(bottom_layout)

        self.load_directory(self.selected_path)

    def _go_up(self) -> None:
        parent_dir = self.selected_path.parent
        if parent_dir != self.selected_path:
            self.load_directory(parent_dir)

    def _go_home(self) -> None:
        self.load_directory(Path.home())

    def _on_table_open_requested(self) -> None:
        paths = self.table.selected_paths()
        if not paths:
            return
        path = paths[0]
        if path.is_dir():
            self.load_directory(path)

    def _on_selection_changed(self) -> None:
        paths = self.table.selected_paths()
        if paths and paths[0].is_dir():
            self.select_button.setText("Выбрать выбранную папку")
        else:
            self.select_button.setText("Выбрать текущую папку")

    def load_directory(self, path: Path) -> None:
        try:
            path = path.resolve()
            if not path.is_dir():
                return

            from archive_app.file_utils import FileEntry, is_hidden_or_system

            entries: list[FileEntry] = []

            with os.scandir(path) as it:
                for entry in it:
                    path_obj = Path(entry.path)
                    if is_hidden_or_system(path_obj):
                        continue
                    try:
                        stat = entry.stat()
                        from datetime import datetime

                        entries.append(
                            FileEntry(
                                path=path_obj,
                                name=entry.name,
                                kind="Папка" if entry.is_dir() else "Файл",
                                is_dir=entry.is_dir(),
                                size=stat.st_size if not entry.is_dir() else 0,
                                modified=datetime.fromtimestamp(stat.st_mtime),
                            )
                        )
                    except OSError:
                        continue

            self.table.set_entries(entries)
            self.selected_path = path
            self.path_label.setText(str(path))
            self.select_button.setText("Выбрать текущую папку")
        except OSError as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть директорию:\n{e}")

    def get_result_path(self) -> Path:
        paths = self.table.selected_paths()
        if paths and paths[0].is_dir():
            return paths[0]
        return self.selected_path
