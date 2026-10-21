# Windows Version validation closeout

Current grouping limitations and the three-report Demo investigation are recorded
separately in [the version diagnosis](version-demo-diagnosis.md). Fixed-input order
determinism does not guarantee cross-Workspace partitions, and a candidate is only
a recommendation within its group. The historical parser scope below belongs to
its evidence baseline; current extraction support is described in
[Document evidence](document-classification-evidence.md#text-evidence-and-omissions).

## Status and evidence provenance

**Fixed-commit Windows Version unit/lifecycle and four-format C public-tool
pipeline evidence verified; Agent/UI end-to-end acceptance remains pending.** The supplied
`version-win-results.zip` was reconciled on 2026-10-18. Logs and JUnit agree:

| Verified run | Passed | Skipped | Failed / errors |
| --- | ---: | ---: | ---: |
| Existing Version tests (95 cases) | 93 | 2 | 0 / 0 |
| Normal-exit / closed-pipes supplement | 1 | 0 | 0 / 0 |
| Combined | 94 | 2 | 0 / 0 |

`commit.txt` identifies `490e5f11d2f545d2e0679b5592d9c398126326e3`.
Environment: Windows 11 build 26100, Python 3.12.10 64-bit AMD64, pytest 9.1.1;
pdfplumber 0.11.10, python-docx 1.2.0, openpyxl 3.1.5, chardet 7.6.0.
Both recorded pytest exit codes are zero. XML timestamps place the two runs on
2026-10-17 (UTC+08:00). No withdrawn screenshot was used.

The two skips are `test_real_trailing_newline_filename_via_parser[v2]` and its
`最终版` case: `Filesystem does not support this filename: OSError`.
Cross-platform suffix-rule cases ran successfully. XML and logs also verify
`test_public_parser_input_and_source_preserved`,
`test_timeout_reaps_actual_process`,
`test_real_repetitive_comparison_budget_ends_worker`, and the normal-exit
supplement. These tests assert actual process state; the sleeping-child test and
normal-exit supplement additionally assert all three pipes closed.

Supplemental source was inspected. Compared with the prepared source, it omits
a module docstring and splits the three pipe assertions into separate statements;
the checked conditions are equivalent. The raw source SHA-256 matches the
archive's `supplement-sha256.txt`:
`3c7bced2a380c6ab399e88e1cb49bea58f5e6e825abf29a3b7957464469335b3`.
Archive SHA-256:
`c1d971fe1a03509cb9fcbf4d80f3c0958a4472d80ed81844196f2311912bf349`.

Evidence limitations: no post-run commit record or pre/post Git status files were
included. Commit, environment, dependencies, logs, XML, exit codes and supplemental
source were checked, but the archive is not a complete source/working-tree
snapshot and cannot independently prove absence of every local change. No full
Windows repository suite or Agent/UI integration is established by these runs.
Raw ZIP, personal paths, hostnames, full logs and install locations stay outside
the repository; only this compact reconciliation is recorded here.

## Version applicability

C safely fast-forwarded from the evidence target to dev
`9199585550920c86ce1521d2114ae9452b822b99`, with a clean initial worktree and no
conflicts. Comparison against the fixed target found **no changes** in
`src/fileforge/document/`, existing Version/parser/extractor tests or
`pyproject.toml`. The new normal-exit test is test-only and comes from the earlier
prepared supplement. The executed supplemental source was subsequently checked
as described above; the four-format pipeline supplement is separate new work.

The verified evidence applies to the unchanged C Version implementation within
the tested unit/lifecycle and supplemental C-tool pipeline scopes. It does not validate subsequent Agent/frontend/task-intelligence
integration. Latest dev also clarified strict shared JSON/snapshot requirements;
unchanged C code and old Windows results alone do not establish compliance with
every newly specified boundary (for example custom JSON subclasses). This round
neither changes those contracts nor claims all consumers have adapted.

PR #13 is merged, at the fixed target above. Its former pending-review/merge
status is historical, not a current blocker. The separate four-format C-tool
pipeline run below closes that scoped test gap. A/B integration, D/consumer
adaptation and complete Real Mode delivery remain separate, unclosed milestones.

## Lifecycle coverage

Existing `tests/test_document_versions.py` covers public calls, deterministic
bucket/group/recommendation/diff rules, resource boundaries, input failures and
immutability. In particular:

- `test_timeout_reaps_actual_process`: real sleeping child, public timeout
  failure, `poll()` proving termination and all three pipes closed.
- `test_real_repetitive_comparison_budget_ends_worker`: actual expensive
  comparison, timeout and actual child termination, not just an error string.
- `test_success_worker_exits_and_closes_all_pipes`: prepared supplement now added
  to the existing test file; checks successful public result, returncode/poll
  equal to zero, and stdin/stdout/stderr closed.

Mock cleanup-error tests verify failure envelopes only; they are not evidence
of actual OS process termination. Newline-suffix core tests do not require real
special filenames and remain cross-platform. Tests operate on synthetic snapshots
and pytest temporary files, never user material or Demo files.

## Joint-chain coverage audit

The verified **94 passed, 2 skipped** (93 Version plus 1 lifecycle) does not
establish four-format end-to-end C-tool coverage. The source audit was reconciled
with the archive's actual test-node inventory; separate Parser success is not
joint-chain evidence.

| Real input format | Fixed-commit read_document -> compare_versions coverage | Gap in that Windows run |
| --- | --- | --- |
| TXT | `test_public_parser_input_and_source_preserved` reads real files, recommends qualifying v2, checks bytes/mtime | Real-file non-grouping and both abstention cases are not covered by that test |
| PDF | Parser tests use real PDF; Version tests use supplied in-memory snapshots | No real PDF-to-Version joint chain |
| DOCX | Parser tests use real DOCX; Version tests use supplied in-memory snapshots | No real DOCX-to-Version joint chain |
| XLSX | Parser tests use real XLSX; Version tests use supplied in-memory snapshots | No real XLSX-to-Version joint chain |

Parser and Version passing separately must not be recorded as combined pipeline
acceptance. Reuse the verified real TXT positive/source-preservation case and existing
Version/lifecycle/resource evidence. Do not rerun unrelated suites solely to
generate another total.

Minimal prepared supplement: `tests/test_document_version_pipeline.py`, 16 cases:
each of TXT/PDF/DOCX/XLSX uses real temporary files through both public tools,
covering qualifying grouping/recommendation, content below the grouping threshold,
identical-content abstention and missing-explicit-version abstention. All preserve
complete returned Documents, repeat-read IDs, original bytes and nanosecond mtime.
PDF fixtures have two text-layer pages; XLSX fixtures have two named sheets;
DOCX fixtures use body paragraphs. No OCR, tables or spreadsheet calculation is
implied. All fixture writes/time setup are confined to pytest temporary paths.

### Verified Windows four-format supplement

The separately supplied retry archive was checked against commit-before and
commit-after records, environment, dependencies, log, JUnit, exit code, source
and SHA-256 record. Both commit records identify
`490e5f11d2f545d2e0679b5592d9c398126326e3`. Windows 11 build 26100 /
Python 3.12.10 64-bit; JUnit records **16 passed, 0 failed, 0 errors,
0 skipped**, matching the log (`16 passed in 15.73s`) and exit code zero.
This run is separate from **93 passed, 2 skipped** and the **1 passed** lifecycle
supplement; it does not rerun or replace those records.

All four formats passed each of qualifying grouping/recommendation, unrelated
single-file groups, identical-content abstention and insufficient-version-evidence
abstention, with source bytes/mtime preserved. These are real temporary-file
`read_document -> compare_versions` calls, not separate Parser/Version totals.
The original coverage-audit gaps above are now closed by this scoped supplement.

The executed source and the prepared repository test have identical Python ASTs;
only UTF-8 BOM / CRLF versus UTF-8 / LF differs. Keep the repository source without
copying platform formatting. Executed source SHA-256 (matching the supplied record):
`bc4205a6b677e99ab95157b0387b14c2cc39a19c6e7fb7e4a1a9ad62e5fa2763`.
Retry archive SHA-256:
`417b2287f45d75a309211f22885573bb4e8599849ba083dd7ef638250d5a9ef0`.

The owner reports that the first attempt failed collection because PowerShell
text was pasted into the test file; after correcting the test source the retry
passed. The initial failed log/source is not in this archive, so that cause is
recorded as owner-reported, not independently reproduced. Before/after Git status
is identical: only the supplemental test and an error backup are untracked; no
tracked runtime modification is shown. No business implementation was changed
for this closeout. Neither the backup nor original logs/ZIP are copied into Git.
The archive is evidence of these runs, not a complete source-tree snapshot.

## Minimal Agent joint verification (A-owned)

1. Use a temporary unknown Workspace; keep both public C tools in the real
   default router. Candidate collection must supply only successfully read
   `data.document` values, with the existing path/identity and count boundaries.
2. Reuse A's existing `test_default_router_compares_read_documents_without_a_custom_resolver`
   and `test_runtime_candidates_are_read_and_compared` as integration anchors;
   use the new four-format C tests as a separate lower-level gate. Neither is
   automatically evidence of the other or of the HTTP/UI path.
3. Verify grouping and normal abstention survive TaskSnapshot/FinalReport;
   empty successful collection stays distinct from not-run or failed reads.
   Reuse A's existing failure/empty-collection tests rather than invent a resolver.
4. Verify read failure/invalid snapshots stop analysis and subsequent mutations;
   any create/copy plan still requires approval. A/B Real Mode and final-report
   acceptance remain with their owners; no new pass is recorded in this round.

## Parsing evidence available to D/A

| Source | Available evidence | Boundary |
| --- | --- | --- |
| Filename / extension | Original resolved filename, lowercase extension | File type or name clue only, not proven subject, purpose or task compliance |
| TXT | Full decoded text with existing encoding detection/replacement | Decoding may replace invalid bytes; no promise of perfect original encoding |
| PDF | Extracted text layers across pages | No OCR; empty text alone cannot prove a scanned document; layout is not guaranteed |
| DOCX | Body paragraphs | Tables, headers, footers, images and other Office content omitted |
| XLSX | Cached cell values with sheet-name headers | Cache may be absent/stale; no formula evaluation, coordinates or styles; no XLSM |
| Document metadata | `file_id`, resolved `path`, `filename`, `extension`, byte `size`, UTC `modified_time`; `metadata` currently `{}` | No author/topic/classification confidence promised; size/time are not semantic purpose or finality |

Use Document.file_id verbatim; upstream FileRecord's database `id` or category is
not a substitute. Unsupported/image/empty/unreadable inputs do not yield invented
Document text. How a future classifier retains those scanned candidates as
unknown/unprocessed must be agreed by D/A without changing the existing public
read-failure semantics or adding private fields. Keep the current 10-supported-
Document collection limit visible; batching and classification contracts remain
separate pending work. No `classify_files` implementation or schema is added here.

## Local verification

Linux / Python 3.12.14, current dev above: combined Version, parser/extractor,
Windows-parser and four-format pipeline regression **181 passed, 4 skipped**.
The four skips require real Windows path semantics. Command:
`python -m pytest tests/test_document_versions.py tests/test_document_parser.py tests/test_extractor.py tests/test_document_windows_validation.py tests/test_document_version_pipeline.py -q -ra`.
Black/Ruff for the two supplemental test files and `git diff --check` passed.
Linux results do not constitute a second Windows run. No full-repository suite,
A/B/D integration or end-to-end acceptance is claimed. No business implementation,
Version contract, classifier or runtime dependency is changed here.
