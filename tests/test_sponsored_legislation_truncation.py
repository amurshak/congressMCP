"""
Regression tests for two bugs found in get_member_sponsored_legislation /
get_member_cosponsored_legislation:

1. Display truncation: convert_members_committees_response truncated any
   non-JSON raw_response (i.e. every one of these tools' actual output, since
   they all return formatted markdown, not JSON) to raw_response[:500] + "...",
   regardless of the requested limit. This cut summaries off mid-word/mid-link
   after roughly the first 3 items.
2. Data loss in dedup: sponsored/cosponsored legislation mixes bills and
   amendments; amendments have type=None, number=None (they use
   "amendmentNumber" instead), so deduplicate_results(key_fields=["congress",
   "type", "number"]) collapsed every amendment within the same congress onto
   one colliding key and silently dropped the rest.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch

from congress_api.utils.response_converters import convert_members_committees_response


class FakeContext:
    pass


def _fabricated_markdown(n: int) -> str:
    """Build a markdown summary matching the impls' own "\n".join(result) format."""
    lines = ["# Sponsored Legislation for Member G000000", f"Found {n} bills:"]
    for i in range(n):
        lines.append(f"\n## HR {1000 + i} (Congress 119)")
        lines.append(f"Title of bill number {i}")
        lines.append(f"[View Details](https://api.congress.gov/v3/bill/119/hr/{1000 + i}?format=json)")
    return "\n".join(lines)


_UNTERMINATED_LINK_RE = re.compile(r"\[[^\]]*$")  # an unclosed "[" with no matching "]"


def _assert_no_mid_word_cutoff(text: str):
    assert not text.rstrip().endswith("..."), "response still hard-truncates with a trailing ellipsis"
    assert not _UNTERMINATED_LINK_RE.search(text), "response ends with an unterminated markdown link"
    # Every rendered bill line must be a complete entry: id + "(Congress " + closing paren.
    for line in text.splitlines():
        if line.startswith("## "):
            assert "(Congress" in line and line.rstrip().endswith(")"), f"truncated bill header: {line!r}"


# --- Bug 1: truncation in the response converter ---

def test_converter_preserves_full_summary_past_500_chars():
    """A 20-item markdown summary (~1800 chars) must not be cut to 500 chars."""
    raw = _fabricated_markdown(20)
    assert len(raw) > 500
    result = convert_members_committees_response(raw, "get_member_sponsored_legislation")
    assert result.summary == raw
    for i in range(20):
        assert f"HR {1000 + i}" in result.summary
    _assert_no_mid_word_cutoff(result.summary)


def test_converter_extracts_results_count_from_found_line():
    raw = _fabricated_markdown(20)
    result = convert_members_committees_response(raw, "get_member_sponsored_legislation")
    assert result.results_count == 20


@pytest.mark.parametrize("n", [5, 20, 50])
def test_converter_never_truncates_regardless_of_size(n):
    """Same dataset shape at multiple sizes: no truncation point should ever appear."""
    raw = _fabricated_markdown(n)
    result = convert_members_committees_response(raw, "get_member_sponsored_legislation")
    assert result.results_count == n
    assert len(result.summary) == len(raw)
    _assert_no_mid_word_cutoff(result.summary)


def test_converter_short_response_passthrough_unaffected():
    """Short, genuinely non-JSON responses (e.g. error/empty messages) pass through untouched."""
    raw = "No sponsored legislation found for member G000000."
    result = convert_members_committees_response(raw, "get_member_sponsored_legislation")
    assert result.summary == raw
    assert result.results_count == 0


# --- Bug 2: dedup collapsing amendments ---

@pytest.mark.asyncio
async def test_sponsored_legislation_does_not_collapse_amendments():
    """Amendments (type=None, number=None) in the same congress must not be
    deduped into a single entry — url must disambiguate them."""
    from congress_api.features.members import get_member_sponsored_legislation

    bills = [
        {"congress": 119, "type": "HR", "number": "1", "title": "A bill",
         "url": "https://api.congress.gov/v3/bill/119/hr/1?format=json"},
    ]
    amendments = [
        {"congress": 119, "type": None, "amendmentNumber": str(500 + i),
         "title": None, "url": f"https://api.congress.gov/v3/amendment/119/hamdt/{500 + i}?format=json"}
        for i in range(5)
    ]
    mock_response = {"sponsoredLegislation": bills + amendments}

    with patch("congress_api.features.members.safe_congressional_request",
               new=AsyncMock(return_value=mock_response)):
        result = await get_member_sponsored_legislation(FakeContext(), bioguide_id="G000000", limit=250)

    assert "Found 6 bills:" in result  # 1 bill + 5 amendments, none collapsed
    for i in range(5):
        assert f"hamdt/{500 + i}" in result


@pytest.mark.asyncio
async def test_cosponsored_legislation_does_not_collapse_amendments():
    from congress_api.features.members import get_member_cosponsored_legislation

    amendments = [
        {"congress": 118, "type": None, "amendmentNumber": str(100 + i),
         "title": None, "url": f"https://api.congress.gov/v3/amendment/118/samdt/{100 + i}?format=json"}
        for i in range(4)
    ]
    mock_response = {"cosponsoredLegislation": amendments}

    with patch("congress_api.features.members.safe_congressional_request",
               new=AsyncMock(return_value=mock_response)):
        result = await get_member_cosponsored_legislation(FakeContext(), bioguide_id="G000000", limit=250)

    assert "Found 4 bills:" in result
    for i in range(4):
        assert f"samdt/{100 + i}" in result


@pytest.mark.asyncio
async def test_end_to_end_wrapper_returns_full_untruncated_summary():
    """The full stack (impl -> wrapper -> structured response) must not truncate."""
    from congress_api.features.members_committees_tools import get_member_sponsored_legislation as wrapper

    bills = [
        {"congress": 119, "type": "HR", "number": str(i), "title": f"Bill {i}",
         "url": f"https://api.congress.gov/v3/bill/119/hr/{i}?format=json"}
        for i in range(20)
    ]
    mock_response = {"sponsoredLegislation": bills}

    with patch("congress_api.features.members.safe_congressional_request",
               new=AsyncMock(return_value=mock_response)):
        resp = await wrapper(FakeContext(), bioguide_id="G000000", limit=20)

    assert resp.results_count == 20
    for i in range(20):
        assert f"Bill {i}" in resp.summary
    _assert_no_mid_word_cutoff(resp.summary)
