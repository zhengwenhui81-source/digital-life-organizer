"""Agent orchestration uses public Document results and keeps paths scoped."""

from __future__ import annotations

from pathlib import Path

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService


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
