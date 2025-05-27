#!/usr/bin/env python3
"""
Simple proxy to connect Claude Desktop to a remote MCP server.
"""
import asyncio
import sys
import httpx
from mcp.transports.stdio import StdioServerTransport

# The URL of your remote MCP server
REMOTE_URL = "https://congressionalmcp-2e92bd988060.herokuapp.com/sse"

async def main():
    """Run the proxy."""
    print("Starting MCP proxy to connect to remote server...", file=sys.stderr)
    print(f"Remote URL: {REMOTE_URL}", file=sys.stderr)
    
    # Create a client for the remote server
    async with httpx.AsyncClient() as client:
        # Set up the stdio transport
        transport = StdioServerTransport()
        
        # Start reading from stdin
        async def forward_to_remote():
            while True:
                try:
                    # Read a message from Claude Desktop
                    message = await transport.receive()
                    if not message:
                        continue
                    
                    # Forward the message to the remote server
                    response = await client.post(
                        f"{REMOTE_URL}/messages",
                        json=message,
                        timeout=30.0
                    )
                    
                    if response.status_code != 200:
                        print(f"Error from remote server: {response.status_code}", file=sys.stderr)
                        print(response.text, file=sys.stderr)
                        continue
                    
                    # Forward the response back to Claude Desktop
                    await transport.send(response.json())
                except Exception as e:
                    print(f"Error in proxy: {e}", file=sys.stderr)
        
        # Run the proxy
        await forward_to_remote()

if __name__ == "__main__":
    asyncio.run(main())
