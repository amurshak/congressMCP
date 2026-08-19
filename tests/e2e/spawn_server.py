#!/usr/bin/env python3
"""Spawn shim: inject credentials from a 0600 file, then exec the MCP server.

Why this exists (F29/F30 postmortem, maintainer directive 2026-08-19): Codex does NOT
forward the parent environment to the MCP servers it spawns, so the inheritance channel
the Claude driver uses delivers nothing there -- the server came up keyless and wore a
misleading error for it (F31). And every channel Codex *does* offer is an artifact:
the config env table is written to mcp-config.toml in the run directory, and the -c
overrides land verbatim in meta.json's `command`. A key riding either would be published
with the run.

So the key travels through a channel that leaves no artifact: this shim reads KEY=VALUE
lines from a mode-0600 file OUTSIDE the run tree (written by the harness at startup,
deleted when the run ends), puts them in its own environment, and execs the real server.
Only the file's PATH appears in run artifacts; the values exist on disk transiently,
readable by the operator alone.

The shim refuses a file readable by group or other: a 0644 secrets file next to a run
someone tars up is exactly the disclosure trace-constraint 1 exists to prevent, and
refusing loudly at spawn beats trusting every caller to have set the mode.

It never prints a value. Errors name the file and the fix, not the contents.
"""
from __future__ import annotations

import os
import sys


def fail(message: str) -> int:
    sys.stderr.write(f"spawn_server: {message}\n")
    return 2


def main(argv: list[str]) -> int:
    secrets_file = None
    module = "congress_api"
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--secrets-file" and args:
            secrets_file = args.pop(0)
        elif arg == "--exec-module" and args:
            # For the shim's own tests: exec a harmless module instead of the server.
            module = args.pop(0)
        else:
            return fail(f"unknown argument {arg!r}")
    if not secrets_file:
        return fail("--secrets-file is required")
    try:
        mode = os.stat(secrets_file).st_mode
    except OSError as exc:
        return fail(f"cannot stat secrets file {secrets_file}: {exc.strerror}. The "
                    "harness writes it at startup and deletes it at exit; a missing "
                    "file usually means the server outlived the run.")
    if mode & 0o077:
        return fail(f"secrets file {secrets_file} is readable by group/other "
                    f"(mode {oct(mode & 0o777)}). Refusing to start: chmod 600 it. "
                    "A shared-readable credential file beside a run directory is a "
                    "disclosure, not a configuration.")
    try:
        with open(secrets_file, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key and value:
                    os.environ[key] = value
    except OSError as exc:
        return fail(f"cannot read secrets file {secrets_file}: {exc.strerror}")
    os.execv(sys.executable, [sys.executable, "-m", module, "--transport", "stdio"])
    return 1  # unreachable; execv does not return on success


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
