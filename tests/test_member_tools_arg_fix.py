"""
Tests that member tool wrappers pass limit / current_member through to the
underlying members.py implementation functions without TypeError.

This is the member-tool equivalent of test_chamber_param_fix.py (which covers
committee tools fixed in #26/#27).

Covered:
  - get_member_sponsored_legislation   (limit)
  - get_member_cosponsored_legislation (limit)
  - get_members_by_congress            (current_member, limit)
  - get_members_by_state               (current_member, limit)
  - get_members_by_district            (current_member)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class FakeContext:
    pass


# ---------------------------------------------------------------------------
# Wrapper → underlying forwarding tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_member_sponsored_legislation_passes_limit():
    """Wrapper must forward limit to the underlying function."""
    from congress_api.features.members_committees_tools import get_member_sponsored_legislation

    mock_response = "# Sponsored Legislation for Member K000397\nFound 5 bills:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch(
        "congress_api.features.members.get_member_sponsored_legislation",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fn, patch(
        "congress_api.features.members_committees_tools.convert_members_committees_response",
        mock_convert,
    ):
        await get_member_sponsored_legislation(
            FakeContext(), bioguide_id="K000397", limit=50
        )
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["bioguide_id"] == "K000397"
        assert call_kwargs["limit"] == 50


@pytest.mark.asyncio
async def test_get_member_cosponsored_legislation_passes_limit():
    """Wrapper must forward limit to the underlying function."""
    from congress_api.features.members_committees_tools import get_member_cosponsored_legislation

    mock_response = "# Cosponsored Legislation for Member K000397\nFound 3 bills:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch(
        "congress_api.features.members.get_member_cosponsored_legislation",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fn, patch(
        "congress_api.features.members_committees_tools.convert_members_committees_response",
        mock_convert,
    ):
        await get_member_cosponsored_legislation(
            FakeContext(), bioguide_id="K000397", limit=30
        )
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["bioguide_id"] == "K000397"
        assert call_kwargs["limit"] == 30


@pytest.mark.asyncio
async def test_get_members_by_congress_passes_current_member_and_limit():
    """Wrapper must forward current_member and limit to the underlying function."""
    from congress_api.features.members_committees_tools import get_members_by_congress

    mock_response = "# Members of the 118th Congress\nFound 10 members:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch(
        "congress_api.features.members.get_members_by_congress",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fn, patch(
        "congress_api.features.members_committees_tools.convert_members_committees_response",
        mock_convert,
    ):
        await get_members_by_congress(
            FakeContext(), congress=118, current_member=True, limit=25
        )
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["congress"] == 118
        assert call_kwargs["current_member"] is True
        assert call_kwargs["limit"] == 25


@pytest.mark.asyncio
async def test_get_members_by_state_passes_current_member_and_limit():
    """Wrapper must forward current_member and limit to the underlying function."""
    from congress_api.features.members_committees_tools import get_members_by_state

    mock_response = "# Members from CA\nFound 2 current members:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch(
        "congress_api.features.members.get_members_by_state",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fn, patch(
        "congress_api.features.members_committees_tools.convert_members_committees_response",
        mock_convert,
    ):
        await get_members_by_state(
            FakeContext(), state_code="CA", current_member=False, limit=10
        )
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["state_code"] == "CA"
        assert call_kwargs["current_member"] is False
        assert call_kwargs["limit"] == 10


@pytest.mark.asyncio
async def test_get_members_by_district_passes_current_member():
    """Wrapper must forward current_member to the underlying function."""
    from congress_api.features.members_committees_tools import get_members_by_district

    mock_response = "# Members from CA District 39\nFound 1 current members:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch(
        "congress_api.features.members.get_members_by_district",
        new=AsyncMock(return_value=mock_response),
    ) as mock_fn, patch(
        "congress_api.features.members_committees_tools.convert_members_committees_response",
        mock_convert,
    ):
        await get_members_by_district(
            FakeContext(), state_code="CA", district=39, current_member=False
        )
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["state_code"] == "CA"
        assert call_kwargs["district"] == 39
        assert call_kwargs["current_member"] is False


# ---------------------------------------------------------------------------
# Limit reaches safe_congressional_request
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sponsored_legislation_limit_reaches_api():
    """A caller-supplied limit must reach the API params dict."""
    from congress_api.features.members import get_member_sponsored_legislation

    mock_data = {"sponsoredLegislation": []}

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value=mock_data),
    ) as mock_req:
        await get_member_sponsored_legislation(FakeContext(), bioguide_id="K000397", limit=100)
        mock_req.assert_called_once()
        _, _, params = mock_req.call_args.args
        assert params["limit"] == 100


@pytest.mark.asyncio
async def test_cosponsored_legislation_limit_reaches_api():
    """A caller-supplied limit must reach the API params dict."""
    from congress_api.features.members import get_member_cosponsored_legislation

    mock_data = {"cosponsoredLegislation": []}

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value=mock_data),
    ) as mock_req:
        await get_member_cosponsored_legislation(FakeContext(), bioguide_id="K000397", limit=75)
        mock_req.assert_called_once()
        _, _, params = mock_req.call_args.args
        assert params["limit"] == 75


# ---------------------------------------------------------------------------
# Limit > 250 is rejected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sponsored_legislation_limit_over_250_rejected():
    """limit > 250 must return an error, not raise TypeError."""
    from congress_api.features.members import get_member_sponsored_legislation

    result = await get_member_sponsored_legislation(
        FakeContext(), bioguide_id="K000397", limit=999
    )
    assert "error" in result.lower() or "invalid" in result.lower() or "limit" in result.lower()


@pytest.mark.asyncio
async def test_cosponsored_legislation_limit_over_250_rejected():
    """limit > 250 must return an error, not raise TypeError."""
    from congress_api.features.members import get_member_cosponsored_legislation

    result = await get_member_cosponsored_legislation(
        FakeContext(), bioguide_id="K000397", limit=300
    )
    assert "error" in result.lower() or "invalid" in result.lower() or "limit" in result.lower()


# ---------------------------------------------------------------------------
# Regression: underlying functions accept the new kwargs without TypeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_underlying_sponsored_accepts_limit_and_offset():
    """Regression: get_member_sponsored_legislation(ctx, bioguide_id, limit, offset) — no TypeError."""
    from congress_api.features.members import get_member_sponsored_legislation

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value={"sponsoredLegislation": []}),
    ):
        # Must not raise TypeError
        result = await get_member_sponsored_legislation(
            FakeContext(), bioguide_id="K000397", limit=10, offset=5
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_underlying_cosponsored_accepts_limit_and_offset():
    """Regression: get_member_cosponsored_legislation(ctx, bioguide_id, limit, offset) — no TypeError."""
    from congress_api.features.members import get_member_cosponsored_legislation

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value={"cosponsoredLegislation": []}),
    ):
        result = await get_member_cosponsored_legislation(
            FakeContext(), bioguide_id="K000397", limit=10, offset=0
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_underlying_members_by_congress_accepts_current_member_and_limit():
    """Regression: get_members_by_congress(ctx, congress, current_member, limit) — no TypeError."""
    from congress_api.features.members import get_members_by_congress

    with patch(
        "congress_api.features.members.get_all_members_paginated",
        new=AsyncMock(return_value={"members": []}),
    ):
        result = await get_members_by_congress(
            FakeContext(), congress=118, current_member=True, limit=50
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_underlying_members_by_state_accepts_current_member_and_limit():
    """Regression: get_members_by_state(ctx, state_code, current_member, limit) — no TypeError."""
    from congress_api.features.members import get_members_by_state

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value={"members": []}),
    ):
        result = await get_members_by_state(
            FakeContext(), state_code="CA", current_member=True, limit=20
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_underlying_members_by_district_accepts_current_member():
    """Regression: get_members_by_district(ctx, state_code, district, current_member) — no TypeError."""
    from congress_api.features.members import get_members_by_district

    with patch(
        "congress_api.features.members.safe_congressional_request",
        new=AsyncMock(return_value={"members": []}),
    ):
        result = await get_members_by_district(
            FakeContext(), state_code="CA", district=39, current_member=True
        )
    assert isinstance(result, str)
