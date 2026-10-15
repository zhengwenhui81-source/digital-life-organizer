# Backend API Dependencies

The Agent HTTP contract is now defined in `API_CONTRACT.md`. The current Agent Workbench may continue to use Mock Mode during frontend-only development, but Real Mode must integrate only with the agreed endpoints and response envelopes below. Existing FileForge `/api/browse`, scan, session and configuration endpoints remain unchanged.

## Agreed Agent HTTP API

| Adapter method | HTTP API | Expected result |
| --- | --- | --- |
| `createTask` | `POST /api/agent/tasks` | `202`, `Task` |
| `getTask` | `GET /api/agent/tasks/{task_id}` | `200`, `TaskSnapshot` |
| `approveTask` | `POST /api/agent/tasks/{task_id}/approve` with `{preview_id}` | `200`, `TaskSnapshot` |
| `rejectTask` | `POST /api/agent/tasks/{task_id}/reject` with `{preview_id}` | `200`, `TaskSnapshot` |
| `getReport` | `GET /api/agent/tasks/{task_id}/report` | `200`, `FinalReport` after completion |

Real Mode must not invent additional analysis endpoints. The frontend should poll `getTask` and render progress from the returned `TaskSnapshot`.

## TaskSnapshot integration

The agreed snapshot shape is:

```json
{
  "task": {},
  "plan": {},
  "results": [],
  "pending_operations": [],
  "preview_id": null,
  "error": null
}
```

Frontend responsibilities:

- render task status from `snapshot.task.status`
- render the Agent Plan from `snapshot.plan`
- derive analysis cards from `snapshot.results: ToolResult[]`
- render approval preview directly from `snapshot.pending_operations: PlanStep[]`
- send the exact current `snapshot.preview_id` on approve or reject
- never execute local file changes directly in browser code
- show `snapshot.error` for backend planning/tool failures

Expected analysis mapping:

- `compare_versions` ToolResult -> Version Groups
- `detect_conflicts` ToolResult -> Conflicts
- `extract_requirements` ToolResult -> Required Materials / requirement analysis
- other ToolResults may be shown as progress/details without creating undocumented shared fields

## Approval behavior

Approval is enforced by the backend. The frontend displays only the concrete operations in the current preview and returns the associated `preview_id`.

A stale, duplicate or mismatched approval may return `409`; the UI must refresh the task snapshot instead of assuming execution succeeded. Rejection uses the existing MVP Task status `failed` and remaining unexecuted steps become `skipped`. The UI should present this as a user-stopped/rejected task when appropriate rather than as an unexpected system crash.

High-risk operations, deletion and destructive overwrite remain forbidden.

## Task persistence and report behavior

For the MVP, the backend may store task state in process memory. Server restart may therefore lose tasks; the frontend should not assume task recovery across backend restarts.

`FinalReport` is guaranteed for `completed` tasks. Calling the report endpoint before completion, including failed/rejected tasks, may return `409`. In those cases the frontend uses the latest `TaskSnapshot` for status and error/rejection detail.

## Remaining backend contract dependencies

The following nested structures are intentionally not frozen yet and must not be guessed by the frontend:

- exact `compare_versions.data.groups[].newest_candidate` representation
- exact `compare_versions.data.groups[].changes[]` representation
- exact shared structure for matched and missing requirement items beyond `extract_requirements.data.required_documents`
- exact `build_package` ToolResult data for actual output path and verification targets

Developer A and Developer C should finalize these shared structures in `API_CONTRACT.md` before strict Real Mode rendering depends on them.

## TEMPORARY MOCK SHAPE

The existing mock structures remain frontend demonstration data only and are **not shared API contracts**:

- Mock scenario input (`happy` / `failed`) is not a Task field.
- Mock data may contain fixed version groups, conflicts, missing items and package paths solely to exercise the UI.
- Mock approval/cancel actions do not perform filesystem operations.
- Mock completed means the simulation finished, not that a real package exists on disk.
- Mock mode must never silently substitute for a failed Real Mode request.

## Local verification

Serve the frontend through the existing FileForge server, which mounts `frontend` at `/static`. Browse needs the real server even in Mock Mode. Agent simulation itself never calls filesystem operation endpoints. Open Folder is not offered unless a future backend contract explicitly supports it.

Automatic actions are not editable from this UI; existing backend configuration may still contain `auto_act=true`. Backend policy enforcement remains Developer A's responsibility. The frontend does not silently change saved settings.
