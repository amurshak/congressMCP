"""Regression tests for the 2026-08-21 functional-review P1 batch.

Covers issues #49 (summaries date window), #50 (search_members endpoint /
pagination / congress order), #51 (latest term in member summaries) and #52
(error branches must return str, not APIErrorResponse).
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


def _member(bioguide, last, chamber_terms, state="New York"):
    """Build an API-shaped member record; terms given oldest-first."""
    return {
        "bioguideId": bioguide,
        "name": f"{last}, Test",
        "directOrderName": f"Test {last}",
        "invertedOrderName": f"{last}, Test",
        "state": state,
        "partyName": "Democratic",
        "terms": {"item": [
            {"chamber": c, "startYear": s, "endYear": e}
            for c, s, e in chamber_terms
        ]},
    }


# ---------------------------------------------------------------------------
# congress_dates helper
# ---------------------------------------------------------------------------

def test_current_congress_math():
    from congress_api.core.congress_dates import (
        congress_start_date, current_congress)
    assert current_congress(date(2026, 8, 21)) == 119
    assert current_congress(date(2025, 1, 3)) == 119
    assert current_congress(date(2025, 1, 2)) == 118   # not yet convened
    assert current_congress(date(2024, 12, 31)) == 118
    assert congress_start_date(119) == date(2025, 1, 3)
    assert congress_start_date(118) == date(2023, 1, 3)


# ---------------------------------------------------------------------------
# #49 search_summaries always sends a date window
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_summaries_defaults_date_window_to_congress():
    from congress_api.features import summaries as mod
    mock = AsyncMock(return_value={"summaries": [], "pagination": {"count": 0}})
    with patch.object(mod, "safe_congressional_request", mock):
        out = await mod.search_summaries(FakeContext(), congress=119)
    endpoint, _ctx, params = mock.call_args.args[:3]
    assert endpoint == "/summaries/119"
    assert params["fromDateTime"] == "2025-01-03T00:00:00Z"
    assert params["toDateTime"].endswith("T00:00:00Z")
    # Empty result names the upstream count so it is not mistaken for a
    # keyword-filter miss.
    assert "Congress.gov reports 0" in out


@pytest.mark.asyncio
async def test_search_summaries_keeps_explicit_dates():
    from congress_api.features import summaries as mod
    mock = AsyncMock(return_value={"summaries": [], "pagination": {"count": 0}})
    with patch.object(mod, "safe_congressional_request", mock):
        await mod.search_summaries(
            FakeContext(), congress=119,
            fromDateTime="2025-06-01T00:00:00Z",
            toDateTime="2025-06-30T00:00:00Z")
    params = mock.call_args.args[2]
    assert params["fromDateTime"] == "2025-06-01T00:00:00Z"
    assert params["toDateTime"] == "2025-06-30T00:00:00Z"


@pytest.mark.asyncio
async def test_search_summaries_browse_without_congress_uses_recent_window():
    from congress_api.features import summaries as mod
    mock = AsyncMock(return_value={"summaries": [], "pagination": {"count": 0}})
    with patch.object(mod, "safe_congressional_request", mock):
        await mod.search_summaries(FakeContext())
    endpoint, _ctx, params = mock.call_args.args[:3]
    assert endpoint == "/summaries"
    assert "fromDateTime" in params and "toDateTime" in params


# ---------------------------------------------------------------------------
# #50 search_members: endpoint choice, pagination, congress order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_members_state_chamber_uses_congress_endpoint_and_pages():
    """NY has 28 current members; the senators sit past the first page of 20.

    With a client-side chamber filter the search must paginate the
    congress-scoped state endpoint, not take one page of /member/NY.
    """
    from congress_api.features import members as mod
    reps = [_member(f"R{i:06d}", f"Rep{i}", [("House of Representatives", 2025, None)])
            for i in range(26)]
    senators = [
        _member("S000148", "Schumer",
                [("House of Representatives", 1981, 1999), ("Senate", 1999, None)]),
        _member("G000555", "Gillibrand",
                [("House of Representatives", 2007, 2009), ("Senate", 2009, None)]),
    ]
    mock = AsyncMock(return_value={"members": reps + senators})
    with patch.object(mod, "safe_congressional_request", mock):
        out = await mod.search_members(
            FakeContext(), state="NY", chamber="senate", congress=119)
    endpoint = mock.call_args.args[0]
    params = mock.call_args.args[2]
    assert endpoint == "/member/congress/119/NY"
    assert params["limit"] == 250 and params["offset"] == 0   # paginated
    assert "Schumer" in out and "Gillibrand" in out
    assert "Rep0" not in out


@pytest.mark.asyncio
async def test_search_members_state_without_filters_is_single_request():
    from congress_api.features import members as mod
    mock = AsyncMock(return_value={"members": [
        _member("A000001", "Alpha", [("House of Representatives", 2025, None)])]})
    with patch.object(mod, "safe_congressional_request", mock):
        await mod.search_members(FakeContext(), state="VT", limit=5)
    endpoint = mock.call_args.args[0]
    params = mock.call_args.args[2]
    assert endpoint == "/member/VT"
    assert params["limit"] == 5 and "offset" not in params


@pytest.mark.asyncio
async def test_search_members_name_search_starts_at_current_congress():
    from congress_api.features import members as mod
    seen = []

    async def fake_paginated(_ctx, endpoint, _params):
        seen.append(endpoint)
        return {"members": []}

    with patch.object(mod, "get_all_members_paginated", fake_paginated), \
            patch.object(mod, "current_congress", lambda: 121):
        await mod.search_members(FakeContext(), name="Nobody")
    assert seen == ["/member/congress/121", "/member/congress/120",
                    "/member/congress/119"]


# ---------------------------------------------------------------------------
# #51 format_member_summary shows the latest term
# ---------------------------------------------------------------------------

def test_format_member_summary_uses_latest_term():
    from congress_api.features.members import format_member_summary
    m = _member("S000148", "Schumer",
                [("House of Representatives", 1981, 1999), ("Senate", 1999, None)])
    out = format_member_summary(m)
    assert "Chamber: Senate" in out
    assert "Term: 1999 - Present" in out
    assert "1981" not in out


def test_latest_term_of_ignores_order():
    from congress_api.features.members import latest_term_of
    newest_first = [{"chamber": "Senate", "startYear": 1999, "endYear": None},
                    {"chamber": "House of Representatives", "startYear": 1981,
                     "endYear": 1999}]
    assert latest_term_of(newest_first)["chamber"] == "Senate"
    assert latest_term_of({"item": list(reversed(newest_first))})["chamber"] == "Senate"
    assert latest_term_of([]) is None
    assert latest_term_of(None) is None


# ---------------------------------------------------------------------------
# #52 error branches return str
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_treaty_text_not_found_returns_str():
    from congress_api.features import treaties as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value={})):
        out = await mod.get_treaty_text(FakeContext(), congress=118, treaty_number=2)
    assert isinstance(out, str)
    assert "data_not_found" in out and "server_error" not in out


@pytest.mark.asyncio
async def test_get_treaty_text_exception_returns_str():
    from congress_api.features import treaties as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(side_effect=RuntimeError("boom"))):
        out = await mod.get_treaty_text(FakeContext(), congress=118, treaty_number=2)
    assert isinstance(out, str)


@pytest.mark.asyncio
async def test_senate_communications_exceptions_return_str():
    from congress_api.features import senate_communications as mod
    boom = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(mod, "safe_congressional_request", boom):
        outs = [
            await mod.get_latest_senate_communications(),
            await mod.get_senate_communication_details(
                FakeContext(), congress=119, communication_type="ec",
                communication_number=1),
            await mod.search_senate_communications(FakeContext(), congress=119),
        ]
    assert all(isinstance(o, str) for o in outs)


def test_no_feature_returns_raw_common_errors():
    """Static guard: every CommonErrors.* return must be wrapped."""
    import re
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "congress_api", "features")
    offenders = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".py"):
                continue
            path = os.path.join(dirpath, f)
            with open(path) as fh:
                for n, line in enumerate(fh, 1):
                    if re.search(r"return\s+CommonErrors\.", line) and \
                            "format_error_response" not in line:
                        offenders.append(f"{path}:{n}")
    assert offenders == []


# ---------------------------------------------------------------------------
# #52 follow-on: /treaty/{congress}/{number} returns a one-element list
# ---------------------------------------------------------------------------

_TREATY = {
    "congressReceived": 118, "number": 2, "suffix": "", "topic": "Taxation",
    "transmittedDate": "2023-03-01", "updateDate": "2024-01-01T00:00:00Z",
    "titles": [{"title": "Tax Convention with Chile", "titleType": "Treaty - Formal Title"}],
    "resolutionText": "<p>Resolved (two-thirds of the Senators present concurring therein)</p>",
    "parts": {"count": 0}, "actions": {"count": 3}, "relatedDocs": [],
    "indexTerms": [{"name": "Chile"}], "countriesParties": [{"name": "Chile"}],
    "inForceDate": None, "oldNumber": None, "oldNumberDisplayName": None,
}


@pytest.mark.asyncio
async def test_get_treaty_text_handles_list_shaped_record():
    from congress_api.features import treaties as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value={"treaty": [_TREATY]})):
        out = await mod.get_treaty_text(FakeContext(), congress=118, treaty_number=2)
    assert isinstance(out, str)
    assert "Chile" in out and "Error" not in out


@pytest.mark.asyncio
async def test_get_treaty_detail_handles_list_shaped_record():
    from congress_api.features import treaties as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value={"treaty": [_TREATY]})):
        out = await mod.get_treaty_detail(FakeContext(), congress=118, treaty_number=2)
    assert isinstance(out, str)
    assert "Chile" in out and "Error" not in out


@pytest.mark.asyncio
async def test_treaty_empty_list_is_not_found_not_server_error():
    """Nonexistent treaty => HTTP 200 with `treaty: []`, not a 404."""
    from congress_api.features import treaties as mod
    with patch.object(mod, "safe_congressional_request",
                      AsyncMock(return_value={"treaty": []})):
        out = await mod.get_treaty_text(FakeContext(), congress=118, treaty_number=99999)
    assert isinstance(out, str)
    assert "data_not_found" in out
    assert "server_error" not in out and "has no attribute" not in out


def test_treaty_record_accepts_dict_and_list():
    from congress_api.features.treaties import _treaty_record
    assert _treaty_record({"treaty": {"number": 1}}) == {"number": 1}
    assert _treaty_record({"treaty": [{"number": 1}]}) == {"number": 1}
    assert _treaty_record({"treaty": []}) is None
    assert _treaty_record({}) is None
    assert _treaty_record(None) is None
