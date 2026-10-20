# C Document/Version → Package acceptance preparation

Checked baseline: `20cd15ca4388232d55dbcc0d396eecd03620bbc0` (includes PR #36 and A helper PR #38).
This checklist neither changes the [merged contract](../API_CONTRACT.md#plan_package--build_package--package-contract-not-implemented)
nor claims Package implementation or acceptance. Package schema and the v1
revalidation/cleanup handoff are confirmed requirements; implementation remains
pending. No new Document field or ID exists.

## Reuse existing coverage

| Existing test | Evidence / boundary |
| --- | --- |
| `tests/test_document_parser.py::test_identity_survives_repeat_reads_and_content_changes` | Same path retains ID when content changes; rename/copy identity has separate coverage |
| `test_same_length_change_with_restored_mtime_keeps_identity_not_content` in that file | New temporary TXT case: identical file_id/path/size/modified_time and exact restored mtime_ns, different decoded text and raw-byte SHA-256; repeated reads are stable on each side |
| `tests/test_document_versions.py` | Full Document preservation, deterministic recommendations/abstention, duplicate/contradictory snapshots, all Version resource limits and standard failures |
| `tests/test_agent_document_integration.py` and existing C/A records | Read failures/contradictory snapshots stop operations; successful groups reach reports. Controlled-plan evidence is not Package execution acceptance |

The new byte digest is test-only, not a public Document field or a Package digest
implementation. Tests mutate only synthetic temporary sources, never user files.

## Keep three separate evidence gates

| Gate | What must be established | What it does not establish |
| --- | --- | --- |
| Analysis freshness / current consistency | Before plan_package, A publicly rereads **every analysis-dependent source**, including notices and unselected relevant candidates. Compare the entire Document with the original successful read using shared strict snapshot rules; raw-file SHA-256 immediately before/after the reread must agree | This is not proof that the original analysis read identical historical raw bytes; equal ID/stat/text alone is insufficient |
| Pre-approval source snapshot and cross-check | D obtains stable source snapshots. After planning and before publishing an executable preview, A checks task/result provenance and each selected source reference, size, mtime_ns and D snapshot.sha256 against its checked evidence; bind the frozen plan/evidence to the same preview_id | D's stable snapshot alone does not replace A's first-stage reread or prove historical analysis bytes |
| Post-approval source validation | A checks approved digests and source/target safety before mutation and at each use; verify copied bytes against approved digests, frozen report bytes and exact file set | This does not repair stale first-stage analysis or eliminate all filesystem races |

These are now formal [v1 revalidation handoff requirements](../API_CONTRACT.md#confirmed-v1-analysis-to-source-revalidation-handoff-not-implemented),
not an unresolved request for A/D to design a protocol. A keeps checked digests and
source/result associations in task-scoped approval state, with no new Document
field. D does not authenticate client-supplied evidence. Full comparison includes
metadata/extra fields, exact types, missing versus null and key-order-independent
object equality. Any failed reread, contradictory Document, unstable byte read,
missing evidence or cross-check mismatch fails the Task without an executable
preview. A cannot substitute D's snapshot or use accept_incomplete to bypass it;
no automatic reanalysis/old-result fallback disguises a failure.

**Accepted guarantee limit:** matching pre/post reread hashes detects observable
change but cannot exclude adversarial change-and-restore during reading or every
filesystem race. Matching the complete Document does not prove original analysis
historical-byte identity. A stronger historical guarantee would need a separately
agreed C/A read-time mechanism; it is not a v1 implementation prerequisite. The
new same-length/restored-mtime test remains a required negative example, not a
claim that the parser returns an atomic byte snapshot.

## Minimum Package checks after D/A delivery

1. Preserve exact original file_id/path/filename in proposed selections, Version
   evidence, unresolved references and frozen reports. A copied destination is not
   the original source; do not repurpose source IDs as content hashes.
2. Apply all three confirmed gates above. Any failed revalidation or mismatch
   fails the current Task without preview; do not silently refresh analysis or
   mix old Version text with a new preflight snapshot.
3. Keep newest_candidate as recommendation only. A proposed selection is not a
   user choice until the same-preview approval. Preserve null candidates, reasons,
   alternatives and version_undecided even if a file is proposed or risks accepted.
4. Reading failure, Version resource failure, contradictory snapshots or any
   upstream failure must stop the current task; no successful plan, approval,
   hidden truncation or replacement with an older successful ToolResult.
5. Keep frozen risks through execution/reporting. The explicitly confirmed
   package_unresolved rule is required for Package reports (even empty items),
   omitted for non-Package reports; accept_incomplete never clears risks.
6. A missing/failed/unverified current Package execution cannot fall back to an
   ordinary successful FinalReport. Retain actual results and report 409.

A source helpers revalidate_documents/bind_selected_snapshots are now merged
and have separate six-test evidence; they are not wired into TaskService/executor.
D planning/snapshots and A authoritative collection, approval/execution/result
mapping still await delivery on this baseline. Do not write tests calling imagined
Package entry points or adapters. Add focused C-owned integration checks only
after the relevant public boundary is delivered; A/D own their production fixes.

## Minimal integration tests awaiting public A/D implementation

| Case | Minimum acceptance assertion |
| --- | --- |
| Valid handoff, including non-selected/notice sources | Every analysis-dependent original successful Document is reread, full comparison and pre/post hashes pass; D selected snapshots match and one preview binds the exact plan/evidence |
| Same ID/size/restored mtime but changed TXT bytes/text | Existing synthetic source setup is reused; full Document mismatch fails with no preview, despite equal stat/ID fields |
| Reread failure or changing raw bytes | Read failure/resource failure/contradiction and differing pre/post hashes prevent planning/preview; no partial result, older-success fallback or risk-acceptance bypass |
| Returned D snapshot/provenance mismatch | Missing or wrong source reference/size/mtime_ns/digest or task/result association fails before executable preview; A does not rewrite D's snapshot |
| Change after approval | A rejects changed approved sources/unsafe targets; stop later operations, retain actual results, task failed and report 409; verification uses approved, not newly substituted digests |
| Retained recommendation/risks | Null newest_candidate and reasons remain evidence, not automatic selection; approved/accepted incomplete risks survive into the required Package report |

Do not implement these against fake adapter functions or assume exported Package
APIs exist. Exercise the delivered A source helpers independently; await D's
public planning/snapshot/report validation and A's task-bound complete evidence
collection, retained helper output, approval/execution and report mapping.
The closed dependency is the v1 protocol design; the remaining dependencies are
implementation and observable integration evidence. Strong historical-byte proof
and race elimination are deliberately not asserted by these tests.

## Status of the earlier contract-wording feedback

PR #36 replaced the earlier section-level “具体 schema 待 A/B 复核” status with:
“The team merged this Package schema in PR #29” and “This clarification confirms
the revalidation handoff and cleanup_results shape”. The old feedback table in
this checklist is superseded, not an outstanding whole-contract freeze blocker.
The new `Confirmed v1 analysis-to-source revalidation handoff (not implemented)`
is normative. Remaining proposed/example wording is not authority to bypass the
confirmed requirements or evidence that implementation has shipped. The explicitly
confirmed package_unresolved requirements remain unchanged.

## Controlled C-only measurements on this baseline

Linux / Python 3.12.14: **9 passed, 0 failed/skipped**. All file operations use
pytest temporary sources; Documents are real read results or explicitly synthetic
snapshots. No real Workspace, HTTP/API, A/D adapter or Package implementation is
invoked. These are controlled C measurements, not Package acceptance.

| Input / reusable test | C public-entry result actually checked | A/D check location | Still awaiting integration |
| --- | --- | --- | --- |
| Real TXT read twice; `test_public_complete_reread_document_is_preserved_and_deduplicated` | Whole Documents equal; comparison succeeds and retains one complete snapshot, null candidate, single_document and empty changes; inputs/source unchanged | A's complete reread comparison, then source/result binding | No A reread gate or approved preview was exercised |
| Same file_id with manually changed metadata; existing `test_duplicates_metadata_order_and_extra_fields` | Reordered equal metadata deduplicates; changed metadata fails compare_versions with data=null and contradiction error; extra/all-field differences are also checked | Shared complete-snapshot check before A planning; D input consistency boundary | Not proof A/D already enforce this rule |
| Temporary TXT rewritten to equal byte length and original mtime; existing new same-stat test | Repeated reads keep file_id/path/size/modified_time; exact mtime_ns restored, text and raw SHA-256 differ | A must detect complete-Document difference in pre-plan reread, not trust stat/ID | Task failure, no preview, no old-result fallback remain A integration checks |
| Real synthetic DOCX core title alpha → bravo; `test_docx_unextracted_property_changes_bytes_not_full_document` | Both real files load with the intended different core title; equal-length uncompressed property entries ensure equal archive size, mtime restored; full parsed Documents are equal but byte hashes differ. C comparison correctly succeeds/deduplicates to single_document | A obtains current raw hashes; D takes a genuine snapshot; A cross-checks them before preview and checks approved bytes later | This does not prove a change occurred inside A's pre/post reread window; if it happened before revalidation and both current hashes agree, v1 does not promise historical-byte detection |
| Nonexistent path in a temporary directory; existing `test_missing_file` | read_document returns success=false/data=null and readable error, no fabricated Document | A pre-plan public reread and failure barrier | No task/preview/report behavior is simulated here |
| Synthetic full Documents exceeding count, per-text, total-text or original-input volume; existing `test_resources_before_deduplication` | compare_versions failures retain data=null and limit messages; duplicates cannot bypass limits | Upstream Version failure stops A planning; do not call D or revive older success | Package/API propagation remains separate; no resource rule is loosened |
| Synthetic same-bucket pairs for identical_content, insufficient_evidence, version_tie; `test_public_abstention_preserves_null_reason_and_original_documents` (3 cases) | Public comparison succeeds with newest_candidate=null, exact reason retained, all original Documents/changes retained and input unchanged | D's frozen evidence/unresolved derivation and A's same-preview selection/risk gate | Abstention is not task failure or automatic selection; no Package unresolved record, approval or report is fabricated by this test |

Metadata in the synthetic metadata test is manually supplied strictly to test
full-snapshot comparison. The actual public reader still emits metadata={};
no claim of automatic metadata extraction or new Document fields is made.
The DOCX sample changes an unextracted property, not visible body text. Its source
zip bytes/size, real title values and full Document equality are asserted before
testing deduplication, rather than assuming the fixture meets the condition.

### Exact offline command used

From the repository root, with its existing installed project/dev dependencies:

```bash
python -m pytest \
  tests/test_document_parser.py::test_same_length_change_with_restored_mtime_keeps_identity_not_content \
  tests/test_document_parser.py::test_docx_unextracted_property_changes_bytes_not_full_document \
  tests/test_document_parser.py::test_missing_file \
  tests/test_document_versions.py::test_public_complete_reread_document_is_preserved_and_deduplicated \
  tests/test_document_versions.py::test_duplicates_metadata_order_and_extra_fields \
  tests/test_document_versions.py::test_resources_before_deduplication \
  tests/test_document_versions.py::test_public_abstention_preserves_null_reason_and_original_documents \
  -q -ra
python -m black --check tests/test_document_parser.py
python -m black --check tests/test_document_versions.py
python -m ruff check tests/test_document_parser.py tests/test_document_versions.py
git diff --check
```

`python` denotes the existing project validation virtual environment, running
Linux / Python 3.12.14. No dependency or global configuration was changed.
The nine-case command above was rerun on the checked baseline: **9 passed**.
Earlier parser/full-suite results remain historical; no whole-suite, Windows,
real LLM, Agent/API or browser acceptance is claimed here.

## Independent helper supplement

`tests/test_document_package_evidence.py` adds **21 passing C cases**. Together
with A's six unchanged existing helper cases, the command below gives
**27 passed, 0 failed/skipped** on the checked baseline. The separate nine-case
C command above also passes; these totals are recorded separately.

```bash
python -m pytest tests/test_document_package_evidence.py tests/test_agent_package_evidence.py -q -ra
python -m black --check tests/test_document_package_evidence.py
python -m ruff check tests/test_document_package_evidence.py tests/test_document_parser.py tests/test_document_versions.py
git diff --check
```

Black checks on each of the three modified Python files, Ruff, document local
links/anchors, conflict-marker/whitespace checks and diff checks pass. The test
source is the four-file PR patch on the checked baseline; no tested production
code differs from that baseline. Raw logs, source attachments and Demo measurement
artifacts are outside this PR.

| Coverage reused | Added independent C evidence |
| --- | --- |
| A's extra-field and numeric-type mismatch cases; C's complete snapshot cases | Nested dict/list differences, missing/null, bool/int, int/float, array order and nested object key-order equivalence; input preservation |
| C's equal full parsed DOCX with changed archive bytes | Real unextracted DOCX property changes during public reread; full parsed result, size and restored mtime remain equal, while the helper rejects changed pre/post SHA-256 |
| A's valid indices and failed original read | Negative, bool, string, float and duplicate indices rejected; arbitrary valid index 999 accepted, demonstrating the Task provenance boundary |
| A's symlink test | Relative/outside-Workspace paths rejected |
| A's valid binding, wrong digest and missing file_id | Wrong source path/filename, size/mtime and bool/null snapshot types rejected without mutation |

Metadata in the helper fixture is explicitly synthetic; the actual reader emits
metadata={}. Injected readers exercise the delivered helper's comparison seam;
the DOCX byte-only case uses real public read_document calls. Minimal selected
snapshot fixtures exercise binding only, not a real D plan or executable preview.

The helper cannot authenticate otherwise legal indices against the current Task,
prove freshness/range/ownership, or discover omitted analysis inputs. A retains
responsibility for authoritative Task provenance and **all** analysis-dependent
sources, including notices and unselected candidates. These remain integration
requirements, not tested helper guarantees.

Real D planning, task-bound preview/approval, post-approval validation, execution,
cleanup, report 409 and unresolved-risk retention remain pending integration.
Filesystem replacement during hashing and further malformed strict-JSON edge
cases are not claimed covered. Full Package execution, Windows and end-to-end
acceptance have not passed by virtue of these tests.

## Platform follow-up: two independent planning cases

Tested source baseline: `4f8fb35258ad018068068ebc9fe2fa3146d8c774`, with only
these local C test additions; dev is `a0267e84a4ace9dd8af470c61bc5ae5a44697681`
(includes #35/#40/#42). Earlier pending-D-planner statements above describe the
older checked baseline, not this follow-up: public read-only plan_package is now
available. Executable Package approval/execution acceptance remains separate.

Linux / Python 3.12.14: the actual combined run collected **29 passing cases**:
23 C cases (previous 21 plus 2 new cases) and A's 6 unchanged helper cases.
The separate nine-case C command above was rerun: **9 passed**. Actual commands
run from repository root using the existing validation interpreter as `python`:

```bash
PYTHONPATH="$PWD/src" python -m pytest tests/test_document_package_evidence.py tests/test_agent_package_evidence.py -q -ra
python -m black --check tests/test_document_package_evidence.py
python -m ruff check tests/test_document_package_evidence.py
git diff --check
```

All checks passed. An additional import-location assertion confirmed the loaded
`fileforge.package.planning` is under this checkout's src, not an older editable
installation. No D production code or ctime check was changed.

- During actual descriptor reading, a synthetic temporary UTF-8 file is rewritten
  in place with different equal-length bytes and its exact original mtime restored.
  The test proves mutation completed, then requires standard failed plan_package
  (success=false, data=null, readable changed error) and no destination directory.
  A write denied by the OS cannot satisfy this assertion; it is not counted as
  successful mutation detection. This is not a Windows replacement test.
- A Chinese-and-space parent path, Chinese filename and Chinese UTF-8 text produce
  a successful read-only plan. Source reference, raw digest/size/mtime, original
  bytes, input request and directory contents remain intact; no output is created.
  This is neither approval nor Package execution acceptance.

Windows follow-up was not executed. Any future PowerShell runner must explicitly
set `$env:PYTHONPATH = Join-Path $Repo "src"` for the independent worktree and
assert actual import locations (at least fileforge.package.planning and
fileforge.document) are under that worktree's src before testing. On receipt of
D's immutable fix HEAD, use another independent worktree; do not merge that fix
into C merely to test it. Platform capability skips must retain their reasons;
OS-denied replacement is not proof that a real replacement was detected.
