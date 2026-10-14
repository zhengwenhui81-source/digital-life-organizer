# TASKS.md

This file tracks the MVP development plan for the two-developer Vibe Coding workflow.

## 0. Shared Setup

- [x] Create shared GitHub repository
- [x] Create `dev` integration branch
- [x] Create `feature/agent-core`
- [x] Create `feature/document-intelligence`
- [x] Add shared collaboration rules
- [x] Add architecture definition
- [x] Add API contract
- [ ] Import / integrate FileForge base code
- [ ] Both developers run the original project successfully
- [ ] Create a shared demo workspace with non-sensitive test files
- [ ] Confirm Python / Node / package-manager versions

## 1. Developer A — Agent Core

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

## 2. Developer B — Document Intelligence & Product Integration

Branch: `feature/document-intelligence`

### Phase B1 — Demo Dataset
- [ ] Build `demo/sample_workspace/`
- [ ] Include requirement document
- [ ] Include several relevant materials
- [ ] Include unrelated files
- [ ] Include multiple versions of one material
- [ ] Include at least one deliberate cross-document conflict
- [ ] Include at least one missing required material

### Phase B2 — Document Parser
MVP priority:
- [ ] TXT
- [ ] PDF
- [ ] DOCX
- [ ] XLSX
- [ ] Normalize parsed output to `Document`
- [ ] Add unsupported-format handling
- [ ] Add parser tests

Optional later:
- [ ] OCR / image text extraction

### Phase B3 — Version Intelligence
- [ ] Filename normalization
- [ ] Candidate version grouping
- [ ] Use modified time / metadata as signals
- [ ] Add content similarity as second-stage validation
- [ ] Identify newest candidate
- [ ] Produce semantic change summary
- [ ] Add version-analysis tests

### Phase B4 — Conflict Detection
- [ ] Extract important fields from requirement documents
- [ ] Detect inconsistent values across documents
- [ ] Return source file for each conflicting value
- [ ] Avoid automatically declaring one source correct
- [ ] Add conflict-detection tests

### Phase B5 — Requirement Extraction
- [ ] Extract required material checklist
- [ ] Match checklist items against local candidate files
- [ ] Report missing items
- [ ] Add requirement-extraction tests

### Phase B6 — Package Builder
- [ ] Select final candidate files
- [ ] Copy files into task package
- [ ] Never silently overwrite
- [ ] Generate `PACKAGE_REPORT.md`
- [ ] Include missing items and conflicts in report
- [ ] Return `ToolResult`

### Phase B7 — Frontend Integration
- [ ] Add natural-language task input
- [ ] Show generated plan
- [ ] Show execution progress
- [ ] Show version groups / conflicts
- [ ] Show approval controls
- [ ] Show missing items
- [ ] Show final package / report

## 3. Integration Milestones

### Milestone 1 — Base Project Works
- [ ] FileForge base code integrated
- [ ] Both developers can launch project locally
- [ ] Shared demo workspace works on both machines

### Milestone 2 — Independent Core Modules Work
- [ ] Agent can generate a structured plan
- [ ] Document parser produces normalized documents
- [ ] Version grouping works on demo data

### Milestone 3 — Tool Integration Works
- [ ] Agent can call Developer B analysis tools through shared contracts
- [ ] `compare_versions` works end-to-end
- [ ] `detect_conflicts` works end-to-end
- [ ] `extract_requirements` works end-to-end

### Milestone 4 — Safe Execution Works
- [ ] Approval gate shown before file-changing operations
- [ ] Package generation works
- [ ] Verification works

### Milestone 5 — Demo Ready
- [ ] Primary demo prompt succeeds consistently
- [ ] No automatic deletion or overwrite possible
- [ ] Frontend shows understandable progress
- [ ] Failure cases produce readable errors
- [ ] Demo backup recording prepared

## 4. Primary Demo Prompt

> 帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，最后生成一个报名资料包。执行文件操作前先让我确认。

## 5. Cut Scope Rules

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

## 6. Daily Collaboration Checklist

Before coding:
- [ ] Pull latest `dev`
- [ ] Merge `dev` into your feature branch
- [ ] Read shared contract changes
- [ ] Choose one small task

Before pushing:
- [ ] Run relevant tests
- [ ] Review `git diff`
- [ ] Confirm no other developer-owned files were changed accidentally
- [ ] Commit with a focused message
- [ ] Push feature branch

Before merging PR:
- [ ] Other developer reviews
- [ ] Shared API changes are reflected in `API_CONTRACT.md`
- [ ] Tests pass
- [ ] Demo behavior is not broken
