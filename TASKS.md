# TASKS.md

This file tracks the MVP development plan for the four-developer Vibe Coding workflow.

> Updated 2026-10-18 (dual-mode lightweight organization scope). The product baseline is now **unknown Workspace + Real Mode by default**. Fixed demo files remain useful for tests / fixtures / regression only; product logic must not depend on a pre-known file list, fixed material names, fixed version patterns, or fixed conflict / missing-item scenarios.

## 0. Shared Setup

- [x] Create shared GitHub repository
- [x] Create `dev` integration branch
- [x] Create `feature/agent-core`
- [x] Create `feature/document-intelligence`
- [x] Create `feature/frontend`
- [x] Create `feature/task-intelligence`
- [x] Add shared collaboration rules
- [x] Add architecture definition
- [x] Add API contract
- [x] Import / integrate FileForge base code
- [ ] All four developers run the original project successfully
- [x] Create a shared non-sensitive `demo/sample_workspace/` for tests / fixtures / regression only
- [ ] Confirm Python / Node / package-manager versions

### Current shared product baseline

- [x] Runtime Workspace is treated as unknown before the task starts.
- [x] Final classroom / product path is **Workspace + Real Mode**; Mock Mode is development / fallback support only.
- [x] Tests may use controlled fixtures, but production logic must not require fixture filenames or a fixed scenario.
- [x] Empty analysis results are valid business outcomes when the corresponding tool succeeds, e.g. no version group, no conflict, no requirement, or no missing item.
- [x] No tool may invent a version choice, requirement, conflict, or final material merely to make the demo look complete.

## 1. Developer A — Agent Core / Backend Orchestration

Branch: `feature/agent-core`

### Phase A1 — Understand and Wrap Existing File Operations
- [ ] Inspect FileForge entry points and module structure
- [ ] Identify scan/search/move/dedup/dry-run implementations
- [ ] Document reusable functions
- [ ] Implement or wrap `list_files`
- [ ] Implement or wrap `search_files`
- [ ] Implement or wrap `find_duplicates`
- [ ] Implement or wrap `create_folder`
- [ ] Implement or wrap `copy_file`
- [ ] Implement or wrap `move_file`
- [ ] Ensure all tools return `ToolResult`

### Phase A2 — Planner
- [x] Convert natural-language goal into structured `Plan`
- [x] Restrict planner to public tools defined in `API_CONTRACT.md`
- [ ] Add / finalize plan validation for unknown-Workspace dynamic execution
- [x] Add planner tests
- [x] Merge configurable Planner / no-LLM E2E support (PR #9)
- [x] Request JSON mode for compatible OpenAI Chat Completions models; omit the unsupported fixed temperature, classify empty/truncated/refused/error responses without exposing response text or credentials (Planner reliability PR)
- [x] One real Windows 11 `gpt-4.1-mini` Real Mode basic scan completed on an unknown Workspace: non-recursive `list_files`, 19 found files, completed task and report, no pending or executed write operations (team-provided 2026-10-18 evidence). This does not accept document analysis or recursive scanning.
- [ ] Verify real `read_document` → Version / conflict / requirement analysis and Matching / Package chains separately.
- [ ] Ensure Planner does not assume fixed demo filenames, fixed requirements, or fixed version/conflict outcomes
- [ ] Treat valid empty analysis results as normal branches rather than task failures

### Phase A3 — Executor
- [x] Execute plan steps sequentially
- [x] Track step status
- [ ] Finalize passing prior ToolResults into later tool arguments for C/D integration
- [x] Stop safely on tool failure
- [x] Add execution tests

### Phase A4 — Approval Gate
- [x] Auto-run low-risk operations
- [x] Pause medium-risk operations
- [x] Produce operation preview
- [x] Bind preview to `preview_id`
- [x] Reject stale / duplicate / mismatched approvals with `409`
- [x] Support approve-all / reject behavior for MVP
- [x] Ensure delete/overwrite are impossible through public tools

### Phase A5 — Verification
- [x] Verify frozen approved folder/copy/move destinations before marking the task completed; failed checks retain a ToolResult and prevent FinalReport
- [ ] Re-scan destination after execution
- [ ] Check expected package contents
- [ ] Check archive operations when used
- [ ] Verify moved-file content against the pre-move source content; current verification checks destination existence and source absence only.
- [ ] Produce verification output for `FinalReport`
- [ ] Verify FinalReport reflects actual filesystem state after approved operations

### Phase A6 — Agent API
- [x] `POST /api/agent/tasks`
- [x] `GET /api/agent/tasks/{task_id}` returning `TaskSnapshot`
- [x] `POST /api/agent/tasks/{task_id}/approve`
- [x] `POST /api/agent/tasks/{task_id}/reject`
- [x] `GET /api/agent/tasks/{task_id}/report`
- [x] In-memory task state for MVP
- [x] HTTP error behavior matches current `API_CONTRACT.md`

### Phase A7 — C/D Tool Integration
- [ ] Register/use Developer C `read_document`
- [ ] Register/use Developer C `compare_versions`
- [ ] Register/use Developer D `detect_conflicts`
- [ ] Register/use Developer D `extract_requirements`
- [ ] Register/use Developer D `match_requirements`
- [ ] Register/use Developer D `build_package`
- [ ] Do not depend on C/D private implementation details
- [ ] Confirm matching / version "undecided but not failed" results remain valid TaskSnapshot results and do not become automatic selections
- [ ] Confirm failure propagation for shared Document conflicts: failed ToolResult retained, task fails safely, no package/file mutation continues, report remains unavailable until completed

## 2. Developer C — Document Parsing & Version Intelligence

Branch: `feature/document-intelligence`

### Phase C1 — Document Parser
MVP priority:
- [x] Inspect and reuse the FileForge text extractor for TXT
- [x] TXT full-text `read_document(path)` with standard `Document` / `ToolResult`
- [x] TXT path-based IDs, encoding/error handling, and source-preservation tests
- [x] PDF text-layer reading across pages (no OCR)
- [x] DOCX body paragraphs and table grids in original order, with merged origins/references and nested cell boundaries (not all Office content; see [DOCX increment](docs/docx-table-extraction.md))
- [x] XLSX cell-value reading across named worksheets (cached formulas only)
- [x] Inspect and reuse the existing PDF/DOCX/XLSX extractors
- [x] Normalize supported extraction results to the existing `Document`
- [x] Distinguish parse/read failures from no extractable text/cell values
- [x] Add temporary real-file tests for long content, errors, identity and source preservation
- [x] Verify the declared multi-format implementation on Windows (see evidence below)

TXT was merged in PR #2; PDF/DOCX/XLSX was merged in PR #5 at
`a6ee13a53100f0b2522f4e9ad07e0e0296bd59d4`.
User-supplied real Windows evidence for that commit records Windows 11 / Python
3.12.10 64-bit: parser + extractor **59 passed, 3 skipped**; supplemental checks
**11 passed, 0 failed, 0 skipped**. Two symbolic-link checks were skipped because
symlinks were unavailable, and one Linux-only case-sensitivity check was skipped
by design. Windows symbolic-link behavior remains unverified.
See [Windows parser validation record](docs/parser-windows-validation.md) for
coverage, evidence provenance and version applicability. This closes the declared
Windows multi-format check, not blanket C1 or Agent integration acceptance.
Supported content remains limited by
[extraction scope](API_CONTRACT.md#read_document-extraction-scope): no OCR, Office
headers/footers/images or formula calculation. DOCX table extraction has separate
fixed-HEAD Windows evidence; old Windows evidence alone does not validate it.
All formats retain the existing
[path ID rule](API_CONTRACT.md#path-based-document-identity).

DOCX table-increment Windows evidence reconciled on 2026-10-18:
`0fcc1df7696090ba74136848df57f97495584b04`, Windows 11 / Python 3.12.10 64-bit;
**17 passed** synthetic cases and **1 passed** original-file audit, separately,
with zero failures/errors/skips and both exit codes zero. Six tables / 215 grid
positions, body order, 10,162 characters, bytes/mtime/size/path/ID preservation
and standard Version limit failure are verified. See [evidence and limits](docs/docx-table-extraction.md#verified-windows-evidence-2026-10-18).
PR #28 is merged; this completes the scoped Windows validation record, not whole
C1/C2/C3, score interpretation or end-to-end delivery.

Windows TXT evidence was reported by the team lead in the 2026-10-15 collaboration
update: Windows 11 / Python 3.12.12, parser + extractor 42 passed and 3 skipped;
symbolic links were not verified due to Windows permissions. This is team-provided
evidence, not a Windows run performed in this development environment.

Optional later:
- [ ] OCR / image text extraction

### Phase C2 — Version Intelligence
- [x] Reuse / extend existing FileForge version-analysis capabilities
- [x] Filename normalization
- [x] Candidate version grouping
- [x] Use modified time / metadata as signals
- [x] Add content similarity as second-stage validation
- [x] Identify newest candidate conservatively; `newest_candidate=null` is valid
- [x] Produce deterministic, source-traceable change summary
- [x] Add version-analysis tests
- [x] Handle no-version / no-reliable-version cases successfully without forced grouping or recommendation
- [x] Confirm strict 100-character / 0.85 grouping, with the identical-text exception; low-similarity filename versions stay separate
- [x] Verify fixed-commit Windows Version unit / process-termination evidence (94 passed, 2 skipped)
- [x] Verify fixed-commit Windows four-format C public-tool pipeline (16 passed, no failures/skips)
- [ ] Complete cross-platform and end-to-end C2 acceptance; local implementation is not whole-phase completion

### Phase C3 — Version Contract
- [x] Finalize `compare_versions.data.groups[].newest_candidate` with team
- [x] Finalize `compare_versions.data.groups[].changes[]` with team
- [x] Record confirmed Version v1 and shared Document collection rules in `API_CONTRACT.md`
- [x] Finalize grouping / recommendation / comparison-order semantics for unknown Workspaces
- [x] Confirm 1 MiB compact JSON UTF-8 bound for complete `{"documents": [...]}` input; see formal contract
- [x] Correct responsibility wording: current A API has no task-cancel endpoint
- [x] Implement/export C public `compare_versions` with standard ToolResult
- [x] Verify fixed-commit Version worker/resource/termination unit tests on real Windows (see evidence record)
- [ ] Complete A registration and end-to-end integration with consumers
- [ ] Complete whole C3 integration/acceptance; contract confirmation and local export alone do not close the phase

Contract and local implementation milestones (not whole-phase acceptance): [Version v1](API_CONTRACT.md#compare_versions) and
[shared Document collection rules](API_CONTRACT.md#shared-document-collection-rules)
are confirmed. C implementation/export and Linux unit/resource/subprocess tests
are locally verified; fixed-commit Windows Version and C-tool pipeline evidence
is reconciled below. Agent integration acceptance remains uncompleted. Checked C2 items describe local scope, not complete cross-platform
acceptance. Unknown Workspaces may have no versions; use task-neutral positive/negative fixtures
only for tests and acceptance, with no fixed classroom v1/v2 dataset requirement.

Local Linux evidence (Python 3.12.14, dev baseline
`eb725e9cf7759bfb5f9e000c9e7428969ceba58f`): Version-specific tests **74 passed**,
including real 5-second timeout termination, repeated-text budget, input limits,
metadata equality, deterministic grouping and original-source preservation.
Parser/extractor regression is retained; Windows-only tests skip on Linux.
Final full-suite run: **256 passed, 20 failed, 4 skipped**;
related Version/parser/extractor tests: **143 passed, 4 skipped** (Windows-only).
Clean dev snapshot in the same environment: **182 passed, 20 failed,
4 skipped**. Failure node IDs and messages match exactly, with **zero new
failures**: 19 cases involve read-only home/config/database paths, and one Planner
case lacks `httpx` in this environment. These are freshly compared results, not
an inherited historical count. The full repository checks are not all passing.
Black/Ruff for C's changed Python files pass. Full-repository Black reports the
same 12 existing files, and Ruff the same 7 diagnostics, as the clean dev snapshot.
That initial Linux round added no dependencies and did not perform Windows
Version validation; the earlier Windows Parser evidence does not cover this tool.
D's shared-rule adaptation is still owned and pending on D's side.

Review-fix evidence at `0a2e9f473fc2957331a871d4d184e44c3677cde4`:
Linux / Python 3.12.14 Version tests **95 passed**; related regression
**164 passed, 4 skipped** (Windows-only path semantics). Full suite:
**277 passed, 20 failed, 4 skipped**; clean dev
`374e4266758a38a2a80f47e7da9bdbd49fc0a0a2`:
**182 passed, 20 failed, 4 skipped**. Failure node IDs/messages match;
19 involve read-only configuration/database paths and one lacks `httpx` in this
environment. These newer results supplement, not replace, the historical initial
implementation record above. Fix-file Black/Ruff and diff checks passed.
Strict end-of-string suffix and lossless JSON input fixes are preserved.
PR #13 subsequently received independent review and was merged into dev at
`490e5f11d2f545d2e0679b5592d9c398126326e3`. The earlier review-pending wording
is superseded; the PR merge alone does not establish Windows or end-to-end acceptance.

Windows Version evidence reconciled (2026-10-18): the supplied archive verifies
**93 passed, 2 skipped** at `490e5f11d2f545d2e0679b5592d9c398126326e3`, plus
**1 passed, 0 skipped** for normal-exit/closed-pipes validation: **94 passed,
2 skipped combined**. Windows 11 / Python 3.12.10 64-bit; both pytest exit codes
are zero. The two skips are unsupported real newline filenames. Exact nodes,
source/hash checks and the missing pre/post Git status limitation are recorded
in [Windows Version validation record](docs/version-windows-validation.md).
- [x] Add normal worker-success exit/pipes regression from the prepared supplement
- [x] Reconcile supplied Windows commit/environment/logs/JUnit/supplement source and skip reasons
- [x] Verify fixed-commit real four-format read_document -> compare_versions Windows pipeline (16 passed)

Unit/lifecycle evidence alone does not close the joint chain; the separate
16-case Windows supplement below covers that scoped C-tool gap. Agent/UI and
end-to-end acceptance remain pending. No withdrawn screenshot is used.

Local test-only integration on latest dev: Linux / Python 3.12.14 **96 Version
passed**, combined Version/parser/extractor **165 passed, 4 skipped**
(Windows-only). Added test Black/Ruff and document/diff checks passed.
No full-suite or end-to-end rerun is claimed; no classification work is implemented.

Joint-chain audit: separate Parser and Version success is not joint-chain proof.
The supplied retry archive now verifies all **16 passed, 0 failed, 0 skipped**
real TXT/PDF/DOCX/XLSX cases in `tests/test_document_version_pipeline.py` at
`490e5f11d2f545d2e0679b5592d9c398126326e3`, on Windows 11 / Python 3.12.10 64-bit.
Each format covers grouping/recommendation, non-grouping, identical-content and
insufficient-version abstention, repeat-read IDs and source bytes/mtime unchanged.
This is a separate run from Version **93 passed, 2 skipped** and lifecycle
**1 passed**. Source AST matches the prepared repository test; before/after
commits and Git status agree. The owner reports an initial collection failure
from pasted PowerShell text, resolved by correcting the test file, without
business changes; the first failed log is not included for independent verification.
Current C implementation and original helper tests are unchanged from the evidence
commit. Linux closeout regression: **181 passed, 4 skipped** (Windows path semantics);
test Black/Ruff and diff checks passed. No full-suite rerun is claimed here.
See the validation record for the exact matrix, minimal A joint-check steps and
parsing-content/metadata scope for D/A. Classification contract/implementation,
A/B Real Mode and end-to-end acceptance remain pending owner work.

Developer C no longer owns conflict detection, requirement extraction, missing-item matching, or package generation; those are assigned to Developer D.

## 3. Developer D — Task Intelligence / Package Builder

Branch: `feature/task-intelligence`

### Phase D0 — Repository / Contract Onboarding
- [ ] Read `AGENTS.md`
- [ ] Read `ARCHITECTURE.md`
- [ ] Read `API_CONTRACT.md`
- [ ] Read `TASKS.md`
- [ ] Inspect FileForge analysis/action capabilities before adding new modules
- [ ] Run relevant existing tests locally
- [ ] Sync `feature/task-intelligence` with latest `dev` before further integration work

### Phase D1 — Conflict Detection
- [ ] Finish / merge `detect_conflicts` from PR #7
- [ ] Detect inconsistent important values across parsed documents
- [ ] Return source file for each conflicting value
- [ ] Avoid automatically declaring one source correct
- [ ] Start with MVP-priority fields such as deadline / required-material conflicts
- [ ] Add conflict-detection tests
- [ ] Treat `conflicts=[]` as a successful empty result, not a failure

### Phase D2 — Requirement Extraction
- [ ] Finish / merge `extract_requirements` from PR #7
- [ ] Extract required material checklist from actual requirement / rule documents
- [ ] Do not depend on fixed black-hackathon filenames or a pre-known material list
- [ ] Return contract-shaped `ToolResult`
- [ ] Add requirement-extraction tests
- [ ] Treat `required_documents=[]` as a successful empty result when no reliable requirements are found

### Phase D3 — Requirement Matching / Missing Items

Current staged delivery decision:

**Phase 1 — filename-based candidate matching MVP**
- [ ] Freeze `match_requirements` public contract after A/B/C/D confirmation
- [ ] Match each requirement to **0 / 1 / N filename-based candidate Documents**
- [ ] Preserve all candidates; do not silently choose a unique file from multiple candidates
- [ ] Produce `required_documents` / `matched` / `missing`
- [ ] Keep `matched=[]` semantics dependent on `success`, `required_documents`, and `missing`; do not use it alone to infer execution state or completeness
- [ ] Do not add a private `unresolved` schema; use only team-frozen public fields
- [ ] Do not reinterpret C Version results or treat a version recommendation as material approval
- [ ] Implement shared Document duplicate/conflict validation after the rule is fully confirmed
- [ ] Add tests for 0/1/N candidates, full duplicates, contradictory snapshots, different IDs, no partial result on failure, and input immutability
- [ ] Update `API_CONTRACT.md` before implementing strict shared consumers
- [ ] Implement `match_requirements` as a separate public tool / change; do **not** expand PR #7 to include it

**Phase 2 — required follow-up, not cancelled**
- [ ] Alias matching
- [ ] Common-name normalization
- [ ] Semantic proof association across different names (for example linking differently named certificates to a broader requirement)
- [ ] Add corresponding cross-name / semantic matching tests

Phase 1 must not be described as satisfying the full generalized matching requirement. Phase 2 remains part of the planned product scope.

### Phase D4 — Package Builder

Architecture and Package schema merged in PR #29; implementation pending under
[API_CONTRACT.md](API_CONTRACT.md#plan_package--build_package--package-contract-not-implemented).
Use the team-required plan_id/selected_files/missing/unresolved/operations/report
structure with a separate content digest, not parallel files/issues arrays.
Separate read-only planning from approved actual execution; freeze full report
bytes before approval and keep runtime outcomes in Snapshot/ToolResult. The
proposed accept_incomplete increment, restricted report write and child-result
correlation are not implemented. PR #27 Agent matching integration is merged in
dev (c74308d), alongside frontend matching and C DOCX/validation updates; none
implements Package execution. No Package completion/acceptance is claimed here; Phase 2 matching
remains required. Planning selected_files are proposals, confirmed with mappings/report in the
same preview approval; accept_incomplete only additionally accepts its risks.
Any upstream failure ends the current Task; no Package recovery or historical
result import is supplied. The fixed proposed cleanup rule is fail-closed:
remove only safely bound, exclusively-created failed fragments; otherwise retain
and disclose. Current A unlink-by-path is insufficient. The four-field
cleanup_results shape and fail-closed recording policy are confirmed but not
implemented; Package execution integration remains pending.
Before plan_package, A must reread every analysis-dependent source, compare the
complete Document and check pre/post raw-byte SHA-256. Before an executable
preview, A must compare D's selected snapshot digests with its checked digests;
after approval it must recheck approved sources and targets. This is current
consistency revalidation, not proof of historical analysis bytes or removal of
all read races. See the handoff in API_CONTRACT.md.
Package FinalReport mapping must bind the current successful verified execution:
actual package_path and successful write results, frozen missing and unresolved,
and current conflict evidence are mandatory. Team-confirmed package_unresolved
retains frozen ordered risks and plan identity; implementation is pending. It is
required on successful verified Package reports and omitted (never null/{}) for
non-Package reports, superseding the earlier null suggestion. accept_incomplete
does not erase risks. Tasks requiring Package cannot fall back to ordinary
success reports when execution/verification is missing or fails; Snapshot keeps
actual results and report returns 409.

- [ ] Implement package selection/generation logic under `src/fileforge/package/**`
- [ ] Use explicit proposed file mappings at planning and obtain same-preview file/report approval before execution; do not present candidates or `newest_candidate` as a user choice.
- [x] Architecture: allow incomplete packages only with explicit acceptance of the specific frozen missing/undecided risks in the same approval.
- [ ] Finalize A/B schema, accept_incomplete request/409 behavior and report/UI implementation; architecture agreement is not integration acceptance.
- [ ] Default to copy, not move
- [ ] Never silently overwrite user files
- [ ] Generate task-neutral `PACKAGE_REPORT.md`
- [ ] Include missing items, conflicts, and unresolved/ambiguous candidate information through frozen public fields
- [ ] Finalize `build_package` ToolResult data shape with team
- [ ] Return `ToolResult`
- [ ] Add package tests

### Shared Document Rule Adaptation (D)
- [ ] Apply confirmed collection rules to existing `detect_conflicts`
- [ ] Apply confirmed collection rules to existing `extract_requirements`
- [ ] Apply the same rules to `match_requirements` when its public interface is finalized
- [ ] Test equal duplicates, metadata key order, every-field contradictions and whole-call failures
- [ ] Verify original-input resource checks precede deduplication under each tool's limits

These are adaptation tasks, not a claim that D's existing algorithms are absent
or that the checks are implemented. Full matching schema remains separately pending.

### Phase D5 — Approval Boundary / Integration
- [ ] Package logic must not bypass Developer A's Approval Gate
- [ ] Real create/copy/move operations remain medium-risk
- [ ] Expose `detect_conflicts`, `extract_requirements`, `match_requirements`, and `build_package` through shared contracts
- [ ] Ensure Developer A can call capabilities without importing D private implementation details

## 4. Developer B — Frontend / Product Experience

Branch: `feature/frontend`

### Phase B1 — Analyze and Reuse Existing Frontend
- [x] Inspect `frontend/`
- [x] Identify existing UI structure and API-call pattern
- [x] Reuse existing file-list / status / browser UI where useful
- [x] Keep existing frontend stack

### Phase B2 — Agent Workspace Skeleton
- [x] Add natural-language task input
- [x] Show selected workspace
- [x] Add Run Agent action
- [x] Add Agent Plan / progress area
- [x] Add visible loading and error states

### Phase B3 — Analysis Result UI
- [x] Show mock version groups / conflicts / required materials
- [x] Defensive Real Mode rendering from `TaskSnapshot.results`
- [ ] Strictly render finalized C/D result schemas after contracts are frozen
- [ ] Render successful empty results distinctly from tool failure / not-run states
- [ ] Render 0/1/N matching candidates without presenting multiple candidates as final selection
- [ ] Render `newest_candidate=null` / conservative version abstention as non-failure

### Phase B4 — Approval and Execution UI
- [x] Show pending file-operation preview
- [x] Show create/copy/move/archive operations clearly
- [x] Add approve / reject controls
- [x] Bind Real Mode approval to exact `preview_id`
- [x] Handle `409` without automatic re-approval
- [x] Never execute local file operations directly from frontend code

### Phase B5 — Final Result UI
- [x] Show task completion state
- [x] Show final package/report fields defensively
- [x] Show/copy package path
- [ ] Final browser/visual polish after real backend integration

### Phase B6 — Mock / Real Mode
- [x] Build Mock Mode for frontend-only development
- [x] Keep Mock Mode isolated from Real Mode
- [x] Implement Real Mode API client for all five Agent HTTP endpoints
- [x] Implement polling for `TaskSnapshot`
- [x] Stop polling on approval/completed/failed states
- [x] Do not silently fall back to Mock on real API failure
- [x] Verify current backend errors are shown as real backend errors in Real Mode

### Phase B7 — Unknown Workspace / Presentation Readiness
- [x] Maintain `demo/sample_workspace/` as a reproducible non-sensitive test / regression fixture
- [ ] Do **not** require the classroom Workspace to equal `demo/sample_workspace/`
- [ ] Verify Real Mode with a previously unknown Workspace selected at runtime
- [ ] Verify UI remains correct when there are no version groups
- [ ] Verify UI remains correct when there are no conflicts
- [ ] Verify UI remains correct when requirements are empty / all missing / all matched
- [ ] Verify UI remains correct with multiple matching candidates and no automatic selection
- [ ] Verify one non-hackathon task (e.g. comprehensive assessment / scholarship / course materials) without changing frontend logic
- [ ] Prepare backup screenshots / recording for classroom reliability

## 5. Shared Contract Decisions / Open Confirmations

### 5.1 Unknown Workspace / Real Mode
- [x] Team product direction: unknown Workspace is the normal runtime assumption, not a special demo case.
- [x] Fixed fixtures may be used for tests, but may not define product behavior.
- [x] Mock Mode is not the final acceptance path.

### 5.2 Matching staged delivery
- [x] B accepts Phase 1 filename-based candidate matching MVP + mandatory Phase 2 follow-up.
- [x] C accepts the staged delivery.
- [x] D accepts the staged delivery.
- [x] A confirms the complete Phase 1 contract at PR #19 HEAD `b28d407a319380c173ec9ca0e11a8b3a0d3ec49c`, including staged delivery and downstream failure propagation.
- [ ] Independently review the final document HEAD and merge the team-confirmed `API_CONTRACT.md` contract before D implements the public matching tool.

Phase 2 remains required: alias matching, common-name normalization, and semantic proof association are **not implemented by Phase 1** and must not be marked as complete.

Matching contract confirmation (not implementation acceptance): the project owner
relayed A's final acceptance of the entire PR #19 draft at
`b28d407a319380c173ec9ca0e11a8b3a0d3ec49c`, following B/C/D confirmation.
This includes the input/output and filename rules, Agent failure propagation,
TaskSnapshot.results retention, successful FinalReport.missing_items mapping and
no fallback to an older success after a newer failure. A explicitly accepted
whitespace-only filename rejection; it is no longer an open proposal.
The absence of matching-specific quotas in v1 is a confirmed boundary, not an
open blocker: do not inherit Version limits or promise arbitrary-scale support.
See the [Phase 1 contract](API_CONTRACT.md#match_requirements--phase-1-contract)
for authoritative rules. Formal freezing still requires final document HEAD
independent review and merge. Implementation, export, registration and integration
acceptance remain unfinished; no corresponding completion box is checked here.
Phase 2 remains required and unfinished.

### 5.3 Shared `Document[]` identity / duplicate / contradictory snapshot rule
Confirmed shared rule for `compare_versions`, `match_requirements`, existing
`detect_conflicts` / `extract_requirements`, and future public Document[] consumers.
The authoritative rules and adaptation scope are in
[API_CONTRACT.md](API_CONTRACT.md#shared-document-collection-rules):

- Same identity is determined by `file_id`.
- A fully identical `Document` (all fields equal, including `metadata`; object key order does not affect equality) may be stably deduplicated **after resource validation**.
- Same `file_id` with any field difference is a contradictory snapshot and should fail the whole tool with standard failed `ToolResult`, `data=null`; never choose by input order and never return partial results.
- Different `file_id` values are not merged merely because filename or text is identical.

Confirmation status:
- [x] B accepts as a shared rule.
- [x] C accepts as a shared rule.
- [x] D accepts as a shared rule / implementation target.
- [x] Record the confirmed shared rule in `API_CONTRACT.md`.

Confirmation basis: the project owner's relayed A integration/input requirements,
B's explicit all-field/metadata-key-order/resource-before-dedup acceptance,
D's explicit shared-rule acceptance without exceptions, and C's acceptance.
The project owner expressly adjudicated this merge to retain those obtained
confirmations and split them from implementation/acceptance status. A document
label alone is not a substitute for those confirmations.

Separate implementation / integration acceptance (not checked by this merge):
- [ ] A completes tool registration/access and Document-failure propagation implementation.
- [ ] A verifies failed ToolResult retention, safe task failure, no continued mutation, and report lifecycle in integration tests.
- [ ] D adapts its existing and future public Document[] tools and tests.

These tasks remain with their owners. Contract confirmation does not imply
existing tools already implement or have verified the rule.

### 5.4 No private `unresolved` field for now
- [x] Current plan does not add a private `unresolved` field.
- [ ] A/B/D finalize how multiple candidates / version abstention appear in `TaskSnapshot`, `FinalReport`, package planning, and UI using frozen public fields.

### 5.5 Confirmed Version contract / pending acceptance
- [x] Confirm strict 100-character / 0.85 grouping and identical-text exception for unknown Workspaces; B explicitly confirmed, C accepted. Real versions may be missed; do not force a relation.
- [x] Confirm Version resource limits, including **1 MiB = 1,048,576 UTF-8 bytes** for the complete actual `{"documents": [...]}` input, not the Document array alone or text alone.
- [x] Record Version v1 in `API_CONTRACT.md` before implementation and strict consumption.

Use the [formal Version contract](API_CONTRACT.md#compare_versions) for compact
JSON measurement (`ensure_ascii=False`, `separators=(",", ":")`,
`allow_nan=False`), pre-dedup/pre-worker checks, full grouping/recommendation/order
semantics and subprocess budgets. This section references obtained confirmations;
it does not redesign or override the contract. Local C implementation and Linux
results are recorded in C2/C3 above.

- [x] Verify fixed-commit real Windows Version unit / subprocess termination evidence.
- [x] Verify fixed-commit Windows four-format read_document -> compare_versions C-tool pipeline (16 passed).
- [ ] Complete A tool integration, failure propagation and result mapping acceptance.
- [ ] Complete D shared-rule adaptation and tests.
- [ ] Complete Real Mode end-to-end acceptance on unknown Workspaces.

None of C2/C3 as a whole, A integration, D adaptation or end-to-end delivery is
marked complete by contract confirmation or this documentation-only merge.

## 6. Integration Milestones

### Milestone 1 — Base Project Works
- [x] FileForge base code integrated
- [ ] All four developers can launch project locally
- [x] Shared regression fixture exists; it is **not** the required classroom Workspace

### Milestone 2 — Independent Core Modules Work
- [x] Developer A: Agent HTTP lifecycle / approval API exists on `dev`
- [x] Developer C: multi-format parser produces normalized documents
- [ ] Developer C: version intelligence works against frozen contract
- [ ] Developer D: conflict / requirement tools from PR #7 are reviewed / merged
- [x] Developer B: Frontend Agent Workspace works with mock data and Real Mode adapter

### Milestone 3 — Backend Tool Integration Works
- [ ] Agent can call Developer C/D analysis tools through shared contracts
- [ ] `read_document` works end-to-end for MVP formats
- [ ] `compare_versions` works end-to-end
- [ ] `detect_conflicts` works end-to-end
- [ ] `extract_requirements` works end-to-end
- [ ] `match_requirements` works end-to-end
- [ ] `build_package` produces valid planned operations / results

### Milestone 4 — Frontend / Backend Integration Works
- [ ] Frontend can submit a natural-language task against an unknown runtime Workspace to real Agent API
- [ ] Frontend can display backend Plan and task status
- [ ] Frontend can display real version / conflict / requirement / matching / missing-item results
- [x] Frontend can submit approval / rejection with `preview_id`
- [ ] Frontend can display real completed `FinalReport` from the full C/D-integrated flow

### Milestone 5 — Safe Execution Works
- [x] Approval gate behavior exists before medium-risk operations
- [ ] Package generation works through the approval boundary
- [ ] Verification works against actual filesystem state
- [x] No automatic deletion or overwrite is possible through current public tool boundary

### Milestone 6 — Real-Mode Demo Ready
- [ ] A previously unknown Workspace can be selected at runtime without code changes
- [ ] Primary regression prompt succeeds consistently when its required evidence exists
- [ ] At least one different task domain works without scenario-specific code changes
- [ ] Empty / ambiguous / failure cases produce understandable, non-misleading UI
- [ ] File-changing operations still require explicit approval
- [ ] Demo backup recording prepared

## 7. Primary Regression Prompt

The following remains a useful **regression scenario**, but it is not the product's only supported scenario and does not imply a fixed classroom Workspace:

> 帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，最后生成一个报名资料包。执行文件操作前先让我确认。

Additional acceptance must cover at least one non-hackathon task using the same product logic and a different Workspace.

## 8. Cut Scope Rules

If schedule slips, cut in this order:
1. OCR
2. MCP integration
3. rich semantic diff visualization
4. multi-field conflict extraction → keep deadline / required-material conflict only
5. advanced UI polish

Do **not** cut:
- unknown-Workspace runtime support
- natural-language task input
- Planner
- Tool Calling
- Approval Gate
- real file operations
- one complete Real Mode end-to-end flow
- the planned Phase 2 matching capability from the final product scope; it may be scheduled after the Phase 1 MVP, but must not be silently reclassified as already complete

## 9. Daily Collaboration Checklist

Before coding:
- [ ] Pull latest `dev`
- [ ] Merge `dev` into your assigned feature branch
- [ ] Read shared contract changes
- [ ] Read the latest `TASKS.md`, especially Section 5 shared decisions
- [ ] Choose one small task

Before pushing:
- [ ] Run relevant tests / frontend checks
- [ ] Review `git diff`
- [ ] Confirm no other developer-owned files were changed accidentally
- [ ] Commit with a focused message
- [ ] Push only your assigned feature branch

Before merging PR:
- [ ] At least one independent review meets `AGENTS.md` (another human developer or a designated AI reviewer)
- [ ] Shared API changes are reflected in `API_CONTRACT.md`
- [ ] Tests / checks pass
- [ ] Unknown-Workspace / Real Mode behavior is not broken


## 10. Lightweight Smart Folder Organization (New, Approved Product Scope)

**Decision (2026-10-18, B / project lead):** retain BOTH product workflows:
1. Existing **task-driven material preparation** (requirements, versions, conflicts, matching, package); do not cancel or downgrade existing work or Matching Phase 2.
2. New **lightweight folder organization (Option A)**: scan an arbitrary user-selected Workspace, classify where justified using filename, extension, metadata and already-supported extracted content, propose useful folders, show uncertain files to the user, and safely organize approved files.

This is an approved **product direction and task allocation**, NOT approval of a new public API contract and NOT evidence of implemented capability. Existing completed PRs stay complete. Continue the currently blocking D Document[] adaptation / matching / package / Agent Real Mode work before this new branch of functionality.

### Shared behavior and boundaries

- [x] Agree on a lightweight, conservative classifier instead of building a new heavyweight semantic-classification subsystem.
- [x] Retain unknown Workspace + Real Mode as runtime assumptions, not a fixed classroom folder or fixed classification taxonomy.
- [ ] Define category derivation from actual candidates and the user's organizing instructions; do not hard-code course/competition/research names or invent a file purpose based on an ambiguous name.
- [ ] Treat ambiguous, unsupported or unparseable items as **needs user confirmation / unknown**, with the original files preserved. An extension-only category is a file-type grouping, not proof of its subject or purpose.
- [ ] Propose folder structures dynamically; support an empty Workspace, one-file Workspace, unrelated files and zero confidently classified files.
- [ ] Default to **copy** into a separate organization destination, not destructive move; never delete or overwrite originals, silently skip conflicts or modify files before backend approval.
- [ ] Reuse A's current frozen `preview_id` approval and filesystem verification; no D or B direct file mutations.
- [ ] Keep source data and generated output separate to avoid re-scanning generated folders as new input; validate paths remain in allowed Workspace scope.
- [ ] State realistic supported input sizes and format limits; current dynamic reading limit is **10 supported documents per collection**, so do not imply hundreds of files can all be content-classified or silently truncate candidates. Plan larger-workspace batching as a separate enhancement if needed.
- [ ] End-to-end acceptance: unknown folder -> discovered files -> conservative proposed categories -> preview folders and copies -> explicit approval -> safe execution -> verify destinations and show uncertain/unprocessed files.

### New contract decision gate (not yet frozen)

- [ ] D drafts a **minimal** public `classify_files` proposal (or equivalent agreed name): inputs from scanned file information / existing Documents plus user organization goal; outputs should preserve each original file identity/path, proposed category, evidence or reason, and uncertainty. Specify successful empty output vs failure; no extra private schema.
- [ ] A/B/C/D review the proposal for ownership, existing ToolResult conventions, Windows paths, available content, safe operation planning, and resource limits.
- [ ] Update `API_CONTRACT.md` and public tool registry **before** any strict cross-member consumer depends on new fields/tool names. Do not treat this proposed tool as currently implemented.
- [ ] Keep directory-plan representation as minimal as possible: prefer existing `create_folder`/`copy_file` PlanSteps and frozen approval preview over an unnecessary new public `plan_folder_organization` tool; introduce a new public tool only if a concrete capability gap is demonstrated and agreed.

### A — Agent Core / Backend Orchestration: new work

- [ ] After completing pending D public-tool integration, consume the agreed classification ToolResult in a task-neutral organization workflow (same unknown-Workspace selection and natural-language input).
- [ ] Translate confirmed classifications into safe `create_folder` / `copy_file` PlanSteps; avoid collision/overwrite and output-inside-input rescan loops; do not automatically move uncertain files.
- [ ] Keep final resolved paths/arguments frozen in `pending_operations` with `preview_id`, require user approval, then verify filesystem outcomes and propagate failures without pretending partial success.
- [ ] Test no files, ambiguous files, failed reads, duplicate target names, stale approvals, denied approval and workspace boundary violations.

### B — Frontend / Product Experience: new work

- [ ] Add an organization-mode entry next to the existing task-material mode without replacing its UI or Real Mode transport.
- [ ] Show a folder-tree / file-to-destination preview, source identity, proposed classification reasons, unknown/needs-confirmation section, file-type-only classification distinction and copy-vs-move semantics.
- [ ] Reuse the current Agent progress, errors, preview approval/rejection and report presentation; no frontend filesystem writes or shadow classification rules.
- [ ] Real Mode test on a previously unknown mixed Workspace, an empty Workspace, unclassifiable files, and collision/failed-operation outcomes; prepare classroom screenshots or backup video after actual integration.

### C — Document Parsing & Version Intelligence: new work

C/A controlled-plan integration at `5df6777dbe385f7e83167445262c95e698b3e9e1`:
Linux **48 passed** (new default-route acceptance) and **25 passed** (existing
Agent/PR #22 tests, including fault injection). See [commands, evidence and A reproduction](docs/c-agent-integration-validation.md).
PR #25 is merged as `99525cb4a4810dfbb592a4549c0d4273b93fd82d`.
C's Linux minimal recheck at dev `4d43cbd897e95dc91234e8e515f0bf7478699d07` confirms
both listing and searching retain two found_files, two read Documents and one
Version group, with original sources unchanged; report regression **1 passed**.
The historical zero result belongs only to `5df6777...`; A's 37-pass author result
is not a C independent run. This is a narrow controlled-plan check, not real
LLM/HTTP/browser acceptance or whole C2/C3/all-consumer shared-rule adaptation.

DOCX tables are merged through PR #28; fixed-HEAD Windows 17 + 1 evidence and
its current-source applicability are recorded in the [DOCX record](docs/docx-table-extraction.md).
Reading table structure does not interpret or calculate scores.

- [x] Document the existing parser contents/field provenance and classification evidence limits in [C input evidence](docs/document-classification-evidence.md): filename/extension clues versus extracted text, currently empty metadata, format omissions and explicit failures. This completes only the explanation, not classifier implementation or acceptance.
- [ ] Assist with public `Document[]` provenance/limits and tests for unsupported, empty-text, image/scanned, and other unreadable items; keep Version responsibilities and remaining integration/acceptance boundaries unchanged.

### D — Task Intelligence: new work

- [ ] After existing shared Document[] adaptation and Matching / Package milestones, draft the minimal classification interface and obtain team agreement before implementation.
- [ ] Implement conservative, task-neutral `classify_files` logic using actual filename/extension/metadata and available extracted text; dynamically derive categories when evidence supports them, otherwise abstain. Do not depend on fixture names or claim model-level semantic certainty.
- [ ] Produce classification decisions that A can translate into an organization plan; surface ambiguous cases and target-name collisions for approval, without D bypassing A's operation gate.
- [ ] Add deterministic regression tests for mixed/unknown files, no supported text, no confident categories, non-hackathon domains, different folder names, same-name collisions, input immutability, and whole-tool failure behavior.

### Implementation order / PR hygiene

1. **Do not block the existing delivery:** D finishes `detect_conflicts` / `extract_requirements` Document[] public-boundary checks, then Matching/Package according to their existing contracts; A integrates safely.
2. D opens a *contract-only proposal* for lightweight classification (and any demonstrated operation-plan schema gap); A/B/C confirm.
3. After `API_CONTRACT.md` is updated, D implements classification in a separate focused PR.
4. A adds classification-to-operations orchestration in an A-owned PR; B adds the organization-mode UI in a B-owned PR; C supplies evidence/scope checks as needed.
5. Four-developer Real Mode integration and safety acceptance. Keep the original task-driven material-packaging workflow working in parallel.

**Acceptance distinction:** filename/extension classification is *not* semantic material-purpose understanding; users must be told when the system cannot establish a reliable category. Neither demo convenience nor a successful Mock Mode render counts as proof of a complete Real Mode workflow.

## Package cross-module testing delegation — 2026-10-20

**Ownership update:** A still implements Agent/TaskService/Approval/Execution/Verification and D still implements Package planning. C is additionally assigned **independent tests/fixtures/evidence only**, not A/D production changes. See [AGENTS.md](AGENTS.md#8-package-validation-delegation-2026-10-20).

- [ ] **C-P1 / immediate:** Add nonduplicative temporary-file tests for A's merged `package_evidence.py` covering complete Document strict identity, metadata/extra types, changed bytes with restored size/mtime, modifications during reread, failed reads, unsafe paths, contradictory sources, and D selected snapshot mismatch. The helper cannot prove that A supplied **all** analysis-dependent read results; test that rule when A's authoritative TaskService integration exists.
- [ ] **C-P2 / prepare now:** Define frozen Package Snapshot/ToolResult/FinalReport tests for partial copy failures, cleanup_results states and unknown ownership, report GET 409, package_unresolved preservation, old success not masking current failure, and omission of package_unresolved on non-Package reports. Do not count tests of not-yet-implemented APIs as passed.
- [ ] **C-P3 / after A and D integration:** Run controlled public-interface Document/Version -> D plan_package -> A preflight/approval/execution/result acceptance without DeepSeek or B's personal Workspace; verify version recommendation never authorizes a file choice and no partial success is presented as a verified final Package.
- [ ] **A:** Provide C authoritative input/result association, approval/error/409 contracts and callable integration seams. Keep all Agent production behavior, mutation/cleanup and final report implementation A-owned.
- [ ] **D:** Provide C public planner inputs and frozen source snapshot semantics; keep planner production implementation D-owned.
- [ ] **B:** Continue real Windows browser/DeepSeek cross-module acceptance; coordinate full-service startup verification using the merged `docs/local-agent-development.md`.

**Current factual baseline:** PR #36, #37 and #38 are merged; A's Package evidence helper and B's Package Fixture are not connected to a real executable Package flow. D `plan_package` PR #35 remains Draft as of this allocation. These checkboxes are not completed by existing unit tests or documentation alone. This allocation adds no API shape and does not change the already-confirmed Package contract.
