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

Developer A decides **what to do and in what order**. Developer A should call shared document-intelligence tools rather than reimplementing their algorithms.

Must not modify Developer B or Developer C owned paths unless explicitly agreed.

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

Developer B does not implement Agent Core or document-analysis algorithms.

Must not modify Developer A or Developer C owned paths unless explicitly agreed.

### Developer C — Document Intelligence / Backend Tools

Branch: `feature/document-intelligence`

Owns:
- `src/fileforge/document/**`
- `src/fileforge/package/**`
- document-intelligence tests

Responsible for:
- document parsing and normalization
- version grouping and comparison
- semantic change summaries
- conflict detection
- requirement extraction
- missing-material matching
- package generation logic
- document-intelligence ToolResult outputs

Developer C decides **how a specific file-analysis task is performed**. Developer C does not control Agent planning or execution order.

Must not modify Developer A or Developer B owned paths unless explicitly agreed.

## 3. Shared Interfaces

The following are shared contracts and may not be renamed or changed unilaterally:
- Task
- Plan
- PlanStep
- Document
- ToolResult
- FinalReport
- public tool names
- API request/response payloads

Any shared-interface change must be reflected in `API_CONTRACT.md` first and agreed by the team before implementation.

Confirmed collaboration decisions must also be reflected in this `AGENTS.md`
and relevant architecture, task, or usage documentation. Keep complete interface
rules in `API_CONTRACT.md`; other documents should link to them rather than
maintain duplicate specifications. Mark only implemented and verified task scope
as complete.

Document identity follows the confirmed
[path-based Document identity contract](API_CONTRACT.md#path-based-document-identity).
The document-reading layer owns ID generation; callers use `read_document(path)`
without supplying an ID. IDs identify normalized paths, so consumers must not
assume identity survives moving or renaming a file or changing environments.

Developer A and Developer C must integrate through the shared tool contracts. Developer B consumes the stable backend API and must not invent a second set of field names for mock data.

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
9. Frontend mock data must follow `API_CONTRACT.md` exactly.

After implementation:
1. Run relevant tests or frontend checks.
2. List changed files.
3. Explain why each file changed.
4. Report any shared-interface/API changes.
5. Report failing tests honestly.

## 5. Forbidden Automatic File Operations

For the MVP:
- Reading, scanning, searching, comparing and analyzing may run automatically.
- Creating folders, copying, moving and renaming require user approval before execution.
- Deleting and overwriting user files are forbidden.
- Old versions must be archived, not deleted.

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

Workflow:
1. Work on your assigned feature branch.
2. Commit small, focused changes.
3. Push only your assigned feature branch during normal development.
4. Open a pull request into `dev` after a coherent feature or milestone is ready.
5. At least one other developer reviews before merge.
6. Merge `dev` into `main` only for stable milestones.

### Direct Push Restrictions

- Direct pushes to `main` and `dev` are forbidden for normal development.
- Developer A must develop and push only on `feature/agent-core` unless the team explicitly agrees otherwise.
- Developer B must develop and push only on `feature/frontend` unless the team explicitly agrees otherwise.
- Developer C must develop and push only on `feature/document-intelligence` unless the team explicitly agrees otherwise.
- All normal feature integration must go through Pull Requests into `dev`.
- `main` may only receive stable milestone/demo changes from `dev`.
- AI coding agents must never switch to, commit to, or push directly to `main` or `dev` as part of normal feature work.

## 8. Commit Convention

Examples:
- `feat(agent): add structured planner`
- `feat(tools): wrap file search tool`
- `feat(document): add normalized parser`
- `feat(version): add version grouping`
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
- document-analysis results exposed through the shared backend contract

### Developer C

Developer C should primarily study and reuse FileForge extractors, analysis modules and file actions relevant to document intelligence. AI-File-Organizer-Agent and Cairn are optional references, not required dependencies for Developer C.
