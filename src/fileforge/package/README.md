# Read-only Package planning

The following is A-side calling code, not a registered Agent adapter. `task` and
`snapshot` are A's authoritative current records; `evidence_indices` is A's local
mapping of the four tool names to their current result indices (or None for a
not-run tool). A has proposed `document` explicitly from a successful C read;
this is not an automatic choice from Matching/Version recommendations. Before
this call, A must perform the confirmed v1 revalidation described below. The
sample assembles only D's input; it does not implement A's preconditions.

```python
from fileforge.package import plan_package

analysis = {
    tool: None if index is None else {
        "result_index": index, "result": snapshot["results"][index],
    }
    for tool, index in evidence_indices.items()
}
result = plan_package(
    task={key: task[key] for key in ("task_id", "user_goal", "workspace")},
    selected_files=[{
        "source": {key: document[key] for key in ("file_id", "path", "filename")},
        "requirements": ["课程笔记"],
        "reason": "当前成功分析的提议，等待同次预览批准",
    }],
    destination=final_package_directory,
    analysis=analysis,
)
# result["success"] alone MUST NOT open executable preview or file execution.
# A must independently pass its provenance/byte-binding preconditions and gate.
```

`document` comes from a successful public
`read_document(path=...)` result's `data.document`. The caller supplies the four
analysis slots exactly as specified in the repository's
[Package contract](../../../API_CONTRACT.md#plan_package--build_package--package-contract-not-implemented).
Each slot is `None` (not run) or `{result_index, result}`. Successful planning
returns standard ToolResult data `{plan, plan_sha256}`; failure returns data null.
Success certifies only D's described read-only checks and proposal generation.
It does not certify analysis byte freshness or authorize an executable preview.
D does not perform that binding check. A's check outcome is not asserted by the
frozen report; consult A's authoritative records. A future passing check is
therefore compatible with the same report wording. A must block preview when its
required preconditions are not met, independently of D's success envelope.
No plan is approved, registered with A, or executed by this function. UUIDs differ
between calls; all stable content (including source observations) has the same
canonical digest independently of that ID. There is no public `build_package`
implementation, executor or tool registration here.

Sources are streamed through read-only descriptors, with descriptor/path identity,
size, mtime and ctime checked before/after reading. The whole source set is read
again before success to detect observable changes during other reads. This costs
two streaming passes and still does not eliminate later races. Generic
`analysis.dedup.hash_file` does not expose these descriptor/identity observations,
so it cannot supply this snapshot guarantee. Native absolute local paths only;
foreign Windows paths on POSIX, UNC/device/URI paths, traversal and symlinks or
Windows reparse points are rejected. Source/target names must agree. Final target
names use NFC + casefold for collision checks only and conservative Windows name
restrictions; names and identities are never rewritten. Destination must be
unoccupied and its parent must already exist. No permission-bit test promises
that a future directory creation will succeed. Platform checks need independent
Windows execution evidence; the current local verification is Linux.

The report is a frozen UTF-8/LF plan record, not a completion certificate. It keeps
all supplied evidence and alternatives, escapes user text, preserves known missing
and unresolved facts and explicitly marks unknown analysis. Conflict text retains
original values/sources; Version abstention is not converted into a choice.
Package requirements and reasons are proposals only. Filename candidates never
establish that templates are completed or that materials are valid.

A must authenticate task/workspace and references, verify evidence indices and
execution provenance against its actual Snapshot, reject **any** upstream failure
(including failures outside the four input slots), register the plan and bind the
preview.
D cannot prove those facts from this input. Any failed supplied analysis is
rejected by D. A still owns same-preview selection/risk approval, safe exclusive
creation/copy/report writing, rechecking frozen source bytes, final validation,
child-result recording and FinalReport mapping. The complete report bytes must
not be regenerated after approval. Digests/IDs are not credentials.

There are no Package-specific quantity/size quotas. Deep valid JSON may exceed
Python's copying/serialization recursion capacity; that returns standard failure
rather than a partial plan or uncaught RecursionError. This is an implementation
limitation, not a newly defined public depth allowance or arbitrary-scale promise.

Local tests:

```bash
python -m pytest -q tests/test_package_planning.py tests/test_package_paths.py tests/test_package_report.py tests/test_package_evidence_freshness.py
```

## Analysis byte-freshness gap (not solved by planning)

Validation checks JSON/schema and equality of supplied references/Document fields;
it does not prove that analysis used the bytes currently at those paths. C's
Document ID hashes a normalized path. Its size/modified_time/text and the retained
Version Documents do not contain a raw-content binding. A retaining the original
ToolResult proves what was supplied, not that the current file is unchanged.
The planning source SHA-256 observes current bytes only; it cannot be assigned
retroactively to an earlier read or analysis. Even same-path, same-size files
with restored mtime can have different bytes. ctime checks during planning do
not supply the missing observation from analysis time.

A temporary-file regression changes both a candidate and its notice in equal
byte lengths and restores mtime. Planning currently succeeds with the new source
hash and old requirements/Version text. No freshness-specific unresolved kind is
invented; the static report warning discloses the limitation. This test records
D-only observation, not acceptance of stale evidence for executable preview.
A integration tests must separately verify preview blocking; this suite neither
invokes A nor treats a read-only success as a satisfied A precondition.
Extracted TXT/PDF/DOCX/XLSX text must not be substituted for a binary-file digest.

## Confirmed v1 handoff — helpers available, TaskService integration pending

[The merged handoff](../../../API_CONTRACT.md#confirmed-v1-analysis-to-source-revalidation-handoff-not-implemented)
now defines current-consistency revalidation. It does not require a new Document
field or an extra plan_package argument:

1. **Before calling D**, A rereads every analysis-dependent source through C's
   public reader, including notices and relevant unselected candidates. It
   compares the complete original and reread Documents with the shared strict
   rules (metadata, extra fields, missing/null and exact JSON types included).
   A also hashes raw bytes before/after that reread; hashes must agree. It keeps
   the checked digest and source/result association in task-scoped state.
2. **After D returns and before executable preview**, A checks provenance and
   compares each selected source reference, size, mtime_ns and D's snapshot SHA-256
   against its checked state. Missing/contradictory evidence or any mismatch
   fails the Task without preview. A must not replace D's snapshot or accept the
   mismatch via accept_incomplete. It binds its associations and frozen plan to
   the same preview_id.
3. **After approval**, A checks approved digests and path/target safety before
   mutation and at use, then verifies created bytes, frozen report and file set.
   Failure stops further operations, preserves child results and returns report
   409. These executor/gate capabilities are not implemented by this D module.

V1 accepts the stated race limit: matching reread Documents and pre/post hashes
checks observable current consistency, not the exact historical bytes originally
parsed, and cannot exclude adversarial change-and-restore. Stronger historical
read-time evidence still needs a separate C/A contract. PR #38 now supplies A's
`fileforge.agent.package_evidence.revalidate_documents` and
`bind_selected_snapshots` helpers for these read-only checks. The helpers retain
checked source/result associations and cross-check D's selected snapshots;
they do not implement TaskService evidence collection, executable preview,
approval or Package execution. D production code does not import these helpers
or declare their checks passed. Independent cross-module acceptance belongs to
C under the AGENTS.md delegation. No new transport field or historical-byte
guarantee is introduced here. D-only freshness tests deliberately bypass A's required
prerevalidation; A integration tests must verify that such stale input never
reaches an executable preview in the real task flow.
