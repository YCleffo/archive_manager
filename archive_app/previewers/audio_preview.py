from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage

from .common import PreviewResult, format_file_details


def build_audio_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    image: QImage | None = None

    try:
        import mutagen  # type: ignore

        audio_file = mutagen.File(str(path))  # type: ignore
        cover_data: bytes | None = None

        if audio_file is not None and hasattr(audio_file, "tags") and audio_file.tags is not None:  # type: ignore
            tags = audio_file.tags  # type: ignore
            for key in tags.keys():  # type: ignore
                key_str = str(cast(Any, key))
                if key_str.startswith("APIC"):
                    cover_data = tags[key].data  # type: ignore
                    break

            if cover_data is None and hasattr(tags, "pictures") and tags.pictures:  # type: ignore
                cover_data = tags.pictures[0].data  # type: ignore

            if cover_data is None and "covr" in tags:  # type: ignore
                covrs = tags["covr"]  # type: ignore
                if covrs:
                    cover_data = bytes(cast(Any, covrs[0]))

        if cover_data:
            from PySide6.QtCore import QByteArray

            image = QImage.fromData(QByteArray(cover_data))  # type: ignore
    except Exception:
        pass

    if image is not None and (
        image.size().width() > max_size.width()
        or image.size().height() > max_size.height()
    ):
        image = image.scaled(
            max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    mime, _ = mimetypes.guess_type(str(path))
    return PreviewResult(
        path=path,
        title=path.name,
        details=format_file_details(
            path,
            mime or "Аудиофайл",
            stat.st_size,
            extra="Превью: обложка альбома." if image is not None else None,
        ),
        image=image,
        error="Миниатюра недоступна (нет обложки)." if image is None else None,
    )
