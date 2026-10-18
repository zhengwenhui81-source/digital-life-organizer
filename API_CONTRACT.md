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
remaining `match_requirements` input/output schema, add it to the public tool
registry, or change conflict/requirement business algorithms. Mentioning future
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

The matching schema is proposed in the [Phase 1 contract draft](#match_requirements--phase-1-contract-draft)
below; it remains subject to final confirmation before strict consumers rely on it.

### match_requirements — Phase 1 contract draft

**契约变更草案，待本 PR 最终确认。** This section specifies proposed public
behavior; it does not claim the tool is implemented, exported or registered.
The fixed public tool list above is unchanged until final confirmation.

#### Confirmation provenance

- A has confirmed complete ToolResult retention in TaskSnapshot.results,
  failure termination/no subsequent file operations, report 409 before completion,
  successful missing-to-FinalReport.missing_items mapping and no fallback to an
  older successful result after a newer failure (relayed by the project owner).
- B/C's latest item-by-item feedback, relayed by the project owner, supplies the
  Phase 1 filename/output rules below. It supersedes the older prototype proposal:
  remove at most the rightmost version suffix, even from a repeated suffix.
- **New proposal requiring explicit confirmation:** reject a filename containing
  only whitespace. This is an additional clarification, not attributed to the
  original B/C confirmation. The examples are explanatory, not execution evidence.
- A must finally review the whole input/output/filename draft, the additional
  filename clarification and its Agent/report integration. Publishing this draft
  does not freeze it or certify implementation in A/B/C/D.

#### Entry point and input

Proposed public entry point (read-only, proposed risk `low`):

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
   all-dot names and names ending with a dot. Reject whitespace-only names under
   the explicitly marked new proposal above.
2. Split at the last dot only when both its prefix and suffix are nonempty.
   The stem is the prefix and the extension includes the dot. With no such split,
   the entire filename is the stem and the extension is `""`.
   `.gitignore` and `.env` have no extension; `.config.json` has stem `.config`
   and extension `.json`; `材料.tar.gz` has stem `材料.tar`, extension `.gz`.
3. `Document.extension` must equal the derived extension ignoring **ASCII letter
   case only**; an extensionless name requires `""`. Mismatch fails the whole call,
   rather than silently repairing or ignoring the candidate. Do not restrict
   extensions to C's current supported parser formats.
4. Compare the stem and requirement exactly: case-sensitive, no whitespace
   trimming/collapsing and no Unicode normalization or full-width folding.
5. Besides exact matching, remove at most the rightmost terminal suffix of the
   form `_vN`, `_vN.N` or `_vN.N.N`: lowercase ASCII `v`, ASCII digits `0-9`,
   leading zeros permitted, strict end-of-string, and a nonempty remaining stem.
   Do not remove other suffixes or repeatedly strip. `申请表_v1_v2` can match
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
One Document may be associated with more than one requirement under these rules;
this does not mean any quantity or combined-proof requirement is fulfilled.

All Phase 1 matches are **not content-reviewed**, as a uniform capability limit;
no `verified`, `unresolved`, `category` or `aliases` field is introduced. Filename
association is not approval of contents, signatures, validity period, quantity or
truthfulness. `missing` means only no filename-rule match in this candidate set,
not absence from the Workspace or machine.

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

No matching-specific resource quotas have been agreed. Do not inherit Version
limits or promise arbitrary-scale processing. Future limits must be validated on
original input before comparison/deduplication, not after duplicates are removed.

Phase 2 alias matching, common-name normalization and semantic proof association
remain required, unfinished work. Phase 1 is not generalized semantic matching.
Package and classify_files contracts are outside this change.

#### Complete JSON examples

These illustrate the draft, not implemented tool output. IDs are illustrative.

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
- the exact `ToolResult.data` shape for the actual package output path and
  verification target list must be agreed with Developer D and the consuming A/B
  developers before implementation is treated as stable

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
