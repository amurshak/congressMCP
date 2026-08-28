"""A8 consumer regression fixtures (work order, 14-defect-priority.md item 2).

The three sections from the 2026-08-25 consumer differential, enrolled in the
extended corpus (category f36-regression) and asserted here against the REAL
bill XML -- corpus-conditional like every extended-corpus test: when a
fixture's bytes are absent from the gitignored cache (CI without credentials),
its test skips; tests/corpus/fetch_corpus.py populates the cache.

- HR 1362 §2 -- note-first order "(42 U.S.C. 2210 note; Public Law 101–426)":
  extracted the P.L. even pre-fix; must not regress, and post-A8 emits BOTH.
- HR 7672 §3 -- the clean repro, P.L.-first: extracted nothing pre-fix; must
  extract both.
- HR 4631 §2 -- listed "must extract" in the work order, but the measured
  text is "...(Public Law 101–426; 42 U.S.C. 2210 note), as added by section
  100204 of Public Law 119–21, is amended..." -- an INTERPOSED provenance
  clause between the trailer and the verb: the A6 class, which A8 explicitly
  keeps out of scope ("not acceptance debt"). The two contract clauses
  collide on this bill; reported to the spec session with the fix. Until the
  spec rules (A6's flip condition governs -- and HR 4631 is now a THIRD
  document carrying the idiom), this test pins the standing behavior: the
  unit stays discoverable as amendatory with amends == [], and P.L. 119-21
  (the intervener that a naive relaxation would capture -- A6's trap) must
  never appear.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from congress_api.features.bill_text.parser import parse_bill_xml

_CORPUS_DIR = Path(__file__).parent / "corpus"
_MANIFEST = json.loads((_CORPUS_DIR / "manifest.json").read_text())

RECA_BOTH = [
    {"kind": "public_law", "cite": "P.L. 101-426"},
    {"kind": "usc_note", "cite": "42 U.S.C. 2210 note"},
]


def _load(package_id: str):
    cache = Path(os.getenv(_MANIFEST["cache_env"],
                           str(_CORPUS_DIR.parent.parent / _MANIFEST["cache_default"])))
    path = cache / f"{package_id}.xml"
    if not path.exists():
        pytest.skip(f"{package_id} not in corpus cache (run tests/corpus/fetch_corpus.py)")
    entry = next(p for p in _MANIFEST["packages"] if p["package_id"] == package_id)
    data = path.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    assert got == entry["sha256"], f"cache bytes for {package_id} do not match manifest"
    return parse_bill_xml(data, package_id, entry["version"], None)


def _unit(parsed, section_id: str):
    return next(u for u in parsed.units if u.section_id == section_id)


def test_hr1362_s2_note_first_emits_both_kinds():
    unit = _unit(_load("BILLS-119hr1362ih"), "S:2")
    assert unit.is_amendatory
    assert unit.amends == RECA_BOTH


def test_hr7672_s3_pl_first_clean_repro_emits_both_kinds():
    unit = _unit(_load("BILLS-119hr7672ih"), "S:3")
    assert unit.is_amendatory
    assert unit.amends == RECA_BOTH


def test_hr7672_order_independence_across_the_two_bills():
    # The differential that corroborated F36, on the real documents: the two
    # orders now yield the identical emitted set.
    a = _unit(_load("BILLS-119hr1362ih"), "S:2").amends
    b = _unit(_load("BILLS-119hr7672ih"), "S:3").amends
    assert a == b == RECA_BOTH


def test_hr4631_s2_is_the_a6_interposed_class_standing_behavior_pinned():
    # See the module docstring: work-order "must extract" vs A8's A6
    # carve-out -- conflict reported to the spec session; standing behavior
    # pinned until it rules. The load-bearing assertions: still discoverable
    # as amendatory, and the intervener (P.L. 119-21) never appears.
    unit = _unit(_load("BILLS-119hr4631ih"), "S:2")
    assert unit.is_amendatory          # the A5/A6 justification for the loss
    assert unit.amends == []           # A6 class: out of A8's scope
    text = " ".join(s.text for s in unit.segments if s.context == "operative")
    assert "as added by section 100204" in text  # the interposition is real
    cites = {a["cite"] for a in unit.amends}
    assert "P.L. 119-21" not in cites  # A6's trap: the intervener must not fire
