"""Agent passes only read candidate Documents to public filename matching."""

from pathlib import Path

import pytest

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService
from fileforge.document import read_document


def _planner(
    *,
    candidate_query: str = "student",
    read_candidates: bool = True,
    include_extraction: bool = True,
):
    def plan(task_id: str, goal: str, workspace: str) -> dict:
        steps = [
            {
                "tool": "search_files",
                "description": "Find notice",
                "arguments": {"workspace": workspace, "query": "notice"},
            },
            {"tool": "read_document", "description": "Read notice", "arguments": {}},
        ]
        if include_extraction:
            steps.append(
                {
                    "tool": "extract_requirements",
                    "description": "Extract material names",
                    "arguments": {},
                }
            )
        steps.append(
            {
                "tool": "search_files",
                "description": "Find candidate materials",
                "arguments": {"workspace": workspace, "query": candidate_query},
            }
        )
        if read_candidates:
            steps.append(
                {
                    "tool": "read_document",
                    "description": "Read candidate materials",
                    "arguments": {},
                }
            )
        steps.append(
            {
                "tool": "match_requirements",
                "description": "Associate filenames with material names",
                "arguments": {},
            }
        )
        return validate_plan({"steps": steps}, task_id, goal)

    return plan


def test_match_uses_extracted_names_and_only_later_candidate_reads(
    tmp_path: Path,
) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "学生证.txt").write_text("Candidate material", encoding="utf-8")
    service = TaskService(planner=_planner(candidate_query="学生证"))
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert [result["tool"] for result in snapshot["results"]] == [
        "search_files",
        "read_document",
        "extract_requirements",
        "search_files",
        "read_document",
        "match_requirements",
    ]
    matching = snapshot["results"][-1]
    assert matching["success"] is True
    assert matching["data"]["required_documents"] == ["学生证"]
    assert matching["data"]["missing"] == []
    assert matching["data"]["matched"][0]["requirement"] == "学生证"
    assert [
        document["filename"] for document in matching["data"]["matched"][0]["documents"]
    ] == ["学生证.txt"]
    assert service.report(task_id)["missing_items"] == []
    assert "not reviewed" in service.report(task_id)["summary"]


def test_zero_candidate_collection_maps_all_requirements_to_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    service = TaskService(planner=_planner(read_candidates=False))
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][-2]["data"] == {"matches": []}
    assert snapshot["results"][-1]["data"] == {
        "required_documents": ["学生证"],
        "matched": [],
        "missing": ["学生证"],
    }
    assert service.report(task_id)["missing_items"] == ["学生证"]


def test_zero_candidate_read_is_skipped_before_matching(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    service = TaskService(planner=_planner())
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert [step["status"] for step in snapshot["plan"]["steps"]] == [
        "completed",
        "completed",
        "completed",
        "completed",
        "skipped",
        "completed",
    ]
    assert [result["tool"] for result in snapshot["results"]] == [
        "search_files",
        "read_document",
        "extract_requirements",
        "search_files",
        "match_requirements",
    ]
    assert snapshot["results"][-1]["data"]["missing"] == ["学生证"]
    assert service.report(task_id)["missing_items"] == ["学生证"]


def test_unread_candidate_files_are_not_reported_as_missing(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "student.txt").write_text("Candidate material", encoding="utf-8")
    service = TaskService(planner=_planner(read_candidates=False))
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1]["tool"] == "search_files"
    assert len(snapshot["results"][-1]["data"]["matches"]) == 1
    assert "Candidate documents are unresolved" in snapshot["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_reread_notice_is_not_a_candidate_material(tmp_path: Path) -> None:
    (tmp_path / "notice学生证.txt").write_text("必须提交学生证", encoding="utf-8")
    service = TaskService(planner=_planner(candidate_query="学生证"))
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert [result["tool"] for result in snapshot["results"]][-1] == "read_document"
    assert "Candidate documents are unresolved" in snapshot["error"]
    assert all(result["tool"] != "match_requirements" for result in snapshot["results"])


def test_no_extracted_requirements_is_distinct_from_matched_materials(
    tmp_path: Path,
) -> None:
    (tmp_path / "notice.txt").write_text("欢迎参加活动。", encoding="utf-8")
    service = TaskService(planner=_planner(read_candidates=False))
    task_id = service.create("Check material requirements", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert snapshot["results"][-1]["data"] == {
        "required_documents": [],
        "matched": [],
        "missing": [],
    }
    assert service.report(task_id)["summary"] == (
        "Analysis completed; requirement extraction returned no material names. "
        "Whether materials are required remains unverified; no package was built."
    )


def test_match_failure_stops_file_operations_and_report(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "student.txt").write_text("Candidate material", encoding="utf-8")
    destination = tmp_path / "must_not_be_created"

    def plan(task_id: str, goal: str, workspace: str) -> dict:
        payload = _planner()(task_id, goal, workspace)
        payload["steps"].append(
            {
                "tool": "create_folder",
                "description": "Create output folder",
                "arguments": {"path": str(destination)},
            }
        )
        return validate_plan(payload, task_id, goal)

    def failed_match(**kwargs: object) -> dict:
        return {
            "success": False,
            "tool": "match_requirements",
            "data": None,
            "message": "Requirement candidate matching failed",
            "error": "Contradictory candidate snapshot",
        }

    service = TaskService(
        planner=plan,
        router=ToolRouter({"match_requirements": failed_match}),
    )
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1] == {
        "success": False,
        "tool": "match_requirements",
        "data": None,
        "message": "Requirement candidate matching failed",
        "error": "Contradictory candidate snapshot",
    }
    assert snapshot["error"] == "Contradictory candidate snapshot"
    assert snapshot["pending_operations"] == []
    assert snapshot["preview_id"] is None
    assert not destination.exists()
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_public_match_validation_failure_is_retained(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "student.txt").write_text("Candidate material", encoding="utf-8")

    def inconsistent_read(path: str) -> dict:
        result = read_document(path)
        if Path(path).name == "student.txt":
            result["data"]["document"]["extension"] = ".docx"
        return result

    service = TaskService(
        planner=_planner(),
        router=ToolRouter({"read_document": inconsistent_read}),
    )
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][-1]["tool"] == "match_requirements"
    assert snapshot["results"][-1]["success"] is False
    assert snapshot["results"][-1]["data"] is None
    assert "extension does not match filename" in snapshot["error"]
    assert snapshot["error"] == snapshot["results"][-1]["error"]
    with pytest.raises(TaskConflict, match="Report is not available"):
        service.report(task_id)


def test_match_does_not_use_notice_or_invent_requirements(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")
    (tmp_path / "student.txt").write_text("Candidate material", encoding="utf-8")
    service = TaskService(planner=_planner(include_extraction=False))
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]

    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert "requires a completed requirement extraction" in snapshot["error"]
    assert all(result["tool"] != "match_requirements" for result in snapshot["results"])


def test_model_supplied_requirement_cannot_replace_extraction(tmp_path: Path) -> None:
    (tmp_path / "notice.txt").write_text("必须提交学生证", encoding="utf-8")

    def plan(task_id: str, goal: str, workspace: str) -> dict:
        payload = _planner(read_candidates=False)(task_id, goal, workspace)
        payload["steps"][-1]["arguments"] = {
            "required_documents": ["身份证"],
            "candidate_documents": [],
        }
        return validate_plan(payload, task_id, goal)

    service = TaskService(planner=plan)
    task_id = service.create("Find material candidates", str(tmp_path))["task_id"]
    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "failed"
    assert "must come from requirement extraction" in snapshot["error"]
    assert all(result["tool"] != "match_requirements" for result in snapshot["results"])


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"required_documents": [], "candidate_documents": [], "path": "x"}, "unknown"),
        ({"required_documents": []}, "missing argument"),
        ({"required_documents": [1], "candidate_documents": []}, "strings"),
        ({"required_documents": [], "candidate_documents": ["x"]}, "objects"),
    ],
)
def test_matching_plan_arguments_are_validated(arguments: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_plan(
            {
                "steps": [
                    {
                        "tool": "match_requirements",
                        "description": "Associate candidate filenames",
                        "arguments": arguments,
                    }
                ]
            },
            "task_test",
            "Match materials",
        )
