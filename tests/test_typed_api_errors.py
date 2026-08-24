"""Issue #53: a Congress.gov 404/400 must reach the user as NOT_FOUND /
INVALID_PARAMETERS, not as "The Congressional API is experiencing issues".

Covers the wrapper (raises the typed CongressionalAPIError), representative
handlers (pass it through), and a static guard that every generic
`except Exception` in a handler module is preceded by the typed clause.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


def _api_error(status):
    return {"error": f"API request failed: {status}", "status_code": status,
            "request_time": 0.1}


# ---------------------------------------------------------------------------
# wrapper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wrapper_raises_typed_not_found_on_404():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError
    with patch.object(mod, "make_api_request", AsyncMock(return_value=_api_error(404))):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119/hr/9999999", FakeContext(), {})
    err = ei.value.error_response
    assert err.error_code == "DATA_NOT_FOUND"
    assert err.error_type == "not_found"
    assert err.details["endpoint"] == "/bill/119/hr/9999999"
    assert "retrying will not help" in " ".join(err.suggestions)


@pytest.mark.asyncio
async def test_wrapper_does_not_retry_404():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError
    mock = AsyncMock(return_value=_api_error(404))
    with patch.object(mod, "make_api_request", mock), \
            pytest.raises(CongressionalAPIError):
        await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                             endpoint_type="bills")  # retry_count=3
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_wrapper_raises_typed_invalid_on_400():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError
    with patch.object(mod, "make_api_request", AsyncMock(return_value=_api_error(400))):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {})
    assert ei.value.error_response.error_code == "INVALID_PARAMETERS"


@pytest.mark.asyncio
async def test_wrapper_keeps_server_error_for_5xx():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError
    with patch.object(mod, "make_api_request", AsyncMock(return_value=_api_error(500))), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")
    assert ei.value.error_response.error_code == "SERVER_ERROR"


# ---------------------------------------------------------------------------
# handlers pass the typed error through
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_member_details_reports_not_found():
    from congress_api.features import members as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await mod.get_member_details(FakeContext(), bioguide_id="ZZZ999")
    assert isinstance(out, str)
    assert "data_not_found" in out
    assert "experiencing issues" not in out and "server_error" not in out


@pytest.mark.asyncio
async def test_get_bill_details_reports_not_found():
    from congress_api.features.buckets.bills import api as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await mod.get_bill_details(FakeContext(), congress=119, bill_type="hr",
                                         bill_number=9999999)
    assert isinstance(out, str)
    assert "data_not_found" in out
    assert "experiencing issues" not in out


@pytest.mark.asyncio
async def test_get_treaty_detail_reports_not_found():
    from congress_api.features import treaties as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await mod.get_treaty_detail(FakeContext(), congress=118, treaty_number=99999)
    assert isinstance(out, str)
    assert "data_not_found" in out and "server_error" not in out


# ---------------------------------------------------------------------------
# static guard
# ---------------------------------------------------------------------------

def _handler_modules():
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "congress_api", "features")
    files = glob.glob(os.path.join(root, "*.py")) + [
        os.path.join(root, "buckets", "bills", "api.py"),
        os.path.join(root, "buckets", "amendments", "api.py"),
    ]
    for f in files:
        src = open(f).read()
        if "return format_error_response" in src and "raise ToolError" not in src:
            yield f, src


def test_every_generic_except_that_formats_errors_has_typed_clause_first():
    """In handler modules, `except Exception as e:` blocks that return a
    formatted error must be preceded by `except CongressionalAPIError`, else a
    typed 404 gets re-wrapped as SERVER_ERROR again."""
    offenders = []
    for f, src in _handler_modules():
        lines = src.split("\n")
        for i, line in enumerate(lines):
            if re.match(r"^\s*except Exception as e:\s*$", line):
                window = "\n".join(lines[i + 1:i + 14])
                if "format_error_response(" not in window:
                    continue
                prev = "\n".join(lines[max(0, i - 2):i])
                if "except CongressionalAPIError" not in prev:
                    offenders.append(f"{os.path.relpath(f)}:{i + 1}")
    assert offenders == []


# ---------------------------------------------------------------------------
# critique follow-ups: pagination path, routers, status-based classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_members_filtered_path_reports_not_found():
    """chamber/party/name searches go through get_all_members_paginated; a
    typed 404 there must not be re-wrapped as SERVER_ERROR."""
    from congress_api.features import members as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await mod.search_members(FakeContext(), state="WY", chamber="senate", congress=119)
    assert "data_not_found" in out and "server_error" not in out
    assert "Pagination error" not in out


@pytest.mark.asyncio
async def test_name_search_skips_congress_that_404s():
    from congress_api.features import members as mod
    from congress_api.core.exceptions import CongressionalAPIError, CommonErrors
    calls = []

    async def fake_paginated(_ctx, endpoint, _params):
        calls.append(endpoint)
        if len(calls) == 1:
            raise CongressionalAPIError(CommonErrors.data_not_found("members", identifier=endpoint))
        return {"members": []}

    with patch.object(mod, "get_all_members_paginated", fake_paginated), \
            patch.object(mod, "current_congress", lambda: 121):
        out = await mod.search_members(FakeContext(), name="Nobody")
    assert len(calls) == 3           # first congress skipped, search continued
    assert isinstance(out, str)


@pytest.mark.asyncio
async def test_router_surfaces_typed_error_from_bare_handler():
    """nominations.* handlers call the wrapper with no try/except; the
    voting_and_nominations router must turn the typed error into a ToolError
    that carries the classification, not a generic failure."""
    from congress_api.features.buckets import voting_and_nominations as router
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        resp = await router.voting_and_nominations(
            FakeContext(), operation="get_nomination_details", congress=119,
            nomination_number=999999)
    assert resp.success is False
    assert resp.error is not None and resp.error.code == "data_not_found"
    assert "experiencing issues" not in resp.summary


def test_every_router_has_typed_clause():
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "congress_api", "features")
    routers = [f for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True)
               if "raise ToolError" in open(f).read() and "except Exception as e:" in open(f).read()]
    assert routers, "no router modules found"
    missing = [os.path.relpath(f) for f in routers
               if "except CongressionalAPIError" not in open(f).read()]
    assert missing == []


@pytest.mark.asyncio
async def test_classification_uses_http_status_not_endpoint_text():
    """An endpoint whose path contains '404' with a 500 status is a server
    error; a 404 status whose message lacks '404' is still not-found."""
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value={"error": "boom", "status_code": 500})), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119/hr/4004", FakeContext(), {},
                                                 endpoint_type="default")
    assert ei.value.error_response.error_code == "SERVER_ERROR"

    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value={"error": "gone", "status_code": 404})):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/member/X", FakeContext(), {})
    assert ei.value.error_response.error_code == "DATA_NOT_FOUND"


@pytest.mark.asyncio
async def test_429_is_rate_limit_not_server_error():
    from congress_api.core import api_wrapper as mod
    from congress_api.core.exceptions import CongressionalAPIError
    with patch.object(mod, "make_api_request",
                      AsyncMock(return_value={"error": "slow down", "status_code": 429})), \
            patch.object(mod.asyncio, "sleep", AsyncMock()):
        with pytest.raises(CongressionalAPIError) as ei:
            await mod.safe_congressional_request("/bill/119", FakeContext(), {},
                                                 endpoint_type="default")
    assert ei.value.error_response.error_code == "RATE_LIMIT_EXCEEDED"
