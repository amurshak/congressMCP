"""Rendering-version tripwire (spec §10 tail, F26 pattern).

The cache key is SCHEMA_VERSION. §10's rule: bump it for ANY change that alters
what a cached index serves -- not only the table schema but segment joining,
delimiter rendering, the header separator, and the byte-split boundary rules
(F12 reordered results on a whitespace-only change). A comment is not a guard;
this test is. index.rendering_fingerprint() hashes the AST of those symbols and
cache.RENDERING_FINGERPRINT pins it beside SCHEMA_VERSION, so changing any of
them without deliberately updating the pair fails CI.

The pin is VERSION-KEYED (F37, 2026-08-23): ast.dump of identical source is not
stable across interpreter series -- the 3.14 digest failed on CI's 3.12 -- so
cache.RENDERING_FINGERPRINTS maps each supported series (CI 3.12, dev 3.14) to
its digest, the bump-both-together rule extends to every entry, and an unlisted
series skips with a named reason. The golden-build digest
(test_bill_text_golden_build.py) is interpreter-stable and guards everywhere.

Run with: pytest tests/test_bill_text_rendering_tripwire.py
"""

from __future__ import annotations

import ast
import re
import textwrap

import pytest

import congress_api.features.bill_text.parser as parser_mod
from congress_api.features.bill_text import cache, index

SERIES = cache.interpreter_series()


def test_rendering_fingerprint_is_pinned_beside_schema_version():
    expected = cache.expected_rendering_fingerprint()
    if expected is None:
        pytest.skip(
            f"AST rendering pin has no entry for Python {SERIES} (pinned series: "
            f"{sorted(cache.RENDERING_FINGERPRINTS)}); ast.dump is not stable "
            "across interpreter series (F37), so this tripwire is skipped here. "
            "The golden-build digest still guards rendering on this interpreter. "
            "To pin this series: add cache.RENDERING_FINGERPRINTS["
            f"{SERIES!r}] = {index.rendering_fingerprint()!r}."
        )
    actual = index.rendering_fingerprint()
    assert actual == expected, (
        "A rendering-determining symbol changed (see index.RENDERING_SYMBOLS). "
        "A cached index built before this change would serve different chunks/"
        "rendering under the same key. If the change is deliberate: bump "
        f"cache.SCHEMA_VERSION (currently {cache.SCHEMA_VERSION}) AND re-pin EVERY "
        f"entry of cache.RENDERING_FINGERPRINTS in the same commit -- for Python "
        f"{SERIES} the new digest is {actual!r}; print index.rendering_fingerprint() "
        "under each other pinned series for theirs."
    )


def test_pinned_series_cover_ci_and_dev_and_look_like_digests():
    # CI pins 3.12 (.github/workflows/test.yml); dev runs 3.14. Dropping either
    # turns the tripwire into a skip on the very interpreter it must guard.
    assert {"3.12", "3.14"} <= set(cache.RENDERING_FINGERPRINTS)
    for series, digest in cache.RENDERING_FINGERPRINTS.items():
        assert re.fullmatch(r"\d+\.\d+", series), series
        assert re.fullmatch(r"[0-9a-f]{64}", digest), (series, digest)


def test_unlisted_interpreter_series_skips_with_a_named_reason(monkeypatch):
    monkeypatch.setattr(cache, "interpreter_series", lambda version_info=None: "3.99")
    assert cache.expected_rendering_fingerprint() is None
    assert cache.expected_rendering_fingerprint("3.14") == cache.RENDERING_FINGERPRINTS["3.14"]
    assert cache.interpreter_series((3, 12, 13, "final", 0)) == "3.99"  # patched
    monkeypatch.undo()
    assert cache.interpreter_series((3, 12, 13, "final", 0)) == "3.12"


def test_fingerprint_is_deterministic():
    assert index.rendering_fingerprint() == index.rendering_fingerprint()


def test_fingerprint_is_sensitive_to_a_rendering_constant(monkeypatch):
    # Non-vacuity: the pin must actually move when a covered symbol changes --
    # and a real rendering change must trip EVERY pinned series, not only the
    # one running here (F37 acceptance).
    before = index.rendering_fingerprint()
    every_pin = set(cache.RENDERING_FINGERPRINTS.values())
    monkeypatch.setattr(parser_mod, "MAX_UNIT_BYTES", parser_mod.MAX_UNIT_BYTES + 1)
    assert index.rendering_fingerprint() != before
    assert index.rendering_fingerprint() not in every_pin
    monkeypatch.undo()
    monkeypatch.setattr(parser_mod, "_QUOTE_OPEN", "<<")
    assert index.rendering_fingerprint() != before
    assert index.rendering_fingerprint() not in every_pin
    monkeypatch.undo()
    monkeypatch.setattr(index, "FTS_TOKENIZER", "unicode61")
    assert index.rendering_fingerprint() != before
    assert index.rendering_fingerprint() not in every_pin


def test_every_covered_symbol_resolves():
    # A renamed symbol must fail loudly here, not silently drop out of the hash.
    for module_name, dotted in index.RENDERING_SYMBOLS:
        assert index._symbol_digest_input(module_name, dotted)


def test_comments_and_docstrings_do_not_trip_it():
    # The digest is over the AST with docstrings stripped: formatting, comments
    # and prose edits are free; a logic change is not.
    a = textwrap.dedent('''
        def f(x):
            """Doc A."""
            # comment A
            return x + 1
    ''')
    b = textwrap.dedent('''
        def f(x):
            """Doc B, rewritten."""

            # a different comment, and blank lines
            return x+1
    ''')
    c = textwrap.dedent('''
        def f(x):
            """Doc A."""
            return x + 2
    ''')
    dump = lambda src: ast.dump(index._strip_docstrings(ast.parse(src)), include_attributes=False)  # noqa: E731
    assert dump(a) == dump(b)
    assert dump(a) != dump(c)


def test_named_rendering_areas_are_all_covered():
    # The four §10 names, by the symbols that implement them, plus the storage
    # definitions. Dropping one from RENDERING_SYMBOLS is a silent narrowing.
    covered = {dotted for _, dotted in index.RENDERING_SYMBOLS}
    assert {"join_segments", "render_segments", "_QUOTE_OPEN", "_QUOTE_CLOSE", "_ATTACH_PUNCT"} <= covered  # joining + delimiters + header separator
    assert {"collapse_ws", "normalize_text", "_tighten_punct"} <= covered  # stored-text normalization
    assert {"byte_split_unit", "_segment_atoms", "_bound_atom", "_chunk_unit", "MAX_UNIT_BYTES"} <= covered  # byte-split boundaries
    assert {"FTS_TOKENIZER", "_SCHEMA_SQL", "BillTextIndex._build", "load_parsed"} <= covered  # storage
