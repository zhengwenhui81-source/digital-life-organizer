"""Read-only, deterministic conflict detection over contract-shaped Documents."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fileforge.task_intelligence._context import _unconditional_sentences
from fileforge.task_intelligence._documents import validate_documents
from fileforge.task_intelligence._encoding import (
    deadline_field,
    material_field,
    material_value,
    source_path,
)
from fileforge.task_intelligence._materials import parse_material_evidence

# Anchored labels deliberately avoid comparing different kinds of deadlines.
_DEADLINE = re.compile(
    r"^(?P<scope>报名|材料提交|提交|申请|答辩)?"
    r"截止(?:日期|时间)?\s*[：:]?\s*"
    r"(?P<y>\d{4})(?:年|[-/])(?P<m>\d{1,2})(?:月|[-/])"
    r"(?P<d>\d{1,2})日?"
    r"(?:[ T]*(?P<h>\d{1,2})(?:[:：]|时|点)(?P<minute>\d{1,2})分?"
    r"(?::(?P<second>\d{2}))?)?\s*$"
)


def _deadlines(text: str):
    for sentence in _unconditional_sentences(text):
        clauses = re.split(r"[，,]", sentence)
        # An unsupported prefix may qualify all following dates. Never throw
        # it away to expose an apparently unconditional deadline.
        if not _DEADLINE.fullmatch(clauses[0].strip()):
            continue
        for clause in clauses:
            match = _DEADLINE.fullmatch(clause.strip())
            if not match:
                continue
            parts = match.groupdict()
            try:
                date = datetime(int(parts["y"]), int(parts["m"]), int(parts["d"]))
                value = f"{date.year:04}-{date.month:02}-{date.day:02}"
                if parts["h"] is not None:
                    hour, minute = int(parts["h"]), int(parts["minute"])
                    second = int(parts["second"] or 0)
                    date.replace(hour=hour, minute=minute, second=second)
                    value += f"T{hour:02}:{minute:02}:{second:02}"
            except ValueError:
                continue
            yield parts["scope"] or "", value


def detect_conflicts(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze Documents without reading paths or modifying caller data.

    Call as detect_conflicts(documents=[...]), matching the public JSON input.
    Caller supplies notices for one task and enforces workspace authorization.
    Unsupported text is ignored rather than interpreted speculatively.
    """
    error = validate_documents(documents)
    if error:
        return {
            "success": False,
            "tool": "detect_conflicts",
            "data": None,
            "message": "Conflict detection failed",
            "error": error,
        }
    deadlines: dict[str, list[dict]] = {}
    materials: dict[str, list[dict]] = {}
    for document in documents:
        source = source_path(document)
        for context, value in _deadlines(document["text"]):
            deadlines.setdefault(context, []).append({"value": value, "source": source})
        for evidence in parse_material_evidence(document["text"], source):
            materials.setdefault(evidence.material, []).append(
                {"value": material_value(evidence.required), "source": evidence.source}
            )
    conflicts = []
    groups = [
        (deadline_field(scope), values) for scope, values in deadlines.items()
    ] + [(material_field(material), values) for material, values in materials.items()]
    for field, values in groups:
        if field.startswith("deadline"):
            # Date-only evidence is not midnight. Different calendar days always
            # disagree; same-day times disagree only when both are explicit.
            distinct = list(dict.fromkeys(entry["value"] for entry in values))
            disagrees = any(
                left[:10] != right[:10]
                or ("T" in left and "T" in right and left != right)
                for index, left in enumerate(distinct)
                for right in distinct[index + 1 :]
            )
        else:
            disagrees = len({entry["value"] for entry in values}) > 1
        if not disagrees:
            continue
        unique = []
        for entry in values:
            if entry not in unique:
                unique.append(entry)
        conflicts.append(
            {"field": field, "values": unique, "recommendation": "请人工确认"}
        )
    return {
        "success": True,
        "tool": "detect_conflicts",
        "data": {"conflicts": conflicts},
        "message": "Conflict detection completed",
        "error": None,
    }
