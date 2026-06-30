"""
Mocked regression tests for the Batch-3 endpoint fixes — assert each impl builds
the CORRECT endpoint path (the bugs were all wrong/non-existent paths).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch


class FakeContext:
    pass


def _endpoint_of(mock):
    return mock.call_args.args[0]


@pytest.mark.asyncio
async def test_committee_communications_uses_house_communication_path():
    from congress_api.features import committees
    resp = {"houseCommunications": [{"number": 1, "congress": 119,
            "communicationType": {"name": "Executive Communication"},
            "referralDate": "2025-01-01", "url": "u"}]}
    with patch.object(committees, "safe_committees_request", new=AsyncMock(return_value=resp)) as m:
        out = await committees.get_committee_communications(FakeContext(), committee_code="hspw00",
                                                            chamber="house", limit=5)
    assert _endpoint_of(m) == "/committee/house/hspw00/house-communication"
    assert "Executive Communication 1" in out
    assert "Referral Date: 2025-01-01" in out


@pytest.mark.asyncio
async def test_committee_communications_uses_senate_communication_path():
    from congress_api.features import committees
    resp = {"senateCommunications": [{"number": 2, "congress": 119,
            "communicationType": {"name": "Executive Communication"},
            "referralDate": "2025-02-02", "url": "u"}]}
    with patch.object(committees, "safe_committees_request", new=AsyncMock(return_value=resp)) as m:
        out = await committees.get_committee_communications(FakeContext(), committee_code="ssga00",
                                                            chamber="senate", limit=5)
    assert _endpoint_of(m) == "/committee/senate/ssga00/senate-communication"
    assert "Executive Communication 2" in out


@pytest.mark.asyncio
async def test_members_by_congress_state_district_uses_congress_path():
    from congress_api.features import members
    resp = {"members": [{"bioguideId": "M001177", "name": "McClintock, Tom",
                         "state": "California", "district": 5, "partyName": "Republican"}]}
    with patch.object(members, "safe_congressional_request", new=AsyncMock(return_value=resp)) as m:
        out = await members.get_members_by_congress_state_district(FakeContext(), congress=119,
                                                                   state_code="CA", district=5)
    assert _endpoint_of(m) == "/member/congress/119/CA/5"
    assert "McClintock" in out


@pytest.mark.asyncio
async def test_search_committee_meetings_drops_committee_code_segment():
    from congress_api.features import committee_meetings
    resp = {"committeeMeetings": [{"chamber": "House", "congress": 119,
                                   "eventId": "119423", "url": "u"}]}
    with patch.object(committee_meetings, "safe_congressional_request", new=AsyncMock(return_value=resp)) as m:
        out = await committee_meetings.search_committee_meetings(FakeContext(), congress=119,
                                                                 chamber="house", committee_code="hsag00", limit=5)
    # committee_code must NOT appear as a path segment (the bug)
    assert _endpoint_of(m) == "/committee-meeting/119/house"
    assert "not supported" in out  # the explanatory note
