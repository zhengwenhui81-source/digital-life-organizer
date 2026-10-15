# API_CONTRACT.md

This document defines shared data structures, public tool contracts, and the MVP Agent HTTP API. These interfaces may not be changed unilaterally.

## 1. Core Data Models

### Task

```json
{
  "task_id": "task_001",
  "user_goal": "帮我准备黑客松报名资料",
  "workspace": "D:/demo_workspace",
  "status": "created"
}
```

Allowed `status` values for MVP:
- `created`
- `planning`
- `awaiting_approval`
- `executing`
- `verifying`
- `completed`
- `failed`

Notes:
- user rejection does not introduce a new Task status in the MVP; the Task becomes `failed`
- the frontend should distinguish a user rejection from a system/tool failure in its displayed message when that context is available

### Plan

```json
{
  "task_id": "task_001",
  "goal": "帮我准备黑客松报名资料",
  "steps": [
    {
      "step_id": "step_001",
      "tool": "search_files",
      "description": "搜索黑客松相关文件",
      "risk": "low",
      "status": "pending",
      "arguments": {}
    }
  ]
}
```

Allowed `risk` values:
- `low`
- `medium`
- `high`

Allowed PlanStep `status` values:
- `pending`
- `running`
- `completed`
- `failed`
- `awaiting_approval`
- `skipped`

### Document

```json
{
  "file_id": "file_001",
  "path": "D:/demo_workspace/报名表.docx",
  "filename": "报名表.docx",
  "extension": ".docx",
  "text": "...",
  "size": 12345,
  "modified_time": "2026-10-14T18:00:00",
  "metadata": {}
}
```

### ToolResult

Every public tool must return this envelope.

Success:

```json
{
  "success": true,
  "tool": "compare_versions",
  "data": {},
  "message": "Version comparison completed",
  "error": null
}
```

Failure:

```json
{
  "success": false,
  "tool": "compare_versions",
  "data": null,
  "message": "Version comparison failed",
  "error": "Unsupported document format"
}
```

### TaskSnapshot

`GET /api/agent/tasks/{task_id}` returns the current task state and the accumulated Agent outputs in one envelope.

```json
{
  "task": {
    "task_id": "task_001",
    "user_goal": "帮我准备黑客松报名资料",
    "workspace": "D:/demo_workspace",
    "status": "awaiting_approval"
  },
  "plan": {
    "task_id": "task_001",
    "goal": "帮我准备黑客松报名资料",
    "steps": []
  },
  "results": [],
  "pending_operations": [],
  "preview_id": "sha256:...",
  "error": null
}
```

Rules:
- `results` is `ToolResult[]`
- `pending_operations` is the set of concrete, already-resolved `PlanStep[]` awaiting approval
- when there are no pending operations, `pending_operations` is `[]` and `preview_id` is `null`
- `error` is a user-readable string or `null`
- analysis cards in the frontend should be derived from the corresponding entries in `results`, not from separate undocumented HTTP endpoints

### FinalReport

```json
{
  "task_id": "task_001",
  "status": "completed",
  "found_files": [],
  "version_groups": [],
  "conflicts": [],
  "missing_items": [],
  "operations": [],
  "package_path": "D:/demo_workspace/Hackathon_Package",
  "summary": ""
}
```

For the MVP, `FinalReport` is guaranteed only for `completed` tasks. Failed or rejected tasks expose their current state and readable failure/rejection detail through `TaskSnapshot`; requesting a report before completion returns `409`.

## 2. Agent HTTP API

The MVP Agent API is fixed as follows.

| Operation | Path | Request | Success response |
| --- | --- | --- | --- |
| Create task | `POST /api/agent/tasks` | `{ "user_goal": string, "workspace": string }` | `202`, `Task` |
| Get task | `GET /api/agent/tasks/{task_id}` | none | `200`, `TaskSnapshot` |
| Approve preview | `POST /api/agent/tasks/{task_id}/approve` | `{ "preview_id": string }` | `200`, `TaskSnapshot` |
| Reject preview | `POST /api/agent/tasks/{task_id}/reject` | `{ "preview_id": string }` | `200`, `TaskSnapshot` |
| Get report | `GET /api/agent/tasks/{task_id}/report` | none | `200`, `FinalReport` |

### Task execution and polling

- creating a task generates `task_id`; the task moves from `created` into `planning`
- low-risk steps may execute automatically in plan order
- before any file-changing operation, the task pauses in `awaiting_approval`
- the frontend polls `GET /api/agent/tasks/{task_id}` to render Plan, ToolResults, progress, errors, and pending operations
- after approval, the task continues through `executing` and `verifying`
- successful completion sets Task status to `completed`; the report endpoint then returns `FinalReport`
- tool or planning failure sets the Task to `failed`; completed steps and accumulated `ToolResult` entries are retained

### Workspace scope

The backend must reject a missing or invalid workspace and must limit scanning, analysis, and task file access to the workspace selected by the user, except for explicit output paths derived from an approved operation under the same task policy.

### MVP task persistence

Task state may be stored in process memory for the MVP. Server restart may lose active and completed task state. SQLite persistence and restart recovery are deferred until after the MVP unless the team explicitly revises this contract.

## 3. Approval Preview Binding

The Agent may automatically execute `low` risk tools.

For `medium` risk tools, the Agent must pause and surface the planned operation to the user before execution.

`high` risk tools are not permitted in the MVP.

When the task pauses for approval:
- the backend freezes each pending operation's tool name, step ID, source/destination paths, and other resolved arguments into the current preview
- the backend generates a `preview_id` for that exact preview snapshot
- the frontend must display `pending_operations` and return the current `preview_id` when approving or rejecting
- approval may execute only the frozen operations belonging to that preview; paths or arguments must not be silently recomputed after approval
- if new analysis creates different file-changing operations, the backend must generate a new preview and request approval again
- approve/reject is valid only while the Task is `awaiting_approval`
- stale, duplicate, or mismatched `preview_id` requests return `409` and must not perform file operations
- rejection marks remaining unexecuted steps as `skipped` and sets the Task to the existing MVP status `failed`
- MVP rejection does not automatically retry; retrying requires creating a new task

## 4. HTTP Error Contract

| Situation | HTTP status / behavior |
| --- | --- |
| Invalid request or workspace does not exist | `400` |
| Task does not exist | `404` |
| Task is not awaiting approval; stale/duplicate `preview_id`; report not yet available | `409` |
| Planning/tool failure after task creation | Task becomes `failed`; `GET` returns a snapshot with `error` |
| Task cannot be created because of an internal server error | `500` |

All file changes remain guarded by the backend approval gate. The MVP must not expose delete or destructive overwrite operations.

## 5. Public Tool Names

MVP public tools are fixed as follows.

### Read-only / analysis tools
- `list_files`
- `search_files`
- `read_document`
- `find_duplicates`
- `compare_versions`
- `detect_conflicts`
- `extract_requirements`
- `verify_result`

### File-changing tools
- `create_folder`
- `copy_file`
- `move_file`
- `build_package`

Do not expose `delete_file` or destructive overwrite tools in the MVP.

## 6. Tool Contracts

### list_files
Input:

```json
{
  "workspace": "string",
  "recursive": true
}
```

Output `data`:

```json
{
  "files": []
}
```

### search_files
Input:

```json
{
  "workspace": "string",
  "query": "string",
  "extensions": []
}
```

Output `data`:

```json
{
  "matches": []
}
```

### read_document
Input:

```json
{
  "path": "string"
}
```

Output `data`:

```json
{
  "document": "Document"
}
```

### find_duplicates
Input:

```json
{
  "workspace": "string"
}
```

Output `data`:

```json
{
  "duplicate_groups": []
}
```

### compare_versions
Input:

```json
{
  "documents": []
}
```

Output `data`:

```json
{
  "groups": [
    {
      "group_id": "version_group_001",
      "documents": [],
      "newest_candidate": null,
      "changes": []
    }
  ]
}
```

The nested shape of `newest_candidate` and each `changes` entry remains to be finalized before strict frontend rendering depends on those fields.

### detect_conflicts
Input:

```json
{
  "documents": []
}
```

Output `data`:

```json
{
  "conflicts": [
    {
      "field": "deadline",
      "values": [
        {
          "value": "2026-10-18",
          "source": "比赛通知.pdf"
        },
        {
          "value": "2026-10-20",
          "source": "补充通知.pdf"
        }
      ],
      "recommendation": "请人工确认"
    }
  ]
}
```

### extract_requirements
Input:

```json
{
  "documents": []
}
```

Output `data`:

```json
{
  "required_documents": [
    "报名表",
    "学生证",
    "身份证",
    "项目介绍",
    "指导教师确认书"
  ]
}
```

The exact shared representation for matched/missing requirement items remains to be finalized with Developer C before the frontend relies on a stricter schema.

### create_folder
Input:

```json
{
  "path": "string"
}
```

Risk: `medium`

### copy_file
Input:

```json
{
  "source": "string",
  "destination": "string"
}
```

Risk: `medium`

### move_file
Input:

```json
{
  "source": "string",
  "destination": "string"
}
```

Risk: `medium`

For old versions, move to an archive location instead of deleting.

### build_package
Input:

```json
{
  "task_id": "string",
  "requirements": [],
  "selected_files": [],
  "destination": "string"
}
```

Rules:
- default to copy, not move
- never overwrite an existing user file silently
- generate a package report when possible
- the exact `ToolResult.data` shape for the actual package output path and verification target list must be agreed with Developer C before implementation is treated as stable

### verify_result
Input:

```json
{
  "task_id": "string",
  "expected": {},
  "workspace": "string"
}
```

Output `data`:

```json
{
  "checks": [],
  "passed": true
}
```

## 7. Interface Change Rule

Any change to:
- Agent HTTP paths
- public tool names
- request fields
- response fields
- shared data models
- risk levels

must update this document first and be agreed by the team before implementation.
