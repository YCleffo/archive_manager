from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable

ProgressCallback = Callable[[str], Any]


SUPPORTED_ARCHIVES = (".zip", ".tar", ".gz", ".tgz", ".bz2")


def _common_parent(paths: list[Path]) -> Path:
    if len(paths) == 1:
        return paths[0].parent
    return Path(
        os.path.commonpath(
            [str(path.parent if path.is_file() else path.parent) for path in paths]
        )
    )


def create_zip_archive(
    output_zip: Path,
    input_paths: Iterable[Path],
    progress: ProgressCallback | None = None,
) -> Path:
    output_zip = Path(output_zip).expanduser().resolve()
    paths = [Path(path).expanduser().resolve() for path in input_paths]
    if not paths:
        raise ValueError("Не выбраны файлы или папки для архивации")

    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Не найдены: " + ", ".join(missing))

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    common_parent = _common_parent(paths)

    with zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for source in paths:
            if source.is_dir():
                # Empty folders are stored too, otherwise they disappear from ZIP.
                has_any = False
                for item in source.rglob("*"):
                    has_any = True
                    arcname = item.relative_to(common_parent)
                    if item.is_dir():
                        archive.writestr(str(arcname).replace("\\", "/") + "/", "")
                    elif item.is_file():
                        if progress:
                            progress(str(item))
                        archive.write(item, arcname)
                if not has_any:
                    arcname = source.relative_to(common_parent)
                    archive.writestr(str(arcname).replace("\\", "/") + "/", "")
            else:
                if progress:
                    progress(str(source))
                archive.write(source, source.relative_to(common_parent))

    return output_zip


def is_supported_archive(path: Path) -> bool:
    name = Path(path).name.lower()
    return name.endswith((".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2"))


def _safe_target(destination: Path, member_name: str) -> Path:
    destination = destination.resolve()
    target = (destination / member_name).resolve()
    try:
        target.relative_to(destination)
    except ValueError as exc:
        raise ValueError(f"Небезопасный путь в архиве: {member_name}") from exc
    return target


def extract_archive(
    archive_path: Path,
    destination: Path,
    progress: ProgressCallback | None = None,
) -> Path:
    archive_path = Path(archive_path).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    if not archive_path.exists():
        raise FileNotFoundError(f"Архив не найден: {archive_path}")

    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                _safe_target(destination, member.filename)
                if progress:
                    progress(member.filename)
                archive.extract(member, destination)
        return destination

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            for member in members:
                _safe_target(destination, member.name)
                if progress:
                    progress(member.name)
            archive.extractall(destination, members=members)
        return destination

    raise ValueError("Поддерживаются только .zip, .tar, .tar.gz, .tgz, .tar.bz2")


def list_archive_members(archive_path: Path) -> list[str]:
    archive_path = Path(archive_path).expanduser().resolve()
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path, "r") as archive:
            return archive.namelist()
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as archive:
            return archive.getnames()
    raise ValueError("Неизвестный тип архива")
