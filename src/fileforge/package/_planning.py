"""Adjustable internal package plan, not a public ToolResult or authorization.

All checks are lexical. No filesystem lookup, symlink resolution or source
existence/permission check is performed. A must preflight and approve execution.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

_REPORT = "PACKAGE_REPORT.md"
_RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])$", re.I)


def _key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _filename(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value in {".", ".."}
        or value.endswith((".", " "))
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or re.search(r'[<>:"/\\|?*]', value)
        or _RESERVED.fullmatch(value.split(".", 1)[0].rstrip(" ."))
    ):
        raise ValueError("Invalid cross-platform filename")
    return value


def _local_path(value: object):
    if not isinstance(value, str) or not value or "://" in value:
        raise ValueError("Expected a local absolute path")
    if os.name == "nt":
        path = PureWindowsPath(value)
        if not path.is_absolute() or path.drive.startswith("\\\\"):
            raise ValueError("Only local absolute Windows drive paths are supported")
        raw_parts = re.split(r"[/\\]", value[len(path.anchor) :])
    else:
        if PureWindowsPath(value).drive or "\\" in value or value.startswith("//"):
            raise ValueError("Windows/UNC paths are unsupported on this host")
        path = PurePosixPath(value)
        if not path.is_absolute():
            raise ValueError("Expected a local absolute path")
        raw_parts = value[1:].split("/")
    if not raw_parts or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("Empty, dot and traversal path components are forbidden")
    for part in raw_parts:
        _filename(part)
    return path


def _plan_package(
    task_id: str,
    requirements: list[str],
    selected_files: list[dict[str, str]],
    destination: str,
) -> dict[str, Any]:
    """Plan copies/report without executing, matching or choosing versions.

    Private input refs are {file_id, path, filename}; extra fields are ignored.
    No output structure here is frozen or intended for direct A/B consumption.
    verification_targets.files is relative to its internal base, NOT directly
    compatible with A's workspace-relative expected.files without adaptation.
    """
    if not isinstance(task_id, str) or not task_id.strip():
        raise ValueError("task_id must be nonempty")
    if not isinstance(requirements, list) or any(
        not isinstance(item, str) or not item.strip() for item in requirements
    ):
        raise ValueError("requirements must be a list of nonempty names")
    if not isinstance(selected_files, list) or not selected_files:
        raise ValueError("selected_files must be a nonempty list")
    package = _local_path(destination)
    copies = []
    by_id, by_path, targets = {}, {}, {_key(_REPORT)}
    for ref in selected_files:
        if not isinstance(ref, dict):
            raise ValueError("Selected file must be an object")
        file_id = ref.get("file_id")
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("Selected file_id must be nonempty")
        name = _filename(ref.get("filename"))
        source = _local_path(ref.get("path"))
        if source.name != name:
            raise ValueError("filename disagrees with source path")
        source_key = _key(str(source))
        identity = (str(source), name)
        if file_id in by_id and by_id[file_id] != identity:
            raise ValueError("Inconsistent selected file identity")
        if source_key in by_path:
            if by_path[source_key] != (file_id, identity):
                raise ValueError("Inconsistent selected source identity")
            continue
        target = package / name
        if _key(str(target)) == source_key or any(
            _key(str(parent)) == source_key for parent in (package, *package.parents)
        ):
            raise ValueError("Source overlaps package destination")
        if _key(name) in targets:
            raise ValueError("Conflicting or reserved target filename")
        by_id[file_id] = identity
        by_path[source_key] = (file_id, identity)
        targets.add(_key(name))
        copies.append(
            {
                "source_file_id": file_id,
                "source": str(source),
                "filename": name,
                "destination": str(target),
            }
        )
    return {
        "status": "planned",
        "task_id": task_id,
        "requirements": list(dict.fromkeys(requirements)),
        "planned_package_path": str(package),
        "copies": copies,
        "planned_report_path": str(package / _REPORT),
        "verification_targets": {
            "base": str(package),
            "files": [item["filename"] for item in copies] + [_REPORT],
            "archive": [],
        },
    }
