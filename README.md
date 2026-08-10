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

**7 toolsets, 90+ operations** covering the Congress.gov API, plus full-text bill retrieval from GovInfo:

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

### Full Bill Text Search

CongressMCP can fetch full Bill DTD XML from GovInfo, parse it locally, build a segment-level SQLite FTS5 index in memory, and return targeted bill sections instead of raw multi-megabyte XML or whole rendered bill pages.

New tools:

| Tool | What it does |
|------|--------------|
| `search_bill_text` | Searches full bill text and returns ranked addressable chunks with snippets, `match_contexts`, and amendatory flags |
| `get_bill_section` | Retrieves a qualified section or chunk id, with `max_bytes` measured against UTF-8 bytes of the returned `text` field |
| `get_bill_toc` | Returns a shallow navigation tree for finding section ids |

No new API key is required. GovInfo and Congress.gov both use api.data.gov keys, so CongressMCP reuses `CONGRESS_API_KEY`; set `GOVINFO_API_KEY` only if you need an explicit GovInfo override.

First-call latency can be seconds for NDAA-scale bills because PR 1 reparses and rebuilds the in-memory FTS5 index on every call. Persistent per-package indexes, LRU eviction, offline cache reuse, and measured live fixture timings are planned for PR 2. Network egress for this feature goes to `api.congress.gov` for text-version metadata and `api.govinfo.gov` for bill XML.

The search response distinguishes matches in `operative`, `quoted`, and `header` segments. If `quoted` appears in `match_contexts`, the hit may include language the bill is removing, even when `operative` also appears; retrieve the section before drawing conclusions about strike-and-insert language.

Each hit also carries `matched_queries` — the subset of your queries that produced it. Read it before reasoning about retrieval behavior: in a multi-query call it attributes every hit to its originating query, so an unexpected result is explained by the field, not by guessing at tokenizer internals.

`amends` resolves U.S. Code citations only (the longhand `Section {sec} of title {title}, United States Code` form and the shorthand `{title} U.S.C. {sec}` form when an amendatory verb follows). It does not resolve named Acts, including the Internal Revenue Code cited by bare section number — so most Title VII tax units report `is_amendatory: true` with `amends: []`. Use `is_amendatory` and `match_contexts` to identify amendatory text; `amends` is a convenience, not a completeness guarantee.

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
| `GOVINFO_API_KEY` | No | — | Optional override for GovInfo; otherwise `CONGRESS_API_KEY` is reused |
| `ENABLE_CACHING` | No | `false` | Cache API responses in memory |
| `CACHE_TIMEOUT` | No | `300` | Cache TTL in seconds |
| `CONGRESSMCP_CACHE_DIR` | No | Platform cache path | Planned PR 2 bill-text package cache root |
| `CONGRESSMCP_CACHE_MAX_BYTES` | No | `524288000` | Planned PR 2 bill-text cache cap |
| `CONGRESSMCP_CACHE_ENABLED` | No | `true` | Planned PR 2 persistent bill-text cache toggle; PR 1 always indexes in memory per call |
| `CONGRESSMCP_VERSION_TTL` | No | `86400` | Planned PR 2 version-resolution cache TTL |
| `CONGRESSMCP_REVALIDATE_DAYS` | No | `30` | Planned PR 2 explicit-version revalidation interval |

Default future bill-text cache locations:

| Platform | Path |
|----------|------|
| Linux | `$XDG_CACHE_HOME/congressmcp`, else `~/.cache/congressmcp` |
| macOS | `~/Library/Caches/congressmcp` |
| Windows | `%LOCALAPPDATA%\congressmcp\Cache` |

Cache CLI skeleton:

```bash
congressmcp cache info
congressmcp cache clear --yes
```

In PR 1 these commands report the planned cache location and remove any package DBs if present; production bill-text indexes are still in-memory only.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

Sustainable Use License

---

**Built for government transparency and accessible civic data.**
