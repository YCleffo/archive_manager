from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from ..search_utils import SearchResult


class OperationSignals(QObject):
    status = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class OperationWorker(QRunnable):
    def __init__(self, callback: Callable[[Callable[[str], None]], Any]) -> None:
        super().__init__()
        self.callback = callback
        self.signals = OperationSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.callback(self.signals.status.emit)
            self.signals.result.emit(result)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class SearchSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal(bool)


class SearchWorker(QRunnable):
    def __init__(
        self,
        search_function: Callable[..., Generator[SearchResult, None, None]],
        root: Path,
        query: str,
        extensions_raw: str,
        include_content: bool,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self.search_function = search_function
        self.root = root
        self.query = query
        self.extensions_raw = extensions_raw
        self.include_content = include_content
        self.cancel_event = cancel_event
        self.signals = SearchSignals()

    @Slot()
    def run(self) -> None:
        try:
            for result in self.search_function(
                self.root,
                query=self.query,
                extensions_raw=self.extensions_raw,
                include_content=self.include_content,
                cancel_event=self.cancel_event,
            ):
                self.signals.result.emit(result)
            self.signals.finished.emit(self.cancel_event.is_set())
        except Exception as exc:
            self.signals.error.emit(str(exc))
