# TenderShield Office MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that lets
QS engineers and bid managers use LLM clients (Claude Desktop, Cursor, etc.)
to read and write Microsoft Word and Excel tender documents without leaving
Office. It can also connect to the TenderShield API to pull live opportunities,
findings, and AI-generated plan dashboards directly into Office files.

## Tools

- `read_word_document(path)` — extract paragraphs and tables from a `.docx`.
- `read_excel_workbook(path, sheet=None, max_rows=100)` — read an `.xlsx`
  workbook or a single sheet as JSON.
- `write_word_comments(path, comments, heading)` — append a review-comments
  section to an existing Word document.
- `create_summary_doc(path, title, sections)` — create a new Word summary
  document from a list of sections/items.
- `append_excel_rows(path, sheet, rows)` — append rows to an Excel worksheet,
  creating the file/sheet if necessary.
- `tendershield_list_opportunities()` — list TenderShield opportunities.
- `tendershield_get_opportunity_summary(opportunity_id)` — opportunity metadata
  and deadlines.
- `tendershield_get_findings(opportunity_id, severity="")` — risk/BOQ findings.
- `tendershield_export_findings_to_excel(opportunity_id, output_path)` — pull
  findings into an `.xlsx` file.
- `tendershield_create_summary_doc(opportunity_id, output_path)` — create a Word
  summary from live TenderShield data.
- `tendershield_plan_dashboard(opportunity_id, query)` — fetch the AI-generated
  plan dashboard.

## Install

```bash
cd mcp-servers/office-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run (stdio)

```bash
python -m tendershield_office_mcp
```

Add the server to your MCP client configuration:

```json
{
  "mcpServers": {
    "tendershield-office": {
      "command": "/absolute/path/to/mcp-servers/office-mcp/.venv/bin/python",
      "args": ["-m", "tendershield_office_mcp"]
    }
  }
}
```

## TenderShield API integration

Set `TENDERSHIELD_API_BASE` (e.g. `http://localhost:8000/api`) and
`TENDERSHIELD_API_TOKEN` (a TenderShield access token) to enable live-data tools.

```bash
export TENDERSHIELD_API_BASE="http://localhost:8000/api"
export TENDERSHIELD_API_TOKEN="<access-token>"
python -m tendershield_office_mcp
```

## Security

The server resolves every path relative to the current working directory and
rejects `..` traversal. Keep tender documents inside the directory from which
you launch the server. API credentials are read from environment variables and
are never stored.
