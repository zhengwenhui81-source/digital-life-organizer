"""Current-source checks before a Package plan becomes executable.

This module deliberately does not claim that a historical analysis read the
same raw bytes. It checks the complete retained Document against a fresh public
read and observes the raw bytes on both sides of that read.
"""

from __future__ import annotations

import hashlib
import math
import os
import stat
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from fileforge.document import read_document


def _json_shape(value: Any, active: set[int] | None = None) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) not in (dict, list):
        return False
    active = set() if active is None else active
    if id(value) in active:
        return False
    active.add(id(value))
    try:
        if type(value) is list:
            return all(_json_shape(item, active) for item in value)
        return all(
            type(key) is str and _json_shape(item, active)
            for key, item in value.items()
        )
    finally:
        active.remove(id(value))


def _same_document(left: Any, right: Any) -> bool:
    """Compare complete JSON Documents, including types and absent fields."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(
            _same_document(left[key], right[key]) for key in left
        )
    if type(left) is list:
        return len(left) == len(right) and all(
            _same_document(a, b) for a, b in zip(left, right)
        )
    return left == right


def _check_path(path: Path, workspace: Path) -> None:
    if not path.is_absolute() or not path.is_relative_to(workspace):
        raise ValueError("Package evidence path escapes workspace")
    for ancestor in (*reversed(path.parents), path):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & 0x400
        ):
            raise ValueError("Package evidence path contains a link")


def _digest(path: Path, workspace: Path) -> tuple[str, int, int]:
    _check_path(path, workspace)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Package evidence source is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        opened = os.fstat(fd)

        def identity(info: os.stat_result) -> tuple[int, int, int, int]:
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

        if identity(before) != identity(opened) or not stat.S_ISREG(opened.st_mode):
            raise ValueError("Package evidence source changed before hashing")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(fd)
        _check_path(path, workspace)
        if identity(opened) != identity(after) or identity(after) != identity(
            path.lstat()
        ):
            raise ValueError("Package evidence source changed while hashing")
        if size != before.st_size:
            raise ValueError("Package evidence source size changed while hashing")
        return digest.hexdigest(), size, before.st_mtime_ns
    finally:
        os.close(fd)


def revalidate_documents(
    workspace: str,
    read_results: Iterable[tuple[int, dict[str, Any]]],
    *,
    reader: Callable[..., dict[str, Any]] = read_document,
) -> dict[int, dict[str, Any]]:
    """Recheck retained successful reads before Package planning.

    The caller supplies every analysis-dependent read from the current Task and
    must separately verify analysis/result provenance. A mismatch raises and
    must block the executable preview. Keys retain the original result indices.
    """
    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Package workspace is invalid")
    _check_path(root, root)
    checked: dict[int, dict[str, Any]] = {}
    identities: dict[str, dict[str, Any]] = {}
    pending = []
    seen_indices = set()
    for index, result in read_results:
        if type(index) is not int or index < 0 or index in seen_indices:
            raise ValueError("Package read result index is invalid")
        seen_indices.add(index)
        if (
            type(result) is not dict
            or result.get("tool") != "read_document"
            or result.get("success") is not True
            or type(result.get("data")) is not dict
            or type(result["data"].get("document")) is not dict
        ):
            raise ValueError("Package evidence requires a successful read_document")
        original = result["data"]["document"]
        if not _json_shape(original):
            raise ValueError("Package Document is not strict JSON")
        path_text = original.get("path")
        file_id = original.get("file_id")
        if type(path_text) is not str or type(file_id) is not str or not file_id:
            raise ValueError("Package Document identity is invalid")
        path = Path(path_text)
        _check_path(path, root)
        if file_id in identities and not _same_document(identities[file_id], original):
            raise ValueError("Contradictory Package Document snapshot")
        identities[file_id] = original
        pending.append((index, original, path, path_text, file_id))
    if not pending:
        raise ValueError("Package evidence has no successful Document reads")
    for index, original, path, path_text, file_id in pending:
        before, size, mtime_ns = _digest(path, root)
        current = reader(path=str(path))
        if (
            type(current) is not dict
            or current.get("tool") != "read_document"
            or current.get("success") is not True
            or type(current.get("data")) is not dict
            or type(current["data"].get("document")) is not dict
        ):
            raise ValueError("Package evidence reread failed")
        reread = current["data"]["document"]
        if not _json_shape(reread) or not _same_document(original, reread):
            raise ValueError("Package Document changed since analysis")
        after, after_size, after_mtime_ns = _digest(path, root)
        if (before, size, mtime_ns) != (after, after_size, after_mtime_ns):
            raise ValueError("Package source bytes changed during reread")
        checked[index] = {
            "file_id": file_id,
            "path": path_text,
            "filename": original.get("filename"),
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": before,
        }
    return checked


def bind_selected_snapshots(
    plan: dict[str, Any], checked: dict[int, dict[str, Any]]
) -> dict[int, int]:
    """Cross-check D's returned selection against A's fresh read evidence.

    Return selected-file index to original read-result index. The caller keeps
    this association alongside the same frozen plan and preview; it must not
    replace a mismatched planning digest with the checked digest.
    """
    if type(plan) is not dict or type(plan.get("selected_files")) is not list:
        raise ValueError("Package plan has no selected files")
    by_identity = {}
    for result_index, evidence in checked.items():
        identity = evidence["file_id"]
        if identity in by_identity and evidence != by_identity[identity][1]:
            raise ValueError("Contradictory checked Package source")
        by_identity[identity] = (result_index, evidence)
    bindings = {}
    for selected_index, selected in enumerate(plan["selected_files"]):
        if type(selected) is not dict:
            raise ValueError("Package selection is invalid")
        source = selected.get("source")
        snapshot = selected.get("snapshot")
        if type(source) is not dict or type(snapshot) is not dict:
            raise ValueError("Package selection has no source snapshot")
        original = by_identity.get(source.get("file_id"))
        if original is None:
            raise ValueError("Package selected source has no checked Document")
        result_index, evidence = original
        if (
            source.get("path") != evidence["path"]
            or source.get("filename") != evidence["filename"]
            or type(snapshot.get("size")) is not int
            or snapshot["size"] != evidence["size"]
            or type(snapshot.get("mtime_ns")) is not int
            or snapshot["mtime_ns"] != evidence["mtime_ns"]
            or snapshot.get("sha256") != evidence["sha256"]
        ):
            raise ValueError("Package plan source snapshot differs from checked bytes")
        bindings[selected_index] = result_index
    return bindings
