# digital-life-organizer

Task-driven local AI file agent for intelligent organization, version analysis, conflict detection, and task-oriented package generation.

## Document reading (current scope)

`fileforge.document.read_document(path)` reads the full content of TXT files and
returns the shared `Document` / `ToolResult` envelope. Other formats are not yet
supported by this public entry point; C1 remains in progress.

Document IDs follow the confirmed
[path-based identity rules](API_CONTRACT.md#path-based-document-identity): IDs are
stable for the same normalized path, but change after moves or renames and are
not portable across environments. See [TASKS.md](TASKS.md#phase-c1--document-parser)
for remaining parser work and [AGENTS.md](AGENTS.md) for collaboration rules.
