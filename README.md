# CongressMCP

**Live U.S. Congressional data for any MCP client — Claude Code, ChatGPT, Copilot, Codex, Cursor, OpenCode, Gemini CLI, Grok Build, and more.**

Bills, full bill text, votes, members, committees, hearings, nominations, and the Congressional Record — queried in natural language through the [Model Context Protocol](https://modelcontextprotocol.io/). Runs locally on your machine against the free Congress.gov and GovInfo APIs. No account, no hosted service, no telemetry.

## Quick Start

### 1. Get a free Congress.gov API key

Sign up at **[api.congress.gov/sign-up](https://api.congress.gov/sign-up/)** — takes 30 seconds. The same key also works for GovInfo (full bill text).

### 2. Install `uv`

CongressMCP is published on PyPI and launched with `uvx`, which ships with [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

(`brew install uv`, `winget install astral-sh.uv`, and `pipx install uv` also work.) Prefer pip? `pip install congressmcp` gives you a `congressmcp` command you can use in place of `uvx congressmcp` below.

### 3. Connect your client

Every client needs the same three facts: **command** `uvx`, **args** `["congressmcp"]`, **env** `CONGRESS_API_KEY`. Clients are listed roughly by how many professional developers use them today (JetBrains Developer Ecosystem survey, mid-2026, then Pragmatic Engineer's 2026 tooling survey), so the one you want is probably near the top:

| Client | Where it's configured | Notes |
|--------|-----------------------|-------|
| [Claude Code](#claude-code) | `claude mcp add …` or `.mcp.json` | |
| [ChatGPT](#remote-clients-chatgpt-claudeai-open-webui) | Developer mode → connector URL | remote only — needs [HTTP mode](#remote--http-mode) |
| [VS Code / GitHub Copilot](#vs-code--github-copilot) | `.vscode/mcp.json` | uses `servers` + `inputs` |
| [OpenAI Codex CLI](#openai-codex-cli) | `codex mcp add …` or `~/.codex/config.toml` | TOML |
| [Cursor](#cursor) | `~/.cursor/mcp.json` or `.cursor/mcp.json` | |
| [JetBrains AI Assistant / Junie](#jetbrains-ai-assistant--junie) | Settings → AI Assistant → MCP | paste the Claude Desktop JSON |
| [OpenCode](#opencode) | `opencode.json` → `mcp` | `command` is a single array |
| [Gemini CLI](#gemini-cli) | `gemini mcp add …` or `~/.gemini/settings.json` | |
| [Claude.ai](#remote-clients-chatgpt-claudeai-open-webui) | Connectors → custom connector URL | remote only — needs [HTTP mode](#remote--http-mode) |
| [Claude Desktop](#claude-desktop) | `claude_desktop_config.json` | |
| [Windsurf](#windsurf) | `~/.codeium/windsurf/mcp_config.json` | |
| [Zed](#zed) | `settings.json` → `context_servers` | |
| [Cline / Roo Code](#cline--roo-code) | MCP settings panel → edit JSON | |
| [Goose](#goose) | `goose configure` or `~/.config/goose/config.yaml` | YAML |
| [Grok Build](#grok-build) | `grok mcp add …` or `~/.grok/config.toml` | TOML; also auto-imports Claude Code / Cursor config |
| [Hermes Agent](#hermes-agent) | `hermes mcp add …` or `~/.hermes/config.yaml` | YAML |
| [OpenClaw](#openclaw) | `openclaw mcp add …` or `~/.openclaw/openclaw.json` | JSON5 |
| [Continue](#continue) | `~/.continue/config.yaml` | YAML, agent mode only |
| [Open WebUI](#remote-clients-chatgpt-claudeai-open-webui) | Admin → Integrations → MCP server URL | remote only — needs [HTTP mode](#remote--http-mode) |
| [LM Studio](#lm-studio) | Program tab → `mcp.json` | Cursor-style JSON |

Anything not listed that speaks MCP over stdio will work with the same three values.

<details>
<summary><a name="claude-code"></a><b>Claude Code</b></summary>

```bash
# just for you
claude mcp add congressmcp --env CONGRESS_API_KEY=your-api-key-here -- uvx congressmcp

# shared with your team via .mcp.json in the repo root
claude mcp add --scope project congressmcp --env CONGRESS_API_KEY='${CONGRESS_API_KEY}' -- uvx congressmcp
```

Put the server name *before* `--env` as shown — if `--env` comes first, the CLI tries to parse the name as another `KEY=value` pair. Equivalent `.mcp.json`:

```json
{
  "mcpServers": {
    "congressmcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "${CONGRESS_API_KEY}" }
    }
  }
}
```

`${VAR}` / `${VAR:-default}` are expanded from your environment, so the key never has to be committed.
</details>

<details>
<summary><a name="vs-code--github-copilot"></a><b>VS Code / GitHub Copilot</b></summary>

Workspace: `.vscode/mcp.json` (or Command Palette → **MCP: Add Server** / **MCP: Open User Configuration** for user-level). VS Code uses `servers` rather than `mcpServers`, and `inputs` lets it prompt for the key and store it securely instead of writing it to disk:

```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "congress-api-key",
      "description": "Congress.gov API key",
      "password": true
    }
  ],
  "servers": {
    "congressmcp": {
      "type": "stdio",
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "${input:congress-api-key}" }
    }
  }
}
```

VS Code shows a trust prompt the first time the server starts.
</details>

<details>
<summary><a name="openai-codex-cli"></a><b>OpenAI Codex CLI</b></summary>

```bash
codex mcp add congressmcp --env CONGRESS_API_KEY=your-api-key-here -- uvx congressmcp
```

Or in `~/.codex/config.toml` (also read by the Codex IDE extension and the ChatGPT desktop app; project-level `.codex/config.toml` works in trusted projects):

```toml
[mcp_servers.congressmcp]
command = "uvx"
args = ["congressmcp"]
env_vars = ["CONGRESS_API_KEY"]   # forward from your shell — nothing secret in the file
```

To inline the key instead, replace the `env_vars` line with a `[mcp_servers.congressmcp.env]` table containing `CONGRESS_API_KEY = "…"`. Check with `codex mcp list` or `/mcp` inside a session.
</details>

<details>
<summary><a name="cursor"></a><b>Cursor</b></summary>

Global: `~/.cursor/mcp.json`. Per-project: `.cursor/mcp.json`.

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "${env:CONGRESS_API_KEY}" }
    }
  }
}
```

`${env:NAME}` reads from your shell environment; a literal key string works too.
</details>

<details>
<summary><a name="jetbrains-ai-assistant--junie"></a><b>JetBrains AI Assistant / Junie</b></summary>

**AI Assistant**: Settings → **Tools → AI Assistant → Model Context Protocol (MCP) → Add → As JSON** and paste the [Claude Desktop](#claude-desktop) block (there's also an *Import from Claude* button that reads `claude_desktop_config.json`).

**Junie**: Settings → **Tools → Junie → MCP Settings**, which edits `~/.junie/mcp/mcp.json` (global) or `.junie/mcp/mcp.json` (project) — same `mcpServers` shape.
</details>

<details>
<summary><a name="opencode"></a><b>OpenCode</b></summary>

Global `~/.config/opencode/opencode.json` or project-root `opencode.json` / `opencode.jsonc` (project overrides global). OpenCode puts the command and its args in one array and calls the env map `environment`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "congressmcp": {
      "type": "local",
      "command": ["uvx", "congressmcp"],
      "environment": { "CONGRESS_API_KEY": "your-api-key-here" },
      "enabled": true
    }
  }
}
```

There's no `opencode mcp add`; edit the file, then check with `opencode mcp list` / `opencode mcp debug congressmcp`. Remote servers use `"type": "remote", "url": "https://<host>/mcp"`.
</details>

<details>
<summary><a name="gemini-cli"></a><b>Gemini CLI</b></summary>

```bash
gemini mcp add -s user -e CONGRESS_API_KEY=your-api-key-here congressmcp uvx congressmcp
```

(`-s user` makes it global; the default scope is the current project.) Or in `~/.gemini/settings.json` / `.gemini/settings.json`:

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "$CONGRESS_API_KEY" }
    }
  }
}
```
</details>

<details>
<summary><a name="claude-desktop"></a><b>Claude Desktop</b></summary>

Claude menu → **Settings… → Developer → Edit Config**, or edit the file directly:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "your-api-key-here" }
    }
  }
}
```

Restart Claude Desktop. If the server doesn't appear, use the absolute path to `uvx` (`which uvx` / `where uvx`) — GUI apps don't always inherit your shell `PATH`. Logs: `~/Library/Logs/Claude/mcp*.log` or `%APPDATA%\Claude\logs`.
</details>

<details>
<summary><a name="windsurf"></a><b>Windsurf</b></summary>

Cascade panel → MCPs icon → raw config, or edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "${env:CONGRESS_API_KEY}" }
    }
  }
}
```

Windsurf caps total tools across all servers at 100; CongressMCP registers 24 (each bundling related operations), so it fits comfortably.
</details>

<details>
<summary><a name="zed"></a><b>Zed</b></summary>

Settings → **AI → MCP Servers → Add Local Server**, or edit `settings.json` (macOS `~/Library/Application Support/Zed/settings.json`, Linux `~/.config/zed/settings.json`, Windows `%APPDATA%\Zed\settings.json`; project-level `.zed/settings.json`):

```json
{
  "context_servers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "your-api-key-here" }
    }
  }
}
```
</details>

<details>
<summary><a name="cline--roo-code"></a><b>Cline / Roo Code</b></summary>

**Cline**: MCP Servers icon → **Configure → Configure MCP Servers** (opens `cline_mcp_settings.json`; the Cline CLI uses `~/.cline/mcp.json`).
**Roo Code**: MCP Servers → **Edit Global MCP**, or per-project `.roo/mcp.json`.

Both use the Claude Desktop shape plus a couple of client-specific fields:

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "uvx",
      "args": ["congressmcp"],
      "env": { "CONGRESS_API_KEY": "your-api-key-here" },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

On Windows, Roo's docs recommend wrapping the command: `"command": "cmd", "args": ["/c", "uvx", "congressmcp"]`.
</details>

<details>
<summary><a name="goose"></a><b>Goose</b></summary>

Interactive: `goose configure` → **Add Extension → Command-line Extension** (command `uvx congressmcp`, then add `CONGRESS_API_KEY` when prompted for env vars). One-off: `goose session --with-extension "CONGRESS_API_KEY=your-api-key-here uvx congressmcp"`. Or in `~/.config/goose/config.yaml`:

```yaml
extensions:
  congressmcp:
    name: congressmcp
    type: stdio
    cmd: uvx
    args: [congressmcp]
    envs: { "CONGRESS_API_KEY": "your-api-key-here" }
    enabled: true
    timeout: 300
```
</details>

<details>
<summary><a name="grok-build"></a><b>Grok Build</b></summary>

xAI's terminal coding agent. If you already configured CongressMCP for Claude Code (`~/.claude.json` / `.mcp.json`) or Cursor (`.cursor/mcp.json`), Grok Build picks it up automatically — nothing more to do. Otherwise:

```bash
grok mcp add congressmcp -- uvx congressmcp      # add --scope project for .grok/config.toml
```

then set the key in `~/.grok/config.toml` (or project `.grok/config.toml`):

```toml
[mcp_servers.congressmcp]
command = "uvx"
args = ["congressmcp"]
env = { CONGRESS_API_KEY = "${CONGRESS_API_KEY}" }
```

`grok mcp list` / `grok mcp doctor congressmcp` to verify; `/mcps` in a session toggles servers. Tools appear as `congressmcp__<tool>`.
</details>

<details>
<summary><a name="hermes-agent"></a><b>Hermes Agent</b></summary>

Nous Research's Hermes Agent. `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  congressmcp:
    command: "uvx"
    args: ["congressmcp"]
    env:
      CONGRESS_API_KEY: "${CONGRESS_API_KEY}"   # or a literal key
    enabled: true
```

Or `hermes mcp add congressmcp --command uvx --args congressmcp` and then add the `env:` block by hand. `hermes mcp test congressmcp` checks the connection; `/reload-mcp` in a session reloads without restarting. Tools appear as `mcp__congressmcp__<tool>`.
</details>

<details>
<summary><a name="openclaw"></a><b>OpenClaw</b></summary>

```bash
openclaw mcp add congressmcp --command uvx --arg congressmcp --env CONGRESS_API_KEY=your-api-key-here
```

Or under `mcp.servers` in `~/.openclaw/openclaw.json` (JSON5, so comments and trailing commas are fine):

```json5
{
  mcp: {
    servers: {
      congressmcp: {
        command: "uvx",
        args: ["congressmcp"],
        env: { CONGRESS_API_KEY: "your-api-key-here" },
      },
    },
  },
}
```

`openclaw mcp status` / `openclaw mcp probe congressmcp` to verify. OpenClaw does not read `mcporter`'s registry — use `mcp.servers`. For a remote server, use `url` with an explicit `transport: "streamable-http"`.
</details>

<details>
<summary><a name="continue"></a><b>Continue</b></summary>

`~/.continue/config.yaml`, or one file per server under `.continue/mcpServers/` in your workspace (Continue also accepts Claude/Cursor-style JSON files dropped in that folder). MCP tools are available in **agent mode**.

```yaml
mcpServers:
  - name: congressmcp
    type: stdio
    command: uvx
    args:
      - congressmcp
    env:
      CONGRESS_API_KEY: ${{ secrets.CONGRESS_API_KEY }}
```
</details>

<details>
<summary><a name="lm-studio"></a><b>LM Studio</b></summary>

**Program** tab → **Install → Edit mcp.json**. LM Studio follows Cursor's `mcp.json` format, so the [Cursor](#cursor) block works as-is — use a literal key string rather than `${env:…}`. This gives any local model that supports tool calling access to congressional data.
</details>

<details>
<summary><a name="remote-clients-chatgpt-claudeai-open-webui"></a><b>Remote clients: ChatGPT, Claude.ai, Open WebUI</b></summary>

These clients can't launch a local process; they connect to an MCP server at a URL. Run CongressMCP in [HTTP mode](#remote--http-mode) and give them the URL:

- **ChatGPT** (Plus/Pro/Business/Enterprise/Edu, web): Settings → **Security and login → Developer mode**, then add a connector with your server URL. Requires a public **HTTPS** endpoint (or a Secure MCP Tunnel).
- **Claude.ai** (web; synced to mobile): **Customize → Connectors → Add custom connector** (Team/Enterprise: Organization settings → Connectors). Must be reachable over the public internet.
- **Open WebUI**: Admin Settings → **Integrations → + Add Server → MCP (Streamable HTTP)**. Streamable HTTP only; it can be on your LAN.

The endpoint in every case is `https://<your-host>/mcp`. Most of the local clients above (OpenCode, Grok Build, Hermes, OpenClaw, Codex, Claude Code, Cursor, VS Code) can also connect to that URL instead of launching `uvx` — useful for sharing one install across a team.
</details>

### 4. Start asking questions

> "Find recent climate change bills in the 119th Congress"
> "Where in the FY2026 NDAA is the Coast Guard's icebreaker funding?"
> "How did senators from California vote on the latest defense bill?"
> "Who are the members of the Senate Judiciary Committee?"
> "What's the latest action on H.R. 1234?"

## Remote / HTTP mode

For clients that connect by URL (ChatGPT, Claude.ai connectors, Open WebUI, or several users sharing one install), run the server over Streamable HTTP:

```bash
CONGRESS_API_KEY=your-key congressmcp --transport streamable-http --host 0.0.0.0 --port 8000
# MCP endpoint: http://<host>:8000/mcp
```

**CongressMCP has no built-in authentication.** The server is designed to run on your own machine. If you expose it beyond localhost, put it behind something that does authenticate — a reverse proxy with an access policy, an HTTPS tunnel with an allow-list, or a VPN — and remember that anyone who can reach it is spending your Congress.gov quota. ChatGPT and Claude.ai additionally require HTTPS on a publicly resolvable hostname.

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

**What changed:** instead of proxying API responses, CongressMCP fetches the full Bill DTD XML from GovInfo, parses it locally, builds a segment-level SQLite FTS5 index per bill version, and returns targeted, addressable bill sections instead of raw multi-megabyte XML or whole rendered bill pages. Indexes are **persisted on disk** and reused across calls and restarts.

| Tool | What it does |
|------|--------------|
| `search_bill_text` | Searches full bill text and returns ranked addressable chunks with snippets, `match_contexts`, and amendatory flags |
| `get_bill_section` | Retrieves a qualified section or chunk id, with `max_bytes` measured against UTF-8 bytes of the returned `text` field |
| `get_bill_toc` | Returns a shallow navigation tree for finding section ids |

**No new API key is needed.** GovInfo and Congress.gov both sit behind api.data.gov, so CongressMCP reuses your existing `CONGRESS_API_KEY` for both; set `GOVINFO_API_KEY` only if you want a separate GovInfo key. (People assume a second key is required. It is not.)

**Where data lives.** One SQLite file per bill version (`<package_id>.v<N>.db`, e.g. `BILLS-119s1071enr.v1.db`) under `packages/` in the cache root, plus a small `manifest.db` index. The cache root is `CONGRESSMCP_CACHE_DIR` if set, otherwise the platform default:

| Platform | Path |
|----------|------|
| Linux | `$XDG_CACHE_HOME/congressmcp`, else `~/.cache/congressmcp` |
| macOS | `~/Library/Caches/congressmcp` |
| Windows | `%LOCALAPPDATA%\congressmcp\Cache` |

**How much disk.** Capped at **500 MB** by default (`CONGRESSMCP_CACHE_MAX_BYTES`, bytes), enforced by least-recently-used eviction after every index write. An NDAA-scale enrolled bill (S.1071/119, 1,448 indexed units) builds an **11 MB** index; most bills are far smaller. Inspect or empty the cache from the command line — it is deliberately not an MCP tool:

```bash
congressmcp cache info          # path, cap, total bytes, one line per package
congressmcp cache clear --yes   # remove every package file and the manifest
```

Deleting the cache directory by hand is also safe at any time; the files are a cache, not a store.

**First-call latency — measured, not estimated.** Cold (nothing cached) on S.1071/119: **4.1–6.8 s** end to end across runs, of which congress.gov version resolution + the GovInfo package summary took 3.0–3.4 s, the XML download 1.1–2.3 s, parse 0.75 s, and the FTS5 build 0.31 s — the network legs are the slow and variable part, and they are the part the cache removes. Warm (index and version resolution cached): **30–60 ms**, no network. Every response carries a `timing` block (`resolve_ms`, `download_ms`, `parse_ms`, `index_ms`, `search_ms`, `total_ms`; a leg is `null` when it did not run) and a `cache` block (`index_hit`, `version_hit`), so you can see which case you got. **Client-timeout implication:** set your MCP client's per-call timeout to at least 30 s; a cold NDAA-scale call under a slow network can exceed a 10 s default and the partial work is not lost — the next call is warm.

**Offline behavior.** A version you have fetched explicitly (`version="enr"`) is fully queryable offline for as long as it stays in the cache; explicitly cached versions are re-checked against GovInfo's `lastModified` only every `CONGRESSMCP_REVALIDATE_DAYS` (30) and rebuilt if the package was reissued. With `version` omitted, the "latest version" answer is cached for `CONGRESSMCP_VERSION_TTL` (86400 s = 1 day; `version_resolution: "cached"`); past the TTL it is re-resolved, and if the network is unavailable the last answer is served **best-effort and labelled** `version_resolution: "cached_offline"` with the resolution timestamp and a note that a newer version may exist. If nothing is cached and the network is down you get `version_resolution_unavailable`, listing the versions of that bill that are cached so you can pin one.

**Network egress.** Exactly two hosts: `api.congress.gov` (bill and text-version metadata) and `api.govinfo.gov` (bill content). Both independently rate-limited per api.data.gov (20,000/h and 36,000/h), so indexing cannot starve the other tools.

Setting `CONGRESSMCP_CACHE_ENABLED=false` turns all of this off: every call re-downloads, re-parses and re-indexes the full document in memory — NDAA-scale latency, every time. It exists for diagnosis, not for normal use.

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
CONGRESS_API_KEY=your-key congressmcp --transport streamable-http --port 8000
```

Point a client at a source checkout by using `"command": "congressmcp"` (with the venv activated or its `bin/` on `PATH`) or `"command": "/path/to/venv/bin/congressmcp"` in place of `uvx`.

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CONGRESS_API_KEY` | Yes | — | Your free Congress.gov API key |
| `GOVINFO_API_KEY` | No | — | Optional override for GovInfo; otherwise `CONGRESS_API_KEY` is reused |
| `ENABLE_CACHING` | No | `false` | Cache API responses in memory |
| `CACHE_TIMEOUT` | No | `300` | Cache TTL in seconds |
| `CONGRESSMCP_BILL_TEXT_ONLY` | No | unset | If truthy, register only the three bill-text tools (standalone bill-text server) |
| `CONGRESSMCP_TRACE_DIR` | No | unset | If set to a directory, write one key-redacted JSONL record per bill-text tool call (debugging) |
| `CONGRESSMCP_CACHE_DIR` | No | Platform cache path (see [Full Bill Text Search](#full-bill-text-search)) | Bill-text package cache root |
| `CONGRESSMCP_CACHE_MAX_BYTES` | No | `524288000` | Bill-text cache cap (500 MB); LRU eviction after each index write |
| `CONGRESSMCP_CACHE_ENABLED` | No | `true` | `false` disables the persistent cache: every call re-fetches and re-parses the full document |
| `CONGRESSMCP_VERSION_TTL` | No | `86400` | Seconds a `version`-omitted "latest version" answer is reused without asking congress.gov |
| `CONGRESSMCP_REVALIDATE_DAYS` | No | `30` | Days before an explicitly cached version is re-checked against GovInfo's `lastModified` |

Cache CLI (the cache is administered from the command line, never via an MCP tool):

```bash
congressmcp cache info          # exit 0
congressmcp cache clear --yes   # exit 0; without --yes in a non-interactive shell it refuses with exit 1
```

## Troubleshooting

- **"command not found: uvx"** in a GUI client (Claude Desktop, Zed, LM Studio, JetBrains): use the absolute path from `which uvx` (macOS/Linux) or `where uvx` (Windows) as the `command`.
- **Windows**: if a client can't spawn `uvx` directly, use `"command": "cmd", "args": ["/c", "uvx", "congressmcp"]`.
- **First start is slow**: `uvx` downloads and caches the package on first run; subsequent starts are fast. Pin a version with `uvx congressmcp@2.1.0` if you want reproducibility.
- **401 / 403 from the API**: the key is missing or wrong. Confirm it works with `curl "https://api.congress.gov/v3/bill?api_key=YOUR_KEY&limit=1"`.
- **Tools missing in the client**: most clients need a restart or an explicit MCP reload after editing config.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

Sustainable Use License

---

**Built for government transparency and accessible civic data.**
