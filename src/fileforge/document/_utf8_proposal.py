"""Isolated UTF-8 proposal; NOT exported, routed or enabled by read_document.

The byte allowance and extension set require contract approval. The Workspace
argument is a test containment guard, never proof of TaskService authorization.
"""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from fileforge.document.parser import _failure

_EXTENSIONS = frozenset({".cpp", ".h", ".hpp", ".json", ".csv"})
_MAX_BYTES = 1_048_576
_CHUNK = 65_536
_WINDOWS_STAT = os.name == "nt"


def _signature(info, *, cross_api=False):
    value = (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
    )
    return value if cross_api and _WINDOWS_STAT else value + (info.st_ctime_ns,)


def _no_links(path):
    """Inspect every visible component, including the test root's ancestors."""
    for component in (*reversed(path.parents), path):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("Symbolic link or reparse point is not allowed")


def _source(path, workspace):
    if type(path) is not str or type(workspace) is not str:
        raise ValueError("Path and test Workspace must be strings")
    root = Path(os.path.abspath(Path(workspace).expanduser()))
    source = Path(path).expanduser()
    if not source.is_absolute():
        source = root / source
    source = Path(os.path.abspath(source))
    if not source.is_relative_to(root):
        raise ValueError("Path is outside test Workspace")
    _no_links(root)
    if not root.is_dir():
        raise ValueError("Test Workspace must be a directory")
    _no_links(source)
    source = source.resolve(strict=True)
    if not source.is_relative_to(root.resolve(strict=True)):
        raise ValueError("Resolved path is outside test Workspace")
    return source


def _read_bytes(source):
    before = source.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Path is not a regular file")
    if before.st_size > _MAX_BYTES:
        raise ValueError(f"Raw file exceeds proposed limit {_MAX_BYTES} bytes")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(source, flags)
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or _signature(
            opened, cross_api=True
        ) != _signature(before, cross_api=True):
            raise ValueError("Source changed before reading")
        raw = bytearray()
        while len(raw) <= _MAX_BYTES:
            chunk = os.read(fd, min(_CHUNK, _MAX_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > _MAX_BYTES:
            raise ValueError(f"Raw file exceeds proposed limit {_MAX_BYTES} bytes")
        after = os.fstat(fd)
        _no_links(source)
        observed = source.lstat()
        if (
            len(raw) != before.st_size
            or _signature(opened) != _signature(after)
            or _signature(before) != _signature(observed)
            or _signature(after, cross_api=True) != _signature(observed, cross_api=True)
        ):
            raise ValueError("Source changed while reading")
        return raw, observed
    finally:
        os.close(fd)


def _read_utf8_candidate(path: str, workspace: str) -> dict:
    """Read actual bytes into the unchanged Document shape, for isolated tests.

    No code/JSON/CSV evaluation, public registration, writes or paid API access.
    Observable consistency checks do not eliminate all path/ABA races. Public
    integration and A's independent provenance/security checks remain pending.
    """
    try:
        source = _source(path, workspace)
        extension = source.suffix.lower()
        if extension not in _EXTENSIONS:
            return _failure("Unsupported UTF-8 proposal extension")
        raw, info = _read_bytes(source)
        content = raw.decode("utf-8-sig", errors="strict")
        if "\x00" in content:
            return _failure("NUL is not supported in UTF-8 document text")
        if not content.strip():
            return _failure("Document is empty or contains only whitespace")
        identity = os.path.normcase(str(source)).encode("utf-8")
        document = {
            "file_id": "file_" + hashlib.sha256(identity).hexdigest(),
            "path": str(source),
            "filename": source.name,
            "extension": extension,
            "text": content,
            "size": info.st_size,
            "modified_time": datetime.fromtimestamp(info.st_mtime, tz=UTC).isoformat(),
            "metadata": {},
        }
    except UnicodeDecodeError:
        return _failure("Invalid UTF-8 document encoding; no replacement decoding")
    except (OSError, ValueError, RuntimeError, TypeError, UnicodeError) as exc:
        return _failure(f"UTF-8 proposal read failed: {exc}")
    return {
        "success": True,
        "tool": "read_document",
        "data": {"document": document},
        "message": "Isolated UTF-8 proposal read succeeded; public reader unchanged",
        "error": None,
    }
