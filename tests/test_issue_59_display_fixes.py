"""
Regression tests for issue #59: cosmetic display bugs.

- Hearings with the API's literal "NoChamber" token (joint/unassigned
  committee hearings) rendered "Chamber: NoChamber" instead of a
  human-readable label.
- The committee-nominations listing rendered "Nominees: Unknown nominees"
  for every row because it read a `nominees` array shape (firstName/
  lastName) that only exists on the nomination *detail* endpoint; the
  committee-level listing instead carries the nominee's name and
  position in a `description` field.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch

from congress_api.features import committees
from congress_api.features.hearings import (
    _display_chamber,
    format_hearing_detail,
    format_hearing_item,
)


class FakeContext:
    pass


# --- Hearing chamber display ---

def test_display_chamber_maps_nochamber_to_joint():
    assert _display_chamber("NoChamber") == "Joint"


def test_display_chamber_passes_through_known_values():
    assert _display_chamber("House") == "House"
    assert _display_chamber("Senate") == "Senate"


def test_display_chamber_defaults_missing_to_na():
    assert _display_chamber(None) == "N/A"
    assert _display_chamber("") == "N/A"


def test_format_hearing_item_shows_joint_not_nochamber():
    hearing = {
        "chamber": "NoChamber",
        "congress": 119,
        "jacketNumber": 61499,
        "updateDate": "2026-08-21T02:06:42Z",
        "url": "https://api.congress.gov/v3/hearing/119/nochamber/61499",
    }
    out = format_hearing_item(hearing)
    assert "Chamber: Joint" in out
    assert "NoChamber" not in out


def test_format_hearing_detail_shows_joint_not_nochamber():
    hearing = {
        "chamber": "NoChamber",
        "title": "Intercepting Terror: Strengthening Ukrainian Air Defense",
        "congress": 119,
        "citation": "J.Hrg.119",
        "jacketNumber": 61499,
        "updateDate": "2026-08-21T02:06:42Z",
    }
    out = format_hearing_detail(hearing)
    assert "Chamber: Joint" in out
    assert "NoChamber" not in out


def test_format_hearing_item_still_shows_house_and_senate():
    house = format_hearing_item({"chamber": "House", "congress": 119,
                                  "jacketNumber": 1, "updateDate": "d",
                                  "url": "u"})
    senate = format_hearing_item({"chamber": "Senate", "congress": 119,
                                   "jacketNumber": 2, "updateDate": "d",
                                   "url": "u"})
    assert "Chamber: House" in house
    assert "Chamber: Senate" in senate


# --- Committee nominations nominee display ---

_NOMINATIONS_PAGE = {
    "nominations": [
        {
            "citation": "PN1201-7",
            "congress": 119,
            "description": (
                "Jurgen Ryan Soekhoe, of the District of Columbia, to be "
                "United States Marshal for the District of Columbia for "
                "the term of four years, vice Patrick A. Burke, term "
                "expired."
            ),
            "number": 1201,
            "updateDate": "2026-07-22T11:00:26Z",
            "url": "https://api.congress.gov/v3/nomination/119/1201-7",
        },
    ],
    "pagination": {"count": 1},
}


@pytest.mark.asyncio
async def test_committee_nominations_uses_description_not_unknown():
    async def _se(endpoint, ctx, params=None):
        return _NOMINATIONS_PAGE

    with patch.object(committees, "safe_committees_request", new=_se):
        out = await committees.get_committee_nominations(
            FakeContext(), committee_code="ssju00", limit=1)

    assert "Unknown nominees" not in out
    assert "Description: Jurgen Ryan Soekhoe" in out


@pytest.mark.asyncio
async def test_committee_nominations_prefers_real_nominee_names():
    page = {
        "nominations": [
            {
                "citation": "PN1-1",
                "congress": 119,
                "number": 1,
                "description": "Should not be shown when nominees present.",
                "nominees": [{"firstName": "Jane", "lastName": "Doe"}],
                "updateDate": "2026-01-01",
                "url": "u",
            },
        ],
        "pagination": {"count": 1},
    }

    async def _se(endpoint, ctx, params=None):
        return page

    with patch.object(committees, "safe_committees_request", new=_se):
        out = await committees.get_committee_nominations(
            FakeContext(), committee_code="ssju00", limit=1)

    assert "Nominees: Jane Doe" in out
    assert "Description:" not in out


@pytest.mark.asyncio
async def test_committee_nominations_omits_line_when_no_nominee_info():
    page = {
        "nominations": [
            {
                "citation": "PN2-1",
                "congress": 119,
                "number": 2,
                "updateDate": "2026-01-01",
                "url": "u",
            },
        ],
        "pagination": {"count": 1},
    }

    async def _se(endpoint, ctx, params=None):
        return page

    with patch.object(committees, "safe_committees_request", new=_se):
        out = await committees.get_committee_nominations(
            FakeContext(), committee_code="ssju00", limit=1)

    assert "Unknown nominees" not in out
    assert "Nominees:" not in out
    assert "Description:" not in out
