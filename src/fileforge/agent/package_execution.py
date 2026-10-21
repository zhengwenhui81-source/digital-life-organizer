"""Single-use, approved Package writes and byte-level verification."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from fileforge.agent.package_evidence import recheck_approved_source_bytes
from fileforge.agent.package_fs import anchored_mkdir, anchored_open, guarded_entries


def _result(
    tool: str, data: dict[str, Any] | None = None, error: str | None = None
) -> dict:
    return {
        "success": error is None,
        "tool": tool,
        "data": data if error is None else None,
        "message": f"{tool} {'completed' if error is None else 'failed'}",
        "error": error,
    }


def _safe_path(path: Path, root: Path, *, allow_missing: bool) -> None:
    if not path.is_absolute() or ".." in path.parts or not path.is_relative_to(root):
        raise ValueError("Package path escapes workspace")
    for parent in (*reversed(path.parents), path):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            if not allow_missing:
                raise ValueError("Package path is missing") from None
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Package path contains a link")
        if parent != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError("Package path has a non-directory ancestor")


def _digest(path: Path, root: Path) -> str:
    _safe_path(path, root, allow_missing=False)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Package file is not regular")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = anchored_open(path, root, flags)
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("Package file changed before reading")
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        after = os.fstat(fd)
        observed = path.lstat()
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) or (observed.st_dev, observed.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("Package file changed while reading")
        return digest.hexdigest()
    finally:
        os.close(fd)


def _copy_one(
    source: Path,
    target: Path,
    expected: str,
    root: Path,
    source_identity: tuple[int, int],
) -> tuple[dict, dict]:
    """Copy to a new target; conservatively retain any failed partial target."""
    step_cleanup = {
        "status": "not_attempted",
        "reason": "no_target_created",
        "residual_state": "absent",
    }
    created = False
    owned: tuple[int, int] | None = None
    try:
        _safe_path(source, root, allow_missing=False)
        _safe_path(target, root, allow_missing=True)
        source_info = source.lstat()
        if (source_info.st_dev, source_info.st_ino) != source_identity:
            raise ValueError("Approved Package source object was replaced")
        if os.path.lexists(target):
            raise FileExistsError("Package target is already occupied")
        if _digest(source, root) != expected:
            raise ValueError("Approved Package source digest changed")
        read_flags = (
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        write_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        source_fd = anchored_open(source, root, read_flags)
        try:
            opened = os.fstat(source_fd)
            if (opened.st_dev, opened.st_ino) != source_identity:
                raise ValueError("Approved Package source object was replaced")
            if _digest(source, root) != expected:
                raise ValueError("Approved Package source digest changed")
            target_fd = anchored_open(target, root, write_flags, 0o600)
            created = True
            try:
                info = os.fstat(target_fd)
                owned = (info.st_dev, info.st_ino)
                digest = hashlib.sha256()
                while chunk := os.read(source_fd, 1024 * 1024):
                    digest.update(chunk)
                    view = memoryview(chunk)
                    while view:
                        written = os.write(target_fd, view)
                        if written <= 0:
                            raise OSError("Package copy made no write progress")
                        view = view[written:]
                os.fsync(target_fd)
                after_opened = os.fstat(source_fd)
                if (
                    after_opened.st_dev,
                    after_opened.st_ino,
                    after_opened.st_size,
                    after_opened.st_mtime_ns,
                ) != (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_size,
                    opened.st_mtime_ns,
                ):
                    raise ValueError("Approved Package source changed during copy")
            finally:
                os.close(target_fd)
        finally:
            os.close(source_fd)
        current = source.lstat()
        if (current.st_dev, current.st_ino) != source_identity:
            raise ValueError("Approved Package source object was replaced")
        if (
            digest.hexdigest() != expected
            or _digest(source, root) != expected
            or _digest(target, root) != expected
        ):
            raise ValueError("Package copied bytes differ from approved source")
        step_cleanup.update(reason="copy_succeeded")
        return (
            _result("copy_file", {"source": str(source), "destination": str(target)}),
            step_cleanup,
        )
    except (OSError, ValueError) as exc:
        if created:
            try:
                observed = target.lstat()
                state = (
                    "owned_fragment"
                    if owned == (observed.st_dev, observed.st_ino)
                    else "other_object"
                )
            except OSError:
                state = "unknown"
            step_cleanup.update(
                reason="Failed copy target retained; conditional unlink is unsafe",
                residual_state=state,
            )
        return _result("copy_file", error=str(exc)), step_cleanup


def _verify(plan: dict, checked: dict[int, dict], root: Path) -> dict:
    checks = []
    try:
        recheck_approved_source_bytes(str(root), checked)
        checks.append({"path": str(root), "kind": "source-snapshot", "passed": True})
        destination = Path(plan["destination"])
        _safe_path(destination, root, allow_missing=False)
        if not destination.is_dir():
            raise ValueError("Package directory is missing")
        expected_names = {"PACKAGE_REPORT.md"}
        for item in plan["selected_files"]:
            target = Path(item["target"])
            expected_names.add(target.name)
            passed = _digest(target, root) == item["snapshot"]["sha256"]
            checks.append(
                {"path": str(target), "kind": "material-digest", "passed": passed}
            )
        report = plan["report"]
        passed = _digest(Path(report["path"]), root) == report["sha256"]
        checks.append(
            {"path": report["path"], "kind": "report-digest", "passed": passed}
        )
        actual_names = guarded_entries(destination, root)
        checks.append(
            {
                "path": str(destination),
                "kind": "file-set",
                "passed": actual_names == expected_names,
            }
        )
        if not all(check["passed"] for check in checks):
            raise ValueError("Package verification differs from frozen plan")
        return _result("verify_result", {"checks": checks, "passed": True})
    except (OSError, ValueError) as exc:
        return _result("verify_result", error=str(exc))


def execute_package(
    plan: dict[str, Any],
    plan_sha256: str,
    checked: dict[int, dict[str, Any]],
    bindings: dict[int, int],
    append: Any,
) -> tuple[dict, list[dict]]:
    """Run frozen descriptors serially after TaskService consumes approval.

    append(step_id, ToolResult) is the sole owner of child result indices.
    """
    root = Path(plan["task"]["workspace"])
    destination = Path(plan["destination"])
    cleanup = []
    generated = []
    verify_index = None
    try:
        recheck_approved_source_bytes(str(root), checked)
        _safe_path(destination, root, allow_missing=True)
        if os.path.lexists(destination) or not destination.parent.is_dir():
            raise ValueError("Package destination is occupied or parent changed")
        for descriptor in plan["operations"]:
            step_id, kind = descriptor["step_id"], descriptor["kind"]
            if kind == "create_directory":
                try:
                    _safe_path(destination, root, allow_missing=True)
                    anchored_mkdir(destination, root)
                    child = _result("create_folder", {"path": str(destination)})
                except (OSError, ValueError) as exc:
                    child = _result("create_folder", error=str(exc))
            elif kind == "copy":
                selected_index = descriptor["selected_file_index"]
                item = plan["selected_files"][selected_index]
                try:
                    recheck_approved_source_bytes(str(root), checked)
                except (OSError, ValueError) as exc:
                    child = _result("copy_file", error=str(exc))
                    record = {
                        "status": "not_attempted",
                        "reason": "Source revalidation failed before target creation",
                        "residual_state": "absent",
                    }
                else:
                    evidence = checked[bindings[selected_index]]
                    child, record = _copy_one(
                        Path(item["source"]["path"]),
                        Path(item["target"]),
                        item["snapshot"]["sha256"],
                        root,
                        (evidence["device"], evidence["inode"]),
                    )
                cleanup.append({"step_id": step_id, **record})
                if child["success"]:
                    generated.append(item["target"])
            elif kind == "write_report":
                report = plan["report"]
                try:
                    path = Path(report["path"])
                    _safe_path(path, root, allow_missing=True)
                    data = report["content"].encode("utf-8", "strict")
                    if hashlib.sha256(data).hexdigest() != report["sha256"]:
                        raise ValueError("Frozen Package report digest changed")
                    flags = (
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_BINARY", 0)
                        | getattr(os, "O_NOFOLLOW", 0)
                    )
                    fd = anchored_open(path, root, flags, 0o600)
                    try:
                        view = memoryview(data)
                        while view:
                            written = os.write(fd, view)
                            if written <= 0:
                                raise OSError("Package report made no write progress")
                            view = view[written:]
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    child = _result(
                        "write_package_report",
                        {"path": str(path), "sha256": _digest(path, root)},
                    )
                    generated.append(str(path))
                except (OSError, ValueError, UnicodeError) as exc:
                    child = _result("write_package_report", error=str(exc))
            else:
                child = _verify(plan, checked, root)
            index = append(step_id, child)
            if kind == "verify":
                verify_index = index
            if not child["success"]:
                raise ValueError(child["error"] or "Package child operation failed")
        return (
            _result(
                "build_package",
                {
                    "plan_id": plan["plan_id"],
                    "plan_sha256": plan_sha256,
                    "package_path": str(destination),
                    "generated_files": generated,
                    "report_path": plan["report"]["path"],
                    "verification_result_index": verify_index,
                },
            ),
            cleanup,
        )
    except (OSError, ValueError) as exc:
        return _result("build_package", error=str(exc)), cleanup
