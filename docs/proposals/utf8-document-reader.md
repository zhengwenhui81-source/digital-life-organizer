# UTF-8 source / JSON / CSV Document reader proposal

Status: **proposal, not frozen, not public implementation**. Baseline:
`f084b8a18198f61634c82e5bc12ee9bffc44f0f0` (Linux / Python 3.12.14 audit).
The active [extraction scope](../../API_CONTRACT.md#read_document-extraction-scope)
remains TXT, PDF, DOCX and XLSX. No existing format behavior changes in this PR.

## Audited boundaries

| Layer | Current behavior |
| --- | --- |
| `fileforge.document.read_document(path)` | Exactly four supported extensions, case insensitive; normalized path identity and full Document; no parser-wide raw-byte hard cap |
| Upstream snippet extractor | Some code extensions and JSON use detected/replacement decoding and a snippet limit; CSV is absent; this is not a successful Document read |
| Agent candidate collection | A owns a four-extension auto-read whitelist and candidate-reading limit; adding a C extractor alone does not change real Agent selection |
| Matching Phase 1 | Already accepts complete valid Documents with other extensions; preserves source references; filename relationships only |
| Workspace / source authority | A authenticates the task, scan/read provenance, Workspace boundary and current evidence; a parser or caller-supplied Workspace does not grant authority |

## Proposed exact extension and decoding rules

1. Add only `.cpp`, `.h`, `.hpp`, `.json`, `.csv`, ignoring extension case.
   Other source suffixes, Markdown, Python, images and XLSM remain outside this
   increment; no MIME sniffing or automatic fallback to arbitrary binary files.
2. For these new suffixes only, decode strict UTF-8, accepting and removing one
   leading UTF-8 BOM. Reject malformed/truncated UTF-8, UTF-16/32 and legacy
   encodings rather than replacing bytes or guessing. Reject embedded NUL.
   Valid Unicode U+FFFD explicitly encoded by the author remains valid text.
3. Preserve decoded characters, whitespace, CRLF/LF and CSV quote/record order.
   Empty or whitespace-only content fails. No 2,000-character snippet or silent
   truncation. TXT retains its current detected/replacement decoding.
4. Treat source, JSON and CSV as **literal text evidence**. Never compile/execute
   source, run scripts, resolve includes, follow JSON references, evaluate CSV
   formula-like cells, fetch URLs, or perform schema/AST/semantic validation.
   A malformed JSON/CSV text file may still be readable text; reading does not
   certify syntax, table dimensions, data types, correctness or material purpose.

## Proposed resource rule (requires team acceptance)

For each new-format file, raw bytes including BOM must be at most **1 MiB =
1,048,576 bytes**. Equality is allowed. Reject a larger stat size before reading;
also bound actual reads to at most the limit plus one byte to detect growth.
On growth, inconsistent observations, permission/decoding/read errors or an
oversized file, return standard failure, `data=null`; no partial Document.

This is a new reader-specific proposal, not an inherited Version allowance.
It bounds retained source bytes, not whole-process memory, OS read latency or
aggregate task cost. It does not retrospectively cap TXT/PDF/DOCX/XLSX, and does
not promise safe extraction of arbitrarily large existing formats. A's candidate
read count remains separate. Version's 10,000 characters/file, total text,
complete JSON budget and worker deadline remain unchanged: a successful new
Document can legitimately fail a later Version call. Matching gains no quota.

## Model, identity, errors and path safety

Keep public input `{path: string}`, the existing complete Document fields,
`metadata={}`, path-based ID formula and `read_document` ToolResult unchanged.
No new format, encoding, hash, scan_ref or provenance field is introduced.
File size is raw byte size; text length may differ. Successful reading is evidence
of extracted text at a path, not proof of immutable historical source bytes.

The existing resolved-path identity rule is unchanged, including symlink target
identity. A must reject unauthorized Workspace paths and unsafe link/reparse
traversal at its existing caller boundary. An isolated candidate may require an
explicit test Workspace and reject link traversal; that parameter is not a new
public input or Task authorization mechanism. No global existing-reader symlink
policy changes in this increment. Check regular-file identity, size and mtime
before/after extraction; retain same-channel ctime checks and Windows cross-API
ctime handling without importing D's private path helpers. Fail observable
source changes; do not claim to eliminate every TOCTOU race or an ABA change.

## Requirements / Matching handoff

After approval and implementation, only complete successful new-format Documents
may enter D's public `match_requirements(required_documents, candidate_documents)`.
Current Phase 1 already validates filename/extension consistency for arbitrary
extensions and returns original `file_id/path/filename` without choosing a version.
Pass the full Document, not a snippet or scan metadata masquerading as a read.
Failure is not an empty candidate set; A must retain it and stop as contracted.
Successful association does not validate source compilation, JSON syntax, CSV
values or whether a material meets the request. Requirements extraction and
semantic association remain D's capabilities; no algorithm change is implied.

## Delivery and acceptance gates

- This contract PR changes no production code, public registration or Agent list.
  Any isolated private prototype/tests are separately reviewed and not exported.
- A/B/C/D confirm the five extensions, BOM/strict decoding, literal-text semantics
  and exact byte cap before public activation. No public data-structure change is
  proposed. Acceptance must update the active extraction-scope table explicitly.
- C then integrates through the existing Document assembly/error/ID boundary and
  runs current parser/extractor/DOCX/Version regressions; no redundant parser stack.
- A separately updates its owned auto-read/Planner selection and checks source
  authority, read-count behavior and downstream resource failures.
- B on fixed Windows 11 / Python 3.12 HEAD checks Chinese paths/text, UTF-8 BOM,
  strict invalid-byte failure, exact/over raw limit and unchanged originals. Record
  link/reparse permission skips. cp936 success is not cp1252 verification.
- B verifies real scan -> read -> Matching -> Snapshot/Report and failure stops;
  candidates and Version recommendations never become automatic selection or
  file writes. No paid API call is needed for C's automated tests.
