"""D-only observations, not acceptance of stale evidence at A's preview gate.

A integration tests must reject uncertified/stale evidence before executable
preview. This suite invokes no A adapter, approval or execution entry point.
"""

import copy
import hashlib
import os
from pathlib import Path

import pytest

from fileforge.document import compare_versions, read_document
from fileforge.package import plan_package
from fileforge.task_intelligence import extract_requirements
from tests import test_package_planning as fixtures

request_data = fixtures.request_data


@pytest.mark.parametrize("include_versions", [False, True])
def test_d_only_observes_current_bytes_without_certifying_old_analysis(
    request_data, include_versions
):
    source = Path(request_data["selected_files"][0]["source"]["path"])
    notice = source.parent / "通知.txt"
    old_doc = read_document(path=str(source))["data"]["document"]
    old_notice = read_document(path=str(notice))["data"]["document"]
    if include_versions:
        version = compare_versions(documents=[old_doc])
        assert version["success"], version
        request_data["analysis"]["compare_versions"]["result"] = version
    old_analysis = copy.deepcopy(request_data["analysis"])
    old_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    for path, before, after in ((source, "模板", "正文"), (notice, "必须", "无需")):
        info = path.stat()
        raw = path.read_bytes()
        rewritten = raw.replace(before.encode(), after.encode())
        assert rewritten != raw and len(rewritten) == len(raw)
        path.write_bytes(rewritten)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        assert path.stat().st_size == info.st_size
        assert path.stat().st_mtime_ns == info.st_mtime_ns
    new_doc = read_document(path=str(source))["data"]["document"]
    for key in ("file_id", "path", "filename", "size", "modified_time"):
        assert new_doc[key] == old_doc[key]
    assert new_doc["text"] != old_doc["text"]
    new_notice = read_document(path=str(notice))["data"]["document"]
    assert new_notice["file_id"] == old_notice["file_id"]
    fresh = extract_requirements(documents=[new_notice])
    assert fresh["success"] and fresh["data"]["required_documents"] == []
    result = plan_package(**request_data)
    # D can render a read-only proposal but cannot certify its analysis freshness.
    # Success here MUST NOT be used as permission for A's executable preview.
    # A's no-preview behavior belongs in A integration acceptance tests.
    assert result["success"], result
    plan = result["data"]["plan"]
    snapshot = plan["selected_files"][0]["snapshot"]
    assert snapshot["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert snapshot["sha256"] != old_hash
    assert plan["analysis"] == old_analysis
    assert plan["analysis"]["extract_requirements"]["result"]["data"][
        "required_documents"
    ] == ["课程笔记"]
    assert [u["kind"] for u in plan["unresolved"]] == (
        ["version_undecided"] if include_versions else []
    )
    if include_versions:
        retained = plan["analysis"]["compare_versions"]["result"]["data"]["groups"][0][
            "documents"
        ][0]
        assert (
            retained["text"] == old_doc["text"] and retained["text"] != new_doc["text"]
        )
    assert plan["missing"] == []
    assert "课程笔记" in plan["report"]["content"]
    assert "D 不执行所附分析与原始文件字节的绑定校验" in plan["report"]["content"]
    assert "A 的检查是否通过不由本报告判定" in plan["report"]["content"]
    assert "计划生成成功不代表已获准进入可执行预览" in plan["report"]["content"]
    assert set(result["data"]) == {"plan", "plan_sha256"}
    assert "不能证明旧分析仍适用" in plan["report"]["content"]
    assert request_data["analysis"] == old_analysis
