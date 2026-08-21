"""The known-failure baseline has ONE record: KNOWN_FAILURES.md (F24 / #20).

check_known_failures.py used to carry a second, unlinked Python copy of the
set; these tests pin the single-source contract -- the fenced blocks of the
markdown ARE the baseline the checker runs against.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

from check_known_failures import BASELINE_DOC, parse_baseline  # noqa: E402


def test_fenced_entries_classify_by_node_id():
    doc = """# heading
prose that must be ignored, even mentioning tests/test_prose.py

```
tests/test_broken_import.py
tests/test_thing.py::test_one
```

more prose

```
tests/test_thing.py::test_two
```
"""
    failures, collection_errors = parse_baseline(doc)
    assert failures == {"tests/test_thing.py::test_one", "tests/test_thing.py::test_two"}
    assert collection_errors == {"tests/test_broken_import.py"}


def test_the_real_baseline_parses_and_every_entry_names_an_existing_concern():
    failures, collection_errors = parse_baseline(BASELINE_DOC.read_text())
    assert failures and collection_errors, "empty baseline -- fences lost in an edit?"
    # A baselined collection error over a file that no longer exists is a stale
    # entry the checker would report as NOW PASSING forever; catch it here first.
    for entry in collection_errors:
        assert (REPO / entry).exists(), f"baselined file {entry} does not exist"
    for entry in failures:
        assert (REPO / entry.split("::")[0]).exists(), f"baselined file behind {entry} does not exist"
    # The six fastmcp-era bucket files were deleted (F24), not fixed; they must
    # never quietly return to the baseline.
    assert not any("hub_bucket" in entry for entry in collection_errors | failures)
