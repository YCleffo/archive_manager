from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from archive_app.archive_utils import create_zip_archive, extract_archive
from archive_app.file_utils import (
    calculate_folder_size,
    copy_items,
    create_folder,
    delete_items,
    move_items,
    rename_item,
)


class FileOperationsController(QObject):
    """Управляет файловыми операциями (создание, удаление, копирование, архивация)."""

    status_requested = Signal(str)
    refresh_requested = Signal()
    error_occurred = Signal(str, str)

    operation_requested = Signal(object, str, object)

    undo_added = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def create_folder(self, parent_path: Path, name: str) -> None:
        try:
            created = create_folder(parent_path, name)

            def make_undo(created_path: Path) -> Callable[[], None]:
                def undo() -> None:
                    delete_items([created_path])

                return undo

            self.undo_added.emit(f"создание папки {created.name}", make_undo(created))
            self.refresh_requested.emit()
            self.status_requested.emit(f"Создана папка: {created.name}")
        except Exception as exc:
            self.error_occurred.emit("Ошибка создания папки", str(exc))

    def rename_item(self, path: Path, new_name: str) -> None:
        try:
            renamed = rename_item(path, new_name)

            def make_undo(source: Path, target: Path) -> Callable[[], None]:
                def undo() -> None:
                    source.rename(target)

                return undo

            self.undo_added.emit(
                f"переименование {renamed.name}", make_undo(renamed, path)
            )
            self.refresh_requested.emit()
            self.status_requested.emit(f"Переименовано: {renamed.name}")
        except Exception as exc:
            self.error_occurred.emit("Ошибка переименования", str(exc))

    def delete_items(self, paths: list[Path]) -> None:
        try:
            delete_items(paths)
            self.refresh_requested.emit()
            self.status_requested.emit(f"Перемещено в корзину: {len(paths)}")
        except Exception as exc:
            self.error_occurred.emit("Ошибка удаления", str(exc))

    def paste_items(self, paths: list[Path], is_cut: bool, dest: Path) -> None:
        if not paths:
            return

        def task(status: Callable[[str], None]) -> int:
            if is_cut:
                status("Перемещение...")
                moved = move_items(paths, dest)
                return len(moved)
            else:
                status("Копирование...")
                copied = copy_items(paths, dest)
                return len(copied)

        self.operation_requested.emit(
            task,
            "Ошибка вставки",
            lambda count: self._paste_finished(int(count), is_cut),  # type: ignore
        )

    def _paste_finished(self, count: int, is_cut: bool) -> None:
        self.refresh_requested.emit()
        if is_cut:
            self.status_requested.emit(f"Перемещено объектов: {count}")
        else:
            self.status_requested.emit(f"Скопировано объектов: {count}")

    def create_zip(self, paths: list[Path], output_path: Path) -> None:
        def task(status: Callable[[str], None]) -> Path:
            status("Создание архива...")
            return create_zip_archive(
                output_path,
                paths,
                progress=lambda name: status(f"Архивирую: {Path(name).name}"),
            )

        self.operation_requested.emit(task, "Ошибка создания архива", self._zip_created)

    def _zip_created(self, created: Path) -> None:
        def make_undo(created_path: Path) -> Callable[[], None]:
            def undo() -> None:
                delete_items([created_path])

            return undo

        self.undo_added.emit(f"создание архива {created.name}", make_undo(created))
        self.refresh_requested.emit()
        self.status_requested.emit(f"Архив создан: {created.name}")

    def extract_archive(self, path: Path, destination_path: Path) -> None:
        def task(status: Callable[[str], None]) -> tuple[Path, Path]:
            status("Распаковка архива...")
            extract_archive(
                path,
                destination_path,
                progress=lambda name: status(f"Распаковываю: {name}"),
            )
            return path, destination_path

        self.operation_requested.emit(
            task,
            "Ошибка распаковки",
            lambda result: self._archive_extracted(result[0], result[1]),  # type: ignore
        )

    def _archive_extracted(self, archive_path: Path, destination: Path) -> None:
        self.refresh_requested.emit()
        self.status_requested.emit(f"Распаковано: {archive_path.name}")

    def calculate_size(self, path: Path) -> None:
        def task(status: Callable[[str], None]) -> tuple[Path, int, int]:
            status(f"Вычисление размера: {path.name}...")
            total_size, total_files = calculate_folder_size(path)
            return path, total_size, total_files

        self.operation_requested.emit(
            task,
            "Ошибка подсчёта размера",
            lambda result: self._size_calculated(result[0], result[1], result[2]),  # type: ignore
        )

    size_calculated = Signal(Path, int, int)

    def _size_calculated(self, path: Path, total_size: int, total_files: int) -> None:
        self.size_calculated.emit(path, total_size, total_files)
