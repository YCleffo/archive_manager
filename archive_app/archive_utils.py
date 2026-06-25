from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterable

ProgressCallback = Callable[[str], Any]

SUPPORTED_ARCHIVES = (".zip", ".tar", ".gz", ".tgz", ".bz2")

MAX_EXTRACT_FILES = 10_000
MAX_EXTRACT_TOTAL_SIZE = 2 * 1024 * 1024 * 1024
MAX_EXTRACT_SINGLE_FILE_SIZE = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 500


def _common_parent(paths: list[Path]) -> Path:
    if len(paths) == 1:
        return paths[0].parent
    return Path(
        os.path.commonpath(
            [str(path.parent if path.is_file() else path.parent) for path in paths]
        )
    )


def _is_same_or_inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents


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

    for source in paths:
        if source.is_dir() and _is_same_or_inside(output_zip, source):
            raise ValueError("Нельзя сохранять архив внутрь архивируемой папки")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    common_parent = _common_parent(paths)

    with zipfile.ZipFile(
        output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for source in paths:
            if source.is_dir():
                has_any = False
                for item in source.rglob("*"):
                    if _is_same_or_inside(item, output_zip):
                        continue
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


def _validate_archive_name(member_name: str) -> str:
    raw = member_name.replace("\\", "/").strip()
    if not raw:
        raise ValueError("Пустое имя элемента архива")

    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)

    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ValueError(f"Абсолютный путь запрещён: {member_name}")

    parts = [part for part in posix.parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"Выход за пределы папки запрещён: {member_name}")

    return "/".join(parts)


def _safe_target(destination: Path, member_name: str) -> Path:
    destination = destination.resolve()
    valid_name = _validate_archive_name(member_name)
    target = (destination / valid_name).resolve()
    try:
        target.relative_to(destination)
    except ValueError as exc:
        raise ValueError(f"Небезопасный путь в архиве: {member_name}") from exc
    return target


def _validate_tar_member(member: tarfile.TarInfo) -> None:
    if member.issym() or member.islnk():
        raise ValueError(f"Ссылки в TAR запрещены: {member.name}")
    if member.isdev() or member.isfifo() or member.ischr() or member.isblk():
        raise ValueError(f"Спецфайлы в TAR запрещены: {member.name}")
    if not (member.isfile() or member.isdir()):
        raise ValueError(f"Неподдерживаемый тип элемента TAR: {member.name}")


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
                    raise ValueError(
                        "Превышен лимит количества файлов в архиве (Zip Bomb)"
                    )

                if member.file_size > MAX_EXTRACT_SINGLE_FILE_SIZE:
                    raise ValueError(f"Файл слишком большой: {member.filename}")
                if member.compress_size == 0 and member.file_size > 0:
                    raise ValueError(f"Подозрительный ZIP-элемент: {member.filename}")
                if (
                    member.compress_size > 0
                    and (member.file_size / member.compress_size)
                    > MAX_COMPRESSION_RATIO
                ):
                    raise ValueError(
                        f"Подозрительный уровень сжатия у файла: {member.filename} (Zip Bomb)"
                    )

                total_size += member.file_size
                if total_size > MAX_EXTRACT_TOTAL_SIZE:
                    raise ValueError("Превышен лимит распакованного размера (Zip Bomb)")

                target = _safe_target(destination, member.filename)

                if target.exists() and target.is_dir() and not member.is_dir():
                    raise ValueError(
                        f"Конфликт: файл из архива пытается перезаписать папку {target.name}"
                    )
                if target.exists() and target.is_file() and member.is_dir():
                    raise ValueError(
                        f"Конфликт: папка из архива пытается перезаписать файл {target.name}"
                    )

                if progress:
                    progress(member.filename)

                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member, "r") as src, open(target, "wb") as dst:
                        import shutil

                        shutil.copyfileobj(src, dst)
        return destination

    if tarfile.is_tarfile(archive_path):
        total_size = 0
        file_count = 0
        with tarfile.open(archive_path, "r:*") as archive:
            for member in archive:
                file_count += 1
                if file_count > MAX_EXTRACT_FILES:
                    raise ValueError(
                        "Превышен лимит количества файлов в архиве (Tar Bomb)"
                    )

                _validate_tar_member(member)

                if member.size > MAX_EXTRACT_SINGLE_FILE_SIZE:
                    raise ValueError(f"Файл слишком большой: {member.name}")

                total_size += member.size
                if total_size > MAX_EXTRACT_TOTAL_SIZE:
                    raise ValueError("Превышен лимит распакованного размера (Tar Bomb)")

                target = _safe_target(destination, member.name)

                if target.exists() and target.is_dir() and not member.isdir():
                    raise ValueError(
                        f"Конфликт: файл из архива пытается перезаписать папку {target.name}"
                    )
                if target.exists() and target.is_file() and member.isdir():
                    raise ValueError(
                        f"Конфликт: папка из архива пытается перезаписать файл {target.name}"
                    )

                if progress:
                    progress(member.name)

                # Safe individual extract
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with archive.extractfile(member) as src, open(target, "wb") as dst:  # type: ignore
                            import shutil

                            shutil.copyfileobj(src, dst)
                    except Exception as e:
                        raise ValueError(
                            f"Ошибка при распаковке файла {member.name}"
                        ) from e
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
