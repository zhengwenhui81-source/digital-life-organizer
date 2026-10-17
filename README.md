# digital-life-organizer

Task-driven local AI file agent for intelligent organization, version analysis, conflict detection, and task-oriented package generation.

## Document reading (current scope)

`fileforge.document.read_document(path)` returns the shared `Document` /
`ToolResult` envelope for TXT, PDF, DOCX and XLSX, without the default
2000-character snippet cutoff. It reads TXT text, PDF text layers across pages,
DOCX body paragraphs, and XLSX values across named worksheets.

PDF OCR is not performed; no extractable PDF text does not prove it is a scan.
DOCX tables, headers and footers are not read. XLSX uses stored formula caches
(which can be stale), omits uncached formula results, and never calculates them.
XLSM is unsupported. See the authoritative
[extraction scope](API_CONTRACT.md#read_document-extraction-scope) for limitations
and error behavior. The reader does not modify source files.

The team lead reported Windows verification of the TXT stage; this multi-format
stage has only been verified on Linux. Windows multi-format checks remain
outstanding, and C1 is not declared fully complete.

Document IDs follow the confirmed
[path-based identity rules](API_CONTRACT.md#path-based-document-identity): IDs are
stable for the same normalized path, but change after moves or renames and are
not portable across environments. See [TASKS.md](TASKS.md#phase-c1--document-parser)
for remaining parser work and [AGENTS.md](AGENTS.md) for collaboration rules.
