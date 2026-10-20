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
from copy import deepcopy
from pathlib import Path
from typing import Any

from fileforge.document import read_document

_ANALYSIS_DOCUMENT_ARGUMENTS = {
    "compare_versions": "documents",
    "detect_conflicts": "documents",
    "extract_requirements": "documents",
    "match_requirements": "candidate_documents",
}
_PACKAGE_ANALYSES = (
    "extract_requirements",
    "match_requirements",
    "detect_conflicts",
    "compare_versions",
)


def collect_package_read_results(
    state: dict[str, Any], *, task_id: str
) -> list[tuple[int, dict[str, Any]]]:
    """Authenticate analysis inputs against earlier reads in this execution.

    Return every successful read, including notice and unselected candidates,
    for current-source revalidation. No caller-supplied Document can become
    Package evidence merely because it appears in an analysis ToolResult.
    """
    if type(state) is not dict:
        raise ValueError("Package execution evidence is invalid")
    plan = state.get("plan")
    steps = plan.get("steps") if type(plan) is dict else None
    if (
        type(task_id) is not str
        or not task_id
        or state.get("task_id") != task_id
        or type(plan) is not dict
        or plan.get("task_id") != task_id
        or type(steps) is not list
    ):
        raise ValueError("Package evidence belongs to a different task or plan")
    step_tools = {}
    for step in steps:
        if (
            type(step) is not dict
            or type(step.get("step_id")) is not str
            or type(step.get("tool")) is not str
            or step["step_id"] in step_tools
        ):
            raise ValueError("Package execution plan has invalid steps")
        step_tools[step["step_id"]] = step["tool"]
    results = state.get("results")
    calls = state.get("result_calls")
    if (
        type(results) is not list
        or type(calls) is not list
        or len(calls) != len(results)
    ):
        raise ValueError("Package result-call provenance is incomplete")
    reads: list[tuple[int, dict[str, Any]]] = []
    documents: list[dict[str, Any]] = []
    for index, (result, call) in enumerate(zip(results, calls)):
        if (
            type(result) is not dict
            or type(call) is not dict
            or type(call.get("result_index")) is not int
            or call["result_index"] != index
            or type(call.get("step_id")) is not str
            or type(call.get("arguments")) is not dict
            or call.get("tool") != result.get("tool")
            or step_tools.get(call["step_id"]) != call["tool"]
        ):
            raise ValueError("Package result-call provenance is inconsistent")
        if result.get("success") is not True:
            raise ValueError("Failed upstream tool prevents Package planning")
        tool = call["tool"]
        if tool == "read_document":
            data = result.get("data")
            document = data.get("document") if type(data) is dict else None
            if type(document) is not dict or not _json_shape(document):
                raise ValueError("Package read result has no valid Document")
            requested_path = call["arguments"].get("path")
            document_path = document.get("path")
            if (
                type(requested_path) is not str
                or type(document_path) is not str
                or not Path(requested_path).is_absolute()
                or not Path(document_path).is_absolute()
                or Path(requested_path).resolve() != Path(document_path).resolve()
            ):
                raise ValueError("Package Document does not belong to read call")
            reads.append((index, result))
            documents.append(document)
        elif tool in _ANALYSIS_DOCUMENT_ARGUMENTS:
            field = _ANALYSIS_DOCUMENT_ARGUMENTS[tool]
            supplied = call["arguments"].get(field)
            if type(supplied) is not list:
                raise ValueError(f"Package {tool} input Documents are missing")
            for document in supplied:
                if (
                    type(document) is not dict
                    or not _json_shape(document)
                    or not any(_same_document(document, prior) for prior in documents)
                ):
                    raise ValueError(
                        f"Package {tool} input lacks an earlier successful read"
                    )
    if not reads:
        raise ValueError("Package evidence has no successful Document reads")
    return reads


def current_package_analysis(
    state: dict[str, Any], *, task_id: str
) -> dict[str, dict[str, Any] | None]:
    """Freeze each latest analysis ToolResult with its current result index.

    This uses the same call/result audit as the read collector. A later failure
    cannot be hidden by choosing an older successful analysis result.
    """
    collect_package_read_results(state, task_id=task_id)
    results = state["results"]
    analysis: dict[str, dict[str, Any] | None] = {}
    for tool in _PACKAGE_ANALYSES:
        latest = next(
            (
                index
                for index in range(len(results) - 1, -1, -1)
                if results[index]["tool"] == tool
            ),
            None,
        )
        if latest is None:
            analysis[tool] = None
            continue
        result = results[latest]
        if not _json_shape(result):
            raise ValueError(f"Package {tool} result is not strict JSON")
        analysis[tool] = {"result_index": latest, "result": deepcopy(result)}
    return analysis


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


def recheck_approved_source_bytes(
    workspace: str, checked: dict[int, dict[str, Any]]
) -> None:
    """Fail if any previously checked analysis source changed after preview.

    Call before mutations and again before each source is used. This is only a
    source-byte check; the Package adapter must separately verify the frozen
    plan/approval, destination vacancy, and path/ancestor safety.
    """
    root = Path(workspace)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("Package workspace is invalid")
    _check_path(root, root)
    if type(checked) is not dict or not checked:
        raise ValueError("Approved Package source evidence is missing")
    for index, evidence in checked.items():
        if (
            type(index) is not int
            or index < 0
            or type(evidence) is not dict
            or type(evidence.get("file_id")) is not str
            or not evidence["file_id"]
            or type(evidence.get("path")) is not str
            or type(evidence.get("size")) is not int
            or evidence["size"] < 0
            or type(evidence.get("mtime_ns")) is not int
            or type(evidence.get("sha256")) is not str
            or len(evidence["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in evidence["sha256"])
        ):
            raise ValueError("Approved Package source evidence is invalid")
        current = _digest(Path(evidence["path"]), root)
        expected = (evidence["sha256"], evidence["size"], evidence["mtime_ns"])
        if current != expected:
            raise ValueError("Approved Package source differs from frozen preview")
