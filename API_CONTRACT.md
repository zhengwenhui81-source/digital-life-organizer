# API_CONTRACT.md

This document defines shared data structures and tool contracts. These interfaces may not be changed unilaterally.

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

## 2. Public Tool Names

MVP public tools are fixed as follows:

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

## 3. Tool Contracts

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

## 4. Approval Contract

The Agent may automatically execute `low` risk tools.

For `medium` risk tools, the Agent must pause and surface the planned operation to the user before execution.

`high` risk tools are not permitted in the MVP.

## 5. Interface Change Rule

Any change to:
- public tool names
- request fields
- response fields
- shared data models
- risk levels

must update this document first and be agreed by both developers before implementation.
