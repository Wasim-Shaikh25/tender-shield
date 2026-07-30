# Microsoft Office MCP Server — Spec

**Status:** done — standalone MCP server for reading/writing Word and Excel
tender documents, with TenderShield API integration.
**Task refs:** TS-187, TS-190

## Purpose

QS engineers live inside Microsoft Word and Excel: tender NITs, GCC/SCC, BOQs,
and review reports are Word documents, while BOQ sheets and rate analysis are
Excel workbooks. An MCP server lets an LLM client read these files, answer
questions about them, and write comments / append rows without the user leaving
Office.

## Public interface

MCP server name: `tendershield-office`

### Tools

- `read_word_document(path: str)` — extract paragraphs and tables from `.docx`.
- `read_excel_workbook(path: str, sheet: str | None, max_rows: int = 100)` —
  read an `.xlsx` workbook or sheet as JSON.
- `write_word_comments(path: str, comments: list[str], heading: str)` — append
  a review-comments section to an existing `.docx`.
- `create_summary_doc(path: str, title: str, sections: list[dict])` — create a
  new Word summary document.
- `append_excel_rows(path: str, sheet: str, rows: list[list])` — append rows
  to a worksheet, creating the workbook/sheet if needed.
- `tendershield_list_opportunities()` — list opportunities from the TenderShield API.
- `tendershield_get_opportunity_summary(opportunity_id: str)` — return opportunity
  metadata plus key deadlines.
- `tendershield_get_findings(opportunity_id: str, severity: str = "")` — return
  risk/BOQ findings for an opportunity, optionally filtered by severity.
- `tendershield_export_findings_to_excel(opportunity_id: str, output_path: str)` —
  pull findings and append them to an Excel workbook.
- `tendershield_create_summary_doc(opportunity_id: str, output_path: str)` —
  create a Word summary from an opportunity's findings and deadlines.
- `tendershield_plan_dashboard(opportunity_id: str, query: str)` — fetch the
  AI-generated dynamic plan dashboard from the TenderShield API.

### Transport

Stdio (default). The server is launched by the MCP host (Claude Desktop, Cursor,
etc.) with the configured `python -m tendershield_office_mcp` command.

## Data owned

None. The server operates on local files provided by the user. It does not store
or cache tender data.

## Behavior

- **B1 (local files only):** every `path` is resolved and must stay inside the
  current working directory. Parent-directory traversal is rejected.
- **B2 (idempotent reads):** read tools never modify the file.
- **B3 (safe writes):** write tools only append comments/rows or create new
  files; they never overwrite existing content unless explicitly requested.
- **B4 (pure data):** extracted text/table data is returned as JSON so the LLM
  can cite it directly.
- **B5 (TenderShield API integration):** when `TENDERSHIELD_API_BASE` and
  `TENDERSHIELD_API_TOKEN` are set, the server can pull live opportunities,
  findings, deadlines, and plan dashboards and merge them into Word/Excel outputs.
  If the variables are missing, these tools return a setup message instead of crashing.

## Acceptance criteria

- A1: `read_word_document` returns paragraphs and tables from a `.docx`.
- A2: `read_excel_workbook` returns cell values for every requested sheet.
- A3: `write_word_comments` appends bullet comments without corrupting the file.
- A4: `append_excel_rows` creates a new workbook when the file does not exist.
- A5: a path containing `..` is rejected.
- A6: TenderShield API tools return data or a clear configuration message when
  `TENDERSHIELD_API_BASE` and `TENDERSHIELD_API_TOKEN` are set.
- A7: `tendershield_export_findings_to_excel` appends findings with severity,
  category, title, producer, page, and status.
- A8: `tendershield_create_summary_doc` generates a summary document grouped by
  finding category and including key deadlines.

## Out of scope

PowerPoint support, real-time co-editing, cloud Office 365 integration (P2).
