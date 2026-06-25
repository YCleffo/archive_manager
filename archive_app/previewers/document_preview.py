from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QFileInfo
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileIconProvider

from .common import PreviewResult, format_file_details


def build_document_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    image: QImage | None = None

    if path.suffix.lower() == ".pdf":
        try:
            import fitz  # type: ignore

            doc = fitz.open(str(path))  # type: ignore
            if doc.page_count > 0:  # type: ignore
                page = doc.load_page(0)  # type: ignore
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)  # type: ignore
                pix = page.get_pixmap(matrix=mat)  # type: ignore
                image = QImage(  # type: ignore
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
            doc.close()
        except Exception:
            pass

    if image is None:
        provider = QFileIconProvider()
        icon = provider.icon(QFileInfo(str(path)))
        if not icon.isNull():
            image = icon.pixmap(256, 256).toImage()

    if image is not None and (
        image.size().width() > max_size.width()
        or image.size().height() > max_size.height()
    ):
        image = image.scaled(
            max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    extra_text = "Превью: системная иконка файла." if image is not None else None
    if path.suffix.lower() == ".pdf" and image is not None:
        extra_text = "Превью: первая страница PDF."

    return PreviewResult(
        path=path,
        title=path.name,
        details=format_file_details(path, "Документ", stat.st_size, extra=extra_text),
        image=image,
        error="Превью недоступно." if image is None else None,
    )
