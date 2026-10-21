"""Conservative, reusable material evidence parsing; no public schema."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fileforge.task_intelligence._context import (
    _join_continuations,
    _unconditional_sentences,
)


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
    r"^(?:\d+[.、．)]|[（(](?:\d+|[一二三四五六七八九十]+)[)）]|[-*])\s*(.+)$"
)
_HEADING = re.compile(
    r"^(?:#{1,6}\s*)?(?:[一二三四五六七八九十]+、)?"
    r"(?:正式)?(?:提交材料|所需材料|必交材料)(?:清单|要求)?"
    r"(?:\s*[:：]\s*(.*))?$"
)
# Typed item identifiers are recognized only inside an explicit material list.
_CODE_NUMBER = re.compile(
    r"^[A-Za-z]{1,12}[-_]?[0-9]+(?:[.-][0-9]+)*[.)、．]?[ \t]+(.+)$"
)
_LABELED = re.compile(r"(?P<name>[^：:]+)[：:]\s*(?P<assertion>.+)$")
_LABEL_ASSERTION = re.compile(
    r"^(?:请)?(?P<mode>必须提交|须提交|需提交|需要提交|无需提交|不必提交|不需要提交|提交)"
    r"[：:\s]*(?P<items>.+)$"
)

# Restrictive qualifiers on a labeled description must not disappear when
# extracting its short material name. No condition reasoning is attempted.
_LABEL_RESTRICTION = re.compile(
    r"仅|限于|专用|专供|适用于|[（(][^）)]*(?:条件|者)[^）)]*[）)]"
)

# Bare Chinese numbering is ambiguous with chapter numbering: terminate scope.
# Parenthesized Chinese/Arabic and plain Arabic lists remain supported.
_SECTION = re.compile(
    r"^(?:#{1,6}\s+|[一二三四五六七八九十]+[、．.]|第[一二三四五六七八九十0-9]+[章节])"
)
# Title-shaped administrative sections remain boundaries after list numbering
# is removed, even with inline descriptions. A colon alone inside a material
# item is not sufficient; unfamiliar/ambiguous prose is not semantically parsed.
_EXPLICIT_SECTION_TITLE = re.compile(
    r"^[^：:\n]{1,32}(?:安排|标准|流程|事项|方式|细则|须知|规则)" r"\s*[:：].*$"
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
    # An explicit list label supplies the material name; the right-hand side
    # must independently require submission. Check restrictions on BOTH sides
    # before a label or comma-separated item can lose its qualifier.
    # Descriptions/criteria alone cannot
    # become requirements. Keep conditions/alternatives attached to the clause.
    label = (
        _LABELED.fullmatch(clause.strip())
        if default is not None and not _ASSERTION.fullmatch(clause.strip())
        else None
    )
    if label:
        assertion = _LABEL_ASSERTION.fullmatch(label["assertion"].strip())
        if (
            assertion
            and not _MODIFIER.search(assertion["items"])
            and not _LABEL_RESTRICTION.search(clause)
        ):
            required = (
                assertion["mode"] in _REQUIRED_MODES or assertion["mode"] == "提交"
            )
            return _items(label["name"], source, required)
        return []
    evidence = []
    statements = re.split(
        r"[，,]\s*(?=(?:请)?(?:必须提交|须提交|需提交|需要提交|无需提交|不必提交|不需要提交))",
        clause,
    )
    # Unknown prose before an explicit assertion may be its qualifier. Do not
    # discard that prefix merely because a later comma exposes a known verb.
    if len(statements) > 1 and not _ASSERTION.fullmatch(statements[0].strip()):
        return []
    for statement in statements:
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
    for raw_line in _join_continuations(text).splitlines():
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
                for clause in _unconditional_sentences(heading[1]):
                    evidence.extend(_clause_evidence(clause, source, True))
            continue
        numbered = _NUMBER.fullmatch(line) or (
            _CODE_NUMBER.fullmatch(line) if in_list else None
        )
        body = numbered[1] if numbered else line
        if (
            _SECTION.match(line)
            or _EXPLICIT_SECTION_TITLE.fullmatch(body)
            or body.endswith(("：", ":"))
        ):
            in_list = False
            continue
        if in_list and numbered and list_indent is None:
            list_indent = indent
        default = True if in_list and numbered else None
        if not numbered:
            in_list = False
        for clause in _unconditional_sentences(body):
            evidence.extend(_clause_evidence(clause, source, default))
    return evidence
