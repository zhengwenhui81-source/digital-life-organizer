"""Matching Phase 1 public-contract acceptance tests."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from fileforge.task_intelligence import match_requirements
from tests.test_task_conflicts import document
from tests.test_task_documents import _invalid_json_value


def candidate(filename, extension, identity="file_a"):
    doc = document("空白模板说明：本材料未经内容审核", f"/work/{filename}")
    doc.update(file_id=identity, filename=filename, extension=extension)
    return doc


def ref(doc):
    return {key: doc[key] for key in ("file_id", "path", "filename")}


def expected(required, matched, missing):
    return {
        "success": True,
        "tool": "match_requirements",
        "data": {
            "required_documents": required,
            "matched": matched,
            "missing": missing,
        },
        "message": "Requirement candidate matching completed",
        "error": None,
    }


def assert_failure(result):
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["tool"] == "match_requirements"
    assert result["success"] is False
    assert result["data"] is None
    assert result["message"] and result["error"]


@pytest.mark.parametrize(
    "filename,extension,requirement,hit",
    [
        ("课程报告.pdf", ".pdf", "课程报告", True),
        ("课程报告", "", "课程报告", True),
        (".env", "", ".env", True),
        (".gitignore", "", ".gitignore", True),
        (".config.json", ".json", ".config", True),
        ("材料.tar.gz", ".gz", "材料.tar", True),
        ("材料.tar.gz", ".gz", "材料", False),
        ("报告.PDF", ".pdf", "报告", True),
        ("Form.pdf", ".PDF", "form", False),
        (" 表 .txt", ".txt", " 表 ", True),
        (" 表 .txt", ".txt", "表", False),
        ("课程  报告.txt", ".txt", "课程 报告", False),
        ("Ａ表.txt", ".txt", "A表", False),
        ("e\u0301.txt", ".txt", "é", False),
        ("报告_v01.pdf", ".pdf", "报告", True),
        ("报告_v1.2.pdf", ".pdf", "报告", True),
        ("报告_v1.2.3.pdf", ".pdf", "报告", True),
        ("报告_V1.pdf", ".pdf", "报告", False),
        ("报告_v１.pdf", ".pdf", "报告", False),
        ("报告_v1.2.3.4.pdf", ".pdf", "报告", False),
        ("报告_v1说明.pdf", ".pdf", "报告", False),
        ("报告_v1\n.pdf", ".pdf", "报告", False),
        ("申请表_v1_v2.pdf", ".pdf", "申请表_v1", True),
        ("申请表_v1_v2.pdf", ".pdf", "申请表", False),
        ("_v1.pdf", ".pdf", "_v1", True),
        ("报告2026_v2.pdf", ".pdf", "报告2026", True),
        ("报告2026_v2.pdf", ".pdf", "报告", False),
        ("学生证办理说明.pdf", ".pdf", "学生证", False),
        ("课程报告填写指南.docx", ".docx", "课程报告", False),
        ("材料.custom", ".custom", "材料", True),
    ],
)
def test_filename_candidate_relationship(filename, extension, requirement, hit):
    doc = candidate(filename, extension)
    result = match_requirements(
        required_documents=[requirement], candidate_documents=[doc]
    )
    assert result == expected(
        [requirement],
        [{"requirement": requirement, "documents": [ref(doc)]}] if hit else [],
        [] if hit else [requirement],
    )


@pytest.mark.parametrize(
    "filename,extension",
    [
        ("", ""),
        (" \t", ""),
        (".", ""),
        ("..", ""),
        ("...", ""),
        ("表.", ""),
        ("..foo", ".foo"),
        ("...foo", ".foo"),
        ("a/表.txt", ".txt"),
        ("a\\表.txt", ".txt"),
        ("表.pdf", ".docx"),
        ("表", ".txt"),
        (".env", ".env"),
        ("表.Ä", ".ä"),
    ],
)
@pytest.mark.parametrize("requirements", [[], ["表"]])
def test_invalid_filename_fails_even_for_empty_requirements(
    filename, extension, requirements
):
    result = match_requirements(
        required_documents=requirements,
        candidate_documents=[candidate(filename, extension)],
    )
    assert_failure(result)


def test_order_zero_one_many_and_shared_duplicates():
    a = candidate("甲_v2.txt", ".txt", "a")
    b = candidate("乙.txt", ".txt", "b")
    c = candidate("甲.txt", ".txt", "c")
    docs = [a, b, deepcopy(a), c]
    docs[2]["metadata"] = dict(reversed(list(a["metadata"].items())))
    result = match_requirements(
        required_documents=["乙", "缺项", "甲", "乙"], candidate_documents=docs
    )
    assert result == expected(
        ["乙", "缺项", "甲"],
        [
            {"requirement": "乙", "documents": [ref(b)]},
            {"requirement": "甲", "documents": [ref(a), ref(c)]},
        ],
        ["缺项"],
    )


def test_same_candidate_independently_associates_with_multiple_requirements():
    doc = candidate("申请表_v1_v2.pdf", ".pdf")
    requirements = ["申请表_v1", "申请表_v1_v2", "申请表"]
    assert match_requirements(requirements, [doc]) == expected(
        requirements,
        [{"requirement": name, "documents": [ref(doc)]} for name in requirements[:2]],
        ["申请表"],
    )


def test_distinct_ids_same_path_and_name_are_not_merged():
    first = candidate("表.txt", ".txt", "a")
    second = deepcopy(first)
    second["file_id"] = "b"
    assert match_requirements(["表"], [first, second]) == expected(
        ["表"], [{"requirement": "表", "documents": [ref(first), ref(second)]}], []
    )


@pytest.mark.parametrize("requirements", [[], ["表", "其他", "表"]])
def test_empty_candidates(requirements):
    names = list(dict.fromkeys(requirements))
    assert match_requirements(requirements, []) == expected(names, [], names)


def test_empty_requirements_valid_candidates():
    assert match_requirements([], [candidate("表.txt", ".txt")]) == expected([], [], [])


@pytest.mark.parametrize(
    "requirements", [None, {}, "表", (), [None], [1], [True], [""], [" \t"]]
)
def test_invalid_requirements(requirements):
    assert_failure(match_requirements(requirements, []))


@pytest.mark.parametrize("documents", [None, {}, (), [None], [{}]])
def test_invalid_candidates(documents):
    assert_failure(match_requirements([], documents))


@pytest.mark.parametrize("field", list(candidate("表.txt", ".txt")) + ["extra"])
def test_same_id_complete_snapshot_contradiction(field):
    first = candidate("表.txt", ".txt")
    second = deepcopy(first)
    if field == "file_id":
        second[field] = "another"
        assert match_requirements(["表"], [first, second])["success"] is True
        return
    if field == "size":
        second[field] += 1
    elif field == "filename":
        second[field] = "另一个表.txt"
    elif field == "extension":
        second[field] = ".TXT"
    elif field in ("metadata", "extra"):
        second[field] = {"different": None}
    else:
        second[field] += "different"
    # Both snapshots are individually valid, including matching-specific fields.
    assert match_requirements(["表"], [first])["success"] is True
    assert match_requirements(["表"], [second])["success"] is True
    result = match_requirements(["表"], [first, second])
    assert_failure(result)
    assert first["file_id"] in result["error"]
    assert "[1]" in result["error"]


@pytest.mark.parametrize("field", ["metadata", "extra"])
@pytest.mark.parametrize(
    "kind",
    [
        "nan",
        "positive-infinity",
        "negative-infinity",
        "integer-key",
        "boolean-key",
        "null-key",
        "set",
        "bytes",
        "datetime",
        "tuple",
        "custom",
        "raising-custom",
        "cyclic-object",
        "cyclic-array",
    ],
)
@pytest.mark.parametrize("duplicate", [False, True])
def test_shared_json_rejection(field, kind, duplicate):
    value = _invalid_json_value(kind)
    doc = candidate("表.txt", ".txt")
    doc[field] = {"value": value}
    docs = [doc, dict(doc)] if duplicate else [doc]
    result = match_requirements([], docs)
    assert_failure(result)
    assert doc[field]["value"] is value
    if kind in {"custom", "raising-custom"}:
        assert value.equality_calls == 0


def test_input_unchanged_no_disk_or_content_review_and_detached_output():
    requirements = ["课程报告", "课程报告"]
    doc = candidate("课程报告.txt", ".txt")
    doc["metadata"] = {"nested": {"a": [True, None, 1.0]}}
    docs = [doc, deepcopy(doc)]
    before = deepcopy((requirements, docs))
    with patch("builtins.open", side_effect=AssertionError("No filesystem access")):
        result = match_requirements(requirements, docs)
    assert result == expected(
        ["课程报告"], [{"requirement": "课程报告", "documents": [ref(doc)]}], []
    )
    assert (requirements, docs) == before
    result["data"]["matched"][0]["documents"][0]["path"] = "/changed"
    result["data"]["required_documents"].append("changed")
    assert (requirements, docs) == before


@pytest.mark.parametrize(
    "left,right", [(True, 1), (False, 0), (1, 1.0), ([1, 2], [2, 1])]
)
@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_strict_snapshot_types_and_array_order(left, right, field):
    first = candidate("表.txt", ".txt")
    first[field] = {"nested": left}
    second = dict(first)
    second[field] = {"nested": right}
    assert_failure(match_requirements(["表"], [first, second]))


def test_equal_nested_metadata_order_and_shared_objects():
    first = candidate("表.txt", ".txt")
    shared = {"x": [1, None, True]}
    first["metadata"] = {"a": shared, "b": shared}
    second = dict(first)
    second["metadata"] = {"b": {"x": [1, None, True]}, "a": {"x": [1, None, True]}}
    assert match_requirements(["表"], [first, second]) == expected(
        ["表"], [{"requirement": "表", "documents": [ref(first)]}], []
    )
    assert first["metadata"]["a"] is shared


def test_metaclass_and_requirement_subclass_rejected_without_comparison():
    calls = []

    class Meta(type):
        def __eq__(cls, other):
            calls.append("meta")
            raise RuntimeError("must not compare")

    class Custom(str, metaclass=Meta):
        def __eq__(self, other):
            calls.append("instance")
            raise RuntimeError("must not compare")

    value = Custom("表")
    assert_failure(match_requirements([value], []))
    doc = candidate("表.txt", ".txt")
    doc["metadata"] = {"custom": value}
    assert_failure(match_requirements([], [doc]))
    assert calls == []


@pytest.mark.parametrize("requirements", [[], ["表"]])
@pytest.mark.parametrize(
    "contradictory", [False, True], ids=["duplicate", "contradiction"]
)
def test_raw_matching_error_precedes_snapshot_comparison(requirements, contradictory):
    from fileforge.task_intelligence import _documents

    first = candidate("表.txt", ".txt", "a")
    second = deepcopy(first)
    if contradictory:
        second["text"] = "不同快照"
    invalid = candidate("其他.pdf", ".docx", "c")
    docs = [first, second, invalid]
    before = deepcopy(docs)
    with patch.object(
        _documents, "_same_snapshot", wraps=_documents._same_snapshot
    ) as compare:
        result = match_requirements(requirements, docs)
    assert_failure(result)
    assert "candidate_documents[2].extension" in result["error"]
    compare.assert_not_called()
    assert docs == before


def test_all_raw_candidates_validated_before_comparison_and_stable_dedup():
    from fileforge.task_intelligence import _documents, matching

    first = candidate("表_v2.txt", ".txt", "a")
    last = candidate("表.txt", ".txt", "b")
    docs = [first, deepcopy(first), last]
    before = deepcopy(docs)
    events = []
    original_validate = matching._validate_candidates
    original_compare = _documents._same_snapshot

    def validate(raw):
        assert raw is docs
        assert len(raw) == 3
        error = original_validate(raw)
        assert error is None
        events.append("validated-all-raw")
        return error

    def compare(left, right):
        assert events == ["validated-all-raw"]
        events.append("compare")
        return original_compare(left, right)

    with patch.object(matching, "_validate_candidates", side_effect=validate):
        with patch.object(_documents, "_same_snapshot", side_effect=compare):
            result = match_requirements(["表"], docs)
    assert events == ["validated-all-raw", "compare"]
    assert result == expected(
        ["表"], [{"requirement": "表", "documents": [ref(first), ref(last)]}], []
    )
    assert docs == before


@pytest.mark.parametrize("invalid_kind", ["json", "structure"])
def test_raw_shared_checks_precede_matching_specific_validation(invalid_kind):
    from fileforge.task_intelligence import _documents, matching

    doc = candidate("表.pdf", ".docx")
    if invalid_kind == "json":
        doc["metadata"] = {"invalid": float("inf")}
    else:
        doc["size"] = -1
    with patch.object(matching, "_validate_candidates") as specific:
        with patch.object(_documents, "_same_snapshot") as compare:
            result = match_requirements(["表"], [doc])
    assert_failure(result)
    specific.assert_not_called()
    compare.assert_not_called()
