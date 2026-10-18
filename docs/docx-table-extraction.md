# DOCX body/table extraction increment

## Scope and representation

This approved parser increment extends the existing python-docx extractor; it
adds no dependency, second reader, Document fields, IDs or scoring logic. Baseline:
`43a723ab0fef9396fa5f0c278b3b28107093df36` (latest dev before implementation).
The existing public `read_document(path)` still requests full supported text.
See [the authoritative scope](../API_CONTRACT.md#read_document-extraction-scope).

Direct body paragraphs and tables appear in XML order. Each table has `[TABLE]`
and `[/TABLE]` boundaries. Rows/columns use 1-based local coordinates, for example:

```text
[TABLE]
R1: C1(rowspan=2,colspan=1)="Example activity" | C2="Gold" | C3="7"
R2: C1=@R1C1 | C2="Silver" | C3="4"
[/TABLE]
```

Synthetic example only; no scoring interpretation is implemented. A combined
horizontal/vertical anchor also carries both spans. Its text appears once;
covered grid slots refer to the origin rather than repeating the category or
shifting scores. Empty cells are `""`; omitted grid positions are `[omitted]`.
JSON-escaped cell strings preserve internal spaces and delimiters/newlines.
Paragraph edge whitespace and empty paragraphs are stripped as before.

Nested tables are rendered inside their containing cell's escaped string, with
explicit boundaries and their own local coordinates; they never become outer
rows. Malformed spans/continuations, content-bearing vertical continuations and
legacy `w:hMerge` return standard parse failures rather than guessed relations.
Standard Word `gridSpan` and `vMerge` merges are supported. Whitespace-only tables
add no fake readable content. Pure tables with text now succeed.

Headers/footers, textboxes, images/OCR, revision/content-control wrappers and
pagination/style/layout reconstruction remain outside scope. This reads text
structure, not categories/levels/points as a semantic model, and does not calculate
scores. TXT/PDF/XLSX behavior is unchanged.

## Read-only real-document audit

The supplied policy was inspected locally without committing it or its full text.
Before: reading succeeded with 6,875 body characters, but none of the six table
structures appeared. After: 10,162 characters, with all six tables in body order.
Each rendered grid slot was independently compared with python-docx's expanded
source grid, following origin references. Text/score association was checked by
row and column, not just by keyword presence.

| Uploaded table (source order) | Grid | Checked slots | Distinct anchors | Merged anchors | Result |
| --- | --- | ---: | ---: | ---: | --- |
| 1 | 9 × 4 | 36 | 36 | 0 | All source grid values match |
| 2 | 7 × 5 | 35 | 19 | 6 | All source grid values match |
| 3 | 4 × 3 | 12 | 12 | 0 | All source grid values match |
| 4 | 10 × 4 | 40 | 27 | 5 | All source grid values match |
| 5 | 9 × 4 | 36 | 25 | 5 | All source grid values match |
| 6 | 14 × 4 | 56 | 35 | 5 | All source grid values match |

Total: 215 grid positions. Original bytes, nanosecond mtime and path-based file_id
were unchanged. The six tables' individual category/level/score observations were
reported to the owner separately; source text and private full audit stay outside
Git. Repository tests use synthetic data only.

## Resource and evidence boundaries

No Version quota was changed. The real document now exceeds the 10,000-character
single-text limit: read_document succeeds with full 10,162 characters, then
compare_versions returns `success=false`, `data=null`, error identifying actual
length 10,162 and limit 10,000. Structural markers/escaping also count as text;
no silent truncation, auto-batching or in-process comparison fallback is introduced.
The total-text, full `{"documents":[...]}` UTF-8 size and worker budgets remain
as specified in [the Version contract](../API_CONTRACT.md#compare_versions).

## Validation

Linux / Python 3.12.14: new DOCX tests **17 passed**. They cover paragraph/table
interleaving, table-only files, horizontal/vertical/combined merges and exact
category-level-score positions, cell spaces/empty/escaped delimiters, nested
boundaries, omitted slots, invalid/legacy merges, long tail beyond 2,000 characters,
repeat-read identity, bytes/mtime preservation, immediate rename-back, empty-table
failures and unchanged Version resource rejection. Initial baseline reproduction
confirmed paragraph-only/table omission before implementation.

Final targeted command (from an installed project/dev environment):

```bash
python -m pytest tests/test_document_docx_tables.py tests/test_document_parser.py tests/test_extractor.py tests/test_document_windows_validation.py tests/test_document_versions.py tests/test_document_version_pipeline.py tests/test_agent_document_integration.py tests/test_agent_report_search.py tests/test_agent_approved_verification.py tests/test_agent_search_recovery.py -q -ra
```

Final combined Linux regression: **230 passed, 4 skipped**; the four skips require
real Windows path semantics. Black/Ruff for changed Python files and diff/document
checks passed. No full-repository run or new full-suite baseline comparison is
claimed. No failure in this targeted run is dismissed as an old baseline failure.

**New DOCX table behavior is unverified on Windows.** Previous Windows parser /
Version / four-format evidence covers the old body-only implementation, not this
increment. Windows merge/nesting/source-preservation/handle-release checks and
real Agent/UI/LLM end-to-end acceptance remain separate work. No whole C1/C2/C3
completion or A/B/D adaptation completion is asserted.

## Change separation

Pre-existing C/A integration/classification documents and their TASKS Chapter 10
edits remain uncommitted. This PR includes only the DOCX implementation, synthetic
tests and related support/validation documentation; its TASKS C1 hunk is staged
separately from those preserved edits. No A/B/D source or tests are modified.
