# Demo version and format diagnosis

Fixed dev: `f084b8a18198f61634c82e5bc12ee9bffc44f0f0` (after PR #54).
Environment: Linux / Python 3.12.14. No algorithm, threshold, resource budget,
production Agent code or public contract is changed.

## Original provided files

All three original DOCX reports in the provided 22-file archive read successfully.
Their hashes match the historical C evidence; extracted lengths are 293, 301 and
386 Unicode characters. No original file or extracted body is committed.

| File | SHA-256 |
| --- | --- |
| 课程设计报告_v1.docx | 5fecc50c3156149caf8c2306620a105af772879c6a48c8468ebf445a238c9ac2 |
| 课程设计报告_v2.docx | 7ebe442cd58fd66856b3a9bf3d4429ea3529b19c29a3a7dcd816d6d4f45adbf1 |
| 课程设计报告_v3.docx | 2b238158f11ad652fa5959f37f3c1f3710651159c963147ec82a2387ca10d941 |

| Pair | Original-text ratio, `autojunk=False` |
| --- | --- |
| v1/v2 | 0.9528619528619529 |
| v1/v3 | 0.8188512518409425 |
| v2/v3 | 0.858806404657933 |

For this batch reversing the arguments produces the same scores. All three
exceed 100 characters, but v1/v3 fails the confirmed 0.85 threshold. The
[complete-link contract](../API_CONTRACT.md#compare_versions) requires every pair
in a group to qualify. A bridge through v2 cannot merge all three. Two groups alone
therefore do not establish a parser error or missing Agent argument.

The public reproduction retained all three complete Documents and returned v2/v3
plus v1 alone at one location. A controlled Agent location returned v1/v2 plus v3
alone. Both follow current greedy file-ID ordering, without forced Demo answers.

## Determinism and recommendation scope

Six actual path-ID orders were exercised with six input permutations each. These
36 comparisons used the **in-process core**, not 36 public workers or Windows runs.
Each fixed complete input set produced identical full results under permutation.
Copying identical bytes to a different Workspace changes path-based IDs and may
change the legal greedy complete-link partition. Cross-Workspace partition
invariance is not guaranteed by v1.

`newest_candidate` recommends only within its group. Recommending v2 does not
eliminate a separately retained v3, prove a global latest version or confirm user
selection. Singletons have null candidates and empty changes. Low similarity is
not proof that materials are unrelated.

An earlier attempted batch of public-worker permutations stopped on the unchanged
5-second comparison timeout. It was not completed or counted as a passing run;
the 36 core comparisons are reported separately. No budget or assertion was relaxed.
The timeout cause remains unconfirmed and is distinct from grouping membership.

## Current controlled Agent reproduction

A temporary copy of all 22 files used the default ToolRouter and real TaskService
resolver. Only a validated Plan was controlled:
`list_files → read_document {} → compare_versions {}`. An observing router delegated
unchanged calls to the default implementation and recorded resolved arguments.

- Found 22; 10 supported files read successfully: 7 DOCX, 2 TXT, 1 PDF.
- Those ten complete Documents, in successful-read order, reached the one comparison
  call. All three reports were present; no fields were dropped.
- The task completed; all Documents remained in comparison groups and FinalReport
  preserved the groups. Source sizes, hashes and mtimes remained unchanged.
- The other 12 discoveries are unsupported, not automatically irrelevant.

This confirms the current controlled path. B's historical DeepSeek task still
requires its actual HEAD, Plan and Snapshot/ToolResult before attributing that
execution to missing reads/arguments or the grouping rule. Empty Plan arguments
are not proof of empty runtime input: the default resolver fills successful reads.

## Public reader versus upstream snippets

| Format | Public read_document / automatic Agent batch | Separate extract_snippet dispatcher |
| --- | --- | --- |
| TXT/PDF/DOCX/XLSX | Supported within documented omissions | Separate snippet behavior, not the public full-Document contract |
| CPP/JSON | Unsupported; explicit read fails with data=null | Decoded text snippet supported; no code execution/AST or JSON semantic analysis |
| CSV | Unsupported; explicit read fails with data=null | Not currently registered |
| H/PY/MD | Unsupported by the public reader | In upstream text dispatch |
| PNG/images | Unsupported by the public reader | Optional image support does not register OCR in C's public reader |

Actual unsupported archive counts: CPP 4, JSON 1, CSV 1, H 1, PY 1, MD 2, PNG 2;
all 12 public reads failed explicitly. The other 10 succeeded. Current Agent
automatic batching selects supported extensions. An explicit unsupported read
fails the material-analysis task before comparison; no Document is invented.
Classification/display must not equate unsupported with unrelated or analyzed.

## Reproduction aid

The [read-only diagnostic](examples/diagnose_document_versions.py) passes complete
Documents in requested order and emits summaries/hashes without extracted bodies
or change excerpts. It does not invoke servers, LLMs, approval or file writes.
Save output outside the scanned Workspace. Byte observations are not atomic
snapshots, authorization or proof of historical analysis freshness.

```powershell
& $Python docs/examples/diagnose_document_versions.py `
    "$Workspace\课程设计报告_v1.docx" `
    "$Workspace\课程设计报告_v2.docx" `
    "$Workspace\课程设计报告_v3.docx"

# Privately exported actual TaskSnapshot; no API/task replay.
& $Python docs/examples/diagnose_document_versions.py --snapshot "$Snapshot" `
    --expect "课程设计报告_v1.docx" `
    --expect "课程设计报告_v2.docx" `
    --expect "课程设计报告_v3.docx"
```

Snapshot mode selects the latest comparison attempt, never an older success after
failure. It compares returned group Documents to earlier full read snapshots using
strict JSON types/fields. Missing expected reads and missing compared filenames
are separate diagnostics. A failed comparison has unknown input coverage. This
inspects exported evidence; it does not expose unrecorded invocation arguments or
authenticate TaskService authority.

## B's remaining acceptance

1. Supply actual running full HEAD, task ID, natural-language goal, Plan and private
   Snapshot/Version ToolResult for the first Demo, with the three file byte hashes.
2. Check the three successful read results and union of all Documents in the latest
   successful comparison; match complete snapshots/text hashes, not only names.
   If input remains uncertain or comparison failed, obtain resolved call evidence
   from A. Snapshot alone does not record every actual invocation argument.
3. Reproduce in Windows on identical bytes; record path-ID order, groups, candidate
   reasons, source preservation and any timeout separately. Do not require a
   different directory's partition to match.
4. Confirm CPP/JSON/CSV remain discovered with truthful content-read status in the
   second Demo. No format support is added here.

Only with historical evidence can that LLM execution be attributed to missing
reads, a partial/different comparison input, runtime failure or the confirmed
heuristic limitation. Requiring all three in one group needs a separately agreed
general contract change; this PR does not make one.

## Checks for this increment

```bash
PYTHONPATH="$PWD/src" python -m pytest tests/test_document_version_diagnostics.py tests/test_document_versions.py tests/test_document_parser.py tests/test_agent_document_integration.py -q -ra
python -m black --check docs/examples/diagnose_document_versions.py tests/test_document_version_diagnostics.py
python -m ruff check docs/examples/diagnose_document_versions.py tests/test_document_version_diagnostics.py
git diff --check
```

The new diagnostic file contributed **22 passed**. The full command returned
**181 passed, 4 failed**, with failures in existing Version tests:
`test_suffix_before_trailing_newline_is_not_a_suffix[v1.1]`,
`test_legal_string_key_order_preserves_full_snapshot_and_permutations`,
`test_success_worker_exits_and_closes_all_pipes`, and
`test_public_complete_reread_document_is_preserved_and_deduplicated`.
They returned failed comparison results; the permutation failure explicitly showed
the unchanged 5-second timeout. A targeted rerun of only those four returned
**4 passed**. The earlier full failure is retained, not relabeled as a clean suite.
The cause remains unconfirmed; no source code in Document/Version was changed.
Black/Ruff and document link/whitespace checks passed. No full-repository,
Windows, real LLM or browser run is claimed for this increment.
