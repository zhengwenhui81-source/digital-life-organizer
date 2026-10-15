"""Execution pauses for approval and stops safely on tool failure."""

from __future__ import annotations

from pathlib import Path

from fileforge.agent import ToolRouter, create_execution, execute, reject, validate_plan


def _plan(workspace: Path) -> dict:
    return validate_plan(
        {"steps": [
            {"tool": "list_files", "description": "Inspect files",
             "arguments": {"workspace": str(workspace)}},
            {"tool": "copy_file", "description": "Copy chosen file",
             "arguments": {"source": str(workspace / "source.txt"),
                           "destination": str(workspace / "copy.txt")}},
        ]},
        "task_001", "Prepare package",
    )


def test_execution_pauses_then_resumes_after_approval(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("content")
    state = create_execution(_plan(tmp_path))
    execute(state, ToolRouter())
    assert state["status"] == "awaiting_approval"
    assert state["plan"]["steps"][0]["status"] == "completed"
    assert state["plan"]["steps"][1]["status"] == "awaiting_approval"
    assert len(state["results"]) == 1
    assert not (tmp_path / "copy.txt").exists()
    assert len(state["pending_operations"]) == 1

    execute(state, ToolRouter(), approve_all=True)
    assert state["status"] == "completed"
    assert len(state["results"]) == 2
    assert (tmp_path / "copy.txt").read_text() == "content"


def test_rejection_skips_file_operation(tmp_path: Path) -> None:
    (tmp_path / "source.txt").write_text("content")
    state = create_execution(_plan(tmp_path))
    execute(state, ToolRouter())
    reject(state)
    assert state["status"] == "failed"
    assert state["plan"]["steps"][1]["status"] == "skipped"
    assert not (tmp_path / "copy.txt").exists()


def test_failure_stops_later_steps(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    plan["steps"][0]["arguments"]["workspace"] = str(tmp_path / "missing")
    state = create_execution(plan)
    execute(state, ToolRouter(), approve_all=True)
    assert state["status"] == "failed"
    assert state["plan"]["steps"][0]["status"] == "failed"
    assert state["plan"]["steps"][1]["status"] == "pending"
    assert len(state["results"]) == 1


def test_router_rejects_unregistered_and_spoofed_approval() -> None:
    router = ToolRouter()
    assert not router.call("delete_file", {})["success"]
    result = router.call("copy_file", {"approved": True}, approved=True)
    assert not result["success"]
    assert "Approval cannot" in result["error"]


def test_results_are_available_to_argument_resolver(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("content")
    plan = _plan(tmp_path)
    plan["steps"][1]["arguments"] = {}
    state = create_execution(plan)

    def resolve(step: dict, results: list[dict]) -> dict:
        if step["tool"] == "list_files":
            return step["arguments"]
        assert results[0]["data"]["files"][0]["filename"] == "source.txt"
        return {"source": str(source), "destination": str(tmp_path / "copy.txt")}

    execute(state, ToolRouter(), approve_all=True, resolver=resolve)
    assert state["status"] == "completed"
    assert (tmp_path / "copy.txt").exists()
