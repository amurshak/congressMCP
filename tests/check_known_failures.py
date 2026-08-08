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

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that cannot even be imported. Recorded per FILE because a collection error
# runs zero tests, so there are no node ids to name.
KNOWN_COLLECTION_ERRORS = {
    # ModuleNotFoundError: No module named 'fastmcp' -- undeclared dependency
    "tests/test_committee_intelligence_hub_bucket.py",
    "tests/test_legislation_hub_bucket.py",
    "tests/test_people_relationships_hub_bucket.py",
    "tests/test_records_communications_hub_bucket.py",
    "tests/test_research_professional_hub_bucket.py",
    "tests/test_voting_political_hub_bucket.py",
    # ModuleNotFoundError: No module named 'congress_api.core.services' -- gone
    "tests/test_email_service.py",
    "tests/test_email_templates.py",
    "tests/test_upgrade_email.py",
    "tests/test_user_creation.py",
}

KNOWN_FAILURES = {
    # 'Mock' object is not subscriptable -- bucket test harness
    "tests/test_bucket_double_conversion.py::test_committee_intelligence_does_not_double_convert",
    "tests/test_bucket_double_conversion.py::test_records_and_hearings_does_not_double_convert",
    "tests/test_bucket_double_conversion.py::test_research_and_professional_does_not_double_convert",
    "tests/test_bucket_double_conversion.py::test_voting_and_nominations_does_not_double_convert",
    # async def with no asyncio marker and no asyncio_mode configured
    "tests/test_registration_endpoint.py::test_registration_endpoint",
    "tests/test_registration_endpoint.py::test_health_endpoint",
}


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
    failures, collection_errors = run_suite()
    ok = report("failure", failures, KNOWN_FAILURES)
    ok &= report("collection error", collection_errors, KNOWN_COLLECTION_ERRORS)
    if ok:
        print(
            f"Baseline matches: {len(KNOWN_FAILURES)} known failures, "
            f"{len(KNOWN_COLLECTION_ERRORS)} known collection errors, nothing new."
        )
        return 0
    print("\nThe known-failing set changed. Investigate, then update KNOWN_FAILURES.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
