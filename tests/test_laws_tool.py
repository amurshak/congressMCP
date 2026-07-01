"""
Mocked tests for the new `laws` tool: endpoint construction, law-type
normalization, routing, and reuse of BillsFormatter.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch

from congress_api.features.buckets import laws


class FakeContext:
    pass


_LIST = {"bills": [{"type": "S", "number": "1003", "congress": 119,
                    "title": "Lulu's Law",
                    "latestAction": {"text": "Became Public Law No: 119-100.",
                                     "actionDate": "2026-06-26"},
                    "laws": [{"number": "119-100", "type": "Public Law"}], "url": "u"}]}
_DETAIL = {"bill": {"type": "S", "number": "5", "congress": 119,
                    "title": "Laken Riley Act",
                    "latestAction": {"text": "Became Public Law No: 119-1.", "actionDate": "2025-01-29"}}}


def _endpoint(mock):
    return mock.call_args.args[0]


def test_normalize_law_type():
    assert laws._normalize_law_type("public") == "pub"
    assert laws._normalize_law_type("pub") == "pub"
    assert laws._normalize_law_type("private") == "priv"
    assert laws._normalize_law_type("priv") == "priv"
    assert laws._normalize_law_type("xyz") is None
    assert laws._normalize_law_type(None) is None


@pytest.mark.asyncio
async def test_get_laws_builds_congress_endpoint():
    with patch.object(laws, "safe_congressional_request", new=AsyncMock(return_value=_LIST)) as m:
        out = await laws.get_laws(FakeContext(), congress=119, limit=5)
    assert _endpoint(m) == "/law/119"
    assert "Lulu" in out and "119th Congress" in out


@pytest.mark.asyncio
async def test_get_laws_builds_lawtype_endpoint():
    with patch.object(laws, "safe_congressional_request", new=AsyncMock(return_value=_LIST)) as m:
        await laws.get_laws(FakeContext(), congress=119, law_type="public", limit=5)
    assert _endpoint(m) == "/law/119/pub"


@pytest.mark.asyncio
async def test_get_laws_rejects_bad_lawtype():
    with patch.object(laws, "safe_congressional_request", new=AsyncMock(return_value=_LIST)):
        out = await laws.get_laws(FakeContext(), congress=119, law_type="bogus")
    assert "Invalid law_type" in out


@pytest.mark.asyncio
async def test_get_law_details_builds_endpoint_and_formats():
    with patch.object(laws, "safe_congressional_request", new=AsyncMock(return_value=_DETAIL)) as m:
        out = await laws.get_law_details(FakeContext(), congress=119, law_type="pub", law_number=1)
    assert _endpoint(m) == "/law/119/pub/1"
    assert "Laken Riley Act" in out


@pytest.mark.asyncio
async def test_route_dispatches_operations():
    with patch.object(laws, "safe_congressional_request", new=AsyncMock(return_value=_LIST)):
        out = await laws.route_laws_operation(FakeContext(), "get_laws", congress=119)
    assert "119th Congress" in out
    with pytest.raises(Exception):
        await laws.route_laws_operation(FakeContext(), "nonsense_op", congress=119)
