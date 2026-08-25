"""Step 3 of the govinfo-search work order (spec section 6.3): pagination.

- token round-trip; malformed tokens decode to None
- exhaustion is COMPUTED (records_consumed >= count), never inferred from
  cursor nullness -- incl. the measured non-null-cursor-on-last-page shape
- short pages (version-heavy page dedups below limit) are legal
- a page that dedups to MORE than limit bills loses nothing: the walk
  resumes the same replayable cursor past the consumed records
- the one tolerated duplication class: a straddling bill reappears with
  the same identity
- the #66 removal pattern: offset (and the other window-path params) are
  gone from search_bills' signature and rejected by the router with a
  clear ToolError; page_token replaces offset in the tool schema
"""
import inspect
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

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
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _record(package_id):
    return {"packageId": package_id, "title": f"Title {package_id}",
            "dateIssued": "2026-01-01"}


# ---------------------------------------------------------------------------
# Token codec
# ---------------------------------------------------------------------------

def test_token_round_trip_without_skip():
    token = gs.encode_page_token("AoJcursor", 90)
    assert gs.decode_page_token(token) == {
        "offsetMark": "AoJcursor", "records_consumed": 90, "skip": 0}


def test_token_round_trip_with_skip():
    token = gs.encode_page_token("*", 12, skip=7)
    assert gs.decode_page_token(token) == {
        "offsetMark": "*", "records_consumed": 12, "skip": 7}


@pytest.mark.parametrize("bad", [
    None, "", "garbage!!", "bm90LWpzb24",              # not JSON
    gs.encode_page_token("*", 1) + "x",                # corrupted
    "eyJvZmZzZXRNYXJrIjoiKiJ9",                        # missing field
    "eyJvZmZzZXRNYXJrIjoiKiIsInJlY29yZHNfY29uc3VtZWQiOi01fQ",  # negative
    "eyJvZmZzZXRNYXJrIjoiIiwicmVjb3Jkc19jb25zdW1lZCI6MX0",     # empty mark
])
def test_malformed_tokens_decode_to_none(bad):
    assert gs.decode_page_token(bad) is None


# ---------------------------------------------------------------------------
# Computed exhaustion
# ---------------------------------------------------------------------------

def test_exhaustion_is_computed_not_cursor_nullness():
    # The measured last-page shape: upstream still returns a cursor.
    token, total = gs.compute_next_token(
        count=30, prior_consumed=20, prior_skip=0, consumed_now=10,
        page_exhausted=True, request_cursor="pg2",
        response_cursor="non-null-cursor-on-last-page")
    assert token is None and total == 30


def test_unexhausted_walk_moves_to_response_cursor():
    token, total = gs.compute_next_token(
        count=90, prior_consumed=0, prior_skip=0, consumed_now=30,
        page_exhausted=True, request_cursor="*", response_cursor="pg2")
    assert total == 30
    assert gs.decode_page_token(token) == {
        "offsetMark": "pg2", "records_consumed": 30, "skip": 0}


def test_partially_consumed_page_replays_same_cursor_with_skip():
    token, total = gs.compute_next_token(
        count=90, prior_consumed=30, prior_skip=5, consumed_now=10,
        page_exhausted=False, request_cursor="pg2", response_cursor="pg3")
    assert total == 40
    assert gs.decode_page_token(token) == {
        "offsetMark": "pg2", "records_consumed": 40, "skip": 15}


def test_missing_cursor_mid_walk_ends_early_not_loops():
    token, total = gs.compute_next_token(
        count=90, prior_consumed=0, prior_skip=0, consumed_now=30,
        page_exhausted=True, request_cursor="*", response_cursor=None)
    assert token is None and total == 30


# ---------------------------------------------------------------------------
# Page consumption
# ---------------------------------------------------------------------------

def test_short_page_version_heavy_dedups_below_limit():
    # 12 records, 3 bills, limit 10: legal short page, fully consumed.
    records = []
    for number in (1, 2, 3):
        for version in ("ih", "rh", "eh", "enr"):
            records.append(_record(f"BILLS-119hr{number}{version}"))
    bills, consumed, exhausted = gs.paginate_records(records, 0, 10)
    assert len(bills) == 3 and consumed == 12 and exhausted is True


def test_overshoot_page_consumes_only_selected_bills_records():
    # 30 single-version bills, limit 10: 10 bills out, boundary at 10,
    # page NOT exhausted -- the tail is resumed, never dropped.
    records = [_record(f"BILLS-119hr{n}ih") for n in range(1, 31)]
    bills, consumed, exhausted = gs.paginate_records(records, 0, 10)
    assert [b["bill_number"] for b in bills] == list(range(1, 11))
    assert consumed == 10 and exhausted is False


def test_full_walk_over_one_page_is_lossless_and_disjoint():
    records = [_record(f"BILLS-119hr{n}ih") for n in range(1, 31)]
    seen, skip, pages = [], 0, 0
    while True:
        bills, consumed, exhausted = gs.paginate_records(records, skip, 10)
        seen.extend(b["bill_number"] for b in bills)
        pages += 1
        if exhausted:
            break
        skip += consumed
    assert pages == 3
    assert seen == list(range(1, 31))  # no loss, no duplication, in order


def test_straddling_bill_reappears_with_same_identity():
    # HR 1's enr sits after the boundary forced by limit=2: the first call
    # returns HR 1 (ih only) + HR 2; the resumed call re-encounters HR 1's
    # enr -- same bill identity, the one tolerated duplication class.
    records = [
        _record("BILLS-119hr1ih"),
        _record("BILLS-119hr2ih"),
        _record("BILLS-119hr3ih"),
        _record("BILLS-119hr1enr"),
    ]
    first, consumed, exhausted = gs.paginate_records(records, 0, 2)
    assert [b["bill"] for b in first] == ["HR 1", "HR 2"]
    assert first[0]["matched_versions"] == ["ih"]
    assert exhausted is False
    second, _, exhausted = gs.paginate_records(records, consumed, 2)
    assert exhausted is True
    reappeared = [b for b in second if b["bill"] == "HR 1"]
    assert len(reappeared) == 1
    assert reappeared[0]["matched_versions"] == ["enr"]
    assert (reappeared[0]["congress"], reappeared[0]["bill_type"],
            reappeared[0]["bill_number"]) == (119, "hr", 1)


# ---------------------------------------------------------------------------
# search_bills wiring: token flows back into the upstream cursor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_bills_walk_passes_cursor_back_upstream():
    from congress_api.features.buckets.bills import api as mod
    page1 = {
        "count": 6,
        "offsetMark": "pg2",
        "results": [_record(f"BILLS-119hr{n}ih") for n in range(1, 4)],
    }
    page2 = {
        "count": 6,
        "offsetMark": "pg3",
        "results": [_record(f"BILLS-119hr{n}ih") for n in range(4, 7)],
    }
    seen_bodies = []

    async def fake_post(body):
        seen_bodies.append(body)
        return FakeSearchResponse(page1 if body["offsetMark"] == "*"
                                  else page2)

    with patch.object(mod, "govinfo_search_post", side_effect=fake_post):
        out1 = json.loads(await mod.search_bills(
            FakeContext(), keywords="RECA", congress=119, limit=10))
        assert out1["results_count"] == 3
        assert out1["next_page_token"] is not None
        out2 = json.loads(await mod.search_bills(
            FakeContext(), keywords="RECA", congress=119, limit=10,
            page_token=out1["next_page_token"]))

    assert seen_bodies[0]["offsetMark"] == "*"
    assert seen_bodies[1]["offsetMark"] == "pg2"   # cursor passed verbatim
    assert out2["next_page_token"] is None         # 6 of 6 consumed
    walked = [b["bill_number"] for b in out1["results"] + out2["results"]]
    assert walked == [1, 2, 3, 4, 5, 6]


@pytest.mark.asyncio
async def test_search_bills_undecodable_token_is_query_error_no_call():
    from congress_api.features.buckets.bills import api as mod
    post = AsyncMock()
    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(FakeContext(), keywords="RECA",
                                     page_token="not-a-token!!!")
    payload = json.loads(out)
    assert payload["error"]["code"] == "govinfo_query_error"
    assert "page_token" in json.dumps(payload["error"])
    post.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_bills_blank_keywords_never_sends(monkeypatch):
    from congress_api.features.buckets.bills import api as mod
    post = AsyncMock()
    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(FakeContext(), keywords="   ")
    assert json.loads(out)["error"]["code"] == "invalid_parameters"
    post.assert_not_awaited()


# ---------------------------------------------------------------------------
# The #66 removal pattern
# ---------------------------------------------------------------------------

def test_search_bills_signature_dropped_window_params():
    from congress_api.features.buckets.bills import search_bills
    params = set(inspect.signature(search_bills).parameters)
    # fromDateTime/toDateTime were removed with the window and RESTORED by
    # Q10 (publishdate:range mapping); offset/sort/format stay gone.
    assert params == {"ctx", "keywords", "congress", "bill_type", "limit",
                      "page_token", "fromDateTime", "toDateTime"}


@pytest.mark.asyncio
@pytest.mark.parametrize("param,value", [
    ("offset", 10), ("sort", "updateDate+desc"), ("format", "json"),
])
async def test_router_rejects_removed_params_with_clear_error(param, value):
    from congress_api.features.bills_tool import route_bills_operation
    with pytest.raises(ToolError, match=param):
        await route_bills_operation(FakeContext(), "search_bills",
                                    keywords="x", **{param: value})


def test_bills_tool_schema_carries_page_token():
    from congress_api.features.bills_tool import bills
    fn = inspect.unwrap(bills)
    assert "page_token" in inspect.signature(fn).parameters
