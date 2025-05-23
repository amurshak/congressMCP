#!/bin/bash
# Congressional MCP Server restart script

echo "Stopping Congressional MCP server if running..."
# Use a more specific pattern to only target this specific server
pkill -f "mcp dev.*run_server\.py$" || true

echo "Starting Congressional MCP server in dev mode..."
source env/bin/activate && mcp dev run_server.py
