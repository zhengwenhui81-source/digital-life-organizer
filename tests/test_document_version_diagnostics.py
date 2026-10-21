"""Version bridge graphs, real Agent arguments and public format boundaries."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from itertools import permutations
from pathlib import Path

import pytest
from docx import Document

from fileforge.agent.executor import ToolRouter
from fileforge.agent.planner import validate_plan
from fileforge.agent.service import TaskConflict, TaskService
from fileforge.document import compare_versions, read_document
from fileforge.document._version_core import compare
from fileforge.extractor import extract_snippet
from tests.test_document_versions import document


def bridge_texts():
    common = "shared baseline sentence\n" * 24
    return [
        common + "x" * 400,
        common + "x" * 350 + "y" * 50,
        common + "x" * 200 + "y" * 200,
    ]


def members(data):
    return {frozenset(d["filename"] for d in g["documents"]) for g in data["groups"]}


@pytest.mark.parametrize(
    "ids,expected",
    [
        (("a", "b", "c"), ({"record_v1.docx", "record_v2.docx"}, {"record_v3.docx"})),
        (("c", "a", "b"), ({"record_v2.docx", "record_v3.docx"}, {"record_v1.docx"})),
    ],
)
def test_bridge_graph_is_complete_link_and_fixed_input_order_invariant(ids, expected):
    docs = [
        document(f"record_v{i + 1}.docx", text, identity)
        for i, (text, identity) in enumerate(zip(bridge_texts(), ids, strict=True))
    ]
    first = compare(docs)
    assert members(first) == {frozenset(g) for g in expected}
    assert sum(len(g["documents"]) for g in first["groups"]) == 3
    for ordering in permutations(docs):
        assert compare(list(ordering)) == first


def test_public_version_keeps_all_bridge_candidates_without_transitive_merge():
    docs = [
        document(f"record_v{i + 1}.docx", text, str(i))
        for i, text in enumerate(bridge_texts())
    ]
    result = compare_versions(docs)
    assert result["success"], result
    assert members(result["data"]) == {
        frozenset({"record_v1.docx", "record_v2.docx"}),
        frozenset({"record_v3.docx"}),
    }
    singleton = next(g for g in result["data"]["groups"] if len(g["documents"]) == 1)
    assert singleton["newest_candidate"] is None and singleton["changes"] == []


class RecordingRouter(ToolRouter):
    def __init__(self):
        super().__init__()
        self.version_arguments = []

    def call(self, name, arguments, *, approved=False):
        if name == "compare_versions":
            self.version_arguments.append(copy.deepcopy(arguments))
        return super().call(name, arguments, approved=approved)


def fingerprints(root):
    return {
        p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
        for p in root.iterdir()
    }


@pytest.mark.parametrize("collection", ["list_files", "search_files"])
def test_default_agent_forwards_three_complete_real_docx_documents(
    tmp_path, collection
):
    for i, body in enumerate(bridge_texts(), start=1):
        source = Document()
        source.add_paragraph(body)
        source.save(tmp_path / f"record_v{i}.docx")
    for extension in (".cpp", ".json", ".csv"):
        (tmp_path / ("record" + extension)).write_text("fixture", encoding="utf-8")
    before = fingerprints(tmp_path)

    def planner(task_id, goal, workspace):
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": collection,
                        "description": "Discover fixture files",
                        "arguments": {
                            "workspace": workspace,
                            **(
                                {"query": "record"}
                                if collection == "search_files"
                                else {}
                            ),
                        },
                    },
                    {
                        "tool": "read_document",
                        "description": "Read runtime candidates",
                        "arguments": {},
                    },
                    {
                        "tool": "compare_versions",
                        "description": "Compare successful reads",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    router = RecordingRouter()
    service = TaskService(planner=planner, router=router)
    task = service.create("Read and compare; no file writes", str(tmp_path))
    service.run(task["task_id"])
    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "completed", snapshot["error"]
    reads = [
        r["data"]["document"]
        for r in snapshot["results"]
        if r["tool"] == "read_document"
    ]
    assert len(reads) == 3
    assert {d["filename"] for d in reads} == {f"record_v{i}.docx" for i in (1, 2, 3)}
    assert router.version_arguments == [{"documents": reads}]
    groups = snapshot["results"][-1]["data"]["groups"]
    assert sorted(
        (d for g in groups for d in g["documents"]), key=lambda d: d["file_id"]
    ) == sorted(reads, key=lambda d: d["file_id"])
    report = service.report(task["task_id"])
    assert report["version_groups"] == groups
    assert len(report["found_files"]) == 6
    assert fingerprints(tmp_path) == before
    assert snapshot["pending_operations"] == []


@pytest.mark.parametrize("suffix", [".cpp", ".CPP", ".json", ".JSON", ".csv", ".CSV"])
def test_read_document_does_not_inherit_upstream_text_extensions(tmp_path, suffix):
    path = tmp_path / ("fixture" + suffix)
    path.write_text('fixture body: {"value":1}\na,b\n', encoding="utf-8")
    before = path.read_bytes(), path.stat().st_mtime_ns
    result = read_document(str(path))
    assert result["success"] is False and result["data"] is None
    assert "Unsupported document format" in result["error"]
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


@pytest.mark.parametrize(
    "suffix,snippet_available", [(".cpp", True), (".json", True), (".csv", False)]
)
def test_snippet_dispatch_is_distinct_from_public_document_reader(
    tmp_path, suffix, snippet_available
):
    path = tmp_path / ("fixture" + suffix)
    path.write_text("fixture body", encoding="utf-8")
    assert (extract_snippet(path) is not None) is snippet_available
    assert read_document(str(path))["success"] is False


@pytest.mark.parametrize("suffix", [".cpp", ".json", ".csv"])
def test_explicit_unsupported_read_stops_agent_before_comparison(tmp_path, suffix):
    path = tmp_path / ("fixture" + suffix)
    path.write_text("fixture", encoding="utf-8")

    def planner(task_id, goal, workspace):
        return validate_plan(
            {
                "steps": [
                    {
                        "tool": "read_document",
                        "description": "Explicit read",
                        "arguments": {"path": str(path)},
                    },
                    {
                        "tool": "compare_versions",
                        "description": "Compare",
                        "arguments": {},
                    },
                ]
            },
            task_id,
            goal,
        )

    router = RecordingRouter()
    service = TaskService(planner=planner, router=router)
    task = service.create("Inspect fixture", str(tmp_path))
    service.run(task["task_id"])
    snapshot = service.snapshot(task["task_id"])
    assert snapshot["task"]["status"] == "failed"
    assert snapshot["results"][0]["data"] is None
    assert router.version_arguments == []
    with pytest.raises(TaskConflict):
        service.report(task["task_id"])


def load_diagnostic():
    path = Path(__file__).parents[1] / "docs/examples/diagnose_document_versions.py"
    spec = importlib.util.spec_from_file_location("document_diagnostic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostic_passes_full_documents_but_omits_text_from_summary(
    tmp_path, monkeypatch
):
    path = tmp_path / "fixture.txt"
    path.write_text("fixture full original text", encoding="utf-8")
    expected = read_document(str(path))["data"]["document"]
    module = load_diagnostic()
    original = module.compare_versions
    captured = []

    def tracked(documents):
        captured.append(copy.deepcopy(documents))
        return original(documents)

    monkeypatch.setattr(module, "compare_versions", tracked)
    result = module.diagnose([path])
    assert captured == [[expected]]
    assert result["compare_success"] and result["source_observations_unchanged"]
    assert "fixture full original text" not in repr(result)


def test_diagnostic_never_silently_drops_unsupported_inputs(tmp_path, monkeypatch):
    paths = [tmp_path / "fixture.txt", tmp_path / "fixture.csv"]
    for p in paths:
        p.write_text("fixture", encoding="utf-8")
    module = load_diagnostic()

    def forbidden(documents):
        raise AssertionError("Must not compare a partial successful subset")

    monkeypatch.setattr(module, "compare_versions", forbidden)
    result = module.diagnose(paths)
    assert len(result["reads"]) == 2
    assert result["compare_called"] is False
    assert result["compare_success"] is None


def test_snapshot_diagnostic_detects_read_but_not_compared_file():
    module = load_diagnostic()
    docs = [document(f"record_v{i}.txt", identity=str(i)) for i in (1, 2, 3)]
    snapshot = {
        "task": {"task_id": "synthetic"},
        "results": [
            *[
                {"tool": "read_document", "success": True, "data": {"document": d}}
                for d in docs
            ],
            {
                "tool": "compare_versions",
                "success": True,
                "data": {"groups": [{"documents": docs[:2]}]},
                "error": None,
            },
        ],
    }
    report = module.inspect_snapshot(snapshot, [d["filename"] for d in docs])
    assert report["missing_successful_reads"] == []
    assert report["missing_from_successful_comparison"] == ["record_v3.txt"]
    assert report["comparison_documents_match_prior_full_reads"] is True


def test_snapshot_diagnostic_does_not_fall_back_after_failed_comparison():
    module = load_diagnostic()
    snapshot = {
        "results": [
            {
                "tool": "compare_versions",
                "success": True,
                "data": {"groups": []},
                "error": None,
            },
            {
                "tool": "compare_versions",
                "success": False,
                "data": None,
                "error": "current failure",
            },
        ]
    }
    report = module.inspect_snapshot(snapshot, ["record.txt"])
    assert report["compare_success"] is False
    assert report["comparison_result_index"] == 1
    assert report["missing_from_successful_comparison"] is None
    assert report["comparison_documents_match_prior_full_reads"] is None


def test_snapshot_diagnostic_compares_complete_snapshot_strict_types():
    module = load_diagnostic()
    original = document(metadata={"value": 1})
    changed = copy.deepcopy(original)
    changed["metadata"]["value"] = 1.0
    snapshot = {
        "results": [
            {"tool": "read_document", "success": True, "data": {"document": original}},
            {
                "tool": "compare_versions",
                "success": True,
                "data": {"groups": [{"documents": [changed]}]},
                "error": None,
            },
        ]
    }
    report = module.inspect_snapshot(snapshot, [])
    assert report["comparison_documents_match_prior_full_reads"] is False
