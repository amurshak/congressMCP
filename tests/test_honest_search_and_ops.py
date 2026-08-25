"""Issues #54 (honest keyword search) and #56 (dead/link-only operations)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch

from mcp.server.mcpserver.exceptions import ToolError


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


# ---------------------------------------------------------------------------
# #56: removed operations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_bill_content_is_gone():
    from congress_api.features.bills_tool import route_bills_operation
    with pytest.raises(ToolError, match="Unknown bills operation"):
        await route_bills_operation(FakeContext(), "get_bill_content",
                                    congress=119, bill_type="hr", bill_number=1)
    import congress_api.features.buckets.bills as bills_pkg
    assert not hasattr(bills_pkg, "get_bill_content")


@pytest.mark.asyncio
async def test_research_stub_operations_are_gone():
    from congress_api.features.buckets.research_and_professional import (
        route_research_and_professional_operation)
    for op in ("get_congress_statistics", "get_legislative_analysis"):
        with pytest.raises(ToolError, match="Unknown operation"):
            await route_research_and_professional_operation(FakeContext(), op)


def test_no_coming_soon_left_in_schema_docs():
    import glob
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "congress_api")
    hits = [f for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True)
            if "coming soon" in open(f).read().lower()]
    assert hits == []


# ---------------------------------------------------------------------------
# #56: get_house_vote_member_votes returns real per-member votes
# ---------------------------------------------------------------------------

_CLERK_XML = """<?xml version="1.0"?>
<rollcall-vote>
  <vote-metadata>
    <congress>119</congress><session>1st</session><rollcall-num>100</rollcall-num>
    <legis-num>H CON RES 14</legis-num>
    <vote-question>On Motion to Concur</vote-question>
    <vote-result>Passed</vote-result>
    <action-date>10-Apr-2025</action-date>
  </vote-metadata>
  <vote-data>
    <recorded-vote><legislator party="D" state="NY">Schumer</legislator><vote>Nay</vote></recorded-vote>
    <recorded-vote><legislator party="R" state="TX">Cornyn</legislator><vote>Yea</vote></recorded-vote>
    <recorded-vote><legislator party="R" state="LA">Johnson</legislator><vote>Yea</vote></recorded-vote>
  </vote-data>
</rollcall-vote>"""


def test_parse_member_votes():
    from congress_api.features.house_votes import parse_member_votes
    header, members, tallies = parse_member_votes(_CLERK_XML)
    assert len(members) == 3
    assert members[0] == {"name": "Schumer", "party": "D", "state": "NY", "vote": "Nay"}
    assert tallies == {"Yea": 2, "Nay": 1}
    assert any("H CON RES 14" in h for h in header)


@pytest.mark.asyncio
async def test_member_votes_returns_structured_items():
    from congress_api.features import house_votes as mod

    async def fake_fetch(ctx, congress, session, vote_number):
        return _CLERK_XML, "https://clerk.house.gov/evs/2025/roll100.xml", None

    with patch.object(mod, "_fetch_member_votes_xml", fake_fetch):
        out = await mod.get_house_vote_member_votes(FakeContext(), congress=119,
                                                    session=1, vote_number=100)
    assert "Tallies" in out and "**Yea**: 2" in out
    assert out.item_kind == "member_vote"
    assert len(out.structured_items) == 3
    # through the bucket converter, members land in the generic items field
    from congress_api.features.buckets.voting_and_nominations import (
        _convert_to_structured_response)
    resp = _convert_to_structured_response(out, "get_house_vote_member_votes")
    assert resp.results_count == 3
    assert resp.items[1]["vote"] == "Yea" and resp.item_kind == "member_vote"


@pytest.mark.asyncio
async def test_member_votes_rejects_entity_xml():
    from congress_api.features import house_votes as mod
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><rollcall-vote/>'

    class FakeResp:
        status_code = 200
        text = evil

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url):
            return FakeResp()

    vote = {"houseRollCallVote":
            {"sourceDataURL": "https://clerk.house.gov/evs/2025/roll100.xml"}}
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value=vote)), \
            patch("httpx.AsyncClient", FakeClient):
        out = await mod.get_house_vote_member_votes(FakeContext(), congress=119,
                                                    session=1, vote_number=100)
    assert "entity" in out.lower()


# ---------------------------------------------------------------------------
# #54: honest keyword search
# ---------------------------------------------------------------------------

# search_bills left the recency window for GovInfo corpus search
# (govinfo-search-spec section 6); #66's honest-window behavior becomes the
# GovInfo-down FALLBACK, where its window-naming assertions are re-pinned
# (tests/test_govinfo_search_failure_flow.py). The corpus-path equivalents
# of the two original assertions live here: a miss is a readable zero, and
# exactly one bounded upstream fetch happens per call.

@pytest.fixture(autouse=True)
def _keyed(monkeypatch):
    """Full-suite isolation: whichever test file imports congress_api first
    fixes api_config.API_KEY for the whole process, and a keyless import
    order would turn every corpus-path test into api_key_missing. Pin a key
    at the client's resolution point; the keyless F31 test overrides it."""
    from congress_api.features.bill_text import client as _client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(_client_mod, "API_KEY", "test-key-govinfo-search")


class _FakeSearchResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_search_bills_miss_is_a_readable_corpus_zero():
    import json
    from congress_api.features.buckets.bills import api as mod
    empty = _FakeSearchResponse({"count": 0, "results": [],
                                 "offsetMark": None})
    with patch.object(mod, "govinfo_search_post",
                      AsyncMock(return_value=empty)):
        out = json.loads(await mod.search_bills(
            FakeContext(), keywords="climate", congress=119, limit=5))
    assert out["search_source"] == "govinfo_fulltext"
    assert out["results_count"] == 0 and out["results"] == []
    diag = out["query_diagnostics"]
    assert "BILLS" in diag["corpus"] and "climate" in diag["upstream_query"]


@pytest.mark.asyncio
async def test_search_bills_makes_one_bounded_corpus_fetch():
    from congress_api.features.buckets.bills import api as mod
    mock = AsyncMock(return_value=_FakeSearchResponse(
        {"count": 0, "results": [], "offsetMark": None}))
    with patch.object(mod, "govinfo_search_post", mock):
        await mod.search_bills(FakeContext(), keywords="x", limit=5)
    assert mock.await_count == 1                       # one fetch per call
    body = mock.call_args.args[0]
    assert body["pageSize"] == 15                      # min(3*limit, 300)
    assert body["sorts"] == [{"field": "score", "sortOrder": "DESC"}]


@pytest.mark.asyncio
async def test_search_amendments_filters_client_side_and_drops_query_param():
    from congress_api.features.buckets.amendments import api as mod
    amendments = [
        {"congress": 119, "type": "SAMDT", "number": 1, "purpose": "To increase defense spending",
         "updateDate": "2026-01-02"},
        {"congress": 119, "type": "SAMDT", "number": 2, "purpose": "To rename a post office",
         "updateDate": "2026-01-01"},
    ]
    captured = {}

    async def fake_request(endpoint, ctx, params, **kw):
        captured.update(params)
        return {"amendments": amendments}

    with patch.object(mod.DefensiveAPIWrapper, "safe_api_request", side_effect=fake_request):
        out = await mod.search_amendments(FakeContext(), keywords="defense", congress=119, limit=5)
    assert "query" not in captured          # bogus API param no longer sent
    assert captured["limit"] == 250          # max window fetched
    assert "defense spending" in out and "post office" not in out.lower()
    # count phrase reflects the filtered set, and title names the window
    assert "purpose filter over the" in out


@pytest.mark.asyncio
async def test_search_amendments_miss_is_honest():
    from congress_api.features.buckets.amendments import api as mod
    amendments = [{"congress": 119, "type": "SAMDT", "number": 1,
                   "purpose": "Unrelated", "updateDate": "2026-01-01"}]
    with patch.object(mod.DefensiveAPIWrapper, "safe_api_request",
                      AsyncMock(return_value={"amendments": amendments})):
        out = await mod.search_amendments(FakeContext(), keywords="zebras", limit=5)
    assert "No match for 'zebras'" in out and "not a full-text" in out


@pytest.mark.asyncio
async def test_crs_miss_message_not_doubled():
    from congress_api.features import crs_reports as mod
    with patch.object(mod, "safe_crs_reports_request",
                      AsyncMock(return_value={"CRSReports": [
                          {"title": "Something else", "id": "1"}]})):
        out = await mod.search_crs_reports(FakeContext(), keywords="tariffs", limit=5)
    assert "No No" not in out
    assert "most recently updated reports" in out
    assert "report_number" in out


@pytest.mark.asyncio
async def test_search_summaries_keyword_window_is_not_truncated():
    """The 250-row fetch must not be cut back down by the response cleaner."""
    from congress_api.features import summaries as mod
    fetch = AsyncMock(return_value={"summaries": [], "pagination": {"count": 0}})
    cleaned = []

    def fake_clean(data, limit):
        cleaned.append(limit)
        return []

    with patch.object(mod, "safe_congressional_request", fetch), \
            patch.object(mod, "clean_summaries_response", fake_clean):
        await mod.search_summaries(FakeContext(), keywords="veterans", congress=119)
    assert fetch.call_args.args[2]["limit"] == 250
    assert cleaned == [250]


@pytest.mark.asyncio
async def test_member_votes_refuses_non_clerk_host():
    from congress_api.features import house_votes as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value={"houseRollCallVote":
                                              {"sourceDataURL": "https://evil.example.com/x.xml"}})):
        out = await mod.get_house_vote_member_votes(FakeContext(), congress=119,
                                                    session=1, vote_number=100)
    assert "unexpected host" in out
