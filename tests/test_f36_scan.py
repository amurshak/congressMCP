"""Planted positives and negatives for the F36 measurement (tests/corpus/f36_scan.py).

Corpus-scan hygiene: every population the scan counts has a planted positive that
fires alone, and every exclusion has a planted negative that does not fire. The
detector's count is not evidence until this holds.

Run with: pytest tests/test_f36_scan.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from congress_api.features.bill_text.parser import Segment, Unit  # noqa: E402
from tests.corpus import f36_scan  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "bill_text_trimmed.xml"
RECA = "(Public Law 101–426; 42 U.S.C. 2210 note)"


def _unit(*segments: tuple[str, str], section_id: str = "S:1") -> Unit:
    return Unit(section_id=section_id, ancestor_path=[], header=None,
                segments=[Segment(c, t) for c, t in segments])


def _only(rec: dict) -> dict:
    assert len(rec["instances"]) == 1, rec["instances"]
    return rec["instances"][0]


# --------------------------------------------------------------------------- #
# Positives -- each population fires alone
# --------------------------------------------------------------------------- #
def test_live_miss_shape_is_strict_no_entry_en_dash():
    # The F36 repro, verbatim shape: parser yields amends == [] and the scan counts it.
    u = _unit(("operative", "Section 5A of the Radiation Exposure Compensation Act "
               f"{RECA} is amended by striking “x”."))
    assert u.is_amendatory and u.amends == [], "if this fires, F36 is fixed -- retire the scan"
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and i["no_entry"] and not i["partial"]
    assert i["shape"] == "pl+usc_note" and i["pl_dash"] == "en-dash"
    assert i["pl"] == "P.L. 101-426" and i["usc_note"] == "42 U.S.C. 2210"
    assert i["missing"] == ["P.L. 101-426", "42 U.S.C. 2210"]


def test_hyphen_public_law_form_is_matched_and_labelled():
    u = _unit(("operative", "Section 2 of the Foo Act (Public Law 101-426; 42 U.S.C. "
               "2210 note) is amended by striking “x”."))
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and i["no_entry"] and i["pl_dash"] == "hyphen"


def test_usc_note_only_parenthetical_is_its_own_shape():
    u = _unit(("operative", "Section 6071(h) of the Deficit Reduction Act of 2005 "
               "(42 U.S.C. 1396a note) is amended— in paragraph (1), by striking "
               "“x”."))
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "strict" and i["no_entry"] and i["shape"] == "usc_note"
    assert i["pl"] is None and i["usc_note"] == "42 U.S.C. 1396a"


def test_interposed_clause_is_relaxed_tier_not_strict():
    # hr10115 S:3 -- the A6 class, reported beside F36 and never counted as it.
    u = _unit(("operative", f"Section 5A of the Radiation Exposure Compensation Act {RECA}, "
               "as added by section 110204 of Public Law 118–5, is amended by "
               "striking “x”."))
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] == "relaxed" and i["no_entry"] and not i["provenance"]


def test_partial_capture_is_reported_beside_not_counted_as_no_entry():
    # "(43 U.S.C. 1331 note; Public Law 109-432) is amended": the P.L. form's hug
    # reaches the verb (P.L. captured), the USC-note does not.
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
    i = _only(f36_scan.scan_unit(u))
    assert i["tier"] is None and not i["provenance"]


def test_provenance_parenthetical_is_excluded():
    u = _unit(("operative", "Section 3 of the Z Act, as added by section 5 of the W Act "
               "(Public Law 118–31; 10 U.S.C. 113 note), is amended by striking "
               "“x”."))
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


def test_unit_metric_counts_strict_no_entry_units_only():
    data = _fixture_with(f"Section 5A of the Radiation Exposure Compensation Act {RECA} "
                         "is amended by striking <quote>x</quote>.")
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
    assert report["totals"]["f36_units_strict"] == 1
    assert report["totals"]["documents"] == 1 and report["precision_sample"]
    md = (out / "report.md").read_text()
    assert "F36 unit count" in md and "D:A/T:I/S:101" in md
    # An extra with no parenthetical cite at all: denominators empty -> non-zero exit,
    # never a clean "0 found".
    plain = tmp_path / "BILLS-119s8enr.xml"
    plain.write_bytes(FIXTURE.read_bytes())
    assert f36_scan.main(["--extra", str(plain), "--out", str(tmp_path / "out2")]) == 1
    # Nothing to scan at all is also a refusal.
    assert f36_scan.main(["--out", str(tmp_path / "out3")]) == 1
    assert not os.path.exists(tmp_path / "out3" / "report.json")
