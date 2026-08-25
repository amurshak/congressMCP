"""Step 4 of the govinfo-search work order (spec section 6.4): the failure
flow -- every row, the canary branching both ways, fallback labeling, and
the F31 keyless instrument. The fallback re-pins #66's honest-window
assertions (window named in the message, honest miss text) under their
new fallback labels.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.features.buckets.bills import api as mod  # noqa: E402
from congress_api.features.buckets.bills import govinfo_search as gs  # noqa: E402


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


@pytest.fixture(autouse=True)
def _keyed(monkeypatch):
    """Full-suite isolation: whichever test file imports congress_api first
    fixes api_config.API_KEY for the whole process, and a keyless import
    order would turn every corpus-path test into api_key_missing. Pin a key
    at the client's resolution point; the keyless F31 test overrides it."""
    from congress_api.features.bill_text import client as _client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(_client_mod, "API_KEY", "test-key-govinfo-search")


class FakeSearchResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {
            "count": 0, "results": [], "offsetMark": None}

    def json(self):
        return self._payload


_WINDOW_BILLS = [
    {"title": "Climate Resilience Act", "policyArea": {"name": "Environment"},
     "type": "HR", "number": "77", "congress": 119,
     "updateDate": "2026-08-01",
     "latestAction": {"text": "Referred to committee"}},
    {"title": "Post Office Naming Act", "policyArea": {"name": "Government"},
     "type": "S", "number": "12", "congress": 119,
     "updateDate": "2026-07-15"},
]


def _window_fetch(bills=None):
    return AsyncMock(return_value={"bills": _WINDOW_BILLS
                                   if bills is None else bills})


async def _run(post_effect, fetch=None, **kwargs):
    fetch = fetch or _window_fetch()
    post = post_effect if isinstance(post_effect, AsyncMock) \
        else AsyncMock(side_effect=post_effect)
    with patch.object(mod, "govinfo_search_post", post), \
            patch.object(mod, "fetch_bill_data", fetch):
        out = await mod.search_bills(FakeContext(), **kwargs)
    return json.loads(out), post, fetch


# ---------------------------------------------------------------------------
# Row: 200
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_row_200_normal_corpus_response_no_fallback():
    payload, post, fetch = await _run(
        [FakeSearchResponse(200, {"count": 1, "offsetMark": "x", "results": [
            {"packageId": "BILLS-119hr4631ih",
             "title": "St. Louis RECA Readjustment Act",
             "dateIssued": "2025-06-05"}]})],
        keywords="RECA", congress=119)
    assert payload["search_source"] == "govinfo_fulltext"
    assert payload["results"][0]["bill"] == "HR 4631"
    fetch.assert_not_awaited()


# ---------------------------------------------------------------------------
# Row: 500 -- canary branching both ways
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_row_500_canary_succeeds_query_error_no_fallback():
    payload, post, fetch = await _run(
        [FakeSearchResponse(500), FakeSearchResponse(200)],
        keywords="weird )( query")
    assert payload["error"]["code"] == "govinfo_query_error"
    assert "canary" in json.dumps(payload["error"]).lower()
    assert post.await_count == 2
    # The canary is the server's constant query: zero caller input.
    canary_sent = post.call_args_list[1].args[0]
    assert canary_sent == gs.canary_body()
    assert "weird" not in json.dumps(canary_sent)
    fetch.assert_not_awaited()          # no fallback on this branch


@pytest.mark.asyncio
async def test_row_500_canary_query_error_names_page_token_when_supplied():
    token = gs.encode_page_token("stale-cursor", 30)
    payload, _, _ = await _run(
        [FakeSearchResponse(500), FakeSearchResponse(200)],
        keywords="fine words", page_token=token)
    err = payload["error"]
    assert err["code"] == "govinfo_query_error"
    assert "page_token" in json.dumps(err)


@pytest.mark.asyncio
async def test_row_500_canary_silent_about_token_when_none_supplied():
    payload, _, _ = await _run(
        [FakeSearchResponse(500), FakeSearchResponse(200)],
        keywords="fine words")
    assert "page_token" not in json.dumps(payload["error"])


@pytest.mark.asyncio
async def test_row_500_canary_fails_fallback_as_search_error():
    payload, post, fetch = await _run(
        [FakeSearchResponse(500), FakeSearchResponse(503)],
        keywords="climate")
    assert payload["search_source"] == "recency_window_fallback"
    assert payload["fallback_trigger"] == "govinfo_search_error"
    assert post.await_count == 2
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_row_500_canary_transport_error_is_outage_too():
    payload, _, _ = await _run(
        [FakeSearchResponse(500), httpx.ConnectError("boom")],
        keywords="climate")
    assert payload["fallback_trigger"] == "govinfo_search_error"


# ---------------------------------------------------------------------------
# Rows: transport / 429 -- no canary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_row_unreachable_fallback_no_canary():
    payload, post, fetch = await _run(
        [httpx.ConnectTimeout("no route")], keywords="climate")
    assert payload["search_source"] == "recency_window_fallback"
    assert payload["fallback_trigger"] == "govinfo_unreachable"
    assert post.await_count == 1          # no canary on transport failure
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_row_429_fallback_no_canary():
    payload, post, _ = await _run(
        [FakeSearchResponse(429)], keywords="climate")
    assert payload["fallback_trigger"] == "govinfo_rate_limited"
    assert post.await_count == 1          # a canary would spend quota


# ---------------------------------------------------------------------------
# Row: keyless (F31 instrument) -- and its key-rejected sibling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_row_keyless_api_key_missing_no_send_no_fallback(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)   # scrubbed env
    monkeypatch.setattr(client_mod, "API_KEY", None)
    post = AsyncMock()
    fetch = AsyncMock()
    with patch.object(mod, "govinfo_search_post", post), \
            patch.object(mod, "fetch_bill_data", fetch):
        out = await mod.search_bills(FakeContext(), keywords="climate")
    err = json.loads(out)["error"]
    assert err["code"] == "api_key_missing"       # F31: never key_rejected
    assert "CONGRESS_API_KEY" in err["remediation"]
    assert "GOVINFO_API_KEY" in err["remediation"]
    post.assert_not_awaited()
    fetch.assert_not_awaited()                    # no fallback


@pytest.mark.asyncio
async def test_keyed_401_is_key_rejected_no_fallback():
    payload, _, fetch = await _run(
        [FakeSearchResponse(401)], keywords="climate")
    assert payload["error"]["code"] == "govinfo_key_rejected"
    fetch.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fallback labeling and #66 window honesty (re-pinned from the old
# primary-path tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fallback_carries_window_metadata_and_named_window():
    payload, _, fetch = await _run(
        [FakeSearchResponse(500), FakeSearchResponse(500)],
        keywords="climate", congress=119, limit=5)
    window = payload["window"]
    assert window["bills_scanned"] == 2
    assert window["oldest_update_date"] == "2026-07-15"
    assert window["window_truncated"] is False
    assert "most recently updated bills" in payload["message"]
    assert payload["results_count"] == len(payload["results"]) == 1
    assert payload["results"][0]["bill"] == "HR 77"
    # The window fetch is the #66 shape: max page, recency sort.
    assert fetch.call_args.kwargs["limit"] == 250
    assert fetch.call_args.kwargs["sort"] == "updateDate+desc"


@pytest.mark.asyncio
async def test_fallback_miss_message_is_honest_and_names_alternatives():
    payload, _, _ = await _run(
        [httpx.ConnectError("down")],
        fetch=_window_fetch([{"title": "Unrelated", "type": "HR",
                              "number": "1", "congress": 119,
                              "updateDate": "2026-08-01"}]),
        keywords="zebras", congress=119)
    assert payload["results_count"] == 0
    message = payload["message"]
    assert "No match for 'zebras'" in message
    assert "most recently updated bills" in message
    assert "not a full-text" in message
    assert "search_bill_text" in message


@pytest.mark.asyncio
async def test_fallback_window_truncated_flag_at_max_page():
    bills = [{"title": f"Bill {n}", "type": "HR", "number": str(n),
              "congress": 119, "updateDate": "2026-08-01"}
             for n in range(250)]
    payload, _, _ = await _run(
        [FakeSearchResponse(429)], fetch=_window_fetch(bills),
        keywords="zzz")
    assert payload["window"]["window_truncated"] is True


@pytest.mark.asyncio
async def test_errored_fallback_is_an_error_not_empty_results():
    # Three-zeros rule: corpus errored AND the fallback errored -> the
    # response is an ERROR envelope wearing the trigger code, never a
    # success shape with zero results.
    fetch = AsyncMock(return_value={"error": "congress.gov 500"})
    payload, _, _ = await _run(
        [httpx.ConnectError("down")], fetch=fetch, keywords="climate")
    err = payload["error"]
    assert err["code"] == "govinfo_unreachable"
    assert "fallback also failed" in err["message"]
    assert "results" not in payload
