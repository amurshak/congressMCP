"""Step 1 of the govinfo-search work order (spec section 6.1): query
assembly and validation, each defense in isolation, plus the reused keyed
client's new POST surface.

Assembly properties under test:
- blank/whitespace keywords -> invalid_parameters, and nothing else runs
- keywords pass through verbatim (operators, quotes, inner whitespace)
- scoping terms appended exactly; sorts always the explicit score DESC
- pageSize = min(3 * limit, 300); resultLevel/historical never sent
- the non-numeric-congress guard (a bad congress: term 500s upstream
  wearing the outage body, so it must die client-side)
- govinfo_search_post: POST /search, X-Api-Key header only (never in the
  query string), JSON body intact, 429 backoff retry.
"""
import json
import os
import sys
from unittest.mock import AsyncMock

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.core.exceptions import (  # noqa: E402
    CongressionalAPIError,
    error_envelope,
)
from congress_api.features.buckets.bills import govinfo_search as gs  # noqa: E402


def _code(exc_info) -> str:
    return error_envelope(exc_info.value.error_response)["error"]["code"]


# ---------------------------------------------------------------------------
# Blank-keyword rejection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("blank", ["", "   ", "\t \n", None])
def test_blank_keywords_rejected_as_invalid_parameters(blank):
    with pytest.raises(CongressionalAPIError) as exc:
        gs.validate_keywords(blank)
    assert _code(exc) == "invalid_parameters"


def test_keywords_pass_through_verbatim_after_outer_strip():
    raw = '  title:"Safe Act" OR RECA -noise  NOT   x  '
    kept = gs.validate_keywords(raw)
    # Outer whitespace stripped; inner spacing, quotes, and operators kept.
    assert kept == 'title:"Safe Act" OR RECA -noise  NOT   x'


# ---------------------------------------------------------------------------
# Scoping guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["abc", "11x", 0, -3, True, 12.5])
def test_congress_guard_rejects_non_positive_int_shapes(bad):
    with pytest.raises(CongressionalAPIError):
        gs.validate_congress(bad)


def test_congress_none_passes_and_numeric_is_sanitized():
    assert gs.validate_congress(None) is None
    assert gs.validate_congress(119) == 119
    # The shared validator int()s numeric strings; the sanitized value is
    # what reaches the congress: term, so this cannot 500 upstream.
    assert gs.validate_congress("118") == 118


def test_bill_type_accepts_exactly_the_eight_documented_values():
    for value in gs.BILL_TYPES:
        assert gs.validate_bill_type(value) == value
        assert gs.validate_bill_type(value.upper()) == value
    assert gs.validate_bill_type(None) is None
    for bad in ("bill", "hrx", "amdt", ""):
        with pytest.raises(CongressionalAPIError):
            gs.validate_bill_type(bad)


def test_limit_clamps_with_advisory_wording():
    assert gs.clamp_limit(25) == (25, None)
    value, note = gs.clamp_limit(0)
    assert value == 1 and "adjusted" in note
    value, note = gs.clamp_limit(9999)
    assert value == 250 and "adjusted" in note
    with pytest.raises(CongressionalAPIError):
        gs.clamp_limit("abc")


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def test_query_assembly_appends_scoping_terms():
    assert gs.build_query("RECA", 119, "hr") == \
        "RECA collection:bills congress:119 billtype:hr"
    assert gs.build_query("RECA", None, None) == "RECA collection:bills"
    assert gs.build_query("RECA", 119, None) == \
        "RECA collection:bills congress:119"
    assert gs.build_query('title:"Safe Act" OR x', None, "sres") == \
        'title:"Safe Act" OR x collection:bills billtype:sres'


def test_body_shape_sorts_and_omissions():
    body = gs.build_search_body("RECA collection:bills", limit=10)
    # Exactly these keys: resultLevel and historical are measured no-ops
    # for BILLS and must not be sent.
    assert set(body) == {"query", "pageSize", "offsetMark", "sorts"}
    assert body["offsetMark"] == "*"
    assert body["sorts"] == [{"field": "score", "sortOrder": "DESC"}]


def test_body_carries_explicit_cursor():
    body = gs.build_search_body("x collection:bills", limit=10,
                                offset_mark="AoJwgIrqmZ0D")
    assert body["offsetMark"] == "AoJwgIrqmZ0D"


@pytest.mark.parametrize("limit,expected", [(1, 3), (10, 30), (100, 300),
                                            (250, 300)])
def test_page_size_is_three_x_limit_capped_at_300(limit, expected):
    assert gs.build_search_body("q", limit)["pageSize"] == expected


def test_sorts_are_a_fresh_list_per_body():
    a = gs.build_search_body("q", 10)
    b = gs.build_search_body("q", 10)
    a["sorts"][0]["sortOrder"] = "ASC"
    assert b["sorts"][0]["sortOrder"] == "DESC"


# ---------------------------------------------------------------------------
# Reused keyed client: POST surface
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_post_sends_keyed_header_post_with_body(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.setenv("GOVINFO_API_KEY", "sekret-key")
    seen = {}

    def handler(request):
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("X-Api-Key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"count": 0, "results": [],
                                         "offsetMark": None})

    async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)) as injected:
        body = gs.build_search_body("RECA collection:bills", 10)
        response = await client_mod.govinfo_search_post(body, client=injected)

    assert response.status_code == 200
    assert seen["method"] == "POST"
    assert seen["url"] == "https://api.govinfo.gov/search"
    assert "?" not in seen["url"]          # never key-in-query
    assert seen["key"] == "sekret-key"     # X-Api-Key header
    assert seen["body"] == body            # JSON transport, verbatim


@pytest.mark.asyncio
async def test_search_post_backs_off_on_429_then_succeeds(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.setenv("GOVINFO_API_KEY", "sekret-key")
    sleeper = AsyncMock()
    monkeypatch.setattr(client_mod.asyncio, "sleep", sleeper)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"count": 0, "results": []})

    async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)) as injected:
        response = await client_mod.govinfo_search_post(
            {"query": "q"}, client=injected)

    assert response.status_code == 200
    assert calls["n"] == 2
    assert sleeper.await_count == 1


@pytest.mark.asyncio
async def test_search_post_keyless_omits_header(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(client_mod, "API_KEY", None)
    seen = {}

    def handler(request):
        seen["has_key"] = "X-Api-Key" in request.headers
        return httpx.Response(401)

    async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)) as injected:
        response = await client_mod.govinfo_search_post(
            {"query": "q"}, client=injected)

    assert response.status_code == 401
    assert seen["has_key"] is False
