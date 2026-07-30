# Microsoft Office MCP Integration

The `tendershield-office` MCP server lets QS engineers use Claude Desktop, Cursor,
Windsurf, or any MCP-compatible client to read and update Word/Excel tender
documents. It can also talk to the TenderShield API to pull live opportunities,
findings, deadlines, and AI-generated plan dashboards directly into Office files.

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

## TenderShield API integration

To pull live data from TenderShield, export these environment variables in the
MCP client configuration or launch shell:

```bash
export TENDERSHIELD_API_BASE="https://api.tendershield.example.com/api"
export TENDERSHIELD_API_TOKEN="<your-jwt-access-token>"
```

The token is a TenderShield access token from `POST /api/auth/login` followed by
`POST /api/auth/mfa/challenge`.

### API-aware tools

| Tool | What it does |
|------|--------------|
| `tendershield_list_opportunities` | List opportunities the token can access. |
| `tendershield_get_opportunity_summary` | Opportunity metadata + upcoming deadlines. |
| `tendershield_get_findings` | Risk/BOQ findings, with optional `severity` filter. |
| `tendershield_export_findings_to_excel` | Pull findings and append to an `.xlsx` file. |
| `tendershield_create_summary_doc` | Create a Word summary of findings + deadlines. |
| `tendershield_plan_dashboard` | Fetch the AI-generated plan dashboard. |

## Security

The server only reads/writes files under the directory from which it is
launched. It rejects paths containing parent-directory traversal. API calls use
the token supplied by the user and never store or cache credentials.
