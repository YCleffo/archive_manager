from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".csv",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".xml",
    ".yml",
    ".yaml",
    ".ini",
    ".cfg",
    ".log",
    ".sql",
    ".php",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".sh",
    ".bat",
    ".ps1",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".idea",
    ".vscode",
}


@dataclass(frozen=True)
class SearchResult:
    path: Path
    kind: str
    size: int | None
    modified: datetime | None
    match_type: str


def parse_extensions(raw: str) -> set[str]:
    if not raw.strip():
        return set()
    result: set[str] = set()
    for item in raw.replace(";", ",").split(","):
        ext = item.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        result.add(ext)
    return result


def is_hidden_or_system(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    try:
        attrs = getattr(path.stat(), "st_file_attributes", 0)
        if attrs & (2 | 4):
            return True
    except OSError:
        pass
    return False


def _read_text_preview(path: Path, limit_bytes: int) -> str:
    data = path.read_bytes()[:limit_bytes]
    for encoding in ("utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(encoding, errors="ignore")
        except UnicodeDecodeError:
            continue
    return ""


def search_files(
    root: Path,
    query: str,
    extensions_raw: str = "",
    include_content: bool = False,
    max_results: int = 1000,
    max_content_bytes: int = 2_000_000,
    cancel_event: threading.Event | None = None,
) -> Generator[SearchResult, None, None]:
    root = Path(root).expanduser().resolve()
    query_clean = query.strip().casefold()
    if not query_clean:
        return

    extensions = parse_extensions(extensions_raw)
    found = 0

    for dirpath, dirnames, filenames in os.walk(root):
        if cancel_event and cancel_event.is_set():
            return

        dirnames[:] = [
            d
            for d in dirnames
            if d not in EXCLUDED_DIR_NAMES
            and not os.path.islink(os.path.join(dirpath, d))
            and not is_hidden_or_system(Path(dirpath) / d)
        ]

        for name in dirnames + filenames:
            if cancel_event and cancel_event.is_set():
                return
            if found >= max_results:
                return

            try:
                path = Path(dirpath) / name
                if path.is_symlink() or is_hidden_or_system(path):
                    continue

                is_dir = path.is_dir()
                if extensions and not is_dir and path.suffix.lower() not in extensions:
                    continue

                stat = path.stat()
                name_match = query_clean in path.name.casefold()
                content_match = False

                if include_content and not is_dir:
                    if (
                        path.suffix.lower() in TEXT_EXTENSIONS
                        and stat.st_size <= max_content_bytes
                    ):
                        try:
                            text = _read_text_preview(
                                path, max_content_bytes
                            ).casefold()
                            content_match = query_clean in text
                        except (OSError, UnicodeError):
                            content_match = False

                if name_match or content_match:
                    found += 1
                    kind = (
                        "Папка"
                        if is_dir
                        else path.suffix.lower().lstrip(".").upper() or "Файл"
                    )
                    yield SearchResult(
                        path=path,
                        kind=kind,
                        size=None if is_dir else stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        match_type="имя" if name_match else "содержимое",
                    )
            except (PermissionError, FileNotFoundError, OSError):
                continue
