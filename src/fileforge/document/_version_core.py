"""Deterministic, task-neutral comparison performed inside the isolated worker."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from fileforge.analysis.versions import extract_version

_SUFFIX = re.compile(
    r"_(v[0-9]+(?:\.[0-9]+){0,2}|最终版|修改版|修订版|终稿|final2|final)\Z"
)


def _name(document: dict) -> tuple[str, tuple | None]:
    stem = Path(document["filename"]).stem
    match = _SUFFIX.search(stem)
    if match is None or match.start() == 0:
        return stem, None
    version = None
    if match[1].startswith("v"):
        # Extract only the validated suffix; never an earlier middle-name version.
        version = extract_version("material_" + match[1] + ".txt")
    return stem[: match.start()], version


def _ref(document: dict) -> dict:
    return {key: document[key] for key in ("file_id", "path", "filename")}


def _time(document: dict) -> datetime | None:
    try:
        value = datetime.fromisoformat(document["modified_time"])
        return value.astimezone(UTC) if value.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def _recommend(documents: list[dict], versions: dict) -> tuple[str, dict | None]:
    if len(documents) == 1:
        return "single_document", None
    if len({d["text"] for d in documents}) == 1:
        return "identical_content", None
    if any(versions[d["file_id"]] is None for d in documents):
        return "insufficient_evidence", None
    highest = max(versions[d["file_id"]] for d in documents)
    winners = [d for d in documents if versions[d["file_id"]] == highest]
    if len(winners) != 1:
        return "version_tie", None
    candidate = winners[0]
    candidate_time = _time(candidate)
    lower = [d for d in documents if versions[d["file_id"]] < highest]
    times = [_time(d) for d in lower]
    if candidate_time is not None and any(
        t is not None and t > candidate_time for t in times
    ):
        return "opposing_time_signal", None
    unavailable = candidate_time is None or any(t is None for t in times)
    reason = "唯一最高显式版本；可比较的时间未提供相反信号。"
    if unavailable:
        reason += "缺失或不可比较的时间未参与判断。"
    reason += "仅推荐候选，未经用户最终确认。"
    return "unique_highest_explicit_version", {**_ref(candidate), "reasons": [reason]}


def _evidence(lines: list[str], start: int, end: int) -> dict | None:
    if start == end:
        return None
    return {"start_line": start + 1, "end_line": end, "text": "".join(lines[start:end])}


def _changes(left: dict, right: dict) -> list[dict]:
    a, b = left["text"].splitlines(keepends=True), right["text"].splitlines(
        keepends=True
    )
    base = {"from": _ref(left), "to": _ref(right)}
    if left["text"] == right["text"]:
        return [
            {
                **base,
                "type": "identical",
                "before": _evidence(a, 0, len(a)),
                "after": _evidence(b, 0, len(b)),
                "summary": "提取文本相同",
            }
        ]
    changes = []
    for kind, i, j, k, end in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if kind == "equal":
            continue
        before, after = _evidence(a, i, j), _evidence(b, k, end)
        if kind == "insert":
            summary = f"插入第{k + 1}至{end}行：{after['text']}"
        elif kind == "delete":
            summary = f"删除第{i + 1}至{j}行：{before['text']}"
        else:
            summary = (
                f"第{i + 1}至{j}行替换为第{k + 1}至{end}行："
                f"{before['text']} → {after['text']}"
            )
        changes.append(
            {**base, "type": kind, "before": before, "after": after, "summary": summary}
        )
    return changes


def compare(documents: list[dict]) -> dict:
    names = {d["file_id"]: _name(d) for d in documents}
    versions = {key: value[1] for key, value in names.items()}
    buckets: dict[tuple, list] = {}
    for d in sorted(documents, key=lambda d: d["file_id"]):
        bucket = (str(Path(d["path"]).parent), d["extension"], names[d["file_id"]][0])
        buckets.setdefault(bucket, []).append(d)
    scores = {}

    def score(a: dict, b: dict) -> float:
        a, b = sorted((a, b), key=lambda d: d["file_id"])
        key = (a["file_id"], b["file_id"])
        if key not in scores:
            if a["text"] == b["text"]:
                scores[key] = 1.0
            elif min(len(a["text"]), len(b["text"])) < 100:
                scores[key] = 0.0
            else:
                scores[key] = SequenceMatcher(
                    None, a["text"], b["text"], autojunk=False
                ).ratio()
        return scores[key]

    groups = []
    for bucket in buckets.values():
        local = []
        for d in bucket:
            eligible = []
            for group in local:
                minimum = min(score(d, member) for member in group)
                if minimum >= 0.85:
                    eligible.append(
                        (-minimum, tuple(m["file_id"] for m in group), group)
                    )
            if eligible:
                min(eligible, key=lambda item: item[:2])[2].append(d)
            else:
                local.append([d])
        groups.extend(local)
    groups.sort(key=lambda g: tuple(d["file_id"] for d in g))
    output = []
    for index, group in enumerate(groups, 1):
        minimum = min(
            (score(a, b) for i, a in enumerate(group) for b in group[i + 1 :]),
            default=None,
        )
        explicit = all(versions[d["file_id"]] is not None for d in group) and len(
            {versions[d["file_id"]] for d in group}
        ) == len(group)
        ordered = sorted(
            group, key=lambda d: versions[d["file_id"]] if explicit else d["file_id"]
        )
        reason, candidate = _recommend(ordered, versions)
        output.append(
            {
                "group_id": f"version_group_{index:03d}",
                "documents": ordered,
                "grouping": {
                    "basis": (
                        "same parent, extension, normalized name "
                        "and content evidence"
                    ),
                    "normalized_name": names[group[0]["file_id"]][0],
                    "similarity_method": "sequence_matcher",
                    "minimum_pair_similarity": minimum,
                },
                "recommendation_reason": reason,
                "comparison_order": {
                    "basis": "explicit_version" if explicit else "stable_id_display",
                    "tie_breaker": "file_id_ascending",
                    "chronology_confirmed": False,
                },
                "newest_candidate": candidate,
                "changes": [
                    c for a, b in zip(ordered, ordered[1:]) for c in _changes(a, b)
                ],
            }
        )
    return {"groups": output}
