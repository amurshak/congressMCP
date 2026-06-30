"""
Mocked tests for committee sub-resource paging (offset / most_recent).

The committee bills/reports/communications endpoints are oldest-first with no
sort, so most_recent must probe pagination.count and fetch the final page, then
reverse for newest-first. The nominations endpoint is already newest-first, so it
must NOT jump. These tests assert that behavior offline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from congress_api.features import committees


class FakeContext:
    pass


# Oldest-first page: item "3" is newest. count says 100 total.
_BILLS_PAGE = {
    "committee-bills": {"bills": [
        {"type": "S", "number": "1", "congress": 118, "actionDate": "2024-01-01"},
        {"type": "S", "number": "2", "congress": 119, "actionDate": "2025-01-01"},
        {"type": "S", "number": "3", "congress": 119, "actionDate": "2026-06-01"},
    ]},
    "pagination": {"count": 100},
}


def _bills_side_effect_factory(calls):
    async def _se(endpoint, ctx, params=None):
        calls.append(dict(params or {}))
        return _BILLS_PAGE
    return _se


@pytest.mark.asyncio
async def test_committee_bills_most_recent_jumps_and_reverses():
    calls = []
    with patch.object(committees, "safe_committees_request",
                      new=_bills_side_effect_factory(calls)):
        out = await committees.get_committee_bills(
            FakeContext(), committee_code="sseg00", chamber="senate", limit=3)
    # First call is the count probe (limit=1); the main fetch jumps to count-limit.
    assert calls[0].get("limit") == 1
    assert calls[-1].get("offset") == 97  # 100 - 3
    # Output reversed -> newest (number 3) appears before oldest (number 1).
    assert out.index("S 3") < out.index("S 1")
    assert "of 100 total" in out


@pytest.mark.asyncio
async def test_committee_bills_oldest_no_jump():
    calls = []
    with patch.object(committees, "safe_committees_request",
                      new=_bills_side_effect_factory(calls)):
        out = await committees.get_committee_bills(
            FakeContext(), committee_code="sseg00", chamber="senate", limit=3,
            most_recent=False)
    # No probe, no offset -> oldest order preserved (number 1 first).
    assert all("offset" not in c for c in calls)
    assert out.index("S 1") < out.index("S 3")


@pytest.mark.asyncio
async def test_committee_bills_explicit_offset_skips_probe():
    calls = []
    with patch.object(committees, "safe_committees_request",
                      new=_bills_side_effect_factory(calls)):
        await committees.get_committee_bills(
            FakeContext(), committee_code="sseg00", chamber="senate", limit=3, offset=10)
    # Explicit offset -> no count probe (no limit==1 call), uses the given offset.
    assert all(c.get("limit") != 1 for c in calls)
    assert calls[-1].get("offset") == 10


@pytest.mark.asyncio
async def test_committee_nominations_newest_first_no_jump():
    calls = []
    nominations_resp = {
        "nominations": [
            {"number": "1127", "congress": 119, "updateDate": "2026-06-25"},
            {"number": "1000", "congress": 119, "updateDate": "2026-01-01"},
        ],
        "pagination": {"count": 5551},
    }

    async def _se(endpoint, ctx, params=None):
        calls.append(dict(params or {}))
        return nominations_resp

    with patch.object(committees, "safe_committees_request", new=_se):
        out = await committees.get_committee_nominations(
            FakeContext(), committee_code="ssju00", limit=2)
    # Newest-first endpoint: single fetch, no probe, no offset, order preserved.
    assert len(calls) == 1
    assert "offset" not in calls[0]
    assert out.index("1127") < out.index("1000")
    assert "of 5551 total" in out
