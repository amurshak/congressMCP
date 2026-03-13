"""Entry point for running CongressMCP as a module.

Usage:
    python -m congress_api                              # stdio (default)
    python -m congress_api --transport streamable-http  # hosted HTTP
    uvx congressmcp                                     # stdio via uvx
"""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Congress MCP Server — 91+ congressional data tools")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)")
    args = parser.parse_args()

    # Set transport before any server imports (mcp_server.py reads MCP_TRANSPORT at import time)
    os.environ["MCP_TRANSPORT"] = args.transport

    # Import the server — main.py handles logging setup and feature initialization at import time
    from congress_api.main import server as mcp

    if args.transport == "stdio":
        mcp.run()
    else:
        import uvicorn
        app = mcp.streamable_http_app()
        print(f"Starting Congress MCP server on {args.host}:{args.port}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
