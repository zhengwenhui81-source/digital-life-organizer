"""TaskService binds D's read-only plan to one authenticated preview."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService


def _planner(notice: Path, material: Path):
    def make(task_id: str, goal: str, workspace: str) -> dict:
        def step(tool: str, arguments: dict) -> dict:
            return {
                "tool": tool,
                "description": tool,
                "arguments": arguments,
            }

        payload = {
            "steps": [
                step("read_document", {"path": str(notice)}),
                step("extract_requirements", {}),
                step("read_document", {"path": str(material)}),
                step("match_requirements", {}),
            ]
        }
        return validate_plan(payload, task_id, goal)

    return make


@pytest.fixture
def package_task(tmp_path: Path, monkeypatch):
    # Scope these tests to A's preview binding. D's Windows lstat/fstat ctime
    # compatibility is owned and tested separately; its pre-existing transient
    # failure must not make A's orchestration assertions nondeterministic.
    def stable_snapshot(path: Path, workspace: Path) -> dict:
        from fileforge.package._paths import scope

        scope(path, workspace)
        raw = path.read_bytes()
        return {
            "size": len(raw),
            "mtime_ns": path.stat().st_mtime_ns,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr("fileforge.package.planning.snapshot", stable_snapshot)
    notice = tmp_path / "通知.txt"
    notice.write_text("报名时必须提交报名表。", encoding="utf-8")
    material = tmp_path / "报名表.txt"
    material.write_text("张三的报名表草稿", encoding="utf-8")
    service = TaskService(planner=_planner(notice, material))
    task_id = service.create("准备报名材料包", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed", snapshot
    assert [result["tool"] for result in snapshot["results"]] == [
        "read_document",
        "extract_requirements",
        "read_document",
        "match_requirements",
    ]
    document = snapshot["results"][2]["data"]["document"]
    selected = [
        {
            "source": {key: document[key] for key in ("file_id", "path", "filename")},
            "requirements": snapshot["results"][1]["data"]["required_documents"],
            "reason": "当前分析中的单一文件候选，仍需同次预览审批",
        }
    ]
    return service, task_id, selected, tmp_path / "输出包", material


def test_read_only_package_preview_binds_current_evidence(package_task):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    assert preview["task"]["status"] == "awaiting_approval", preview["error"]
    assert preview["preview_id"].startswith("sha256:")
    assert preview["results"][-1]["tool"] == "plan_package"
    assert preview["results"][-1]["success"] is True
    plan = preview["results"][-1]["data"]["plan"]
    assert [step["tool"] for step in preview["pending_operations"]] == [
        "create_folder",
        "copy_file",
        "write_package_report",
        "verify_result",
    ]
    assert preview["pending_operations"][1]["arguments"] == {
        "source": str(material),
        "destination": str(destination / material.name),
    }
    assert service._tasks[task_id]["package_approval"]["plan_id"] == plan["plan_id"]
    assert service._tasks[task_id]["package_approval"]["plan_sha256"] == (
        preview["results"][-1]["data"]["plan_sha256"]
    )
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="not available"):
        service.decide(
            task_id, preview["preview_id"], approve=True, accept_incomplete=True
        )
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="analysis is not completed"):
        service.prepare_package(task_id, selected, str(destination))
    with pytest.raises(TaskConflict, match="specific risks"):
        service.decide(task_id, preview["preview_id"], approve=True)
    assert service.snapshot(task_id)["preview_id"] == preview["preview_id"]
    rejected = service.decide(task_id, preview["preview_id"], approve=False)
    assert rejected["task"]["status"] == "failed"
    assert rejected["preview_id"] is None
    with pytest.raises(TaskConflict, match="stale"):
        service.decide(task_id, preview["preview_id"], approve=True)
    assert not destination.exists()


def test_changed_source_fails_before_d_planning(package_task, monkeypatch):
    service, task_id, selected, destination, material = package_task
    material.write_text("文件已被改写", encoding="utf-8")

    def forbidden(**kwargs):
        raise AssertionError("D planning must not run after failed preflight")

    monkeypatch.setattr("fileforge.package.plan_package", forbidden)
    with pytest.raises(ValueError, match="changed"):
        service.prepare_package(task_id, selected, str(destination))
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["preview_id"] is None
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)
    assert not destination.exists()


def test_d_plan_snapshot_mismatch_fails_closed(package_task, monkeypatch):
    from fileforge.package import plan_package

    service, task_id, selected, destination, _ = package_task

    def changed_snapshot(**kwargs):
        result = deepcopy(plan_package(**kwargs))
        assert result["success"], result
        result["data"]["plan"]["selected_files"][0]["snapshot"]["sha256"] = "0" * 64
        # Keep the tampered manifest self-consistent: the separate A/D byte
        # cross-check, rather than only the plan digest, must reject it.
        canonical = json.dumps(
            {
                key: value
                for key, value in result["data"]["plan"].items()
                if key != "plan_id"
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        result["data"]["plan_sha256"] = (
            "sha256:" + hashlib.sha256(canonical).hexdigest()
        )
        return result

    monkeypatch.setattr("fileforge.package.plan_package", changed_snapshot)
    snapshot = service.prepare_package(task_id, selected, str(destination))
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1]["tool"] == "plan_package"
    assert snapshot["results"][-1]["success"] is False
    assert snapshot["results"][-1]["data"] is None
    assert snapshot["preview_id"] is None
    assert not destination.exists()


def test_d_planning_failure_stops_without_preview(package_task):
    service, task_id, selected, destination, _ = package_task
    destination.mkdir()
    snapshot = service.prepare_package(task_id, selected, str(destination))
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["preview_id"] is None
    assert snapshot["results"][-1]["tool"] == "plan_package"
    assert snapshot["results"][-1]["success"] is False
    assert snapshot["results"][-1]["data"] is None
    assert list(destination.iterdir()) == []
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)
