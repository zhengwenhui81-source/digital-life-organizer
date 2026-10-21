"""Isolated read-only planning experiment, NOT a classifier/approval contract.

Local frozen dataclasses below are synthetic test inputs, not D's proposed JSON
schema. No production consumer, tool registration or filesystem writer uses them.
Path observations are advisory: A must revalidate authorized sources/targets at
execution, including bytes and object identity. This module grants no authority.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

_OUTPUT = "整理结果"
_RESERVED = re.compile(
    r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])", re.I
)


@dataclass(frozen=True)
class _Source:
    file_id: str | None
    path: str
    filename: str


@dataclass(frozen=True)
class _Item:
    source: _Source
    category: str | None
    evidence: tuple[object, ...]
    selected: bool = False
    needs_confirmation: bool = True
    classification_confirmed: bool = False
    basis: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class _Mapping:
    source: _Source
    target: str | None
    category: str | None
    evidence: tuple[object, ...]
    disposition: str
    basis: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class _Draft:
    mappings: tuple[_Mapping, ...]
    directories: tuple[str, ...]
    diagnostics: tuple[str, ...]


def _json_value(value: object, active: set[int] | None = None) -> None:
    """Validate opaque evidence without assuming a classifier field schema."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Evidence contains a nonfinite number")
        return
    if type(value) not in (dict, list):
        raise ValueError("Evidence must contain JSON values")
    active = set() if active is None else active
    if id(value) in active:
        raise ValueError("Evidence contains a cycle")
    active.add(id(value))
    try:
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                raise ValueError("Evidence keys must be strings")
            children = value.values()
        else:
            children = value
        for child in children:
            _json_value(child, active)
    finally:
        active.remove(id(value))


def _key(name: str) -> str:
    # Experimental lexical policy consistent with current Package name keys.
    # Keep spelling intact in all output; this is collision detection only.
    return unicodedata.normalize("NFC", name).casefold()


def _name(name: str) -> None:
    if (
        type(name) is not str
        or not name.strip()
        or not name.strip(".")
        or name.endswith((".", " "))
        or len(name.encode("utf-16-le")) // 2 > 255
        or any(unicodedata.category(c) == "Cc" or c in '<>:"/\\|?*' for c in name)
        or _RESERVED.fullmatch(name.split(".")[0].rstrip(" "))
    ):
        raise ValueError("Unsafe cross-platform name")


def _native(raw: str) -> Path:
    if type(raw) is not str or not raw or "\x00" in raw:
        raise ValueError("Expected a native absolute path")
    win = PureWindowsPath(raw)
    if raw.startswith(("//", "\\\\")) or "://" in raw:
        raise ValueError("UNC/device/URI paths are unsupported")
    if os.name != "nt" and (win.drive or "\\" in raw):
        raise ValueError("Foreign Windows path")
    path = Path(raw)
    if (
        not path.is_absolute()
        or (os.name == "nt" and not win.drive)
        or any(part in (".", "..") for part in re.split(r"[/\\]", raw))
    ):
        raise ValueError("Absolute non-traversing path required")
    return path


def _observe(path: Path) -> os.stat_result:
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Links/reparse points are unsupported")
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError("Source ancestor is not a directory")
    return info


def _source(source: _Source, root: Path) -> None:
    if type(source) is not _Source:
        raise ValueError("Expected a local source reference")
    if source.file_id is not None and (
        type(source.file_id) is not str or not source.file_id.strip()
    ):
        raise ValueError("Invalid optional source identity")
    _name(source.filename)
    path = _native(source.path)
    if not path.is_relative_to(root) or path == root:
        raise ValueError("Source is outside workspace")
    relative = path.relative_to(root)
    if _key(relative.parts[0]) == _key(_OUTPUT):
        raise ValueError("Generated output cannot be an input source")
    if path.name != source.filename:
        raise ValueError("Source filename/path mismatch")
    if not stat.S_ISREG(_observe(path).st_mode):
        raise ValueError("Source is not a regular file")


def _plan(workspace: str, items: tuple[_Item, ...]) -> _Draft:
    """Propose lexical copies only; no hashing, approval, scanning or writing.

    A catches validation/I/O errors and rejects any nonempty diagnostics before
    freezing. Only relative proposals are returned: no operations, approval IDs,
    byte evidence or public classifier fields are invented here.
    """
    root = _native(workspace)
    if not stat.S_ISDIR(_observe(root).st_mode):
        raise ValueError("Workspace is not a directory")
    if type(items) is not tuple:
        raise ValueError("Expected an isolated tuple fixture, not classifier JSON")
    # Validate even unselected entries. Never silently discard contradictory IDs.
    identities: dict[str, _Item] = {}
    id_paths: dict[str, str] = {}
    unique: list[_Item] = []
    for item in items:
        if type(item) is not _Item:
            raise ValueError("Expected a local synthetic classification item")
        _source(item.source, root)
        if any(
            type(flag) is not bool
            for flag in (
                item.selected,
                item.needs_confirmation,
                item.classification_confirmed,
            )
        ):
            raise ValueError("Selection flags must be exact booleans")
        if type(item.evidence) is not tuple:
            raise ValueError("Evidence must be an internal tuple")
        for evidence in item.evidence:
            _json_value(evidence)
        if item.basis is not None and (
            type(item.basis) is not str or not item.basis.strip()
        ):
            raise ValueError("Invalid classification basis")
        if type(item.reason) is not str:
            raise ValueError("Invalid classification reason")
        if item.category is not None:
            _name(item.category)
            if _key(item.category) == _key(_OUTPUT):
                raise ValueError("Output folder cannot be a category")
        if item.source.file_id is not None:
            previous_path = id_paths.setdefault(item.source.file_id, item.source.path)
            if previous_path != item.source.path:
                raise ValueError("Contradictory source/classification identity")
        previous = identities.get(item.source.path)
        if previous is not None:
            if previous != item or json.dumps(
                previous.evidence, sort_keys=True, ensure_ascii=False, allow_nan=False
            ) != json.dumps(
                item.evidence, sort_keys=True, ensure_ascii=False, allow_nan=False
            ):
                raise ValueError("Contradictory source/classification identity")
            continue
        identities[item.source.path] = item
        unique.append(item)

    mappings: list[_Mapping] = []
    directories: list[str] = []
    diagnostics: list[str] = []
    categories: dict[str, str] = {}
    targets: set[tuple[str, str]] = set()
    relative_output = PurePosixPath(_OUTPUT)
    for item in unique:
        evidence = copy.deepcopy(item.evidence)
        confirmed = not item.needs_confirmation or item.classification_confirmed
        if item.category is None or not item.evidence or not confirmed:
            mappings.append(
                _Mapping(
                    item.source,
                    None,
                    item.category,
                    evidence,
                    "pending",
                    item.basis,
                    item.reason,
                )
            )
            continue
        if not item.selected:
            mappings.append(
                _Mapping(
                    item.source,
                    None,
                    item.category,
                    evidence,
                    "unselected",
                    item.basis,
                    item.reason,
                )
            )
            continue
        category_key = _key(item.category)
        old = categories.setdefault(category_key, item.category)
        if old != item.category:
            diagnostics.append("Category spelling collision")
        target_key = category_key, _key(item.source.filename)
        if target_key in targets:
            diagnostics.append("Destination name collision")
        targets.add(target_key)
        category = relative_output / item.category
        destination = category / item.source.filename
        mappings.append(
            _Mapping(
                item.source,
                str(destination),
                item.category,
                evidence,
                "proposed",
                item.basis,
                item.reason,
            )
        )
        if str(category) not in directories:
            directories.append(str(category))

    if directories:
        # Prototype policy: any existing output spelling/alias blocks this plan.
        # No reuse/merging/automatic suffixing until A/D agree that behavior.
        if any(_key(child.name) == _key(_OUTPUT) for child in root.iterdir()):
            diagnostics.append("Organization output already exists")
        directories.insert(0, str(relative_output))
    return _Draft(
        tuple(mappings),
        tuple(directories),
        tuple(dict.fromkeys(diagnostics)),
    )
