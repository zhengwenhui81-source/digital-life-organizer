# TASKS.md

This file tracks the MVP development plan for the four-developer Vibe Coding workflow.

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
- [ ] Create a shared demo workspace with non-sensitive test files
- [ ] Confirm Python / Node / package-manager versions

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
- [ ] Convert natural-language goal into structured `Plan`
- [ ] Restrict planner to public tools defined in `API_CONTRACT.md`
- [ ] Add plan validation
- [ ] Add planner tests

### Phase A3 — Executor
- [ ] Execute plan steps sequentially
- [ ] Track step status
- [ ] Pass tool results back into execution context
- [ ] Stop safely on tool failure
- [ ] Add execution tests

### Phase A4 — Approval Gate
- [ ] Auto-run low-risk operations
- [ ] Pause medium-risk operations
- [ ] Produce operation preview
- [ ] Bind preview to `preview_id`
- [ ] Reject stale / duplicate / mismatched approvals with `409`
- [ ] Support approve-all / reject behavior for MVP
- [ ] Ensure delete/overwrite are impossible through public tools

### Phase A5 — Verification
- [ ] Re-scan destination after execution
- [ ] Check expected package contents
- [ ] Check archive operations when used
- [ ] Produce verification output for `FinalReport`

### Phase A6 — Agent API
- [ ] `POST /api/agent/tasks`
- [ ] `GET /api/agent/tasks/{task_id}` returning `TaskSnapshot`
- [ ] `POST /api/agent/tasks/{task_id}/approve`
- [ ] `POST /api/agent/tasks/{task_id}/reject`
- [ ] `GET /api/agent/tasks/{task_id}/report`
- [ ] In-memory task state for MVP
- [ ] HTTP error behavior matches `API_CONTRACT.md`

### Phase A7 — C/D Tool Integration
- [ ] Register/use Developer C `read_document`
- [ ] Register/use Developer C `compare_versions`
- [ ] Register/use Developer D `detect_conflicts`
- [ ] Register/use Developer D `extract_requirements`
- [ ] Register/use Developer D `build_package`
- [ ] Do not depend on C/D private implementation details

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
- [x] Reuse / extend existing FileForge version-analysis capabilities
- [x] Filename normalization
- [x] Candidate version grouping
- [x] Use modified time / metadata as signals
- [x] Add content similarity as second-stage validation
- [x] Identify newest candidate
- [x] Produce semantic change summary
- [x] Add version-analysis tests

### Phase C3 — Version Contract
- [x] Finalize `compare_versions.data.groups[].newest_candidate` with team
- [x] Finalize `compare_versions.data.groups[].changes[]` with team
- [x] Record confirmed Version v1 and shared Document collection rules in `API_CONTRACT.md`
- [x] Implement/export C public `compare_versions` with standard ToolResult
- [ ] Validate Version worker/resource/termination behavior on real Windows
- [ ] Complete A registration and end-to-end integration with consumers

Contract-only milestone: [Version v1](API_CONTRACT.md#compare_versions) and
[shared Document collection rules](API_CONTRACT.md#shared-document-collection-rules)
are confirmed. C implementation/export and Linux unit/resource/subprocess tests
are locally verified; Windows Version and Agent integration acceptance remain
uncompleted. Checked C2 items describe local scope, not complete cross-platform
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
This round adds no dependencies. Real Windows Version validation has not run;
the earlier Windows Parser evidence does not cover this new tool. D's shared-rule
adaptation is still owned and pending on D's side.

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

### Phase D1 — Conflict Detection
- [ ] Implement `detect_conflicts`
- [ ] Detect inconsistent important values across parsed documents
- [ ] Return source file for each conflicting value
- [ ] Avoid automatically declaring one source correct
- [ ] Start with MVP-priority fields such as deadline / required-material conflicts
- [ ] Add conflict-detection tests

### Phase D2 — Requirement Extraction
- [ ] Implement `extract_requirements`
- [ ] Extract required material checklist from requirement/notice documents
- [ ] Return contract-shaped `ToolResult`
- [ ] Add requirement-extraction tests

### Phase D3 — Requirement Matching / Missing Items
- [ ] Match required items against local candidate files
- [ ] Produce required / matched / missing analysis
- [ ] Finalize shared representation with A/B/C before consumers depend on it
- [ ] Update `API_CONTRACT.md` first when shared fields are agreed
- [ ] Add matching tests

### Phase D4 — Package Builder
- [ ] Implement package selection/generation logic under `src/fileforge/package/**`
- [ ] Use selected final candidate files
- [ ] Default to copy, not move
- [ ] Never silently overwrite user files
- [ ] Generate `PACKAGE_REPORT.md`
- [ ] Include missing items and conflicts in report when available
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
- [ ] Expose `detect_conflicts`, `extract_requirements`, and `build_package` through shared contracts
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
- [x] Verify current missing Agent API returns real `404` in Real Mode

### Phase B7 — Demo Dataset / Presentation
- [ ] Build or curate `demo/sample_workspace/`
- [ ] Include requirement document
- [ ] Include several relevant materials
- [ ] Include unrelated files
- [ ] Include multiple versions of one material
- [ ] Include at least one deliberate cross-document conflict
- [ ] Include at least one missing required material
- [ ] Prepare a stable demo flow and backup screenshots/recording

## 5. Integration Milestones

### Milestone 1 — Base Project Works
- [x] FileForge base code integrated
- [ ] All four developers can launch project locally
- [ ] Shared demo workspace works on all machines

### Milestone 2 — Independent Core Modules Work
- [ ] Developer A: Agent Core + HTTP API works against shared contracts
- [ ] Developer C: multi-format parser produces normalized documents
- [ ] Developer C: version grouping works on demo data
- [ ] Developer D: conflict / requirement tools work independently
- [x] Developer B: Frontend Agent Workspace works with mock data and Real Mode adapter

### Milestone 3 — Backend Tool Integration Works
- [ ] Agent can call Developer C/D analysis tools through shared contracts
- [ ] `read_document` works end-to-end for MVP formats
- [ ] `compare_versions` works end-to-end
- [ ] `detect_conflicts` works end-to-end
- [ ] `extract_requirements` works end-to-end
- [ ] `build_package` produces valid planned operations / results

### Milestone 4 — Frontend / Backend Integration Works
- [ ] Frontend can submit a natural-language task to real Agent API
- [ ] Frontend can display backend Plan and task status
- [ ] Frontend can display real version / conflict / missing-item results
- [ ] Frontend can submit approval / rejection with `preview_id`
- [ ] Frontend can display real `FinalReport`

### Milestone 5 — Safe Execution Works
- [ ] Approval gate shown before file-changing operations
- [ ] Package generation works
- [ ] Verification works
- [ ] No automatic deletion or overwrite is possible

### Milestone 6 — Demo Ready
- [ ] Primary demo prompt succeeds consistently
- [ ] Frontend shows understandable progress
- [ ] Failure cases produce readable errors
- [ ] Demo backup recording prepared

## 6. Primary Demo Prompt

> 帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，最后生成一个报名资料包。执行文件操作前先让我确认。

## 7. Cut Scope Rules

If schedule slips, cut in this order:
1. OCR
2. MCP integration
3. rich semantic diff visualization
4. multi-field conflict extraction → keep deadline / required-material conflict only
5. advanced UI polish

Do **not** cut:
- natural-language task input
- Planner
- Tool Calling
- Approval Gate
- real file operations
- one complete end-to-end demo flow

## 8. Daily Collaboration Checklist

Before coding:
- [ ] Pull latest `dev`
- [ ] Merge `dev` into your assigned feature branch
- [ ] Read shared contract changes
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
- [ ] Demo behavior is not broken
