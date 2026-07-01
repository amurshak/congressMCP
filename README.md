# CongressMCP

**91+ congressional data tools for Claude, Cursor, VS Code, and any MCP client.**

Access live U.S. Congressional data — bills, votes, members, committees, hearings, and more — through natural language via the [Model Context Protocol](https://modelcontextprotocol.io/).

## Quick Start

### 1. Get a free Congress.gov API key

Sign up at **[api.congress.gov/sign-up](https://api.congress.gov/sign-up/)** (takes 30 seconds, completely free).

### 2. Configure your MCP client

**Claude Desktop** — add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": {
        "CONGRESS_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**VS Code** — add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": {
        "CONGRESS_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Cursor** — add to `~/.cursor/mcp.json` using the same format as VS Code.

### 3. Start asking questions

> "Find recent climate change bills in the 119th Congress"
> "How did senators from California vote on the latest defense bill?"
> "Who are the members of the Senate Judiciary Committee?"
> "What's the latest action on H.R. 1234?"

## Tools

**7 toolsets, 90+ operations** covering the Congress.gov API:

| Toolset | Operations | What it does |
|---------|-----------|--------------|
| **Bills** | 16 | Search, details, text, actions, amendments, cosponsors, subjects |
| **Laws** | 2 | Enacted public/private laws by congress (`get_laws`, `get_law_details`) |
| **Amendments** | 7 | Search, details, actions, sponsors, text |
| **Treaties & Summaries** | 5 | Treaty search, actions, committees, text; bill summaries |
| **Members & Committees** | 13 | Member search by name/state/district, sponsored legislation, committee bills/reports/communications |
| **Voting & Nominations** | 13 | House/Senate votes, nominations, roll calls |
| **Records & Hearings** | 10+ | Congressional Record, hearings, CRS reports, committee prints |

`search_committees` and `search_summaries` take an **optional** `keywords` argument —
omit it to browse/list (committees can also be filtered by `chamber`/`committee_type`).

## Running from source

```bash
git clone https://github.com/amurshak/congressMCP
cd congressMCP
pip install -e .

# stdio (default — for MCP clients)
CONGRESS_API_KEY=your-key congressmcp

# HTTP (for self-hosting / remote access)
congressmcp --transport streamable-http --port 8000
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONGRESS_API_KEY` | Yes | — | Your free Congress.gov API key |
| `MCP_TRANSPORT` | No | `stdio` | Transport mode (`stdio` or `streamable-http`) |
| `ENABLE_CACHING` | No | `false` | Cache API responses in memory |
| `CACHE_TIMEOUT` | No | `300` | Cache TTL in seconds |

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

Sustainable Use License

---

**Built for government transparency and accessible civic data.**
