"""Pure Markdown rendering of a package PLAN, never an execution report."""

from __future__ import annotations

import html
import json
import re
from typing import Any

from fileforge.package._planning import _plan_package


def _escape(value: str) -> str:
    text = html.escape(value, quote=True)
    text = re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _analysis(label: str, value: list | None) -> list[str]:
    lines = [f"## {label}"]
    if value is None:
        lines.append("未提供分析结果")
    elif not value:
        lines.append("调用方明确提供空结果（不代表已执行或已验证）")
    else:
        lines.extend(
            "- " + _escape(json.dumps(item, ensure_ascii=False)) for item in value
        )
    return lines


def _render_plan_report(
    plan: dict[str, Any], *, conflicts: list | None = None, missing: list | None = None
) -> str:
    """Return Markdown only. Optional analysis is supplied, never inferred.

    The adjustable private plan must be exactly the pure planner's output.
    Reject completed/modified plans rather than accidentally rendering success.
    """
    if not isinstance(plan, dict) or plan.get("status") != "planned":
        raise ValueError("Only a planned package can be rendered")
    try:
        expected = _plan_package(
            plan["task_id"],
            plan["requirements"],
            [
                {
                    "file_id": c["source_file_id"],
                    "path": c["source"],
                    "filename": c["filename"],
                }
                for c in plan["copies"]
            ],
            plan["planned_package_path"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid private package plan") from exc
    if expected != plan:
        raise ValueError("Plan differs from the pure planner's output")
    if any(
        value is not None and not isinstance(value, list)
        for value in (conflicts, missing)
    ):
        raise ValueError("Analysis must be a list or None")
    try:
        sections = (
            _analysis("冲突（调用方提供）", conflicts)
            + [""]
            + _analysis("缺项（调用方提供）", missing)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Analysis must be JSON-serializable") from exc
    lines = [
        "# 材料包计划报告",
        "",
        "**尚未执行、尚未验证。此文档不是实际打包完成报告。**",
        "未创建目录、未复制材料、未写入报告；来源存在性和目标可创建性均未检查。",
        "",
        "任务：" + _escape(plan["task_id"]),
        "计划包目录：" + _escape(plan["planned_package_path"]),
        "计划报告路径：" + _escape(plan["planned_report_path"]),
        "",
        "## 要求",
    ]
    lines.extend(
        ["- " + _escape(name) for name in plan["requirements"]] or ["未提供要求条目"]
    )
    lines.extend(
        ["", "## 计划复制（未执行）", "", "| 来源 | 计划目标 |", "| --- | --- |"]
    )
    lines.extend(
        f"| {_escape(c['source'])} | {_escape(c['destination'])} |"
        for c in plan["copies"]
    )
    lines.extend(
        ["", *sections, "", "所有文件操作仍须经 A 的 Approval Gate 批准后执行。"]
    )
    return "\n".join(lines) + "\n"
