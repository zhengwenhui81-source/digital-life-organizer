# Isolated UTF-8 reader proposal validation

Status: **private prototype, not public format activation**. The proposed
[contract](proposals/utf8-document-reader.md) is PR #59; its extensions and byte
cap require team confirmation. The prototype is not exported by
`fileforge.document`, used by `parser.py`, registered in ToolRouter, or added to
A's auto-read whitelist. The tests explicitly verify that public `read_document`
still rejects the new extensions. No existing A/D production or test file changes.

Baseline: `f084b8a18198f61634c82e5bc12ee9bffc44f0f0`.
Actual environment: Linux / Python 3.12.14, pytest 9.1.1, Black 26.10.1.
Imports were checked against this isolated worktree's `src`; all material samples
are generated under pytest temporary directories. No original Demo file, full
environment log, user path, API key or paid API request is included.

## Current evidence

| Scope | Actual result |
| --- | --- |
| New private UTF-8 proposal tests | 59 passed (included in the 140 below) |
| New proposal + original parser + DOCX tables + extractor | 140 passed, no failures/skips |
| Original Version + public Matching | 258 passed, 3 failed; Matching's 161 cases all passed, Version 97 passed / 3 failed |
| Earlier proposal/parser/DOCX/extractor/four-format pipeline run | 152 passed, 4 failed; all four failures in existing Version pipeline comparisons |
| Corrected seven-node failure retry | 5 passed, 2 failed; both failures explicitly report the unchanged 5-second Version deadline |
| New Python files, Black and Ruff | Passed after formatting/import cleanup |

The broader runs were partly concurrent, including Version workers. Failing
assertions show `compare_versions.success=false`; the first output did not expose
the full error string. The corrected retry exposed `Version comparison timed
out: 5-second budget exceeded` for its two failures; the cause of exceeding that
budget and the other initial failures is **not established** and not attributed
to this patch or dismissed as environment noise. No Version budget/timeout,
assertion or production code was changed. Do not turn later reruns into a claim
that the original full suites passed. These results block any blanket regression
or public activation claim; this remains a Draft prototype.

## Reproducible commands

Use a Python 3.12 environment with the existing project development dependencies;
`python` below denotes that interpreter. No new dependencies are required.

```bash
PYTHONPATH="$PWD/src" python -c \
  'import sys,fileforge.document.parser as p; print(sys.version); print(p.__file__)'
PYTHONPATH="$PWD/src" python -m pytest \
  tests/test_document_utf8_proposal.py tests/test_document_parser.py \
  tests/test_document_docx_tables.py tests/test_extractor.py -q -ra
PYTHONPATH="$PWD/src" python -m pytest \
  tests/test_document_versions.py tests/test_task_matching.py -q -ra
PYTHONPATH="$PWD/src" python -m pytest \
  tests/test_document_utf8_proposal.py tests/test_document_parser.py \
  tests/test_document_docx_tables.py tests/test_document_version_pipeline.py \
  tests/test_extractor.py -q -ra
python -m black --check \
  src/fileforge/document/_utf8_proposal.py tests/test_document_utf8_proposal.py
python -m ruff check \
  src/fileforge/document/_utf8_proposal.py tests/test_document_utf8_proposal.py
git diff --check
```

Initial failing nodes:

- `test_document_version_pipeline.py::test_real_formats_read_then_compare[identical-.pdf]`
- `test_document_version_pipeline.py::test_real_formats_read_then_compare[no_version-.txt]`
- `test_document_version_pipeline.py::test_real_formats_read_then_compare[no_version-.pdf]`
- `test_document_version_pipeline.py::test_real_formats_read_then_compare[no_version-.docx]`
- `test_document_versions.py::test_empty_and_unknown_workspace_are_success`
- `test_document_versions.py::test_public_task_neutral_recommendation[\u5956\u5b66\u91d1\u7533\u8bf7]`
- `test_document_versions.py::test_public_task_neutral_recommendation[\u7efc\u6d4b\u8bf4\u660e]`

For exact reruns, prefix nodes with `tests/`, pass them as subprocess argv (pytest
escapes Unicode parameter IDs), and use `-vv --showlocals -ra`. One first retry
used unescaped Chinese IDs and exited 4 without executing tests; it is not a test
failure or passing evidence. The corrected seven-node retry returned **5 passed, 2 failed**. The remaining
failures were `[no_version-.pdf]` and the scholarship recommendation parameter,
both explicitly exceeding the existing 5-second budget. No further reruns were
used to chase a green result.

## What the 59 new tests prove

- Five suffixes, uppercase extensions, ASCII/Chinese, optional BOM and exact raw
  CRLF/quote/multiline content. Full Document shape, ID, raw size and UTC mtime,
  repeat reads and unchanged source bytes/mtime are checked.
- Malformed/truncated UTF-8, common non-UTF-8 fixtures, NUL/empty content, an
  invalid byte after a stream chunk, exact inclusive byte boundaries (including
  BOM and multibyte text), oversized stat rejection before open and bounded
  stream growth rejection. Real and injected read errors return `data=null`.
- Workspace escape/traversal, missing files, directories and actual symlink
  components fail. The reparse probe is **simulated**, not a Windows junction
  test. Descriptor closure is checked on success and failure. Signature tests
  retain each identity field and same-channel ctime; Windows branch probes are
  **simulations**, not actual Windows filesystem evidence.
- Literal source/JSON/CSV never executes or evaluates content. Reading malformed
  JSON/CSV as text is intentional, not syntax approval. No encoding oracle is
  claimed for bytes valid in multiple encodings.
- Five real temporary files yield full Documents that the existing **public**
  Matching tool accepts. It preserves source identity/order and 0/1/N filename
  candidates; contradictory snapshots fail. No D private implementation import.
  This proves structural compatibility of the candidate Documents, not formal
  reader/Agent support or semantic Requirements extraction accuracy.
- A 10,001-character candidate still fails public Version input validation
  **before subprocess creation**. New reader bounds never override Version.

## Remaining release / B acceptance work

1. Confirm the separate contract, then review a production integration using the
   existing C assembly/error/identity boundary. No new Document fields are needed.
2. A updates its owned extension selection, authorization and provenance, keeping
   failed reads blocking and read-count/downstream budgets explicit.
3. B executes fixed-HEAD Windows 11 / Python 3.12 tests: Chinese paths and text,
   BOM/invalid encoding, byte boundaries, stable and observably changing sources,
   source hash/mtime preservation and real link/reparse capability. Preserve
   permission skips; a Linux simulated reparse or Windows branch is insufficient.
4. B separately records cp1252 if claimed (cp936 is not that evidence), and real
   scan -> read -> public Matching -> TaskSnapshot/Report with error propagation.
   Fixture success cannot stand in for DeepSeek, browser, Package or full E2E.

The private prototype's explicit Workspace is only test containment, not a new
public parameter or authorization token. No read-time hash is added to Document,
no immutable historical byte proof is claimed, and no file writes are authorized.
