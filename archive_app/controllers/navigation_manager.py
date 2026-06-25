from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal


class NavigationManager(QObject):
    """Управляет историей навигации."""

    # Сигнал испускается при запросе перехода по пути
    # Аргументы: path, add_history, clear_forward, scroll_to
    navigate_requested = Signal(Path, bool, bool, object)

    # Сигнал испускается при изменении состояния истории (доступность кнопок назад/вперёд)
    history_changed = Signal(bool, bool)  # can_go_back, can_go_forward

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.history: list[tuple[Path, int]] = []
        self.forward_history: list[tuple[Path, int]] = []
        self._current_path = Path.home().resolve()

    @property
    def current_path(self) -> Path:
        return self._current_path

    @current_path.setter
    def current_path(self, path: Path) -> None:
        self._current_path = path

    def commit_navigation(
        self,
        target_path: Path,
        current_scroll: int = 0,
        add_history: bool = True,
        clear_forward: bool = True,
    ) -> None:
        target_path = Path(target_path)
        if add_history and target_path != self._current_path:
            self.history.append((self._current_path, current_scroll))
            if clear_forward:
                self.forward_history.clear()
        self._current_path = target_path
        self._emit_history_changed()

    def push_history(
        self, path: Path, current_scroll: int, clear_forward: bool = True
    ) -> None:
        if path != self._current_path:
            self.history.append((self._current_path, current_scroll))
            if clear_forward:
                self.forward_history.clear()
            self._emit_history_changed()

    def go_back(self, current_scroll: int) -> None:
        if not self.history:
            return
        self.forward_history.append((self._current_path, current_scroll))
        previous_path, scroll = self.history.pop()
        self._emit_history_changed()
        self.navigate_requested.emit(previous_path, False, False, scroll)

    def go_forward(self, current_scroll: int) -> None:
        if not self.forward_history:
            return
        self.history.append((self._current_path, current_scroll))
        next_path, scroll = self.forward_history.pop()
        self._emit_history_changed()
        self.navigate_requested.emit(next_path, False, False, scroll)

    def go_up(self) -> None:
        parent = self._current_path.parent
        if parent != self._current_path:
            self.navigate_requested.emit(parent, True, True, None)

    def go_home(self) -> None:
        self.navigate_requested.emit(Path.home(), True, True, None)

    def clear(self) -> None:
        self.history.clear()
        self.forward_history.clear()
        self._emit_history_changed()

    def can_go_back(self) -> bool:
        return bool(self.history)

    def can_go_forward(self) -> bool:
        return bool(self.forward_history)

    def can_go_up(self) -> bool:
        return self._current_path.parent != self._current_path

    def _emit_history_changed(self) -> None:
        self.history_changed.emit(self.can_go_back(), self.can_go_forward())
