from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable

ProgressCallback = Callable[[str], Any]

SUPPORTED_ARCHIVES = (".zip", ".tar", ".gz", ".tgz", ".bz2")

MAX_EXTRACT_FILES = 50_000
MAX_EXTRACT_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
MAX_COMPRESSION_RATIO = 1000

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

    # Prevent archiving into itself
    for path in paths:
        try:
            if path == output_zip or output_zip.is_relative_to(path):
                raise ValueError(f"Нельзя сохранить архив внутрь архивируемой папки: {path.name}")
        except AttributeError:
            # Fallback for older python without is_relative_to
            try:
                output_zip.relative_to(path)
                raise ValueError(f"Нельзя сохранить архив внутрь архивируемой папки: {path.name}")
            except ValueError:
                pass

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    common_parent = _common_parent(paths)

    with zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for source in paths:
            if source.is_dir():
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
    member_name_clean = member_name.lstrip("/").lstrip("\\")
    if ".." in member_name_clean:
        raise ValueError(f"Опасный путь '..' в архиве: {member_name}")
    target = (destination / member_name_clean).resolve()
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
        total_size = 0
        file_count = 0
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                file_count += 1
                if file_count > MAX_EXTRACT_FILES:
                    raise ValueError("Превышен лимит количества файлов в архиве (Zip Bomb)")
                total_size += member.file_size
                if total_size > MAX_EXTRACT_SIZE:
                    raise ValueError("Превышен лимит распакованного размера (Zip Bomb)")
                if member.compress_size > 0 and (member.file_size / member.compress_size) > MAX_COMPRESSION_RATIO:
                    raise ValueError(f"Подозрительный уровень сжатия у файла: {member.filename} (Zip Bomb)")

                target = _safe_target(destination, member.filename)
                
                # Check for overwriting
                if target.exists() and target.is_dir() and not member.is_dir():
                    raise ValueError(f"Конфликт: файл из архива пытается перезаписать папку {target.name}")

                if progress:
                    progress(member.filename)
                
                # Note: zipfile.extract() resolves to the same safe target internally
                archive.extract(member, destination)
        return destination

    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as archive:
            members = archive.getmembers()
            if len(members) > MAX_EXTRACT_FILES:
                raise ValueError("Превышен лимит количества файлов в архиве (Tar Bomb)")
            
            total_size = sum(m.size for m in members)
            if total_size > MAX_EXTRACT_SIZE:
                 raise ValueError("Превышен лимит распакованного размера (Tar Bomb)")

            safe_members: list[tarfile.TarInfo] = []
            for member in members:
                # Resolve safe target to check ZipSlip
                target = _safe_target(destination, member.name)
                
                # Check for symlinks escaping sandbox
                if member.issym() or member.islnk():
                    link_target = Path(member.linkname)
                    if link_target.is_absolute() or ".." in link_target.parts:
                        continue # Skip dangerous links
                
                # Check for overwriting
                if target.exists() and target.is_dir() and not member.isdir():
                    raise ValueError(f"Конфликт: файл из архива пытается перезаписать папку {target.name}")
                    
                safe_members.append(member)
                if progress:
                    progress(member.name)
                    
            archive.extractall(destination, members=safe_members)
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
