from __future__ import annotations

import importlib
import mimetypes
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, cast

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


@dataclass(frozen=True)
class PreviewResult:
    path: Path
    title: str
    details: str
    image: QImage | None = None
    error: str | None = None


def get_ffmpeg_path() -> str | None:
    """Возвращает путь к ffmpeg для превью видео.

    Порядок поиска:
    1. `tools/ffmpeg.exe` рядом с проектом или внутри PyInstaller-bundle.
    2. ffmpeg из зависимости `imageio-ffmpeg`.
    3. системный ffmpeg из PATH.

    В production-архиве `tools/ffmpeg.exe` можно не хранить: сборка берёт
    ffmpeg из `imageio-ffmpeg`, а при желании внешний бинарник можно положить
    в `tools/ffmpeg.exe` перед сборкой.
    """
    return _find_ffmpeg()


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=16)
def _cached_build_preview(
    path_str: str, mtime: float, width: int, height: int
) -> PreviewResult:
    path = Path(path_str)
    max_size = QSize(width, height)

    if path.is_dir():
        return _build_info_preview(path, "Папка")

    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return _build_image_preview(path, max_size)

    if suffix in VIDEO_EXTENSIONS:
        return _build_video_preview(path, max_size)

    mime, _ = mimetypes.guess_type(str(path))
    return _build_info_preview(path, mime or "Файл")


def build_preview(path: Path, max_size: QSize = PREVIEW_MAX_SIZE) -> PreviewResult:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return PreviewResult(path, path.name, "Файл уже не существует.")

    mtime = path.stat().st_mtime
    return _cached_build_preview(str(path), mtime, max_size.width(), max_size.height())


def _build_image_preview(path: Path, max_size: QSize) -> PreviewResult:
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
        pillow_result = _build_pillow_image_preview(
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


def _build_pillow_image_preview(
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
                details=_format_file_details(path, "HEIC-изображение", stat_size),
                error="HEIC прочитан, но миниатюра не создана.",
            )

        return PreviewResult(
            path=path,
            title=path.name,
            details=_format_file_details(
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
            details=_format_file_details(path, "HEIC-изображение", stat_size),
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
            details=_format_file_details(path, "HEIC-изображение", stat_size),
            error=error,
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


def _extract_video_frame(
    path: Path, max_size: QSize
) -> tuple[QImage | None, str | None]:
    ffmpeg = get_ffmpeg_path()
    if ffmpeg is None:
        return (
            None,
            (
                "Для превью видео нужен ffmpeg. Установи зависимости "
                "из requirements.txt или положи ffmpeg.exe в папку tools."
            ),
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
            last_error = (
                "ffmpeg вернул кадр, но приложение не смогло прочитать картинку."
            )
            continue

        if (
            image.size().width() > max_size.width()
            or image.size().height() > max_size.height()
        ):
            image = image.scaled(
                max_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return image, None

    return None, last_error


def _find_ffmpeg() -> str | None:
    executable_name = "ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg"
    bundled_ffmpeg = _bundle_root() / "tools" / executable_name

    if bundled_ffmpeg.exists():
        return str(bundled_ffmpeg)

    try:
        module = importlib.import_module("imageio_ffmpeg")
        getter = getattr(module, "get_ffmpeg_exe", None)
        if callable(getter):
            get_executable = cast(Callable[[], str], getter)
            executable = get_executable()
            if executable:
                return executable
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
