"""Material plans must separate rule evidence from candidate evidence."""

import json
from pathlib import Path

import pytest

from fileforge.agent import ToolRouter, plan_task
from fileforge.agent.service import TaskConflict, TaskService


def _steps(workspace: str, *, package: bool = False) -> list[dict]:
    names = [
        ("search_files", {"workspace": workspace, "query": "通知"}),
        ("read_document", {}),
        ("extract_requirements", {}),
        ("detect_conflicts", {}),
        ("search_files", {"workspace": workspace, "query": "报名表"}),
        ("read_document", {}),
        ("match_requirements", {}),
    ]
    if package:
        names.append(("build_package", {}))
    return [
        {"tool": name, "description": name, "arguments": arguments}
        for name, arguments in names
    ]


@pytest.mark.parametrize(
    "remove",
    [
        "search_files",
        "read_document",
        "extract_requirements",
        "detect_conflicts",
        "match_requirements",
    ],
)
def test_material_planner_rejects_omitted_steps(tmp_path: Path, remove: str) -> None:
    steps = _steps(str(tmp_path))
    steps.pop(next(index for index, step in enumerate(steps) if step["tool"] == remove))
    with pytest.raises(ValueError, match="Material plan is missing or misorders"):
        plan_task(
            "task_001",
            "核对提交材料及通知要求",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_list_only_material_package_plan_is_rejected(tmp_path: Path) -> None:
    steps = [
        {
            "tool": "list_files",
            "description": "scan",
            "arguments": {"workspace": str(tmp_path)},
        }
    ]
    with pytest.raises(ValueError, match="Material plan"):
        plan_task(
            "task_001",
            "根据提交要求核对材料并打包",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_requirements_extraction_only_does_not_require_matching(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path))[:3]
    plan = plan_task(
        "task_001",
        "仅提取通知中的提交要求",
        str(tmp_path),
        generate=lambda _: json.dumps({"steps": steps}),
    )
    assert [step["tool"] for step in plan["steps"]] == [
        "search_files",
        "read_document",
        "extract_requirements",
    ]


def test_material_package_must_end_with_restricted_marker(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path), package=True)
    assert (
        plan_task(
            "task_001",
            "核对提交材料并打包",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )["steps"][-1]["tool"]
        == "build_package"
    )
    with pytest.raises(ValueError, match="end with build_package"):
        plan_task(
            "task_001",
            "核对提交材料并打包",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps[:-1]}),
        )


@pytest.mark.parametrize("index", [1, 2, 3, 5, 6])
def test_model_cannot_supply_material_evidence(tmp_path: Path, index: int) -> None:
    steps = _steps(str(tmp_path))
    steps[index]["arguments"] = (
        {"path": str(tmp_path / "invented.txt")}
        if steps[index]["tool"] == "read_document"
        else (
            {"documents": [{"text": "invented"}]}
            if steps[index]["tool"] != "match_requirements"
            else {"required_documents": ["invented"], "candidate_documents": []}
        )
    )
    with pytest.raises(ValueError, match="current Task results"):
        plan_task(
            "task_001",
            "核对提交材料",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_material_read_cannot_switch_collection_scope(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path))
    steps.insert(
        1,
        {
            "tool": "list_files",
            "description": "unrelated collection",
            "arguments": {"workspace": str(tmp_path)},
        },
    )
    with pytest.raises(ValueError, match="matching search results"):
        plan_task(
            "task_001",
            "核对提交材料",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_extra_read_cannot_supply_model_document(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path))
    steps.insert(
        2,
        {
            "tool": "read_document",
            "description": "invented rule",
            "arguments": {"path": str(tmp_path / "invented.txt")},
        },
    )
    with pytest.raises(ValueError, match="current Task results"):
        plan_task(
            "task_001",
            "核对提交材料",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_material_plan_rejects_model_supplied_version_evidence(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path))
    steps.insert(
        3,
        {
            "tool": "compare_versions",
            "description": "invented versions",
            "arguments": {"documents": [{"text": "invented"}]},
        },
    )
    with pytest.raises(ValueError, match="current Task results"):
        plan_task(
            "task_001",
            "核对提交材料",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_material_plan_rejects_direct_file_changes(tmp_path: Path) -> None:
    steps = _steps(str(tmp_path), package=True)
    steps.insert(
        -1,
        {
            "tool": "copy_file",
            "description": "bypass package preview",
            "arguments": {},
        },
    )
    with pytest.raises(ValueError, match="frozen preview"):
        plan_task(
            "task_001",
            "核对提交材料并打包",
            str(tmp_path),
            generate=lambda _: json.dumps({"steps": steps}),
        )


def test_runtime_uses_separate_successful_notice_and_candidate_reads(
    tmp_path: Path,
) -> None:
    (tmp_path / "通知.txt").write_text("报名必须提交报名表。", encoding="utf-8")
    (tmp_path / "补充通知.txt").write_text("申请人须提供报名表。", encoding="utf-8")
    (tmp_path / "报名表.txt").write_text("申请人资料", encoding="utf-8")
    observed = {}

    def extract_requirements(documents: list[dict]) -> dict:
        observed["rules"] = [document["filename"] for document in documents]
        return {
            "success": True,
            "tool": "extract_requirements",
            "data": {"required_documents": ["报名表"]},
            "message": "ok",
            "error": None,
        }

    def detect_conflicts(documents: list[dict]) -> dict:
        observed["conflicts"] = [document["filename"] for document in documents]
        return {
            "success": True,
            "tool": "detect_conflicts",
            "data": {"conflicts": []},
            "message": "ok",
            "error": None,
        }

    def match_requirements(
        required_documents: list[str], candidate_documents: list[dict]
    ) -> dict:
        observed["required"] = required_documents
        observed["candidates"] = [
            document["filename"] for document in candidate_documents
        ]
        return {
            "success": True,
            "tool": "match_requirements",
            "data": {
                "required_documents": required_documents,
                "matched": [],
                "missing": required_documents,
            },
            "message": "ok",
            "error": None,
        }

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return plan_task(
            task_id,
            goal,
            workspace,
            generate=lambda _: json.dumps({"steps": _steps(workspace)}),
        )

    router = ToolRouter(
        extra_tools={
            "extract_requirements": extract_requirements,
            "detect_conflicts": detect_conflicts,
            "match_requirements": match_requirements,
        }
    )
    service = TaskService(planner=planner, router=router)
    task = service.create("核对提交材料", str(tmp_path))
    service.run(task["task_id"])
    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed", snapshot["error"]
    assert observed == {
        "rules": ["补充通知.txt", "通知.txt"],
        "conflicts": ["补充通知.txt", "通知.txt"],
        "required": ["报名表"],
        "candidates": ["报名表.txt"],
    }
    calls = service._entry(task["task_id"])["execution"]["result_calls"]
    assert [call["tool"] for call in calls] == [
        "search_files",
        "read_document",
        "read_document",
        "extract_requirements",
        "detect_conflicts",
        "search_files",
        "read_document",
        "match_requirements",
    ]
    assert {doc["filename"] for doc in calls[3]["arguments"]["documents"]} == {
        "通知.txt",
        "补充通知.txt",
    }
    assert calls[-1]["arguments"]["candidate_documents"][0]["filename"] == "报名表.txt"


def test_unsupported_candidate_is_unanalyzed_not_missing(tmp_path: Path) -> None:
    (tmp_path / "通知.txt").write_text("报名必须提交报名表。", encoding="utf-8")
    (tmp_path / "报名表.bin").write_bytes(b"unsupported")

    def planner(task_id: str, goal: str, workspace: str) -> dict:
        return plan_task(
            task_id,
            goal,
            workspace,
            generate=lambda _: json.dumps({"steps": _steps(workspace)}),
        )

    service = TaskService(planner=planner)
    task = service.create("核对提交材料", str(tmp_path))
    service.run(task["task_id"])
    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert "unsupported files remain unanalyzed, not proven absent" in snapshot["error"]
    assert snapshot["results"][-1]["data"]["matches"][0]["filename"] == "报名表.bin"
    assert not any(
        result["tool"] == "match_requirements" for result in snapshot["results"]
    )
    with pytest.raises(TaskConflict):
        service.report(task["task_id"])
