"""A missing search hit cannot masquerade as document analysis success."""

from pathlib import Path

import pytest

from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService
from fileforge.tools.files import search_files


def _plan(query: str):
    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "search_files",
                        "description": "Find the notice",
                        "arguments": {"workspace": workspace, "query": query},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read the notice",
                        "arguments": {},
                    },
                    {
                        "tool": "extract_requirements",
                        "description": "Extract required materials",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    return planner


def test_zero_hit_stops_before_read_and_extraction(tmp_path: Path) -> None:
    (tmp_path / "unrelated.txt").write_text("必须提交学生证", encoding="utf-8")
    service = TaskService(planner=_plan("综合测评实施办法"))
    task_id = service.create("Read the named notice", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][0]["success"] is True
    assert snapshot["results"][0]["data"] == {"matches": []}
    assert len(snapshot["results"]) == 1
    assert [step["status"] for step in snapshot["plan"]["steps"]] == [
        "completed",
        "failed",
        "pending",
    ]
    assert "No matching document found" in snapshot["error"]
    assert "analysis was not performed" in snapshot["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_dash_fallback_reads_only_named_notice(tmp_path: Path) -> None:
    filename = "2025-2026学年机器人科学与工程学院本科生综合测评实施办法.txt"
    (tmp_path / filename).write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("必须提交身份证", encoding="utf-8")
    query = "2025—2026学年机器人科学与工程学院本科生综合测评实施办法"
    service = TaskService(planner=_plan(query))
    task_id = service.create("Extract requirements from the notice", str(tmp_path))[
        "task_id"
    ]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "search_files",
        "read_document",
        "extract_requirements",
    ]
    assert [item["filename"] for item in snapshot["results"][0]["data"]["matches"]] == [
        filename
    ]
    assert snapshot["results"][1]["data"]["document"]["filename"] == filename
    assert snapshot["results"][2]["data"] == {"required_documents": ["学生证"]}


def test_exact_hits_take_precedence_over_dash_fallback(tmp_path: Path) -> None:
    for name in ("2025—2026通知.txt", "2025-2026通知.txt"):
        (tmp_path / name).write_text("Notice", encoding="utf-8")

    result = search_files(str(tmp_path), "2025—2026通知")

    assert result["success"] is True
    assert [item["filename"] for item in result["data"]["matches"]] == [
        "2025—2026通知.txt"
    ]


def test_unreadable_candidates_do_not_become_empty_analysis(tmp_path: Path) -> None:
    (tmp_path / "notice.bin").write_bytes(b"Not a supported document")
    service = TaskService(planner=_plan("notice"))
    task_id = service.create("Analyze the notice", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]] == ["search_files"]
    assert snapshot["plan"]["steps"][1]["status"] == "failed"
    assert "No readable document found" in snapshot["error"]


def test_requirement_extraction_without_read_is_not_an_empty_result(
    tmp_path: Path,
) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "search_files",
                        "description": "Find the notice",
                        "arguments": {"workspace": workspace, "query": "notice"},
                    },
                    {
                        "tool": "extract_requirements",
                        "description": "Extract requirements",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task_id = service.create("Extract notice requirements", str(tmp_path))["task_id"]
    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]] == ["search_files"]
    assert snapshot["plan"]["steps"][1]["status"] == "failed"
    assert snapshot["error"] == (
        "No document was read; requirements were not extracted"
    )


def test_read_document_with_no_materials_reports_empty_extraction(
    tmp_path: Path,
) -> None:
    (tmp_path / "notice.txt").write_text("欢迎参加活动。", encoding="utf-8")
    service = TaskService(planner=_plan("notice"))
    task_id = service.create("Check notice materials", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][1]["tool"] == "read_document"
    assert snapshot["results"][1]["success"] is True
    assert snapshot["results"][2]["data"] == {"required_documents": []}
    assert service.report(task_id)["summary"] == (
        "Documents read; no material requirements found"
    )
