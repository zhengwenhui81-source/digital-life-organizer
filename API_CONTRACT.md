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

### Shared Document collection rules

**Status: contract confirmed through the project owner by A/B/C/D; implementation
and tool-by-tool adaptation are separate, pending work.**

These rules apply to `compare_versions`, `match_requirements` and every public
tool consuming `Document[]`, including the existing `detect_conflicts` and
`extract_requirements` inputs and future `classify_files` Document collections.
No new Document model or ID mechanism is introduced.

- Validate JSON legality of the complete original input, including metadata and
  every extra field, before snapshot comparison or deduplication. Allow only
  null, booleans, strings, finite numbers, arrays and string-keyed objects.
  Reject NaN/Infinity, non-string object keys, non-JSON types and circular
  references without coercion (no `default=str` or tuple-to-array conversion).
  Shared nested objects are allowed when they do not form a cycle.
- Snapshot equality is type-strict recursively: integer `1` differs from floating
  `1.0`, and booleans differ from numbers (`true` vs `1`, `false` vs `0`).
  A missing field differs from a field explicitly set to null. These rules apply
  to the whole Document, including metadata and extra fields.
- Invalid JSON input fails the whole call with the standard failed ToolResult,
  `data=null` and a readable error, before business analysis; no partial result
  is returned. Reject custom values before invoking their equality methods.
  Deep inputs must not cause an uncaught RecursionError; no shared public depth
  quota is introduced here.
- Identity is determined by the existing `file_id`, not filename, content hash,
  array position or a newly generated identifier.
- Validate the applicable tool's resource limits on the original input before
  snapshot comparison or deduplication. Duplicate entries still count toward quantity, text and input
  volume limits; deduplication cannot bypass them. Version-specific numeric
  limits below are not automatically imposed on other tools.
- Documents with the same `file_id` may be stably deduplicated only when **all
  fields** agree, including `metadata` and any other supplied fields. Preserve
  the first occurrence of an equal snapshot; this does not authorize choosing
  among conflicting snapshots.
- Compare JSON object members by key/value equality, recursively, independent of
  object key order. In particular, reordered but otherwise equal `metadata`
  objects are equal. Array order remains significant. Do not ignore fields,
  normalize conflicting values or compare JSON strings by their key ordering.
- If the same `file_id` has any field difference (including missing versus
  present fields), reject the entire tool call with the standard failed
  `ToolResult`: `success=false`, the actual tool name, `data=null`, and readable
  nonempty `message` / `error` identifying the contradictory snapshot. Never
  select by input order, silently discard the contradiction or return partial
  results. This is an input identity error, not a successful semantic conflict
  detected between different documents.
- A collects successful `read_document.data.document` values and stops the task
  on a read failure. An unresolved argument, placeholder or failed read is not
  an empty candidate set. B renders the unified ToolResult; it does not implement
  another Document identity/conflict policy in the frontend.

**D adaptation scope:** D must apply these rules at the public boundaries of
`detect_conflicts` and `extract_requirements`, and of `match_requirements` when
its public interface is finalized. Tests must cover equal duplicates, reordered
metadata keys, differences in every field, resource validation before dedup,
and whole-call failure without partial output. This document does not certify
that existing D implementations already enforce them. It does not freeze the
separately specified `match_requirements` input/output schema, register a runtime
tool, or change conflict/requirement business algorithms. Its team-confirmed
[Phase 1 contract](#match_requirements--phase-1-contract) has separate final HEAD
review/merge and implementation requirements. Mentioning future
`match_requirements` or `classify_files` here does not freeze their public entry
points or output schemas. Confirmation of these rules does not certify that
C/A/B or other consumers already implement them.

### Path-based Document identity

**Status: active, confirmed by the team through the project owner in this session.**

Rules for the first version:
- The document-reading layer generates `file_id`; no registration service,
  database table, or additional Agent/public request parameter is introduced.
- No shared path-normalization helper currently exists. Expand the input using
  `Path(path).expanduser().resolve()`, resolving relative components and symbolic
  links to the absolute target path. Use that target for reading and for the
  Document's `path`, `filename`, and `extension` fields.
- For ID generation, apply the host's `os.path.normcase()` to the resolved path
  string (Windows system case/separator normalization; Linux preserves case).
  Encode that string as UTF-8, then set `file_id` to `"file_"` plus the full
  lowercase hexadecimal SHA-256 digest (64 hex characters). Do not use Python's
  built-in `hash()` or random UUIDs.
- Repeated reads and content changes at the same normalized path preserve the
  ID. Moving, renaming, or copying to a different normalized path changes the ID.
  Symbolic links resolving to the same target share the target's ID. A spelling
  change that normalizes to the same path does not change identity.
- Stability is limited to consistent path rules in the same runtime environment;
  IDs are not portable identities across computers, operating systems, or mount
  locations. This does not implement identity tracking after file moves.
- Path-resolution, UTF-8 path-encoding, or file-read failure returns the existing
  failed `ToolResult` envelope: `success=false`, `tool="read_document"`, `data=null`,
  a readable `message` and `error`. No partial successful Document is returned.
- Keep the public input `{ "path": string }` and existing Document/ToolResult
  fields unchanged. Supported formats and extraction scope are defined below;
  all use this same identity rule and envelope.

### read_document extraction scope

`read_document(path)` supports exactly `.txt`, `.pdf`, `.docx`, and `.xlsx`
(case-insensitive extensions). It reuses FileForge extractors with an explicit
full-text limit (`sys.maxsize`), rather than the 2000-character snippet default.
The complete readable content is held in memory; this is not a streaming reader.

| Format | Supported content | Limits |
| --- | --- | --- |
| TXT | Full decoded text using the existing encoding detection and replacement behavior | Whitespace-only/empty content fails |
| PDF | Text layer across all pages | No OCR or guaranteed table/layout reconstruction; no text does not establish that a file is scanned |
| DOCX | Body paragraphs in order | Tables, headers, footers, images and other Office content are not read; this is not complete Office extraction |
| XLSX | Cell values across worksheets in workbook order, with sheet-name headers | Read-only, `data_only=True`; formula caches may be stale, missing caches are omitted, and formulas are never calculated; styles, charts and cell coordinates are not preserved |

XLSM remains unsupported by this public entry point, even though the upstream
extractor can handle it. Source files are never saved or modified by the reader.
Parser exceptions and read failures return failed `ToolResult` envelopes with
readable errors. Successful parsing with no supported text/cell values also
returns a failed envelope, explicitly describing the absence of extractable
content rather than reporting a parse error. No partial successful Document is
returned for an exception. Mixed XLSX content may succeed while uncached formula
cells are omitted; callers must not assume a complete set of calculated values.

These scope limits apply even to successful Documents. C1 progress and outstanding
verification are tracked in `TASKS.md`; recognizing four extensions alone does
not establish complete C1 acceptance.

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

Package-specific proposed approve acceptance is described in the
[Package proposal](#plan_package--build_package--minimal-package-proposal);
the table above remains the currently implemented request shape.

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
- `match_requirements` — Phase 1 team-confirmed; final HEAD review/merge pending,
  not implemented/exported/registered
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

**Status: v1 contract confirmed; public C implementation/package export locally
verified on Linux. Windows Version verification, Agent registration and full
integration remain pending. Contract acceptance alone is not implementation evidence.**
No new Document, ToolResult or path-ID mechanism is introduced.

#### Input and outcome semantics

```json
{"documents": []}
```

Public signature: `compare_versions(documents: list[Document]) -> ToolResult`.
Use full Documents from successful `read_document` results. The
[shared collection rules](#shared-document-collection-rules) apply. Empty or
whitespace-only text is not a valid successfully read candidate. Expected input
validation, serialization and resource errors return a failed ToolResult with
`data=null`, not an outward validation exception or partial result.

A calls with `documents=[]` only after collection establishes genuinely zero
candidates. That succeeds with `data={"groups": []}`. Valid nonempty input with
no identifiable version relations also **succeeds**: retain every deduplicated
candidate in a singleton group, with `newest_candidate=null`,
`recommendation_reason="single_document"`, and `changes=[]`.
Insufficient evidence is normal abstention, not a tool failure.

Default runtime input comes from an **unknown Workspace**. Do not assume any
version suffix, highly similar content, multiple versions or a particular task.
Do not force grouping/recommendation to make a demonstration succeed. Controlled
v1/v2 fixtures are for tests, regression and contract acceptance only; B is not
required to add fixed classroom samples.

#### Group fields

Success uses the existing envelope (`success=true`, `tool="compare_versions"`,
`error=null`) with `data.groups`. Every group has these fields:

| Field | Contract |
| --- | --- |
| `group_id` | `version_group_001`, etc., assigned in deterministic group order; batch-local correlation only, not cross-task identity or approval evidence |
| `documents` | Full Documents; retain all candidates except equal snapshots removed under the shared rule, in comparison order |
| `grouping.basis` | String describing the common parent directory, extension, normalized name and content-evidence conditions; no task classification |
| `grouping.normalized_name` | Material stem after the single allowed suffix removal |
| `grouping.similarity_method` | `sequence_matcher` |
| `grouping.minimum_pair_similarity` | Number: minimum pairwise score within the group; null for a singleton; display may round to 4 decimals, decisions use unrounded scores |
| `recommendation_reason` | One of the six values in the priority table below |
| `comparison_order` | `{basis, tie_breaker, chronology_confirmed}` as defined below |
| `newest_candidate` | null or `{file_id, path, filename, reasons: string[]}` referencing a member Document verbatim |
| `changes` | Array of evidence-backed adjacent comparisons as defined below |

No material aliases or additional version metadata keys are frozen. D consumes
these public results without private C imports, file reparsing or ID generation.

#### Grouping normalization and evidence

Use one task-neutral algorithm and parameter set across all material categories;
no task-name, semantic-purpose or particular-filename exceptions. Grouping
normalization generates candidates; recommendation evidence is separate.

1. Derive the parent from the already normalized Document path, without creating
   another path/ID normalization rule. Candidate bucket: same parent directory,
   same extension, same normalized material name.
2. From the filename stem remove **one** exact trailing whitelist suffix, leaving
   a nonempty material name. Explicit version suffixes are `_vN`, `_vN.N`,
   `_vN.N.N` (ASCII nonnegative integers). Reuse existing extraction with strict
   end validation; missing components are zero as in the existing extractor.
   `_v1` and `_v1.0` therefore have equal version tuples.
3. Grouping-only suffixes: `_最终版`, `_修改版`, `_修订版`, `_终稿`, `_final`,
   `_final2`. They create no numeric version and have no recommendation priority;
   `final2` is not v2.
4. Preserve material-name case. Match lowercase `v`, `final`, `final2` with ASCII
   underscore only. No `_V2`, `_FINAL`, hyphen/space/fullwidth separators,
   recursive stripping, ordinary word/digit deletion or inferred aliases.
   `项目_v1_final` becomes `项目_v1` and supplies no explicit version evidence.
   Do not accept arbitrary `_finalN`, four-part versions, dates, `_最新版`,
   `_定稿`, `_副本`, `(1)` or other unlisted suffixes. Nonmatches keep the stem.
5. Equal names alone never guarantee grouping. Within a bucket, exactly equal
   extracted text is eligible, including short equal text. Otherwise **both
   texts must have at least 100 Unicode characters**, and
   `SequenceMatcher(None, a.text, b.text, autojunk=False).ratio() >= 0.85`.
   Use original extracted text without whitespace/content normalization; order
   each score's arguments by ascending `file_id`.
6. These strict v1 thresholds are confirmed heuristics, not accuracy estimates.
   They may miss real versions, including short or substantially rewritten
   v1/v2 files. Low similarity means no group, not proof of unrelated material.
   No weak-relation/strong-match second schema is introduced.
7. Visit candidates by ascending `file_id`. A candidate may join a group only if
   it satisfies the content condition with every member (no transitive closure).
   Among eligible groups choose the highest minimum score to existing members;
   ties choose the lexicographically smallest sorted member-ID tuple. Otherwise
   create a singleton. Cache pair scores if useful without changing semantics.
8. Sort final groups by sorted member-ID tuple, then assign group IDs. Same
   input set in a different order must not change membership, recommendation or
   comparison direction. Group IDs need not survive input-set changes.

#### Comparison order and recommendation

If all members have distinct explicit version tuples, order by ascending tuple
and set `comparison_order.basis="explicit_version"`; otherwise order by ascending
`file_id` and set `basis="stable_id_display"`. Always include
`tie_breaker="file_id_ascending"`, `chronology_confirmed=false`.
Stable-ID order is display order, not chronology. Even version order is not a
user-confirmed history.

Apply the following first-match priority:

| Priority | Condition | `recommendation_reason` | `newest_candidate` |
| --- | --- | --- | --- |
| 1 | One member | `single_document` | null |
| 2 | All extracted texts exactly equal, regardless of version names | `identical_content` | null |
| 3 | Any member lacks an explicit version | `insufficient_evidence` | null |
| 4 | Multiple files share the highest version tuple | `version_tie` | null |
| 5 | Unique highest version has an opposing comparable time signal | `opposing_time_signal` | null |
| 6 | Unique highest version and no opposing comparable time signal | `unique_highest_explicit_version` | Member reference and reasons |

Lower-version ties do not alone block a unique highest recommendation, but do
require stable-ID display/comparison order. Parse time only when it is an ISO
value with an explicit UTC offset; compare in UTC, never invent a timezone.
Only a lower version with a strictly later comparable modification time blocks
the candidate. Equal, unavailable or incomparable times do not block it;
`reasons` must state the evidence and unavailable time participation. Required
Document fields still cannot be omitted.

A recommendation is **not a user's final selection**, task compliance judgment,
or file-operation authorization. Neither newest mtime nor a final-looking name
alone proves finality. Keep all candidates; no automatic copy/move/archive/package
operation follows from a recommendation. A's approval boundary remains in force.

#### Changes and summaries

Compare adjacent ordered members only (n-1 pairs), using original lines and the
standard-library sequence comparison. For each pair, emit non-equal blocks in
source position order. Each entry has:

| Field | Contract |
| --- | --- |
| `from`, `to` | `{file_id, path, filename}` copied from two distinct member Documents; direction is from-text to to-text |
| `type` | `insert`, `delete`, `replace`, or `identical` |
| `before`, `after` | null or `{start_line, end_line, text}`; 1-based inclusive line range, exact joined original lines including newlines |
| `summary` | Deterministic template describing original text changes and locations; no task-specific suitability or finality judgment |

For insertion `before=null`; for deletion `after=null`. Do not invent line ranges
for absent content. For equal extracted texts emit one `identical` entry using
both full texts and line ranges, summary `提取文本相同`; this is not binary-file
identity. A singleton has `changes=[]`. Adjacent equal pairs may occur in a group
whose other texts differ.

For example, same-bucket v1 and `_最终版` may group only if content qualifies;
then missing explicit version evidence causes abstention. If their texts are
equal, `identical_content` wins instead. No fixture is assumed to qualify merely
because of its filename.

#### Resource limits and failure boundary

Validate before deduplication and before launching the comparison subprocess:

- At most 10 Documents, each text at most 10,000 Python Unicode characters,
  total text at most 50,000 characters (`len`, not UTF-8 bytes or grapheme count).
- At most **1 MiB = 1,048,576 UTF-8 bytes** for the complete actual
  `{"documents": [...]}` input object, including wrapper punctuation/keys,
  metadata and every actually supplied field. Do not measure just Document[],
  project away fields, or deduplicate first. This does not permit otherwise
  invalid arguments or include HTTP headers/other Agent task wrappers.
- For actual input object `payload`, the measurement semantics are:

```python
len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
```

Check input/Document types and quantity/text limits first, then complete input
size, then deduplicate and compare. No truncation, sampling, silent field removal
or partial grouping. Report the exceeded limit and actual value; volume errors
include exact actual UTF-8 byte size and 1,048,576-byte limit. Nonserializable
values, NaN/Infinity, cycles or UTF-8 encoding errors produce a readable standard
failure; do not invent a measured size or stringify invalid values with
`default=str`.

Do not materialize unbounded JSON strings and byte copies merely to measure.
Use equivalent bounded-chunk counting including escaping, keys and separators;
a single huge string also requires chunking, since `iterencode` chunks are not
inherently bounded. Count remaining valid input without retaining its serialized
copy when exact oversize reporting is needed. Construct a size-bounded transport
buffer only after acceptance. Measurement itself has no fixed-time guarantee.
This is a **serialized-input boundary, not total memory or HTTP-request limit**;
objects, algorithm workspace, subprocess and output consume additional resources.

Use one temporary standard-library subprocess for the whole comparison.
After successful process creation, the total comparison/communication budget is
**5 seconds**, not 5 seconds per pair; include grouping, similarity, differences,
summary, result serialization and transfer. On timeout kill the process, wait
at most **0.5 seconds** for cleanup, discard partial/late output and fail with
`data=null`. Acceptance must verify the process has ended, not just a timeout
message. Do not use a thread timeout that leaves computation running or a
post-computation elapsed-time check. No descendant processes, external services
or unlimited in-process fallback. Startup failure or cleanup error also fails
readably; never wait indefinitely.

Preflight validation/measurement and process creation are outside that budget.
This is **not a strict 5/5.5-second HTTP or whole-tool deadline**. A owns tool
registration, candidate collection/resolution, read-failure termination,
unexpected-exception fallback, TaskSnapshot/FinalReport mapping and failed task
state. C owns comparison-process monitoring and termination acceptance. A has no
existing task-cancellation API or startup-inclusive hard deadline. Cancellation,
independent workers or stronger deadlines require a separate future proposal.

#### Acceptance and implementation status

Use the same algorithm/parameters for project introductions, scholarship
applications, evaluation statements, personal summaries and course reports.
Cover unrelated/empty/singleton inputs as successful outcomes; no task-name or
fixture-specific branch. Verify input permutation invariance, strict thresholds,
equal short text, version ties, time signals, original evidence, identity rules,
all resource boundaries and process termination on Linux and Windows.

Contract confirmation alone does not certify implementation or integration.
The C public implementation/export now has Linux local tests; see TASKS.md for
actual results and remaining Windows/Agent integration acceptance.
`read_document` parser verification is a separate milestone; its Windows evidence
does not verify the Version subprocess. End-to-end integration remains incomplete.

### detect_conflicts

The confirmed [Document collection rules](#shared-document-collection-rules)
apply to this existing input. D must adapt validation/deduplication and tests;
contract publication is not evidence that the adaptation is implemented.

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

The confirmed [Document collection rules](#shared-document-collection-rules)
apply to this existing input. D must adapt validation/deduplication and tests;
its requirement-extraction behavior and output schema are unchanged here.

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

The matching schema is team-confirmed in the [Phase 1 contract](#match_requirements--phase-1-contract)
below; final document HEAD independent review and merge are still required
before treating it as frozen and implementing strict consumers.

### match_requirements — Phase 1 contract

**团队已确认，待最终 HEAD 独立复审及合入。** Formal freezing is completed
through final document HEAD review and merge, not by team confirmation alone.
This documentation does not implement, export, register or verify the tool.
The public tool list records its contract status, not runtime availability.

#### Confirmation provenance

- A/B/C/D confirmation applies to PR #19 HEAD
  `b28d407a319380c173ec9ca0e11a8b3a0d3ec49c`. B/C/D confirmed the rules earlier;
  A's final acceptance of the entire Phase 1 draft was relayed by the project owner.
- A accepted the complete input/output and filename rules, Agent failure
  propagation, TaskSnapshot.results retention and FinalReport.missing_items
  semantics, including no fallback to an older success after a newer failure.
- The previously additional whitespace-only filename rejection is now explicitly
  accepted by A, as is whitespace-only requirement rejection.
- No matching-specific quota in v1, no inherited Version limits and no
  arbitrary-scale guarantee are confirmed boundaries, not open blockers.
- Phase 2 remains required and unfinished. Final HEAD independent review/merge,
  tool implementation/export/registration and integration acceptance remain
  separate steps; none is certified complete by this confirmation record.

#### Entry point and input

Team-confirmed public entry point (read-only, risk `low`):

```python
match_requirements(
    required_documents: list[str],
    candidate_documents: list[Document],
) -> ToolResult
```

- `required_documents` contains exact built-in strings, neither empty nor entirely
  whitespace. Stably deduplicate by the original string, preserving its first
  occurrence. Do not trim or rewrite output requirements.
- `candidate_documents` contains complete Documents. Apply the confirmed
  [shared collection rules](#shared-document-collection-rules), including strict
  JSON legality, strict recursive types, all supplied fields, missing/null
  distinction, contradictory-snapshot whole-call failure and stable deduplication.
- Validate the complete original input and each tool-specific resource rule
  before comparing snapshots or deduplicating. Even when requirements are empty,
  fully validate supplied candidates; never hide invalid input behind an empty
  success. No partial result is returned on failure.
- Different IDs remain distinct, including identical names/text. Do not add a
  one-to-one path/file_id constraint or regenerate identity. Returned references
  copy the original `file_id`, `path` and `filename` values verbatim.
- A supplies successfully read Documents from the task's authorized Workspace and
  excludes notices from candidates. D's structural validation cannot authenticate
  the source. Unresolved arguments or failed reads are not empty candidate sets.
- No disk reads/writes, scanning, C private helper imports or version selection.

#### Filename matching rules

1. `filename` is a single name with neither `/` nor `\`. Reject empty names,
   whitespace-only names, all-dot names and names ending with a dot.
2. Split at the last dot only when both its prefix and suffix are nonempty.
   The stem is the prefix and the extension includes the dot. With no such split,
   the entire filename is the stem and the extension is `""`.
   `.gitignore` and `.env` have no extension; `.config.json` has stem `.config`
   and extension `.json`; `材料.tar.gz` has stem `材料.tar`, extension `.gz`.
   Reject a split whose stem consists only of dots: `..foo` would split to stem
   `.` and extension `.foo`, so it is invalid. `.env` remains stem `.env` with
   extension `""`; `.config.json` remains stem `.config`, extension `.json`.
3. `Document.extension` must equal the derived extension ignoring **ASCII letter
   case only**; an extensionless name requires `""`. Mismatch fails the whole call,
   rather than silently repairing or ignoring the candidate. Do not restrict
   extensions to C's current supported parser formats.
4. Compare the stem and requirement exactly: case-sensitive, no whitespace
   trimming/collapsing and no Unicode normalization or full-width folding.
5. Besides exact matching, remove at most the rightmost terminal suffix of the
   form `_vN`, `_vN.N` or `_vN.N.N`: lowercase ASCII `v`, ASCII digits `0-9`,
   leading zeros permitted, strict end-of-string, and a nonempty remaining stem.
   Do not remove other suffixes or repeatedly strip. `申请表_v1_v2.pdf` can match
   `申请表_v1`, but cannot be stripped twice to match `申请表`.
6. Exact match first means only the decision order for **one candidate**. An exact
   hit must not suppress other candidates matching through a version suffix.
   `申请表.txt` and `申请表_v01.2.pdf` both remain candidates for `申请表`.
   No arbitrary substring match: `学生证办理说明` does not match `学生证`.
7. These rules establish filename relationships only. Do not infer a newest file,
   redo C Version reasoning or silently turn `newest_candidate=null` into a choice.

#### Success data and ordering invariants

The success data has exactly these fields:

- `required_documents: string[]`: stably deduplicated requirements.
- `matched: [{requirement, documents: [{file_id, path, filename}]}]`.
- `missing: string[]`.

Every deduplicated requirement enters exactly one of matched or missing. Both
arrays follow requirement order. Each matched.documents is nonempty and retains
all matching candidates in original candidate order after shared deduplication.
Zero candidates is expressed by missing; one/many by matched.documents length.
Build each requirement's candidate relation independently; never allocate and
remove candidates across requirements. For requirements `申请表_v1` and
`申请表_v1_v2`, the same `申请表_v1_v2.pdf` appears in both candidate lists
(suffix match and exact match respectively). This does not mean one file fulfills
two submission requirements, any quantity requirement or a combined-proof rule.

All Phase 1 matches are **not content-reviewed**, as a uniform capability limit;
no `verified`, `unresolved`, `category` or `aliases` field is introduced. Filename
association is not approval of contents, signatures, validity period, quantity or
truthfulness. `missing` means only no filename-rule match in this candidate set,
not absence from the Workspace or machine. Its display meaning is
**“本次未找到文件名候选”**, not content review or authenticity approval.

Empty requirements succeed with three empty arrays, not a claim of completeness.
Nonempty requirements with empty candidates succeed with every deduplicated
requirement in missing. `matched=[]` alone does not express execution state.

#### Failure and A/B integration

- Standard failure: `success=false`, `tool="match_requirements"`, `data=null`,
  nonempty readable message/error. Invalid inputs and identity contradictions are
  failures, not missing items; business matching must not run and no partial
  matched/missing output is returned.
- A retains the complete ToolResult in TaskSnapshot.results. Failure sets the task
  to failed, preserves the error and stops subsequent file operations; a report
  for an uncompleted task returns 409.
- On successful matching only, map data.missing to FinalReport.missing_items.
  A later failure must not fall back to an older successful matching result.
- Not-run is expressed by execution state/result absence, never fabricated success
  with empty arrays. Failed/not-run must not be described as no missing items.
  Successful empty requirements mean no identified requirements, not all materials
  ready. B must preserve this distinction without treating candidates as approved.

#### Limits and deferred scope

The confirmed v1 boundary has no matching-specific resource quotas. Do not inherit Version
limits or promise arbitrary-scale processing. Future limits must be validated on
original input before comparison/deduplication, not after duplicates are removed.
A's candidate-reading limits are orchestration limits only; they are not this
tool's resource quotas or capacity guarantees.

Phase 2 alias matching, common-name normalization and semantic proof association
remain required, unfinished work. Phase 1 is not generalized semantic matching.
Package and classify_files contracts are outside this change.

#### Complete JSON examples

These illustrate the team-confirmed contract, not implemented tool output. IDs are illustrative.

Request:

```json
{
  "required_documents": ["申请表", "实践证明", "申请表"],
  "candidate_documents": [
    {
      "file_id": "file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "path": "/work/申请表.txt",
      "filename": "申请表.txt",
      "extension": ".txt",
      "text": "example",
      "size": 7,
      "modified_time": "2026-10-18T08:00:00+00:00",
      "metadata": {}
    },
    {
      "file_id": "file_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "path": "/work/申请表_v01.2.PDF",
      "filename": "申请表_v01.2.PDF",
      "extension": ".pdf",
      "text": "example",
      "size": 7,
      "modified_time": "2026-10-18T09:00:00+00:00",
      "metadata": {}
    }
  ]
}
```

Success (retains both exact and suffix candidates):

```json
{
  "success": true,
  "tool": "match_requirements",
  "data": {
    "required_documents": ["申请表", "实践证明"],
    "matched": [
      {
        "requirement": "申请表",
        "documents": [
          {"file_id": "file_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "path": "/work/申请表.txt", "filename": "申请表.txt"},
          {"file_id": "file_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "path": "/work/申请表_v01.2.PDF", "filename": "申请表_v01.2.PDF"}
        ]
      }
    ],
    "missing": ["实践证明"]
  },
  "message": "Requirement candidate matching completed",
  "error": null
}
```

Empty requirements request and success:

```json
{"required_documents": [], "candidate_documents": []}
```

```json
{
  "success": true,
  "tool": "match_requirements",
  "data": {"required_documents": [], "matched": [], "missing": []},
  "message": "Requirement candidate matching completed",
  "error": null
}
```

Empty candidates request and success:

```json
{"required_documents": ["申请表", "实践证明", "申请表"], "candidate_documents": []}
```

```json
{
  "success": true,
  "tool": "match_requirements",
  "data": {"required_documents": ["申请表", "实践证明"], "matched": [], "missing": ["申请表", "实践证明"]},
  "message": "Requirement candidate matching completed",
  "error": null
}
```

Invalid request and failure (exact error wording is illustrative):

```json
{"required_documents": [null], "candidate_documents": []}
```

```json
{
  "success": false,
  "tool": "match_requirements",
  "data": null,
  "message": "Requirement candidate matching failed",
  "error": "required_documents[0] must be a nonempty string"
}
```

A contradictory same-ID snapshot uses the same failure envelope with a readable
error identifying its file_id and candidate input position, never partial data.

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

### plan_package / build_package — minimal Package proposal

**架构已确认，具体 schema 待 A/B 复核。** All interfaces, fields and HTTP
increments in this section are **proposed**, not implemented/exported/registered
capabilities. The overall architecture has A/B acceptance; the UUID lifecycle,
digest exclusions, Package-local unresolved records, Snapshot extension,
restricted report writer and partial-failure correlation below remain concrete
schema proposals for A/B review. This proposal replaces the earlier provisional
four-field build_package sketch; it does not change Matching, classify_files or
Phase 2.

#### Actual baseline and ownership

At dev `43a723ab0fef9396fa5f0c278b3b28107093df36`, A freezes concrete
create_folder/copy_file/move_file operations and rejects caller-supplied approved.
TaskService verifies copied target bytes against the then-current source SHA-256;
that is not a comparison against an approved source snapshot. Public verify_result
checks workspace-relative existence only. Neither a Package router nor a report
write operation exists. The approve HTTP route accepts exactly preview_id today.
PR #27 at `62c1c0d95d015d1607b1b05241c9de4fc80ef4de` is read-only reference
for matching integration, not merged baseline capability.

D owns plan validation, read-only snapshots and frozen report rendering. A owns
service authority, approval, composite execution, filesystem defenses and result
recording. B owns preview/risk acceptance and actual-result display. C Version
results remain evidence/recommendations, not selected_files or approval.

#### Proposed planning request

`plan_package(task, selected_files, destination, analysis) -> ToolResult`, risk low.
It may read selected sources for preflight/snapshots, but creates no directories,
copies no files and writes no report. Planning success means a ready-to-preview
plan only, never completed packaging or guaranteed future execution.

| Field | Proposed shape and authority |
| --- | --- |
| task | Exactly `{task_id, user_goal, workspace}`. A obtains these from its authoritative Task record, checks equality at the boundary and binds them to the execution. D checks structure/scope but cannot authenticate a caller. No second context object. |
| selected_files | Nonempty ordered array of `{source:{file_id,path,filename}, requirements:string[], reason:string}` explicitly chosen by the user/caller. reason records the selection basis, not content approval. Candidate matches or newest_candidate do not create a selection. |
| destination | Final task-neutral package directory, absolute native-host path inside task.workspace. Do not append a fixed Hackathon name. |
| analysis | Exactly four slots: extract_requirements, match_requirements, detect_conflicts, compare_versions. Each is null (not run), or `{result_index, result:ToolResult}` from this Task's current effective execution. A validates provenance/freshness; a failed latest result cannot be replaced with an older success. Slot/tool names must agree. |

All request/manifest objects have exactly their listed keys; source references
have exactly file_id/path/filename, all nonempty built-in strings. Requirements
are nonempty/non-whitespace built-in strings, stably deduplicated without rewriting;
reason is nonempty. A successful extraction constrains selection requirements to
its checklist; an empty selection requirements array means an explicitly selected
extra, not inferred satisfaction. result_index/selected_file_index/selected_file_indices entries
are nonnegative exact integers (not bool), referencing their declared arrays.
Snapshot size is a nonnegative exact integer; mtime_ns is an exact integer;
SHA-256 hex values have exactly 64 lowercase hex digits.
This is the only analysis evidence representation. Do not add parallel
context/decision/result copies. Requirements are read from successful extraction
results; unknown requirements stay unknown, not a fabricated successful empty
checklist. Each successful match result must refer to the same effective
requirements; incompatible supplied evidence fails planning. Existing ordinary
Agent failure policy is unchanged: this proposal does not resume a failed Task.
Displaying failed analysis in a new planning/review task does not authorize its
execution; A must explicitly admit and bind that context under this proposal.

Validate complete strict JSON before tool-specific validation/deduplication.
Use file_id identity and all supplied reference fields; contradictions fail the
whole call. Equal selections with identical requirements/reason may be stably
deduplicated; differing records for one ID fail, rather than choosing by order.
A verifies references against authorized task files. Do not infer a path/ID
bijection, rebuild C IDs or equate file_id with source content.

Conservative v1 path proposal: native local absolute paths only, no foreign drive,
UNC/device/URI formats, traversal components or links/reparse points in workspace,
sources or destination ancestors. Sources must be readable regular files. Reject
source/target overlap, an occupied package directory (including dangling links),
case/Unicode-equivalent target collisions and reserved PACKAGE_REPORT.md targets.
For target collision detection only use NFC + casefold without rewriting names;
reject Windows-reserved names, controls, separators and trailing dots/spaces.
This is proposed Package safety validation, not a change to Matching name rules.
Target parent must already exist; v1 creates only the final package directory.

#### Proposed frozen plan: one authoritative manifest

Successful plan_package data is exactly `{plan, plan_sha256}`. The frozen plan
uses the single team-required structure below; no parallel files/issues arrays.
`plan_sha256` is an independent digest, not a replacement for plan_id.

plan_id is generated by D's planning layer on each successful plan as
`"package_plan_" + uuid.uuid4().hex` (lowercase 32-hex suffix). This generator and
lifecycle are proposed for A/B review. Repeating identical input need not produce
the same UUID; neither tests nor callers may assume the whole plan_package output
is deterministic. Content serialization/digest and operation order are defined
separately below. The ID is opaque, not path-derived or a content hash. A registers it under the authoritative task_id;
callers do not supply it to plan_package or create authority by inventing an ID.
The server never rebinds an existing ID to different content. A new selection,
path, snapshot, analysis/risk or report requires a new plan_id and preview; the
previous executable registration/preview becomes stale. Task termination,
rejection, completion/failure of the single authorized execution, or loss of A's
in-memory task registry prevents reuse. Consuming preview_id starts that authorized
execution; it does not invalidate its own in-progress child operations. Retained IDs/results are historical evidence, not reusable approval.

`plan` contains:

| Field | Proposed meaning |
| --- | --- |
| plan_id | Server-registered, task-scoped plan identifier generated as above; never an authorization credential. |
| task | Same authoritative task tuple, one copy. |
| destination | Final package path; planned until build succeeds. |
| selected_files | Unique source/target/snapshot mapping in selected order: `{source, requirements, reason, target, snapshot:{size,mtime_ns,sha256}}`. Enriches request selected_files without retaining a second copy. Snapshots reflect a stable read before preview. |
| analysis | The four evidence slots above, frozen verbatim with original result indices. |
| missing | Stable string[] of known filename-candidate gaps from the current successful match_requirements result; provenance stays in analysis.match_requirements. A manual selection does not silently rewrite that result. Empty does not prove completeness when an analysis is unknown/failed. |
| unresolved | Proposed Package-local array `{kind, text, source_tool, source_result_index, documents}`. kind is selection_pending, version_undecided, conflict, analysis_not_run or analysis_failed. source_tool names the affected analysis; source_result_index is null only for not-run. documents contains ordered existing references, possibly empty. NOT a global shared unresolved schema. |
| report | Exactly `{path, content, sha256}`; full frozen Markdown body and bytes digest. |
| operations | Ordered descriptors: `{step_id,kind}` for create_directory/write_report/verify; `{step_id,kind:"copy",selected_file_index}` for each selected_files entry. References resolve only against this frozen manifest. No second copy of path/hash facts. |
| verification_targets | `{selected_file_indices:[0,...], report:true, exact_directory_entries:true}`. Indices reference selected_files, report references report.path/sha256. Proposed Package verification format, NOT directly public verify_result.expected. |

Operation order is create_directory, copies in selected_files order, write_report, verify.
A expands descriptors into concrete frozen PlanSteps before approval: create_folder
uses destination; each copy_file uses selected_files[i].source.path and target; report write
uses the frozen report; verification uses all target mappings and approved digests.
Step IDs are package_001, package_002, etc., deterministically assigned in order.
Concrete child previews describe the composite build; they must not also be
scheduled as independent top-level steps and executed a second time. A's adapter
owns this expansion/execution under one Package gate, which the baseline executor
does not yet support. This expansion is deterministic, not runtime selection/replanning. All selected-file
indices must occur exactly once in copy order and verification; fixed operations
occur exactly once. No extra files, operations or unapproved field substitutions.

Derive missing/unresolved once from the frozen effective evidence:

- Successful match_requirements: copy its known missing names, stably deduplicated,
  to missing. Do not also create an unresolved item for the same missing fact.
- A matching slot that is null or failed yields no invented missing names; missing
  is empty for unknown gaps and unresolved must contain analysis_not_run or
  analysis_failed respectively, identifying the tool and current failed index.
- For every other null analysis slot, add analysis_not_run with source_tool and
  null source_result_index; for a failed ToolResult add analysis_failed with its
  source index. Neither is a successful empty analysis. Success with empty output
  creates no such unknown/failure record.
- A successful nonempty detect_conflicts result creates conflict unresolved
  records tied to that result. Do not choose the correct notice automatically.
- A required candidate group with no explicit selected file creates
  selection_pending, unless the requirement is already listed in missing.
  A Version group with newest_candidate=null creates version_undecided unless
  the user explicitly resolved its selection; recommendation never selects a file.
- Unused alternatives remain in frozen analysis/report, not automatically risks
  when a user's explicit choice has resolved the group. Deduplicate the same
  unresolved cause/source/affected references; do not produce parallel issues.

These Package-only unresolved kinds/records and derivation details remain for A/B
review. No empty missing/unresolved pair may conceal absent or failed analysis.

#### Source, report and plan byte digests

- Source sha256 is lowercase 64-hex SHA-256 over exact file bytes, streaming.
  size counts bytes; mtime_ns is an integer observation, not proof of content.
  Compare descriptor/path identity and observable state before/after reading;
  unstable reads fail without partial snapshots. Preflight is not approval and
  cannot eliminate races; A must defend/recheck during execution.
- Report content is the entire decoded string, LF line endings only; reject CR
  rather than silently convert it. Its bytes are content.encode("utf-8", "strict"),
  no BOM, no added/removed final newline and no Unicode normalization. sha256 is
  lowercase 64-hex over those exact bytes. Encoding or digest mismatch fails.
- Plan digest is `"sha256:" + sha256(canonical_bytes).hexdigest()` where:

```python
canonical_bytes = json.dumps(
    {key: value for key, value in plan.items() if key != "plan_id"},
    ensure_ascii=False, sort_keys=True,
    separators=(",", ":"), allow_nan=False,
).encode("utf-8", "strict")
```

All plan content fields except plan_id and all nested supplied members
participate, including task, selected_files/snapshots, missing, unresolved,
report content/digest, analysis and ordered descriptors. Objects sort
keys recursively; arrays retain order. No whitespace, BOM, trailing newline or
normalization is added. Python standard-json scalar serialization above is the
reference algorithm; cross-language implementations must match its bytes. Reject
non-JSON/nonfinite/cyclic values, invalid schemas, encoding or serialization
failures; no default=str, truncation or omitted fields. No Package quotas have
been agreed; this is not an arbitrary-scale guarantee.

Excluded fields are exactly plan.plan_id, the outer ToolResult envelope and
data.plan_sha256. No other plan content is excluded. There is no digest member
inside plan and no circular preview_id input. Same content under a new ID can
have the same content digest; A still binds and checks the distinct ID. Report
hash is checked before computing the plan hash. The server recomputes and freezes
its own manifest; client digest claims are never trusted. Digests identify content,
not caller authority, user choice or approval. preview_id remains generated by A
and binds task_id, plan_id, plan_sha256, the full server-frozen plan,
concrete operations and actual approval state. Neither plan_id nor digest grants
authority or substitutes for the same-preview approval.

#### Frozen report and incomplete approval (proposed HTTP increment)

The report describes goal, requirements or unknown state, selected files/reasons,
unselected candidates, missing/unresolved evidence and planned operations. It prominently says
"审批前冻结的计划记录；不证明实际执行或验证成功". Freeze full content before
approval and write those exact bytes afterwards: no rerendering, timestamps or
execution facts injected after approval. Actual statuses/hashes/checks live in
Snapshot/ToolResult. A report containing final execution status would require a
separately confirmed mechanism; this proposal does not promise both immutable full
content and execution-time body updates. Escape Markdown/HTML/newlines in input.

Proposed minimal approve request extends only the existing approve route:
`{preview_id:string, accept_incomplete?:boolean}`, exact built-in bool, default
false. Reject unknown fields/invalid types with 400. Reject still accepts only
preview_id; do not add acceptance to rejection.

- A validates task existence (404), awaiting_approval/current preview (409), then
  checks this preview's frozen missing/unresolved before consuming approval.
- For a Package preview with nonempty missing or unresolved, true explicitly
  accepts exactly the frozen missing names and unresolved texts/sources/references. An incomplete package is allowed
  only with nonempty explicit selection and this same-preview risk acceptance.
- Missing/false acceptance with either list nonempty returns 409, does not consume preview_id,
  change awaiting_approval or execute anything; the same still-valid preview may
  be retried with true. This acceptance check must precede current decide()'s
  preview consumption. It does not revive a stale/changed/failed Task.
- Both lists empty: ordinary preview approval works without the new field. True never
  creates a permanent authorization or substitutes for file selection.
- Stale/duplicate/wrong previews return 409 without operations; changed selection,
  path, content snapshot, missing/unresolved or report requires a new plan/preview and approval.
  Reject follows existing failed/skipped behavior. Rejected tasks do not retry.

No public approved=true, approval token or caller-supplied preview_id is accepted
by either Package tool. Approval is exclusively A's server-side boundary.

#### Proposed build input, restricted report operation and result ownership

Replace the provisional build_package input with exactly
`{task_id:string, plan_id:string, plan_sha256:string}`. A looks up the plan by
task_id and plan_id and checks its content digest; neither is a credential. A's medium-risk router adapter retrieves the server-frozen
plan for that task and verifies the current consumed approval context. A standalone
call with a forged/copied hash or no current authorized execution must fail without
mutation. There is no public plan body, approved flag or caller-selected output
path in the build request. New approval is required for any changed plan.

D supplies the planning API and validation logic through public agreed boundaries;
A's composite execution adapter invokes approved file tools and records their
results. D does not import A/C private implementations or create a second approval
system. Exact adapter wiring is an A/D implementation decision, not a fake Python
approved parameter. The build gate covers the entire ordered Package, including
its otherwise read-only final verification, before final success is possible.

Proposed restricted medium-risk tool:
write_package_report(task_id, plan_id, plan_sha256).
Only A invokes it inside the same Package approval context. It retrieves exactly
the bound report.path/content/sha256, checks scope and writes exclusive binary
bytes. It accepts no arbitrary path or content, cannot render/overwrite a report,
and cannot run separately by merely supplying a digest. Success data is exactly
`{path:string, sha256:string}` describing the bytes actually written; failure
uses data=null. Add its runtime support,
preview validation and tool contract only after review; it is unavailable today.

Before mutations and again at use, check source bytes against approved snapshots,
workspace/ancestor identities and destination vacancy. Reject links, changed
sources, occupied targets or scope changes; do not silently recompute hashes,
rename, choose versions, overwrite or auto-retry. Use exclusive final directory
and file creation; defend parent replacement/TOCTOU with platform-appropriate
handles. A current copy_file alone does not supply these guarantees.

Execute descriptors serially; append each attempted directory/copy/report/verify
ToolResult exactly once. On first failure stop remaining operations, then emit one
final failed build_package ToolResult, data=null. If all succeed, emit final build
success only after verification. Verification compares material bytes with the
**approved source digest**, report bytes with the frozen report digest, correct
paths/types, and the exact expected flat file set. Presence-only verification or
source-vs-target equality at the end is insufficient. No final re-render of report.

Proposed minimal Snapshot extension (not currently implemented):
`package_execution:{plan_id, plan_sha256, operation_results:[{step_id,result_index}], final_result_index}`,
nullable when no Package execution exists; final_result_index is null until a
terminal result. It correlates existing results, not duplicate envelopes or a new
Task status. A alone appends child results and owns this mapping; the executor
appends the adapter's returned final build result once, then records its index.
D returns its planning result but never also appends children. A must implement
one append owner/ordered commit to avoid duplicate records or lost failed children.
No callback/object capability is accepted in public JSON. All child/final results
remain standard ToolResult. New nested result schemas are specified below by
examples: create_folder/copy_file keep existing data; report write returns its
actual path and digest; package verify_result uses ordinary checks/passed with
scope labels for source-snapshot, material-digest, report-digest and file-set.

On partial failure keep child results, mark Task failed and expose Snapshot; final
build data=null and FinalReport GET returns 409. No transaction rollback or
automatic retry is promised. Existing copy_file may unlink its own newly-created
failed-copy fragment; retaining fragments vs permitting that narrowly scoped
cleanup is an explicit A/D decision before execution implementation. Never delete
sources, preexisting files or recursively clean a package. Cleanup failure must be
visible, not mislabeled as rollback success. New attempts require reinspection,
new plan/preview and explicit approval, not silent reuse of a partial directory.

Successful build data is exactly `{plan_id,plan_sha256,package_path,generated_files,
report_path,verification_result_index}`. generated_files lists only created
absolute file paths in copy order followed by report; it does not assign new
Document IDs or include directories. The indexed successful verify_result holds
actual checks. Package success means operations/verification completed, not
material completeness/authenticity approval; missing/unresolved remain in the frozen
report and analysis. A may map actual package_path/operations into FinalReport
only after completed; it must not label a planned path as an actual package.

#### Complete proposed examples

Examples below are illustrative schema/byte-digest fixtures, NOT evidence of an
implemented Package. They include full manifest, report body and computed hashes.

##### Complete plan

Request:

```json
{
  "task": {"task_id": "task_complete", "user_goal": "准备课程结题材料", "workspace": "/work"},
  "selected_files": [
    {
      "source": {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"},
      "requirements": ["结题报告"],
      "reason": "用户明确选择"
    }
  ],
  "destination": "/work/课程结题材料包",
  "analysis": {
    "extract_requirements": {
      "result_index": 0,
      "result": {
        "success": true,
        "tool": "extract_requirements",
        "data": {
          "required_documents": ["结题报告"]
        },
        "message": "extract_requirements completed",
        "error": null
      }
    },
    "match_requirements": {
      "result_index": 1,
      "result": {
        "success": true,
        "tool": "match_requirements",
        "data": {
          "required_documents": ["结题报告"],
          "matched": [
            {
              "requirement": "结题报告",
              "documents": [
                {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"}
              ]
            }
          ],
          "missing": []
        },
        "message": "match_requirements completed",
        "error": null
      }
    },
    "detect_conflicts": {
      "result_index": 2,
      "result": {
        "success": true,
        "tool": "detect_conflicts",
        "data": {
          "conflicts": []
        },
        "message": "detect_conflicts completed",
        "error": null
      }
    },
    "compare_versions": {
      "result_index": 3,
      "result": {
        "success": true,
        "tool": "compare_versions",
        "data": {
          "groups": []
        },
        "message": "compare_versions completed",
        "error": null
      }
    }
  }
}
```

Planning success:

```json
{
  "success": true,
  "tool": "plan_package",
  "data": {
    "plan": {
      "plan_id": "package_plan_11111111111111111111111111111111",
      "task": {"task_id": "task_complete", "user_goal": "准备课程结题材料", "workspace": "/work"},
      "destination": "/work/课程结题材料包",
      "selected_files": [
        {
          "source": {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"},
          "requirements": ["结题报告"],
          "reason": "用户明确选择",
          "target": "/work/课程结题材料包/结题报告.txt",
          "snapshot": {"size": 6, "mtime_ns": 1792310400000000000, "sha256": "b6a98d9ce9a2d9149288fa3df42d377c3e42737afdcdaf714e33c0a100b51060"}
        }
      ],
      "analysis": {
        "extract_requirements": {
          "result_index": 0,
          "result": {
            "success": true,
            "tool": "extract_requirements",
            "data": {
              "required_documents": ["结题报告"]
            },
            "message": "extract_requirements completed",
            "error": null
          }
        },
        "match_requirements": {
          "result_index": 1,
          "result": {
            "success": true,
            "tool": "match_requirements",
            "data": {
              "required_documents": ["结题报告"],
              "matched": [
                {
                  "requirement": "结题报告",
                  "documents": [
                    {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"}
                  ]
                }
              ],
              "missing": []
            },
            "message": "match_requirements completed",
            "error": null
          }
        },
        "detect_conflicts": {
          "result_index": 2,
          "result": {
            "success": true,
            "tool": "detect_conflicts",
            "data": {
              "conflicts": []
            },
            "message": "detect_conflicts completed",
            "error": null
          }
        },
        "compare_versions": {
          "result_index": 3,
          "result": {
            "success": true,
            "tool": "compare_versions",
            "data": {
              "groups": []
            },
            "message": "compare_versions completed",
            "error": null
          }
        }
      },
      "missing": [],
      "unresolved": [],
      "report": {
        "path": "/work/课程结题材料包/PACKAGE_REPORT.md",
        "content": "# 课程结题材料包计划\n\n审批前冻结的计划记录；不证明实际执行或验证成功。\n\n任务目标：准备课程结题材料\n要求：结题报告\n计划复制：/work/结题报告.txt → /work/课程结题材料包/结题报告.txt；选择依据：用户明确选择\n调用方提供成功分析：未报告缺项、冲突或版本未决；不代表材料审核通过。\n分析来源：当前任务 results[0..3]；本报告不记录实际执行或验证状态。\n计划顺序：创建目录、逐项复制、写入本报告、验证。\n",
        "sha256": "85942afe005f7356775039142ff8bc7cee63b077bdd57ab30f8f2752ff8b5a9c"
      },
      "operations": [
        {"kind": "create_directory", "step_id": "package_001"},
        {"kind": "copy", "step_id": "package_002", "selected_file_index": 0},
        {"kind": "write_report", "step_id": "package_003"},
        {"kind": "verify", "step_id": "package_004"}
      ],
      "verification_targets": {
        "report": true,
        "exact_directory_entries": true,
        "selected_file_indices": [0]
      }
    },
    "plan_sha256": "sha256:eeedf0e37ea8f49ad452ebfea187cb63859b92c3b82b098223a3590801d76cb6"
  },
  "message": "plan_package completed",
  "error": null
}
```

##### Incomplete plan with a missing item and an unselected requirement

Request:

```json
{
  "task": {"task_id": "task_incomplete", "user_goal": "准备课程结题材料", "workspace": "/work"},
  "selected_files": [
    {
      "source": {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"},
      "requirements": ["结题报告"],
      "reason": "用户明确选择"
    },
    {
      "source": {"file_id": "file_14292727e6298fa05953a29ad76c1c05b82abcfe0f09b2c07d2dc36710465d4b", "path": "/work/原始记录.txt", "filename": "原始记录.txt"},
      "requirements": ["原始记录"],
      "reason": "用户明确选择"
    }
  ],
  "destination": "/work/课程结题材料包",
  "analysis": {
    "extract_requirements": {
      "result_index": 0,
      "result": {
        "success": true,
        "tool": "extract_requirements",
        "data": {
          "required_documents": ["结题报告", "原始记录", "签字页", "测试记录"]
        },
        "message": "extract_requirements completed",
        "error": null
      }
    },
    "match_requirements": {
      "result_index": 1,
      "result": {
        "success": true,
        "tool": "match_requirements",
        "data": {
          "required_documents": ["结题报告", "原始记录", "签字页", "测试记录"],
          "matched": [
            {
              "requirement": "结题报告",
              "documents": [
                {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"}
              ]
            },
            {
              "requirement": "原始记录",
              "documents": [
                {"file_id": "file_14292727e6298fa05953a29ad76c1c05b82abcfe0f09b2c07d2dc36710465d4b", "path": "/work/原始记录.txt", "filename": "原始记录.txt"}
              ]
            },
            {
              "requirement": "测试记录",
              "documents": [
                {"file_id": "file_9d85cfd4903f0a5eefc95606f8d9fd6501e6e17d05222529be9024bd9dde4a70", "path": "/work/测试记录候选.txt", "filename": "测试记录候选.txt"}
              ]
            }
          ],
          "missing": ["签字页"]
        },
        "message": "match_requirements completed",
        "error": null
      }
    },
    "detect_conflicts": {
      "result_index": 2,
      "result": {
        "success": true,
        "tool": "detect_conflicts",
        "data": {
          "conflicts": []
        },
        "message": "detect_conflicts completed",
        "error": null
      }
    },
    "compare_versions": {
      "result_index": 3,
      "result": {
        "success": true,
        "tool": "compare_versions",
        "data": {
          "groups": []
        },
        "message": "compare_versions completed",
        "error": null
      }
    }
  }
}
```

Planning success:

```json
{
  "success": true,
  "tool": "plan_package",
  "data": {
    "plan": {
      "plan_id": "package_plan_22222222222222222222222222222222",
      "task": {"task_id": "task_incomplete", "user_goal": "准备课程结题材料", "workspace": "/work"},
      "destination": "/work/课程结题材料包",
      "selected_files": [
        {
          "source": {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"},
          "requirements": ["结题报告"],
          "reason": "用户明确选择",
          "target": "/work/课程结题材料包/结题报告.txt",
          "snapshot": {"size": 6, "mtime_ns": 1792310400000000000, "sha256": "b6a98d9ce9a2d9149288fa3df42d377c3e42737afdcdaf714e33c0a100b51060"}
        },
        {
          "source": {"file_id": "file_14292727e6298fa05953a29ad76c1c05b82abcfe0f09b2c07d2dc36710465d4b", "path": "/work/原始记录.txt", "filename": "原始记录.txt"},
          "requirements": ["原始记录"],
          "reason": "用户明确选择",
          "target": "/work/课程结题材料包/原始记录.txt",
          "snapshot": {"size": 5, "mtime_ns": 1792310400000000001, "sha256": "f2c82decdd7181cf98945929a62598db7e6b477e11f6e0eb0ae97020eff151ad"}
        }
      ],
      "analysis": {
        "extract_requirements": {
          "result_index": 0,
          "result": {
            "success": true,
            "tool": "extract_requirements",
            "data": {
              "required_documents": ["结题报告", "原始记录", "签字页", "测试记录"]
            },
            "message": "extract_requirements completed",
            "error": null
          }
        },
        "match_requirements": {
          "result_index": 1,
          "result": {
            "success": true,
            "tool": "match_requirements",
            "data": {
              "required_documents": ["结题报告", "原始记录", "签字页", "测试记录"],
              "matched": [
                {
                  "requirement": "结题报告",
                  "documents": [
                    {"file_id": "file_e51eaa4886a308a14b0d2bed7e0062a6ec7b05548ed473cb2115936f180708b2", "path": "/work/结题报告.txt", "filename": "结题报告.txt"}
                  ]
                },
                {
                  "requirement": "原始记录",
                  "documents": [
                    {"file_id": "file_14292727e6298fa05953a29ad76c1c05b82abcfe0f09b2c07d2dc36710465d4b", "path": "/work/原始记录.txt", "filename": "原始记录.txt"}
                  ]
                },
                {
                  "requirement": "测试记录",
                  "documents": [
                    {"file_id": "file_9d85cfd4903f0a5eefc95606f8d9fd6501e6e17d05222529be9024bd9dde4a70", "path": "/work/测试记录候选.txt", "filename": "测试记录候选.txt"}
                  ]
                }
              ],
              "missing": ["签字页"]
            },
            "message": "match_requirements completed",
            "error": null
          }
        },
        "detect_conflicts": {
          "result_index": 2,
          "result": {
            "success": true,
            "tool": "detect_conflicts",
            "data": {
              "conflicts": []
            },
            "message": "detect_conflicts completed",
            "error": null
          }
        },
        "compare_versions": {
          "result_index": 3,
          "result": {
            "success": true,
            "tool": "compare_versions",
            "data": {
              "groups": []
            },
            "message": "compare_versions completed",
            "error": null
          }
        }
      },
      "missing": ["签字页"],
      "unresolved": [
        {
          "kind": "selection_pending",
          "text": "测试记录候选尚未被明确选定",
          "source_result_index": 1,
          "documents": [
            {"file_id": "file_9d85cfd4903f0a5eefc95606f8d9fd6501e6e17d05222529be9024bd9dde4a70", "path": "/work/测试记录候选.txt", "filename": "测试记录候选.txt"}
          ],
          "source_tool": "match_requirements"
        }
      ],
      "report": {
        "path": "/work/课程结题材料包/PACKAGE_REPORT.md",
        "content": "# 课程结题材料包计划\n\n审批前冻结的计划记录；不证明实际执行或验证成功。\n\n任务目标：准备课程结题材料\n要求：结题报告、原始记录、签字页、测试记录\n计划复制：/work/结题报告.txt → /work/课程结题材料包/结题报告.txt；选择依据：用户明确选择\n计划复制：/work/原始记录.txt → /work/课程结题材料包/原始记录.txt；选择依据：用户明确选择\n缺项：签字页（匹配结果索引 1）；未选：/work/测试记录候选.txt（匹配结果索引 1）。\n未决：测试记录尚未选定。需同次审批明确接受上述两项风险。\n分析来源：当前任务 results[0..3]；本报告不记录实际执行或验证状态。\n计划顺序：创建目录、逐项复制、写入本报告、验证。\n",
        "sha256": "fc7436c6d73f8bdf0bddf99b108bfe98bded1d7a48c7401d236c75110e228fed"
      },
      "operations": [
        {"kind": "create_directory", "step_id": "package_001"},
        {"kind": "copy", "step_id": "package_002", "selected_file_index": 0},
        {"kind": "copy", "step_id": "package_003", "selected_file_index": 1},
        {"kind": "write_report", "step_id": "package_004"},
        {"kind": "verify", "step_id": "package_005"}
      ],
      "verification_targets": {
        "report": true,
        "exact_directory_entries": true,
        "selected_file_indices": [0, 1]
      }
    },
    "plan_sha256": "sha256:51364b3e62d349121ce6a7adc4f0a8f395afefbf53a08aaed68ff4ee6a2c8133"
  },
  "message": "plan_package completed",
  "error": null
}
```

##### Approval with and without explicit acceptance

The following HTTP behavior is proposed, not supported by the baseline route.

POST /api/agent/tasks/task_incomplete/approve:

```json
{"preview_id": "sha256:server-generated-preview"}
```

Response 409 (Task remains awaiting_approval; preview is unconsumed):

```json
{"detail": "Explicit acceptance required for the frozen missing and undecided items"}
```

Retry against the same still-valid preview:

```json
{"preview_id": "sha256:server-generated-preview", "accept_incomplete": true}
```

Proposed build input, supplied by A inside that authorized execution:

```json
{"task_id": "task_incomplete", "plan_sha256": "sha256:51364b3e62d349121ce6a7adc4f0a8f395afefbf53a08aaed68ff4ee6a2c8133", "plan_id": "package_plan_22222222222222222222222222222222"}
```

##### Actual execution success (illustrative; all operations must really succeed)

Verification at results[9]:

```json
{
  "success": true,
  "tool": "verify_result",
  "data": {
    "checks": [
      {"path": "/work/课程结题材料包/结题报告.txt", "kind": "material-digest", "passed": true},
      {"path": "/work/课程结题材料包/原始记录.txt", "kind": "material-digest", "passed": true},
      {"path": "/work/课程结题材料包/PACKAGE_REPORT.md", "kind": "report-digest", "passed": true},
      {"path": "/work/课程结题材料包", "kind": "file-set", "passed": true},
      {"path": "/work", "kind": "source-snapshot", "passed": true}
    ],
    "passed": true
  },
  "message": "verify_result completed",
  "error": null
}
```

Final result at results[10], after explicit risk acceptance and successful children:

```json
{
  "success": true,
  "tool": "build_package",
  "data": {
    "plan_sha256": "sha256:51364b3e62d349121ce6a7adc4f0a8f395afefbf53a08aaed68ff4ee6a2c8133",
    "package_path": "/work/课程结题材料包",
    "generated_files": ["/work/课程结题材料包/结题报告.txt", "/work/课程结题材料包/原始记录.txt", "/work/课程结题材料包/PACKAGE_REPORT.md"],
    "report_path": "/work/课程结题材料包/PACKAGE_REPORT.md",
    "verification_result_index": 9,
    "plan_id": "package_plan_22222222222222222222222222222222"
  },
  "message": "build_package completed",
  "error": null
}
```

##### Second copy fails: proposed Snapshot metadata and child results

Indices 0..3 are current analysis, 4 is the plan, 5 directory, 6 first copy,
7 failed second copy, 8 final failed build. Report and verification are not run.
The new package_execution member below is explicitly proposed, not existing API.

Snapshot metadata (results omitted here only to avoid repeating the frozen plan):

```json
{
  "task": {"task_id": "task_incomplete", "user_goal": "准备课程结题材料", "workspace": "/work", "status": "failed"},
  "plan": {
    "task_id": "task_incomplete",
    "goal": "准备课程结题材料",
    "steps": [
      {
        "step_id": "build_001",
        "tool": "build_package",
        "description": "执行同次获批的冻结材料包方案",
        "risk": "medium",
        "status": "failed",
        "arguments": {"task_id": "task_incomplete", "plan_sha256": "sha256:51364b3e62d349121ce6a7adc4f0a8f395afefbf53a08aaed68ff4ee6a2c8133", "plan_id": "package_plan_22222222222222222222222222222222"}
      }
    ]
  },
  "pending_operations": [],
  "preview_id": null,
  "error": "Package partially created; inspect child results and destination; no retry performed",
  "package_execution": {
    "plan_sha256": "sha256:51364b3e62d349121ce6a7adc4f0a8f395afefbf53a08aaed68ff4ee6a2c8133",
    "operation_results": [
      {"step_id": "package_001", "result_index": 5},
      {"step_id": "package_002", "result_index": 6},
      {"step_id": "package_003", "result_index": 7}
    ],
    "final_result_index": 8,
    "plan_id": "package_plan_22222222222222222222222222222222"
  }
}
```

Existing TaskSnapshot.results[5:9] in order; indices 0..4 remain the analysis and full plan shown above:

```json
[
  {
    "success": true,
    "tool": "create_folder",
    "data": {"path": "/work/课程结题材料包"},
    "message": "create_folder completed",
    "error": null
  },
  {
    "success": true,
    "tool": "copy_file",
    "data": {"source": "/work/结题报告.txt", "destination": "/work/课程结题材料包/结题报告.txt"},
    "message": "copy_file completed",
    "error": null
  },
  {"success": false, "tool": "copy_file", "data": null, "message": "copy_file failed", "error": "Second source differs from approved snapshot; execution stopped"},
  {"success": false, "tool": "build_package", "data": null, "message": "build_package failed", "error": "Package partially created; inspect child results and destination; no retry performed"}
]
```

GET /api/agent/tasks/task_incomplete returns that Snapshot.
GET /api/agent/tasks/task_incomplete/report returns 409:

```json
{"detail": "Report is not available"}
```

No failed build data contains a partial manifest. The created directory/first
copy remain observable; the failed copy may leave a fragment under the cleanup
decision above. Do not claim unchanged filesystem or successful rollback.

#### Decisions before implementation

A/B review the minimal request/manifest/issue schema, operation descriptors and
proposed plan_id-based Snapshot correlation; A/D review the restricted report tool, source/
parent race defenses and failed-fragment policy. A must implement acceptance
validation before preview consumption and a single child/final append owner.
B must display unknown/failed analysis and explicit incomplete risk acceptance.
Only then deliver contract PR → D planning/snapshot/report implementation PR →
A approval/execution/result-stream PR → cross-task temporary-file integration.
No Package implementation, generic classification or policy extraction is started
by this documentation. Matching Phase 2 remains required and unfinished.

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
