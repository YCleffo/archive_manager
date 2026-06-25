from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FileEntry:
    path: Path
    name: str
    kind: str
    size: int | None
    modified: datetime | None
    is_dir: bool


def format_size(size: int | None) -> str:
    if size is None:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def format_modified(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def list_directory(path: Path) -> list[FileEntry]:
    path = Path(path).expanduser().resolve()
    entries: list[FileEntry] = []
    for child in path.iterdir():
        try:
            stat = child.stat()
            is_dir = child.is_dir()
            kind = "Папка" if is_dir else child.suffix.lower().lstrip(".").upper() or "Файл"
            size = None if is_dir else stat.st_size
            modified = datetime.fromtimestamp(stat.st_mtime)
            entries.append(
                FileEntry(
                    path=child,
                    name=child.name,
                    kind=kind,
                    size=size,
                    modified=modified,
                    is_dir=is_dir,
                )
            )
        except PermissionError:
            entries.append(
                FileEntry(
                    path=child,
                    name=child.name,
                    kind="Нет доступа",
                    size=None,
                    modified=None,
                    is_dir=False,
                )
            )
        except FileNotFoundError:
            continue

    entries.sort(key=lambda item: (not item.is_dir, item.name.casefold()))
    return entries


def open_in_system(path: Path) -> None:
    path = Path(path)
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def ensure_unique_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def copy_items(paths: Iterable[Path], destination: Path) -> list[Path]:
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in paths:
        source = Path(source).resolve()
        target = ensure_unique_path(destination / source.name)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        copied.append(target)
    return copied


def move_items(paths: Iterable[Path], destination: Path) -> list[Path]:
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for source in paths:
        source = Path(source).resolve()
        target = ensure_unique_path(destination / source.name)
        shutil.move(str(source), str(target))
        moved.append(target)
    return moved


def delete_items(paths: Iterable[Path]) -> None:
    for path in paths:
        path = Path(path)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def rename_item(path: Path, new_name: str) -> Path:
    path = Path(path)
    clean_name = new_name.strip()
    if not clean_name:
        raise ValueError("Новое имя не может быть пустым")
    if any(sep in clean_name for sep in ("/", "\\")):
        raise ValueError("Новое имя не должно содержать / или \\")
    target = path.with_name(clean_name)
    if target.exists():
        raise FileExistsError(f"Уже существует: {target.name}")
    return path.rename(target)


def create_folder(parent: Path, name: str) -> Path:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Имя папки не может быть пустым")
    if any(sep in clean_name for sep in ("/", "\\")):
        raise ValueError("Имя папки не должно содержать / или \\")
    target = Path(parent) / clean_name
    target.mkdir(parents=False, exist_ok=False)
    return target
