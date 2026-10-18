# Backend API Dependencies

The Agent HTTP contract is now defined in `API_CONTRACT.md`. The current Agent Workbench may continue to use Mock Mode during frontend-only development, but Real Mode must integrate only with the agreed endpoints and response envelopes below. Existing FileForge `/api/browse`, scan, session and configuration endpoints remain unchanged.

## Frontend implementation status

Real Mode now calls all five agreed endpoints through `agent-api.js`:
`createTask(userGoal, workspace)`, `getTask(taskId)`,
`approveTask(taskId, previewId)`, `rejectTask(taskId, previewId)` and
`getReport(taskId)`. Requests use JSON and retain HTTP status on errors.
Invalid JSON, unexpected success status, unavailable backend and a 15-second
request timeout produce visible errors. No request automatically falls back to
Mock Mode; mutation requests are never automatically retried.

The workbench polls sequentially every 1000 ms for created/planning/executing/
verifying. It pauses at awaiting_approval, stops at failed/completed, and only
fetches FinalReport after a completed snapshot. A Refresh Task Status button
allows recovery after transport errors or a report that is not ready (409).
Refreshing clears the scheduled poll; in-flight guards prevent concurrent loops
and repeated task/approval submissions.

Real approval displays `pending_operations` PlanSteps and their exact arguments,
and submits the associated nonempty `preview_id`. A 409 triggers one snapshot
refresh with a stale-preview message and does not repeat approval or rejection.
Other approval errors disable the old preview until the user refreshes status,
because the backend may have accepted the operation before the connection failed.

Real rendering now consumes the confirmed compare_versions v1 groups, candidate
references, recommendation_reason, comparison order and line-change evidence.
It distinguishes not-run, successful empty, failure and unavailable response
structure. Null recommendations are successful abstention, never an error or a
frontend choice. All supplied candidates and full source paths remain visible.
It does not interpret Mock candidate IDs, infer missing
materials, or invent file-operation paths. Mock-specific adaptation stays in the
frontend mode branches; `agent-mock.js` remains unchanged. The optional third
createTask argument selects the Mock scenario and is never sent to the real API.

Verification: Node syntax checks and fetch-stub/DOM checks cover Mock happy path,
reject/failure, Real polling and exact payloads, approval 409 refresh, report 409
recovery, missing optional fields, HTTP 400/404/409/500, invalid JSON, unreachable
backend, and repeated Run/Approve/Refresh clicks. A local FileForge HTTP check
also verified root/static scripts/health/browse return 200 and Real createTask
returns the backend's actual 404 without using Mock. The temporary server was
stopped. Actual Agent execution and browser visual/clipboard behavior still
require integration verification.

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
- `match_requirements` ToolResult -> separate Matching Phase 1 panel, preserving every filename candidate, file_id, filename, path and backend order
- other ToolResults may be shown as progress/details without creating undocumented shared fields

## Approval behavior

Approval is enforced by the backend. The frontend displays only the concrete operations in the current preview and returns the associated `preview_id`.

A stale, duplicate or mismatched approval may return `409`; the UI must refresh the task snapshot instead of assuming execution succeeded. Rejection uses the existing MVP Task status `failed` and remaining unexecuted steps become `skipped`. The UI should present this as a user-stopped/rejected task when appropriate rather than as an unexpected system crash.

High-risk operations, deletion and destructive overwrite remain forbidden.

## Task persistence and report behavior

For the MVP, the backend may store task state in process memory. Server restart may therefore lose tasks; the frontend should not assume task recovery across backend restarts.

`FinalReport` is guaranteed for `completed` tasks. Calling the report endpoint before completion, including failed/rejected tasks, may return `409`. In those cases the frontend uses the latest `TaskSnapshot` for status and error/rejection detail.

## Remaining backend contract dependencies

The Version v1 structure is now confirmed in API_CONTRACT.md and rendered by
agent-results.js. Its recommendation never means an approved final selection.
The following remaining structures must not be guessed by the frontend:

- exact `build_package` ToolResult data for actual output path and verification targets

Package and classification still require agreed contracts before strict consumers.
Matching Phase 1's three-array shape is in API_CONTRACT.md and implemented by the
public D tool merged in PR #24. Some contract/task prose still says review/merge
pending; that wording is stale and is not edited by B. This frontend consumes the
documented result shape only when supplied in TaskSnapshot.results. No additional
matching/classification endpoint or tool-call parameters are introduced.

## Matching and final-report semantics

Requirement extraction alone does not confirm candidate matching. Successful empty
requirements mean no explicit requirements were extracted; they do not establish
completeness. Real Mode selects the latest match_requirements ToolResult by tool
name; it does not interpret an empty FinalReport.missing_items alone as completeness.
Task completion alone does not prove every analysis tool executed. A failed or
absent conflict result is explicitly marked unknown even when the report array
is empty. A failed task clears any stale successful report and copy action.

The Matching panel distinguishes absent result (not executed), failure, incomplete
response, successful no requirements, all unmatched, partially matched and all
requirements with candidates. Zero candidates is conveyed by data.missing and
displayed as “本次未找到文件名候选”, not proof of absence or failed review. All N
candidates and their order are preserved. Requirements/candidate identity fields
are rendered verbatim with HTML escaping. No ranking, content review, selected
version, unresolved field or new Mock shape is added.

Final Result repeats the latest Matching evidence, never falls back to an older
success after a failure, and warns if report.missing_items differs from the latest
successful data.missing. Completed is not materials approved. Empty package_path
means no generated package path was reported; the copy-path button stays hidden.

Readiness baseline: origin/dev 43a723a (PR #24 merged). A's executor/planner still
does not register Matching, and service._report still initializes missing_items
to []. Matching HTTP retention/mapping/failure propagation are NOT accepted by
this UI change. A must supply authorized successfully read candidates, exclude
notices, retain complete ToolResults and stop execution on failure before genuine
HTTP Matching acceptance. D's Phase 2 aliases/semantic proof remain unfinished.

## Frontend checks

Run the dependency-free Node checks from the repository root:

```sh
node --test frontend/tests/*.test.cjs
```

With the project Python dependencies installed, also run:

```sh
python -B frontend/tests/real-results-smoke.py
python -B frontend/tests/matching-public-smoke.py
```

This uses real HTTP handlers, TaskService and public C/D results in temporary
unknown course workspaces (0/1/2 documents) and passes them to the frontend
renderer. A fixed test planner isolates model availability; D tools are called
directly for this check, not silently registered into the Agent. This test is
not proof of the unfinished LLM/Matching/Package classroom workflow.

matching-public-smoke.py separately invokes the actual D public Matching tool on
six in-memory cases and passes its untouched output to the JS renderer. No model,
Workspace file operations, HTTP endpoint or Agent registration is involved.
Snapshot/FinalReport Matching UI integration tests use explicitly stubbed HTTP
responses. These do not certify the absent Agent Matching path. The older
real-results-smoke.py is a separate C/D historical test, not run as Matching
acceptance and not a substitute for the new check.

The tests cover result states, version abstention and recommendations, escaped
evidence, arbitrary source paths, multiple candidates, real polling/approval and
report errors, Mock regressions, and the request-free organization placeholder.
Task-driven material preparation remains available alongside the explicitly
unfinished organization entry. Classroom acceptance must use Real Mode with a
runtime-selected unknown workspace, not a fixture or a successful Mock render.

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
