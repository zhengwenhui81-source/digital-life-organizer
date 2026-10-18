# ARCHITECTURE.md

## 1. Product Goal

Digital Life Organizer is a **task-driven local AI file agent**.

It is not merely an automatic file classifier. The system accepts a natural-language goal and autonomously plans and executes a multi-step file task with user approval for risky operations.

Core flow:

```text
User Goal
   ↓
Frontend Task Workspace
   ↓
Agent Core
   ↓
Planner / Tool Routing
   ↓
Document Parsing + Version Intelligence
   ↓
Task Intelligence
   ↓
Version / Conflict / Requirement Analysis
   ↓
Action Plan
   ↓
User Approval
   ↓
File Operations / Package Builder
   ↓
Verification
   ↓
Final Package / Report
```

## 2. MVP Principles

1. Local-first.
2. Reuse FileForge capabilities before writing replacements.
3. Single-agent architecture for the MVP.
4. All file changes go through explicit tool interfaces.
5. Medium/high-risk operations require user approval.
6. No automatic delete or overwrite.
7. Focus on one stable end-to-end demo before adding optional features.
8. Prefer explainable intermediate results over hidden autonomous behavior.
9. Keep Frontend, Agent Orchestration, Document/Version Intelligence, and Task Intelligence as separate responsibilities connected through shared contracts.

## 3. High-Level Modules

```text
Digital Life Organizer
│
├── Frontend / Product Experience
│   ├── natural-language task input
│   ├── plan/progress display
│   ├── conflict/version display
│   ├── approval UI
│   ├── loading/error handling
│   └── final result display
│
├── Agent Core / Orchestration
│   ├── Planner
│   ├── Tool Router
│   ├── Executor
│   ├── Approval Gate
│   └── Verifier
│
├── Document Parsing & Version Intelligence
│   ├── Document Parser
│   ├── TXT / PDF / DOCX / XLSX readers
│   ├── Version Detector
│   ├── Version Diff
│   └── Newest Candidate Selection
│
├── Task Intelligence / Package Builder
│   ├── Conflict Detector
│   ├── Requirement Extractor
│   ├── Missing Material Matcher
│   ├── Candidate Selection Logic
│   └── Package Builder
│
├── File Tools / Existing FileForge Capabilities
│   ├── Scan
│   ├── Search
│   ├── Duplicate Detection
│   ├── Create Folder
│   ├── Copy
│   └── Move / Archive
│
└── Local File System / SQLite
```

## 4. Responsibility Split

### Developer A — Agent Core

Responsible for deciding **what to do next and in what order**.

Inputs:
- user goal
- workspace
- tool results

Outputs:
- structured plan
- tool calls
- approval request
- execution status
- verification result

Developer A owns orchestration, not the internal algorithms of C/D intelligence tools.

### Developer B — Frontend

Responsible for presenting **what the Agent is doing and what the user must decide**.

Inputs:
- Task / Plan / TaskSnapshot / ToolResult / FinalReport APIs

Outputs:
- task submission UI
- progress visualization
- version/conflict/missing-item cards
- approval interaction
- final package/report presentation

Developer B must not duplicate backend decision logic in the browser. Real Mode follows `API_CONTRACT.md`; mock-only structures must remain isolated.

### Developer C — Document Parsing & Version Intelligence

Responsible for understanding **what each file contains and how multiple files relate as versions of the same material**.

Inputs:
- file paths
- file metadata
- parsed document candidates

Outputs:
- normalized document content
- version groups
- newest candidate
- semantic version differences

Developer C exposes `read_document` / `compare_versions` behavior through shared contracts so Agent Core can call it without depending on private implementation details.

The document-reading layer generates path-based `Document.file_id` values as
specified in [API_CONTRACT.md](API_CONTRACT.md#path-based-document-identity).
This requires no file registry, database schema change, or extra Agent parameter.
Identity tracking across moves/renames is outside this first version. The current
public `fileforge.document.read_document(path)` dispatches TXT, PDF, DOCX and XLSX
to existing FileForge extractors, sharing path normalization, ID generation,
Document assembly and failure envelopes. It reads without the snippet default.
Extraction covers PDF text layers, DOCX body paragraphs and XLSX cached cell
values with sheet names; OCR, DOCX tables and spreadsheet calculation remain
outside scope. See [extraction scope](API_CONTRACT.md#read_document-extraction-scope)
for complete limitations. No second parser framework or identity service is added.

The [Version contract](API_CONTRACT.md#compare_versions) is now confirmed but
implemented/exported in C with Linux local verification; Windows Version and
Agent integration acceptance remain pending. It analyzes supplied Documents
from unknown Workspaces conservatively; no relationships is a normal success.
Comparison output never selects an approved final file or triggers operations.
Controlled version fixtures serve tests/regression/acceptance, not an assumption
about runtime inputs. No cancellation API, permanent worker service or whole-HTTP
hard deadline is introduced.

### Developer D — Task Intelligence / Package Builder

Responsible for understanding **what parsed/versioned files mean for the user's current task and how approved results become a final package**.

Inputs:
- normalized documents
- version-analysis results
- user task context
- extracted task requirements
- selected candidate files

Outputs:
- cross-document conflicts
- requirement checklist
- required / matched / missing material results
- package-generation result
- package report data

Developer D owns the algorithms behind `detect_conflicts`, `extract_requirements`, missing-material analysis and `build_package`. Developer D does not control Agent planning/execution order and must not bypass the Agent approval gate for real filesystem mutations.

## 5. Integration Direction

The intended dependency direction is:

```text
Frontend (Developer B)
        ↓ Agent HTTP API
Agent Core (Developer A)
        ↓ Public Tool Contract
 ┌───────────────────────────────┐
 │                               │
Document / Version (Developer C) Task Intelligence (Developer D)
 │                               │
 └──────── contract-shaped data ─┘
        ↓
FileForge / Local File System
```

More concretely:

```text
C: read_document / compare_versions
        ↓ ToolResult / Document / version groups
D: detect_conflicts / extract_requirements / build_package
        ↓ ToolResult
A: Planner / Executor / Approval / Verification
        ↓ TaskSnapshot / FinalReport
B: Frontend
```

Integration should preserve this direction. Avoid direct frontend dependencies on internal C/D modules. A should call public tools rather than import private analysis implementations. C and D should not reach into each other's private modules unless a shared boundary is explicitly agreed.

All public Document[] consumers use the confirmed
[collection identity rules](API_CONTRACT.md#shared-document-collection-rules).
C/D implement their own owned public-boundary adaptation against that contract;
no private cross-module dependency or frontend identity algorithm is required.
D must adapt existing detect_conflicts/extract_requirements and future public
matching; that work and its tests are not certified by contract publication.

## 6. Risk Model

### LOW
Can execute automatically:
- scan
- list
- search
- read
- parse
- compare
- analyze
- detect duplicates
- detect conflicts
- extract requirements

### MEDIUM
Requires approval before real filesystem change:
- create folder
- copy
- move
- rename
- archive
- package materialization when it creates/copies/moves files

### HIGH
Forbidden in MVP:
- delete
- overwrite
- destructive batch modification

## 7. MVP Demo Scenario

Primary demo prompt:

> 帮我准备生成式人工智能黑客松报名资料。根据比赛通知找到需要提交的文件，同一材料如果有多个版本选择最新版本，检查不同通知有没有冲突，缺少的材料告诉我，最后生成一个报名资料包。执行文件操作前先让我确认。

Expected flow:
1. Read competition requirement files.
2. Extract required materials.
3. Search relevant local files.
4. Group multiple versions of the same material.
5. Compare versions and choose the newest candidate.
6. Detect conflicting information across documents.
7. Identify missing required materials.
8. Generate a proposed action plan.
9. Request approval.
10. Copy selected files into a task package.
11. Archive old versions only if explicitly approved.
12. Verify the package and produce a final report.

## 8. Non-Goals for First MVP

Do not prioritize:
- multi-agent orchestration
- OCR-heavy image understanding
- full-disk lifelong memory
- perfect Office format support
- cloud deployment
- advanced permissions system
- autonomous destructive actions
- complex real-time background monitoring

## 9. Future Extensions

Possible later additions:
- MCP server exposing file tools
- richer semantic search
- operation history and undo
- optional cloud model providers
- OCR and screenshot understanding
- personal memory across tasks
- multi-agent specialization
