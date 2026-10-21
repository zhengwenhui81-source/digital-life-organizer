"""Validate and freeze a read-only Package plan for the Agent approval gate."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from copy import deepcopy
from pathlib import Path
from typing import Any

from fileforge.agent.package_evidence import (
    _json_shape,
    _same_document,
    bind_selected_snapshots,
)


def freeze_package_preview(
    task: dict[str, Any],
    analysis: dict[str, Any],
    checked: dict[int, dict[str, Any]],
    result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Return frozen plan, selection bindings and concrete preview operations.

    This is a read-only boundary. The returned operation descriptions are not
    executable authority; only the later same-preview approval can grant that.
    """
    if (
        type(result) is not dict
        or result.get("tool") != "plan_package"
        or result.get("success") is not True
        or result.get("error") is not None
        or type(result.get("data")) is not dict
        or set(result["data"]) != {"plan", "plan_sha256"}
        or not _json_shape(result)
    ):
        raise ValueError("Package planning did not return a valid successful result")
    plan = result["data"]["plan"]
    digest = result["data"]["plan_sha256"]
    if (
        type(plan) is not dict
        or set(plan)
        != {
            "task",
            "destination",
            "selected_files",
            "analysis",
            "missing",
            "unresolved",
            "report",
            "operations",
            "verification_targets",
            "plan_id",
        }
        or type(digest) is not str
        or type(plan.get("plan_id")) is not str
        or not plan["plan_id"].startswith("package_plan_")
        or len(plan["plan_id"]) != 45
        or any(char not in "0123456789abcdef" for char in plan["plan_id"][13:])
        or not _same_document(plan.get("task"), task)
        or not _same_document(plan.get("analysis"), analysis)
    ):
        raise ValueError("Package plan does not match this task and its analysis")
    canonical = json.dumps(
        {key: value for key, value in plan.items() if key != "plan_id"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", "strict")
    if digest != "sha256:" + hashlib.sha256(canonical).hexdigest():
        raise ValueError("Package plan digest does not match frozen content")
    report = plan.get("report")
    if (
        type(report) is not dict
        or set(report) != {"path", "content", "sha256"}
        or type(report["content"]) is not str
        or "\r" in report["content"]
        or report["sha256"]
        != hashlib.sha256(report["content"].encode("utf-8", "strict")).hexdigest()
    ):
        raise ValueError("Package report differs from its frozen bytes")
    bindings = bind_selected_snapshots(plan, checked)
    selected = plan["selected_files"]
    if not selected:
        raise ValueError("Package preview needs at least one proposed file")
    destination = plan.get("destination")
    root = Path(task["workspace"])
    if (
        type(destination) is not str
        or not Path(destination).is_absolute()
        or ".." in Path(destination).parts
        or not Path(destination).is_relative_to(root)
        or Path(destination) == root
        or not Path(destination).parent.is_dir()
        or os.path.lexists(destination)
        or type(plan.get("missing")) is not list
        or type(plan.get("unresolved")) is not list
        or type(plan.get("operations")) is not list
        or report["path"] != str(Path(destination) / "PACKAGE_REPORT.md")
    ):
        raise ValueError("Package plan has invalid preview paths or risks")
    for ancestor in (root, *reversed(Path(destination).parents), Path(destination)):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Package preview path contains a link")
    for item in selected:
        source = item.get("source") if type(item) is dict else None
        if (
            type(source) is not dict
            or type(source.get("filename")) is not str
            or Path(source["filename"]).name != source["filename"]
            or item.get("target") != str(Path(destination) / source["filename"])
        ):
            raise ValueError("Package selected target differs from frozen directory")
    targets = plan.get("verification_targets")
    if (
        type(targets) is not dict
        or set(targets)
        != {"selected_file_indices", "report", "exact_directory_entries"}
        or type(targets["selected_file_indices"]) is not list
        or any(type(index) is not int for index in targets["selected_file_indices"])
        or targets["selected_file_indices"] != list(range(len(selected)))
        or targets["report"] is not True
        or targets["exact_directory_entries"] is not True
    ):
        raise ValueError("Package verification targets are incomplete")
    descriptors = plan["operations"]
    kinds = [item.get("kind") if type(item) is dict else None for item in descriptors]
    if kinds != [
        "create_directory",
        *(["copy"] * len(selected)),
        "write_report",
        "verify",
    ]:
        raise ValueError("Package plan has unexpected operation order")
    operations = []
    for index, descriptor in enumerate(descriptors, 1):
        step_id = f"package_{index:03d}"
        kind = descriptor["kind"]
        expected_keys = (
            {"step_id", "kind", "selected_file_index"}
            if kind == "copy"
            else {"step_id", "kind"}
        )
        if set(descriptor) != expected_keys or descriptor.get("step_id") != step_id:
            raise ValueError("Package plan operation descriptor is invalid")
        if kind == "create_directory":
            tool, arguments, risk = "create_folder", {"path": destination}, "medium"
        elif kind == "copy":
            selected_index = index - 2
            if (
                type(descriptor["selected_file_index"]) is not int
                or descriptor["selected_file_index"] != selected_index
            ):
                raise ValueError("Package copy selection index is invalid")
            item = selected[selected_index]
            tool = "copy_file"
            arguments = {
                "source": item["source"]["path"],
                "destination": item["target"],
            }
            risk = "medium"
        elif kind == "write_report":
            tool = "write_package_report"
            arguments = {
                "task_id": task["task_id"],
                "plan_id": plan["plan_id"],
                "plan_sha256": digest,
            }
            risk = "medium"
        else:
            tool = "verify_result"
            arguments = {
                "task_id": task["task_id"],
                "workspace": task["workspace"],
                "expected": plan["verification_targets"],
            }
            risk = "low"
        operations.append(
            {
                "step_id": step_id,
                "tool": tool,
                "description": f"Package {kind}",
                "risk": risk,
                "status": "awaiting_approval",
                "arguments": arguments,
            }
        )
    return deepcopy(plan), deepcopy(bindings), operations
