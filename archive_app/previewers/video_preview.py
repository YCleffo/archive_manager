from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage

from .common import PREVIEW_TIMEOUT_SECONDS, PreviewResult, format_file_details


def get_ffmpeg_path() -> str | None:
    """Возвращает путь к ffmpeg для превью видео."""
    return _find_ffmpeg()


def build_video_preview(path: Path, max_size: QSize) -> PreviewResult:
    stat = path.stat()
    image, error = extract_video_frame(path, max_size)
    details = format_file_details(
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


def extract_video_frame(
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

        image = QImage.fromData(completed.stdout)
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


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


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
