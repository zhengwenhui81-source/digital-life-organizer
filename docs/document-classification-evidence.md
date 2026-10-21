# Existing Document evidence for downstream classification

This is C's input-capability explanation for TASKS Chapter 10, not a classification
contract or implementation. Use the existing [Document and shared rules](../API_CONTRACT.md#document),
[identity](../API_CONTRACT.md#path-based-document-identity) and
[extraction scope](../API_CONTRACT.md#read_document-extraction-scope) as authority.
No category/confidence/author/topic/alias fields or another ID mechanism are added.

## Actual fields and provenance

`fileforge.document.read_document(path)` returns a successful
`ToolResult.data.document` with these existing fields. Implementation:
[src/fileforge/document/parser.py](../src/fileforge/document/parser.py).

| Field | Actual source | Safe interpretation / limit |
| --- | --- | --- |
| file_id | SHA-256 of system-case-normalized, resolved absolute target path, prefixed with file_ | Path identity in one consistent environment, not content identity or a subject label; rename/move can change it |
| path | expanduser/resolve target path, including symlink resolution | Provenance/location only; caller A enforces Workspace authorization |
| filename | Resolved target's name | A name clue; may be misleading, not proof of content, purpose or task compliance |
| extension | Resolved target's lowercase suffix | Supported-format clue; does not authenticate material meaning or guarantee valid contents |
| text | Existing extractor's supported readable content, with an explicit full-text limit | Content evidence only within the format omissions below; not proof the whole physical document was understood |
| size | File stat size before extraction, in bytes | Storage size, not text length, importance or completeness |
| modified_time | File stat mtime before extraction, represented as UTC ISO time | Filesystem timestamp, not authorship, reliable chronology, finality or task suitability |
| metadata | Currently always an empty object, {} | No extracted author/title/tags, category, confidence or document properties are currently supplied |

A scan/search FileRecord is not a successful Document read. Filename, extension,
size and timestamps can be available from discovery even when content was never
read; never turn this into a claim that extracted content was analyzed. Do not
substitute a FileRecord/database ID for Document.file_id. Stat and extraction are
not an atomic filesystem snapshot; concurrent external file edits are not certified
away by this interface.

## Text evidence and omissions

Scope checked at merged dev `4d43cbd897e95dc91234e8e515f0bf7478699d07`. PR #28 is
merged as `53f6dd840df2408024d4f6248fb511751416138b`: DOCX body/table reading
is implemented, not merely approved. Its [separate fixed-HEAD Windows evidence](docx-table-extraction.md#verified-windows-evidence-2026-10-18)
records 17 synthetic passes and one real-document pass. C parser/extractor code
is unchanged between that evidence HEAD and this dev. This is not scoring
understanding or classification delivery.

The public reader supports only TXT, PDF, DOCX and XLSX (case-insensitive suffix).
It passes `sys.maxsize` to the existing extractor, avoiding the default
2,000-character snippet; complete supported text is held in memory, not streamed.

Rechecked at dev `f084b8a18198f61634c82e5bc12ee9bffc44f0f0`: CPP and JSON
can use the separate upstream snippet dispatcher, but remain unsupported by public
`read_document` and Agent automatic Document batches. CSV is unsupported by both
current dispatchers. See the [Demo diagnosis](version-demo-diagnosis.md#public-reader-versus-upstream-snippets)
for measured format counts and explicit-read failure semantics. File discovery
must not be presented as content extraction or proof that a file is irrelevant.

| Format / implementation | Actual text produced | Omitted / uncertain evidence |
| --- | --- | --- |
| [TXT](../src/fileforge/extractor/text.py) | Read bytes, chardet encoding detection, fallback UTF-8, replacement decoding; decoded text | Replacement characters or incorrect detection may lose meaning; upstream extractor supporting other text suffixes does not expand public support beyond TXT |
| [PDF](../src/fileforge/extractor/pdf.py) | Text layers from pages in order, joined with newlines | No OCR; no text alone does not establish a scanned document; images and layout/table fidelity are not guaranteed, and no structured page citation field is returned |
| [DOCX](../src/fileforge/extractor/docx.py) | Body paragraphs and table grids in original order; merged origins/spans and covered-slot references; nested tables stay inside their cells | No headers, footers, textboxes, images, revision/content-control wrappers or complete Word layout; structural reading is not scoring/category interpretation |
| [XLSX](../src/fileforge/extractor/xlsx.py) | Read-only/data_only values in worksheet order; nonempty rows joined with ` | ` and nonempty sheets headed `[sheet name]` | Formula caches can be absent or stale; missing values are omitted, no formula calculation; no coordinates/styles/charts or XLSM public support |

Sheet names and cell text may provide clues, but are not verified business
categories. The reader does not generate semantic classifications, aliases or
claims of task suitability. Version recommendations describe version evidence,
not classification or permission to operate on files.

## Failure versus unavailable content

- Unsupported format, nonexistent/unreadable file and parser exception return
  `success=false`, `data=null`, readable message/error; they yield no successful
  Document or partial content claim.
- Whitespace-only TXT and no extractable PDF text / DOCX body/table text / XLSX values also
  fail explicitly. Keep the reason distinct from a parser exception. Do not turn
  failure into empty successful text, no candidates, or content already analyzed.
- Partial-format success still has omissions: e.g. XLSX may contain ordinary cell
  values while uncached formula cells are omitted; a DOCX body/table can succeed
  while header/footer/textbox/image contents are unread. The content is usable only with these qualifications.
- A's current read-to-Version workflow stops on read failure. A/D must separately
  agree how a future classification workflow represents discovered unreadable,
  image/unsupported or uncertain items for confirmation while preserving sources.
  This note introduces no private status field or exception to current semantics.

## Integration and testing work still owned by the team

A owns candidate provenance, Workspace checks, successful-read collection and
failure/report propagation. D owns conservative classification/matching behavior;
B owns accurate presentation. An extension-only decision must be described as
file-type grouping, never material-purpose/content analysis. Ambiguous evidence
must remain uncertain under the eventual agreed interface.

Existing parser tests cover empty, unsupported, damaged and format-specific
omissions. The [controlled-plan C/A run](c-agent-integration-validation.md) covers
real read failures and stopping operations. These do not certify future classifier
handling of unreadable items. Still needed after a public classification proposal:
A/D tests retaining those discoveries without invented Documents, misleading
content-analysis claims or silent drops; evidence-poor/mixed-content cases;
original-source preservation; agreed batching beyond A's current ten supported
candidates per collection. Version quotas are not automatically classifier quotas.
Classify_files schema/implementation, OCR and new readers remain outside this work.
