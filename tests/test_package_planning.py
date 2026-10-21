"""Contract-level Package planning with real public C reads and D analysis."""

import copy
import hashlib
import json

import pytest

from fileforge.document import read_document
from fileforge.package import plan_package
from fileforge.task_intelligence import extract_requirements, match_requirements


@pytest.fixture
def request_data(tmp_path):
    source = tmp_path / "课程笔记.txt"
    source.write_text("这是课程笔记模板，内容尚未审核。", encoding="utf-8")
    read = read_document(str(source))
    assert read["success"]
    document = read["data"]["document"]
    notice = tmp_path / "通知.txt"
    notice.write_text("必须提交课程笔记", encoding="utf-8")
    extraction = extract_requirements(
        documents=[read_document(str(notice))["data"]["document"]]
    )
    matching = match_requirements(
        required_documents=extraction["data"]["required_documents"],
        candidate_documents=[document],
    )

    def success(tool, data):
        return dict(success=True, tool=tool, data=data, message="Completed", error=None)

    analysis = {
        "extract_requirements": {"result_index": 0, "result": extraction},
        "match_requirements": {"result_index": 1, "result": matching},
        "detect_conflicts": {
            "result_index": 2,
            "result": success("detect_conflicts", {"conflicts": []}),
        },
        "compare_versions": {
            "result_index": 3,
            "result": success("compare_versions", {"groups": []}),
        },
    }
    return dict(
        task=dict(task_id="course", user_goal="整理课程资料", workspace=str(tmp_path)),
        selected_files=[
            dict(
                source={k: document[k] for k in ("file_id", "path", "filename")},
                requirements=["课程笔记"],
                reason="当前成功分析的提议，等待审批",
            )
        ],
        destination=str(tmp_path / "课程包"),
        analysis=analysis,
    )


def test_complete_plan(request_data):
    before = copy.deepcopy(request_data)
    a = plan_package(**request_data)
    b = plan_package(**request_data)
    assert a["success"], a
    p = a["data"]["plan"]
    assert p["plan_id"] != b["data"]["plan"]["plan_id"]
    assert a["data"]["plan_sha256"] == b["data"]["plan_sha256"]
    assert p["missing"] == p["unresolved"] == []
    assert [o["kind"] for o in p["operations"]] == [
        "create_directory",
        "copy",
        "write_report",
        "verify",
    ]
    assert [o["step_id"] for o in p["operations"]] == [
        "package_001",
        "package_002",
        "package_003",
        "package_004",
    ]
    assert p["operations"][1]["selected_file_index"] == 0
    assert p["verification_targets"] == dict(
        selected_file_indices=[0], report=True, exact_directory_entries=True
    )
    source = request_data["selected_files"][0]["source"]
    assert p["selected_files"][0]["source"] == source
    raw = open(source["path"], "rb").read()
    snapshot = p["selected_files"][0]["snapshot"]
    assert snapshot["sha256"] == hashlib.sha256(raw).hexdigest()
    assert snapshot["size"] == len(raw)
    assert (
        p["report"]["sha256"]
        == hashlib.sha256(p["report"]["content"].encode("utf-8")).hexdigest()
    )
    canonical = json.dumps(
        {k: v for k, v in p.items() if k != "plan_id"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert a["data"]["plan_sha256"] == "sha256:" + hashlib.sha256(canonical).hexdigest()
    assert request_data == before


def test_unknown_and_failed_analysis(request_data):
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    a = plan_package(**request_data)
    assert a["success"], a
    assert [u["source_tool"] for u in a["data"]["plan"]["unresolved"]] == list(
        request_data["analysis"]
    )
    assert all(u["kind"] == "analysis_not_run" for u in a["data"]["plan"]["unresolved"])
    assert "未提供分析结果" in a["data"]["plan"]["report"]["content"]
    request_data["analysis"]["match_requirements"] = dict(
        result_index=1,
        result=dict(
            success=False,
            tool="match_requirements",
            data=None,
            message="Failed",
            error="read failure",
        ),
    )
    a = plan_package(**request_data)
    assert not a["success"] and a["data"] is None


def test_dedup_and_contradiction(request_data):
    request_data["selected_files"] *= 2
    a = plan_package(**request_data)
    assert a["success"] and len(a["data"]["plan"]["selected_files"]) == 1
    request_data["selected_files"] = [
        copy.deepcopy(x) for x in request_data["selected_files"]
    ]
    request_data["selected_files"][1]["reason"] = "different"
    a = plan_package(**request_data)
    assert not a["success"] and a["data"] is None


@pytest.mark.parametrize(
    "bad", [float("nan"), float("inf"), set(), b"x", (1,), object()]
)
def test_invalid_json(request_data, bad):
    request_data["task"]["user_goal"] = bad
    a = plan_package(**request_data)
    assert not a["success"] and a["data"] is None


def test_missing_unselected_conflict_and_version(request_data, tmp_path):
    extra = tmp_path / "证明_v2.txt"
    extra.write_text("证明模板，尚未填写", encoding="utf-8")
    d = read_document(str(extra))["data"]["document"]
    req = ["课程笔记", "证明", "签字页"]
    request_data["task"]["user_goal"] = "准备奖学金材料"
    request_data["analysis"]["extract_requirements"]["result"]["data"][
        "required_documents"
    ] = req
    doc = read_document(request_data["selected_files"][0]["source"]["path"])["data"][
        "document"
    ]
    request_data["analysis"]["match_requirements"]["result"] = match_requirements(
        required_documents=req, candidate_documents=[doc, d]
    )
    conflict = dict(
        field="deadline",
        values=[
            dict(value="2026-10-18", source="a"),
            dict(value="2026-10-20", source="b"),
        ],
    )
    request_data["analysis"]["detect_conflicts"]["result"]["data"]["conflicts"] = [
        conflict
    ]
    # Real public Version shape; no recommendation or auto-selection.
    from fileforge.document import compare_versions

    version = compare_versions(documents=[d])
    assert version["success"], version
    request_data["analysis"]["compare_versions"]["result"] = version
    a = plan_package(**request_data)
    assert a["success"], a
    p = a["data"]["plan"]
    assert p["missing"] == ["签字页"]
    assert [u["kind"] for u in p["unresolved"]] == [
        "conflict",
        "selection_pending",
        "version_undecided",
    ]
    assert len(p["selected_files"]) == 1
    assert "证明\\_v2\\.txt" in p["report"]["content"]
    assert r"2026\-10\-18" in p["report"]["content"]
    assert p["analysis"] == request_data["analysis"]


def test_incompatible_evidence(request_data):
    request_data["analysis"]["match_requirements"]["result"]["data"][
        "required_documents"
    ] = ["other"]
    a = plan_package(**request_data)
    assert not a["success"] and a["data"] is None


@pytest.mark.parametrize("field", ["path", "filename"])
def test_reference_contradictions_across_evidence(request_data, field):
    request_data["selected_files"][0]["source"][field] += "changed"
    result = plan_package(**request_data)
    assert not result["success"] and result["data"] is None


@pytest.mark.parametrize(
    "tool",
    [
        "extract_requirements",
        "match_requirements",
        "detect_conflicts",
        "compare_versions",
    ],
)
def test_any_supplied_failure_stops_before_read(request_data, tool, monkeypatch):
    from fileforge.package import planning

    def forbidden(*args, **kwargs):
        raise AssertionError("Source read after upstream failure")

    monkeypatch.setattr(planning, "snapshot", forbidden)
    request_data["analysis"][tool]["result"].update(
        success=False, data=None, error="upstream failure"
    )
    result = plan_package(**request_data)
    assert not result["success"] and result["data"] is None
    assert tool in result["error"]


def test_full_empty_analysis_not_unknown(request_data):
    for tool in ("extract_requirements", "match_requirements"):
        request_data["analysis"][tool]["result"]["data"]["required_documents"] = []
    request_data["analysis"]["match_requirements"]["result"]["data"].update(
        matched=[], missing=[]
    )
    request_data["selected_files"][0]["requirements"] = []
    r = plan_package(**request_data)
    assert r["success"], r
    assert r["data"]["plan"]["unresolved"] == []
    assert "成功提取但要求为空" in r["data"]["plan"]["report"]["content"]


def test_nested_json_cycle_and_shared_data(request_data):
    cycle = []
    cycle.append(cycle)
    request_data["analysis"]["compare_versions"]["result"]["data"]["groups"] = cycle
    r = plan_package(**request_data)
    assert not r["success"] and r["data"] is None and "circular" in r["error"]
    assert cycle[0] is cycle


def test_custom_comparison_never_called(request_data):
    class Meta(type):
        def __eq__(cls, other):
            raise AssertionError("metaclass equality")

    class Custom(metaclass=Meta):
        def __eq__(self, other):
            raise AssertionError("instance equality")

    value = Custom()
    request_data["selected_files"][0]["reason"] = value
    r = plan_package(**request_data)
    assert not r["success"] and r["data"] is None
    assert request_data["selected_files"][0]["reason"] is value


def test_deep_json_returns_failure_not_recursion_error(request_data):
    value = []
    for _ in range(1500):
        value = [value]
    request_data["analysis"]["compare_versions"]["result"]["data"]["groups"] = value
    r = plan_package(**request_data)
    assert not r["success"] and r["data"] is None


def test_stable_order_with_two_selected_files(request_data, tmp_path):
    source = tmp_path / "额外附件.txt"
    source.write_text("附件内容", encoding="utf-8")
    d = read_document(str(source))["data"]["document"]
    extra = dict(
        source={k: d[k] for k in ("file_id", "path", "filename")},
        requirements=[],
        reason="额外提议附件",
    )
    request_data["selected_files"].insert(0, extra)
    request_data["selected_files"].append(copy.deepcopy(extra))
    request_data["analysis"] = dict(reversed(list(request_data["analysis"].items())))
    r = plan_package(**request_data)
    assert r["success"], r
    p = r["data"]["plan"]
    assert [x["source"]["filename"] for x in p["selected_files"]] == [
        "额外附件.txt",
        "课程笔记.txt",
    ]
    assert [
        x["selected_file_index"] for x in p["operations"] if x["kind"] == "copy"
    ] == [0, 1]
    assert p["verification_targets"]["selected_file_indices"] == [0, 1]


@pytest.mark.parametrize(
    "name,goal", [("成绩证明", "准备奖学金材料"), ("项目总结", "准备课程项目结题")]
)
def test_real_task_domains(tmp_path, name, goal):
    notice = tmp_path / "通知.txt"
    notice.write_text("必须提交" + name, encoding="utf-8")
    source = tmp_path / (name + ".txt")
    source.write_text("未填写的模板正文，不能证明审核完成", encoding="utf-8")
    extraction = extract_requirements(
        documents=[read_document(str(notice))["data"]["document"]]
    )
    document = read_document(str(source))["data"]["document"]
    matching = match_requirements(
        required_documents=extraction["data"]["required_documents"],
        candidate_documents=[document],
    )
    analysis = dict(
        extract_requirements=dict(result_index=0, result=extraction),
        match_requirements=dict(result_index=1, result=matching),
        detect_conflicts=None,
        compare_versions=None,
    )
    r = plan_package(
        task=dict(task_id="task", user_goal=goal, workspace=str(tmp_path)),
        selected_files=[
            dict(
                source={k: document[k] for k in ("file_id", "path", "filename")},
                requirements=[name],
                reason="任务分析提议",
            )
        ],
        destination=str(tmp_path / "材料包"),
        analysis=analysis,
    )
    assert r["success"], r
    assert r["data"]["plan"]["missing"] == []
    assert [x["source_tool"] for x in r["data"]["plan"]["unresolved"]] == [
        "detect_conflicts",
        "compare_versions",
    ]
    assert "不代表材料内容或真实性审核通过" in r["data"]["plan"]["report"]["content"]


def test_different_id_same_path_is_not_rejected(request_data):
    request_data["selected_files"][0]["source"][
        "file_id"
    ] = "caller-supplied-other-identity"
    r = plan_package(**request_data)
    assert r["success"], r
    assert (
        r["data"]["plan"]["selected_files"][0]["source"]["file_id"]
        == "caller-supplied-other-identity"
    )
    assert r["data"]["plan"]["unresolved"][0]["kind"] == "selection_pending"


def test_version_recommendation_does_not_change_proposal(request_data, tmp_path):
    from fileforge.document import compare_versions

    documents = []
    for suffix, end in [("v1", "甲"), ("v2", "乙")]:
        path = tmp_path / f"课程笔记_{suffix}.txt"
        path.write_text("同一课程资料的共同正文" * 30 + end, encoding="utf-8")
        documents.append(read_document(str(path))["data"]["document"])
    version = compare_versions(documents=documents)
    assert version["success"], version
    groups = version["data"]["groups"]
    assert len(groups) == 1 and groups[0]["newest_candidate"] is not None
    assert groups[0]["newest_candidate"]["file_id"] == documents[1]["file_id"]
    request_data["analysis"]["compare_versions"]["result"] = version
    request_data["analysis"]["match_requirements"]["result"] = match_requirements(
        required_documents=["课程笔记"], candidate_documents=documents
    )
    request_data["selected_files"][0]["source"] = {
        k: documents[0][k] for k in ("file_id", "path", "filename")
    }
    r = plan_package(**request_data)
    assert r["success"], r
    assert (
        r["data"]["plan"]["selected_files"][0]["source"]["file_id"]
        == documents[0]["file_id"]
    )
    assert r["data"]["plan"]["analysis"]["compare_versions"]["result"] == version


def test_manual_proposal_does_not_erase_frozen_missing(request_data):
    request_data["analysis"]["match_requirements"]["result"]["data"].update(
        matched=[], missing=["课程笔记"]
    )
    r = plan_package(**request_data)
    assert r["success"], r
    assert r["data"]["plan"]["missing"] == ["课程笔记"]
    assert r["data"]["plan"]["unresolved"] == []
