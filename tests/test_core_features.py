from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from archive_app.archive_utils import create_zip_archive, extract_archive, list_archive_members
from archive_app.file_utils import (
    calculate_folder_size,
    create_folder,
    ensure_unique_path,
    format_size,
    list_directory,
    rename_item,
)
from archive_app.search_utils import parse_extensions, search_files


def test_create_zip_archive_contains_files_and_folders(tmp_path: Path) -> None:
    source = tmp_path / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (source / "one.txt").write_text("one", encoding="utf-8")
    (nested / "two.txt").write_text("two", encoding="utf-8")

    archive_path = create_zip_archive(tmp_path / "result.zip", [source])
    members = set(list_archive_members(archive_path))

    assert "source/one.txt" in members
    assert "source/nested/two.txt" in members


def test_extract_zip_restores_nested_files(tmp_path: Path) -> None:
    archive_path = tmp_path / "data.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/file.txt", "hello")
        archive.writestr("folder/inner/second.txt", "world")

    destination = tmp_path / "out"
    extract_archive(archive_path, destination)

    assert (destination / "folder" / "file.txt").read_text(encoding="utf-8") == "hello"
    assert (destination / "folder" / "inner" / "second.txt").read_text(encoding="utf-8") == "world"


def test_extract_tar_restores_regular_files(tmp_path: Path) -> None:
    source_file = tmp_path / "source.txt"
    source_file.write_text("tar data", encoding="utf-8")
    archive_path = tmp_path / "data.tar"

    with tarfile.open(archive_path, "w") as archive:
        archive.add(source_file, arcname="safe/source.txt")

    destination = tmp_path / "out"
    extract_archive(archive_path, destination)

    assert (destination / "safe" / "source.txt").read_text(encoding="utf-8") == "tar data"


def test_list_directory_hides_dot_files_and_sorts_folders_first(tmp_path: Path) -> None:
    (tmp_path / "z_file.txt").write_text("file", encoding="utf-8")
    (tmp_path / "a_folder").mkdir()
    (tmp_path / ".hidden.txt").write_text("hidden", encoding="utf-8")

    entries = list_directory(tmp_path)

    assert [entry.name for entry in entries] == ["a_folder", "z_file.txt"]
    assert entries[0].is_dir is True


def test_calculate_folder_size_counts_nested_regular_files(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "a.bin").write_bytes(b"12345")
    (nested / "b.bin").write_bytes(b"123")

    total_size, total_files = calculate_folder_size(tmp_path)

    assert total_size == 8
    assert total_files == 2


def test_ensure_unique_path_adds_counter(tmp_path: Path) -> None:
    existing = tmp_path / "file.txt"
    existing.write_text("old", encoding="utf-8")

    assert ensure_unique_path(existing) == tmp_path / "file_1.txt"


def test_create_folder_and_rename_item_validate_names(tmp_path: Path) -> None:
    created = create_folder(tmp_path, "docs")
    assert created.exists()

    renamed = rename_item(created, "docs_new")
    assert renamed.name == "docs_new"
    assert renamed.exists()

    with pytest.raises(ValueError):
        create_folder(tmp_path, "bad/name")

    with pytest.raises(ValueError):
        rename_item(renamed, "bad\\name")


def test_search_files_finds_by_name(tmp_path: Path) -> None:
    target = tmp_path / "report_final.txt"
    target.write_text("content", encoding="utf-8")

    results = list(search_files(tmp_path, "report", include_content=False))

    assert len(results) == 1
    assert results[0].path == target
    assert results[0].match_type == "имя"


def test_search_files_finds_by_content(tmp_path: Path) -> None:
    target = tmp_path / "notes.txt"
    target.write_text("секретный маршрут лежит здесь", encoding="utf-8")

    results = list(search_files(tmp_path, "маршрут", include_content=True))

    assert len(results) == 1
    assert results[0].path == target
    assert results[0].match_type == "содержимое"


def test_search_files_respects_extension_filter(tmp_path: Path) -> None:
    (tmp_path / "match.txt").write_text("needle", encoding="utf-8")
    (tmp_path / "match.md").write_text("needle", encoding="utf-8")

    results = list(search_files(tmp_path, "match", extensions_raw="txt"))

    assert [result.path.name for result in results] == ["match.txt"]
    assert parse_extensions("txt, .md;py") == {".txt", ".md", ".py"}


def test_search_files_skips_service_directories(tmp_path: Path) -> None:
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()
    (node_modules / "target.txt").write_text("target", encoding="utf-8")
    visible = tmp_path / "target.txt"
    visible.write_text("target", encoding="utf-8")

    results = list(search_files(tmp_path, "target", include_content=False))

    assert [result.path for result in results] == [visible]


def test_format_size_uses_readable_units() -> None:
    assert format_size(0) == "0 Б"
    assert format_size(1024) == "1.0 КБ"
    assert format_size(1024 * 1024) == "1.0 МБ"
