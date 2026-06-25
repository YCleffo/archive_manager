from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .theme import make_interactive

TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".json", ".csv", ".html", ".css", ".js", 
    ".ts", ".xml", ".yml", ".yaml", ".ini", ".log", ".sql", ".sh", 
    ".bat", ".ps1"
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"
}

MAX_TEXT_READ_SIZE = 5 * 1024 * 1024  # 5 MB

class PreviewDialog(QDialog):
    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = Path(path).resolve()
        self.setWindowTitle(f"Просмотр - {self.path.name}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        try:
            widget = self._create_preview_widget()
            layout.addWidget(widget, 1)
        except Exception as e:
            error_label = QLabel(f"Ошибка чтения файла:\n{e}")
            error_label.setStyleSheet("color: #d32f2f;")
            layout.addWidget(error_label, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        close_btn.setText("Закрыть")
        make_interactive(close_btn, "Закрыть окно просмотра")
        layout.addWidget(buttons)

    def _create_preview_widget(self) -> QWidget:
        suffix = self.path.suffix.lower()

        if suffix in TEXT_EXTENSIONS:
            return self._create_text_preview()
        
        if suffix in IMAGE_EXTENSIONS:
            return self._create_image_preview()
        
        return self._create_fallback_preview()

    def _create_text_preview(self) -> QWidget:
        stat = self.path.stat()
        if stat.st_size > MAX_TEXT_READ_SIZE:
            return QLabel(f"Файл слишком велик для текстового просмотра ({stat.st_size} байт).\nОграничение: {MAX_TEXT_READ_SIZE} байт.")

        editor = QPlainTextEdit(self)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        try:
            text = self.path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = self.path.read_text(encoding="windows-1251")
            except UnicodeDecodeError:
                text = "Ошибка кодировки: Не удалось прочитать файл как текст (UTF-8 или Windows-1251)."
        
        editor.setPlainText(text)
        return editor

    def _create_image_preview(self) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        label = QLabel(scroll)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = QPixmap(str(self.path))
        if pixmap.isNull():
            return QLabel("Ошибка загрузки изображения.")

        # Scale down if too large, but allow viewing actual size if smaller than window
        # For simplicity, let's make it scale to fit by default.
        label.setPixmap(pixmap)
        label.setScaledContents(False)
        
        def resize_event(event: QResizeEvent) -> None:
            if not pixmap.isNull():
                size = scroll.viewport().size()
                if pixmap.width() > size.width() or pixmap.height() > size.height():
                    label.setPixmap(pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    label.setPixmap(pixmap)
            QLabel.resizeEvent(label, event)
            
        label.resizeEvent = resize_event

        scroll.setWidget(label)
        return scroll

    def _create_fallback_preview(self) -> QWidget:
        stat = self.path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        mime, _ = mimetypes.guess_type(str(self.path))
        
        info = (
            f"Имя: {self.path.name}\n"
            f"Тип: {mime or 'Неизвестный'}\n"
            f"Размер: {stat.st_size} байт\n"
            f"Изменён: {mtime}\n"
            f"Путь: {self.path}\n\n"
            "Внутренний просмотр для данного формата не поддерживается."
        )
        
        label = QLabel(info)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 14px; color: #1d2733;")
        return label
