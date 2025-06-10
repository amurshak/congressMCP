# CongressMCP Installation for Cline

## Overview
CongressMCP provides comprehensive access to US congressional data through 113+ operations covering bills, votes, members, committees, and legislative intelligence.

## Step 1: Install Package
```bash
npm install -g congressmcp
```

## Step 2: Get API Key
1. Visit https://congressmcp.lawgiver.ai
2. Sign up for free account (all functions included)
3. Verify email to receive your API key

## Step 3: Configure Cline
Add this configuration to your Cline MCP settings file:

**Settings File Location:**
- **macOS:** `/Users/[username]/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **Windows:** `C:\Users\[username]\AppData\Roaming\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`
- **Linux:** `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

**Configuration:**
Add this to your `cline_mcp_settings.json` file:

```json
{
  "mcpServers": {
    "congressmcp": {
      "command": "npx",
      "args": ["-y", "congressmcp"],
      "env": {
        "CONGRESSMCP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

**Note:** If the file doesn't exist, create it with the configuration above.

## Step 4: Restart Cline
Restart Cline to activate the congressional research tools.

## Usage Examples
Once configured, you can ask questions like:
- "What climate bills were introduced this week?"
- "How did senators vote on the infrastructure bill?"
- "Show me all amendments to HR 1234"
- "Which committees handle healthcare policy?"
- "Find recent Supreme Court nominations"

## Available Tools
- **Legislation Hub**: Bills, amendments, summaries, treaties
- **Members & Committees**: Congressional members, committee information
- **Voting Records**: House votes, nominations, roll calls
- **Congressional Records**: Daily records, hearings, communications
- **Committee Intelligence**: Reports, prints, meetings
- **Research Tools**: CRS reports, professional analytics

## Free Tier
- All 113+ functions included
- 200 API calls per month
- No credit card required

## Troubleshooting
- Ensure API key is correctly set in environment variables
- Verify npm package is globally installed
- Check that Cline has restarted after configuration
- Visit https://congressmcp.lawgiver.ai for support