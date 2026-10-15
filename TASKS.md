# TASKS.md

This file tracks the MVP development plan for the three-developer Vibe Coding workflow.

## 0. Shared Setup

- [x] Create shared GitHub repository
- [x] Create `dev` integration branch
- [x] Create `feature/agent-core`
- [x] Create `feature/document-intelligence`
- [x] Create `feature/frontend`
- [x] Add shared collaboration rules
- [x] Add architecture definition
- [x] Add API contract
- [x] Import / integrate FileForge base code
- [ ] All three developers run the original project successfully
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
- [ ] Support approve-all / reject behavior for MVP
- [ ] Ensure delete/overwrite are impossible through public tools

### Phase A5 — Verification
- [ ] Re-scan destination after execution
- [ ] Check expected package contents
- [ ] Check archive operations when used
- [ ] Produce verification output for `FinalReport`

### Phase A6 — Agent API
- [ ] Natural-language task endpoint
- [ ] Plan preview endpoint
- [ ] Approval / execution endpoint
- [ ] Task status endpoint
- [ ] Final report endpoint

## 2. Developer C — Document Intelligence / Backend Tools

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
- [ ] Verify the multi-format implementation on Windows

TXT was merged in PR #2. The additional formats above are implemented and tested
locally on Linux; no new PR or integration milestone is claimed by these checks.
C1 is not declared fully accepted: Windows multi-format verification remains
outstanding, and supported content is explicitly limited by
[extraction scope](API_CONTRACT.md#read_document-extraction-scope). DOCX tables,
OCR and formula calculation are not implicitly covered by checked format items.
All formats follow the existing
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
- [ ] Identify newest candidate
- [ ] Produce semantic change summary
- [ ] Add version-analysis tests

### Phase C3 — Conflict Detection
- [ ] Extract important fields from requirement documents
- [ ] Detect inconsistent values across documents
- [ ] Return source file for each conflicting value
- [ ] Avoid automatically declaring one source correct
- [ ] Add conflict-detection tests

### Phase C4 — Requirement Extraction
- [ ] Extract required material checklist
- [ ] Match checklist items against local candidate files
- [ ] Report missing items
- [ ] Add requirement-extraction tests

### Phase C5 — Package Builder
- [ ] Select final candidate files
- [ ] Prepare package operations through shared tool contracts
- [ ] Never silently overwrite
- [ ] Generate `PACKAGE_REPORT.md`
- [ ] Include missing items and conflicts in report
- [ ] Return `ToolResult`

### Phase C6 — Integration Contract
- [ ] Expose `compare_versions` behavior through shared contract
- [ ] Expose `detect_conflicts` behavior through shared contract
- [ ] Expose `extract_requirements` behavior through shared contract
- [ ] Expose `build_package` behavior through shared contract
- [ ] Ensure Developer A can call these capabilities without importing internal implementation details

## 3. Developer B — Frontend / Product Experience

Branch: `feature/frontend`

### Phase B1 — Analyze and Reuse Existing Frontend
- [ ] Inspect `frontend/`
- [ ] Identify existing UI structure and API-call pattern
- [ ] Identify reusable file-list / status / action UI
- [ ] Produce frontend migration plan before large edits
- [ ] Do not replace the frontend stack unless explicitly approved

### Phase B2 — Agent Workspace Skeleton
- [ ] Add natural-language task input
- [ ] Show selected workspace
- [ ] Add Run / Analyze action
- [ ] Add Agent Plan / progress area
- [ ] Add visible loading and error states

### Phase B3 — Analysis Result UI
- [ ] Show version groups
- [ ] Mark latest version candidate
- [ ] Show semantic-change summary when available
- [ ] Show conflict warnings and source files
- [ ] Show required / missing material checklist

### Phase B4 — Approval and Execution UI
- [ ] Show pending file-operation preview
- [ ] Show create/copy/move/archive operations clearly
- [ ] Add approve-all / cancel controls for MVP
- [ ] Never execute local file operations directly from frontend code

### Phase B5 — Final Result UI
- [ ] Show task completion state
- [ ] Show found / missing / conflict summary
- [ ] Show final package path
- [ ] Add Open Folder only if backend supports it; otherwise show/copy path

### Phase B6 — Mock Mode
- [ ] Build mock data using the exact `API_CONTRACT.md` field names
- [ ] Cover task-created state
- [ ] Cover planner-returned state
- [ ] Cover version-analysis state
- [ ] Cover conflict state
- [ ] Cover waiting-approval state
- [ ] Cover completed state

### Phase B7 — Demo Dataset / Presentation
- [ ] Build or curate `demo/sample_workspace/`
- [ ] Include requirement document
- [ ] Include several relevant materials
- [ ] Include unrelated files
- [ ] Include multiple versions of one material
- [ ] Include at least one deliberate cross-document conflict
- [ ] Include at least one missing required material
- [ ] Prepare a stable demo flow and backup screenshots/recording

## 4. Integration Milestones

### Milestone 1 — Base Project Works
- [x] FileForge base code integrated
- [ ] All three developers can launch project locally
- [ ] Shared demo workspace works on all machines

### Milestone 2 — Independent Core Modules Work
- [ ] Developer A: Agent can generate a structured plan
- [ ] Developer C: Document parser produces normalized documents
- [ ] Developer C: Version grouping works on demo data
- [ ] Developer B: Frontend Agent Workspace works with mock data

### Milestone 3 — Backend Tool Integration Works
- [ ] Agent can call Developer C analysis tools through shared contracts
- [ ] `compare_versions` works end-to-end
- [ ] `detect_conflicts` works end-to-end
- [ ] `extract_requirements` works end-to-end
- [ ] `build_package` produces valid planned operations / results

### Milestone 4 — Frontend / Backend Integration Works
- [ ] Frontend can submit a natural-language task
- [ ] Frontend can display backend Plan and task status
- [ ] Frontend can display version / conflict / missing-item results
- [ ] Frontend can submit approval / rejection

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

## 5. Primary Demo Prompt

> 帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，最后生成一个报名资料包。执行文件操作前先让我确认。

## 6. Cut Scope Rules

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

## 7. Daily Collaboration Checklist

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
- [ ] At least one other developer reviews
- [ ] Shared API changes are reflected in `API_CONTRACT.md`
- [ ] Tests / checks pass
- [ ] Demo behavior is not broken
