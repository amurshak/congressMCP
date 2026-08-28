"""Q11 local snippets (govinfo-search-spec Addendum 4 item 1).

The ruling's test list, each pinned here:
  * structural distinctness of all three states on one response
  * cache-only mode makes ZERO network calls (call-counter asserted -- the
    F21 instrument pattern)
  * snippet_fetch caps at 5, fetches exactly min(N, uncached hits) in rank
    order, and the fetched packages land enrolled
  * per-term localization matches a hit that phrase-matching would miss
  * the empty-string snippet is unrepresentable
  * match_contexts present on every emitted snippet (the quoted-governs
    sentence is pinned in test_govinfo_search_description.py)

Run with: pytest tests/test_govinfo_snippets.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-snippets")

import congress_api.features.bill_text.client as client_mod  # noqa: E402
import congress_api.features.bill_text.service as service_mod  # noqa: E402
import congress_api.features.buckets.bills.api as api_mod  # noqa: E402
from congress_api.features.bill_text import cache  # noqa: E402
from congress_api.features.bill_text.parser import parse_bill_xml  # noqa: E402
from congress_api.features.buckets.bills import govinfo_snippets  # noqa: E402
from congress_api.features.buckets.bills.govinfo_snippets import (  # noqa: E402
    LocalizedSnippet,
    attach_snippets,
    clamp_snippet_fetch,
    extract_text_terms,
)

FIXTURES = Path(__file__).parent / "fixtures"
BILL_XML = (FIXTURES / "bill_text_trimmed.xml").read_bytes()
HRES_XML = (FIXTURES / "hres_trimmed.xml").read_bytes()


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    service_mod.reset_store()
    yield service_mod.get_store()
    service_mod.reset_store()


def _enroll(store, xml: bytes, package_id: str, version: str):
    parsed = parse_bill_xml(xml, package_id, version, "2025-01-01T00:00:00Z")
    index, _ = store.build_and_publish(parsed, last_modified="2025-01-01T00:00:00Z")
    index.close()


def _hit(package_id: str, version: str) -> dict:
    return {"package_id": package_id, "version": version}


# --------------------------------------------------------------------------- #
# Parameter clamp and term extraction
# --------------------------------------------------------------------------- #
def test_clamp_snippet_fetch_defaults_caps_and_rejects():
    assert clamp_snippet_fetch(None) == (0, None)
    assert clamp_snippet_fetch(0) == (0, None)
    assert clamp_snippet_fetch(5) == (5, None)
    clamped, note = clamp_snippet_fetch(9)
    assert clamped == 5 and "clamped" in note and "9" in note
    from congress_api.core.exceptions import CongressionalAPIError
    for bad in (-1, "3", 2.5, True):
        with pytest.raises(CongressionalAPIError):
            clamp_snippet_fetch(bad)


def test_extract_text_terms_drops_query_language_keeps_text():
    terms = extract_text_terms(
        'congress:119 billtype:hr "Radiation Exposure" compensation AND '
        'downwinders NOT mining -uranium title:"Some Act" '
        'publishdate:range(2025-01-01,2025-02-01) wild*card')
    assert terms == ["Radiation Exposure", "compensation", "downwinders",
                     "wildcard"]
    # Pure fielded query: nothing to localize.
    assert extract_text_terms("congress:119 billtype:s docnumber:1071") == []


# --------------------------------------------------------------------------- #
# The structural tri-state, on one bills list
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_three_states_are_structurally_distinct_on_one_response(store):
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")   # matches "icebreaker"
    _enroll(store, HRES_XML, "BILLS-119hres1ih", "ih")     # does not
    bills = [
        _hit("BILLS-119s1071enr", "enr"),   # cached, term matches -> localized
        _hit("BILLS-119hres1ih", "ih"),     # cached, no match -> not_localized
        _hit("BILLS-119hr9999ih", "ih"),    # uncached, no budget -> absent
    ]
    fetched = await attach_snippets(bills, "icebreaker", 0)
    assert fetched == 0

    localized, missed, absent = bills
    assert localized["snippet_status"] == "localized"
    assert isinstance(localized["snippet"], dict)
    assert localized["snippet"]["text"]
    assert localized["snippet"]["section_id"]
    assert localized["snippet"]["match_contexts"]

    assert missed["snippet_status"] == "not_localized"
    assert missed["snippet"] is None

    assert "snippet_status" not in absent
    assert "snippet" not in absent
    # The three states are pairwise distinguishable from the serialized
    # response alone: status value, null-vs-object, and key absence.


@pytest.mark.asyncio
async def test_cache_only_mode_makes_zero_network_calls(store, monkeypatch):
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")
    calls = AsyncMock(side_effect=AssertionError("network touched"))
    monkeypatch.setattr(client_mod, "fetch_govinfo_package", calls)
    bills = [
        _hit("BILLS-119s1071enr", "enr"),
        _hit("BILLS-119hr9999ih", "ih"),   # uncached -- must NOT be fetched
    ]
    await attach_snippets(bills, "icebreaker", 0)
    assert calls.call_count == 0           # the F21 call-counter assertion
    assert bills[0]["snippet_status"] == "localized"
    assert "snippet_status" not in bills[1]


# --------------------------------------------------------------------------- #
# The opt-in bounded fetch
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_snippet_fetch_fetches_min_n_uncached_in_rank_order(store, monkeypatch):
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")
    fetch_order: list[str] = []

    async def fake_fetch(package_id, *, skip_download=None):
        fetch_order.append(package_id)
        return "2025-01-01T00:00:00Z", BILL_XML

    monkeypatch.setattr(client_mod, "fetch_govinfo_package", fake_fetch)
    bills = [
        _hit("BILLS-119s1071enr", "enr"),  # cached: consumes NO budget
        _hit("BILLS-119hr9991ih", "ih"),   # uncached #1 (best-ranked)
        _hit("BILLS-119hr9992ih", "ih"),   # uncached #2
        _hit("BILLS-119hr9993ih", "ih"),   # uncached #3: beyond budget
    ]
    fetched = await attach_snippets(bills, "icebreaker", 2)
    # Exactly min(N, uncached) fetches, in rank order, skipping cached hits.
    assert fetched == 2
    assert fetch_order == ["BILLS-119hr9991ih", "BILLS-119hr9992ih"]
    # The fetched packages land ENROLLED (Q8 requested warming).
    assert store.open("BILLS-119hr9991ih", None) is not None
    assert store.open("BILLS-119hr9992ih", None) is not None
    assert store.open("BILLS-119hr9993ih", None) is None
    # And their hits localized (the fixture text matches the term).
    assert bills[1]["snippet_status"] == "localized"
    assert bills[2]["snippet_status"] == "localized"
    assert "snippet_status" not in bills[3]


@pytest.mark.asyncio
async def test_failed_fetch_leaves_the_hit_in_the_absent_state(store, monkeypatch):
    async def broken_fetch(package_id, *, skip_download=None):
        raise OSError("network down")

    monkeypatch.setattr(client_mod, "fetch_govinfo_package", broken_fetch)
    bills = [_hit("BILLS-119hr9991ih", "ih")]
    fetched = await attach_snippets(bills, "icebreaker", 1)
    assert fetched == 0
    # No text ever existed locally to attempt against: absent, not
    # not_localized -- and the enrichment never fails the search.
    assert "snippet_status" not in bills[0]
    assert "snippet" not in bills[0]


# --------------------------------------------------------------------------- #
# Per-term localization
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_per_term_localization_matches_where_phrase_matching_misses(store):
    # "icebreaker" and "infrastructure" appear in DIFFERENT sections of the
    # fixture, so the two-word phrase matches nothing while per-term does --
    # the ruled semantic gap (GovInfo ANDs raw words; FTS5 matches phrases).
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")
    index = store.open("BILLS-119s1071enr", None)
    assert index.search(["icebreaker infrastructure"], 5) == []  # phrase misses
    assert index.search(["icebreaker", "infrastructure"], 5)    # per-term hits
    bills = [_hit("BILLS-119s1071enr", "enr")]
    await attach_snippets(bills, "icebreaker infrastructure", 0)
    assert bills[0]["snippet_status"] == "localized"


@pytest.mark.asyncio
async def test_pure_fielded_query_attempts_nothing(store):
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")
    bills = [_hit("BILLS-119s1071enr", "enr")]
    await attach_snippets(bills, "congress:119 billtype:s docnumber:1071", 0)
    assert "snippet_status" not in bills[0]
    assert "snippet" not in bills[0]


# --------------------------------------------------------------------------- #
# The unrepresentable states and the amendatory-trap disclosure
# --------------------------------------------------------------------------- #
def test_empty_snippet_text_is_unrepresentable():
    with pytest.raises(ValidationError):
        LocalizedSnippet(text="", section_id="S:1", match_contexts=["operative"])
    with pytest.raises(ValidationError):
        LocalizedSnippet(text="x", section_id="S:1", match_contexts=[])


def test_localize_downgrades_an_unrepresentable_snippet_structurally():
    class FakeUnit:
        section_id = "S:1"

    class FakeHitObj:
        unit = FakeUnit()
        snippet = ""            # the unrepresentable state
        match_contexts = ["operative"]

    class FakeIndex:
        def search(self, terms, max_hits):
            return [FakeHitObj()]

    hit: dict = {}
    govinfo_snippets._localize(hit, FakeIndex(), ["term"])
    assert hit["snippet_status"] == "not_localized"
    assert hit["snippet"] is None


@pytest.mark.asyncio
async def test_quoted_match_carries_contexts_and_delimited_text(store):
    # The fixture's S:102 quoted-block holds "Only quoted needle language
    # appears here" -- a snippet drawn from it must flag itself.
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")
    bills = [_hit("BILLS-119s1071enr", "enr")]
    await attach_snippets(bills, "needle", 0)
    snippet = bills[0]["snippet"]
    assert bills[0]["snippet_status"] == "localized"
    assert "quoted" in snippet["match_contexts"]
    assert '"' in snippet["text"]  # the quoted span is delimited in the text
    assert snippet["section_id"]


# --------------------------------------------------------------------------- #
# Through search_bills (the response wire shape)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_states_survive_the_search_bills_wire(store, monkeypatch):
    monkeypatch.setattr(client_mod, "API_KEY", "test-key-govinfo-snippets")
    _enroll(store, BILL_XML, "BILLS-119s1071enr", "enr")

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"count": 2, "offsetMark": None, "results": [
                {"packageId": "BILLS-119s1071enr", "title": "Cutter bill",
                 "dateIssued": "2025-01-01"},
                {"packageId": "BILLS-119hr9999ih", "title": "Other bill",
                 "dateIssued": "2025-01-01"},
            ]}

    async def fake_post(body):
        return FakeResponse()

    with patch.object(api_mod, "govinfo_search_post", side_effect=fake_post):
        raw = await api_mod.search_bills(FakeContext(), keywords="icebreaker",
                                         congress=119)
    payload = json.loads(raw)
    by_pkg = {b["package_id"]: b for b in payload["results"]}
    cached = by_pkg["BILLS-119s1071enr"]
    uncached = by_pkg["BILLS-119hr9999ih"]
    assert cached["snippet_status"] == "localized"
    assert cached["snippet"]["match_contexts"]
    assert "snippet_status" not in uncached and "snippet" not in uncached
