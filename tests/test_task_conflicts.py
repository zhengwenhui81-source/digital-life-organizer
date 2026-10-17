"""Contract and conservative extraction tests for task conflict detection."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from fileforge.task_intelligence import detect_conflicts
from fileforge.task_intelligence._materials import parse_material_evidence


def document(text, path="/not-a-real-workspace/通知.txt"):
    return {
        "file_id": "file_test",
        "path": path,
        "filename": path.rsplit("/", 1)[-1],
        "extension": ".txt",
        "text": text,
        "size": len(text.encode()),
        "modified_time": "2026-10-01T00:00:00+00:00",
        "metadata": {},
    }


def conflicts(*texts):
    return detect_conflicts(documents=[document(text) for text in texts])["data"][
        "conflicts"
    ]


def test_deadline_conflict_preserves_sources_without_choosing_winner():
    docs = [
        document("报名截止：2026-10-18", "/a/通知.txt"),
        document("报名截止：2026-10-20", "/b/通知.txt"),
        document("报名截止：2026-10-20", "/c/最新补充通知.txt"),
    ]
    result = detect_conflicts(documents=docs)
    assert result == {
        "success": True,
        "tool": "detect_conflicts",
        "data": {
            "conflicts": [
                {
                    "field": "deadline:报名",
                    "values": [
                        {"value": "2026-10-18", "source": docs[0]["path"]},
                        {"value": "2026-10-20", "source": docs[1]["path"]},
                        {"value": "2026-10-20", "source": docs[2]["path"]},
                    ],
                    "recommendation": "请人工确认",
                }
            ]
        },
        "message": "Conflict detection completed",
        "error": None,
    }


@pytest.mark.parametrize(
    "left,right",
    [
        ("截止日期：2026年1月2日", "截止日期：2026-01-02"),
        ("提交截止：2026/1/2 09:05", "提交截止：2026-01-02 9时5分"),
        ("提交截止：2026-01-02T09:05:00", "提交截止：2026-01-02 09:05"),
    ],
)
def test_equivalent_dates_and_times(left, right):
    assert conflicts(left, right) == []


@pytest.mark.parametrize(
    "left,right",
    [
        ("报名截止：2026-10-18", "提交截止：2026-10-20"),
        ("报名截止：2026-10-18", "答辩截止：2026-10-20"),
        ("活动时间：2026-10-18", "活动时间：2026-10-20"),
        ("答辩时间：2026-10-18", "提交截止：2026-10-20"),
        ("截止日期：10月18日", "截止日期：2026-10-20"),
        ("截止日期：2026-10-18", "截止日期：2026-10-18 18:00"),
        ("提交截止：2026-10-18 18:00 UTC", "提交截止：2026-10-18 19:00 UTC"),
        ("提交截止：2026-02-30", "提交截止：2026-03-01"),
    ],
)
def test_different_contexts_and_unsupported_dates_do_not_conflict(left, right):
    assert conflicts(left, right) == []


@pytest.mark.parametrize("time", ["19:00", "18:01", "18:00:01"])
def test_explicit_time_is_not_discarded(time):
    found = conflicts("提交截止：2026-10-18 18:00", f"提交截止：2026-10-18 {time}")
    assert len(found) == 1
    assert found[0]["values"][0]["value"] == "2026-10-18T18:00:00"
    assert found[0]["values"][1]["value"] != "2026-10-18T18:00:00"


def test_required_material_conflict():
    found = conflicts("必须提交学生证、报名表。", "无需提交学生证；必须提交报名表。")
    assert found == [
        {
            "field": "required_documents:学生证",
            "values": [
                {"value": "required", "source": document("")["path"]},
                {"value": "not_required", "source": document("")["path"]},
            ],
            "recommendation": "请人工确认",
        }
    ]


@pytest.mark.parametrize(
    "text",
    [
        "必须提交报名表",  # Omission is not a negative assertion.
        "可选提交学生证",
        "学生证为可选材料",
        "必须提交学生证（可选）",
        "如有学生证，必须提交学生证",
        "无需提交学生证或护照",  # Alternatives require later interpretation.
    ],
)
def test_optional_partial_and_conditional_materials(text):
    assert conflicts("必须提交学生证", text) == []


def test_reusable_material_evidence():
    evidence = parse_material_evidence("须提交报名表、学生证；不必提交身份证", "/a.txt")
    assert [(e.material, e.required, e.source) for e in evidence] == [
        ("报名表", True, "/a.txt"),
        ("学生证", True, "/a.txt"),
        ("身份证", False, "/a.txt"),
    ]


def test_empty_single_document_and_internal_conflict():
    assert detect_conflicts(documents=[])["data"] == {"conflicts": []}
    assert conflicts("报名截止：2026-10-18。必须提交学生证") == []
    assert len(conflicts("截止日期：2026-10-18；截止日期：2026-10-20")) == 1


@pytest.mark.parametrize(
    "invalid",
    [None, {}, "text", (), [None], [{}], [{"text": "hello"}]],
)
def test_invalid_input_standard_failure(invalid):
    result = detect_conflicts(documents=invalid)
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["success"] is False
    assert result["tool"] == "detect_conflicts"
    assert result["data"] is None
    assert isinstance(result["message"], str) and result["message"]
    assert isinstance(result["error"], str) and result["error"]


@pytest.mark.parametrize("key,value", [("text", None), ("path", ""), ("size", True)])
def test_invalid_document_fields(key, value):
    doc = document("hello")
    doc[key] = value
    assert detect_conflicts([doc])["success"] is False


def test_input_unchanged_and_no_file_access():
    docs = [document("必须提交学生证"), document("无需提交学生证")]
    original = deepcopy(docs)
    with patch("builtins.open", side_effect=AssertionError("No file access")):
        result = detect_conflicts(documents=docs)
    assert result["success"] is True
    assert docs == original


def test_different_days_conflict_across_precision_without_inventing_time():
    found = conflicts("报名截止：2026-10-18", "报名截止：2026-10-20 18:00")
    assert len(found) == 1
    assert [entry["value"] for entry in found[0]["values"]] == [
        "2026-10-18",
        "2026-10-20T18:00:00",
    ]


def test_all_same_scope_evidence_is_kept_in_one_conflict():
    docs = [
        document("报名截止：2026-10-18", "/a/通知.txt"),
        document(
            "报名截止：2026-10-18 18:00，报名截止：2026-10-18 20:00", "/b/通知.txt"
        ),
        document("报名截止：2026-10-18 20:00", "/c/通知.txt"),
    ]
    found = detect_conflicts(documents=docs)["data"]["conflicts"]
    assert len(found) == 1
    assert found[0]["values"] == [
        {"value": "2026-10-18", "source": "/a/通知.txt"},
        {"value": "2026-10-18T18:00:00", "source": "/b/通知.txt"},
        {"value": "2026-10-18T20:00:00", "source": "/b/通知.txt"},
        {"value": "2026-10-18T20:00:00", "source": "/c/通知.txt"},
    ]


@pytest.mark.parametrize("separator", ["，", ",", "；", "。", "\n"])
def test_internal_deadline_assertions_keep_both_values(separator):
    found = conflicts(f"提交截止：2026-10-18{separator}提交截止：2026-10-20")
    assert len(found) == 1
    assert [v["value"] for v in found[0]["values"]] == ["2026-10-18", "2026-10-20"]


@pytest.mark.parametrize(
    "text",
    [
        "无需提交学生证（必交）",
        "必须提交学生证（非必需）",
        "必须提交身份证非必需",
        "无需提交学生证为必交材料",
    ],
)
def test_material_annotations_are_not_material_names(text):
    assert parse_material_evidence(text, "/notice.txt") == []


@pytest.mark.parametrize(
    "text", ["必须提交学生证（可选）", "可选提交学生证", "学生证为可选材料"]
)
def test_optional_evidence_cannot_conflict_with_negative_requirement(text):
    assert conflicts("无需提交学生证", text) == []


def test_material_sources_and_internal_polarities_are_preserved():
    docs = [
        document("必须提交学生证；无需提交学生证；无需提交学生证", "/a/通知.txt"),
        document("必须提交学生证", "/b/通知.txt"),
    ]
    found = detect_conflicts(documents=docs)["data"]["conflicts"]
    assert len(found) == 1
    assert found[0]["values"] == [
        {"value": "required", "source": "/a/通知.txt"},
        {"value": "not_required", "source": "/a/通知.txt"},
        {"value": "required", "source": "/b/通知.txt"},
    ]


@pytest.mark.parametrize("key", list(document("text")))
def test_every_missing_document_field_returns_failure(key):
    doc = document("text")
    del doc[key]
    result = detect_conflicts(documents=[doc])
    assert result["success"] is False
    assert result["data"] is None
    assert result["error"]


def test_small_year_is_zero_padded_without_inference():
    found = conflicts("截止日期：0001-01-01", "截止日期：0001-01-02")
    assert [v["value"] for v in found[0]["values"]] == ["0001-01-01", "0001-01-02"]


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("截止日期：2026年1月2日", "2026-01-02"),
        ("截止日期：2026/1/2", "2026-01-02"),
        ("截止日期：2026-01-02", "2026-01-02"),
        ("截止日期：2026/1/2 09:05", "2026-01-02T09:05:00"),
        ("截止日期：2026-01-02 9时5分", "2026-01-02T09:05:00"),
        ("截止日期：2026-01-02T09:05:01", "2026-01-02T09:05:01"),
    ],
)
def test_supported_date_forms_have_positive_extraction_control(expression, expected):
    found = conflicts(expression, "截止日期：2026-01-03 10:00")
    assert len(found) == 1
    assert found[0]["values"][0]["value"] == expected


def test_json_input_and_output_round_trip():
    import json

    docs = json.loads(
        json.dumps([document("必须提交学生证"), document("无需提交学生证")])
    )
    result = detect_conflicts(**{"documents": docs})
    assert json.loads(json.dumps(result)) == result
    assert len(result["data"]["conflicts"]) == 1


@pytest.mark.parametrize(
    "prefix",
    ["如发生延期", "若发生延期", "只有审批通过", "在发生延期的情况下", "仅当收到确认"],
)
@pytest.mark.parametrize("separator", ["，", ",", "，\n"])
def test_review_conditional_deadline_not_promoted_after_comma(prefix, separator):
    assert (
        conflicts(f"{prefix}{separator}报名截止：2026-10-20", "报名截止：2026-10-18")
        == []
    )


def test_review_unknown_prefix_is_not_discarded_to_expose_deadline():
    assert (
        conflicts("以最终核准为准，报名截止：2026-10-20", "报名截止：2026-10-18") == []
    )


def test_review_independent_deadlines_survive_other_conditional_sentences():
    found = conflicts(
        "如发生延期，报名截止：2026-10-20。报名截止：2026-10-18",
        "报名截止：2026-10-19",
    )
    assert len(found) == 1
    assert [v["value"] for v in found[0]["values"]] == ["2026-10-18", "2026-10-19"]
