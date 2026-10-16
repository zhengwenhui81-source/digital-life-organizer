"""Report content is a plan, never proof of execution or verification."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from fileforge.package._planning import _plan_package
from fileforge.package._report import _render_plan_report
from tests.test_package_planning import ref


def test_report_shows_task_requirements_mapping_and_unexecuted_state():
    plan = _plan_package("task_1", ["报名表"], [ref()], "/workspace/package")
    text = _render_plan_report(plan)
    assert "task\\_1" in text
    assert "报名表" in text and "/inputs/报名表\\.pdf" in text
    assert "/workspace/package/报名表\\.pdf" in text
    assert "尚未执行、尚未验证" in text
    assert "未创建目录、未复制材料、未写入报告" in text
    assert "验证通过" not in text and "已完成" not in text
    assert "Approval Gate" in text


def test_unknown_analysis_is_distinct_from_explicit_empty():
    plan = _plan_package("task", [], [ref()], "/workspace/package")
    unknown = _render_plan_report(plan)
    empty = _render_plan_report(plan, conflicts=[], missing=[])
    assert unknown.count("未提供分析结果") == 2
    assert "未提供分析结果" not in empty
    assert empty.count("调用方明确提供空结果") == 2
    assert "无冲突" not in unknown and "无缺项" not in unknown


def test_markdown_html_and_newlines_are_escaped_not_interpreted():
    plan = _plan_package(
        "task\n# fake",
        ["[报名表]|<script>\n**材料**"],
        [ref("[材料]_`v1`.txt")],
        "/workspace/package",
    )
    text = _render_plan_report(
        plan,
        conflicts=[{"field": "<img>", "value": "[x](url)"}],
        missing=["身份证\n# fake"],
    )
    assert "task<br>\\# fake" in text
    assert "\\[报名表\\]\\|&lt;script&gt;<br>\\*\\*材料\\*\\*" in text
    assert "\\[材料\\]\\_\\`v1\\`\\.txt" in text
    assert "<script>" not in text and "<img>" not in text
    assert "\n# fake" not in text


@pytest.mark.parametrize("status", ["completed", "executing", "failed"])
def test_nonplan_states_rejected(status):
    plan = _plan_package("task", [], [ref()], "/workspace/package")
    plan["status"] = status
    with pytest.raises(ValueError, match="planned"):
        _render_plan_report(plan)


def test_tampered_targets_rejected():
    plan = _plan_package("task", [], [ref()], "/workspace/package")
    plan["copies"][0]["destination"] = "/elsewhere/材料.pdf"
    with pytest.raises(ValueError):
        _render_plan_report(plan)


def test_renderer_no_io_inputs_unchanged_and_order_stable():
    plan = _plan_package("task", ["学生证", "报名表"], [ref()], "/workspace/package")
    conflicts, missing = [{"field": "deadline", "values": ["a", "b"]}], ["学生证"]
    before = deepcopy((plan, conflicts, missing))
    with (
        patch("io.open", side_effect=AssertionError("No IO")),
        patch("builtins.open", side_effect=AssertionError("No IO")),
        patch("os.mkdir", side_effect=AssertionError("No mkdir")),
        patch("os.stat", side_effect=AssertionError("No stat")),
    ):
        text = _render_plan_report(plan, conflicts=conflicts, missing=missing)
        assert text == _render_plan_report(plan, conflicts=conflicts, missing=missing)
    assert (plan, conflicts, missing) == before
    assert text.index("- 学生证") < text.index("- 报名表")
