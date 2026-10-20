"""Package preflight must use real, earlier Agent read results."""

from copy import deepcopy
from pathlib import Path

import pytest

from fileforge.agent.package_evidence import (
    collect_package_read_results,
    current_package_analysis,
)
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService


def _result(tool: str, data: dict | None, *, success: bool = True) -> dict:
    return {
        "tool": tool,
        "success": success,
        "data": data,
        "message": "done" if success else "failed",
        "error": None if success else "unreadable",
    }


def _call(index: int, tool: str, arguments: dict) -> dict:
    return {
        "result_index": index,
        "step_id": f"step_{index}",
        "tool": tool,
        "arguments": arguments,
    }


def _state() -> dict:
    workspace = Path.cwd() / "synthetic-workspace"
    notice = {
        "file_id": "notice-id",
        "path": str(workspace / "notice.txt"),
        "filename": "notice.txt",
        "metadata": {"source_revision": 1},
    }
    candidate = {
        "file_id": "candidate-id",
        "path": str(workspace / "candidate.txt"),
        "filename": "candidate.txt",
        "metadata": {},
    }
    return {
        "task_id": "task_001",
        "plan": {
            "task_id": "task_001",
            "steps": [
                {"step_id": "step_0", "tool": "read_document"},
                {"step_id": "step_1", "tool": "extract_requirements"},
                {"step_id": "step_2", "tool": "read_document"},
                {"step_id": "step_3", "tool": "match_requirements"},
            ],
        },
        "results": [
            _result("read_document", {"document": notice}),
            _result("extract_requirements", {"required_documents": ["Candidate"]}),
            _result("read_document", {"document": candidate}),
            _result("match_requirements", {"matched": [], "missing": []}),
        ],
        "result_calls": [
            _call(0, "read_document", {"path": notice["path"]}),
            _call(1, "extract_requirements", {"documents": [deepcopy(notice)]}),
            _call(2, "read_document", {"path": candidate["path"]}),
            _call(
                3,
                "match_requirements",
                {
                    "required_documents": ["Candidate"],
                    "candidate_documents": [deepcopy(candidate)],
                },
            ),
        ],
    }


def test_collects_notice_and_candidate_reads_in_result_order() -> None:
    state = _state()
    assert collect_package_read_results(state, task_id="task_001") == [
        (0, state["results"][0]),
        (2, state["results"][2]),
    ]


@pytest.mark.parametrize(
    "change",
    [
        lambda state: state["result_calls"][1]["arguments"]["documents"][0][
            "metadata"
        ].update(source_revision=1.0),
        lambda state: state["result_calls"][1]["arguments"]["documents"][0].update(
            extra=None
        ),
        lambda state: state["result_calls"][3]["arguments"].update(
            candidate_documents=[{"file_id": "forged"}]
        ),
        lambda state: state["result_calls"][1].update(result_index=3),
        lambda state: state["result_calls"][1].update(step_id="step_2"),
        lambda state: state["result_calls"][0]["arguments"].update(path="bad.txt"),
        lambda state: state["results"][0].update(success=False, data=None),
    ],
)
def test_rejects_forged_stale_or_failed_evidence(change) -> None:
    state = _state()
    change(state)
    with pytest.raises(ValueError):
        collect_package_read_results(state, task_id="task_001")


def test_analysis_cannot_use_document_read_later() -> None:
    state = _state()
    candidate = deepcopy(state["results"][2]["data"]["document"])
    state["result_calls"][1]["arguments"]["documents"] = [candidate]
    with pytest.raises(ValueError, match="earlier successful read"):
        collect_package_read_results(state, task_id="task_001")


def test_missing_call_record_blocks_package_preflight() -> None:
    state = _state()
    state["result_calls"].pop()
    with pytest.raises(ValueError, match="provenance is incomplete"):
        collect_package_read_results(state, task_id="task_001")


@pytest.mark.parametrize("field", ["task_id", "plan"])
def test_rejects_evidence_from_another_task_or_plan(field: str) -> None:
    state = _state()
    if field == "task_id":
        state["task_id"] = "task_other"
    else:
        state["plan"]["task_id"] = "task_other"
    with pytest.raises(ValueError, match="different task or plan"):
        collect_package_read_results(state, task_id="task_001")


def test_freezes_latest_analysis_result_and_marks_absent_tools() -> None:
    state = _state()
    analysis = current_package_analysis(state, task_id="task_001")
    assert analysis["extract_requirements"] == {
        "result_index": 1,
        "result": state["results"][1],
    }
    assert analysis["match_requirements"] == {
        "result_index": 3,
        "result": state["results"][3],
    }
    assert analysis["detect_conflicts"] is None
    assert analysis["compare_versions"] is None
    state["results"][1]["data"]["required_documents"].append("changed")
    assert analysis["extract_requirements"]["result"]["data"]["required_documents"] == [
        "Candidate"
    ]


def test_service_preflight_uses_authoritative_task_and_all_reads(
    tmp_path: Path,
) -> None:
    first = tmp_path / "notice.txt"
    second = tmp_path / "candidate.txt"
    first.write_text("Notice", encoding="utf-8")
    second.write_text("Candidate", encoding="utf-8")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "read_document",
                        "description": "Read notice",
                        "arguments": {"path": str(first)},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read candidate",
                        "arguments": {"path": str(second)},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task = service.create("Read sources", str(tmp_path))
    service.run(task["task_id"])
    assert service.snapshot(task["task_id"])["task"]["status"] == "completed"
    preflight = service._package_preflight(task["task_id"])
    assert list(preflight["checked"]) == [0, 1]
    assert {item["path"] for item in preflight["checked"].values()} == {
        str(first),
        str(second),
    }
    assert all(value is None for value in preflight["analysis"].values())

    second.write_text("Changed candidate", encoding="utf-8")
    with pytest.raises(ValueError, match="changed since analysis"):
        service._package_preflight(task["task_id"])
    failed_snapshot = service.snapshot(task["task_id"])
    assert failed_snapshot["task"]["status"] == "failed"
    assert failed_snapshot["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task["task_id"])


def test_service_preflight_rejects_cross_task_execution(tmp_path: Path) -> None:
    path = tmp_path / "notice.txt"
    path.write_text("Notice", encoding="utf-8")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "read_document",
                        "description": "Read notice",
                        "arguments": {"path": str(path)},
                    }
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task = service.create("Read notice", str(tmp_path))
    service.run(task["task_id"])
    service._tasks[task["task_id"]]["execution"]["plan"]["task_id"] = "other"
    with pytest.raises(ValueError, match="different task or plan"):
        service._package_preflight(task["task_id"])
    assert service.snapshot(task["task_id"])["task"]["status"] == "failed"

