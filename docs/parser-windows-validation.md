# Windows parser validation record

## Version and provenance

User-supplied evidence, dated 2026-10-16 (UTC+08:00), verifies commit
`a6ee13a53100f0b2522f4e9ad07e0e0296bd59d4` (PR #5 merge).
The initial C branch HEAD matched that exact commit. Before committing this
record, C safely fast-forwarded to latest dev
`be68be2cc9c8f4ebc756784893bafdda6c0b6c21` without conflicts or stashing.
Compared with the validated commit, `src/fileforge/document/`,
`src/fileforge/extractor/`, existing parser/extractor tests and `pyproject.toml`
are unchanged. New upstream changes affect Agent/frontend code, so the Windows
evidence remains applicable to this parser implementation; it is not a new
Windows run of the entire updated repository. Future relevant changes require
checking applicability and rerunning affected tests.

Environment: Windows 11 (build 26100), Python 3.12.10 64-bit AMD64,
pytest 9.1.1; pdfplumber 0.11.10, python-docx 1.2.0, openpyxl 3.1.5,
chardet 7.6.0. This is a user-run Windows validation, not a Windows run in the
Linux development environment.

The submitted ZIP contains a nested results ZIP. Both logs and JUnit XML were
checked, together with `commit.txt`, `environment.txt`, `dependencies.txt` and
the supplemental test source. The editable dependency entry identifies the same
repository and commit. The archive does not contain a complete working-tree
snapshot or status, so it cannot independently prove absence of all local edits.

Outer attachment SHA-256:
`da30af92e9d4d2dee80c69652aec67b410e4f8b6cbddcb6bbf47e10c1fb29104`.
Supplemental source SHA-256 (identical to the repository copy):
`c7974ad2b78dc0df4372f3c1cc2a7720126feaf48fc7379c2d3b5636d239b544`.
The pre-existing local supplemental test differed only in two docstrings and
one comment; executable logic was compared before adopting the supplied source.
Raw evidence remains outside the repository: personal paths, hostnames, full
logs, XML and temporary dependency-install paths are intentionally excluded.

## Actual Windows results

| Run | Passed | Failed / errors | Skipped |
| --- | ---: | ---: | ---: |
| `tests/test_document_parser.py` + `tests/test_extractor.py` | 59 | 0 / 0 | 3 |
| `tests/test_document_windows_validation.py` | 11 | 0 / 0 | 0 |

Combined Windows result: **70 passed, 3 skipped, 0 failures/errors**.

The three original-suite skips were:

- `test_relative_absolute_and_symlink_paths_agree`: symbolic links unavailable.
- `test_broken_symlink_returns_failure`: symbolic links unavailable.
- `test_linux_does_not_lowercase_paths`: Linux-only path semantics.

The original suite covers PDF multiple pages, DOCX body paragraphs, XLSX named
worksheets, full-text tails, decoding and failure envelopes. Supplemental checks
cover TXT/PDF/DOCX/XLSX in Chinese/space paths with uppercase extensions, text
beyond 2000 characters, repeated-read identity, source bytes and nanosecond mtime,
immediate rename and restore after repeated reads, and four Windows case-alias
identity cases. Corrupt PDF/DOCX/XLSX files return standard failures and permit
immediate rename/restore. All mutations are limited to pytest temporary files.

## Scope and remaining gaps

This verifies the declared parser scope, not all Office content or all Windows
configurations. Windows symbolic-link behavior remains unverified; no security
setting changes are required to suppress skips. The Linux-only skip is expected.
No OCR, DOCX tables/headers/footers, formula calculation or XLSM support is added.
The authoritative limits remain in
[API_CONTRACT.md](../API_CONTRACT.md#read_document-extraction-scope).
This record does not claim complete C1 acceptance, Agent integration, Version
Intelligence implementation, or a full Windows repository test run.

## Linux regression after evidence integration

Linux / Python 3.12.14 regression after integration: **69 passed, 4 skipped**.
All four skips require real Windows case-alias semantics.
Command: `python -m pytest tests/test_document_parser.py tests/test_extractor.py tests/test_document_windows_validation.py -q -ra`.
Black `--check` and Ruff on the supplemental test passed; `git diff --check` and
local Markdown link/whitespace checks passed. No full repository suite was run
in this documentation/test-only round; historical failure counts are not being
reasserted as current results.
