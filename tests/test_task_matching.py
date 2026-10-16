"""Behavior tests for D's private, adjustable filename-matching prototype."""

from copy import deepcopy
from unittest.mock import patch

import pytest

import fileforge.task_intelligence as public
from fileforge.task_intelligence._matching import _match_materials
from tests.test_task_conflicts import document


def candidate(filename, folder="/candidates"):
    doc = document("正文不参与匹配", f"{folder}/{filename}")
    doc["file_id"] = f"original:{doc['path']}"
    doc["filename"] = filename
    doc["extension"] = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    return doc


def test_exact_name_different_extensions_and_original_identity():
    docs = [candidate("报名表.pdf"), candidate("报名表.docx")]
    result = _match_materials(["报名表", "学生证"], docs)
    assert result == {
        "required_documents": ["报名表", "学生证"],
        "matched": [
            {
                "requirement": "报名表",
                "documents": [
                    {key: doc[key] for key in ("file_id", "path", "filename")}
                    for doc in docs
                ],
            }
        ],
        "missing": ["学生证"],
    }


def test_versions_keep_all_candidates_in_input_order_not_version_order():
    filenames = ["报名表_v2.docx", "报名表.pdf", "报名表_v1.docx", "报名表_v1.2.3.pdf"]
    docs = [candidate(name) for name in filenames]
    result = _match_materials(["报名表"], docs)
    assert [ref["filename"] for ref in result["matched"][0]["documents"]] == filenames
    assert result["missing"] == []


@pytest.mark.parametrize(
    "filename",
    [
        "学生证办理说明.pdf",
        "报名表填写指南.docx",
        "报名表_v1_填写指南.pdf",
        "报名表_v1final.pdf",
        "报名表_v1.2.3.4.pdf",
        "报名表_v1_v2.pdf",
        "报名表2026.pdf",
    ],
)
def test_no_substring_or_ambiguous_suffix_matching(filename):
    result = _match_materials(["学生证", "报名表"], [candidate(filename)])
    assert result["matched"] == []
    assert result["missing"] == ["学生证", "报名表"]


def test_numbers_and_literal_version_names_not_truncated():
    docs = [candidate("报名表2026_v2.pdf"), candidate("报告_v1.pdf")]
    result = _match_materials(["报名表2026", "报名表", "报告_v1"], docs)
    assert [item["requirement"] for item in result["matched"]] == [
        "报名表2026",
        "报告_v1",
    ]
    assert result["missing"] == ["报名表"]


def test_duplicate_requirements_and_candidates_preserve_distinct_paths():
    first = candidate("报名表.pdf", "/a")
    second = candidate("报名表.pdf", "/b")
    result = _match_materials(
        ["报名表", "学生证", "报名表", "学生证"], [first, deepcopy(first), second]
    )
    assert result["required_documents"] == ["报名表", "学生证"]
    assert result["missing"] == ["学生证"]
    assert [ref["path"] for ref in result["matched"][0]["documents"]] == [
        first["path"],
        second["path"],
    ]


def test_empty_inputs():
    assert _match_materials([], []) == {
        "required_documents": [],
        "matched": [],
        "missing": [],
    }
    assert _match_materials([], [candidate("报名表.pdf")])["matched"] == []
    assert _match_materials(["报名表"], []) == {
        "required_documents": ["报名表"],
        "matched": [],
        "missing": ["报名表"],
    }


@pytest.mark.parametrize(
    "required", [None, "报名表", (), [None], [12], [""], ["  "], [{}]]
)
def test_invalid_requirements(required):
    with pytest.raises(ValueError):
        _match_materials(required, [])


@pytest.mark.parametrize("docs", [None, {}, [None], [{}], [{"filename": "报名表.pdf"}]])
def test_invalid_documents(docs):
    with pytest.raises(ValueError):
        _match_materials(["报名表"], docs)


@pytest.mark.parametrize("filename", ["/a/报名表.pdf", "a\\报名表.pdf", ".", ".."])
def test_filename_must_not_be_path(filename):
    with pytest.raises(ValueError):
        _match_materials(["报名表"], [candidate(filename)])


def test_names_not_normalized_and_body_not_used():
    docs = [candidate("不相关.pdf"), candidate("Form.pdf")]
    docs[0]["text"] = "报名表 学生证"
    result = _match_materials(["报名表", "form", " Form"], docs)
    assert result["missing"] == ["报名表", "form", " Form"]
    assert result["matched"] == []


def test_inputs_unchanged_no_file_access_and_references_detached():
    required = ["报名表"]
    docs = [candidate("报名表_v1.docx")]
    before = deepcopy((required, docs))
    with patch("builtins.open", side_effect=AssertionError("No disk reads")):
        result = _match_materials(required, docs)
    assert (required, docs) == before
    result["matched"][0]["documents"][0]["path"] = "/changed"
    result["required_documents"].append("new")
    assert (required, docs) == before


def test_private_prototype_not_exported_as_public_tool():
    assert not hasattr(public, "_match_materials")
    assert public.__all__ == ["detect_conflicts", "extract_requirements"]


@pytest.mark.parametrize("inconsistency", ["id", "path", "filename"])
def test_inconsistent_document_identity_rejected_without_mutating_input(inconsistency):
    first = candidate("报名表.pdf", "/a")
    second = candidate("报名表.pdf", "/b")
    if inconsistency == "id":
        second["file_id"] = first["file_id"]
    elif inconsistency == "path":
        second["path"] = first["path"]
    else:
        second = deepcopy(first)
        second["filename"] = "学生证.pdf"
    docs = [first, second]
    before = deepcopy(docs)
    with pytest.raises(ValueError, match="Inconsistent Document identity"):
        _match_materials(["报名表"], docs)
    assert docs == before
