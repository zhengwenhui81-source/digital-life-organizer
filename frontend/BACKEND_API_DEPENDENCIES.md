# Backend API Dependencies

The current Agent Workbench explicitly runs in Mock Mode. Real mode fails with a
clear error until the team agrees on the HTTP contract. No guessed routes are
called and no automatic fallback is used. Existing FileForge `/api/browse`, scan,
session and configuration endpoints remain unchanged.

## Required capabilities (Developer A)

| Adapter method | Required behavior |
| --- | --- |
| createTask | Accept `user_goal`, `workspace`; return `Task` |
| getTask | Return Task, Plan and intermediate ToolResult data; define error details |
| approveTask | Bind approval to the displayed operations; reject stale/duplicate approval |
| rejectTask | Define rejection status, skipped steps and retry semantics |
| getReport | Return FinalReport after verification |

HTTP paths, request/response envelopes, persistence and polling behavior must be
agreed in API_CONTRACT.md before real integration. Approval must be enforced by
the backend. High-risk operations, deletion and overwrite are forbidden.

## TEMPORARY MOCK SHAPE

These are frontend demonstration structures, **not shared API contracts**:

- Mock snapshot: `{task, plan, results: ToolResult[], missing_items: string[], operations, error}`.
- `newest_candidate`: Document `file_id`; `changes`: string array.
- `missing_items`: material-name strings. Required checklist matches these names
  for presentation only; no browser algorithm searches or analyzes user files.
- `operations`: `{tool, source, destination, status}`. `move_file` is displayed
  as MOVE / ARCHIVE for the fixed mock archive example; no public archive tool added.
- Failure detail: snapshot `error` string. Cancel uses Task `failed` and marks
  remaining steps `skipped`; rejection semantics need team agreement.
- `scenario` is a mock-only input (`happy` / `failed`), not a Task field.
- `plan ready` and `analyzing` are demonstration phases represented by PlanStep
  changes while Task remains `planning`; they are not added Task status values.
- Mock FinalReport uses the existing top-level fields. Package path is a fixed
  example, not a path created on disk. Completed means the simulation finished;
  conflicts and missing materials remain visible.

Confirm Document references, version change entries, matching results, operation
preview/results, failure details and rejection semantics before replacing mocks.

## Local verification

Serve index.html through the existing FileForge server, which mounts frontend at
`/static`. Browse needs the real server even in Mock Mode. Agent simulation itself
never calls filesystem operation endpoints. Open Folder is not offered.

Automatic actions are not editable from this UI; existing backend configuration
may still contain `auto_act=true`. Backend policy enforcement remains Developer
A's responsibility. The frontend does not silently change saved settings.
