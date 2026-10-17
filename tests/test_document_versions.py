"""Version contract acceptance with real public worker and controlled snapshots."""

from __future__ import annotations

import copy
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fileforge.document import compare_versions, read_document
from fileforge.document import versions as api
from fileforge.document._version_core import compare


def document(name="report_v1.txt", text=None, identity="a", **fields):
    return {
        "file_id": identity,
        "path": "/unknown/" + name,
        "filename": name,
        "extension": Path(name).suffix,
        "text": text or ("common line\n" * 12 + "old\n"),
        "size": 100,
        "modified_time": "2026-10-17T10:00:00+00:00",
        "metadata": {},
        **fields,
    }


def pair(name="report"):
    return [
        document(name + "_v1.txt"),
        document(name + "_v2.txt", "common line\n" * 12 + "new\n", "b"),
    ]


def failure(result, contains=""):
    assert set(result) == {"success", "tool", "data", "message", "error"}
    assert result["success"] is False and result["data"] is None
    assert result["tool"] == "compare_versions"
    assert result["message"] and contains.lower() in result["error"].lower()


@pytest.mark.parametrize("value", [None, {}, "", [None], [{}], ["placeholder"]])
def test_invalid_input(value):
    failure(compare_versions(value))


@pytest.mark.parametrize(
    "field,value",
    [
        ("file_id", ""),
        ("path", None),
        ("filename", " "),
        ("extension", 1),
        ("text", " \n"),
        ("size", True),
        ("size", -1),
        ("modified_time", None),
        ("metadata", []),
    ],
)
def test_document_validation(field, value):
    d = document()
    d[field] = value
    failure(compare_versions([d]), field)


def test_missing_fields():
    for field in document():
        d = document()
        del d[field]
        failure(compare_versions([d]), field)


def test_empty_and_unknown_workspace_are_success():
    assert compare_versions([])["data"] == {"groups": []}
    docs = [
        document("notes.txt", "short", "x"),
        document("other.txt", "different", "y"),
    ]
    result = compare_versions(docs)
    assert result["success"] and result["error"] is None
    assert len(result["data"]["groups"]) == 2
    for g in result["data"]["groups"]:
        assert g["recommendation_reason"] == "single_document"
        assert g["newest_candidate"] is None and g["changes"] == []


@pytest.mark.parametrize(
    "material", ["项目介绍", "奖学金申请", "综测说明", "个人总结", "课程报告"]
)
def test_public_task_neutral_recommendation(material):
    docs = pair(material)
    before = copy.deepcopy(docs)
    result = compare_versions(docs)
    assert result["success"], result
    g = result["data"]["groups"][0]
    assert len(g["documents"]) == 2
    assert g["newest_candidate"]["file_id"] == "b"
    assert g["recommendation_reason"] == "unique_highest_explicit_version"
    assert g["comparison_order"] == {
        "basis": "explicit_version",
        "tie_breaker": "file_id_ascending",
        "chronology_confirmed": False,
    }
    assert g["changes"][0]["before"] == {
        "start_line": 13,
        "end_line": 13,
        "text": "old\n",
    }
    assert g["changes"][0]["after"]["text"] == "new\n"
    assert docs == before


def test_permutations_complete_link_and_stable_direction():
    docs = pair() + [
        document("report_最终版.txt", pair()[0]["text"], "c"),
        document("unrelated.txt", identity="z"),
    ]
    expected = compare(docs)
    for permutation in itertools.permutations(docs):
        assert compare(list(permutation)) == expected
    assert compare_versions(list(reversed(docs)))["data"] == expected
    assert expected["groups"][0]["recommendation_reason"] == "insufficient_evidence"
    assert expected["groups"][0]["comparison_order"]["basis"] == "stable_id_display"


@pytest.mark.parametrize(
    "suffix",
    ["v1", "v1.1", "v1.2.3", "最终版", "修改版", "修订版", "终稿", "final", "final2"],
)
def test_whitelist_and_identical_short_text(suffix):
    a = document("material_v0.txt", "same", "a")
    b = document(f"material_{suffix}.txt", "same", "b")
    g = compare([a, b])["groups"][0]
    assert len(g["documents"]) == 2
    assert g["recommendation_reason"] == "identical_content"
    assert g["newest_candidate"] is None
    assert g["changes"][0]["type"] == "identical"
    assert g["changes"][0]["summary"] == "提取文本相同"


@pytest.mark.parametrize(
    "name",
    [
        "material_V2.txt",
        "material_FINAL.txt",
        "material-v2.txt",
        "material final.txt",
        "material_final3.txt",
        "material_v1.2.3.4.txt",
        "material_2026.txt",
        "material_v1_final.txt",
        "material_final_middle.txt",
        "Material_v2.txt",
    ],
)
def test_no_broad_normalization(name):
    assert (
        len(
            compare([document("material_v1.txt"), document(name, identity="b")])[
                "groups"
            ]
        )
        == 2
    )


def test_content_threshold_and_bucket_boundaries():
    for text in ["a" * 99, "a" * 84 + "b" * 16]:
        assert (
            len(
                compare(
                    [document(text="a" * 100), document("report_v2.txt", text, "b")]
                )["groups"]
            )
            == 2
        )
    assert (
        len(
            compare(
                [
                    document(text="a" * 100),
                    document("report_v2.txt", "a" * 85 + "b" * 15, "b"),
                ]
            )["groups"]
        )
        == 1
    )
    for fields in [{"path": "/elsewhere/report_v2.txt"}, {"extension": ".pdf"}]:
        docs = pair()
        docs[1].update(fields)
        assert len(compare(docs)["groups"]) == 2
    docs = [
        document(text="a" * 100),
        document("report_v2.txt", "a" * 85 + "b" * 15, "b"),
        document("report_v3.txt", "a" * 70 + "b" * 30, "c"),
    ]
    groups = compare(docs)["groups"]
    assert [len(g["documents"]) for g in groups] == [2, 1]


@pytest.mark.parametrize(
    "time_value,expected",
    [
        ("2026-10-18T10:00:00+00:00", "opposing_time_signal"),
        ("2026-10-17T18:00:00+08:00", "unique_highest_explicit_version"),
        ("2026-10-18T10:00:00", "unique_highest_explicit_version"),
        ("", "unique_highest_explicit_version"),
        ("invalid", "unique_highest_explicit_version"),
    ],
)
def test_time_signals(time_value, expected):
    docs = pair()
    docs[0]["modified_time"] = time_value
    g = compare(docs)["groups"][0]
    assert g["recommendation_reason"] == expected
    if time_value in ["", "invalid", "2026-10-18T10:00:00"]:
        assert "未参与" in g["newest_candidate"]["reasons"][0]


def test_priority_ties_and_lower_tie_order():
    docs = pair()
    docs[1]["filename"] = "report_v1.0.txt"
    assert compare(docs)["groups"][0]["recommendation_reason"] == "version_tie"
    docs.append(document("report_v2.txt", docs[1]["text"], "c"))
    g = compare(docs)["groups"][0]
    assert g["newest_candidate"]["file_id"] == "c"
    assert g["comparison_order"]["basis"] == "stable_id_display"
    for d in docs:
        d["text"] = "same"
    assert compare(docs)["groups"][0]["recommendation_reason"] == "identical_content"


def test_insert_delete_original_lines_and_adjacent_only():
    base = "common line\r\n" * 15
    docs = [
        document("report_v1.txt", base, "a"),
        document("report_v2.txt", base + "tail\r\n", "b"),
        document("report_v3.txt", base, "c"),
    ]
    changes = compare(docs)["groups"][0]["changes"]
    assert [c["type"] for c in changes] == ["insert", "delete"]
    assert changes[0]["before"] is None and changes[1]["after"] is None
    assert changes[0]["after"] == {"start_line": 16, "end_line": 16, "text": "tail\r\n"}
    assert changes[0]["from"]["file_id"] == "a" and changes[1]["to"]["file_id"] == "c"


def test_duplicates_metadata_order_and_extra_fields():
    a = document(metadata={"x": {"a": 1, "b": [2, 3]}, "y": 2})
    b = copy.deepcopy(a)
    b["metadata"] = {"y": 2, "x": {"b": [2, 3], "a": 1}}
    assert len(compare_versions([a, b])["data"]["groups"][0]["documents"]) == 1
    for field in a:
        b = copy.deepcopy(a)
        if field == "file_id":
            continue
        if field == "metadata":
            b[field] = {"different": True}
        elif field == "size":
            b[field] += 1
        else:
            b[field] += "changed"
        failure(compare_versions([a, b]), "contradictory")
    b = copy.deepcopy(a)
    b["extra"] = True
    failure(compare_versions([a, b]), "contradictory")


@pytest.mark.parametrize("value", [object(), float("nan"), float("inf"), "\ud800"])
def test_serialization_failures(value):
    failure(compare_versions([document(metadata={"bad": value})]))


def test_circular_input():
    metadata = {}
    metadata["self"] = metadata
    failure(compare_versions([document(metadata=metadata)]), "circular")


def test_json_count_matches_compact_serialization_and_chunks():
    value = {
        "documents": [
            document(
                metadata={
                    "中文": '"\\\n😀' * 5000,
                    "keys": {"null": 1, "2": True},
                    "array": [1, 1.5, None, False],
                }
            )
        ]
    }
    chunks = list(api._json_chunks(value))
    assert (
        b"".join(chunks)
        == json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    )
    assert max(map(len, chunks)) <= 4096 * 6


def test_volume_includes_wrapper_and_all_fields(monkeypatch):
    d = document(metadata={"padding": ""}, extra="also counted")
    base = len(
        json.dumps(
            {"documents": [d]},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )
    d["metadata"]["padding"] = "x" * (1_048_576 - base)
    assert len(api._validate([d])) == 1_048_576
    assert compare_versions([d])["success"]
    d["metadata"]["padding"] += "x"
    monkeypatch.setattr(
        api, "_worker_command", lambda: pytest.fail("must fail before worker")
    )
    failure(compare_versions([d]), "1048577 bytes exceeds limit 1048576")
    d["metadata"]["padding"] += "x" * 200_000
    failure(compare_versions([d]), "1248577 bytes")


def test_resources_before_deduplication():
    d = document(text="x" * 10_000)
    assert len(json.loads(api._validate([d] * 5))["documents"]) == 1
    failure(compare_versions([d] * 6), "60000")
    failure(compare_versions([document()] * 11), "count 11")
    assert api._validate([document()] * 10)
    failure(compare_versions([document(text="x" * 10_001)]), "10001")
    docs = [document(text="x" * 10_000, identity=str(i)) for i in range(5)]
    docs.append(document(text="x", identity="extra"))
    failure(compare_versions(docs), "50001")
    d = document(metadata={"padding": "x" * 600_000})
    failure(compare_versions([d, d]), "exceeds limit 1048576")


def test_public_parser_input_and_source_preserved(tmp_path):
    files = [tmp_path / "材料_v1.txt", tmp_path / "材料_v2.txt"]
    for path, text in zip(files, [d["text"] for d in pair()], strict=True):
        path.write_text(text)
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]
    docs = [read_document(str(p))["data"]["document"] for p in files]
    result = compare_versions(docs)
    assert result["success"], result
    assert (
        result["data"]["groups"][0]["newest_candidate"]["file_id"] == docs[1]["file_id"]
    )
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in files]


def test_timeout_reaps_actual_process(monkeypatch):
    processes = []
    original = subprocess.Popen

    def tracked(*args, **kwargs):
        p = original(*args, **kwargs)
        processes.append(p)
        return p

    monkeypatch.setattr(api.subprocess, "Popen", tracked)
    monkeypatch.setattr(
        api,
        "_worker_command",
        lambda: [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    start = time.monotonic()
    failure(compare_versions(pair()), "timed out")
    assert time.monotonic() - start < 8
    assert len(processes) == 1 and processes[0].poll() is not None
    assert (
        processes[0].stdin.closed
        and processes[0].stdout.closed
        and processes[0].stderr.closed
    )


@pytest.mark.parametrize(
    "script", ["raise SystemExit(2)", "print('not json')", "print('{}')"]
)
def test_worker_failures_no_partial_results(monkeypatch, script):
    monkeypatch.setattr(api, "_worker_command", lambda: [sys.executable, "-c", script])
    failure(compare_versions(pair()))


def test_worker_start_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("startup unavailable")

    monkeypatch.setattr(api.subprocess, "Popen", fail)
    failure(compare_versions(pair()), "startup unavailable")


@pytest.mark.parametrize(
    "middle,expected_ids",
    [
        ("a" * 80 + "b" * 10 + "c" * 10, ["a", "c"]),
        ("a" * 80 + "b" * 5 + "c" * 15, ["a"]),
    ],
)
def test_eligible_group_score_and_tie_break(middle, expected_ids):
    docs = [
        document("report_v1.txt", "a" * 80 + "b" * 20, "a"),
        document("report_v2.txt", "a" * 80 + "c" * 20, "b"),
        document("report_v3.txt", middle, "c"),
    ]
    expected = compare(docs)
    assert [d["file_id"] for d in expected["groups"][0]["documents"]] == expected_ids
    for order in itertools.permutations(docs):
        assert compare(list(order)) == expected


def test_real_repetitive_comparison_budget_ends_worker(monkeypatch):
    processes = []
    original = subprocess.Popen

    def tracked(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(api.subprocess, "Popen", tracked)
    docs = [
        document(f"report_v{i}.txt", "ab" * 4999 + str(i) + "x", str(i))
        for i in range(5)
    ]
    failure(compare_versions(docs), "timed out")
    assert len(processes) == 1 and processes[0].poll() is not None


def test_cleanup_error_is_failure_without_partial_data(monkeypatch):
    class Unreapable:
        returncode = None

        def communicate(self, *args, **kwargs):
            raise subprocess.TimeoutExpired("worker", kwargs["timeout"])

        def kill(self):
            pass

    monkeypatch.setattr(api.subprocess, "Popen", lambda *a, **kw: Unreapable())
    failure(compare_versions(pair()), "cleanup failed")


def test_ten_unique_inputs_short_unknown_names():
    docs = [document(f"unknown_{i}.txt", "short", str(i)) for i in range(10)]
    result = compare_versions(docs)
    assert result["success"] and len(result["data"]["groups"]) == 10


def test_measuring_large_metadata_does_not_copy_whole_string():
    import tracemalloc

    d = document(metadata={"padding": "x" * 8_000_000})
    tracemalloc.start()
    try:
        failure(compare_versions([d]), "exceeds limit 1048576")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 500_000


def test_empty_stem_and_same_text_different_materials_stay_separate():
    docs = [document("_v1.txt", "same", "a"), document("_v2.txt", "same", "b")]
    assert len(compare(docs)["groups"]) == 2


def test_nested_array_order_and_json_type_differences_are_conflicts():
    a = document(metadata={"items": [1, 2], "value": 1})
    b = copy.deepcopy(a)
    b["metadata"]["items"].reverse()
    failure(compare_versions([a, b]), "contradictory")
    b = copy.deepcopy(a)
    b["metadata"]["value"] = True
    failure(compare_versions([a, b]), "contradictory")


def test_metadata_numeric_key_types_cannot_hide_conflicting_snapshots():
    a = document(metadata={1: "value"})
    b = document(metadata={True: "value"})
    failure(compare_versions([a, b]), "keys must be strings")


@pytest.mark.parametrize(
    "suffix",
    ["v2", "v1.1", "v1.2.3", "最终版", "修改版", "修订版", "终稿", "final", "final2"],
)
def test_suffix_before_trailing_newline_is_not_a_suffix(suffix):
    from fileforge.document._version_core import _name

    name = f"report_{suffix}\n.txt"
    assert _name(document(name)) == (f"report_{suffix}\n", None)
    docs = [document(), document(name, pair()[1]["text"], "b")]
    result = compare_versions(docs)
    assert result["success"], result
    groups = result["data"]["groups"]
    assert len(groups) == 2
    assert all(g["newest_candidate"] is None for g in groups)


@pytest.mark.parametrize("suffix", ["v2", "最终版"])
def test_real_trailing_newline_filename_via_parser(tmp_path, suffix):
    names = ["report_v1.txt", f"report_{suffix}\n.txt"]
    paths = [tmp_path / name for name in names]
    try:
        for path, d in zip(paths, pair(), strict=True):
            path.write_text(d["text"], encoding="utf-8")
    except OSError as exc:
        pytest.skip(f"Filesystem does not support this filename: {type(exc).__name__}")
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
    docs = []
    for path in paths:
        result = read_document(str(path))
        assert result["success"], result
        docs.append(result["data"]["document"])
    result = compare_versions(docs)
    assert result["success"], result
    assert len(result["data"]["groups"]) == 2
    assert all(g["newest_candidate"] is None for g in result["data"]["groups"])
    assert before == [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]


@pytest.mark.parametrize("reverse_keys", [False, True])
@pytest.mark.parametrize("nested", [False, True])
def test_lossy_object_keys_fail_before_worker_without_mutation(
    monkeypatch, reverse_keys, nested
):
    keys = [(1, "numeric"), ("1", "string")]
    if reverse_keys:
        keys.reverse()
    metadata = dict(keys)
    if nested:
        metadata = {"items": [{"nested": metadata}]}
    a = document(metadata=metadata)
    b = copy.deepcopy(a)
    if nested:
        inner = b["metadata"]["items"][0]["nested"]
        b["metadata"]["items"][0]["nested"] = dict(reversed(list(inner.items())))
    else:
        b["metadata"] = dict(reversed(list(metadata.items())))
    before = copy.deepcopy([a, b])
    before_order = repr([a, b])
    monkeypatch.setattr(
        api, "_worker_command", lambda: pytest.fail("invalid input reached worker")
    )
    for docs in ([a], [a, b], [b, a]):
        failure(compare_versions(docs), "string")
    assert [a, b] == before
    assert repr([a, b]) == before_order
    assert list(a["metadata"].items()) == list(before[0]["metadata"].items())


@pytest.mark.parametrize("key", [None, False, 2, 1.5])
def test_nonstring_keys_in_extra_nested_fields_are_invalid(key):
    failure(compare_versions([document(extra={"items": [{key: "value"}]})]), "string")


def test_legal_string_key_order_preserves_full_snapshot_and_permutations():
    a = document(metadata={"1": "string", "nested": {"a": 1, "b": [2, 3]}})
    duplicate = copy.deepcopy(a)
    duplicate["metadata"] = {"nested": {"b": [2, 3], "a": 1}, "1": "string"}
    b = pair()[1]
    docs = [a, duplicate, b]
    before = copy.deepcopy(docs)
    before_order = repr(docs)
    expected = compare_versions(docs)
    assert expected["success"], expected
    for order in itertools.permutations(docs):
        assert compare_versions(list(order)) == expected
    returned = expected["data"]["groups"][0]["documents"][0]
    assert returned == a
    assert returned["metadata"] == a["metadata"]
    assert docs == before
    assert repr(docs) == before_order


def test_non_json_tuple_cannot_silently_become_list():
    failure(compare_versions([document(metadata={"values": (1, 2)})]), "JSON")
