#!/usr/bin/env python3
"""Pre-warm a cell's bill-text cache by DIRECT server-side calls (§17-PR2).

    CONGRESSMCP_CACHE_DIR=<cell cache dir> python tests/e2e/warm_cache.py < specs.json

stdin is a JSON list of package specs, each {"package_id", "congress",
"bill_type", "number", "version"}; stdout is a JSON list of per-package
records. The harness (run_suite.run_one) spawns this once per warm cell,
BEFORE the prompt's CLI process, and then asserts on disk that every named
package file exists -- the warm state is verified, never assumed.

WHY A SUBPROCESS, AND WHY THE TOOL FUNCTION. §17-PR2: "the harness pre-warms
by direct server-side calls for the named packages before the prompt -- never
by burning a model turn." Warming through a model turn would put a consumer
call in the measurement and make the cell's first real call look warm because
a prior model call was not. So the warm call goes straight through the tool
function (get_bill_toc, depth=1 -- the cheapest call that drives the full
resolve/download/parse/index/publish path) in a process whose environment
carries the cell's CONGRESSMCP_CACHE_DIR and NO trace dir: the warming calls
must not appear in the cell's trace, so this process refuses to start if
CONGRESSMCP_TRACE_DIR is set. A separate process also keeps the harness's own
interpreter free of the server's process-wide store (service.get_store() binds
to the cache dir on first use).

WHAT "WARM" MEANS HERE. One call per named package with version=None -- the
shape a consumer's first call takes -- so that BOTH the package file and the
version-resolution row (the CONGRESSMCP_VERSION_TTL "cached" path) are warm,
exactly the state a server is in after having served this bill once. If the
resolved package is not the named one (the named version is not current), a
second, explicit-version call guarantees the named package is on disk; both
calls are recorded. Every call's envelope fields that matter for reading the
cell (package_id, version_resolution, cache.index_hit/version_hit, timing)
are returned verbatim so the meta row can disclose what the warm did.

Never prints a credential: the only values that leave this process are tool
envelope fields and file stats.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

TRACE_ENV = "CONGRESSMCP_TRACE_DIR"
CACHE_ENV = "CONGRESSMCP_CACHE_DIR"


def fail(message: str) -> int:
    sys.stderr.write(f"warm_cache: {message}\n")
    return 2


def _call_record(version_arg: str | None, resp: dict) -> dict:
    """The envelope fields a reader needs, verbatim; the error shape if any."""
    if "error" in resp:
        err = resp["error"] or {}
        return {
            "version_arg": version_arg,
            "error": err.get("code"),
            "message": err.get("message"),
        }
    return {
        "version_arg": version_arg,
        "package_id": resp.get("package_id"),
        "version": resp.get("version"),
        "version_resolution": resp.get("version_resolution"),
        "cache": resp.get("cache"),
        "timing": resp.get("timing"),
    }


async def warm_packages(specs: list[dict], cache_dir: Path,
                        toc=None) -> list[dict]:
    """Warm each spec; return one record per spec. `toc` is injectable for tests."""
    if toc is None:
        from congress_api.features.bill_text.tools import get_bill_toc  # noqa: PLC0415
        toc = get_bill_toc
    from congress_api.features.bill_text import cache as cache_mod  # noqa: PLC0415

    layout = cache_mod.CacheLayout(cache_dir)
    records: list[dict] = []
    for spec in specs:
        package_id = spec["package_id"]
        calls: list[dict] = []
        resp = await toc(None, congress=int(spec["congress"]),
                         bill_type=spec["bill_type"], number=int(spec["number"]),
                         depth=1)
        calls.append(_call_record(None, resp))
        if resp.get("package_id") != package_id:
            # The named version is not the current one: pin it explicitly so
            # the named package is the one on disk (the version=None call above
            # still warmed the resolution row for whatever is current).
            resp = await toc(None, congress=int(spec["congress"]),
                             bill_type=spec["bill_type"], number=int(spec["number"]),
                             version=spec["version"], depth=1)
            calls.append(_call_record(spec["version"], resp))
        path = layout.package_path(package_id)
        present = path.exists()
        records.append({
            "package_id": package_id,
            "calls": calls,
            "file": str(path),
            "present": present,
            "bytes": path.stat().st_size if present else None,
        })
    return records


def main(argv: list[str]) -> int:
    if argv:
        return fail(f"takes no arguments (got {argv!r}); specs arrive on stdin")
    if os.getenv(TRACE_ENV, "").strip():
        return fail(f"{TRACE_ENV} is set. Warming calls must not appear in the "
                    "cell's trace; the harness spawns this process with the "
                    "trace switch off. Refusing to warm into a traced server.")
    raw = os.getenv(CACHE_ENV, "").strip()
    if not raw:
        return fail(f"{CACHE_ENV} is not set. Warming into the platform-default "
                    "cache dir would leave the cell sharing state with whatever "
                    "ran before it -- the undisclosed shared state the cache "
                    "axis exists to rule out.")
    cache_dir = Path(raw)
    try:
        specs = json.loads(sys.stdin.read() or "[]")
    except json.JSONDecodeError as exc:
        return fail(f"stdin is not a JSON list of package specs: {exc}")
    if not isinstance(specs, list) or not specs:
        return fail("stdin must be a non-empty JSON list of package specs")
    sys.path.insert(0, str(REPO))
    records = asyncio.run(warm_packages(specs, cache_dir))
    sys.stdout.write(json.dumps(records) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
