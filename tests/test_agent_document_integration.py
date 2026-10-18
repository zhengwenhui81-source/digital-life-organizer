"""Agent orchestration uses public Document results and keeps paths scoped."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService
from fileforge.document import read_document


def _planner(path: Path, *, compare: bool = False):
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        steps = [
            {
                "tool": "read_document",
                "description": "Read selected document",
                "arguments": {"path": str(path)},
            }
        ]
        if compare:
            steps.append(
                {
                    "tool": "compare_versions",
                    "description": "Compare selected documents",
                    "arguments": {},
                }
            )
        return validate_plan({"steps": steps}, task_id, goal)

    return plan


def _conflict_planner(path: Path, destination: Path | None = None):
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        steps = [
            {
                "tool": "read_document",
                "description": "Read notice",
                "arguments": {"path": str(path)},
            },
            {
                "tool": "detect_conflicts",
                "description": "Detect conflicting notices",
                "arguments": {},
            },
        ]
        if destination is not None:
            steps.append(
                {
                    "tool": "create_folder",
                    "description": "Create package after approval",
                    "arguments": {"path": str(destination)},
                }
            )
        return validate_plan({"steps": steps}, task_id, goal)

    return plan


def _notice_resolver(step: dict, results: list[dict]) -> dict:
    if step["tool"] == "detect_conflicts":
        return {"documents": [results[0]["data"]["document"]]}
    return step["arguments"]


def test_default_router_reads_document_into_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")
    service = TaskService(planner=_planner(source))
    task = service.create("Inspect notes", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][0]["tool"] == "read_document"
    assert snapshot["results"][0]["data"]["document"]["text"] == "Useful notes"


def test_default_router_compares_read_documents_without_a_custom_resolver(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")
    service = TaskService(planner=_planner(source, compare=True))
    task = service.create("Compare notes", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "read_document",
        "compare_versions",
    ]
    groups = snapshot["results"][1]["data"]["groups"]
    assert len(groups) == 1
    assert groups[0]["documents"] == [snapshot["results"][0]["data"]["document"]]
    assert groups[0]["newest_candidate"] is None
    assert service.report(task["task_id"])["version_groups"] == groups


def test_empty_candidate_collection_can_compare_successfully(tmp_path: Path) -> None:
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "list_files",
                        "description": "List candidate files",
                        "arguments": {"workspace": workspace},
                    },
                    {
                        "tool": "compare_versions",
                        "description": "Compare candidates",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=plan)
    task = service.create("Find versions", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][1]["success"] is True
    assert snapshot["results"][1]["data"] == {"groups": []}
    assert service.report(task["task_id"])["version_groups"] == []


def test_compare_without_candidate_collection_is_not_an_empty_result(
    tmp_path: Path,
) -> None:
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "compare_versions",
                        "description": "Compare candidates",
                        "arguments": {},
                    }
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=plan)
    task = service.create("Find versions", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "documents are unresolved" in snapshot["error"]
    assert snapshot["results"] == []


def test_read_failure_stops_before_comparison(tmp_path: Path) -> None:
    called = False

    def compare_versions(documents: list[dict]) -> dict:
        nonlocal called
        called = True
        return {
            "success": True,
            "tool": "compare_versions",
            "data": {"groups": []},
            "message": "Completed",
            "error": None,
        }

    service = TaskService(
        planner=_planner(tmp_path / "missing.txt", compare=True),
        router=ToolRouter({"compare_versions": compare_versions}),
    )
    task = service.create("Compare files", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]] == ["read_document"]
    assert "File not found" in snapshot["error"]
    assert not called


def test_resolver_passes_successful_documents_and_report_keeps_groups(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")
    received = []
    groups = [{"group_id": "version_group_001", "documents": []}]

    def compare_versions(documents: list[dict]) -> dict:
        received.extend(documents)
        return {
            "success": True,
            "tool": "compare_versions",
            "data": {"groups": groups},
            "message": "Completed",
            "error": None,
        }

    def resolve(step: dict, results: list[dict]) -> dict:
        if step["tool"] == "compare_versions":
            return {"documents": [results[0]["data"]["document"]]}
        return step["arguments"]

    service = TaskService(
        planner=_planner(source, compare=True),
        router=ToolRouter({"compare_versions": compare_versions}),
        resolver=resolve,
    )
    task = service.create("Compare files", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "read_document",
        "compare_versions",
    ]
    assert received[0]["path"] == str(source.resolve())
    assert service.report(task["task_id"])["version_groups"] == groups


def test_resolved_path_cannot_leave_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.txt"

    def resolve(step: dict, results: list[dict]) -> dict:
        return {"path": str(outside)}

    service = TaskService(planner=_planner(tmp_path / "inside.txt"), resolver=resolve)
    task = service.create("Read a file", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "escapes workspace" in snapshot["error"]
    assert snapshot["results"] == []


def test_resolved_document_cannot_leave_workspace(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")
    outside = tmp_path.parent / "outside.txt"
    called = False

    def compare_versions(documents: list[dict]) -> dict:
        nonlocal called
        called = True
        return {
            "success": True,
            "tool": "compare_versions",
            "data": {"groups": []},
            "message": "Completed",
            "error": None,
        }

    def resolve(step: dict, results: list[dict]) -> dict:
        if step["tool"] == "compare_versions":
            document = dict(results[0]["data"]["document"])
            document["path"] = str(outside)
            return {"documents": [document]}
        return step["arguments"]

    service = TaskService(
        planner=_planner(source, compare=True),
        router=ToolRouter({"compare_versions": compare_versions}),
        resolver=resolve,
    )
    task = service.create("Compare files", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "escapes workspace" in snapshot["error"]
    assert not called


def test_analysis_rejects_document_not_read_by_task(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")

    def resolve(step: dict, results: list[dict]) -> dict:
        if step["tool"] == "compare_versions":
            document = dict(results[0]["data"]["document"])
            document["text"] = "Invented content"
            return {"documents": [document]}
        return step["arguments"]

    service = TaskService(
        planner=_planner(source, compare=True),
        router=ToolRouter({"compare_versions": lambda documents: None}),
        resolver=resolve,
    )
    task = service.create("Compare files", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "successful read_document" in snapshot["error"]
    assert [result["tool"] for result in snapshot["results"]] == ["read_document"]


def test_unexpected_tool_error_is_retained_as_failure_result() -> None:
    def broken(documents: list[dict]) -> dict:
        raise RuntimeError("Comparison worker exited")

    result = ToolRouter({"compare_versions": broken}).call(
        "compare_versions", {"documents": []}
    )
    assert result == {
        "success": False,
        "tool": "compare_versions",
        "data": None,
        "message": "compare_versions failed",
        "error": "Comparison worker exited",
    }


def test_contradictory_read_snapshots_fail_before_file_operations(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("Useful notes", encoding="utf-8")
    destination = tmp_path / "package"
    reads = 0

    def changing_read(path: str) -> dict:
        nonlocal reads
        reads += 1
        result = deepcopy(read_document(path))
        if reads == 2:
            result["data"]["document"]["text"] = "Different notes"
        return result

    def plan(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "read_document",
                        "description": "Read first snapshot",
                        "arguments": {"path": str(source)},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read second snapshot",
                        "arguments": {"path": str(source)},
                    },
                    {
                        "tool": "compare_versions",
                        "description": "Compare snapshots",
                        "arguments": {},
                    },
                    {
                        "tool": "create_folder",
                        "description": "Create package after approval",
                        "arguments": {"path": str(destination)},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(
        planner=plan, router=ToolRouter({"read_document": changing_read})
    )
    task = service.create("Prepare package", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "read_document",
        "read_document",
        "compare_versions",
    ]
    failure = snapshot["results"][-1]
    assert failure["success"] is False
    assert failure["data"] is None
    assert "Contradictory Document snapshot" in failure["error"]
    assert snapshot["error"] == failure["error"]
    assert snapshot["pending_operations"] == []
    assert snapshot["preview_id"] is None
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task["task_id"])


def test_successful_conflicts_reach_snapshot_and_final_report(tmp_path: Path) -> None:
    source = tmp_path / "notice.txt"
    source.write_text("报名截止日期：2026年10月18日", encoding="utf-8")
    conflicts = [
        {
            "field": "deadline",
            "values": [{"value": "2026-10-18", "source": str(source)}],
            "recommendation": "请人工确认",
        }
    ]

    def detect_conflicts(documents: list[dict]) -> dict:
        assert [document["path"] for document in documents] == [str(source.resolve())]
        return {
            "success": True,
            "tool": "detect_conflicts",
            "data": {"conflicts": conflicts},
            "message": "Conflict detection completed",
            "error": None,
        }

    service = TaskService(
        planner=_conflict_planner(source),
        router=ToolRouter({"detect_conflicts": detect_conflicts}),
        resolver=_notice_resolver,
    )
    task = service.create("Check notice", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][-1]["data"]["conflicts"] == conflicts
    assert service.report(task["task_id"])["conflicts"] == conflicts


def test_failed_conflict_analysis_stops_before_package_and_report(
    tmp_path: Path,
) -> None:
    source = tmp_path / "notice.txt"
    source.write_text("报名截止日期：2026年10月18日", encoding="utf-8")
    destination = tmp_path / "package"

    def detect_conflicts(documents: list[dict]) -> dict:
        return {
            "success": False,
            "tool": "detect_conflicts",
            "data": None,
            "message": "Conflict detection failed",
            "error": "Contradictory Document snapshot for file_id file_001",
        }

    service = TaskService(
        planner=_conflict_planner(source, destination),
        router=ToolRouter({"detect_conflicts": detect_conflicts}),
        resolver=_notice_resolver,
    )
    task = service.create("Prepare package", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "read_document",
        "detect_conflicts",
    ]
    assert snapshot["results"][-1]["data"] is None
    assert snapshot["error"] == snapshot["results"][-1]["error"]
    assert snapshot["preview_id"] is None
    assert snapshot["pending_operations"] == []
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task["task_id"])
