"""D17/D18 characterization tests (tool-defect-register, joint entry) --
the register's standing rule: regression probes land with the fix.

The two asserts from the register's entry are pinned here verbatim in
spirit, driven by the measured 2026-08-24 upstream shapes (spec 2b):
- A1: the full unquoted title -> count 1, exactly BILLS-119hr4631ih
- A2: 'Radiation Exposure Compensation' (no 'Act') -> 31 RECA records
- A3: the D17 differential is structurally dead -- two queries sharing
  only 'Act' cannot return byte-identical lists, because the caller's
  words reach the corpus matcher ANDed instead of being OR-substring
  matched against a recency page
- A4: zzzqqx -> honest, diagnosable zero (not an error, not noise)
- A8: 119hr10115ih reachable by keywords (the 2026-08-22 real-use miss)

These run against mocked upstream responses REPLAYING the measured
outcomes; the live A1-A8 acceptance run (scripts/
govinfo_search_acceptance.py) is the measurement itself.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.features.buckets.bills import api as mod  # noqa: E402


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


@pytest.fixture(autouse=True)
def _keyed(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(client_mod, "API_KEY", "test-key-govinfo-search")


class FakeSearchResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _reca_record(package_id, title):
    return {"packageId": package_id, "title": title,
            "dateIssued": "2025-06-05"}


# The measured 2b outcomes, keyed by the caller's keywords as they appear
# leading the assembled query.
_MEASURED = {
    "St. Louis RECA Readjustment Act": {
        "count": 1, "offsetMark": "end-cursor", "results": [
            _reca_record("BILLS-119hr4631ih",
                         "St. Louis RECA Readjustment Act")]},
    "Radiation Exposure Compensation": {
        "count": 31, "offsetMark": "c31", "results": [
            _reca_record(f"BILLS-119hr{4600 + n}ih",
                         f"RECA-related bill {n}") for n in range(31)]},
    "Radiation Exposure Compensation Act": {
        "count": 31, "offsetMark": "c31", "results": [
            _reca_record(f"BILLS-119hr{4600 + n}ih",
                         f"RECA-related bill {n}") for n in range(1, 32)]},
    "zzzqqx": {"count": 0, "offsetMark": None, "results": []},
    "RECA": {
        "count": 6, "offsetMark": "c6", "results": [
            _reca_record("BILLS-119hr4631ih",
                         "St. Louis RECA Readjustment Act"),
            _reca_record("BILLS-119hr10115ih",
                         "RECA Extension Act"),
        ] + [_reca_record(f"BILLS-119s{n}is", f"RECA bill {n}")
             for n in range(4)]},
}


async def _search(keywords, **kwargs):
    async def fake_post(body):
        query = body["query"]
        for kw, payload in _MEASURED.items():
            if query.startswith(kw + " collection:bills"):
                return FakeSearchResponse(payload)
        raise AssertionError(f"unexpected query: {query!r}")

    with patch.object(mod, "govinfo_search_post", side_effect=fake_post), \
            patch.object(mod, "fetch_bill_data", AsyncMock()):
        return await mod.search_bills(FakeContext(), keywords=keywords,
                                      congress=119, **kwargs)


@pytest.mark.asyncio
async def test_a1_hr4631_reachable_by_its_own_exact_title():
    # The register's first assert: fails on the old window (returned 10
    # unrelated bills, none of them HR 4631).
    out = await _search("St. Louis RECA Readjustment Act")
    assert "HR 4631" in out
    payload = json.loads(out)
    assert payload["results"][0]["package_id"] == "BILLS-119hr4631ih"


@pytest.mark.asyncio
async def test_a2_dropping_act_does_not_zero_the_query():
    # The register's second assert: 'Radiation Exposure Compensation'
    # returned 0 on the old matcher.
    out = await _search("Radiation Exposure Compensation")
    payload = json.loads(out)
    assert payload["results_count"] > 0
    assert payload["total_version_matches"] == 31


@pytest.mark.asyncio
async def test_a3_differential_is_dead():
    # D17's pinned differential: two queries sharing no token but 'Act'
    # returned byte-identical top-10 lists. Dead: results now track the
    # query's own terms.
    reca = json.loads(await _search("Radiation Exposure Compensation",
                                    limit=10))
    named = json.loads(await _search("St. Louis RECA Readjustment Act",
                                     limit=10))
    assert json.dumps(reca["results"]) != json.dumps(named["results"])
    # and dropping 'Act' from a matching query must not zero it (above),
    # nor must adding it: both forms return the RECA set, not a newest-
    # bills page.
    with_act = json.loads(await _search("Radiation Exposure Compensation "
                                        "Act", limit=10))
    assert with_act["results_count"] > 0


@pytest.mark.asyncio
async def test_a4_nonsense_is_an_honest_diagnosable_zero():
    payload = json.loads(await _search("zzzqqx"))
    assert payload["results_count"] == 0
    assert payload["results"] == []
    assert "error" not in payload
    assert payload["query_diagnostics"]["upstream_query"].startswith("zzzqqx")


@pytest.mark.asyncio
async def test_a8_hr10115_reachable_by_keyword():
    # The 2026-08-22 real-use failure: a live session could not reach
    # 119hr10115ih through search_bills at all. RECA -> 6 hits including
    # it (measured).
    payload = json.loads(await _search("RECA"))
    ids = {r["package_id"] for r in payload["results"]}
    assert "BILLS-119hr10115ih" in ids
    assert "BILLS-119hr4631ih" in ids
    # Q8/cache composition: the hit carries the identifiers a follow-up
    # search_bill_text call needs.
    hit = next(r for r in payload["results"]
               if r["package_id"] == "BILLS-119hr10115ih")
    assert (hit["congress"], hit["bill_type"], hit["bill_number"]) == \
        (119, "hr", 10115)
    assert hit["version"] in hit["matched_versions"]


@pytest.mark.asyncio
async def test_a5_monotonicity_smaller_limit_is_a_prefix():
    # By construction (identical upstream ranking, rank-order dedup) --
    # asserted here at the mapping level with a constant record stream.
    records = [{"packageId": f"BILLS-119hr{n}ih", "title": f"B{n}",
                "dateIssued": "2026-01-01"} for n in range(1, 31)]

    def payload(limit):
        return {"count": 30, "offsetMark": "c",
                "results": records[:3 * limit]}

    async def run(limit):
        async def fake_post(body):
            return FakeSearchResponse(payload(limit))
        with patch.object(mod, "govinfo_search_post",
                          side_effect=fake_post):
            out = await mod.search_bills(FakeContext(), keywords="x",
                                         limit=limit)
        return [r["package_id"] for r in json.loads(out)["results"]]

    import asyncio  # noqa: F401  (pytest-asyncio drives the loop)
    small = await run(5)
    large = await run(10)
    assert small == large[:len(small)]
