# TASKS.md

This file tracks the MVP development plan for the four-developer Vibe Coding workflow.

> Updated 2026-10-17. The product baseline is now **unknown Workspace + Real Mode by default**. Fixed demo files remain useful for tests / fixtures / regression only; product logic must not depend on a pre-known file list, fixed material names, fixed version patterns, or fixed conflict / missing-item scenarios.

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
- [ ] Re-scan destination after execution
- [ ] Check expected package contents
- [ ] Check archive operations when used
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
- [x] DOCX body-paragraph reading (not tables or all Office content)
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
[extraction scope](API_CONTRACT.md#read_document-extraction-scope): no OCR, DOCX
tables or formula calculation. All formats retain the existing
[path ID rule](API_CONTRACT.md#path-based-document-identity).

Windows TXT evidence was reported by the team lead in the 2026-10-15 collaboration
update: Windows 11 / Python 3.12.12, parser + extractor 42 passed and 3 skipped;
symbolic links were not verified due to Windows permissions. This is team-provided
evidence, not a Windows run performed in this development environment.

Optional later:
- [ ] OCR / image text extraction

### Phase C2 — Version Intelligence
- [ ] Reuse / extend existing FileForge version-analysis capabilities
- [ ] Filename normalization
- [ ] Candidate version grouping
- [ ] Use modified time / metadata as signals
- [ ] Add content similarity as second-stage validation
- [ ] Identify newest candidate conservatively; `newest_candidate=null` is a valid result
- [ ] Produce deterministic, source-traceable change summary
- [ ] Add version-analysis tests
- [ ] Ensure no-version / no-reliable-version cases succeed without inventing a group or recommendation
- [ ] Finalize the unknown-Workspace behavior for low-similarity obvious filename versions (e.g. whether `<0.85` means separate groups or candidate relationship without recommendation)

### Phase C3 — Version Contract
- [ ] Finalize `compare_versions.data.groups[].newest_candidate` with team
- [ ] Finalize `compare_versions.data.groups[].changes[]` with team
- [ ] Finalize grouping / recommendation / comparison-order semantics for unknown Workspaces
- [ ] Finalize complete serialized `Document[]` input-size bound with A
- [ ] Correct responsibility wording: current A API has no task-cancel endpoint; do not claim task cancellation is already implemented
- [ ] Update `API_CONTRACT.md` before strict consumers depend on those fields
- [ ] Expose `compare_versions` through shared public Tool contract

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
- [ ] Implement package selection/generation logic under `src/fileforge/package/**`
- [ ] Use only resolved / selected files; do not silently convert multiple candidates or `newest_candidate=null` into a final choice
- [ ] Decide with A/B whether an incomplete package may be generated when `missing` remains, and how that status appears in report/UI
- [ ] Default to copy, not move
- [ ] Never silently overwrite user files
- [ ] Generate task-neutral `PACKAGE_REPORT.md`
- [ ] Include missing items, conflicts, and unresolved/ambiguous candidate information through frozen public fields
- [ ] Finalize `build_package` ToolResult data shape with team
- [ ] Return `ToolResult`
- [ ] Add package tests

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
- [ ] A confirms staged delivery / downstream failure propagation as needed for Agent integration.
- [ ] After all confirmations, update `API_CONTRACT.md` **before** D implements the public matching tool.

Phase 2 remains required: alias matching, common-name normalization, and semantic proof association are **not implemented by Phase 1** and must not be marked as complete.

### 5.3 Shared `Document[]` identity / duplicate / contradictory snapshot rule
Proposed shared rule for `compare_versions`, `match_requirements`, and future public tools consuming `Document[]`:

- Same identity is determined by `file_id`.
- A fully identical `Document` (all fields equal, including `metadata`; object key order does not affect equality) may be stably deduplicated **after resource validation**.
- Same `file_id` with any field difference is a contradictory snapshot and should fail the whole tool with standard failed `ToolResult`, `data=null`; never choose by input order and never return partial results.
- Different `file_id` values are not merged merely because filename or text is identical.

Confirmation status:
- [x] B accepts as a shared rule.
- [x] C accepts as a shared rule.
- [x] D accepts as a shared rule / implementation target.
- [ ] A confirms the shared rule and Agent failure propagation.
- [ ] After A confirms, write the shared rule into `API_CONTRACT.md` before public tools rely on it.

This confirmation does not imply existing tools already implement the rule.

### 5.4 No private `unresolved` field for now
- [x] Current plan does not add a private `unresolved` field.
- [ ] A/B/D finalize how multiple candidates / version abstention appear in `TaskSnapshot`, `FinalReport`, package planning, and UI using frozen public fields.

### 5.5 Version contract still open
- [ ] Finalize the random/unknown-Workspace meaning of the current 100-character / 0.85 similarity heuristic.
- [ ] Finalize Version resource limits including complete serialized `Document[]` size, not text-only size.
- [ ] Freeze Version contract before C implementation and strict B/A consumption.

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
