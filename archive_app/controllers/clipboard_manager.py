from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class ClipboardManager(QObject):
    """Управляет состоянием буфера обмена приложения."""

    clipboard_changed = Signal(int, bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._paths: list[Path] = []
        self._is_cut: bool = False

    @property
    def paths(self) -> list[Path]:
        return self._paths

    @property
    def is_cut(self) -> bool:
        return self._is_cut

    @property
    def has_items(self) -> bool:
        return len(self._paths) > 0

    def copy_items(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._paths = paths.copy()
        self._is_cut = False
        self.clipboard_changed.emit(len(self._paths), self._is_cut)

    def cut_items(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._paths = paths.copy()
        self._is_cut = True
        self.clipboard_changed.emit(len(self._paths), self._is_cut)

    def clear(self) -> None:
        if not self._paths:
            return
        self._paths = []
        self._is_cut = False
        self.clipboard_changed.emit(0, False)

    def get_status_text(self) -> str:
        count = len(self._paths)
        if count == 0:
            return "Буфер пуст"
        mode = "вырезано" if self._is_cut else "скопировано"
        return f"В буфере: {mode} {count} | можно вставить: {count}"
