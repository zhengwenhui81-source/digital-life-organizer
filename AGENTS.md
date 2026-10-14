# AGENTS.md

This file defines collaboration rules for all human developers and AI coding agents working in this repository.

## 1. Project Scope

Digital Life Organizer is a task-driven local AI file agent.

The MVP workflow is:

User Goal → Plan → Search → Document Analysis → Version/Conflict Detection → Action Plan → User Approval → File Operations → Verification → Final Package

The project is based on an existing file-management codebase and should reuse working upstream functionality whenever possible.

## 2. Code Ownership

### Developer A — Agent Core
Owns:
- `src/fileforge/agent/**`
- `src/fileforge/tools/**`
- agent-related backend APIs
- agent tests

Responsible for:
- Planner
- Tool Calling
- Executor
- Approval Gate
- Verification
- task state and execution flow

Must not modify Developer B owned paths unless explicitly agreed.

### Developer B — Document Intelligence & Product Integration
Owns:
- `src/fileforge/document/**`
- `src/fileforge/package/**`
- `frontend/**`
- `demo/**`

Responsible for:
- document parsing
- version grouping and comparison
- conflict detection
- requirement extraction
- package generation
- frontend integration and demo data

Must not modify Developer A owned paths unless explicitly agreed.

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

Any shared-interface change must be reflected in `API_CONTRACT.md` first and agreed by both developers.

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
3. Do not modify files owned by the other developer unless explicitly requested.
4. Do not rename public interfaces without approval.
5. Do not add dependencies unless necessary.
6. Do not perform broad refactors while implementing a feature.
7. Keep changes minimal and scoped to the requested task.
8. Add or update tests for new logic.

After implementation:
1. Run relevant tests.
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
- `feature/document-intelligence`: Developer B

Workflow:
1. Work on your assigned feature branch.
2. Commit small, focused changes.
3. Push the branch.
4. Open a pull request into `dev`.
5. The other developer reviews before merge.
6. Merge `dev` into `main` only for stable milestones.

## 8. Commit Convention

Examples:
- `feat(agent): add structured planner`
- `feat(document): add docx parser`
- `feat(version): add version grouping`
- `feat(package): add package builder`
- `fix(agent): handle failed tool call`
- `test(version): add version grouping cases`
- `docs(api): update tool contract`
