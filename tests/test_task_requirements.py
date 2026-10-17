"""Requirement extraction and shared-parser integration expectations."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from fileforge.task_intelligence import detect_conflicts, extract_requirements
from tests.test_task_conflicts import document


def required(text):
    result = extract_requirements(documents=[document(text)])
    assert result["success"] is True
    return result["data"]["required_documents"]


@pytest.mark.parametrize(
    "prefix", ["必须提交", "须提交", "需提交", "需要提交", "请必须提交"]
)
def test_explicit_required_statements(prefix):
    assert required(f"{prefix}报名表、学生证，项目介绍。") == [
        "报名表",
        "学生证",
        "项目介绍",
    ]


@pytest.mark.parametrize(
    "heading", ["提交材料", "所需材料", "必交材料", "## 所需材料", "一、提交材料"]
)
def test_numbered_lists_and_next_section_boundary(heading):
    text = (
        f"{heading}：\n1. 报名表\n2、学生证\n（3）项目介绍\n"
        "二、活动安排\n1. 答辩\n2. 合影"
    )
    assert required(text) == ["报名表", "学生证", "项目介绍"]


@pytest.mark.parametrize(
    "boundary", ["", "活动安排：", "其他说明：", "接下来介绍活动安排。"]
)
def test_list_scope_ends_before_unrelated_numbered_items(boundary):
    assert required(f"所需材料：\n1. 报名表\n{boundary}\n1. 合影") == ["报名表"]


def test_inline_heading_bullets_and_chinese_numbering():
    text = (
        "提交材料：报名表、学生证\n- 项目介绍\n* 研究与开发报告\n"
        "（一）姓名和联系方式\n\n讨论中提到护照。"
    )
    assert required(text) == [
        "报名表",
        "学生证",
        "项目介绍",
        "研究与开发报告",
        "姓名和联系方式",
    ]


def test_stable_dedup_across_documents_and_polarities():
    docs = [
        document("必须提交报名表、学生证；无需提交报名表", "/a.txt"),
        document("无需提交学生证；必须提交项目介绍、报名表", "/b.txt"),
    ]
    result = extract_requirements(documents=docs)
    assert result == {
        "success": True,
        "tool": "extract_requirements",
        "data": {"required_documents": ["报名表", "学生证", "项目介绍"]},
        "message": "Requirement extraction completed",
        "error": None,
    }
    found = detect_conflicts(documents=docs)["data"]["conflicts"]
    assert {entry["field"] for entry in found} == {
        "required_documents:报名表",
        "required_documents:学生证",
    }


@pytest.mark.parametrize("marker", ["（必交）", "(必交)"])
def test_exact_mandatory_marker(marker):
    assert required(f"学生证{marker}；必须提交报名表{marker}") == ["学生证", "报名表"]
    assert required(f"所需材料：\n1. 学生证{marker}\n2. 项目介绍（可选）") == ["学生证"]


@pytest.mark.parametrize(
    "text",
    [
        "无需提交学生证",
        "不需要提交学生证",
        "不必提交学生证",
        "学生证（可选）",
        "必须提交学生证（可选）",
        "学生证（原件）",
        "必须提交学生证（原件）",
        "必须提交学生证（必交，如有）",
        "如有学生证，必须提交学生证",
        "必须提交学生证或护照",
        "所需材料：\n1. 学生证（如有）\n2. 身份证或护照\n3. 可选提交项目介绍",
        "学生证是常见证件，报名表上有姓名",
        "活动安排：\n1. 学生证\n2. 报名表",
        "所需材料：\n1. 学生证（二选一）",
    ],
)
def test_optional_negative_conditions_alternatives_and_prose(text):
    assert required(text) == []


def test_document_scope_never_carries_over():
    docs = [document("所需材料：\n1. 报名表"), document("1. 学生证")]
    assert extract_requirements(docs)["data"] == {"required_documents": ["报名表"]}


def test_positive_evidence_survives_later_negative_in_same_document():
    docs = [document("必交材料：\n1. 学生证\n\n无需提交学生证")]
    assert extract_requirements(docs)["data"] == {"required_documents": ["学生证"]}
    assert detect_conflicts(docs)["data"]["conflicts"][0]["values"] == [
        {"value": "required", "source": docs[0]["path"]},
        {"value": "not_required", "source": docs[0]["path"]},
    ]


@pytest.mark.parametrize("invalid", [None, {}, "text", [None], [{}], [{"text": "x"}]])
def test_invalid_input_failure_envelope(invalid):
    result = extract_requirements(documents=invalid)
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["success"] is False
    assert result["tool"] == "extract_requirements"
    assert result["data"] is None
    assert result["message"] and result["error"]


def test_empty_input_and_input_unchanged_without_file_access():
    assert extract_requirements([])["data"] == {"required_documents": []}
    docs = [document("所需材料：\n1. 报名表\n2. 学生证（必交）")]
    original = deepcopy(docs)
    with patch("builtins.open", side_effect=AssertionError("No file access")):
        assert extract_requirements(docs)["data"] == {
            "required_documents": ["报名表", "学生证"]
        }
    assert docs == original


@pytest.mark.parametrize(
    "text",
    [
        "所需材料：\n1. 项目介绍\n活动安排：\n1. 学生证",
        "所需材料：\n1. 学生证（可选）",
        "所需材料：\n1. 如果有学生证则提交",
        "所需材料：\n1. 学生证或护照",
        "必须提交学生证（原件）",
    ],
)
def test_shared_parser_does_not_invent_conflicts(text):
    docs = [document(text), document("无需提交学生证")]
    assert detect_conflicts(docs)["data"] == {"conflicts": []}


def test_next_section_with_inline_description_ends_material_scope():
    text = "所需材料：\n1. 报名表\n二、活动安排：线下答辩\n1. 学生证"
    assert required(text) == ["报名表"]
    assert detect_conflicts([document(text), document("无需提交学生证")])["data"] == {
        "conflicts": []
    }


def test_heading_semicolon_parallel_items():
    assert required("必交材料：报名表；学生证、研究与开发报告") == [
        "报名表",
        "学生证",
        "研究与开发报告",
    ]


def test_comma_separated_assertions_do_not_inherit_wrong_polarity():
    docs = [document("必须提交学生证，无需提交学生证，必须提交报名表")]
    assert extract_requirements(docs)["data"] == {
        "required_documents": ["学生证", "报名表"]
    }
    found = detect_conflicts(docs)["data"]["conflicts"]
    assert len(found) == 1
    assert found[0]["field"] == "required_documents:学生证"
    assert [v["value"] for v in found[0]["values"]] == ["required", "not_required"]


def test_comma_split_does_not_detach_conditional_assertion():
    docs = [document("如有学生证，必须提交学生证"), document("无需提交学生证")]
    assert extract_requirements(docs)["data"] == {"required_documents": []}
    assert detect_conflicts(docs)["data"] == {"conflicts": []}


def test_nested_conditional_list_does_not_become_mandatory():
    text = "所需材料：\n1. 如有则提供\n  - 学生证\n" "  必须提交身份证\n2. 报名表"
    docs = [document(text)]
    assert extract_requirements(docs)["data"] == {"required_documents": ["报名表"]}
    assert detect_conflicts(docs + [document("无需提交学生证、身份证")])["data"] == {
        "conflicts": []
    }


@pytest.mark.parametrize(
    "heading",
    ["二、评审标准", "三、完全未知的新章节", "## 评审标准", "第二章 评分细则"],
)
def test_review_section_boundary_does_not_inherit_material_scope(heading):
    text = f"所需材料：\n1. 报名表\n{heading}\n1. 创新性\n2. 可行性"
    assert required(text) == ["报名表"]


@pytest.mark.parametrize(
    "prefix", ["只有获奖者", "只有已交原件者", "仅当审核通过", "在审核通过的情况下"]
)
@pytest.mark.parametrize("assertion", ["必须提交学生证", "无需提交学生证"])
def test_review_conditional_material_clause_is_not_unconditional(prefix, assertion):
    text = f"{prefix}，{assertion}"
    assert required(text) == []
    assert detect_conflicts([document(text), document("必须提交学生证")])["data"] == {
        "conflicts": []
    }


def test_review_conditions_do_not_hide_independent_material_sentences():
    text = (
        "只有获奖者，必须提交学生证。必须提交报名表\n"
        "只有已交原件者，无需提交学生证；必须提交项目介绍"
    )
    assert required(text) == ["报名表", "项目介绍"]


def test_review_comma_newline_keeps_material_condition():
    assert required("只有获奖者，\n必须提交学生证\n必须提交报名表") == ["报名表"]


def test_review_unambiguous_material_numbering_still_works():
    assert required("所需材料：\n1. 报名表\n2、学生证\n（3）项目介绍") == [
        "报名表",
        "学生证",
        "项目介绍",
    ]


def test_review_unknown_prefix_does_not_expose_material_assertion():
    text = "以最终核准为准，必须提交学生证；必须提交报名表"
    assert required(text) == ["报名表"]
    assert detect_conflicts([document(text), document("无需提交学生证")])["data"] == {
        "conflicts": []
    }


def test_review_bare_chinese_numbering_is_explicitly_conservative_boundary():
    text = (
        "提交材料：报名表、学生证\n- 项目介绍\n* 研究与开发报告\n"
        "一、姓名和联系方式\n1. 其他条目"
    )
    assert required(text) == ["报名表", "学生证", "项目介绍", "研究与开发报告"]
