# C/A controlled-plan integration acceptance

## Fixed baseline and method

Baseline: `5df6777dbe385f7e83167445262c95e698b3e9e1` (dev, including PR #22).
Executed on Linux / Python 3.12.14, 2026-10-18 (Asia/Shanghai).
PR #22 adds verification of approved filesystem operations; it does not replace
C's parser/Version implementation. The subsequent PR #19 merge changes matching
contract/task documentation, not these runtime paths.

Runtime-created temporary unknown Workspaces were processed by `TaskService`,
the default `ToolRouter` and actual scoped resolver. Only a validated controlled
Plan was injected. The new harness neither invokes C functions directly nor
replaces tools/resolver. No fixture-specific business branch was added.
This verifies an in-process Agent orchestration slice, **not real LLM planning,
HTTP/background lifecycle, browser UI or complete end-to-end delivery**.

## Actual commands and results

The acceptance environment already had the project and dev dependencies installed.
The actual interpreter below is an environment-local virtualenv, not a required
installation path. Commands were run from the repository root:

```bash
/workspace/work/parser-validation-venv/bin/python -m pytest /workspace/work/c-agent-acceptance/test_c_agent_acceptance.py -c pyproject.toml -q -ra --junitxml=/workspace/work/c-agent-acceptance/results.xml > /workspace/work/c-agent-acceptance/pytest.log 2>&1
/workspace/work/parser-validation-venv/bin/python -m pytest tests/test_agent_document_integration.py tests/test_agent_approved_verification.py -q -ra --junitxml=/workspace/work/c-agent-acceptance/existing-agent-results.xml > /workspace/work/c-agent-acceptance/existing-agent-pytest.log 2>&1
```

| Run | Result | Time | Evidence boundary |
| --- | --- | --- | --- |
| New controlled-plan acceptance harness | 48 passed, 0 failed/errors/skipped | 22.76 s | Default tools/resolver; real temporary files |
| Existing Agent document integration and PR #22 regression | 25 passed, 0 failed/errors/skipped | 4.71 s | Contains both real default-path tests and explicit fault injection/custom-tool tests; do not describe all 25 as unmodified default-router runs |

Logs/JUnit agree with exit code zero. The original external harness SHA-256 is
`14e2b35d00c3967ba0d0e7b607324e0e8387afc04a1efd6a66b94b104f591616`.
The 48-case harness and raw logs remain external acceptance artifacts, not
repository tests or committed evidence; this record does not claim the full
48-case suite is reproducible from this document alone. The focused A reproduction
below is included and independently runnable.

The 48 cases comprise: 32 = two discovery routes × four formats × grouping,
non-grouping, identical-content and missing-version scenarios; two true-empty
collections; eight real read failures; two real oversized Documents; two invalid
Document argument types; one unresolved-input failure; one approval-gate check.

Observed results:
- TXT/PDF/DOCX/XLSX pass `list_files` or `search_files` → runtime candidate reads
  → `compare_versions` → `TaskSnapshot.results`. Full read Documents are retained
  in groups; qualifying v2 recommendations and old/new changes evidence survive.
- Unrelated content retains single-file groups. Identical content and insufficient
  explicit versions abstain normally. Empty Workspaces succeed with `groups=[]`;
  unresolved inputs fail without inventing an empty comparison result.
- TXT whitespace and damaged PDF/DOCX/XLSX stop before comparison. Successful
  reading of 10,001 text characters then fails Version's 10,000-character limit;
  malformed `documents` type also fails with a standard `data=null` ToolResult.
- TaskSnapshot retains tool failures and propagates their error to task failure;
  no subsequent planned folder operation, preview or successful report appears.
  Resolver failure before tool dispatch has no fabricated ToolResult.
- Successful `FinalReport.version_groups` equals comparison groups. Recommendation
  alone does not authorize a planned folder operation: the task waits for approval.
- Every new case preserves source byte hashes and nanosecond modification times.
  All writes/time setup are confined to temporary fixtures, never user/Demo files.

## Historical report mapping issue and merged-fix recheck

Run using the same fixed checkout and an installed project environment:

```bash
python docs/examples/reproduce_search_report.py
```

The script is supplemental material, not present in the fixed baseline commit;
copy it into that checkout without changing runtime files if reproducing there.
It needs only Python's standard library plus the existing installed project
(and its declared dependencies); no new dependency or credentials are needed.
The script injects only a validated Plan and checks the actual default tools,
comparison, snapshot/report mapping and source preservation. Output omits paths.

Observed on the fixed baseline:

| Route | Discovered | Read | Version groups | FinalReport.found_files |
| --- | ---: | ---: | ---: | ---: |
| list_files | 2 | 2 | 1 | 2 |
| search_files | 2 | 2 | 1 | 0 |

`found_paths_match_discovery` is true for listing and false for searching.
The script exits zero when the observation succeeds; zero does **not** certify
correct report mapping. After an A fix, the search row should retain discovered
paths and the same correct Version groups. It does not assert the old bug must
remain, so it can also be used to check the fix.

Historical ownership: at the fixed baseline
`5df6777dbe385f7e83167445262c95e698b3e9e1`, A's `TaskService._report()` collects
only successful `list_files.data.files`, omitting `search_files.data.matches`.
The zero found-files result above describes that baseline, not the fix branch.

PR #25 HEAD `db7744b4875d8cb333d551b6e4dd84c053ba9883` is merged as
`99525cb4a4810dfbb592a4549c0d4273b93fd82d`, confirmed through GitHub and local
ancestry. C reran the included minimal reproduction at latest dev
`4d43cbd897e95dc91234e8e515f0bf7478699d07` on Linux / Python 3.12.14:

| Route | Discovered | Read | Version groups | FinalReport.found_files | Paths match discovery |
| --- | ---: | ---: | ---: | ---: | --- |
| list_files | 2 | 2 | 1 | 2 | true |
| search_files | 2 | 2 | 1 | 2 | true |

Both tasks completed, source bytes/mtime were unchanged and Version groups were
retained. The historical zero row above remains evidence for the old baseline,
not the merged implementation. This independently closes the narrow search/report
mapping recheck; A's earlier 37-pass author report is not counted as C execution.
No A business code was changed. The new dev also includes subsequent Agent/matching
changes: the old 48/25 runs are historical, not a fresh certification of all those
changes. Remaining product acceptance below is not closed by this small recheck.

## Remaining acceptance

Windows Agent integration, real LLM planning, HTTP/browser UI, approval/execution
across the full product flow and unknown-Workspace Real Mode remain unverified
by this run. Existing Windows C-tool evidence is separate and cannot substitute.
The 25-test suite includes injected contradictory-snapshot checks, not a new real
file-race proof. All-consumer shared-rule and D matching/classification integration acceptance
are outside this run; their latest implementation status follows owner records. No full-repository green or whole C2/C3 completion
is claimed. See [parsing evidence boundaries](document-classification-evidence.md)
for A/D's downstream input interpretation.

## Historical documentation/material precheck

The focused reproduction was actually executed again on the fixed baseline with:

```bash
/workspace/work/parser-validation-venv/bin/python docs/examples/reproduce_search_report.py
/workspace/work/parser-validation-venv/bin/python -m black --check docs/examples/reproduce_search_report.py
/workspace/work/parser-validation-venv/bin/python -m ruff check docs/examples/reproduce_search_report.py
git diff --check
```

It exited zero and observed the two rows above, with `sources_unchanged=true`.
Script formatting/lint, local Markdown target/anchor existence, whitespace and
conflict-marker checks passed. The original 48/25 test results above are reused,
not claimed as rerun in this documentation-only round. No runtime or formal
contract changes, repository-wide tests, commits or pushes were performed in that
historical precheck.

## Current document closeout checks

Commands on the latest dev cited above, using the existing installed project/dev
environment:

```bash
python docs/examples/reproduce_search_report.py
python -m pytest tests/test_agent_report_search.py -q -ra
python -m black --check docs/examples/reproduce_search_report.py
python -m ruff check docs/examples/reproduce_search_report.py
git diff --check
```

The reproduction returned both rows shown above; targeted report test **1 passed**.
Script Black/Ruff and document links/anchors/whitespace checks passed. Original
48/25 and Windows evidence are reused with their fixed baseline labels, not rerun
or combined into a new pass total. This document/script-only closeout does not
claim Windows Agent, LLM, HTTP, browser or whole-product acceptance.
