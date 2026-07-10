"""
Regression tests for two bugs found while auditing the response-truncation fix
for total blast radius, in the four bucket tools (committee_intelligence,
records_and_hearings, research_and_professional, voting_and_nominations):

1. Double conversion: each top-level @mcp.tool function called
   route_X_operation(...) (which ALREADY returns a fully-converted structured
   Response object — it calls _convert_to_structured_response internally) and
   then called _convert_to_structured_response AGAIN on that object. Since the
   object is no longer a str, isinstance(raw_response, str) is False, the
   converter falls into its "else: data = raw_response" branch, data is a
   Pydantic model rather than a dict, so results/activities/etc. are always
   empty and results_count is always 0 — regardless of how much real data the
   API actually returned. This was total data loss on every call through the
   real MCP tool surface (not just truncation).

2. Duplicate 500-char truncation: each of these 4 files had its own local copy
   of the same raw_response[:500] + "..." bug already fixed in
   response_converters.py's convert_members_committees_response. Because bug 1
   always intercepted the *outer* call, this *inner* truncation had been masked
   in practice (the outer bug discarded the truncated-but-real data anyway) —
   fixing bug 1 alone would have surfaced bug 2 as visibly cut-off summaries.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch


class FakeContext:
    pass


def _fabricated_markdown(n: int, header: str) -> str:
    lines = [header]
    for i in range(n):
        lines.append(f"\nItem {i}: some real content that must survive the round trip")
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_committee_intelligence_does_not_double_convert():
    from congress_api.features.buckets import committee_intelligence as mod

    raw = _fabricated_markdown(5, "# Committee Reports (5 found)")
    with patch("congress_api.features.committee_reports.get_latest_committee_reports",
               new=AsyncMock(return_value=raw)):
        resp = await mod.committee_intelligence(FakeContext(), operation="get_latest_committee_reports")

    assert resp.results_count == 5, "double-conversion bug: results_count always 0"
    assert "Item 4" in resp.summary, "double-conversion bug: data discarded"
    assert not resp.summary.rstrip().endswith("..."), "duplicate 500-char truncation not fixed"


@pytest.mark.asyncio
async def test_records_and_hearings_does_not_double_convert():
    from congress_api.features.buckets import records_and_hearings as mod

    raw = _fabricated_markdown(5, "Found 5 hearings")
    with patch("congress_api.features.hearings.search_hearings", new=AsyncMock(return_value=raw)):
        resp = await mod.records_and_hearings(FakeContext(), operation="search_hearings", congress=119)

    assert resp.results_count == 5
    assert "Item 4" in resp.summary
    assert not resp.summary.rstrip().endswith("...")


@pytest.mark.asyncio
async def test_research_and_professional_does_not_double_convert():
    from congress_api.features.buckets import research_and_professional as mod

    raw = _fabricated_markdown(5, "Found 5 reports")
    with patch("congress_api.features.crs_reports.search_crs_reports", new=AsyncMock(return_value=raw)):
        resp = await mod.research_and_professional(FakeContext(), operation="search_crs_reports", keywords="x")

    assert resp.results_count == 5
    assert "Item 4" in resp.summary
    assert not resp.summary.rstrip().endswith("...")


@pytest.mark.asyncio
async def test_voting_and_nominations_does_not_double_convert():
    from congress_api.features.buckets import voting_and_nominations as mod

    raw = _fabricated_markdown(5, "# Latest Nominations (5 found)")
    with patch("congress_api.features.nominations.get_latest_nominations", new=AsyncMock(return_value=raw)):
        resp = await mod.voting_and_nominations(FakeContext(), operation="get_latest_nominations")

    assert resp.results_count == 5
    assert "Item 4" in resp.summary
    assert not resp.summary.rstrip().endswith("...")


# --- shared count-extraction helper ---

def test_extract_result_count_handles_found_n_prefix():
    from congress_api.utils.response_converters import _extract_result_count
    assert _extract_result_count("Found 191 bills:") == 191


def test_extract_result_count_handles_n_found_suffix():
    from congress_api.utils.response_converters import _extract_result_count
    assert _extract_result_count("# Latest Committee Reports (10 found)\n\n...") == 10


def test_extract_result_count_returns_zero_when_absent():
    from congress_api.utils.response_converters import _extract_result_count
    assert _extract_result_count("Search Results - Hearings:\n\nChamber: House") == 0


# --- return-type annotation regression ---
#
# The double-conversion fix above made each top-level @mcp.tool function return
# route_X_operation's result directly (already a Pydantic Response object), but
# the function signatures were still declared "-> str" from the old
# _convert_to_structured_response(...) call. FastMCP validates a tool's actual
# return value against its declared return type to build/check the output
# schema — a plain Python-level test (calling the function directly and reading
# .summary/.results_count off the result) does NOT exercise that validation, so
# this regression shipped once already and only surfaced through a real MCP
# tool call. This test catches it statically, without needing a live server.

import inspect


@pytest.mark.parametrize("tool_name,module_path,expected_type_name", [
    ("committee_intelligence", "congress_api.features.buckets.committee_intelligence", "CommitteeIntelligenceResponse"),
    ("records_and_hearings", "congress_api.features.buckets.records_and_hearings", "RecordsHearingsResponse"),
    ("research_and_professional", "congress_api.features.buckets.research_and_professional", "ResearchProfessionalResponse"),
    ("voting_and_nominations", "congress_api.features.buckets.voting_and_nominations", "VotingNominationsResponse"),
])
def test_bucket_tool_return_annotation_matches_actual_return_type(tool_name, module_path, expected_type_name):
    import importlib
    mod = importlib.import_module(module_path)
    tool_fn = getattr(mod, tool_name)
    annotation = inspect.signature(tool_fn).return_annotation
    assert annotation is not str, (
        f"{tool_name} declares '-> str' but returns route_{tool_name}_operation's "
        f"already-structured Pydantic response — FastMCP will reject the real "
        f"output as invalid (str expected, Pydantic model given)."
    )
    assert getattr(annotation, "__name__", None) == expected_type_name, (
        f"{tool_name}'s return annotation is {annotation!r}, expected {expected_type_name}"
    )
