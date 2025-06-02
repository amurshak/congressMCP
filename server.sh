#!/bin/bash
# Congressional MCP Server restart script

echo "Stopping Congressional MCP server and related dev tools if running..."

# Forcefully kill processes on known MCP Inspector/Proxy ports
echo "Attempting to free port 6277 (MCP Proxy)..."
if pids=$(lsof -t -i:6277); then kill -9 $pids 2>/dev/null; fi

echo "Attempting to free port 6274 (MCP Inspector)..."
if pids=$(lsof -t -i:6274); then kill -9 $pids 2>/dev/null; fi

# Also attempt the original pkill for the server process itself
echo "Attempting to stop the main server process..."
pkill -f "mcp dev.*run_server\.py" || true
pkill -f "mcp run.*run_server\.py" || true
pkill -f "uvicorn asgi:app" || true
pkill -f "python -m congress_api.main" || true
pkill -f "fastmcp run.*run_server\.py" || true

# Add a small delay to allow ports to be fully released by the OS
echo "Waiting for ports to be released..."
sleep 2

echo "Starting Congressional MCP server with fastmcp run..."
source env/bin/activate && fastmcp run run_server.py
