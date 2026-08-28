"""Planted positives and negatives for the F36 scan (tests/corpus/f36_scan.py).

Corpus-scan hygiene: every population the scan counts has a planted positive that
fires alone, and every exclusion has a planted negative that does not fire. The
detector's count is not evidence until this holds.

POST-FIX (A8, 2026-08-27): the parser now extracts the parenthetical-trailer
citations, so the live shapes DRAIN -- the scan is the acceptance instrument and
these tests pin both directions: (a) the fixed parser satisfies each shape (no
longer counted missing), and (b) the detector still counts a miss when one
exists -- simulated by disabling the trailer pattern (a regression stand-in),
so a drained corpus report can never be the vacuous output of a detector that
stopped detecting.

Run with: pytest tests/test_f36_scan.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from congress_api.features.bill_text import parser as parser_mod  # noqa: E402
from congress_api.features.bill_text.parser import Segment, Unit  # noqa: E402
from tests.corpus import f36_scan  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "bill_text_trimmed.xml"
RECA = "(Public Law 101–426; 42 U.S.C. 2210 note)"
# A regex that can never match: stands in for a regression of the A8 trailer
# pass, restoring the pre-fix miss so the detector's counting stays testable.
_NEVER = re.compile(r"(?!x)x")


@pytest.fixture
def broken_trailer(monkeypatch):
    monkeypatch.setattr(parser_mod, "AMENDS_PAREN_TRAILER_RE", _NEVER)


def _unit(*segments: tuple[str, str], section_id: str = "S:1") -> Unit:
    return Unit(section_id=section_id, ancestor_path=[], header=None,
                segments=[Segment(c, t) for c, t in segments])


def _only(rec: dict) -> dict:
    assert len(rec["instances"]) == 1, rec["instances"]
    return rec["instances"][0]


# --------------------------------------------------------------------------- #
# The fixed parser drains each live shape -- and the detector still sees a
# miss when the trailer pass is broken (non-vacuity, both directions)
# --------------------------------------------------------------------------- #
def test_live_miss_shape_now_extracts_and_scan_reports_it_satisfied():
    # The F36 repro, verbatim shape: post-A8 the parser extracts both cites and
    # the scan records the instance as fully in amends.
    u = _unit(("operative", "Section 5A of the Radiation Exposure Compensation Act "
               f"{RECA} is amended by striking “x”."))
    assert u.is_amendatory
    assert u.amends == [
        {"kind": "public_law", "cite": "P.L. 101-426"},
        {"kind": "usc_note", "cite": "42 U.S.C. 2210 note"},
    ]
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and not i["no_entry"] and not i["partial"]
    assert i["shape"] == "pl+usc_note" and i["pl_dash"] == "en-dash"
    assert i["pl"] == "P.L. 101-426" and i["usc_note"] == "42 U.S.C. 2210"
    assert i["in_amends"] == ["P.L. 101-426", "42 U.S.C. 2210"]
    assert i["missing"] == []


def test_detector_still_counts_a_miss_when_the_trailer_pass_is_broken(broken_trailer):
    # Non-vacuity: with the A8 pattern disabled the pre-fix miss returns, and
    # the scan counts it exactly as the 2026-08-22 measurement did.
    u = _unit(("operative", "Section 5A of the Radiation Exposure Compensation Act "
               f"{RECA} is amended by striking “x”."))
    assert u.amends == []
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and i["no_entry"] and not i["partial"]
    assert i["missing"] == ["P.L. 101-426", "42 U.S.C. 2210"]


def test_hyphen_public_law_form_is_matched_labelled_and_satisfied():
    u = _unit(("operative", "Section 2 of the Foo Act (Public Law 101-426; 42 U.S.C. "
               "2210 note) is amended by striking “x”."))
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and not i["no_entry"] and i["pl_dash"] == "hyphen"


def test_usc_note_only_parenthetical_is_its_own_shape_and_satisfied():
    # The A8 membership predicate: the instance records the bare "T U.S.C. S"
    # (set identity with the pre-fix report) and is satisfied by the note-form
    # amends cite, never by a bare `usc` emission.
    u = _unit(("operative", "Section 6071(h) of the Deficit Reduction Act of 2005 "
               "(42 U.S.C. 1396a note) is amended— in paragraph (1), by striking "
               "“x”."))
    assert u.amends == [{"kind": "usc_note", "cite": "42 U.S.C. 1396a note"}]
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and not i["no_entry"] and i["shape"] == "usc_note"
    assert i["pl"] is None and i["usc_note"] == "42 U.S.C. 1396a"
    assert i["in_amends"] == ["42 U.S.C. 1396a"]


def test_usc_note_instance_is_not_satisfied_by_a_bare_usc_emission():
    # Wrong-kind extraction must still read as missing (A8's discriminator:
    # fetch-this-section on a note cite retrieves the wrong law).
    class _Fake:
        section_id = "S:1"
        segments = [Segment("operative",
                            "Section 1 of the Y Act (43 U.S.C. 1331 note) "
                            "is amended by striking “x”.")]
        is_amendatory = True
        amends = [{"kind": "usc", "cite": "43 U.S.C. 1331"}]
    i = _only(f36_scan.scan_unit(_Fake()))
    assert i["no_entry"] and i["missing"] == ["43 U.S.C. 1331"]


def test_interposed_clause_is_relaxed_tier_not_strict():
    # hr10115 S:3 -- the A6 class, reported beside F36 and never counted as it.
    # A8 keeps it out of scope: the interposed clause defeats the trailer hug,
    # so the cites stay unextracted and the scan still reports the class.
    u = _unit(("operative", f"Section 5A of the Radiation Exposure Compensation Act {RECA}, "
               "as added by section 110204 of Public Law 118–5, is amended by "
               "striking “x”."))
    assert u.amends == []
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "relaxed" and i["no_entry"] and not i["provenance"]


def test_note_first_partial_shape_now_extracts_both_cites():
    # Pre-fix PARTIAL: "(43 U.S.C. 1331 note; Public Law 109–432) is amended"
    # captured the P.L. (rightmost, hug reaches) and missed the note. Post-A8
    # both extract, order-independent.
    u = _unit(("operative", "Section 1 of the Y Act (43 U.S.C. 1331 note; Public Law "
               "109–432) is amended by striking “x”."))
    assert {a["cite"] for a in u.amends} == {"P.L. 109-432", "43 U.S.C. 1331 note"}
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and not i["partial"] and not i["no_entry"]
    assert sorted(i["in_amends"]) == ["43 U.S.C. 1331", "P.L. 109-432"]


def test_partial_is_still_reported_when_only_the_pl_lands(broken_trailer):
    # With the trailer pass broken, the P.L.'s own hug still fires on the
    # note-first order -- the pre-fix partial class, still countable.
    u = _unit(("operative", "Section 1 of the Y Act (43 U.S.C. 1331 note; Public Law "
               "109–432) is amended by striking “x”."))
    assert {a["cite"] for a in u.amends} == {"P.L. 109-432"}
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and i["partial"] and not i["no_entry"]
    assert i["in_amends"] == ["P.L. 109-432"] and i["missing"] == ["43 U.S.C. 1331"]


# --------------------------------------------------------------------------- #
# Negatives -- each exclusion holds
# --------------------------------------------------------------------------- #
def test_non_amendatory_reference_in_an_amendatory_unit_is_not_hugged():
    # hr10115 S:12 -- the live planted negative: the same parenthetical in a definition.
    u = _unit(("operative", "The term covered individual means an individual who has "
               f"received payment pursuant to a claim submitted under the Act {RECA}. "
               "Section 3 of title 5, United States Code, is amended by striking "
               "“x”."))
    assert u.is_amendatory
    # The definition's cites stay out of amends (V13 binds the new pattern too).
    assert {a["cite"] for a in u.amends} == {"5 U.S.C. 3"}
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] is None and not i["provenance"]


def test_provenance_parenthetical_is_excluded():
    u = _unit(("operative", "Section 3 of the Z Act, as added by section 5 of the W Act "
               "(Public Law 118–31; 10 U.S.C. 113 note), is amended by striking "
               "“x”."))
    assert u.amends == []
    i = _only(f36_scan.scan_unit(u))
    assert i["provenance"] and i["tier"] is None


def test_quoted_segments_are_never_scanned():
    # Scoping by segment identity (§6): inserted language carrying the shape is not a
    # candidate, however perfectly hugged.
    u = _unit(("operative", "Section 1 of title 10, United States Code, is amended to "
               "read as follows:"),
              ("quoted", f"Section 2 of the Q Act {RECA} is amended by striking x."))
    assert f36_scan.scan_unit(u) is None


def test_unit_without_any_parenthetical_cite_is_not_a_record():
    u = _unit(("operative", "Section 5601 of title 14, United States Code, is amended."))
    assert f36_scan.scan_unit(u) is None


# --------------------------------------------------------------------------- #
# Document-level metric and the artifact path
# --------------------------------------------------------------------------- #
def _fixture_with(text: str) -> bytes:
    xml = FIXTURE.read_text()
    old = ("Section 5601 of title 14, United States Code, is amended by striking "
           "<quote>icebreaker</quote> and inserting <quote>polar security cutter</quote>.")
    assert old in xml
    return xml.replace(old, text, 1).encode()


def test_unit_metric_drains_post_fix_and_counts_under_regression(broken_trailer):
    data = _fixture_with(f"Section 5A of the Radiation Exposure Compensation Act {RECA} "
                         "is amended by striking <quote>x</quote>.")
    # Under the simulated regression the metric counts the unit...
    d = f36_scan.scan_document("BILLS-119s9enr", data, "enr")
    assert d["amendatory_units"] >= 1 and d["instances_strict_no_entry"] == 1
    assert d["f36_units_strict"] == ["D:A/T:I/S:101"]
    assert d["f36_units_relaxed_only"] == []
    assert d["pl_dash_forms_strict_missing"] == {"en-dash": 1}
    assert d["strict_no_entry_shapes"] == {"pl+usc_note": 1}
    assert set(d) >= {"units", "amendatory_units", "units_with_paren_cite",
                      "instances_total", "instances_not_hugged", "instances_provenance",
                      "instances_strict", "instances_strict_partial", "instances_relaxed",
                      "instances_relaxed_no_entry", "sha256", "records"}


def test_unit_metric_is_zero_on_the_fixed_parser():
    data = _fixture_with(f"Section 5A of the Radiation Exposure Compensation Act {RECA} "
                         "is amended by striking <quote>x</quote>.")
    d = f36_scan.scan_document("BILLS-119s9enr", data, "enr")
    assert d["amendatory_units"] >= 1 and d["instances_strict"] == 1
    assert d["instances_strict_no_entry"] == 0 and d["f36_units_strict"] == []


def test_main_writes_artifacts_and_refuses_empty_denominators(tmp_path, monkeypatch):
    monkeypatch.setenv(f36_scan.MANIFEST["cache_env"], str(tmp_path / "empty-corpus"))
    (tmp_path / "empty-corpus").mkdir()
    xml = tmp_path / "BILLS-119s9enr.xml"
    xml.write_bytes(_fixture_with(
        f"Section 5A of the Radiation Exposure Compensation Act {RECA} is amended by "
        "striking <quote>x</quote>."))
    out = tmp_path / "out"
    assert f36_scan.main(["--extra", str(xml), "--focus", "BILLS-119s9enr",
                          "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text())
    # Post-fix: the instance is present (denominator non-empty), drained.
    assert report["totals"]["instances_strict"] == 1
    assert report["totals"]["f36_units_strict"] == 0
    assert report["totals"]["documents"] == 1
    md = (out / "report.md").read_text()
    assert "F36 unit count" in md
    # An extra with no parenthetical cite at all: denominators empty -> non-zero exit,
    # never a clean "0 found".
    plain = tmp_path / "BILLS-119s8enr.xml"
    plain.write_bytes(FIXTURE.read_bytes())
    assert f36_scan.main(["--extra", str(plain), "--out", str(tmp_path / "out2")]) == 1
    # Nothing to scan at all is also a refusal.
    assert f36_scan.main(["--out", str(tmp_path / "out3")]) == 1
    assert not os.path.exists(tmp_path / "out3" / "report.json")
