"""Render only a frozen plan record; never an execution or review certificate."""

import html
import json
import re


def escape(value):
    value = re.sub(r"([\\`*_{}\[\]()#+.!|~-])", r"\\\1", str(value))
    value = html.escape(value, quote=True)
    return value.replace("\r", "&#13;").replace("\n", "&#10;")


def render_report(plan):
    lines = [
        "# PACKAGE 计划记录",
        "",
        "审批前冻结的计划记录；不证明实际执行或验证成功。",
        "生成本计划时，打包尚未执行、尚未验证；"
        "文件名候选不代表材料内容或真实性审核通过。",
        "选材是提议，待同次预览批准确认；本报告不记录实际执行结果。",
        "D 不执行所附分析与原始文件字节的绑定校验；"
        "A 的检查是否通过不由本报告判定，须查阅 A 的权威记录。",
        "来源 SHA-256 仅记录规划时内容，不能证明旧分析仍适用。",
        "计划生成成功不代表已获准进入可执行预览或执行文件操作。",
        "",
        "任务：" + escape(plan["task"]["task_id"]),
        "目标：" + escape(plan["task"]["user_goal"]),
        "计划目录：" + escape(plan["destination"]),
        "",
        "## 要求",
    ]
    extraction = plan["analysis"]["extract_requirements"]
    if extraction:
        requirements = extraction["result"]["data"]["required_documents"]
        lines += ["- " + escape(x) for x in requirements] or [
            "成功提取但要求为空；不表示材料齐全。"
        ]
    else:
        lines += ["未提供分析结果；要求未知。"]
    lines += ["", "## 提议映射"]
    for item in plan["selected_files"]:
        lines += [
            "- " + escape(item["source"]["path"]) + " → " + escape(item["target"]),
            "  提议依据：" + escape(item["reason"]),
            "  来源 SHA-256：" + item["snapshot"]["sha256"],
        ]
    lines += ["", "## 已知缺项（仅本次未找到文件名候选）"]
    lines += ["- " + escape(x) for x in plan["missing"]] or [
        (
            "当前成功匹配未报告缺项。"
            if plan["analysis"]["match_requirements"]
            else "未提供分析结果；不代表无缺项。"
        )
    ]
    lines += ["", "## 未决事项"]
    lines += [
        "- " + escape(json.dumps(u, ensure_ascii=False, sort_keys=True))
        for u in plan["unresolved"]
    ] or ["成功分析未报告未决事项；不代表材料审核通过。"]
    lines += ["", "## 冻结分析及全部候选（含未提议的备选）"]
    for tool, slot in plan["analysis"].items():
        lines += [
            "- "
            + escape(tool)
            + ": "
            + (
                "未提供分析结果"
                if slot is None
                else escape(json.dumps(slot, ensure_ascii=False, sort_keys=True))
            )
        ]
    lines += ["", "## 操作计划"]
    lines += [
        "- " + escape(json.dumps(o, ensure_ascii=False, sort_keys=True))
        for o in plan["operations"]
    ]
    return "\n".join(lines) + "\n"
