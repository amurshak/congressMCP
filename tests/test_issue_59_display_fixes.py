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
    assert _display_chamber("NoChamber") == "Joint (nochamber)"


def test_display_chamber_is_case_insensitive():
    # The API uses lowercase "nochamber" in URLs/path params and the
    # mixed-case "NoChamber" in JSON payload values -- both must map.
    assert _display_chamber("nochamber") == "Joint (nochamber)"
    assert _display_chamber("NOCHAMBER") == "Joint (nochamber)"


def test_display_chamber_passes_through_known_values():
    assert _display_chamber("House") == "House"
    assert _display_chamber("Senate") == "Senate"


def test_display_chamber_defaults_missing_to_na():
    assert _display_chamber(None) == "N/A"
    assert _display_chamber("") == "N/A"


def test_display_chamber_keeps_nochamber_valid_for_round_trip():
    # A client that copies the displayed chamber value back into
    # get_hearings_by_congress_and_chamber/get_hearing_details must still
    # find a value ParameterValidator.validate_chamber() accepts.
    from congress_api.core.validators import ParameterValidator

    displayed = _display_chamber("NoChamber")
    assert "nochamber" in displayed.lower()
    result = ParameterValidator.validate_chamber(
        "nochamber", allow_nochamber=True)
    assert result.is_valid


def test_format_hearing_item_shows_joint_not_nochamber():
    hearing = {
        "chamber": "NoChamber",
        "congress": 119,
        "jacketNumber": 61499,
        "updateDate": "2026-08-21T02:06:42Z",
        "url": "https://api.congress.gov/v3/hearing/119/nochamber/61499",
    }
    out = format_hearing_item(hearing)
    assert "Chamber: Joint (nochamber)" in out
    # Assert on the Chamber line specifically -- the fixture's own URL
    # legitimately contains "nochamber" in lowercase, so a bare
    # "NoChamber" absence check would pass even if the raw token leaked.
    chamber_line = next(l for l in out.splitlines() if l.startswith("Chamber:"))
    assert chamber_line == "Chamber: Joint (nochamber)"


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
    chamber_line = next(l for l in out.splitlines() if l.startswith("Chamber:"))
    assert chamber_line == "Chamber: Joint (nochamber)"


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


@pytest.mark.asyncio
async def test_committee_nominations_empty_nominees_list_uses_description():
    # An empty `nominees: []` (present but empty) must behave the same as
    # a missing key -- fall back to `description`, not print "Unknown".
    page = {
        "nominations": [
            {
                "citation": "PN3-1",
                "congress": 119,
                "number": 3,
                "nominees": [],
                "description": "A real nominee description.",
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

    assert "Description: A real nominee description." in out


@pytest.mark.asyncio
async def test_committee_nominations_tolerates_non_dict_nominee_entries():
    page = {
        "nominations": [
            {
                "citation": "PN4-1",
                "congress": 119,
                "number": 4,
                "nominees": ["not-a-dict"],
                "description": "Fallback description.",
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

    assert "Description: Fallback description." in out


@pytest.mark.asyncio
async def test_committee_nominations_whitespace_only_description_omitted():
    page = {
        "nominations": [
            {
                "citation": "PN5-1",
                "congress": 119,
                "number": 5,
                "description": "   ",
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

    assert "Description:" not in out
    assert "Nominees:" not in out
