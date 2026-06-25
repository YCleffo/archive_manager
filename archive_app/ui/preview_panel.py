from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..preview_utils import PreviewResult
from .theme import make_interactive


class PreviewPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PreviewPanel")
        self.setMinimumWidth(320)
        self.setMaximumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Превью", self)
        title.setObjectName("PreviewPanelTitle")
        layout.addWidget(title)

        self.image_label = QLabel(self)
        self.image_label.setObjectName("PreviewImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(240)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.image_label.setText("Выберите файл одним кликом")
        self.image_label.setWordWrap(True)
        layout.addWidget(self.image_label)

        self.name_label = QLabel("Ничего не выбрано", self)
        self.name_label.setObjectName("PreviewName")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        self.details_label = QLabel(
            "Один клик показывает миниатюру.\nДвойной клик открывает файл в стандартной программе.",
            self,
        )
        self.details_label.setObjectName("PreviewDetails")
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.details_label)

        self.open_button = QPushButton("Открыть в стандартной программе", self)
        self.open_button.setObjectName("PreviewOpenButton")
        make_interactive(self.open_button, "Открыть выбранный файл системной программой")
        self.open_button.setEnabled(False)
        layout.addWidget(self.open_button)

        layout.addStretch(1)

    def set_empty(self, message: str = "Выберите файл одним кликом") -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(message)
        self.name_label.setText("Ничего не выбрано")
        self.details_label.setText(
            "Один клик показывает миниатюру.\nДвойной клик открывает файл в стандартной программе."
        )
        self.open_button.setEnabled(False)

    def set_loading(self, name: str) -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Загрузка превью…")
        self.name_label.setText(name)
        self.details_label.setText("Читаю миниатюру в фоне, интерфейс не зависнет.")
        self.open_button.setEnabled(True)

    def set_multiple(self, selected_count: int, files: int, folders: int) -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Выбрано несколько объектов")
        self.name_label.setText(f"Выбрано: {selected_count}")
        self.details_label.setText(f"Файлов: {files}\nПапок: {folders}")
        self.open_button.setEnabled(False)

    def set_result(self, result: PreviewResult) -> None:
        self.name_label.setText(result.title)
        details = result.details
        if result.error:
            details += f"\n\nПревью: {result.error}"
        self.details_label.setText(details)

        if result.image is not None and not result.image.isNull():
            pixmap = QPixmap.fromImage(result.image)
            self.image_label.setText("")
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Миниатюра недоступна")
        self.open_button.setEnabled(result.path.exists() and result.path.is_file())
