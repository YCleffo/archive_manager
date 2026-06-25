import re
import subprocess
from pathlib import Path


def get_git_commit_count() -> int | None:
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except Exception as e:
        print(f"Error getting commit count: {e}")
        return None


def update_file(path: Path, pattern: str, replacement: str) -> None:
    if not path.exists():
        print(f"File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content, count = re.subn(pattern, replacement, content)

    if count > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Updated {path} ({count} replacements)")
    else:
        print(f"No changes made to {path} (pattern not found)")


def main() -> None:
    commits = get_git_commit_count()
    if commits is None:
        return

    version_str = f"1.5.{commits}"
    version_win_str = f"1.5.{commits}.0"
    version_tuple_str = f"1, 5, {commits}, 0"

    print(f"Updating version to {version_str} ({commits} commits)")

    base_dir = Path(__file__).parent

    # 1. archive_app/__init__.py
    init_path = base_dir / "archive_app" / "__init__.py"
    update_file(init_path, r'__version__\s*=\s*".*?"', f'__version__ = "{version_str}"')

    # 2. packaging/windows/app.manifest
    manifest_path = base_dir / "packaging" / "windows" / "app.manifest"
    update_file(
        manifest_path,
        r'<assemblyIdentity version=".*?"',
        f'<assemblyIdentity version="{version_win_str}"',
    )

    # 3. packaging/windows/version_info.txt
    version_info_path = base_dir / "packaging" / "windows" / "version_info.txt"
    update_file(
        version_info_path, r"filevers=\(.*?\)", f"filevers=({version_tuple_str})"
    )
    update_file(
        version_info_path, r"prodvers=\(.*?\)", f"prodvers=({version_tuple_str})"
    )
    update_file(
        version_info_path,
        r"'FileVersion',\s*'.*?'",
        f"'FileVersion', '{version_win_str}'",
    )
    update_file(
        version_info_path,
        r"'ProductVersion',\s*'.*?'",
        f"'ProductVersion', '{version_win_str}'",
    )


if __name__ == "__main__":
    main()
