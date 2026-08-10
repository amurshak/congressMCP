"""Entry point for running CongressMCP as a module.

Usage:
    python -m congress_api                              # stdio (default)
    python -m congress_api --transport streamable-http  # hosted HTTP
    uvx congressmcp                                     # stdio via uvx
"""
import argparse
import os
import platform
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Congress MCP Server — 91+ congressional data tools")
    subparsers = parser.add_subparsers(dest="command")
    cache_parser = subparsers.add_parser("cache", help="Inspect or clear the bill-text cache")
    cache_subparsers = cache_parser.add_subparsers(dest="cache_command")
    cache_subparsers.add_parser("info", help="Show bill-text cache information")
    clear_parser = cache_subparsers.add_parser("clear", help="Clear the bill-text cache")
    clear_parser.add_argument("--yes", action="store_true", help="Confirm non-interactively")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)")
    args = parser.parse_args()

    if args.command == "cache":
        return _cache_cli(args)

    # Import the server — main.py handles logging setup and feature initialization at import time
    from congress_api.main import server as mcp

    if args.transport == "stdio":
        mcp.run()
    else:
        import uvicorn
        app = mcp.streamable_http_app(stateless_http=True)
        print(f"Starting Congress MCP server on {args.host}:{args.port}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port)


def _cache_cli(args):
    cache_dir = _cache_dir()
    packages_dir = cache_dir / "packages"
    files = sorted(packages_dir.glob("*.db")) if packages_dir.exists() else []
    total = sum(path.stat().st_size for path in files if path.exists())
    cap = int(os.getenv("CONGRESSMCP_CACHE_MAX_BYTES", "524288000"))

    if args.cache_command == "info":
        print(f"path: {cache_dir}")
        print(f"schema_version: in-memory-pr1")
        print(f"total_bytes: {total}")
        print(f"cap_bytes: {cap}")
        if not files:
            print("packages: []")
        else:
            print("packages:")
            for path in files:
                print(f"  - {path.name}\t{path.stat().st_size}")
        return 0

    if args.cache_command == "clear":
        if not args.yes:
            print("Bill-text persistent caching is planned for PR 2. Nothing was removed.")
            print("Re-run with --yes once persistent cache files exist.")
            return 1
        removed = 0
        for path in files:
            path.unlink()
            removed += 1
        print(f"removed_packages: {removed}")
        return 0

    print("Specify `congressmcp cache info` or `congressmcp cache clear --yes`.", file=sys.stderr)
    return 2


def _cache_dir() -> Path:
    override = os.getenv("CONGRESSMCP_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Caches" / "congressmcp"
    if system == "Windows":
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "congressmcp" / "Cache"
    return Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "congressmcp"


if __name__ == "__main__":
    # sys.exit(main()), not bare main(): the console script generated from
    # [project.scripts] wraps the entry point and propagates its return value, so
    # `congressmcp cache clear` without --yes exits 2 while `python -m congress_api
    # cache clear` exited 0 for the same refusal. Two invocation paths disagreeing
    # about the exit code makes the CLI unscriptable through the module form.
    raise SystemExit(main())
