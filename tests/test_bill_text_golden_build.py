"""Golden-build fingerprint (spec §10 tail, ruled 2026-08-21).

The AST tripwire (test_bill_text_rendering_tripwire.py) names the touched
symbol but measures source. This measures the property: build the in-tree
trimmed fixtures through the REAL build path (PackageStore.build_and_publish),
dump every stored row in canonical order, sha256 it, and pin the digest beside
SCHEMA_VERSION. Any change -- parser semantics such as AMENDATORY_RE or amends
resolution, the segmenter, the schema, the tokenizer -- that would make a
rebuilt package differ from a cached one fails here; a pure refactor does not.
A trimmed fixture detects change, not correctness (§13).

Run with: pytest tests/test_bill_text_golden_build.py
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

import pytest

import congress_api.features.bill_text.parser as parser_mod
from congress_api.features.bill_text import cache, index
from congress_api.features.bill_text.parser import parse_bill_xml
from congress_api.features.bill_text.store import PackageStore

FIXTURES = Path(__file__).parent / "fixtures"

# (fixture file, package_id, version, last_modified) -- fixed inputs so the
# build is a pure function of the code under test.
GOLDEN_INPUTS = (
    ("bill_text_trimmed.xml", "BILLS-119s1071enr", "enr", "2025-12-19T03:11:48Z"),
    ("hres_trimmed.xml", "BILLS-119hres1ih", "ih", "2025-01-03T00:00:00Z"),
    ("hres_preamble_trimmed.xml", "BILLS-119hres2ih", "ih", "2025-01-03T00:00:00Z"),
    # F35/F36 (2026-08-27): the three fixtures above exercise neither a
    # subdivided section (F35's enum rendering) nor a parenthetical citation
    # trailer (F36's amends extraction) -- measured during the fix: the digest
    # did NOT move on either change, a blind spot in this instrument. This
    # fixture makes both properties visible to the golden build.
    ("f35_f36_trimmed.xml", "BILLS-119hr9999ih", "ih", "2025-01-03T00:00:00Z"),
)


def golden_build(tmp_path: Path) -> str:
    store = PackageStore(cache.CacheSettings(cache_dir=tmp_path / "golden", max_bytes=10**12), reconcile=False)
    h = hashlib.sha256()
    try:
        for name, package_id, version, last_modified in GOLDEN_INPUTS:
            parsed = parse_bill_xml((FIXTURES / name).read_bytes(), package_id, version, last_modified)
            built, _ = store.build_and_publish(parsed, last_modified=last_modified)  # the real path
            built.close()
            conn = sqlite3.connect(f"file:{store.layout.package_path(package_id)}?mode=ro", uri=True)
            try:
                digest = index.canonical_rows_digest(conn)
            finally:
                conn.close()
            h.update(f"{name} {package_id}\n{digest}\n".encode())
    finally:
        store.close()
    return h.hexdigest()


def test_golden_build_is_pinned_beside_schema_version(tmp_path):
    actual = golden_build(tmp_path)
    assert actual == cache.GOLDEN_BUILD_FINGERPRINT, (
        "A rebuilt package now differs from what a cached one holds (stored rows "
        "changed: parser semantics, segmenter, schema, or tokenizer). Every cached "
        "package in the wild would serve stale field values under the same key. "
        "If deliberate: bump cache.SCHEMA_VERSION "
        f"(currently {cache.SCHEMA_VERSION}) AND set cache.GOLDEN_BUILD_FINGERPRINT = "
        f"{actual!r} in the same commit. (Run test_bill_text_rendering_tripwire to "
        "learn which rendering symbol moved, if one did.)"
    )


def test_golden_build_is_deterministic(tmp_path):
    assert golden_build(tmp_path / "a") == golden_build(tmp_path / "b")


def test_golden_build_moves_on_a_parser_semantics_change(tmp_path, monkeypatch):
    # Non-vacuity for exactly the class the ruling names: an is_amendatory
    # detector change touches no rendering symbol but changes stored values.
    before = golden_build(tmp_path / "a")
    monkeypatch.setattr(parser_mod, "AMENDATORY_RE", re.compile(r"(?!x)x"))  # matches nothing
    assert golden_build(tmp_path / "b") != before


def test_golden_build_ignores_a_pure_refactor(tmp_path, monkeypatch):
    # Replacing a rendering function with a behavior-identical wrapper moves the
    # AST tripwire (it measures source) but must NOT move the golden build.
    before = golden_build(tmp_path / "a")
    real = parser_mod.collapse_ws
    monkeypatch.setattr(parser_mod, "collapse_ws", lambda text: real(text))
    assert golden_build(tmp_path / "b") == before


def test_canonical_dump_excludes_cache_owned_and_timestamp_columns():
    # Only build output: document/units/segments/seg_vocab. meta (cache-owned:
    # schema_version, build_complete) is not part of the golden surface, and no
    # covered table has a timestamp column.
    tables = [t for t, _ in index.GOLDEN_TABLES]
    assert tables == ["document", "units", "segments", "seg_vocab"]
    assert "meta" not in tables
