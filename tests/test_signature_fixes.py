"""
Mocked regression tests for the Batch-1 signature fixes:
- search_committees: keywords optional (browse mode), committee_type filters
  client-side, and the tool wrapper no longer crashes forwarding committee_type.
- search_summaries: keywords optional (browse mode), no "keywords cannot be empty".

These patch the API layer so they run offline and fast.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch


class FakeContext:
    pass


_COMMITTEES = {
    "committees": [
        {"name": "Judiciary Committee", "chamber": "House", "systemCode": "hsju00",
         "committeeTypeCode": "Standing", "url": "u1"},
        {"name": "Select Committee on Intelligence", "chamber": "House", "systemCode": "hlig00",
         "committeeTypeCode": "Select", "url": "u2"},
    ]
}


@pytest.mark.asyncio
async def test_search_committees_browse_without_keywords():
    """Impl must not require keywords; browsing returns committees."""
    from congress_api.features import committees
    with patch.object(committees, "safe_committees_request", new=AsyncMock(return_value=_COMMITTEES)):
        result = await committees.search_committees(FakeContext(), chamber="house", limit=10)
    assert "Judiciary Committee" in result
    assert "cannot be empty" not in result.lower()


@pytest.mark.asyncio
async def test_search_committees_keyword_filters_clientside():
    from congress_api.features import committees
    with patch.object(committees, "safe_committees_request", new=AsyncMock(return_value=_COMMITTEES)):
        result = await committees.search_committees(FakeContext(), keywords="judiciary", limit=10)
    assert "Judiciary Committee" in result
    assert "Intelligence" not in result


@pytest.mark.asyncio
async def test_search_committees_type_filters_clientside():
    from congress_api.features import committees
    with patch.object(committees, "safe_committees_request", new=AsyncMock(return_value=_COMMITTEES)):
        select = await committees.search_committees(FakeContext(), committee_type="select", limit=10)
        standing = await committees.search_committees(FakeContext(), committee_type="standing", limit=10)
    assert "Intelligence" in select and "Judiciary" not in select
    assert "Judiciary" in standing and "Intelligence" not in standing


@pytest.mark.asyncio
async def test_search_committees_wrapper_forwards_committee_type_without_crash():
    """The #1 regression: wrapper forwarding committee_type used to crash the impl."""
    from congress_api.features import members_committees_tools as mct
    with patch("congress_api.features.committees.safe_committees_request",
               new=AsyncMock(return_value=_COMMITTEES)):
        resp = await mct.search_committees(FakeContext(), chamber="House",
                                           committee_type="Standing", limit=10)
    # wrapper returns a structured response; success means no exception path
    assert resp.success is True
    assert resp.operation == "search_committees"


@pytest.mark.asyncio
async def test_search_summaries_optional_keywords_no_empty_error():
    """search_summaries must browse without keywords (no 'cannot be empty')."""
    from congress_api.features import summaries
    payload = {"summaries": [{"bill": {"congress": 119, "type": "HR", "number": "1",
                                        "title": "Test"}, "actionDate": "2025-01-01",
                              "text": "A summary", "updateDate": "2025-01-02"}]}
    with patch.object(summaries, "safe_congressional_request", new=AsyncMock(return_value=payload)):
        result = await summaries.search_summaries(FakeContext(), congress=119, limit=5)
    assert "cannot be empty" not in result.lower()
    assert "Recent Bill Summaries" in result or "summaries" in result.lower()
