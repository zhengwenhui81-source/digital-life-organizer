"""Generic explicitly submitted labels, using C's public reader."""

import pytest
from docx import Document

from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements


def read_text(tmp_path, text, name="notification.docx"):
    path = tmp_path / name
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(path)
    result = read_document(path=str(path))
    assert result["success"], result
    return result["data"]["document"]


@pytest.mark.parametrize("heading", ["正式提交材料清单", "所需材料", "必交材料要求"])
@pytest.mark.parametrize("number", ["M12", "item-3", "Q_9", "7.", "（三）"])
def test_labeled_explicit_submission(tmp_path, heading, number):
    doc = read_text(
        tmp_path,
        heading
        + "\n"
        + number
        + " 研究计划：提交一份研究计划，含背景与方法。\n评分规则\n1. 创新性\n2. 可行性",
    )
    result = extract_requirements(documents=[doc])
    assert result["data"] == {"required_documents": ["研究计划"]}


@pytest.mark.parametrize(
    "body",
    [
        "如获奖，必须提交资格证明",
        "只有已交原件者，无需提交资格证明",
        "可选提交资格证明",
        "提交资格证明或护照",
        "任选一种证明提交",
        "无需提交资格证明",
        "不必提交资格证明",
        "建议提交资格证明",
        "提交资格证明（仅获奖者）",
        "提交资格证明（条件满足时）",
    ],
)
def test_conditions_optional_negative_not_unconditional(tmp_path, body):
    doc = read_text(
        tmp_path,
        "正式提交材料清单\nM1 资格证明：" + body + "\nM2 研究计划：提交研究计划。",
    )
    result = extract_requirements(documents=[doc])
    assert result["data"] == {"required_documents": ["研究计划"]}
    other = read_text(tmp_path, "必须提交资格证明", "other.docx")
    conflicts = detect_conflicts(documents=[doc, other])["data"]["conflicts"]
    if body.startswith(("无需提交", "不必提交")):
        assert len(conflicts) == 1
        assert {v["value"] for v in conflicts[0]["values"]} == {
            "required",
            "not_required",
        }
    else:
        assert conflicts == []


@pytest.mark.parametrize(
    "boundary", ["二、评审标准", "## 后续说明", "3. 活动安排：在线评审", "普通说明段落"]
)
def test_section_boundaries_still_stop_scope(tmp_path, boundary):
    doc = read_text(
        tmp_path,
        "正式提交材料清单\nM1 研究计划：提交研究计划。\n"
        + boundary
        + "\nM2 资格证明：提交资格证明。",
    )
    assert extract_requirements(documents=[doc])["data"] == {
        "required_documents": ["研究计划"]
    }


def test_unheaded_labels_and_normal_prose_stay_empty(tmp_path):
    doc = read_text(
        tmp_path, "会议记录\nM1 研究计划：提交研究计划。\n评分规则\n1. 创新性"
    )
    assert extract_requirements(documents=[doc])["data"] == {"required_documents": []}


def test_label_name_keeps_conjunctions_and_stable_order(tmp_path):
    doc = read_text(
        tmp_path,
        "正式提交材料清单\nM1 研究与开发报告：提交报告。\n"
        "M2 资格证明：提交证明。\nM3 研究与开发报告：提交报告。",
    )
    assert extract_requirements(documents=[doc])["data"] == {
        "required_documents": ["研究与开发报告", "资格证明"]
    }


def test_existing_colon_assertions_are_not_reinterpreted_as_labels(tmp_path):
    doc = read_text(
        tmp_path, "所需材料：\n1. 必须提交：研究计划\n2. 无需提交：资格证明"
    )
    assert extract_requirements(documents=[doc])["data"] == {
        "required_documents": ["研究计划"]
    }
    other = read_text(tmp_path, "必须提交资格证明", "other.docx")
    conflicts = detect_conflicts(documents=[doc, other])["data"]["conflicts"]
    assert len(conflicts) == 1
    assert {v["value"] for v in conflicts[0]["values"]} == {"required", "not_required"}
