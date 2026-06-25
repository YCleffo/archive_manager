from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from send2trash import send2trash


def _is_same_or_inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents


def is_hidden_or_system(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        # FILE_ATTRIBUTE_HIDDEN = 2, FILE_ATTRIBUTE_SYSTEM = 4
        if attrs & (2 | 4):
            return True
    except OSError:
        pass
    return False


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
    units = ["Б", "КБ", "МБ", "ГБ", "ТБ"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "Б":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} Б"


def format_modified(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%d.%m.%Y %H:%M")


def list_directory(path: Path) -> list[FileEntry]:
    path = Path(path).expanduser().resolve()
    entries: list[FileEntry] = []
    for child in path.iterdir():
        if is_hidden_or_system(child):
            continue
        try:
            stat = child.stat()
            is_dir = child.is_dir()
            kind = (
                "Папка"
                if is_dir
                else child.suffix.lower().lstrip(".").upper() or "Файл"
            )
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

        if source.is_dir() and _is_same_or_inside(destination, source):
            raise ValueError(
                f"Нельзя скопировать или переместить папку внутрь самой себя: {source.name}"
            )

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

        if source.is_dir() and _is_same_or_inside(destination, source):
            raise ValueError(
                f"Нельзя скопировать или переместить папку внутрь самой себя: {source.name}"
            )

        target = ensure_unique_path(destination / source.name)
        shutil.move(str(source), str(target))
        moved.append(target)
    return moved


def delete_items(paths: Iterable[Path]) -> None:
    for path in paths:
        path = Path(path)
        if path.exists():
            send2trash(str(path))


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


def calculate_folder_size(path: Path | str) -> tuple[int, int]:
    total_size = 0
    total_files = 0

    def scan(p: str) -> None:
        nonlocal total_size, total_files
        try:
            with os.scandir(p) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat(follow_symlinks=False).st_size
                        total_files += 1
                    elif entry.is_dir(follow_symlinks=False):
                        scan(entry.path)
        except OSError:
            pass

    scan(str(path))
    return total_size, total_files
