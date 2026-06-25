from __future__ import annotations

import importlib
import mimetypes
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from .file_utils import format_size

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
}

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


@dataclass(frozen=True)
class PreviewResult:
    path: Path
    title: str
    details: str
    image: QImage | None = None
    error: str | None = None


def build_preview(path: Path, max_size: QSize = PREVIEW_MAX_SIZE) -> PreviewResult:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return PreviewResult(path, path.name, "Файл уже не существует.")

    if path.is_dir():
        return _build_info_preview(path, "Папка")

    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return _build_image_preview(path, max_size)

    if suffix in VIDEO_EXTENSIONS:
        return _build_video_preview(path, max_size)

    mime, _ = mimetypes.guess_type(str(path))
    return _build_info_preview(path, mime or "Файл")


def _build_image_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)

    original_size = reader.size()
    if original_size.isValid() and not original_size.isEmpty():
        scaled_size = original_size.scaled(
            max_size, Qt.AspectRatioMode.KeepAspectRatio
        )
        reader.setScaledSize(scaled_size)
        dimensions = f"{original_size.width()} × {original_size.height()} px"
    else:
        dimensions = "не удалось определить заранее"

    image = reader.read()
    if image.isNull():
        return PreviewResult(
            path=path,
            title=path.name,
            details=_format_file_details(path, "Изображение", stat.st_size),
            error=reader.errorString() or "Не удалось загрузить изображение.",
        )

    return PreviewResult(
        path=path,
        title=path.name,
        details=_format_file_details(
            path,
            "Изображение",
            stat.st_size,
            extra=f"Размер изображения: {dimensions}",
        ),
        image=image,
    )


def _build_video_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    image, error = _extract_video_frame(path, max_size)
    details = _format_file_details(
        path,
        "Видео",
        stat.st_size,
        extra="Превью: первый доступный кадр без запуска проигрывателя.",
    )
    return PreviewResult(
        path=path,
        title=path.name,
        details=details,
        image=image,
        error=error,
    )


def _build_info_preview(path: Path, kind: str) -> PreviewResult:
    try:
        stat = path.stat()
        details = _format_file_details(path, kind, stat.st_size)
    except OSError as exc:
        details = f"{kind}\nПуть: {path}\nОшибка доступа: {exc}"
    return PreviewResult(path=path, title=path.name, details=details)


def _extract_video_frame(path: Path, max_size: QSize) -> tuple[QImage | None, str | None]:
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        return (
            None,
            "Для превью видео нужен ffmpeg. Он ставится через зависимость imageio-ffmpeg из requirements.txt.",
        )

    width = max(120, max_size.width())
    attempts = ("00:00:01", "00:00:00")
    last_error = "Не удалось получить кадр из видео."

    for timestamp in attempts:
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            timestamp,
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:-2",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=PREVIEW_TIMEOUT_SECONDS,
                creationflags=_subprocess_creation_flags(),
            )
        except subprocess.TimeoutExpired:
            last_error = "Видео слишком долго отдаёт кадр для превью."
            continue
        except OSError as exc:
            return None, f"Не удалось запустить ffmpeg: {exc}"

        if completed.returncode != 0 or not completed.stdout:
            message = completed.stderr.decode("utf-8", errors="ignore").strip()
            last_error = message or last_error
            continue

        image = QImage.fromData(completed.stdout, b"PNG")
        if image.isNull():
            last_error = "ffmpeg вернул кадр, но приложение не смогло прочитать картинку."
            continue

        if image.size().width() > max_size.width() or image.size().height() > max_size.height():
            image = image.scaled(
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return image, None

    return None, last_error


def _find_ffmpeg() -> str | None:
    try:
        module = importlib.import_module("imageio_ffmpeg")
        getter = getattr(module, "get_ffmpeg_exe", None)
        if callable(getter):
            executable = getter()
            if executable:
                return str(executable)
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _subprocess_creation_flags() -> int:
    if sys.platform.startswith("win"):
        return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return 0


def _format_file_details(
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
