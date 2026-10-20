"""Search-discovered files remain visible in the completed Agent report."""

from pathlib import Path

from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService


def test_search_then_read_reports_found_files(tmp_path: Path) -> None:
    for name in ("notice_alpha.txt", "notice_beta.txt"):
        (tmp_path / name).write_text("Application deadline: 2026-11-01")
    (tmp_path / "unrelated.txt").write_text("Other file")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "search_files",
                        "description": "Find notices",
                        "arguments": {"workspace": workspace, "query": "notice"},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read matching notices",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task_id = service.create("Find and read notices", str(tmp_path))["task_id"]
    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "search_files",
        "read_document",
        "read_document",
    ]
    expected = snapshot["results"][0]["data"]["matches"]
    assert {item["filename"] for item in expected} == {
        "notice_alpha.txt",
        "notice_beta.txt",
    }
    report = service.report(task_id)
    assert report["found_files"] == expected
    assert report["operations"] == []


def test_list_and_search_count_each_file_once(tmp_path: Path) -> None:
    for name in ("notice.txt", "material.txt", "other.txt", "notes.docx"):
        (tmp_path / name).write_text("fixture", encoding="utf-8")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "list_files",
                        "description": "Scan workspace",
                        "arguments": {"workspace": workspace},
                    },
                    {
                        "tool": "search_files",
                        "description": "Search text files",
                        "arguments": {"workspace": workspace, "query": ".txt"},
                    },
                    {
                        "tool": "search_files",
                        "description": "Search notice again",
                        "arguments": {"workspace": workspace, "query": "notice"},
                    },
                ]
            },
            task_id,
            goal,
        )

    service = TaskService(planner=planner)
    task_id = service.create("Find files", str(tmp_path))["task_id"]
    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert len(snapshot["results"][0]["data"]["files"]) == 4
    assert len(snapshot["results"][1]["data"]["matches"]) == 3
    assert len(snapshot["results"][2]["data"]["matches"]) == 1
    found = service.report(task_id)["found_files"]
    assert len(found) == 4
    assert [item["path"] for item in found] == [
        item["path"] for item in snapshot["results"][0]["data"]["files"]
    ]
