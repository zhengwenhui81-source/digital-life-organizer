# Runtime organization inputs

The organization context builder scans the selected workspace and reads actual
supported documents. It no longer requires the course fixture's filenames,
file count, six categories, or v3 final-version choice. The course entry point
calls this builder; `prepare()` and its fixture mapping remain available for
reproducing the original example without changing its source materials.

Optional `[整理规则] source => output/category/source` lines are validated against
the scanned file set. Output and category names come from the document. Explicit
mappings must cover that set exactly and cannot escape the workspace, collide,
or overwrite an existing output directory. Without mapping lines, the builder
supplies observed text and the user goal to the existing planner; it does not
synthesize a final-version choice or manufacture classification evidence.

Requirement-like filenames prioritize reads but do not establish a document's
role. When none are found, supported documents are read as candidates. More
than ten candidate documents requires narrowing the workspace or using the
existing interactive workflow. Unsupported bodies are not read. This is a
flat-directory context builder, not a new recursive semantic classifier.

The copy auditor derives counts and destinations from actual completed plans,
checks explicit rules against actual task reads, and verifies source preservation,
copy hashes, output file/directory sets, tool completion and the existing backend
verification result. The material-input record binds the initial explicit routes
so omitting the task's requirement read cannot silently weaken that check.
Audit success verifies copies and explicit mapping compliance, not semantic
classification accuracy or submission-content completeness.

## Validation

Linux / Python 3.12: the following targeted command passed **92 tests**:

```console
python -m pytest -q demo/test_course22_demo.py tests/test_organization_context.py tests/test_agent_planner.py tests/test_agent_api.py tests/test_agent_document_integration.py tests/test_agent_file_tools.py
```

New tests include 2, 5, 13 and 25 input files, different requirement filenames,
user-defined categories, v1 selected while v9 is archived, no explicit mappings,
invalid and colliding destinations, incomplete rules, existing output, read limits,
unreadable documents, and destination tampering. Variable-input tests use the
real Planner validation, TaskService, approval gate, filesystem tools and hash
verification with a **controlled model reply**. They are not real DeepSeek
acceptance or a classification-accuracy measurement.

The original 22-file preparation/context/audit regression still passes. One old
assertion rejecting any non-fixture category is replaced by an assertion that a
valid user-defined category is accepted; invalid paths still have negative tests.

Frontend files and the model/approval/execution implementations are unchanged.
The course video page retains scenario-specific labels and its default 22-file
goal; it is still a presentation for that example, not a generic results UI.
Use the normal Agent interface for other scenarios. A real DeepSeek replay on
Windows remains necessary before treating this branch as a replacement for the
recorded-demo version. No full-project test or real-model rerun is claimed.
