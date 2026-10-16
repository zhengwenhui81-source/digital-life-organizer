"""Conservative, reusable material evidence parsing; no public schema."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialEvidence:
    material: str
    required: bool
    source: str


_ASSERTION = re.compile(
    r"^(?:请)?(?P<mode>必须提交|须提交|需提交|需要提交|无需提交|不必提交|不需要提交)"
    r"[：:\s]*(?P<items>.+)$"
)
_REQUIRED_MODES = {"必须提交", "须提交", "需提交", "需要提交"}
_ITEM = re.compile(r"[\w\u4e00-\u9fff· -]{1,40}")
_NUMBER = re.compile(
    r"^(?:\d+[.、．)]|[（(]\d+[)）]|[一二三四五六七八九十]+、|[-*])\s*(.+)$"
)
_HEADING = re.compile(
    r"^(?:#{1,6}\s*)?(?:[一二三四五六七八九十]+、)?"
    r"(?:提交材料|所需材料|必交材料)(?:\s*[:：]\s*(.*))?$"
)
_OTHER_SECTION = re.compile(
    r"^(?:活动安排|时间安排|注意事项|联系方式|报名流程|评审安排|提交方式|其他事项)(?:[:：].*)?$"
)
# A condition/alternative governs the entire expression, not just a list item.
_COMPLEX = re.compile(
    r"或|任选|二选一|选一|如|若|根据|视情况|仅限|限于|的需|的须|者需|者须"
)
_MODIFIER = re.compile(r"非必需|非必交|必交|选交|不需|不用|为|可不|建议|可选|自愿")
_MARKER = re.compile(r"(.+?)(?:（必交）|\(必交\))$")


def _items(text: str, source: str, default: bool | None) -> list[MaterialEvidence]:
    """A default only comes from an explicit assertion or bounded heading."""
    text = text.strip().rstrip("。；;")
    if _COMPLEX.search(text):
        return []
    assertion = _ASSERTION.fullmatch(text)
    if assertion:
        default = assertion["mode"] in _REQUIRED_MODES
        text = assertion["items"]
    # Embedded assertions require separate sentences; never inherit the first
    # assertion's polarity across a later statement, optional or otherwise.
    if re.search(r"提交", text):
        return []
    evidence = []
    for item in re.split(r"[、，,]", text):
        item = item.strip()
        required = default
        marker = _MARKER.fullmatch(item)
        if marker:
            if default is False:
                continue  # Contradictory annotation: do not guess its polarity.
            item = marker[1].strip()
            required = True
        if required is None or not _ITEM.fullmatch(item) or _MODIFIER.search(item):
            continue
        evidence.append(MaterialEvidence(item, required, source))
    return evidence


def _clause_evidence(
    clause: str, source: str, default: bool | None
) -> list[MaterialEvidence]:
    # Keep conditions/alternatives attached before separating explicit assertions.
    if _COMPLEX.search(clause):
        return []
    evidence = []
    for statement in re.split(
        r"[，,]\s*(?=(?:请)?(?:必须提交|须提交|需提交|需要提交|无需提交|不必提交|不需要提交))",
        clause,
    ):
        evidence.extend(_items(statement, source, default))
    return evidence


def parse_material_evidence(text: str, source: str) -> list[MaterialEvidence]:
    """Parse assertions, explicit mandatory markers and bounded material lists.

    A heading covers only immediately following numbered/bulleted lines. Blank
    lines, ordinary paragraphs and new headings end the scope. No aliases,
    quantity reasoning, conditional inference or filesystem access is involved.
    """
    evidence = []
    in_list = False
    list_indent = None
    for raw_line in text.splitlines():
        expanded = raw_line.expandtabs()
        indent = len(expanded) - len(expanded.lstrip())
        line = raw_line.strip()
        if not line:
            in_list = False
            list_indent = None
            continue
        if list_indent is not None and indent > list_indent:
            continue  # Nested content must not escape a conditional parent item.
        heading = _HEADING.fullmatch(line)
        if heading:
            in_list = True
            list_indent = None
            if heading[1]:
                for clause in re.split(r"[。；;！？!?]", heading[1]):
                    evidence.extend(_clause_evidence(clause, source, True))
            continue
        numbered = _NUMBER.fullmatch(line)
        body = numbered[1] if numbered else line
        if _OTHER_SECTION.fullmatch(body) or body.endswith(("：", ":")):
            in_list = False
            continue
        if in_list and numbered and list_indent is None:
            list_indent = indent
        default = True if in_list and numbered else None
        if not numbered:
            in_list = False
        for clause in re.split(r"[。；;！？!?]", body):
            evidence.extend(_clause_evidence(clause, source, default))
    return evidence
