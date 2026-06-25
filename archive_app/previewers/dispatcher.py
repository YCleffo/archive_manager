from __future__ import annotations

import mimetypes
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize

from .audio_preview import build_audio_preview
from .common import (
    AUDIO_EXTENSIONS,
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    PREVIEW_MAX_SIZE,
    VIDEO_EXTENSIONS,
    PreviewResult,
    build_info_preview,
)
from .document_preview import build_document_preview
from .image_preview import build_image_preview
from .video_preview import build_video_preview


@lru_cache(maxsize=16)
def _cached_build_preview(
    path_str: str, mtime: float, width: int, height: int
) -> PreviewResult:
    path = Path(path_str)
    max_size = QSize(width, height)

    if path.is_dir():
        return build_info_preview(path, "Папка")

    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return build_image_preview(path, max_size)
    if suffix in VIDEO_EXTENSIONS:
        return build_video_preview(path, max_size)
    if suffix in DOCUMENT_EXTENSIONS:
        return build_document_preview(path, max_size)
    if suffix in AUDIO_EXTENSIONS:
        return build_audio_preview(path, max_size)

    mime, _ = mimetypes.guess_type(str(path))
    return build_info_preview(path, mime or "Файл")


def build_preview(path: Path, max_size: QSize = PREVIEW_MAX_SIZE) -> PreviewResult:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return PreviewResult(path, path.name, "Файл уже не существует.")

    mtime = path.stat().st_mtime
    return _cached_build_preview(str(path), mtime, max_size.width(), max_size.height())
