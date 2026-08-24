"""Issue #55: typed lists and results_count must reflect real data.

Converter-level tests using StructuredText carriers; end-to-end wrapper
coverage lives alongside (mocked API -> populated lists).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from congress_api.utils.structured import StructuredText, structured  # noqa: E402
from congress_api.utils.response_converters import (  # noqa: E402
    convert_members_committees_response,
)


def test_structured_text_is_str():
    s = structured("# Found 2 members:", "member", [{"bioguideId": "X"}])
    assert isinstance(s, str)
    assert s == "# Found 2 members:"
    assert s.item_kind == "member"
    assert len(s.structured_items) == 1
    # non-dict entries are dropped defensively
    assert structured("t", "member", [{"a": 1}, "junk", None]).structured_items == [{"a": 1}]


def _schumer():
    return {
        "bioguideId": "S000148",
        "name": "Schumer, Charles E.",
        "partyName": "Democratic",
        "state": "New York",
        "url": "https://api.congress.gov/v3/member/S000148?format=json",
        "terms": {"item": [
            {"chamber": "House of Representatives", "startYear": 1981, "endYear": 1999},
            {"chamber": "Senate", "startYear": 1999, "endYear": None},
        ]},
    }


def test_members_converter_populates_from_items():
    raw = structured("# Member Search Results\nFound 1 members:\n...", "member", [_schumer()])
    resp = convert_members_committees_response(raw, "search_members")
    assert resp.results_count == 1
    assert len(resp.members) == 1
    m = resp.members[0]
    assert m.bioguide_id == "S000148"
    assert m.chamber == "Senate"            # latest term, not oldest
    assert m.current_member is True
    assert m.party == "Democratic"
    assert resp.summary.startswith("# Member Search Results")
    assert resp.items == [] and resp.item_kind == "member"


def test_committees_converter_populates_from_items():
    raw = structured("Committees matching 'judiciary':\n...", "committee", [{
        "systemCode": "ssju00", "name": "Judiciary Committee",
        "chamber": "Senate", "committeeTypeCode": "Standing",
        "url": "https://api.congress.gov/v3/committee/senate/ssju00?format=json",
    }])
    resp = convert_members_committees_response(raw, "search_committees")
    assert resp.results_count == 1
    assert resp.committees[0].committee_code == "ssju00"
    assert resp.committees[0].chamber == "Senate"


def test_other_kinds_pass_through_in_items():
    bills = [{"type": "HR", "number": "1", "congress": 119, "url": "u"}] * 3
    raw = structured("# Sponsored Legislation\nFound 3 bills:", "bill", bills)
    resp = convert_members_committees_response(raw, "get_member_sponsored_legislation")
    assert resp.results_count == 3
    assert resp.members == [] and resp.committees == []
    assert resp.item_kind == "bill"
    assert len(resp.items) == 3 and resp.items[0]["type"] == "HR"


def test_plain_string_falls_back_to_legacy_count():
    resp = convert_members_committees_response("# X\nFound 20 bills:\n...", "op")
    assert resp.results_count == 20
    assert resp.members == [] and resp.items == []


def test_error_string_stays_zero():
    resp = convert_members_committees_response("No members found matching the criteria.", "op")
    assert resp.results_count == 0 and resp.success is True


def test_empty_items_means_zero_not_regex():
    """An impl that attaches an empty list is authoritative: count 0 even if
    the text contains a number the regex would catch."""
    raw = structured("Found 999 in some unrelated prose", "member", [])
    resp = convert_members_committees_response(raw, "op")
    assert resp.results_count == 0


def test_votes_converter():
    from congress_api.features.buckets.voting_and_nominations import _convert_to_structured_response
    votes = [{"congress": 119, "sessionNumber": 1, "rollCallNumber": 306,
              "legislationType": "HR", "legislationNumber": "5348",
              "voteType": "2/3 Yea-And-Nay", "result": "Passed",
              "startDate": "2025-12-01T18:57:00-05:00",
              "url": "https://api.congress.gov/v3/house-vote/119/1/306"}]
    resp = _convert_to_structured_response(structured("# House Votes...", "house_vote", votes),
                                           "get_house_votes_by_session")
    assert resp.results_count == 1
    v = resp.votes[0]
    assert v.vote_number == 306 and v.legislation == "HR 5348" and v.result == "Passed"
    assert resp.nominations == []


def test_nominations_converter():
    from congress_api.features.buckets.voting_and_nominations import _convert_to_structured_response
    noms = [{"citation": "PN730-2", "congress": 119, "number": 730,
             "organization": "Federal Labor Relations Authority",
             "nominationType": {"isMilitary": False},
             "receivedDate": "2026-01-13",
             "latestAction": {"actionDate": "2026-08-07", "text": "Confirmed by the Senate"},
             "updateDate": "2026-08-08", "url": "u"}]
    resp = _convert_to_structured_response(structured("# Latest Nominations", "nomination", noms),
                                           "get_latest_nominations")
    assert resp.results_count == 1
    n = resp.nominations[0]
    assert n.nomination_number == "730" and n.citation == "PN730-2"
    assert n.is_military is False and "Confirmed" in n.latest_action


def test_committee_intelligence_converter():
    from congress_api.features.buckets.committee_intelligence import _convert_to_structured_response
    reports = [{"citation": "H. Rept. 119-10", "congress": 119, "chamber": "House",
                "type": "HRPT", "number": 10, "updateDate": "2026-08-01", "url": "u"}]
    resp = _convert_to_structured_response(structured("# Latest Committee Reports (1 found)",
                                                      "committee_report", reports),
                                           "get_latest_committee_reports")
    assert resp.results_count == 1
    a = resp.activities[0]
    assert a.activity_type == "report" and a.citation == "H. Rept. 119-10" and a.identifier == "10"


def test_records_hearings_converter():
    from congress_api.features.buckets.records_and_hearings import _convert_to_structured_response
    issues = [{"Congress": "119", "Issue": "134", "Volume": "172", "Session": "2",
               "PublishDate": "2026-08-20", "Id": 27000}]
    resp = _convert_to_structured_response(structured("Search Results - Congressional Record",
                                                      "record", issues),
                                           "search_congressional_record")
    assert resp.results_count == 1
    r = resp.records[0]
    assert r.volume == 172 and r.issue == 134 and r.congress == 119 and r.id == "27000"

    comms = [{"communicationNumber": 1, "communicationType": {"code": "ec"}}]
    resp2 = _convert_to_structured_response(structured("comms", "communication", comms),
                                            "search_house_communications")
    assert resp2.results_count == 1 and resp2.item_kind == "communication"
    assert resp2.items == comms and resp2.hearings == [] and resp2.records == []


def test_research_converter():
    from congress_api.features.buckets.research_and_professional import _convert_to_structured_response
    reports = [{"title": "Iran Sanctions", "publishDate": "2026-01-01", "status": "Active", "url": "u"}]
    resp = _convert_to_structured_response(structured("CRS", "crs_report", reports),
                                           "search_crs_reports")
    assert resp.results_count == 1
    assert resp.research_materials[0].title == "Iran Sanctions"
    assert resp.research_materials[0].type == "CRS Report"


def test_converters_never_raise_on_junk_items():
    from congress_api.features.buckets.voting_and_nominations import _convert_to_structured_response
    resp = _convert_to_structured_response(
        StructuredText("text", "house_vote", [{"rollCallNumber": "not-an-int"}]),
        "get_house_votes_by_congress")
    # junk falls into the except branch -> success=False with the error noted,
    # never an exception propagating out of the converter
    assert resp.success is False
    assert resp.results_count == 0
    assert "Error processing response" in resp.summary
