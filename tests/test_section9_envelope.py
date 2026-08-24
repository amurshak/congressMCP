"""One error envelope for the whole server (spec section 9).

format_error_response emits {"error": {code, message, detail, remediation}}
as JSON; structured tools additionally carry the typed `error` field with
success=False. Codes are stable lowercase strings; detail never carries
secret-bearing URLs (F22 rule).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch

from congress_api.core.exceptions import (
    CommonErrors,
    CongressionalAPIError,
    ErrorText,
    error_envelope,
    format_error_response,
)


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


def _api_error(status):
    return {"error": f"API request failed: {status}", "status_code": status,
            "request_time": 0.1}


# ---------------------------------------------------------------------------
# the choke point
# ---------------------------------------------------------------------------

def test_format_error_response_is_json_envelope():
    err = CommonErrors.data_not_found("bill", identifier="119/hr/9999999")
    out = format_error_response(err)
    assert isinstance(out, str) and isinstance(out, ErrorText)
    payload = json.loads(out)["error"]
    assert payload["code"] == "data_not_found"
    assert "119/hr/9999999" in payload["message"]
    assert payload["remediation"]            # suggestions folded in
    assert out.error_response is err         # typed carrier for converters


def test_envelope_strips_url_secrets_from_detail():
    err = CommonErrors.api_server_error(
        "/bill/119", message="boom")
    err.details = {"endpoint": "/bill/119",
                   "url": "https://api.congress.gov/v3/bill/119?api_key=SECRET123&format=json",
                   "next": "https://cdn.example.com/file.xml?X-Amz-Signature=tok"}
    payload = error_envelope(err)["error"]
    assert payload["detail"]["url"] == "https://api.congress.gov/v3/bill/119"
    assert "SECRET123" not in json.dumps(payload)
    assert "X-Amz-Signature" not in json.dumps(payload)
    assert payload["detail"]["endpoint"] == "/bill/119"   # non-URLs untouched


def test_envelope_code_is_lowercase_stable():
    for make, expected in (
        (lambda: CommonErrors.invalid_parameter("x", 1, "bad"), "invalid_parameter"),
        (lambda: CommonErrors.api_server_error("/x"), "server_error"),
        (lambda: CommonErrors.rate_limit_exceeded("/x"), "rate_limit_exceeded"),
    ):
        assert error_envelope(make())["error"]["code"] == expected


# ---------------------------------------------------------------------------
# str-returning tools emit the envelope as their whole response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_str_tool_404_is_parseable_envelope():
    from congress_api.features.buckets.bills import api as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await mod.get_bill_details(FakeContext(), congress=119, bill_type="hr",
                                         bill_number=9999999)
    payload = json.loads(out)["error"]
    assert payload["code"] == "data_not_found"
    assert "retrying will not help" in payload["remediation"]


@pytest.mark.asyncio
async def test_str_router_returns_envelope_not_toolerror():
    """laws.* handlers call the wrapper bare; the router returns the JSON
    envelope now instead of a stringified ToolError."""
    from congress_api.features.buckets import laws as router
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        out = await router.laws(FakeContext(), operation="get_law_details",
                                congress=119, law_type="pub", law_number=999999)
    payload = json.loads(out)["error"]
    assert payload["code"] == "data_not_found"


# ---------------------------------------------------------------------------
# structured tools carry the typed error field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_structured_tool_carries_error_field():
    from congress_api.features import members_committees_tools as mod
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        resp = await mod.get_member_details(FakeContext(), bioguide_id="ZZZ999")
    assert resp.success is False
    assert resp.error is not None
    assert resp.error.code == "data_not_found"
    assert resp.error.remediation
    assert resp.results_count == 0
    assert resp.summary.startswith("data_not_found:")


@pytest.mark.asyncio
async def test_model_router_carries_error_field():
    from congress_api.features.buckets import voting_and_nominations as router
    from congress_api.core import api_wrapper
    with patch.object(api_wrapper, "make_api_request", AsyncMock(return_value=_api_error(404))):
        resp = await router.voting_and_nominations(
            FakeContext(), operation="get_nomination_details", congress=119,
            nomination_number=999999)
    assert resp.success is False and resp.error.code == "data_not_found"
    assert resp.votes == [] and resp.nominations == []


def test_all_five_converters_populate_error():
    from congress_api.utils.response_converters import convert_members_committees_response
    from congress_api.features.buckets.voting_and_nominations import (
        _convert_to_structured_response as conv_votes)
    from congress_api.features.buckets.records_and_hearings import (
        _convert_to_structured_response as conv_records)
    from congress_api.features.buckets.committee_intelligence import (
        _convert_to_structured_response as conv_ci)
    from congress_api.features.buckets.research_and_professional import (
        _convert_to_structured_response as conv_research)
    err_text = format_error_response(CommonErrors.data_not_found("thing", identifier="x"))
    for conv in (lambda r: convert_members_committees_response(r, "op"),
                 lambda r: conv_votes(r, "op"), lambda r: conv_records(r, "op"),
                 lambda r: conv_ci(r, "op"), lambda r: conv_research(r, "op")):
        resp = conv(err_text)
        assert resp.success is False, conv
        assert resp.error is not None and resp.error.code == "data_not_found"
        assert resp.results_count == 0


def test_success_paths_have_no_error_field():
    from congress_api.utils.response_converters import convert_members_committees_response
    resp = convert_members_committees_response("# X\nFound 2 members:", "op")
    assert resp.success is True and resp.error is None


@pytest.mark.asyncio
async def test_wrapper_unexpected_exception_carries_internal_error():
    from congress_api.features import members_committees_tools as mod
    with patch("congress_api.features.members.get_member_details",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = await mod.get_member_details(FakeContext(), bioguide_id="S000148")
    assert resp.success is False
    assert resp.error is not None and resp.error.code == "internal_error"
    assert "boom" in resp.error.message


def test_wrapper_raises_typed_error_with_envelope_str():
    err = CommonErrors.data_not_found("bill", identifier="x")
    exc = CongressionalAPIError(err)
    payload = json.loads(str(exc))["error"]
    assert payload["code"] == "data_not_found"
