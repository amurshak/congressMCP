"""F40 conformance: every amends kind the extractor can emit round-trips
through every response model that carries amends, enumerated from the ONE
shared vocabulary (models.AMENDS_KINDS) and pinned individually -- the
00-INDEX enumeration rule. Two literals kept in sync by discipline was
F40's cause: the A8 `usc_note` kind shipped in the extractor while the
models' Literal rejected it, and validation discarded ENTIRE responses --
text included -- on both tools.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from congress_api.features.bill_text import parser
from congress_api.features.bill_text.models import (
    AMENDS_KINDS,
    AmendsTarget,
    BillSectionResponse,
    SearchBillTextResponse,
    SearchHit,
)


def test_vocabulary_members_pinned_individually():
    # The enumeration itself, each member its own assertion: a vocabulary
    # whose members are not individually pinned is the assumption the
    # enumeration rule exists to reject.
    assert "usc" in AMENDS_KINDS
    assert "usc_note" in AMENDS_KINDS
    assert "public_law" in AMENDS_KINDS
    assert len(AMENDS_KINDS) == 3


def test_extractor_source_emits_no_sibling_kinds():
    # F40 fix order: verify no sibling kinds slipped in, against the
    # source of truth -- not the error message, which reports only the
    # first failure. Scans the extractor source for every kind literal
    # fed into the `found` set.
    source = Path(parser.__file__).read_text()
    emitted = set(re.findall(r'found\.add\(\(\s*"([a-z_]+)"', source))
    assert emitted, "instrument dead: no emission sites found in parser"
    assert emitted <= set(AMENDS_KINDS), (
        f"extractor emits kind(s) outside the shared vocabulary: "
        f"{sorted(emitted - set(AMENDS_KINDS))}")


def _hit(entry: dict) -> dict:
    return {
        "section_id": "S:2", "node_kind": "structural",
        "ancestor_path": [], "header": "Amendments",
        "snippet": "is amended", "match_contexts": ["operative"],
        "matched_queries": ["amended"], "is_amendatory": True,
        "amends": [entry], "score": 1.0,
        "byte_length": 10, "subtree_byte_length": 10,
    }


def _envelope() -> dict:
    return {
        "package_id": "BILLS-119hr1362ih", "version": "ih",
        "version_resolved_at": "2026-08-27T00:00:00Z",
        "govinfo_url": "https://www.govinfo.gov/x",
        "sections_indexed": 1, "chunks_indexed": 0,
    }


@pytest.mark.parametrize("kind", AMENDS_KINDS)
def test_amends_target_round_trip(kind):
    target = AmendsTarget.model_validate(
        {"kind": kind, "cite": "42 U.S.C. 2210 note"})
    assert target.model_dump()["kind"] == kind


@pytest.mark.parametrize("kind", AMENDS_KINDS)
def test_search_hit_round_trip(kind):
    entry = {"kind": kind, "cite": "42 U.S.C. 2210 note"}
    hit = SearchHit.model_validate(_hit(entry))
    assert hit.model_dump()["amends"] == [entry]


@pytest.mark.parametrize("kind", AMENDS_KINDS)
def test_search_response_round_trip(kind):
    # The full wire shape search_bill_text serializes -- F40 discarded
    # THIS model's whole payload when one amends entry failed.
    entry = {"kind": kind, "cite": "P.L. 101-426"}
    payload = dict(_envelope(), chunks_searched=0,
                   queries_used=["amended"], hits=[_hit(entry)])
    response = SearchBillTextResponse.model_validate(payload)
    assert response.model_dump()["hits"][0]["amends"] == [entry]


@pytest.mark.parametrize("kind", AMENDS_KINDS)
def test_bill_section_response_round_trip(kind):
    # The section-direct path (and the F33 assembled shape aggregates
    # into this same model's amends field).
    entry = {"kind": kind, "cite": "10 U.S.C. 2304 note"}
    payload = dict(
        _envelope(), section_id="S:2", node_kind="structural",
        ancestor_path=[], header="X", text="is amended",
        is_amendatory=True, amends=[entry],
        byte_length=10, subtree_byte_length=10, truncated=False)
    response = BillSectionResponse.model_validate(payload)
    assert response.model_dump()["amends"] == [entry]


def test_unknown_kind_still_rejected_by_models():
    # Widening must not mean open: the models still reject a kind
    # outside the vocabulary (the detector is not vacuous).
    with pytest.raises(ValidationError):
        AmendsTarget.model_validate({"kind": "bogus", "cite": "x"})


_TRAILER_XML = b"""<?xml version="1.0"?>
<bill><legis-body>
<section id="s1"><enum>1.</enum><header>Amendment</header>
<text>The Radiation Exposure Compensation Act (42 U.S.C. 2210 note;
Public Law 101-426) is amended by striking section 2.</text></section>
</legis-body></bill>"""


def test_extractor_guard_fires_on_unshared_kind(monkeypatch):
    # Non-vacuity of the F40 choke-point guard: an emission outside the
    # shared vocabulary fails loudly AT EXTRACTION, never by reaching the
    # models. Injected at the trailer pass; any pass feeds the same
    # guarded set.
    parsed = parser.parse_bill_xml(_TRAILER_XML, "BILLS-119hr0ih", "ih", None)
    unit = next(u for u in parsed.units if u.is_amendatory)
    assert any(e["kind"] == "usc_note" for e in unit.amends)  # baseline

    monkeypatch.setattr(parser, "_paren_trailer_cites",
                        lambda body, pl_precedes=False: {("bogus", "X")})
    with pytest.raises(ValueError, match="bogus"):
        _ = unit.amends
