"""Q10 / section-7 Addendum 2: time-bounding restored on
publishdate:range. Each defense in isolation:

- validation: ISO date or datetime accepted, datetime TRUNCATED to its
  date; malformed shapes rejected as invalid_parameter, never sent
- from <= to enforced; equal bounds legal (the measured inclusive
  single-day form)
- assembly: publishdate:range(from,to) appended, both one-sided forms
  native (range(from,) / range(,to)); no term when unbounded
- the fallback filters updateDate client-side, inclusive, and NAMES the
  semantic difference (updateDate vs publication date) in message and
  structured metadata
"""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.core.exceptions import CongressionalAPIError  # noqa: E402
from congress_api.features.buckets.bills import api as mod  # noqa: E402
from congress_api.features.buckets.bills import govinfo_search as gs  # noqa: E402


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
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {
            "count": 0, "results": [], "offsetMark": None}

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("2025-01-01", "2025-01-01"),
    ("2026-01-01T12:30:00Z", "2026-01-01"),      # truncated
    ("2026-01-01T12:30", "2026-01-01"),
    ("2026-01-01T12:30:00+00:00", "2026-01-01"),
    (None, None),
])
def test_date_bound_accepts_iso_and_truncates(value, expected):
    assert gs.validate_date_bound("fromDateTime", value) == expected


@pytest.mark.parametrize("bad", [
    "2025-1-1", "garbage", "2025-13-01", "01/01/2025",
    "2025-01-01Tnoon", "2025-01-01T25:99", "20250101", "",
])
def test_date_bound_rejects_malformed(bad):
    with pytest.raises(CongressionalAPIError):
        gs.validate_date_bound("fromDateTime", bad)


def test_date_order_enforced_from_not_after_to():
    with pytest.raises(CongressionalAPIError):
        gs.validate_date_order("2026-01-02", "2026-01-01")
    # Equal bounds = the measured single-day form; one-sided skips check.
    gs.validate_date_order("2026-01-01", "2026-01-01")
    gs.validate_date_order("2026-01-01", None)
    gs.validate_date_order(None, "2026-01-01")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def test_range_appended_after_scoping_terms():
    assert gs.build_query("RECA", 119, "hr",
                          from_date="2025-01-01",
                          to_date="2025-12-31") == (
        "RECA collection:bills congress:119 billtype:hr "
        "publishdate:range(2025-01-01,2025-12-31)")


def test_one_sided_forms_are_native():
    assert gs.build_query("RECA", None, None,
                          from_date="2026-01-01").endswith(
        "publishdate:range(2026-01-01,)")
    assert gs.build_query("RECA", None, None,
                          to_date="2025-12-31").endswith(
        "publishdate:range(,2025-12-31)")


def test_unbounded_query_carries_no_publishdate_term():
    assert "publishdate" not in gs.build_query("RECA", 119, None)


@pytest.mark.asyncio
async def test_search_bills_sends_range_and_truncates_datetime():
    post = AsyncMock(return_value=FakeSearchResponse())
    with patch.object(mod, "govinfo_search_post", post):
        await mod.search_bills(FakeContext(), keywords="RECA", congress=119,
                               fromDateTime="2025-07-23T08:00:00Z",
                               toDateTime="2025-07-23")
    # The MAIN query is the first call -- a zero total now legitimately
    # fires Q12 leave-one-out probes after it (which drop constraints by
    # design), so the last call is no longer the query under test.
    body = post.call_args_list[0].args[0]
    assert body["query"].endswith(
        "publishdate:range(2025-07-23,2025-07-23)")


@pytest.mark.asyncio
async def test_invalid_bound_is_rejected_before_send():
    post = AsyncMock()
    with patch.object(mod, "govinfo_search_post", post):
        out = await mod.search_bills(FakeContext(), keywords="RECA",
                                     fromDateTime="not-a-date")
    assert json.loads(out)["error"]["code"] == "invalid_parameter"
    post.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fallback: updateDate filter + named semantics
# ---------------------------------------------------------------------------

_WINDOW = [
    {"title": "Climate Act of 2025", "type": "HR", "number": "1",
     "congress": 119, "updateDate": "2025-06-15"},
    {"title": "Climate Act of 2026", "type": "HR", "number": "2",
     "congress": 119, "updateDate": "2026-02-03"},
    {"title": "Climate boundary bill", "type": "HR", "number": "3",
     "congress": 119, "updateDate": "2026-01-01T09:00:00Z"},
    {"title": "Climate dateless bill", "type": "HR", "number": "4",
     "congress": 119},
]


async def _fallback(**kwargs):
    post = AsyncMock(side_effect=[FakeSearchResponse(429)])
    fetch = AsyncMock(return_value={"bills": _WINDOW})
    with patch.object(mod, "govinfo_search_post", post), \
            patch.object(mod, "fetch_bill_data", fetch):
        return json.loads(await mod.search_bills(
            FakeContext(), keywords="climate", **kwargs))


@pytest.mark.asyncio
async def test_fallback_filters_update_date_inclusive():
    payload = await _fallback(fromDateTime="2026-01-01",
                              toDateTime="2026-12-31")
    numbers = sorted(b["bill_number"] for b in payload["results"])
    # 2026 rows only; the boundary row (exactly 2026-01-01, with a time
    # part) is INSIDE; the dateless row is excluded under bounds.
    assert numbers == [2, 3]


@pytest.mark.asyncio
async def test_fallback_names_the_update_date_semantics():
    payload = await _fallback(fromDateTime="2026-01-01")
    assert "updateDate" in payload["message"]
    assert "NOT the version publication date" in payload["message"]
    assert payload["date_bounds"] == {"from": "2026-01-01", "to": None,
                                      "applied_to": "updateDate"}


@pytest.mark.asyncio
async def test_fallback_zero_under_bounds_still_names_semantics():
    payload = await _fallback(fromDateTime="2030-01-01")
    assert payload["results_count"] == 0
    assert "updateDate" in payload["message"]


@pytest.mark.asyncio
async def test_fallback_unbounded_carries_no_bounds_metadata():
    payload = await _fallback()
    assert "date_bounds" not in payload
    assert "updateDate (last update)" not in payload["message"]
