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

## Verified Windows evidence (2026-10-18)

User-supplied real Windows 11 build 26100 / Python 3.12.10 64-bit evidence applies
to `0fcc1df7696090ba74136848df57f97495584b04` (the reviewed PR #28 HEAD).
PR #28 was subsequently merged by the team as
`53f6dd840df2408024d4f6248fb511751416138b`; this evidence update did not merge it.
The closeout branch safely fast-forwarded to dev
`4d43cbd897e95dc91234e8e515f0bf7478699d07`. Comparison from the evidence HEAD found no
changes in `src/fileforge/document/`, `src/fileforge/extractor/`, the DOCX/parser
tests or `pyproject.toml`. The fixed-HEAD evidence therefore still applies to the
unchanged tested C behavior, not subsequent Agent/UI/matching integration. This
document-only update changes no implementation; future runtime changes require
reassessing scope.

| Separate Windows run | Passed | Failed / errors | Skipped | Exit |
| --- | ---: | ---: | ---: | ---: |
| Existing synthetic DOCX suite | 17 | 0 / 0 | 0 | 0 |
| Read-only original-document supplement | 1 | 0 / 0 | 0 | 0 |

Logs and JUnit agree. Before/after commits match the fixed HEAD; before/after
Git status and tracked-diff records are empty. Environment records fixed-source
import, pytest 9.1.1, python-docx 1.2.0, pdfplumber 0.11.10, openpyxl 3.1.5 and
chardet 7.6.0. The supplied supplement matches the final chat-provided validation
logic; its hash matches its recorded SHA-256. It retains exact original-file hash,
215-slot merged-anchor mapping, complete body/table-order equality, 10,162 text
characters, byte/mtime/size/path preservation, normalized-path ID/repeat-read
checks and standard Version over-limit failure (`success=false`, `data=null`).
The 17-test inventory includes synthetic immediate rename/back for handle release;
the original user file was never renamed or modified.

Supplement source SHA-256:
`3a54baa366cc19f0a18e5d7a6cc6cf6604a3c632ba70b1b2eaf22b4a609f83a5`.
Evidence archive SHA-256:
`84339d207119d8d9e338133ccfa32a223205dcf2ccd9c3d0e35ceaa323376b6b`.
Only these compact results are recorded. Raw archive/log/XML/bytecode, machine
paths/hostname and the original DOCX/full extracted text are not committed.
The package is run evidence, not a complete independent source-tree snapshot.
These are user Windows executions reconciled by C, not Windows runs on this
Linux host. No unrelated tests were rerun for this documentation update.

Reading completeness within the declared scope is not scoring understanding.
The original document still fails Version's unchanged 10,000-character limit
as described above. Older Windows evidence remains historical; this separate
fixed-HEAD evidence covers the DOCX increment's tested scope. Real Agent/UI/LLM
end-to-end acceptance and all-consumer adaptation remain separate work; no whole
C1/C2/C3 completion is asserted.

## Change separation

PR #28 excluded the then-uncommitted C/A integration/classification documents.
This separate documentation closeout now gathers those records, the minimal A
reproduction and verified DOCX Windows evidence. No A/B/D business code, original
attachments, raw logs/XML/bytecode or personal-machine information is included.
