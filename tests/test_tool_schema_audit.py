"""CI gate for scripts/audit_tool_schemas.py.

Runs the static schema-vs-implementation audit as part of the normal test
suite so drift between a bucket/flat tool's exposed schema and its actual
handler signature fails CI the same way any other regression would, instead
of requiring someone to remember to run the script by hand.

See scripts/audit_tool_schemas.py's module docstring for what counts as
"blocking" here: an EXTRA param a handler doesn't accept is only blocking if
the wrapper's own default guarantees it gets sent on every call (a
conditional EXTRA is already made safe at runtime by
validate_operation_kwargs, and is inherent to the bucket-tool design, not a
bug). MISSING_FROM_SCHEMA, DROPPED_BY_WRAPPER, UNUSED_IN_BODY, and any
resolution ERROR are always blocking.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-for-audit-test")

from scripts.audit_tool_schemas import format_report, run_audit  # noqa: E402


def test_no_blocking_schema_drift():
    results = run_audit()
    report, has_blocking = format_report(results, apply_allowlist=True)
    assert not has_blocking, (
        "Schema/implementation drift found (run `python scripts/audit_tool_schemas.py` "
        f"for the full report):\n{report}"
    )
