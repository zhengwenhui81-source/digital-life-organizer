"""DOCX body paragraphs and table grids using python-docx (no layout/OCR)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph


@dataclass
class _Anchor:
    row: int
    column: int
    width: int
    text: str
    vertical: bool = False
    height: int = 1


def _blocks(element, parent):
    """Visit direct body/cell blocks only, preserving their XML order."""
    for child in element:
        if child.tag == qn("w:p"):
            text = Paragraph(child, parent).text.strip()
            if text:
                yield text
        elif child.tag == qn("w:tbl"):
            text = _table(Table(child, parent))
            if text:
                yield text


def _table(table: Table) -> str | None:
    """Render each grid slot; merged continuations reference one text anchor.

    python-docx row.cells repeats merged origins, so inspect physical w:tc cells
    and their gridSpan/vMerge instead. Skipped grid positions are not empty cells.
    A nested table is rendered within its cell's JSON-escaped text, never as an
    unrelated outer row. Unsupported/inconsistent merge geometry fails explicitly.
    """
    width = len(table._tbl.tblGrid.gridCol_lst)
    rows: list[list[_Anchor | None]] = []
    has_text = False
    for row_index, tr in enumerate(table._tbl.tr_lst):
        row: list[_Anchor | None] = [None] * width
        before = tr.find("w:trPr/w:gridBefore", tr.nsmap)
        column = int(before.get(qn("w:val"))) if before is not None else 0
        after = tr.find("w:trPr/w:gridAfter", tr.nsmap)
        skipped_after = int(after.get(qn("w:val"))) if after is not None else 0
        if column < 0 or skipped_after < 0:
            raise ValueError("Invalid DOCX table omitted-cell geometry")
        for tc in tr.tc_lst:
            if tc.find("w:tcPr/w:hMerge", tc.nsmap) is not None:
                raise ValueError("Legacy DOCX hMerge is unsupported; use gridSpan")
            span = tc.grid_span
            if span < 1 or column + span > width:
                raise ValueError("Invalid DOCX table column span")
            cell_text = "\n".join(_blocks(tc, _Cell(tc, table)))
            if tc.vMerge == "continue":
                origin = rows[-1][column] if rows else None
                if (
                    origin is None
                    or not origin.vertical
                    or origin.column != column
                    or origin.width != span
                    or origin.row + origin.height != row_index
                    or any(
                        rows[-1][c] is not origin for c in range(column, column + span)
                    )
                    or cell_text
                ):
                    raise ValueError("Invalid DOCX table vertical merge continuation")
                origin.height += 1
            else:
                origin = _Anchor(
                    row_index, column, span, cell_text, vertical=tc.vMerge == "restart"
                )
                has_text = has_text or bool(cell_text)
            row[column : column + span] = [origin] * span
            column += span
        if column + skipped_after != width:
            raise ValueError("Invalid DOCX table row grid width")
        rows.append(row)
    # Structural markers alone must not make a blank document look readable.
    if not has_text:
        return None
    lines = ["[TABLE]"]
    for row_index, row in enumerate(rows):
        cells = []
        for column, origin in enumerate(row):
            label = f"C{column + 1}"
            if origin is None:
                value = "[omitted]"
            elif (origin.row, origin.column) != (row_index, column):
                value = f"@R{origin.row + 1}C{origin.column + 1}"
            else:
                if origin.height > 1 or origin.width > 1:
                    label += f"(rowspan={origin.height},colspan={origin.width})"
                value = json.dumps(origin.text, ensure_ascii=False)
            cells.append(f"{label}={value}")
        lines.append(f"R{row_index + 1}: " + " | ".join(cells))
    lines.append("[/TABLE]")
    return "\n".join(lines)


def extract(path: Path, max_chars: int = 2000) -> str | None:
    """Extract ordered body paragraphs/tables; public reader requests full text.

    Header/footer/textbox/image content and Word pagination/layout are excluded.
    Paragraph edge whitespace is stripped as before; internal spaces remain.
    Table cell values use JSON string escaping so embedded delimiters/newlines
    cannot silently shift columns. The existing upstream snippet limit remains.
    """
    document = Document(str(path))
    content = "\n".join(_blocks(document.element.body, document))
    return content[:max_chars] if content.strip() else None
