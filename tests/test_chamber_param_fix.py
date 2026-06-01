"""
Tests that get_committee_bills, get_committee_reports, and get_committee_communications
accept and pass through the chamber parameter correctly (Issue #26 fix).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class FakeContext:
    pass


@pytest.mark.asyncio
async def test_get_committee_bills_accepts_chamber():
    """Tool wrapper must pass chamber through to the underlying function."""
    from congress_api.features.members_committees_tools import get_committee_bills

    mock_response = "Bills referred to House Committee hsju:\n- HR 1: Test Bill"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch("congress_api.features.committees.get_committee_bills", new=AsyncMock(return_value=mock_response)) as mock_fn, \
         patch("congress_api.features.members_committees_tools.convert_members_committees_response", mock_convert):
        await get_committee_bills(FakeContext(), chamber="house", committee_code="hsju", limit=5)
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["chamber"] == "house"
        assert call_kwargs["committee_code"] == "hsju"


@pytest.mark.asyncio
async def test_get_committee_reports_accepts_chamber():
    """Tool wrapper must pass chamber through to the underlying function."""
    from congress_api.features.members_committees_tools import get_committee_reports

    mock_response = "Reports from Senate Committee ssfi:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch("congress_api.features.committees.get_committee_reports", new=AsyncMock(return_value=mock_response)) as mock_fn, \
         patch("congress_api.features.members_committees_tools.convert_members_committees_response", mock_convert):
        await get_committee_reports(FakeContext(), chamber="senate", committee_code="ssfi", limit=5)
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["chamber"] == "senate"
        assert call_kwargs["committee_code"] == "ssfi"


@pytest.mark.asyncio
async def test_get_committee_communications_accepts_chamber():
    """Tool wrapper must pass chamber through to the underlying function."""
    from congress_api.features.members_committees_tools import get_committee_communications

    mock_response = "Communications from House Committee hsju:"
    mock_convert = MagicMock(return_value=MagicMock(success=True))

    with patch("congress_api.features.committees.get_committee_communications", new=AsyncMock(return_value=mock_response)) as mock_fn, \
         patch("congress_api.features.members_committees_tools.convert_members_committees_response", mock_convert):
        await get_committee_communications(FakeContext(), chamber="house", committee_code="hsju", limit=5)
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["chamber"] == "house"
        assert call_kwargs["committee_code"] == "hsju"
