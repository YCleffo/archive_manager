from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from .common import HEIC_EXTENSIONS, PreviewResult, format_file_details


def build_image_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)

    original_size = reader.size()
    if original_size.isValid() and not original_size.isEmpty():
        scaled_size = original_size.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(scaled_size)
        dimensions = f"{original_size.width()} × {original_size.height()} px"
    else:
        dimensions = "не удалось определить заранее"

    image = reader.read()
    if image.isNull():
        pillow_result = build_pillow_image_preview(
            path=path,
            max_size=max_size,
            stat_size=stat.st_size,
            qt_error=reader.errorString(),
        )
        if pillow_result is not None:
            return pillow_result
        return PreviewResult(
            path=path,
            title=path.name,
            details=format_file_details(path, "Изображение", stat.st_size),
            error=reader.errorString() or "Не удалось загрузить изображение.",
        )

    return PreviewResult(
        path=path,
        title=path.name,
        details=format_file_details(
            path,
            "Изображение",
            stat.st_size,
            extra=f"Размер изображения: {dimensions}",
        ),
        image=image,
    )


def build_pillow_image_preview(
    path: Path,
    max_size: QSize,
    stat_size: int,
    qt_error: str | None = None,
) -> PreviewResult | None:
    suffix = path.suffix.lower()
    if suffix not in HEIC_EXTENSIONS:
        return None

    try:
        heif_module = importlib.import_module("pillow_heif")
        register_heif_opener = getattr(heif_module, "register_heif_opener", None)
        if callable(register_heif_opener):
            register_heif_opener()

        pillow_module = importlib.import_module("PIL.Image")
        open_image: Any = getattr(pillow_module, "open")
        resampling = getattr(pillow_module, "Resampling", None)
        lanczos = getattr(resampling, "LANCZOS", 1) if resampling is not None else 1

        with open_image(path) as pil_image:
            original_width, original_height = pil_image.size
            pil_image.thumbnail((max_size.width(), max_size.height()), lanczos)
            if pil_image.mode not in ("RGB", "RGBA"):
                pil_image = pil_image.convert("RGBA")

            if pil_image.mode == "RGB":
                q_format = QImage.Format.Format_RGB888
                bytes_per_line = pil_image.width * 3
            else:
                q_format = QImage.Format.Format_RGBA8888
                bytes_per_line = pil_image.width * 4

            data = pil_image.tobytes()
            q_image = QImage(
                data,
                pil_image.width,
                pil_image.height,
                bytes_per_line,
                q_format,
            ).copy()

        if q_image.isNull():
            return PreviewResult(
                path=path,
                title=path.name,
                details=format_file_details(path, "HEIC-изображение", stat_size),
                error="HEIC прочитан, но миниатюра не создана.",
            )

        return PreviewResult(
            path=path,
            title=path.name,
            details=format_file_details(
                path,
                "HEIC-изображение",
                stat_size,
                extra=f"Размер изображения: {original_width} × {original_height} px",
            ),
            image=q_image,
        )
    except ModuleNotFoundError:
        return PreviewResult(
            path=path,
            title=path.name,
            details=format_file_details(path, "HEIC-изображение", stat_size),
            error=(
                "Для HEIC-превью установи зависимости из requirements.txt: "
                "Pillow и pillow-heif."
            ),
        )
    except Exception as exc:
        error = f"Не удалось прочитать HEIC: {exc}"
        if qt_error:
            error += f"\nQt: {qt_error}"
        return PreviewResult(
            path=path,
            title=path.name,
            details=format_file_details(path, "HEIC-изображение", stat_size),
            error=error,
        )
