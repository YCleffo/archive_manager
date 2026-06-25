from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from archive_app.file_utils import format_size

PREVIEW_MAX_SIZE = QSize(360, 240)
PREVIEW_TIMEOUT_SECONDS = 15

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".jpe",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".ico",
    ".heic",
    ".heif",
    ".hif",
}

HEIC_EXTENSIONS = {".heic", ".heif", ".hif"}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".m4v",
    ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".webm",
    ".mpeg",
    ".mpg",
    ".3gp",
    ".flv",
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
    ".djvu",
    ".epub",
    ".fb2",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".m4a",
    ".wav",
    ".ogg",
    ".aac",
    ".wma",
    ".alac",
    ".aiff",
}


@dataclass(frozen=True)
class PreviewResult:
    path: Path
    title: str
    details: str
    image: QImage | None = None
    error: str | None = None


def build_info_preview(path: Path, kind: str) -> PreviewResult:
    try:
        stat = path.stat()
        details = format_file_details(path, kind, stat.st_size)
    except OSError as exc:
        details = f"{kind}\nПуть: {path}\nОшибка доступа: {exc}"
    return PreviewResult(path=path, title=path.name, details=details)


def format_file_details(
    path: Path,
    kind: str,
    size: int,
    extra: str | None = None,
) -> str:
    mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%d.%m.%Y %H:%M:%S")
    parts: list[str] = [
        f"Тип: {kind}",
        f"Размер: {format_size(size)}",
        f"Изменён: {mtime}",
        f"Путь: {path}",
    ]
    if extra:
        parts.insert(1, extra)
    return "\n".join(parts)
