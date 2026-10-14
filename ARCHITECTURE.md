# ARCHITECTURE.md

## 1. Product Goal

Digital Life Organizer is a **task-driven local AI file agent**.

It is not merely an automatic file classifier. The system accepts a natural-language goal and autonomously plans and executes a multi-step file task with user approval for risky operations.

Core flow:

```text
User Goal
   ↓
Planner
   ↓
Search / Scan
   ↓
Document Intelligence
   ↓
Version & Conflict Analysis
   ↓
Action Plan
   ↓
User Approval
   ↓
File Operations
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

## 3. High-Level Modules

```text
Digital Life Organizer
│
├── Frontend
│   ├── natural-language task input
│   ├── plan/progress display
│   ├── conflict/version display
│   ├── approval UI
│   └── final result display
│
├── Agent Layer
│   ├── Planner
│   ├── Tool Router
│   ├── Executor
│   ├── Approval Gate
│   └── Verifier
│
├── Document Intelligence
│   ├── Document Parser
│   ├── Version Detector
│   ├── Version Diff
│   ├── Conflict Detector
│   ├── Requirement Extractor
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

### Agent Core
Responsible for deciding **what to do next**.

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

### Document Intelligence
Responsible for understanding **what the files mean**.

Inputs:
- file paths / parsed documents

Outputs:
- normalized document content
- version groups
- semantic differences
- conflicts
- requirement checklist
- package generation results

## 5. Risk Model

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

### MEDIUM
Requires approval:
- create folder
- copy
- move
- rename
- archive

### HIGH
Forbidden in MVP:
- delete
- overwrite
- destructive batch modification

## 6. MVP Demo Scenario

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

## 7. Non-Goals for First MVP

Do not prioritize:
- multi-agent orchestration
- OCR-heavy image understanding
- full-disk lifelong memory
- perfect Office format support
- cloud deployment
- advanced permissions system
- autonomous destructive actions
- complex real-time background monitoring

## 8. Future Extensions

Possible later additions:
- MCP server exposing file tools
- richer semantic search
- operation history and undo
- optional cloud model providers
- OCR and screenshot understanding
- personal memory across tasks
- multi-agent specialization
