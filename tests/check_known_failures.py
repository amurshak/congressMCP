#!/usr/bin/env python
"""Verify the suite's failing set still equals the recorded baseline.

See KNOWN_FAILURES.md for why. The point is not to bless the failures -- it is to make
the set an artifact that changes visibly, so a genuine regression cannot hide among
failures everyone has learned to scroll past.

Fails when the set GROWS (a regression) and equally when it SHRINKS (something was
fixed and KNOWN_FAILURES.md was not updated). A baseline that only ratchets one way
rots into a bigger version of the problem it was meant to solve.

    python tests/check_known_failures.py

Exits 0 when the live set matches, 1 otherwise, printing the symmetric difference.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_DOC = Path(__file__).resolve().parent / "KNOWN_FAILURES.md"


def parse_baseline(text: str) -> tuple[set[str], set[str]]:
    """Extract (failures, collection_errors) from KNOWN_FAILURES.md.

    The fenced code blocks of that document ARE the baseline -- the one record
    (#20). This script used to carry its own Python copy of the same set with
    no link to the prose one; two unlinked copies of a baseline will desync,
    and a desynced baseline greenwashes exactly like the stale entries it
    exists to catch. An entry with a `::` node id is a test failure; a bare
    path is a file-level collection error (a collection error runs zero tests,
    so there is no node id to name).
    """
    failures: set[str] = set()
    collection_errors: set[str] = set()
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            continue
        entry = line.strip()
        if entry:
            (failures if "::" in entry else collection_errors).add(entry)
    return failures, collection_errors


def run_suite() -> tuple[set[str], set[str]]:
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", "tests/",
            "-q", "--tb=no", "-p", "no:cacheprovider",
            "--continue-on-collection-errors",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    failures, collection_errors = set(), set()
    for line in result.stdout.splitlines():
        if line.startswith("FAILED "):
            failures.add(line.split(None, 1)[1].split(" - ")[0].strip())
        elif line.startswith("ERROR "):
            target = line.split(None, 1)[1].split(" - ")[0].strip()
            # A collection error names a file; an ERROR on a node id is a fixture or
            # teardown error, which belongs with the failures.
            (collection_errors if "::" not in target else failures).add(target)
    return failures, collection_errors


def report(label: str, live: set[str], known: set[str]) -> bool:
    new, fixed = sorted(live - known), sorted(known - live)
    for item in new:
        print(f"  REGRESSION  {label}: {item}")
    for item in fixed:
        print(f"  NOW PASSING {label}: {item}  (remove it from KNOWN_FAILURES.md)")
    return not (new or fixed)


def main() -> int:
    known_failures, known_collection_errors = parse_baseline(BASELINE_DOC.read_text())
    if not (known_failures or known_collection_errors):
        # An empty parse is far more likely a broken document (or a reformat that
        # dropped the fences) than a suite that suddenly runs clean. Say so
        # rather than reporting every live failure as a regression against
        # nothing.
        print(f"FATAL: no baseline entries parsed from {BASELINE_DOC}. If the suite "
              "is genuinely clean now, delete this check; otherwise the fenced "
              "blocks were lost in an edit.")
        return 1
    failures, collection_errors = run_suite()
    ok = report("failure", failures, known_failures)
    ok &= report("collection error", collection_errors, known_collection_errors)
    if ok:
        print(
            f"Baseline matches: {len(known_failures)} known failures, "
            f"{len(known_collection_errors)} known collection errors, nothing new."
        )
        return 0
    print("\nThe known-failing set changed. Investigate, then update KNOWN_FAILURES.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
