# AGENTS.md

This file defines collaboration rules for all human developers and AI coding agents working in this repository.

## 1. Project Scope

Digital Life Organizer is a task-driven local AI file agent.

The MVP workflow is:

User Goal → Plan → Search → Document Analysis → Version/Conflict Detection → Action Plan → User Approval → File Operations → Verification → Final Package

The project is based on an existing file-management codebase and should reuse working upstream functionality whenever possible.

## 2. Code Ownership

### Developer A — Agent Core / Backend Orchestration

Branch: `feature/agent-core`

Owns:
- `src/fileforge/agent/**`
- `src/fileforge/tools/**`
- agent-related backend APIs
- agent tests

Responsible for:
- Planner
- Tool Calling / Tool Router
- Executor
- Approval Gate
- Verification
- task state and execution flow
- Agent API endpoints

Developer A decides **what to do and in what order**. Developer A should call shared intelligence tools rather than reimplementing their algorithms.

Must not modify Developer B, C or D owned paths unless explicitly agreed.

### Developer B — Frontend / Product Experience

Branch: `feature/frontend`

Owns:
- `frontend/**`
- `demo/**`
- frontend mock data and UI integration code

Responsible for:
- Agent workspace UI
- natural-language task input
- plan/progress display
- version/conflict/missing-item presentation
- approval controls
- final result/package presentation
- loading/error states
- frontend API integration
- demo presentation data

Developer B does not implement Agent Core or backend analysis algorithms.

Must not modify Developer A, C or D owned paths unless explicitly agreed.

### Developer C — Document Parsing & Version Intelligence

Branch: `feature/document-intelligence`

Owns:
- `src/fileforge/document/**`
- document-parser and version-intelligence tests

Responsible for:
- document parsing and normalization
- TXT / PDF / DOCX / XLSX reading
- path-based `Document.file_id`
- version grouping and comparison
- newest-candidate selection
- semantic change summaries
- `read_document` and `compare_versions` ToolResult outputs

Developer C decides **what a file contains and how multiple versions of the same material relate**. Developer C does not control Agent planning, task-level conflict/requirement interpretation, package generation or execution order.

Must not modify Developer A, B or D owned paths unless explicitly agreed.

### Developer D — Task Intelligence / Package Builder

Branch: `feature/task-intelligence`

Owns:
- `src/fileforge/task_intelligence/**`
- `src/fileforge/package/**`
- conflict / requirement / package-related tests

Responsible for:
- conflict detection across parsed documents
- requirement extraction from task/notice documents
- required / matched / missing material analysis
- task-oriented package selection logic
- package generation logic
- `detect_conflicts`, `extract_requirements`, and `build_package` ToolResult outputs

Developer D decides **what the parsed files mean for the user's current task and how selected results become a final package**. Developer D does not control Agent orchestration or frontend presentation.

Must not modify Developer A, B or C owned paths unless explicitly agreed.

## 3. Shared Interfaces

The following are shared contracts and may not be renamed or changed unilaterally:
- Task
- Plan
- PlanStep
- Document
- ToolResult
- TaskSnapshot
- FinalReport
- public tool names
- API request/response payloads

Any shared-interface change must be reflected in `API_CONTRACT.md` first and agreed by the team before implementation.

Confirmed collaboration decisions must also be reflected in this `AGENTS.md` and relevant architecture, task, or usage documentation. Keep complete interface rules in `API_CONTRACT.md`; other documents should link to them rather than maintain duplicate specifications. Mark only implemented and verified task scope as complete.

Document identity follows the confirmed [path-based Document identity contract](API_CONTRACT.md#path-based-document-identity). The document-reading layer owns ID generation; callers use `read_document(path)` without supplying an ID. IDs identify normalized paths, so consumers must not assume identity survives moving or renaming a file or changing environments.

Parser support and omissions are defined in
[read_document extraction scope](API_CONTRACT.md#read_document-extraction-scope).
TXT, PDF text layers, DOCX body paragraphs/tables, and XLSX cached cell values share the
same Document/ToolResult and ID rules. Do not infer complete Office extraction,
OCR, formula evaluation, or XLSM support from the supported extension list.

Confirmed [Document collection rules](API_CONTRACT.md#shared-document-collection-rules)
apply to every public Document[] consumer, including C's version comparison and
D's conflict/requirement/matching tools. B renders ToolResult without inventing
another identity policy. D owns adaptation and tests of its existing tools.
The [compare_versions v1 contract](API_CONTRACT.md#compare_versions) is confirmed;
the public C implementation/export is verified on Linux, with fixed-commit Windows
unit/lifecycle and four-format C-tool pipeline evidence reconciled in
[the validation record](docs/version-windows-validation.md). Default Agent routing
and scoped Linux integration are checked in the
[C/A record](docs/c-agent-integration-validation.md); full integration acceptance
remains separate and pending. Unknown Workspaces need not contain versions; controlled fixtures are for
acceptance tests, not a runtime or classroom prerequisite.

Integration boundaries:
- Developer A consumes C and D capabilities through shared public tool contracts.
- Developer C and Developer D may exchange only contract-shaped data or explicitly agreed internal inputs; neither should depend on the other's private implementation details.
- Developer B consumes the stable backend API and must not invent a second set of shared field names for Real Mode.
- Mock-only frontend structures may exist only when clearly isolated from the real API contract.

## 4. AI Coding Rules

Before editing code, every AI coding agent must:
1. Read `AGENTS.md`.
2. Read `ARCHITECTURE.md`.
3. Read `API_CONTRACT.md`.
4. Read `TASKS.md`.
5. Inspect the existing implementation before creating new modules.
6. State which files it plans to modify.

During implementation:
1. Reuse existing FileForge functionality whenever possible.
2. Do not rewrite working upstream modules without a concrete reason.
3. Do not modify files owned by another developer unless explicitly requested.
4. Do not rename public interfaces without approval.
5. Do not add dependencies unless necessary.
6. Do not perform broad refactors while implementing a feature.
7. Keep changes minimal and scoped to the requested task.
8. Add or update tests for new backend logic.
9. Frontend Real Mode must follow `API_CONTRACT.md`; mock-only data must remain clearly isolated.

After implementation:
1. Run relevant tests or frontend checks.
2. List changed files.
3. Explain why each file changed.
4. Report any shared-interface/API changes.
5. Report failing tests honestly.

## 5. Forbidden Automatic File Operations

For the MVP:
- Reading, scanning, searching, comparing and analyzing may run automatically.
- Creating folders, copying, moving, renaming and archiving require user approval before execution.
- Deleting and overwriting user files are forbidden.
- Old versions must be archived, not deleted.
- Package generation may plan/calculate outputs before approval, but real filesystem changes must still pass through Developer A's backend Approval Gate.

## 6. Architecture Guardrails

Do not independently:
- replace the base framework
- migrate the frontend stack
- replace SQLite
- introduce microservices
- introduce Docker as a required runtime
- change the top-level directory structure
- introduce a multi-agent architecture for the MVP

## 7. Branching Rules

Primary branches:
- `main`: stable milestone/demo branch
- `dev`: integration branch
- `feature/agent-core`: Developer A
- `feature/frontend`: Developer B
- `feature/document-intelligence`: Developer C
- `feature/task-intelligence`: Developer D

Workflow:
1. Work on your assigned feature branch.
2. Commit small, focused changes.
3. Push only your assigned feature branch during normal development.
4. Open a pull request into `dev` after a coherent feature or milestone is ready.
5. The pull request must receive at least one independent review before merge. The reviewer may be another human developer or a designated AI reviewer with repository access. A designated AI review counts when it inspects the current PR HEAD/diff, checks repository rules and shared contracts, and explicitly reports whether blocking issues exist. No additional human review is required unless the AI review requests changes or the team explicitly asks for one.
6. Merge `dev` into `main` only for stable milestones.

### Review Policy

- ChatGPT with connected GitHub repository access is an approved designated AI reviewer for this project.
- A ChatGPT review may satisfy the required independent PR review by itself.
- The review must be based on the PR's current HEAD, not an obsolete commit.
- The review should check scope/ownership, `AGENTS.md`, `API_CONTRACT.md`, relevant tests/checks, safety boundaries, and integration compatibility.
- If the PR changes after the review in a way that materially affects reviewed code or contracts, review the updated HEAD again before merge.
- The PR author does not need to seek an additional human approval after a non-blocking designated AI review.

### Direct Push Restrictions

- Direct pushes to `main` and `dev` are forbidden for normal development.
- Developer A must develop and push only on `feature/agent-core` unless the team explicitly agrees otherwise.
- Developer B must develop and push only on `feature/frontend` unless the team explicitly agrees otherwise.
- Developer C must develop and push only on `feature/document-intelligence` unless the team explicitly agrees otherwise.
- Developer D must develop and push only on `feature/task-intelligence` unless the team explicitly agrees otherwise.
- All normal feature integration must go through Pull Requests into `dev`.
- `main` may only receive stable milestone/demo changes from `dev`.
- AI coding agents must never switch to, commit to, or push directly to `main` or `dev` as part of normal feature work.

## 8. Commit Convention

Examples:
- `feat(agent): add structured planner`
- `feat(tools): wrap file search tool`
- `feat(document): add normalized parser`
- `feat(version): add version grouping`
- `feat(task): add conflict detection`
- `feat(requirements): add material matching`
- `feat(package): add package builder`
- `feat(frontend): add agent workspace`
- `fix(agent): handle failed tool call`
- `test(version): add version grouping cases`
- `docs(api): update tool contract`

## 9. External Reference Projects

The only upstream codebase currently integrated into this repository is FileForge.

### FileForge

FileForge is the actual codebase used as the project foundation. All developers should reuse existing FileForge functionality before creating replacements.

### AI-File-Organizer-Agent

Reference-only, primarily for Developer A.

Use as a reference for:
- Agent planning flow
- plan preview
- user approval before file operations
- tool-calling workflow
- Plan → Approve → Execute interaction pattern

Do NOT:
- copy the entire project into this repository
- replace the existing FileForge architecture with it
- introduce its dependencies unless a specific feature requires them

### Cairn

Reference-only, primarily for Developer A.

Use as a reference for:
- file tool interface design
- semantic file search patterns
- MCP-style filesystem tools
- read/search/move/tag tool abstractions

Do NOT:
- migrate Cairn wholesale
- introduce MCP as a mandatory MVP dependency
- replace existing FileForge file operations when they can be reused

### Developer B

Developer B does not need to study or integrate AI-File-Organizer-Agent or Cairn for frontend work.

Developer B should primarily rely on:
- existing FileForge frontend
- `API_CONTRACT.md`
- backend APIs implemented by Developer A
- analysis results exposed through the shared backend contract

### Developer C

Developer C should primarily study and reuse FileForge extractors and analysis modules relevant to document parsing and version intelligence. AI-File-Organizer-Agent and Cairn are optional references, not required dependencies.

### Developer D

Developer D should primarily study existing FileForge analysis/action capabilities that can support task-level conflict, requirement and package logic. Package filesystem mutations must still be executed through approved public tools rather than bypassing the Agent approval layer.

## 8. Package validation delegation (2026-10-20)

The team lead delegates **independent Package verification tests, temporary-file fixtures, and test evidence** to Developer C to reduce Developer A's integration workload. This is a limited **testing/acceptance ownership exception**, not a transfer of production module ownership.

- **A retains exclusive production ownership** of `src/fileforge/agent/**`, including authoritative TaskService evidence collection, Package preview/approval, post-approval checks, filesystem mutations, cleanup_results recording, FinalReport and HTTP behavior.
- **D retains** `src/fileforge/package/**`, including the read-only `plan_package` implementation. **B retains** `frontend/**` and Windows Real Mode/browser acceptance.
- **C owns the supplementary cross-module Package test scenarios, fixtures and validation records**: full Document/source revalidation, analysis provenance, A/D source snapshot mismatch, partial/failed copies and cleanup outcomes, Package vs non-Package report invariants, and eventual public-interface integration with Document/Version. Use separate C-authored test files and coordinate any edits to A/D-owned existing test files; never modify A/D production modules without explicit agreement.
- C must not invent unimplemented approval/execution APIs or claim that fixtures, read-only helper tests, or accepted contracts prove actual Package execution. Mark future-API cases as pending, or skip explicitly with reasons; only implemented public behavior may be counted as passing.
- Existing `API_CONTRACT.md` and its strict Package evidence, approval, and cleanup semantics are unchanged. New shared field names or endpoint changes still require full team review and a separate contract PR.
- A and D provide C with public interfaces and authoritative index/error/409 expectations; C independently tests them. Keep PRs focused, reviewable and targeted at `dev`.

## 10. Workflow 2 — Smart Folder Organization Ownership (2026-10-21)

This section is the current, approved **delivery scope and module-ownership allocation** for the second workflow. It supersedes only conflicting earlier Workflow 2 allocations; it does not transfer ownership of Workflow 1 Package code or override any existing safety/PR rules.

- **C (primary development owner, target ~45% of Workflow 2 work):** implement the organization-only read-only directory/operation planner, safe Windows destination/path/collision analysis, and reusable filesystem create/copy/byte-verification components **only at integration seams and source paths agreed with A**. C owns tests for these components. C must not wire any filesystem write directly to an HTTP/UI endpoint or bypass TaskService, frozen preview, approval, or A's execution gate. Reuse existing A low-level tools whenever suitable; do not create a second independent executor. Any A-owned source edit needs A's explicit agreement and a narrowly scoped PR.
- **D (~25%):** own the minimal classification contract proposal and conservative content/evidence-based classifier, with abstention and unsupported/uncertain states. D does not control writes.
- **A (~15% of incremental Workflow 2 work):** own Agent/ToolRouter/TaskService integration, authoritative task/source/preview binding, user approval, orchestration and the only production write-entry point. A remains owner of Workflow 1 Package execution and its existing safety responsibilities.
- **B (~15%):** own real organization-mode UI, user correction/confirmation, frozen preview, execution/report display and Windows acceptance; no frontend filesystem mutation.
- C-authored PRs require review by A or B (not C's self-approval). A/B/D work is independently reviewed under the existing PR rules. Shared APIs and crossed code ownership need agreement **before** implementation.

**Required outcome:** in a user-selected real Workspace, after an explicit user-approved frozen preview, create `整理结果/` within that Workspace, derive useful category subfolders from evidence, **copy** selected files (no move/delete/overwrite), retain every original, exclude the output subtree from later scans, and verify every reported successful copy byte-for-byte. Ambiguous classifications remain unexecuted until explicitly resolved by the user. The classifier accuracy goal is >=95% on a human-labeled set, reported alongside coverage; it is a target, not a measured achievement or unconditional guarantee.

**Contract gate:** the product behavior and ownership above are approved; `classify_files` field-level schema and any organization plan/executor interface are **not yet frozen or implemented**. D and C must draft minimal proposals, and A/B/C/D must jointly approve changes to `API_CONTRACT.md` before strict consumers implement them. Never infer a new public tool/endpoint from this allocation.
