"""Contract-shaped file tools built on FileForge's scanner and deduplication.

The existing Scanner supplies file metadata and honors .forgeignore. The existing
hash_file/find_exact_duplicates functions supply exact duplicate detection.
FileForge's mover may overwrite a destination, so the Agent wrapper uses an
exclusive destination create for both copy and move instead.

Approval is an internal, keyword-only execution gate. It is deliberately absent
from the public tool arguments in API_CONTRACT.md; the future Agent approval
endpoint is responsible for passing it after the user approves a preview.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fileforge.analysis.dedup import find_exact_duplicates, hash_file
from fileforge.models import FileRecord
from fileforge.scanner import Scanner

_DASH_FOLD = str.maketrans({char: "-" for char in "‐‑‒–—―−﹣－"})


def _result(
    tool: str, data: dict[str, Any] | None = None, *, error: str | None = None
) -> dict[str, Any]:
    """Return the shared ToolResult envelope."""
    return {
        "success": error is None,
        "tool": tool,
        "data": data if error is None else None,
        "message": f"{tool} {'completed' if error is None else 'failed'}",
        "error": error,
    }


def _record_data(record: FileRecord) -> dict[str, Any]:
    return {
        "path": str(record.path),
        "filename": record.name,
        "extension": record.extension,
        "size": record.size_bytes,
        "modified_time": record.modified_at.isoformat(),
    }


def _scan(workspace: str, *, recursive: bool = True) -> list[FileRecord]:
    root = Path(workspace).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Workspace is not a directory: {root}")
    scanner = Scanner.from_directory(root, ignore_patterns=[])
    if not recursive:
        scanner._max_depth = 0
    return sorted(scanner.scan([root]), key=lambda record: str(record.path).casefold())


def list_files(workspace: str, recursive: bool = True) -> dict[str, Any]:
    try:
        files = [_record_data(r) for r in _scan(workspace, recursive=recursive)]
        return _result("list_files", {"files": files})
    except (OSError, UnicodeError) as exc:
        return _result("list_files", error=str(exc))


def search_files(
    workspace: str, query: str, extensions: list[str] | None = None
) -> dict[str, Any]:
    try:
        if not query.strip():
            raise ValueError("Search query must not be empty")
        allowed = {
            ext.casefold() if ext.startswith(".") else f".{ext.casefold()}"
            for ext in (extensions or [])
        }
        records = [
            record
            for record in _scan(workspace)
            if not allowed or record.extension.casefold() in allowed
        ]
        matches = [
            record for record in records if query.casefold() in record.name.casefold()
        ]
        if not matches:
            # Keep the full query and extension filter. This only recovers a
            # typographic dash mismatch, never an unrelated filename.
            folded_query = query.translate(_DASH_FOLD).casefold()
            matches = [
                record
                for record in records
                if folded_query in record.name.translate(_DASH_FOLD).casefold()
            ]
        matches = [_record_data(record) for record in matches]
        return _result("search_files", {"matches": matches})
    except (OSError, UnicodeError, ValueError) as exc:
        return _result("search_files", error=str(exc))


def find_duplicates(workspace: str) -> dict[str, Any]:
    try:
        records = _scan(workspace)
        for record in records:
            record.sha256 = hash_file(record.path)
        groups = find_exact_duplicates(records)
        duplicate_groups = [[_record_data(r) for r in group] for group in groups]
        return _result("find_duplicates", {"duplicate_groups": duplicate_groups})
    except (OSError, UnicodeError) as exc:
        return _result("find_duplicates", error=str(exc))


def _require_approval(approved: bool) -> None:
    if not approved:
        raise PermissionError("User approval is required before changing files")


def create_folder(path: str, *, approved: bool = False) -> dict[str, Any]:
    try:
        _require_approval(approved)
        destination = Path(path).expanduser()
        destination.mkdir(parents=True, exist_ok=False)
        return _result("create_folder", {"path": str(destination)})
    except (OSError, ValueError) as exc:
        return _result("create_folder", error=str(exc))


def _copy_exclusive(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Source file not found: {source}")
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Destination folder not found: {destination.parent}")
    with source.open("rb") as input_file:
        # Exclusive mode rejects an existing file or symlink, including a file
        # created between preview and execution.
        created = False
        try:
            with destination.open("xb") as output_file:
                created = True
                shutil.copyfileobj(input_file, output_file)
        except BaseException:
            if created:
                destination.unlink()
            raise


def copy_file(
    source: str, destination: str, *, approved: bool = False
) -> dict[str, Any]:
    try:
        _require_approval(approved)
        src, dst = Path(source).expanduser(), Path(destination).expanduser()
        _copy_exclusive(src, dst)
        return _result("copy_file", {"source": str(src), "destination": str(dst)})
    except (OSError, ValueError) as exc:
        return _result("copy_file", error=str(exc))


def move_file(
    source: str, destination: str, *, approved: bool = False
) -> dict[str, Any]:
    try:
        _require_approval(approved)
        src, dst = Path(source).expanduser(), Path(destination).expanduser()
        _copy_exclusive(src, dst)
        src.unlink()
        return _result("move_file", {"source": str(src), "destination": str(dst)})
    except (OSError, ValueError) as exc:
        return _result("move_file", error=str(exc))
