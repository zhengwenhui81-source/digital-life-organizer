"""Shared Document collection rules at both public D boundaries."""

from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import call, patch

import pytest

from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements
from tests.test_task_conflicts import document


@pytest.fixture(
    params=[detect_conflicts, extract_requirements], ids=lambda f: f.__name__
)
def tool(request):
    return request.param


def assert_failure(result, tool):
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["tool"] == tool.__name__
    assert result["success"] is False
    assert result["data"] is None
    assert result["message"] and result["error"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "/other/通知.txt"),
        ("filename", "另一通知.txt"),
        ("extension", ".pdf"),
        ("text", "无需提交学生证"),
        ("size", 999),
        ("modified_time", "2026-10-18T00:00:00+00:00"),
        ("metadata", {"origin": "other"}),
        ("extra", {"task": "another"}),
    ],
)
def test_same_id_field_difference_fails_whole_call(tool, field, value):
    first = document("必须提交学生证")
    second = deepcopy(first)
    second[field] = value
    # Both snapshots independently satisfy the tool's existing shape rules.
    assert tool(documents=[first])["success"] is True
    assert tool(documents=[second])["success"] is True
    docs = [first, second]
    before = deepcopy(docs)
    for ordered in (docs, list(reversed(docs))):
        result = tool(documents=ordered)
        assert_failure(result, tool)
        assert "Contradictory Document snapshot" in result["error"]
        assert first["file_id"] in result["error"]
        assert "documents[1]" in result["error"]
    assert docs == before


@pytest.mark.parametrize(
    "left,right",
    [
        ({"nested": {"value": 1}}, {"nested": {"value": 2}}),
        ({"items": [1, 2]}, {"items": [2, 1]}),
        ({"flag": True}, {"flag": 1}),
        ({"flag": False}, {"flag": 0}),
        ({"number": 1}, {"number": 1.0}),
    ],
)
def test_metadata_recursive_differences_fail(tool, left, right):
    first = document("必须提交报名表")
    first["metadata"] = left
    second = deepcopy(first)
    second["metadata"] = right
    assert_failure(tool(documents=[first, second]), tool)


@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_equal_nested_objects_deduplicate_before_parser(tool, field):
    first = document("必须提交报名表")
    first[field] = {"a": {"x": 1, "y": [2, {"m": 3, "n": 4}]}, "b": 5}
    duplicate = deepcopy(first)
    duplicate[field] = {"b": 5, "a": {"y": [2, {"n": 4, "m": 3}], "x": 1}}
    last = document("必须提交学生证")
    last["file_id"] = "file_other"
    docs = [first, duplicate, last, deepcopy(first)]
    before = deepcopy(docs)
    module = tool.__module__
    with patch(f"{module}.parse_material_evidence", return_value=[]) as parser:
        with patch("builtins.open", side_effect=AssertionError("No file access")):
            result = tool(documents=docs)
    assert result["success"] is True
    assert parser.call_args_list == [
        call(first["text"], first["path"]),
        call(last["text"], last["path"]),
    ]
    assert docs == before


def test_different_ids_keep_identical_name_and_text(tool):
    first = document("必须提交报名表")
    second = deepcopy(first)
    second["file_id"] = "file_other"
    with patch(f"{tool.__module__}.parse_material_evidence", return_value=[]) as parser:
        assert tool(documents=[first, second])["success"] is True
    assert parser.call_count == 2


def test_all_original_items_validated_before_parser_or_dedup(tool):
    first = document("必须提交报名表")
    invalid = deepcopy(first)
    invalid["size"] = -1
    with patch(f"{tool.__module__}.parse_material_evidence") as parser:
        assert_failure(tool(documents=[first, deepcopy(first), invalid]), tool)
    parser.assert_not_called()


def test_missing_versus_present_extra_field_is_contradiction(tool):
    first = document("必须提交报名表")
    second = deepcopy(first)
    second["extra"] = None
    assert_failure(tool(documents=[first, second]), tool)


def test_file_id_change_is_distinct_identity_not_contradiction(tool):
    first = document("必须提交报名表")
    second = deepcopy(first)
    second["file_id"] = "file_different"
    assert tool(documents=[first, second])["success"] is True


def test_empty_input_standard_success(tool):
    result = tool(documents=[])
    key = "conflicts" if tool is detect_conflicts else "required_documents"
    assert result == {
        "success": True,
        "tool": tool.__name__,
        "data": {key: []},
        "message": (
            "Conflict detection completed"
            if tool is detect_conflicts
            else "Requirement extraction completed"
        ),
        "error": None,
    }


def test_real_c_snapshot_duplicate_and_changed_snapshot(tool, tmp_path):
    source = tmp_path / "通知.txt"
    source.write_text("必须提交报名表", encoding="utf-8")
    read = read_document(path=str(source))
    assert read["success"] is True
    original = read["data"]["document"]
    docs = [original, deepcopy(original)]
    before = deepcopy(docs)
    assert tool(documents=docs) == tool(documents=[original])
    assert docs == before
    source.write_text("必须提交学生证", encoding="utf-8")
    changed = read_document(path=str(source))
    assert changed["success"] is True
    assert changed["data"]["document"]["file_id"] == original["file_id"]
    assert_failure(tool(documents=[original, changed["data"]["document"]]), tool)


def test_original_collection_validated_without_inventing_version_limits(tool):
    from fileforge.task_intelligence import _documents

    first = document("正文" * 6000)
    first["extra"] = "x" * 1_048_577
    docs = [first] + [deepcopy(first) for _ in range(10)]
    with patch.object(
        _documents, "validate_documents", wraps=_documents.validate_documents
    ) as validate:
        with patch(
            f"{tool.__module__}.parse_material_evidence", return_value=[]
        ) as parser:
            assert tool(documents=docs)["success"] is True
    validate.assert_called_once_with(docs)
    assert validate.call_args.args[0] is docs
    assert len(validate.call_args.args[0]) == 11
    # Quantity, text and serialized-size limits belong to Version, not these tools.
    assert parser.call_count == 1


def test_contradiction_never_reaches_business_parser(tool):
    first = document("必须提交报名表")
    second = deepcopy(first)
    second["text"] = "无需提交报名表"
    with patch(f"{tool.__module__}.parse_material_evidence") as parser:
        assert_failure(tool(documents=[first, second]), tool)
    parser.assert_not_called()


# Shared JSON-input rules confirmed by A/C and recorded in API_CONTRACT.md.
class _CustomValue:
    def __init__(self, raises=False):
        self.raises = raises
        self.equality_calls = 0

    def __eq__(self, other):
        self.equality_calls += 1
        if self.raises:
            raise RuntimeError("Custom equality must not run during validation")
        return self is other


def _invalid_json_value(kind):
    if kind == "nan":
        return float("nan")
    if kind == "positive-infinity":
        return float("inf")
    if kind == "negative-infinity":
        return float("-inf")
    if kind == "integer-key":
        return {1: "value"}
    if kind == "boolean-key":
        return {True: "value"}
    if kind == "null-key":
        return {None: "value"}
    if kind == "set":
        return {1, 2}
    if kind == "bytes":
        return b"value"
    if kind == "datetime":
        from datetime import datetime

        return datetime(2026, 10, 18)
    if kind == "tuple":
        return (True, 1)
    if kind == "custom":
        return _CustomValue()
    if kind == "raising-custom":
        return _CustomValue(raises=True)
    if kind == "cyclic-object":
        value = {}
        value["self"] = value
        return value
    if kind == "cyclic-array":
        value = []
        value.append(value)
        return value
    raise AssertionError(f"Unknown test case: {kind}")


@pytest.mark.parametrize("field", ["metadata", "extra"])
@pytest.mark.parametrize("duplicate", [False, True], ids=["single", "same-id"])
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
def test_confirmed_non_json_input_rejected_before_analysis(
    tool, field, duplicate, kind
):
    value = _invalid_json_value(kind)
    first = document("必须提交报名表")
    first[field] = {"nested": {"value": value}}
    docs = [first]
    if duplicate:
        # A shallow copy preserves the exact test value, including cycles.
        docs.append(dict(first))
    original_id = first["file_id"]
    with ExitStack() as stack:
        parser = stack.enter_context(
            patch(f"{tool.__module__}.parse_material_evidence")
        )
        deadlines = (
            stack.enter_context(patch(f"{tool.__module__}._deadlines"))
            if tool is detect_conflicts
            else None
        )
        try:
            result = tool(documents=docs)
        finally:
            # No deepcopy/equality on cyclic or custom data, even after exceptions.
            assert docs[0] is first
            assert first["file_id"] == original_id
            assert first[field]["nested"]["value"] is value
            if duplicate:
                assert docs[1] is not first
                assert docs[1][field] is first[field]
            if kind == "cyclic-object":
                assert value["self"] is value
            elif kind == "cyclic-array":
                assert len(value) == 1 and value[0] is value
            elif kind in {"custom", "raising-custom"}:
                assert value.equality_calls == 0
            parser.assert_not_called()
            if deadlines is not None:
                deadlines.assert_not_called()
    assert_failure(result, tool)


@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_confirmed_shared_noncyclic_json_is_accepted(tool, field):
    shared = {"items": [None, True, False, 1, 0, "文字", {"a": 2, "b": 3}]}
    first = document("必须提交报名表")
    first[field] = {"left": shared, "right": shared}
    second = dict(first)
    second[field] = {"right": shared, "left": shared}
    with patch(f"{tool.__module__}.parse_material_evidence", return_value=[]) as parser:
        result = tool(documents=[first, second])
    assert result["success"] is True
    parser.assert_called_once_with(first["text"], first["path"])
    assert first[field]["left"] is shared
    assert first[field]["right"] is shared
    assert second[field]["left"] is shared
    assert shared["items"][1] is True
    assert shared["items"][2] is False


@pytest.mark.parametrize("field", ["metadata", "extra"])
@pytest.mark.parametrize(
    "left,right",
    [
        ([1, 2], [2, 1]),
        ({"flag": True}, {"flag": 1}),
        ({"flag": False}, {"flag": 0}),
        ({"number": 1}, {"number": 1.0}),
    ],
    ids=["array-order", "true-vs-one", "false-vs-zero", "integer-vs-float"],
)
def test_confirmed_json_differences_still_fail_without_analysis(
    tool, field, left, right
):
    first = document("必须提交报名表")
    first[field] = {"nested": left}
    second = dict(first)
    second[field] = {"nested": right}
    with patch(f"{tool.__module__}.parse_material_evidence") as parser:
        result = tool(documents=[first, second])
    parser.assert_not_called()
    assert_failure(result, tool)
    assert first[field]["nested"] is left
    assert second[field]["nested"] is right


@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_deep_json_input_has_no_python_recursion_depth_limit(tool, field):
    left, right = {"leaf": True}, {"leaf": True}
    for _ in range(2000):
        left, right = {"child": [left]}, {"child": [right]}
    first = document("必须提交报名表")
    first[field] = left
    second = dict(first)
    second[field] = right
    with patch(f"{tool.__module__}.parse_material_evidence", return_value=[]) as parser:
        assert tool(documents=[first, second])["success"] is True
    parser.assert_called_once()
    assert first[field] is left
    assert second[field] is right


@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_invalid_later_input_is_checked_before_snapshot_comparison(tool, field):
    first = document("必须提交报名表")
    second = dict(first)
    second["text"] = "无需提交报名表"
    last = document("必须提交学生证")
    value = _CustomValue(raises=True)
    last[field] = {"value": value}
    from fileforge.task_intelligence import _documents

    with patch.object(_documents, "_same_snapshot") as compare:
        with patch(f"{tool.__module__}.parse_material_evidence") as parser:
            result = tool(documents=[first, second, last])
    assert_failure(result, tool)
    assert "documents[2]" in result["error"]
    compare.assert_not_called()
    parser.assert_not_called()
    assert value.equality_calls == 0
    assert last[field]["value"] is value


@pytest.mark.parametrize("field", ["metadata", "extra"])
def test_nested_missing_field_differs_from_explicit_null(tool, field):
    first = document("必须提交报名表")
    first[field] = {"nested": {}}
    second = dict(first)
    second[field] = {"nested": {"value": None}}
    result = tool(documents=[first, second])
    assert_failure(result, tool)
    assert "documents[1]" in result["error"]
    assert "value" not in first[field]["nested"]
    assert second[field]["nested"]["value"] is None


@pytest.mark.parametrize("field", ["metadata", "extra"])
@pytest.mark.parametrize("duplicate", [False, True])
def test_all_legal_json_scalar_types_are_accepted(tool, field, duplicate):
    first = document("必须提交报名表")
    values = [None, True, False, "", "文字", 0, 1, -2, 1.0, -0.5, [], {}]
    first[field] = {"values": values}
    docs = [first, dict(first)] if duplicate else [first]
    assert tool(documents=docs)["success"] is True
    assert first[field]["values"] is values
    assert values[1] is True and values[2] is False
    assert type(values[8]) is float
