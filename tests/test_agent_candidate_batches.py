"""Same-Task candidate batching with scan/read provenance and safe limits."""

from pathlib import Path

import pytest

from fileforge.agent import ToolRouter, validate_plan
from fileforge.agent.package_evidence import collect_package_read_results
from fileforge.agent.service import TaskConflict, TaskService


def _plan(*tools: str):
    def build(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": tool,
                        "description": f"Run {tool}",
                        "arguments": (
                            {"workspace": workspace} if tool == "list_files" else {}
                        ),
                    }
                    for tool in tools
                ]
            },
            task_id,
            goal,
        )

    return build


@pytest.fixture
def mixed_workspace_22(tmp_path: Path) -> Path:
    for index in range(20):
        (tmp_path / f"document_{index:02d}.txt").write_text(
            f"General document {index:02d} with readable content.",
            encoding="utf-8",
        )
    for index in range(2):
        (tmp_path / f"attachment_{index:02d}.bin").write_bytes(b"binary attachment")
    return tmp_path


def test_mixed_22_files_are_tracked_in_one_task(mixed_workspace_22: Path) -> None:
    service = TaskService(
        planner=_plan("list_files", "read_document", "extract_requirements")
    )
    task = service.create("Analyze the current workspace", str(mixed_workspace_22))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    state = service._entry(task["task_id"])["execution"]
    assert snapshot["task"]["status"] == "completed"
    assert len(snapshot["results"][0]["data"]["files"]) == 22
    assert len([r for r in snapshot["results"] if r["tool"] == "read_document"]) == 20
    assert snapshot["results"][-1]["tool"] == "extract_requirements"
    assert snapshot["results"][-1]["success"] is True
    assert len(state["candidate_ledger"]) == 22
    assert (
        sum(
            item["status"] == "unsupported_format" for item in state["candidate_ledger"]
        )
        == 2
    )
    reads = [
        item
        for item in state["candidate_ledger"]
        if item["read_result_index"] is not None
    ]
    assert len(reads) == 20
    assert {item["batch_index"] for item in reads} == {0, 1}
    for item in reads:
        index = item["read_result_index"]
        call = state["result_calls"][index]
        assert item["scan_result_index"] == 0
        assert call["result_index"] == index
        assert call["batch_index"] == item["batch_index"]
        assert call["batch_item_index"] == item["batch_item_index"]
        assert call["arguments"]["path"] == item["resolved_path"]
        assert item["status"] == "read_succeeded"
        assert item["analysis_status"] == "completed"
        assert item["analysis_results"] == [
            {
                "result_index": 21,
                "tool": "extract_requirements",
                "success": True,
                "error": None,
            }
        ]
    assert len(service.report(task["task_id"])["found_files"]) == 22
    assert len(collect_package_read_results(state, task_id=task["task_id"])) == 20


def test_22_readable_documents_use_three_bounded_batches(tmp_path: Path) -> None:
    for index in range(22):
        (tmp_path / f"source_{index:02d}.txt").write_text(
            "Readable source", encoding="utf-8"
        )
    service = TaskService(planner=_plan("list_files", "read_document"))
    task = service.create("Read every source", str(tmp_path))

    service.run(task["task_id"])

    state = service._entry(task["task_id"])["execution"]
    assert service.snapshot(task["task_id"])["task"]["status"] == "completed"
    assert [
        sum(item["batch_index"] == index for item in state["candidate_ledger"])
        for index in range(3)
    ] == [10, 10, 2]
    assert len([r for r in state["results"] if r["tool"] == "read_document"]) == 22


def test_failed_read_records_remaining_candidates_without_analysis(
    tmp_path: Path,
) -> None:
    for index in range(22):
        (tmp_path / f"source_{index:02d}.txt").write_text(
            " " if index == 12 else "Readable source", encoding="utf-8"
        )
    service = TaskService(
        planner=_plan("list_files", "read_document", "extract_requirements")
    )
    task = service.create("Analyze all sources", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    state = service._entry(task["task_id"])["execution"]
    assert snapshot["task"]["status"] == "failed"
    assert all(
        result["tool"] != "extract_requirements" for result in snapshot["results"]
    )
    ledger = state["candidate_ledger"]
    assert [item["status"] for item in ledger[:13]] == [
        *(["read_succeeded"] * 12),
        "read_failed",
    ]
    assert all(item["status"] == "not_read_after_failure" for item in ledger[13:])
    assert all(item["analysis_status"] == "not_run" for item in ledger)
    assert ledger[12]["read_result_index"] == 13
    assert ledger[12]["error"]
    assert snapshot["preview_id"] is None
    with pytest.raises(TaskConflict):
        service.report(task["task_id"])


def test_version_limit_is_not_reinterpreted_as_global_cross_batch_result(
    tmp_path: Path,
) -> None:
    for index in range(11):
        (tmp_path / f"source_{index:02d}.txt").write_text(
            "Readable source", encoding="utf-8"
        )
    service = TaskService(
        planner=_plan("list_files", "read_document", "compare_versions")
    )
    task = service.create("Compare all document versions", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "cross-batch version grouping is unavailable" in snapshot["error"]
    assert len([r for r in snapshot["results"] if r["tool"] == "read_document"]) == 11
    assert all(r["tool"] != "compare_versions" for r in snapshot["results"])
    with pytest.raises(TaskConflict):
        service.report(task["task_id"])


def test_analysis_failure_is_linked_to_every_supplied_document(tmp_path: Path) -> None:
    for index in range(12):
        (tmp_path / f"source_{index:02d}.txt").write_text(
            "Readable source", encoding="utf-8"
        )

    def fail_analysis(documents: list[dict]) -> dict:
        assert len(documents) == 12
        return {
            "success": False,
            "tool": "extract_requirements",
            "data": None,
            "message": "Analysis failed",
            "error": "Controlled analysis failure",
        }

    service = TaskService(
        planner=_plan("list_files", "read_document", "extract_requirements"),
        router=ToolRouter(extra_tools={"extract_requirements": fail_analysis}),
    )
    task = service.create("Analyze all sources", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    ledger = service._entry(task["task_id"])["execution"]["candidate_ledger"]
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1]["error"] == "Controlled analysis failure"
    assert all(item["status"] == "read_succeeded" for item in ledger)
    assert all(item["analysis_status"] == "failed" for item in ledger)
    assert all(
        item["analysis_results"][-1]["error"] == "Controlled analysis failure"
        for item in ledger
    )


def test_task_candidate_limit_rejects_whole_collection_before_reads(
    tmp_path: Path,
) -> None:
    for index in range(101):
        (tmp_path / f"source_{index:03d}.txt").write_text("Content", encoding="utf-8")
    service = TaskService(planner=_plan("list_files", "read_document"))
    task = service.create("Read all candidates", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "exceeds 100" in snapshot["error"]
    assert [result["tool"] for result in snapshot["results"]] == ["list_files"]


def test_duplicate_scan_snapshot_has_one_read_and_both_source_indices(
    tmp_path: Path,
) -> None:
    source = tmp_path / "document.txt"
    source.write_text("Content", encoding="utf-8")
    candidate = {
        "path": str(source),
        "filename": source.name,
        "size": source.stat().st_size,
    }

    def scan(workspace: str) -> dict:
        return {
            "success": True,
            "tool": "list_files",
            "data": {"files": [candidate, dict(candidate)]},
            "message": "Scanned",
            "error": None,
        }

    service = TaskService(
        planner=_plan("list_files", "read_document"),
        router=ToolRouter(extra_tools={"list_files": scan}),
    )
    task = service.create("Read candidates", str(tmp_path))

    service.run(task["task_id"])

    state = service._entry(task["task_id"])["execution"]
    assert service.snapshot(task["task_id"])["task"]["status"] == "completed"
    assert len(state["candidate_ledger"]) == 1
    assert state["candidate_ledger"][0]["scan_item_indices"] == [0, 1]
    assert len([r for r in state["results"] if r["tool"] == "read_document"]) == 1


def test_contradictory_scan_snapshot_stops_before_any_read(tmp_path: Path) -> None:
    source = tmp_path / "document.txt"
    source.write_text("Content", encoding="utf-8")

    def scan(workspace: str) -> dict:
        return {
            "success": True,
            "tool": "list_files",
            "data": {
                "files": [
                    {"path": str(source), "size": 7},
                    {"path": str(source), "size": 8},
                ]
            },
            "message": "Scanned",
            "error": None,
        }

    service = TaskService(
        planner=_plan("list_files", "read_document"),
        router=ToolRouter(extra_tools={"list_files": scan}),
    )
    task = service.create("Read candidates", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "contradictory snapshots" in snapshot["error"]
    assert [result["tool"] for result in snapshot["results"]] == ["list_files"]


def test_source_byte_limit_stops_before_any_read(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    with source.open("wb") as stream:
        stream.truncate(10 * 1024 * 1024 + 1)
    service = TaskService(planner=_plan("list_files", "read_document"))
    task = service.create("Read candidates", str(tmp_path))

    service.run(task["task_id"])

    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "source exceeds" in snapshot["error"]
    assert [result["tool"] for result in snapshot["results"]] == ["list_files"]
