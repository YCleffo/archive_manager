from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QResizeEvent, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPlainTextEdit,
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
        self.setMinimumWidth(260)
        self.setMaximumWidth(480)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._current_image: QImage | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Превью", self)
        title.setObjectName("PreviewPanelTitle")
        layout.addWidget(title)

        self.image_label = QLabel(self)
        self.image_label.setObjectName("PreviewImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(220)
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

        self.details_text = QPlainTextEdit(self)
        self.details_text.setObjectName("PreviewDetailsText")
        self.details_text.setReadOnly(True)
        self.details_text.setFrameShape(QFrame.Shape.NoFrame)
        self.details_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.details_text.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.details_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.details_text.setMinimumHeight(150)
        self.details_text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.details_text.setPlainText(
            "Один клик показывает миниатюру.\n"
            "Двойной клик открывает файл в стандартной программе."
        )
        layout.addWidget(self.details_text, 1)

        self.open_button = QPushButton("Открыть в стандартной программе", self)
        self.open_button.setObjectName("PreviewOpenButton")
        make_interactive(self.open_button, "Открыть выбранный файл системной программой")
        self.open_button.setEnabled(False)
        layout.addWidget(self.open_button)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_image_pixmap()

    def set_empty(self, message: str = "Выберите файл одним кликом") -> None:
        self._current_image = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(message)
        self.name_label.setText("Ничего не выбрано")
        self.details_text.setPlainText(
            "Один клик показывает миниатюру.\n"
            "Двойной клик открывает файл в стандартной программе."
        )
        self.open_button.setEnabled(False)

    def set_loading(self, name: str) -> None:
        self._current_image = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Загрузка превью…")
        self.name_label.setText(name)
        self.details_text.setPlainText("Читаю миниатюру в фоне, интерфейс не зависнет.")
        self.open_button.setEnabled(True)

    def set_multiple(self, selected_count: int, files: int, folders: int) -> None:
        self._current_image = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("Выбрано несколько объектов")
        self.name_label.setText(f"Выбрано: {selected_count}")
        self.details_text.setPlainText(f"Файлов: {files}\nПапок: {folders}")
        self.open_button.setEnabled(False)

    def set_result(self, result: PreviewResult) -> None:
        self.name_label.setText(result.title)
        details = result.details
        if result.error:
            details += f"\n\nПревью: {result.error}"
        self.details_text.setPlainText(details)

        self._current_image = result.image if result.image is not None and not result.image.isNull() else None
        if self._current_image is not None:
            self.image_label.setText("")
            self._update_image_pixmap()
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Миниатюра недоступна")
        self.open_button.setEnabled(result.path.exists() and result.path.is_file())

    def _update_image_pixmap(self) -> None:
        if self._current_image is None or self._current_image.isNull():
            return

        target_size = self.image_label.contentsRect().size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        pixmap = QPixmap.fromImage(self._current_image)
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
