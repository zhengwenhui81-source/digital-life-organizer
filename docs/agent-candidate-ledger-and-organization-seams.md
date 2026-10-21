# Agent candidate batching and organization execution seams

Status: **A design proposal; not a frozen public contract or implemented feature.**

This note records the current Agent behavior and the smallest general design that
can cover workspaces with more than one readable-document batch. It also fixes
the ownership boundary between C's read-only organization planner and A's sole
approval and filesystem execution path. Public fields require A/B/C/D agreement
before implementation.

## Current readable-candidate behavior

`TaskService` currently resolves an argument-free `read_document` step from the
latest successful `list_files` or `search_files` result. It keeps supported
`.txt`, `.pdf`, `.docx`, and `.xlsx` paths and rejects the step when that one
collection contains more than 10 readable paths.

The value 10 is therefore a **per resolved collection/step limit**, not a safe
task-wide processing guarantee. The current one-shot Plan has no pagination or
task-level coverage record. It cannot claim to have content-analyzed all 22
files by silently repeating, truncating, or treating unsupported/unread files as
analyzed.

## Proposed task-level candidate ledger

A future Agent enhancement should create one immutable, task-scoped ledger from
authenticated successful scan/search ToolResults. Suggested information is:

```json
{
  "items": [
    {
      "scan_ref": {"result_index": 0, "item_index": 0},
      "canonical_path": "/workspace/example.docx",
      "scan_snapshot": {},
      "read_state": "queued",
      "document_result_index": null,
      "analysis_result_indices": []
    }
  ],
  "batches": [
    {
      "batch_id": "batch-001",
      "item_indices": [0],
      "read_result_indices": [],
      "analysis_result_indices": []
    }
  ],
  "coverage": {
    "discovered": 1,
    "readable": 1,
    "read_succeeded": 0,
    "unsupported": 0,
    "remaining": 1,
    "complete": false
  }
}
```

The names above are illustrative. The frozen contract must define the actual
scan snapshot and status enums.

Required behavior:

1. Bind every item to one current Task and one exact scan ToolResult/index.
   Canonicalize and check Workspace scope before ledger insertion. Repeated
   scans may add evidence references, but must not create duplicate processing
   identities for the same resolved file and equal snapshot.
2. Preserve a deterministic order. A practical v1 is first authenticated
   discovery order with each batch containing at most 10 readable files.
   Record every unsupported, deferred, failed, and unattempted item; never
   silently truncate it.
3. Preserve the existing failure rule. A real `read_document` failure terminates
   the task, and later ledger items become explicitly unattempted after failure.
4. Pass only successful, task-bound full Documents to analysis tools. A result
   from another task, an obsolete scan, a changed file, an invalid result index,
   or a mismatched path/file identity invalidates that reference.
5. Treat analysis coverage separately from read coverage. A successful read does
   not prove that Requirements, Version, Matching, or classification considered
   the file.

### Cross-batch limits

Batching reads does not automatically make analysis globally valid:

- `compare_versions` accepts at most 10 Documents per comparison. Independent
  batches can miss a version relationship across a batch boundary. A task must
  not claim global Version completion until the team freezes a deterministic
  cross-batch comparison/merge rule.
- Requirements, conflict detection, Matching, and future classification each
  need an explicit aggregation rule and their own resource limits. A must not
  invent merged public results.
- Package selection may reference only authenticated evidence whose coverage is
  disclosed. Missing or deferred analysis cannot be converted into a positive
  material decision.

The current `TaskSnapshot` has no frozen per-file coverage field. Meeting the
requirement that every discovered file has a traceable status therefore needs a
team decision: either add a task-level coverage object or define a dedicated
standard ToolResult. This PR does not choose or publish that field.

## Workflow 2 read-only planning seam

The organization flow should have one A-owned orchestration entry after the
`classify_files` contract and C adapter are available:

```python
prepare_organization(task_id, classification_result_index)
```

The signature is an internal recommended seam, not a new HTTP API. A performs:

1. authenticate the current Task, user goal, classification ToolResult, source
   scan references, Document references, and coverage;
2. collect only user-confirmed proposed mappings while preserving abstentions
   and unselected items;
3. call C's read-only organization planner once;
4. reject the whole draft when `diagnostics` is nonempty; catch validation or
   read exceptions as task failure, without a fallback planner;
5. recheck categories, relative targets, output-subtree exclusion, collisions,
   Workspace scope, current source identity, and byte digest;
6. freeze the exact directory/copy operations and bind them to the existing
   one-time `preview_id` approval mechanism;
7. after approval, use A's existing anchored, exclusive filesystem primitives,
   cleanup records, and byte-level verification.

C's private draft shape (`mappings`, `directories`, `diagnostics`) is suitable
for step 3 if it remains read-only and uses relative targets. `proposed` means a
candidate mapping only. It grants no approval and creates no operation by
itself. C does not generate `preview_id`, perform writes, add an executor, or
silently resolve collisions.

## Reusable A-owned filesystem layer

Workflow 2 must reuse the security properties already present in
`fileforge.agent.package_fs` and the Package execution path: anchored traversal,
link/reparse rejection, exclusive target creation, source identity and SHA-256
rechecks, byte-equality verification, and conservative cleanup records.

The Package-specific `_copy_one` function is not a public C interface. Once the
classification contract is frozen, A should extract or wrap neutral internal
operations under the Agent module, conceptually:

```python
create_frozen_directory(workspace, relative_target)
copy_frozen_file(workspace, frozen_source, relative_target)
verify_frozen_copy(workspace, frozen_source, relative_target)
```

These functions remain behind TaskService's frozen preview and Approval Gate.
They must not accept model-created authorization, overwrite an existing object,
delete an original, or downgrade validation after an operating-system error.
C can consume and test the read-only seam; A remains the only production owner
of writes and execution records.
