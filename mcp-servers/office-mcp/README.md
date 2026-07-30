# TenderShield Office MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that lets
QS engineers and bid managers use LLM clients (Claude Desktop, Cursor, etc.)
to read and write Microsoft Word and Excel tender documents without leaving
Office.

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

## Security

The server resolves every path relative to the current working directory and
rejects `..` traversal. Keep tender documents inside the directory from which
you launch the server.
