# C private organization planner

This is a non-public implementation milestone under
[Workflow 2 ownership](../AGENTS.md#10-workflow-2--smart-folder-organization-ownership-2026-10-21).
It does not register a classifier, tool, HTTP endpoint or filesystem writer.
The classifier decision gate in [API_CONTRACT.md](../API_CONTRACT.md) still applies.

## Delivered behavior

`src/fileforge/organization/_draft.py` accepts an authoritative native Workspace
and a tuple of private `_Item` values. These are internal test/adapter values,
not a proposed replacement for D's public classification fields or quotas.

- A source keeps its original path and filename. `file_id` may be absent; the
  planner never invents an ID for a scan result.
- Categories are dynamic. Only an explicitly selected item with a category,
  evidence and resolved confirmation status gets a proposed relative target.
  Pending and unselected items remain in the mappings, with their basis, reason
  and evidence. Evidence is preserved as detached JSON values, including original
  indices/references; the planner cannot authenticate those references.
- Targets use relative POSIX spelling such as `整理结果/动态类别/文件.bin`.
  `directories` contains the output root and proposed category directories.
  The return value has no executable operations, approval state or preview IDs.
- Validation rejects traversal, foreign/UNC/device/URI paths, sources outside
  Workspace, filename mismatch, non-files, links and observed reparse attributes.
  Windows reserved names, controls, forbidden characters, trailing spaces/dots
  and overlong UTF-16 components are rejected on every platform.
- NFC/casefold keys detect category spelling and target collisions without
  rewriting source names. Existing output directories/files, including detected
  aliases, produce diagnostics. Sources inside the output subtree are rejected.
  This does not implement the initial scan's output-exclusion policy.
- A nonempty diagnostic list retains candidate mappings for diagnosis only.
  A must reject the whole draft. A also catches validation/read-observation errors;
  it must not freeze partial mappings or substitute another planner.

## Confirmed orchestration boundary

The agreed order remains D classification, A authentication of the current
task/result index/goal/scan/read/selection, C read-only planning, A second validation,
absolute-path recomputation, frozen operations, `preview_id`, approval and execution.
A must check every mapping against the authoritative classification and complete
scan coverage. C does not establish task ownership, source freshness or approval.

The production adapter awaits D's finalized fields and A's concrete receiving
interface. No Package analysis slots or `prepare_package` calls are reused here.
Classification-specific limits belong to the agreed classification boundary;
this module does not inherit Version limits or claim arbitrary-size safety.

## Existing A components: inspected candidates, not a new C write interface

At development baseline `3493801eb10a346273edd3cf09791808638900fa`:

| Existing implementation | Observed reusable capability | Required agreement before production use |
| --- | --- | --- |
| `agent/package_fs.py`: `anchored_mkdir`, `anchored_open`, `guarded_entries` | Exclusive creation and handle/descriptor-anchored paths; regular-file and link/reparse checks | A confirms an organization-safe shared entry/module. These functions are low-level mechanics, not an authorization gate. |
| `agent/package_execution.py`: `_copy_one`, `_digest` | Byte digest comparison, exclusive targets, source object checks, conservative failed-fragment reporting | A confirms/extracts the shared interface. C production must not import these private helpers or call `execute_package` with a made-up Package plan. |
| `agent/package_execution.py`: `execute_package` | Package operation sequencing and result recording | Keep Package-specific sequencing with A; do not wrap it as a second organization executor. |

Please A confirm which shared callable/module organization execution should use,
who owns any extraction, and how A's consumed frozen approval is checked before
each dispatched write. Existing low-level helpers are callable Python functions;
they do not independently prove TaskService approval. This PR adds no C writer
that could reach them. A retains the only production mutation dispatcher.

The test-only primitive calls below characterize current behavior in disposable
fixtures. They are not production integration or an authorization proof. A failed
copy currently retains an observed owned fragment and reports it; it does not
promise deletion or rollback.

## Reproduction and evidence

Environment: Linux / Python 3.12.14. Use the project's development dependencies;
no dependency or public protocol is changed by this milestone.

At the baseline above, the command below returned **91 passed, 0 skipped**:
36 core planner cases, 20 evidence cases, 6 test-only reuse cases, and 29 existing
C/A source cases. Black and Ruff passed for the five new Python files; staged
whitespace and local-document link checks passed. These are Linux results only.

```bash
PYTHONPATH="$PWD/src" python -c 'import fileforge.organization._draft as m; print(m.__file__)'
PYTHONPATH="$PWD/src" python -m pytest \
  tests/test_organization_draft.py \
  tests/test_organization_evidence.py \
  tests/test_organization_component_reuse.py \
  tests/test_document_package_evidence.py \
  tests/test_agent_package_evidence.py -q -ra
python -m black --check src/fileforge/organization tests/test_organization_*.py
python -m ruff check src/fileforge/organization tests/test_organization_*.py
git diff --check
```

Planner tests cover empty/mixed temporary Workspaces, Chinese paths, dynamic
categories, unknown/unselected items, structured evidence, optional IDs, strict
duplicate comparison, same names, output reuse, traversal and actual symlinks.
An injected reparse attribute is explicitly a simulation, not Windows evidence.
A guarded test forbids file opening/content reads and mutation during planning.
Changing source bytes before a valid lexical draft deliberately remains possible:
A must reject stale analysis using its separate full Document and byte checks.

Six additional test-only checks characterize A's existing exclusive directory
creation, correct-byte copying, occupied-target rejection, changed bytes with
restored size/mtime, failed partial-copy retention and actual symlink rejection.
The 29 existing C/A source tests remain separate from those component checks.

Windows, real classification, organization TaskService wiring/approval, cleanup
integration, browser, DeepSeek and complete organization execution are pending.
The original Document/Version implementation and thresholds are unchanged.
