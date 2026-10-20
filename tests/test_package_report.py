"""Frozen report bytes preserve unknown analysis and safely render user text."""

from fileforge.package import plan_package
from tests import test_package_planning as fixtures

request_data = fixtures.request_data


def test_markdown_and_newline_escaping(request_data):
    request_data["task"]["user_goal"] = "<script>\r\n# injected | [link](x)"
    request_data["selected_files"][0]["reason"] = "*approved*\n<script>"
    result = plan_package(**request_data)
    assert result["success"], result
    body = result["data"]["plan"]["report"]["content"]
    assert "<script>" not in body and "\r" not in body
    assert "\n# injected" not in body
    assert "&lt;script&gt;" in body and "&#10;" in body
    assert "尚未执行、尚未验证" in body
    assert "不证明实际执行或验证成功" in body
    assert "待同次预览批准确认" in body
    assert "D 不执行所附分析与原始文件字节的绑定校验" in body
    assert "A 的检查是否通过不由本报告判定" in body
    assert "计划生成成功不代表已获准进入可执行预览" in body
    assert "A 尚未验证" not in body
    assert "A 的校验未通过" not in body


def test_unknown_distinct_from_successful_empty(request_data):
    known = plan_package(**request_data)
    request_data["analysis"] = dict.fromkeys(request_data["analysis"])
    unknown = plan_package(**request_data)
    assert known["success"] and unknown["success"]
    a, b = (x["data"]["plan"] for x in (known, unknown))
    assert a["missing"] == b["missing"] == []
    assert a["unresolved"] == [] and len(b["unresolved"]) == 4
    assert "未提供分析结果" not in a["report"]["content"]
    assert "未提供分析结果" in b["report"]["content"]


def test_no_mutation_of_returned_evidence_aliases_input(request_data):
    result = plan_package(**request_data)
    assert result["success"]
    result["data"]["plan"]["analysis"]["match_requirements"]["result"]["data"][
        "missing"
    ].append("new")
    assert (
        request_data["analysis"]["match_requirements"]["result"]["data"]["missing"]
        == []
    )
