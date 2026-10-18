"""Approved operations need disk evidence before a completed report exists."""

from pathlib import Path

import pytest

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService


def _plan(task_id: str, goal: str, workspace: str) -> dict:
    return validate_plan(
        {
            "steps": [
                {
                    "tool": "copy_file",
                    "description": "Copy source",
                    "arguments": {
                        "source": str(Path(workspace) / "source.txt"),
                        "destination": str(Path(workspace) / "copy.txt"),
                    },
                },
            ]
        },
        task_id,
        goal,
    )


def _operation_plan(*operations: tuple[str, dict[str, str]]):
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": tool,
                        "description": tool,
                        "arguments": arguments,
                    }
                    for tool, arguments in operations
                ]
            },
            task_id,
            goal,
        )

    return plan


def test_approved_copy_is_verified_before_report(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("source")
    service = TaskService(planner=_plan)
    task_id = service.create("copy", str(tmp_path))["task_id"]
    service.run(task_id)
    preview = service.snapshot(task_id)["preview_id"]
    snapshot = service.decide(task_id, preview, approve=True)
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][-1]["tool"] == "verify_result"
    assert snapshot["results"][-1]["data"]["passed"] is True
    report = service.report(task_id)
    assert report["status"] == "completed"
    assert "verified" in report["summary"]


def test_approved_folder_and_move_are_verified(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source")
    folder = tmp_path / "organized"
    destination = folder / "source.txt"
    planner = _operation_plan(
        ("create_folder", {"path": str(folder)}),
        ("move_file", {"source": str(source), "destination": str(destination)}),
    )
    service = TaskService(planner=planner)
    task_id = service.create("organize", str(tmp_path))["task_id"]
    service.run(task_id)
    preview = service.snapshot(task_id)["preview_id"]
    snapshot = service.decide(task_id, preview, approve=True)
    assert snapshot["task"]["status"] == "completed"
    assert [check["kind"] for check in snapshot["results"][-1]["data"]["checks"]] == [
        "create_folder",
        "move_file",
    ]
    assert destination.read_text() == "source"
    assert not source.exists()


def test_success_claim_with_wrong_contents_fails_verification(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("source")

    def false_copy(source: str, destination: str, *, approved: bool = False) -> dict:
        assert approved
        Path(destination).write_text("wrong content")
        return {
            "success": True,
            "tool": "copy_file",
            "data": {
                "source": source,
                "destination": destination,
            },
            "message": "copy_file completed",
            "error": None,
        }

    service = TaskService(planner=_plan, router=ToolRouter({"copy_file": false_copy}))
    task_id = service.create("copy", str(tmp_path))["task_id"]
    service.run(task_id)
    preview = service.snapshot(task_id)["preview_id"]
    snapshot = service.decide(task_id, preview, approve=True)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1]["tool"] == "verify_result"
    assert snapshot["results"][-1]["success"] is False
    assert snapshot["results"][-1]["data"] is None
    assert snapshot["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_partially_completed_operations_do_not_produce_report(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("source")
    first = tmp_path / "first.txt"
    occupied = tmp_path / "occupied.txt"
    occupied.write_text("keep")
    planner = _operation_plan(
        ("copy_file", {"source": str(source), "destination": str(first)}),
        ("copy_file", {"source": str(source), "destination": str(occupied)}),
    )
    service = TaskService(planner=planner)
    task_id = service.create("copy twice", str(tmp_path))["task_id"]
    service.run(task_id)
    preview = service.snapshot(task_id)["preview_id"]
    snapshot = service.decide(task_id, preview, approve=True)
    assert snapshot["task"]["status"] == "failed"
    assert first.read_text() == "source"
    assert occupied.read_text() == "keep"
    assert snapshot["results"][-1]["tool"] == "copy_file"
    assert snapshot["results"][-1]["success"] is False
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)
