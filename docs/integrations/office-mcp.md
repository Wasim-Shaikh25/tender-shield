# Microsoft Office MCP Integration

The `tendershield-office` MCP server lets QS engineers use Claude Desktop, Cursor,
Windsurf, or any MCP-compatible client to read and update Word/Excel tender
documents.

## Setup

```bash
cd mcp-servers/office-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure your MCP client

Add this to your client settings:

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

## Example workflows

- **"Read the NIT and tell me the submission deadline"** — the LLM calls
  `read_word_document` on the NIT file and answers from the extracted text.
- **"Add these review comments to the GCC"** — the LLM calls
  `write_word_comments` with the risk findings.
- **"Append the corrected BOQ rates to the Excel sheet"** — the LLM calls
  `append_excel_rows`.

## Security

The server only reads/writes files under the directory from which it is
launched. It rejects paths containing parent-directory traversal.
