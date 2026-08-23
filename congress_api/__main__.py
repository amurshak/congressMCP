"""Entry point for running CongressMCP as a module.

Usage:
    python -m congress_api                              # stdio (default)
    python -m congress_api --transport streamable-http  # hosted HTTP
    uvx congressmcp                                     # stdio via uvx
"""
import argparse
import sys


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
    # The persistent-cache module owns the layout -- cache root and platform
    # defaults, packages/ glob, cap env var, schema version (spec §10). This
    # CLI reads them from it and re-declares nothing, so `cache info`/`clear`
    # can never point at a different path than the server writes to.
    # Imported lazily and WITHOUT the server stack: administering a broken
    # cache must work when the server cannot start.
    from congress_api.features.bill_text import cache

    settings = cache.CacheSettings.from_env()
    layout = settings.layout

    if args.cache_command == "info":
        info = cache.describe(settings)
        print(f"path: {info.path}")
        print(f"manifest: {info.manifest_path}")
        print(f"schema_version: {info.schema_version}")
        print(f"enabled: {'true' if info.enabled else 'false'}")
        print(f"total_bytes: {info.total_bytes}")
        print(f"cap_bytes: {info.cap_bytes}")
        if info.temp_files:
            print(f"in_progress_builds: {info.temp_files}")
        if not info.packages:
            print("packages: []")
        else:
            print("packages:")
            for entry in info.packages:
                print(f"  - {entry.name}\t{entry.bytes}\t{entry.status}")
        return 0

    if args.cache_command == "clear":
        if not args.yes and not _confirm_clear(layout):
            # Refusal exits 1 on BOTH entry points (spec §10 exit-code
            # contract); a completed clear exits 0.
            print("Refusing to clear the bill-text cache without confirmation.", file=sys.stderr)
            print(f"Re-run with --yes to remove everything under {layout.root}.", file=sys.stderr)
            return 1
        result = cache.clear(layout)
        print(f"removed_packages: {result.removed_packages}")
        print(f"removed_in_progress_builds: {result.removed_temps}")
        print(f"removed_manifest: {'true' if result.removed_manifest else 'false'}")
        for failure in result.failed:
            print(f"could_not_remove: {failure}", file=sys.stderr)
        return 0

    print("Specify `congressmcp cache info` or `congressmcp cache clear --yes`.", file=sys.stderr)
    return 2


def _confirm_clear(layout) -> bool:
    """Interactive confirmation for `cache clear` without --yes. Only a TTY on
    both stdin and stdout is asked; a non-interactive caller is refused."""
    try:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        interactive = False
    if not interactive:
        return False
    count = len(layout.package_files())
    total = layout.total_bytes()
    try:
        answer = input(
            f"Remove {count} cached package file(s), {total} bytes, and the manifest "
            f"under {layout.root}? [y/N] "
        )
    except EOFError:
        return False
    return answer.strip().lower() in {"y", "yes"}


if __name__ == "__main__":
    # SystemExit(main()), not bare main(): the console script generated from
    # [project.scripts] wraps the entry point and propagates its return value,
    # while a bare main() here would discard it and exit 0. Spec §10 pins the
    # exit-code contract on BOTH entry points: `cache clear` refused for want of
    # --yes exits 1; a completed `cache clear` and any `cache info` exit 0.
    raise SystemExit(main())
