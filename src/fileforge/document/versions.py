"""Validated public version comparison with a disposable, bounded worker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 1_048_576
COMPARISON_SECONDS = 5.0
CLEANUP_SECONDS = 0.5


def _json_chunks(value: Any, active: set[int] | None = None):
    """Match compact JSON without allocating an unbounded encoded string chunk."""
    if active is None:
        active = set()
    if isinstance(value, str):
        yield b'"'
        for offset in range(0, len(value), 4096):
            yield json.dumps(value[offset : offset + 4096], ensure_ascii=False)[
                1:-1
            ].encode("utf-8")
        yield b'"'
    elif value is None or isinstance(value, (bool, int, float)):
        yield json.dumps(value, allow_nan=False).encode("utf-8")
    elif isinstance(value, (dict, list)):
        marker = id(value)
        if marker in active:
            raise ValueError("Circular reference in input")
        active.add(marker)
        try:
            mapping = isinstance(value, dict)
            yield b"{" if mapping else b"["
            for index, item in enumerate(value.items() if mapping else value):
                if index:
                    yield b","
                if mapping:
                    key, item = item
                    if not isinstance(key, str):
                        raise TypeError("JSON object keys must be strings")
                    yield from _json_chunks(key, active)
                    yield b":"
                yield from _json_chunks(item, active)
            yield b"}" if mapping else b"]"
        finally:
            active.remove(marker)
    else:
        raise TypeError(f"Input value {type(value).__name__} is not JSON serializable")


def _same(left: Any, right: Any) -> bool:
    """Snapshot equality includes types/extra fields, ignoring object key order."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        right_members = {(type(key), key): value for key, value in right.items()}
        return len(left) == len(right) and all(
            (type(key), key) in right_members
            and _same(value, right_members[(type(key), key)])
            for key, value in left.items()
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _same(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _validate(documents: Any) -> bytes:
    if not isinstance(documents, list):
        raise ValueError("documents must be a list of Documents")
    if len(documents) > 10:
        raise ValueError(f"documents count {len(documents)} exceeds limit 10")
    total = 0
    for index, document in enumerate(documents):
        label = f"documents[{index}]"
        if not isinstance(document, dict):
            raise ValueError(f"{label} must be a Document object")
        for field in (
            "file_id",
            "path",
            "filename",
            "extension",
            "text",
            "modified_time",
        ):
            if not isinstance(document.get(field), str):
                raise ValueError(f"{label}.{field} must be a string")
            if field != "modified_time" and not document[field].strip():
                raise ValueError(f"{label}.{field} must not be empty or whitespace")
        if type(document.get("size")) is not int or document["size"] < 0:
            raise ValueError(f"{label}.size must be a nonnegative integer")
        if not isinstance(document.get("metadata"), dict):
            raise ValueError(f"{label}.metadata must be an object")
        length = len(document["text"])
        if length > 10_000:
            raise ValueError(f"{label}.text length {length} exceeds limit 10000")
        total += length
    if total > 50_000:
        raise ValueError(f"total text length {total} exceeds limit 50000")
    payload = {"documents": documents}
    size = sum(len(chunk) for chunk in _json_chunks(payload))
    if size > MAX_INPUT_BYTES:
        raise ValueError(
            f"serialized input size {size} bytes exceeds limit {MAX_INPUT_BYTES} bytes"
        )
    # All measurements above are on the original, pre-deduplication payload.
    unique: dict[str, dict] = {}
    for document in documents:
        key = document["file_id"]
        if key in unique and not _same(unique[key], document):
            raise ValueError(f"Contradictory Document snapshot for file_id {key}")
        unique.setdefault(key, document)
    return b"".join(_json_chunks({"documents": list(unique.values())}))


def _failure(error: str) -> dict[str, Any]:
    return {
        "success": False,
        "tool": "compare_versions",
        "data": None,
        "message": "Version comparison failed",
        "error": error,
    }


def _worker_command() -> list[str]:
    return [sys.executable, "-m", "fileforge.document._version_worker"]


def _stop(process: subprocess.Popen) -> str | None:
    """Always bound cleanup; callers must never accept partial worker output."""
    try:
        process.kill()
        process.communicate(timeout=CLEANUP_SECONDS)
        if process.returncode is None:
            return "Comparison process did not terminate"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"Comparison process cleanup failed: {exc}"
    return None


def compare_versions(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare supplied snapshots, never reading or modifying their source paths."""
    try:
        payload = _validate(documents)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        return _failure(f"Invalid version input: {exc}")
    process = None
    try:
        env = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
        process = subprocess.Popen(
            _worker_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        output, _ = process.communicate(payload, timeout=COMPARISON_SECONDS)
        if process.returncode != 0:
            return _failure(
                f"Version comparison worker exited with {process.returncode}"
            )
        data = json.loads(output)
        if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
            return _failure("Invalid version comparison worker result")
    except subprocess.TimeoutExpired:
        cleanup_error = _stop(process)
        return _failure(
            cleanup_error or "Version comparison timed out: 5-second budget exceeded"
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        cleanup_error = _stop(process) if process and process.poll() is None else None
        return _failure(cleanup_error or f"Version comparison worker failed: {exc}")
    return {
        "success": True,
        "tool": "compare_versions",
        "data": data,
        "message": "Version comparison completed",
        "error": None,
    }
