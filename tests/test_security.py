import shutil
import tarfile
import zipfile
from pathlib import Path
import pytest

from archive_app.archive_utils import (
    _validate_archive_name,  # type: ignore
    create_zip_archive,
    extract_archive,
)
from archive_app.file_utils import copy_items, move_items


@pytest.fixture
def temp_workspace(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield workspace
    if workspace.exists():
        shutil.rmtree(workspace)


def test_validate_archive_name():
    assert _validate_archive_name("test.txt") == "test.txt"
    assert _validate_archive_name("folder/test.txt") == "folder/test.txt"
    assert _validate_archive_name("folder\\test.txt") == "folder/test.txt"

    with pytest.raises(ValueError, match="Абсолютный путь запрещён"):
        _validate_archive_name("/etc/passwd")

    with pytest.raises(ValueError, match="Абсолютный путь запрещён"):
        _validate_archive_name("C:\\Windows\\System32")

    with pytest.raises(ValueError, match="Выход за пределы папки запрещён"):
        _validate_archive_name("../test.txt")

    with pytest.raises(ValueError, match="Выход за пределы папки запрещён"):
        _validate_archive_name("folder/../../test.txt")


def test_path_normalization():
    assert _validate_archive_name("a\\b\\c") == "a/b/c"
    assert _validate_archive_name("a/b/c") == "a/b/c"


def test_zip_slip(temp_workspace: Path):
    zip_path = temp_workspace / "slip.zip"
    dest = temp_workspace / "dest"
    dest.mkdir()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../slipped.txt", "content")
        zf.writestr("/absolute.txt", "content")

    with pytest.raises(ValueError):
        extract_archive(zip_path, dest)


def test_tar_slip(temp_workspace: Path):
    tar_path = temp_workspace / "slip.tar"
    dest = temp_workspace / "dest"
    dest.mkdir()

    with tarfile.open(tar_path, "w") as tf:
        info = tarfile.TarInfo(name="../slipped.txt")
        info.size = 5
        import io

        tf.addfile(info, io.BytesIO(b"hello"))

    with pytest.raises(ValueError):
        extract_archive(tar_path, dest)


def test_zip_bomb_files(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    import archive_app.archive_utils

    monkeypatch.setattr(archive_app.archive_utils, "MAX_EXTRACT_FILES", 5)

    zip_path = temp_workspace / "bomb.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for i in range(10):
            zf.writestr(f"file_{i}.txt", "data")

    with pytest.raises(ValueError, match="Превышен лимит количества файлов"):
        extract_archive(zip_path, temp_workspace / "dest")


def test_zip_bomb_size(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch):
    import archive_app.archive_utils

    monkeypatch.setattr(archive_app.archive_utils, "MAX_EXTRACT_SINGLE_FILE_SIZE", 10)

    zip_path = temp_workspace / "bomb.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("huge.txt", "This is larger than 10 bytes")

    with pytest.raises(ValueError, match="Файл слишком большой"):
        extract_archive(zip_path, temp_workspace / "dest")


def test_tar_symlink_denied(temp_workspace: Path):
    tar_path = temp_workspace / "symlink.tar"
    with tarfile.open(tar_path, "w") as tf:
        info = tarfile.TarInfo(name="link.txt")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)

    with pytest.raises(ValueError, match="Ссылки в TAR запрещены"):
        extract_archive(tar_path, temp_workspace / "dest")


def test_tar_hardlink_denied(temp_workspace: Path):
    tar_path = temp_workspace / "hardlink.tar"
    with tarfile.open(tar_path, "w") as tf:
        info = tarfile.TarInfo(name="link.txt")
        info.type = tarfile.LNKTYPE
        info.linkname = "/etc/passwd"
        tf.addfile(info)

    with pytest.raises(ValueError, match="Ссылки в TAR запрещены"):
        extract_archive(tar_path, temp_workspace / "dest")


def test_self_archiving(temp_workspace: Path):
    source = temp_workspace / "source"
    source.mkdir()
    (source / "file.txt").write_text("hello")

    out_zip = source / "archive.zip"
    with pytest.raises(
        ValueError, match="Нельзя сохранять архив внутрь архивируемой папки"
    ):
        create_zip_archive(out_zip, [source])


def test_self_copy(temp_workspace: Path):
    folder = temp_workspace / "folder"
    folder.mkdir()

    with pytest.raises(
        ValueError, match="Нельзя скопировать или переместить папку внутрь самой себя"
    ):
        copy_items([folder], folder)

    inner = folder / "inner"
    inner.mkdir()
    with pytest.raises(
        ValueError, match="Нельзя скопировать или переместить папку внутрь самой себя"
    ):
        copy_items([folder], inner)


def test_self_move(temp_workspace: Path):
    folder = temp_workspace / "folder"
    folder.mkdir()

    with pytest.raises(
        ValueError, match="Нельзя скопировать или переместить папку внутрь самой себя"
    ):
        move_items([folder], folder)

    inner = folder / "inner"
    inner.mkdir()
    with pytest.raises(
        ValueError, match="Нельзя скопировать или переместить папку внутрь самой себя"
    ):
        move_items([folder], inner)
