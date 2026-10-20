# digital-life-organizer

Task-driven local AI file agent for intelligent organization, version analysis, conflict detection, and task-oriented package generation.

For Windows/Linux Agent development, offline tests, service startup and optional
real LLM configuration, see the [local Agent run guide](docs/local-agent-development.md).

## Document reading (current scope)

`fileforge.document.read_document(path)` returns the shared `Document` /
`ToolResult` envelope for TXT, PDF, DOCX and XLSX, without the default
2000-character snippet cutoff. It reads TXT text, PDF text layers across pages,
DOCX body paragraphs/tables in original order, and XLSX values across named worksheets.

PDF OCR is not performed; no extractable PDF text does not prove it is a scan.
DOCX tables preserve row/column positions and merged-cell references; headers,
footers, textboxes and images are not read. XLSX uses stored formula caches
(which can be stale), omits uncached formula results, and never calculates them.
XLSM is unsupported. See the authoritative
[extraction scope](API_CONTRACT.md#read_document-extraction-scope) for limitations
and error behavior. The reader does not modify source files.

User-supplied Windows 11 / Python 3.12.10 64-bit evidence verifies the declared
multi-format parser at `a6ee13a53100f0b2522f4e9ad07e0e0296bd59d4`:
59 parser/extractor tests passed (3 skipped), plus 11 supplemental tests passed.
Windows symbolic-link behavior remains unverified. See the
[validation record](docs/parser-windows-validation.md) for skips and applicability;
this does not establish complete C1 or end-to-end Agent acceptance.

Document IDs follow the confirmed
[path-based identity rules](API_CONTRACT.md#path-based-document-identity): IDs are
stable for the same normalized path, but change after moves or renames and are
not portable across environments. See [TASKS.md](TASKS.md#phase-c1--document-parser)
for remaining parser work and [AGENTS.md](AGENTS.md) for collaboration rules.

DOCX table extraction has separate fixed-HEAD Windows evidence: 17 synthetic
tests and one real-document audit passed. Previous Windows results cover the
body-only implementation and remain historical. See the [table extraction record](docs/docx-table-extraction.md)
for current Linux checks, representation and unchanged Version size limits.

## Version contract status

The [compare_versions v1 contract](API_CONTRACT.md#compare_versions) and
[shared Document collection rules](API_CONTRACT.md#shared-document-collection-rules)
are confirmed. `fileforge.document.compare_versions(documents)` is now implemented
and locally tested on Linux. Fixed-commit Windows unit/lifecycle and four-format
C-tool pipeline evidence is reconciled in the
[validation record](docs/version-windows-validation.md). Default Agent routing and
controlled-plan Linux integration have [scoped evidence](docs/c-agent-integration-validation.md);
full integration/end-to-end acceptance remains pending. D tool collection-rule adaptation/tests and their acceptance remain separately
tracked by the responsible owner. Runtime inputs come from unknown
Workspaces; finding no version relationships is a normal successful result.
Controlled version fixtures are for tests/regression/acceptance, not a guaranteed
classroom dataset. See [TASKS.md](TASKS.md#phase-c3--version-contract) for pending work.
