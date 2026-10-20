"""Read-only Package plan, stable source observations and frozen report bytes."""

import copy
import hashlib
import json
import uuid

from fileforge.package._paths import (
    check_chain,
    check_name,
    collision_key,
    native_path,
    prepare_paths,
    scope,
    snapshot,
)
from fileforge.package._report import render_report
from fileforge.package._validation import REF, TOOLS, names, validate


def _risks(analysis, selected):
    missing = []
    unresolved = []

    def add(kind, text, tool, documents):
        slot = analysis[tool]
        value = dict(
            kind=kind,
            text=text,
            source_tool=tool,
            source_result_index=slot["result_index"] if slot else None,
            documents=documents,
        )
        if value not in unresolved:
            unresolved.append(value)

    for tool in TOOLS:
        if analysis[tool] is None:
            add("analysis_not_run", "未提供分析结果：" + tool, tool, [])
    matching = analysis["match_requirements"]
    if matching:
        missing = names(matching["result"]["data"]["missing"], "missing")
    conflict = analysis["detect_conflicts"]
    if conflict:
        for item in conflict["result"]["data"]["conflicts"]:
            add(
                "conflict",
                json.dumps(item, ensure_ascii=False, sort_keys=True),
                "detect_conflicts",
                [],
            )
    if matching:
        for group in matching["result"]["data"]["matched"]:
            if not any(
                group["requirement"] in f["requirements"]
                and f["source"] in group["documents"]
                for f in selected
            ):
                add(
                    "selection_pending",
                    "尚未纳入提议选择：" + group["requirement"],
                    "match_requirements",
                    group["documents"],
                )
    versions = analysis["compare_versions"]
    if versions:
        for group in versions["result"]["data"]["groups"]:
            if group["newest_candidate"] is None:
                add(
                    "version_undecided",
                    "版本未决："
                    + group["group_id"]
                    + "；"
                    + group["recommendation_reason"],
                    "compare_versions",
                    [{k: d[k] for k in REF} for d in group["documents"]],
                )
    return missing, unresolved


def plan_package(task, selected_files, destination, analysis):
    """Propose only; A owns Task/evidence authority and the approval boundary.

    No source/target changes, approval credential, tool registration or build.
    Reads cannot eliminate later races; A must recheck frozen bytes at execution.
    Planning hashes observe current sources, not the bytes underlying old
    analysis. That binding is absent from the current input/reader contract.
    """
    try:
        selected = validate(task, selected_files, analysis, destination)
        # Copy only after strict JSON validation. Cycles/custom objects never reach it.
        task, analysis, selected = copy.deepcopy((task, analysis, selected))
        # Freeze slot order independently of caller object-key order.
        analysis = {tool: analysis[tool] for tool in TOOLS}
        root, dest = prepare_paths(task["workspace"], destination)
        used = {collision_key("PACKAGE_REPORT.md")}
        enriched = []
        for item in selected:
            source = item["source"]
            path = native_path(source["path"])
            scope(path, root)
            if path.name != source["filename"]:
                raise ValueError("Source filename disagrees with source path")
            check_name(source["filename"])
            key = collision_key(source["filename"])
            if key in used:
                raise ValueError("Target name collision or reserved PACKAGE_REPORT.md")
            used.add(key)
            target = dest / source["filename"]
            if path == target or path.is_relative_to(dest) or path == dest:
                raise ValueError("Source/target overlap")
            enriched.append(
                dict(
                    source=source,
                    requirements=names(item["requirements"], "requirements"),
                    reason=item["reason"],
                    target=str(target),
                    snapshot=snapshot(path, root),
                )
            )
        # Recheck all source observations after the entire read set has completed.
        # Re-reading catches observable changes while a later source was hashed.
        for item in enriched:
            if snapshot(native_path(item["source"]["path"]), root) != item["snapshot"]:
                raise ValueError("Source changed during plan creation")
        prepare_paths(task["workspace"], destination)
        check_chain(root)
        missing, unresolved = _risks(analysis, enriched)
        operations = (
            [dict(kind="create_directory")]
            + [dict(kind="copy", selected_file_index=i) for i in range(len(enriched))]
            + [dict(kind="write_report"), dict(kind="verify")]
        )
        for index, op in enumerate(operations, 1):
            op["step_id"] = f"package_{index:03d}"
        plan = dict(
            task=task,
            destination=str(dest),
            selected_files=enriched,
            analysis=analysis,
            missing=missing,
            unresolved=unresolved,
            operations=operations,
            verification_targets=dict(
                selected_file_indices=list(range(len(enriched))),
                report=True,
                exact_directory_entries=True,
            ),
        )
        content = render_report(plan)
        if "\r" in content:
            raise ValueError("Report must use LF only")
        report_bytes = content.encode("utf-8", "strict")
        plan["report"] = dict(
            path=str(dest / "PACKAGE_REPORT.md"),
            content=content,
            sha256=hashlib.sha256(report_bytes).hexdigest(),
        )
        canonical = json.dumps(
            plan,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", "strict")
        digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
        plan["plan_id"] = "package_plan_" + uuid.uuid4().hex
        return dict(
            success=True,
            tool="plan_package",
            data=dict(plan=plan, plan_sha256=digest),
            message="Package plan created; not executed or approved",
            error=None,
        )
    except (
        ValueError,
        TypeError,
        OSError,
        UnicodeError,
        RecursionError,
        OverflowError,
    ) as exc:
        return dict(
            success=False,
            tool="plan_package",
            data=None,
            message="Package planning failed",
            error=str(exc) or type(exc).__name__,
        )
