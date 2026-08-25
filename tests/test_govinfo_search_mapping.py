"""Step 2 of the govinfo-search work order (spec section 6.2): response
mapping. The load-bearing properties:

- packageId parse carries identity (carry, don't reconstruct); malformed
  ids are skipped, never guessed
- bill-level dedup in rank order, first occurrence wins
- the grouping property as a SET COMPARISON: the fetched records equal
  the union over hits of {bill} x matched_versions
- precedence fronting per the shipped 53-code table, including the
  dateless-version shape (precedence-primary, date only a tie-break)
- results_count counts the returned list (#65); total_version_matches is
  the upstream count under its honest name; search_source marks origin
- a corpus zero is readable (corpus-level query_diagnostics)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.features.buckets.bills import govinfo_search as gs  # noqa: E402


def _record(package_id, title=None, date=None):
    record = {"packageId": package_id,
              "title": title or f"Title of {package_id}"}
    if date is not None:
        record["dateIssued"] = date
    return record


# ---------------------------------------------------------------------------
# packageId parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("package_id,expected", [
    ("BILLS-119hr4631ih", (119, "hr", 4631, "ih")),
    ("BILLS-119s1071enr", (119, "s", 1071, "enr")),
    ("BILLS-103hconres76pcs2", (103, "hconres", 76, "pcs2")),
    ("BILLS-119hres5eh", (119, "hres", 5, "eh")),      # hres, not hr+'es5...'
    ("BILLS-119hr12345eh", (119, "hr", 12345, "eh")),  # no digit bleed
    ("BILLS-118sjres33ats", (118, "sjres", 33, "ats")),
])
def test_parse_package_id_well_formed(package_id, expected):
    assert gs.parse_package_id(package_id) == expected


@pytest.mark.parametrize("bad", [
    None, "", "PLAW-119publ1", "BILLS-119xx1ih", "BILLS-119hr1234",
    "BILLS-hr1234ih", "BILLS-119hr1234ih extra", "CREC-2026-01-01",
])
def test_parse_package_id_rejects_malformed(bad):
    assert gs.parse_package_id(bad) is None


# ---------------------------------------------------------------------------
# Grouping: rank order, set comparison, skip-not-guess
# ---------------------------------------------------------------------------

def test_grouping_set_comparison_fetched_equals_union_of_hits():
    # Interleaved bills, multiple versions each, in upstream rank order.
    records = [
        _record("BILLS-119hr4631ih"),
        _record("BILLS-119s1071enr"),
        _record("BILLS-119hr4631rh"),
        _record("BILLS-119hr10115ih"),
        _record("BILLS-119s1071is"),
        _record("BILLS-119s1071eah"),
    ]
    bills, skipped = gs.group_records(records)
    assert skipped == []
    fetched = {gs.parse_package_id(r["packageId"]) for r in records}
    union = {
        (b["congress"], b["bill_type"], b["bill_number"], v)
        for b in bills for v in b["matched_versions"]
    }
    assert fetched == union


def test_grouping_rank_order_first_occurrence_wins():
    records = [
        _record("BILLS-119hr2ih"),
        _record("BILLS-119s9is"),
        _record("BILLS-119hr2rh"),   # later record must not move HR 2's rank
        _record("BILLS-119hr7ih"),
    ]
    bills, _ = gs.group_records(records)
    assert [b["bill"] for b in bills] == ["HR 2", "S 9", "HR 7"]


def test_grouping_skips_malformed_ids_and_reports_them():
    records = [
        _record("BILLS-119hr1ih"),
        {"packageId": "PLAW-119publ1", "title": "not a bill"},
        {"title": "no id at all"},
        "not-even-a-dict",
    ]
    bills, skipped = gs.group_records(records)
    assert [b["bill"] for b in bills] == ["HR 1"]
    assert len(skipped) == 3


# ---------------------------------------------------------------------------
# Precedence fronting
# ---------------------------------------------------------------------------

def test_fronting_prefers_precedence_and_carries_that_record():
    records = [
        _record("BILLS-119hr1ih", title="Introduced title",
                date="2025-01-03"),
        _record("BILLS-119hr1enr", title="Enrolled title",
                date="2025-06-01"),
    ]
    bills, _ = gs.group_records(records)
    (bill,) = bills
    assert bill["version"] == "enr"
    assert bill["package_id"] == "BILLS-119hr1enr"   # carried, not rebuilt
    assert bill["title"] == "Enrolled title"
    assert bill["date_issued"] == "2025-06-01"
    assert bill["matched_versions"] == ["enr", "ih"]  # precedence-ordered


def test_fronting_dateless_version_precedence_primary():
    # enr with NO dateIssued must still outrank a dated ih: precedence is
    # primary; a missing date sorts last only within its own tier.
    records = [
        _record("BILLS-119hr1ih", date="2025-01-03"),
        _record("BILLS-119hr1enr"),          # dateless
    ]
    bills, _ = gs.group_records(records)
    assert bills[0]["version"] == "enr"
    assert bills[0]["date_issued"] is None


def test_fronting_unknown_code_loses_to_any_known_stage():
    records = [
        _record("BILLS-119hr1zzz9", date="2026-01-01"),  # unknown, newest
        _record("BILLS-119hr1ih", date="2025-01-01"),
    ]
    bills, _ = gs.group_records(records)
    assert bills[0]["version"] == "ih"
    assert bills[0]["matched_versions"] == ["ih", "zzz9"]


def test_fronting_negative_code_never_wins_over_text_stage():
    records = [
        _record("BILLS-119hr1fph", date="2026-01-01"),  # failed passage
        _record("BILLS-119hr1eh", date="2025-01-01"),
    ]
    bills, _ = gs.group_records(records)
    assert bills[0]["version"] == "eh"


# ---------------------------------------------------------------------------
# Response shape: counts, marker, readable zero
# ---------------------------------------------------------------------------

def test_counts_and_marker():
    records = [
        _record("BILLS-119hr1ih"),
        _record("BILLS-119hr1rh"),
        _record("BILLS-119s2is"),
    ]
    bills, _ = gs.group_records(records)
    response = gs.build_corpus_response(
        bills, total_version_matches=57,
        upstream_query="x collection:bills")
    assert response["search_source"] == "govinfo_fulltext"
    assert response["results_count"] == len(response["results"]) == 2  # #65
    assert response["total_version_matches"] == 57  # upstream, version-level
    assert "query_diagnostics" not in response


def test_zero_is_readable_not_bare():
    response = gs.build_corpus_response(
        [], total_version_matches=0,
        upstream_query="zzzqqx collection:bills congress:119",
        congress=119, bill_type=None)
    assert response["results_count"] == 0 and response["results"] == []
    diag = response["query_diagnostics"]
    assert "BILLS" in diag["corpus"]
    assert diag["upstream_query"] == "zzzqqx collection:bills congress:119"
    assert diag["scope"] == {"congress": 119, "bill_type": None}
    assert "ANDed" in diag["note"]


def test_request_note_rides_along_when_present():
    response = gs.build_corpus_response(
        [], 0, "q collection:bills",
        request_note="Limit 999 was too high, adjusted to 250")
    assert "adjusted" in response["request_note"]
    assert "request_note" not in gs.build_corpus_response(
        [], 0, "q collection:bills")
