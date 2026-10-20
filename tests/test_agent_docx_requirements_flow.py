"""Controlled four-DOCX flow isolates Agent selection from extraction logic."""

from copy import deepcopy
from pathlib import Path

from docx import Document as WordDocument

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskService
from fileforge.task_intelligence import match_requirements


def test_docx_reads_are_forwarded_from_latest_search_and_scans_count_once(
    tmp_path: Path,
) -> None:
    texts = {
        "notice.docx": "申请人必须提交报名表。",
        "material_a.docx": "候选材料 A",
        "material_b.docx": "候选材料 B",
        "material_c.docx": "候选材料 C",
    }
    for filename, text in texts.items():
        document = WordDocument()
        document.add_paragraph(text)
        document.save(tmp_path / filename)

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
                        "description": "Find documents",
                        "arguments": {"workspace": workspace, "query": "notice"},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read documents",
                        "arguments": {},
                    },
                    {
                        "tool": "extract_requirements",
                        "description": "Extract required materials",
                        "arguments": {},
                    },
                    {
                        "tool": "list_files",
                        "description": "Collect material candidates",
                        "arguments": {"workspace": workspace},
                    },
                    {
                        "tool": "read_document",
                        "description": "Read material candidates",
                        "arguments": {},
                    },
                    {
                        "tool": "match_requirements",
                        "description": "Match candidates",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    received: list[dict] = []
    matched_input: list[dict] = []

    def capture_extraction(documents: list[dict]) -> dict:
        received.extend(deepcopy(documents))
        return {
            "success": True,
            "tool": "extract_requirements",
            "data": {"required_documents": []},
            "message": "No names extracted by controlled tool",
            "error": None,
        }

    def capture_matching(
        required_documents: list[str], candidate_documents: list[dict]
    ) -> dict:
        matched_input.extend(deepcopy(candidate_documents))
        return match_requirements(required_documents, candidate_documents)

    service = TaskService(
        planner=planner,
        router=ToolRouter(
            {
                "extract_requirements": capture_extraction,
                "match_requirements": capture_matching,
            }
        ),
    )
    task_id = service.create("Check required materials", str(tmp_path))["task_id"]
    service.run(task_id)

    snapshot = service.snapshot(task_id)
    assert snapshot["task"]["status"] == "completed"
    assert len(received) == 1
    expected_texts = {"notice.docx": texts["notice.docx"]}
    assert {
        document["filename"]: document["text"] for document in received
    } == expected_texts
    assert {document["filename"] for document in matched_input} == set(texts) - {
        "notice.docx"
    }
    assert snapshot["results"][-1]["data"] == {
        "required_documents": [],
        "matched": [],
        "missing": [],
    }
    report = service.report(task_id)
    assert len(report["found_files"]) == 4
    assert "remains unverified; no package was built" in report["summary"]

