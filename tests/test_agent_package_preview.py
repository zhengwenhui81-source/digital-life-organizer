"""TaskService binds D's read-only plan to one authenticated preview."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService


def _planner(
    notice: Path, material: Path, extra: Path | None = None, *, package: bool = False
):
    def make(task_id: str, goal: str, workspace: str) -> dict:
        def step(tool: str, arguments: dict) -> dict:
            return {
                "tool": tool,
                "description": tool,
                "arguments": arguments,
            }

        steps = [
            step("read_document", {"path": str(notice)}),
            step("extract_requirements", {}),
            step("read_document", {"path": str(material)}),
        ]
        if extra is not None:
            steps.append(step("read_document", {"path": str(extra)}))
        steps.append(step("match_requirements", {}))
        if package:
            steps.append(step("build_package", {}))
        payload = {"steps": steps}
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
    with pytest.raises(TaskConflict, match="specific risks"):
        service.decide(task_id, preview["preview_id"], approve=True)
    assert service.snapshot(task_id)["preview_id"] == preview["preview_id"]
    completed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert completed["task"]["status"] == "completed", completed["error"]
    assert (destination / material.name).read_bytes() == material.read_bytes()
    assert (destination / "PACKAGE_REPORT.md").is_file()
    assert (
        hashlib.sha256((destination / "PACKAGE_REPORT.md").read_bytes()).hexdigest()
        == plan["report"]["sha256"]
    )
    assert completed["package_execution"]["final_result_index"] is not None
    report = service.report(task_id)
    assert report["package_path"] == str(destination)
    assert report["missing_items"] == plan["missing"]
    assert report["package_unresolved"] == {
        "plan_id": plan["plan_id"],
        "plan_sha256": preview["results"][-1]["data"]["plan_sha256"],
        "items": plan["unresolved"],
    }
    assert [item["tool"] for item in report["operations"]] == [
        "create_folder",
        "copy_file",
        "write_package_report",
    ]
    with pytest.raises(TaskConflict, match="analysis is not completed"):
        service.prepare_package(task_id, selected, str(destination))
    with pytest.raises(TaskConflict, match="stale"):
        service.decide(task_id, preview["preview_id"], approve=True)
    assert destination.is_dir()


def test_controlled_package_plan_uses_existing_approval_http_api(package_task):
    from fastapi.testclient import TestClient

    from fileforge.api import agent
    from fileforge.api.server import app

    _, _, _, _, material = package_task
    notice = material.parent / "通知.txt"
    notice.write_text("所需材料：\n1. 报名表\n2. 学生证", encoding="utf-8")
    service = TaskService(planner=_planner(notice, material, package=True))
    task_id = service.create("整理材料并打包", str(material.parent))["task_id"]
    service.run(task_id)
    app.dependency_overrides[agent.get_service] = lambda: service
    try:
        with TestClient(app) as client:
            preview_response = client.get(f"/api/agent/tasks/{task_id}")
            assert preview_response.status_code == 200
            preview = preview_response.json()
            assert preview["task"]["status"] == "awaiting_approval", preview["error"]
            assert preview["results"][-1]["tool"] == "plan_package"
            assert not Path(
                preview["pending_operations"][0]["arguments"]["path"]
            ).exists()
            risk_pending = client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"preview_id": preview["preview_id"]},
            )
            assert risk_pending.status_code == 409
            assert (
                client.get(f"/api/agent/tasks/{task_id}").json()["preview_id"]
                == preview["preview_id"]
            )
            approval = client.post(
                f"/api/agent/tasks/{task_id}/approve",
                json={"preview_id": preview["preview_id"], "accept_incomplete": True},
            )
            assert approval.status_code == 200, approval.text
            completed = approval.json()
            assert completed["task"]["status"] == "completed", completed["error"]
            assert (
                material.parent / f"package_{task_id}" / material.name
            ).read_bytes() == material.read_bytes()
            report = client.get(f"/api/agent/tasks/{task_id}/report")
            assert report.status_code == 200, report.text
            assert report.json()["missing_items"] == ["学生证"]
            assert report.json()["package_path"] == str(
                material.parent / f"package_{task_id}"
            )
    finally:
        app.dependency_overrides.clear()


def test_ambiguous_filename_candidates_are_not_auto_selected(
    package_task, tmp_path: Path
):
    _, _, _, _, _ = package_task
    notice = tmp_path / "规则.txt"
    notice.write_text("所需材料：\n1. 报名表", encoding="utf-8")
    first = tmp_path / "报名表_v1.txt"
    second = tmp_path / "报名表_v2.txt"
    first.write_text("版本一", encoding="utf-8")
    second.write_text("版本二", encoding="utf-8")
    service = TaskService(planner=_planner(notice, first, second, package=True))
    task_id = service.create("打包材料", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert "No unambiguous material candidate" in snapshot["error"]
    assert snapshot["preview_id"] is None
    assert not (tmp_path / f"package_{task_id}").exists()
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_planner_cannot_supply_package_authority_or_precede_analysis(tmp_path: Path):
    notice = tmp_path / "规则.txt"
    notice.write_text("所需材料：\n1. 报名表", encoding="utf-8")
    material = tmp_path / "报名表.txt"
    material.write_text("内容", encoding="utf-8")
    with pytest.raises(ValueError, match="arguments must be empty"):
        validate_plan(
            {
                "steps": [
                    {
                        "tool": "build_package",
                        "description": "未经审批打包",
                        "arguments": {"task_id": "forged"},
                    }
                ]
            },
            "task_example",
            "打包",
        )

    def unsafe_order(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {"tool": "build_package", "description": "打包", "arguments": {}},
                    {
                        "tool": "read_document",
                        "description": "读取",
                        "arguments": {"path": str(notice)},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=unsafe_order)
    task_id = service.create("打包材料", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert "must follow completed read-only analysis" in snapshot["error"]
    assert snapshot["results"] == []
    assert not (tmp_path / f"package_{task_id}").exists()


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


def test_source_change_after_preview_fails_without_writes(package_task):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    assert preview["task"]["status"] == "awaiting_approval"
    material.write_text("审批前来源已改变", encoding="utf-8")
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert failed["results"][-1]["tool"] == "build_package"
    assert failed["results"][-1]["data"] is None
    assert failed["package_execution"]["operation_results"] == []
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_same_byte_source_replacement_after_preview_fails(package_task):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    original = material.stat()
    replacement = material.with_name("replacement.txt")
    replacement.write_bytes(material.read_bytes())
    os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
    os.replace(replacement, material)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert "differs from frozen preview" in failed["error"]
    assert failed["package_execution"]["operation_results"] == []
    assert not destination.exists()


def test_verification_failure_retains_writes_and_blocks_report(
    package_task, monkeypatch
):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    from fileforge.agent import package_execution

    monkeypatch.setattr(
        package_execution,
        "_verify",
        lambda *_: {
            "success": False,
            "tool": "verify_result",
            "data": None,
            "message": "verify_result failed",
            "error": "injected verification failure",
        },
    )
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert (destination / material.name).read_bytes() == material.read_bytes()
    assert (destination / "PACKAGE_REPORT.md").exists()
    assert failed["results"][-2]["tool"] == "verify_result"
    assert failed["results"][-1]["tool"] == "build_package"
    assert failed["results"][-1]["data"] is None
    assert (
        failed["package_execution"]["final_result_index"] == len(failed["results"]) - 1
    )
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_changed_pending_preview_cannot_consume_approval(package_task):
    service, task_id, selected, destination, _ = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    with service._lock:
        service._tasks[task_id]["execution"]["pending_operations"][1]["arguments"][
            "destination"
        ] = str(destination / "different.txt")
    with pytest.raises(TaskConflict, match="not bound"):
        service.decide(
            task_id, preview["preview_id"], approve=True, accept_incomplete=True
        )
    assert service.snapshot(task_id)["preview_id"] == preview["preview_id"]
    assert not destination.exists()


def test_report_mapping_failure_marks_build_failed(package_task, monkeypatch):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))

    def fail_mapping(*_):
        raise ValueError("injected report provenance mismatch")

    monkeypatch.setattr(service, "_package_report", fail_mapping)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert (destination / material.name).read_bytes() == material.read_bytes()
    assert failed["task"]["status"] == "failed"
    assert failed["results"][-1]["tool"] == "build_package"
    assert failed["results"][-1]["data"] is None
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_occupied_destination_after_preview_is_preserved(package_task):
    service, task_id, selected, destination, _ = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    destination.mkdir()
    occupant = destination / "keep.txt"
    occupant.write_text("existing", encoding="utf-8")
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert failed["results"][-1]["data"] is None
    assert occupant.read_text(encoding="utf-8") == "existing"


def test_partial_copy_failure_retains_actual_results(tmp_path: Path, monkeypatch):
    notice = tmp_path / "通知.txt"
    notice.write_text("必须提交报名表。", encoding="utf-8")
    first = tmp_path / "报名表.txt"
    first.write_text("报名表内容", encoding="utf-8")
    second = tmp_path / "补充说明.txt"
    second.write_text("补充说明内容", encoding="utf-8")
    service = TaskService(planner=_planner(notice, first, second))
    task_id = service.create("准备材料包", str(tmp_path))["task_id"]
    service.run(task_id)
    assert service.snapshot(task_id)["task"]["status"] == "completed"
    reads = [
        r["data"]["document"]
        for r in service.snapshot(task_id)["results"]
        if r["tool"] == "read_document"
    ]
    selected = [
        {
            "source": {key: doc[key] for key in ("file_id", "path", "filename")},
            "requirements": [],
            "reason": "待用户确认的附加材料",
        }
        for doc in reads[1:]
    ]
    from fileforge.package import planning

    def stable_snapshot(path: Path, workspace: Path) -> dict:
        raw = path.read_bytes()
        return {
            "size": len(raw),
            "mtime_ns": path.stat().st_mtime_ns,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(planning, "snapshot", stable_snapshot)
    destination = tmp_path / "材料包"
    preview = service.prepare_package(task_id, selected, str(destination))
    assert preview["task"]["status"] == "awaiting_approval", preview["error"]
    from fileforge.agent import package_execution

    real_copy = package_execution._copy_one

    def fail_second(source, target, expected, root, source_identity):
        if source == second:
            return (
                {
                    "success": False,
                    "tool": "copy_file",
                    "data": None,
                    "message": "copy_file failed",
                    "error": "injected copy interruption",
                },
                {
                    "status": "not_attempted",
                    "reason": "ownership_uncertain",
                    "residual_state": "unknown",
                },
            )
        return real_copy(source, target, expected, root, source_identity)

    monkeypatch.setattr(package_execution, "_copy_one", fail_second)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert (destination / first.name).read_bytes() == first.read_bytes()
    assert not (destination / second.name).exists()
    assert not (destination / "PACKAGE_REPORT.md").exists()
    mapping = failed["package_execution"]
    assert len(mapping["operation_results"]) == 3
    assert [item["status"] for item in mapping["cleanup_results"]] == [
        "not_attempted",
        "not_attempted",
    ]
    assert mapping["cleanup_results"][1]["residual_state"] == "unknown"
    assert failed["results"][mapping["final_result_index"]]["data"] is None
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_failed_copy_retains_owned_unverified_target(package_task, monkeypatch):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    from fileforge.agent import package_execution

    actual_digest = package_execution._digest

    def fail_target_check(path: Path, root: Path) -> str:
        if path == destination / material.name:
            raise ValueError("injected target verification error")
        return actual_digest(path, root)

    monkeypatch.setattr(package_execution, "_digest", fail_target_check)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert (destination / material.name).exists()
    assert not (destination / "PACKAGE_REPORT.md").exists()
    assert failed["results"][-2]["tool"] == "copy_file"
    assert failed["results"][-2]["data"] is None
    assert failed["package_execution"]["cleanup_results"] == [
        {
            "step_id": "package_002",
            "status": "not_attempted",
            "reason": "Failed copy target retained; conditional unlink is unsafe",
            "residual_state": "owned_fragment",
        }
    ]
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


def test_report_write_failure_retains_copy_and_blocks_success(
    package_task, monkeypatch
):
    service, task_id, selected, destination, material = package_task
    preview = service.prepare_package(task_id, selected, str(destination))
    from fileforge.agent import package_execution

    actual_open = package_execution.anchored_open

    def deny_report(path, root, flags, *args, **kwargs):
        if Path(path).name == "PACKAGE_REPORT.md":
            raise PermissionError("injected report write denial")
        return actual_open(path, root, flags, *args, **kwargs)

    monkeypatch.setattr(package_execution, "anchored_open", deny_report)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    assert (destination / material.name).read_bytes() == material.read_bytes()
    assert not (destination / "PACKAGE_REPORT.md").exists()
    assert [item["tool"] for item in failed["results"][-3:]] == [
        "copy_file",
        "write_package_report",
        "build_package",
    ]
    assert failed["results"][-2]["data"] is None
    assert failed["results"][-1]["data"] is None
    with pytest.raises(TaskConflict, match="not available"):
        service.report(task_id)


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


def test_copy_preflight_change_after_first_copy_records_failed_child(
    tmp_path: Path, monkeypatch
):
    notice = tmp_path / "notice.txt"
    notice.write_text("需要报名表和说明。", encoding="utf-8")
    first = tmp_path / "报名表.txt"
    first.write_text("报名表", encoding="utf-8")
    second = tmp_path / "说明.txt"
    second.write_text("说明", encoding="utf-8")
    service = TaskService(planner=_planner(notice, first, second))
    task_id = service.create("打包两份文件", str(tmp_path))["task_id"]
    service.run(task_id)
    snapshot = service.snapshot(task_id)
    reads = [
        r["data"]["document"]
        for r in snapshot["results"]
        if r["tool"] == "read_document"
    ]
    selected = [
        {
            "source": {key: doc[key] for key in ("file_id", "path", "filename")},
            "requirements": [],
            "reason": "selected for same-preview approval",
        }
        for doc in reads[1:]
    ]
    from fileforge.package import planning

    def stable_snapshot(path, workspace):
        raw = path.read_bytes()
        return {
            "size": len(raw),
            "mtime_ns": path.stat().st_mtime_ns,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    monkeypatch.setattr(planning, "snapshot", stable_snapshot)
    destination = tmp_path / "out"
    preview = service.prepare_package(task_id, selected, str(destination))
    assert preview["task"]["status"] == "awaiting_approval", preview["error"]
    from fileforge.agent import package_execution

    original_copy = package_execution._copy_one

    def change_after_first(source, target, expected, root, source_identity):
        result = original_copy(source, target, expected, root, source_identity)
        if source == first and result[0]["success"]:
            second.write_text("已经修改", encoding="utf-8")
        return result

    monkeypatch.setattr(package_execution, "_copy_one", change_after_first)
    failed = service.decide(
        task_id, preview["preview_id"], approve=True, accept_incomplete=True
    )
    assert failed["task"]["status"] == "failed"
    records = failed["package_execution"]["operation_results"]
    assert [failed["results"][r["result_index"]]["tool"] for r in records] == [
        "create_folder",
        "copy_file",
        "copy_file",
    ]
    assert failed["results"][records[-1]["result_index"]]["success"] is False
    cleanup = failed["package_execution"]["cleanup_results"]
    assert cleanup[-1] == {
        "step_id": "package_003",
        "status": "not_attempted",
        "reason": "Source revalidation failed before target creation",
        "residual_state": "absent",
    }
    assert not (destination / second.name).exists()
    assert (destination / first.name).exists()


def test_package_anchored_create_write_and_entries(tmp_path: Path):
    import os

    from fileforge.agent.package_fs import (
        anchored_mkdir,
        anchored_open,
        guarded_entries,
    )

    root = tmp_path / "workspace"
    root.mkdir()
    destination = root / "bundle"
    anchored_mkdir(destination, root)
    file = destination / "report.txt"
    fd = anchored_open(file, root, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        os.write(fd, b"frozen")
    finally:
        os.close(fd)
    assert file.read_bytes() == b"frozen"
    assert guarded_entries(destination, root) == {"report.txt"}
    with pytest.raises(FileExistsError):
        anchored_open(file, root, os.O_WRONLY | os.O_CREAT | os.O_EXCL)


def test_package_anchored_open_rejects_parent_symlink(tmp_path: Path):
    import os

    from fileforge.agent.package_fs import anchored_open

    root = tmp_path / "workspace"
    root.mkdir()
    other = tmp_path / "outside"
    other.mkdir()
    (other / "outside.txt").write_text("safe", encoding="utf-8")
    link = root / "link"
    try:
        link.symlink_to(other, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating directory symlinks is unavailable here")
    with pytest.raises((OSError, ValueError)):
        anchored_open(link / "outside.txt", root, os.O_RDONLY)
    assert (other / "outside.txt").read_text(encoding="utf-8") == "safe"


def test_posix_parent_retarget_cannot_redirect_anchored_file(
    tmp_path: Path, monkeypatch
):
    import os

    from fileforge.agent import package_fs

    if os.name == "nt":
        pytest.skip("POSIX dir_fd test")
    root = tmp_path / "workspace"
    root.mkdir()
    parent = root / "parent"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = parent / "protected.txt"
    real_open = os.open
    changed = False

    def swap_during_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal changed
        if path == "protected.txt" and dir_fd is not None and not changed:
            changed = True
            parent.rename(root / "retired")
            parent.symlink_to(outside, target_is_directory=True)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(package_fs.os, "open", swap_during_open)
    fd = package_fs.anchored_open(target, root, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    try:
        os.write(fd, b"anchored")
    finally:
        os.close(fd)
    assert (root / "retired" / "protected.txt").read_bytes() == b"anchored"
    assert not (outside / "protected.txt").exists()


def test_windows_relative_handle_cannot_follow_parent_retarget(tmp_path: Path):
    import os

    if os.name != "nt":
        pytest.skip("Windows native handle test")

    import msvcrt

    from fileforge.agent.package_fs import _parent, _win_relative

    root = tmp_path / "workspace"
    root.mkdir()
    parent = root / "parent"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    with _parent(parent / "new.txt", root, writing=True) as pinned:
        try:
            parent.rename(root / "moved")
            parent.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip("Windows does not allow parent replacement in this environment")
        handle = _win_relative(pinned, "new.txt", directory=False, create=True)
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        try:
            os.write(fd, b"anchored")
        finally:
            os.close(fd)
    assert (root / "moved" / "new.txt").read_bytes() == b"anchored"
    assert not (outside / "new.txt").exists()
