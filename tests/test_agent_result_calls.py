"""Internal tool-call provenance for later Package evidence checks."""

from pathlib import Path

from fileforge.agent import ToolRouter, create_execution, execute, validate_plan


def _read_plan() -> dict:
    return validate_plan(
        {
            "steps": [
                {
                    "tool": "read_document",
                    "description": "Read sources",
                    "arguments": {},
                }
            ]
        },
        "task_001",
        "Read source documents",
    )


def test_result_calls_record_batch_arguments_and_indices(tmp_path: Path) -> None:
    plan = _read_plan()
    state = create_execution(plan)
    paths = [str(tmp_path / "notice.txt"), str(tmp_path / "candidate.txt")]

    def read_document(path: str) -> dict:
        return {
            "success": True,
            "tool": "read_document",
            "data": {"document": {"path": path}},
            "message": "read",
            "error": None,
        }

    calls = [{"path": path} for path in paths]
    execute(
        state,
        ToolRouter(extra_tools={"read_document": read_document}),
        resolver=lambda step, results: calls,
    )
    assert state["status"] == "completed"
    assert state["result_calls"] == [
        {
            "result_index": index,
            "step_id": plan["steps"][0]["step_id"],
            "tool": "read_document",
            "arguments": {"path": path},
        }
        for index, path in enumerate(paths)
    ]
    calls[0]["path"] = "changed-after-execution"
    assert state["result_calls"][0]["arguments"] == {"path": paths[0]}


def test_result_calls_keep_failed_call_without_later_calls(tmp_path: Path) -> None:
    state = create_execution(_read_plan())
    paths = [str(tmp_path / "bad.txt"), str(tmp_path / "later.txt")]

    def fail_read(path: str) -> dict:
        return {
            "success": False,
            "tool": "read_document",
            "data": None,
            "message": "failed",
            "error": "unreadable",
        }

    execute(
        state,
        ToolRouter(extra_tools={"read_document": fail_read}),
        resolver=lambda step, results: [{"path": path} for path in paths],
    )
    assert state["status"] == "failed"
    assert len(state["results"]) == len(state["result_calls"]) == 1
    assert state["result_calls"][0]["result_index"] == 0
    assert state["result_calls"][0]["arguments"] == {"path": paths[0]}
