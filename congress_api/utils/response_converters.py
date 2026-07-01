"""
Response converters - Extract structured Pydantic models from raw API responses.

Centralizes the conversion logic previously duplicated across deprecated bucket files.
"""

import json
import logging
import re

from ..models.responses import (
    AmendmentSummary,
    BillSummary,
    CommitteeSummary,
    LegislationHubResponse,
    MemberSummary,
    MembersCommitteesResponse,
)

logger = logging.getLogger(__name__)

_COUNT_LINE_RE = re.compile(r"Found\s+(\d+)", re.IGNORECASE)


def _extract_result_count(text: str) -> int:
    """Best-effort recovery of a result count from a 'Found N ...' summary line.

    The impls report their count in prose (e.g. "Found 191 bills:"), not as a
    structured field, since these converters receive pre-formatted markdown
    rather than raw JSON (see _extract_json). Returns 0 if no such line exists.
    """
    match = _COUNT_LINE_RE.search(text)
    return int(match.group(1)) if match else 0


def _extract_json(raw_response: str) -> dict | None:
    """Extract the outermost JSON object from a raw string response.

    Uses a brace-counting approach instead of a greedy regex so that
    trailing text after the closing brace doesn't corrupt the parse.
    Returns None if no valid JSON object is found.
    """
    start = raw_response.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(raw_response)):
        ch = raw_response[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw_response[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def convert_legislation_response(raw_response: str, operation: str) -> LegislationHubResponse:
    """Convert raw string response to structured LegislationHubResponse."""
    try:
        if isinstance(raw_response, str):
            data = _extract_json(raw_response)
            if data is None:
                return LegislationHubResponse(
                    success=True,
                    operation=operation,
                    results_count=0,
                    bills=[],
                    amendments=[],
                    summary=raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    total_available=None,
                    next_steps=[],
                )
        else:
            data = raw_response

        bills = []
        amendments = []

        if isinstance(data, dict):
            if "bills" in data:
                for bill_data in data.get("bills", []):
                    if isinstance(bill_data, dict):
                        bills.append(
                            BillSummary(
                                congress=bill_data.get("congress", 0),
                                bill_type=bill_data.get("type", ""),
                                bill_number=bill_data.get("number", 0),
                                title=bill_data.get("title", ""),
                                sponsor=bill_data.get("sponsor"),
                                introduced_date=bill_data.get("introducedDate"),
                                latest_action=bill_data.get("latestAction"),
                                url=bill_data.get("url"),
                            )
                        )

            if "amendments" in data:
                for amend_data in data.get("amendments", []):
                    if isinstance(amend_data, dict):
                        amendments.append(
                            AmendmentSummary(
                                congress=amend_data.get("congress", 0),
                                amendment_type=amend_data.get("type", ""),
                                amendment_number=amend_data.get("number", 0),
                                purpose=amend_data.get("purpose"),
                                sponsor=amend_data.get("sponsor"),
                                submitted_date=amend_data.get("submittedDate"),
                                bill_number=amend_data.get("billNumber"),
                                url=amend_data.get("url"),
                            )
                        )

        results_count = len(bills) + len(amendments)

        return LegislationHubResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            bills=bills,
            amendments=amendments,
            summary=f"Found {len(bills)} bills and {len(amendments)} amendments",
            total_available=None,
            next_steps=[],
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return LegislationHubResponse(
            success=False,
            operation=operation,
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error processing response: {str(e)}",
            total_available=None,
            next_steps=[],
        )


def convert_members_committees_response(raw_response: str, operation: str) -> MembersCommitteesResponse:
    """Convert raw string response to structured MembersCommitteesResponse."""
    try:
        if isinstance(raw_response, str):
            data = _extract_json(raw_response)
            if data is None:
                # All members/committees impls return pre-formatted human-readable
                # markdown, not JSON, so this "no JSON found" branch is the NORMAL
                # path for every one of these tools, not a fallback for malformed
                # data. It must therefore preserve the full response: a prior bug
                # here truncated it to raw_response[:500], which for any member or
                # committee with more than a handful of results cut the summary off
                # mid-word (and always reported results_count=0 regardless of how
                # much data was actually returned).
                return MembersCommitteesResponse(
                    success=True,
                    operation=operation,
                    results_count=_extract_result_count(raw_response),
                    members=[],
                    committees=[],
                    summary=raw_response,
                    context=f"Performed {operation} operation",
                )
        else:
            data = raw_response

        members = []
        committees = []

        if isinstance(data, dict):
            if "members" in data:
                for member_data in data.get("members", []):
                    if isinstance(member_data, dict):
                        members.append(
                            MemberSummary(
                                bioguide_id=member_data.get("bioguideId", ""),
                                name=member_data.get("name", ""),
                                party=member_data.get("partyName"),
                                state=member_data.get("state"),
                                district=member_data.get("district"),
                                chamber=member_data.get("chamber", ""),
                                current_member=member_data.get("currentMember", False),
                                url=member_data.get("url"),
                            )
                        )

            if "committees" in data:
                for committee_data in data.get("committees", []):
                    if isinstance(committee_data, dict):
                        committees.append(
                            CommitteeSummary(
                                committee_code=committee_data.get("systemCode", ""),
                                name=committee_data.get("name", ""),
                                chamber=committee_data.get("chamber", ""),
                                committee_type=committee_data.get("committeeTypeCode", ""),
                                url=committee_data.get("url"),
                            )
                        )

        results_count = len(members) + len(committees)

        return MembersCommitteesResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            members=members,
            committees=committees,
            summary=f"Found {len(members)} members and {len(committees)} committees",
            context=f"Performed {operation} operation",
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation=operation,
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error processing response: {str(e)}",
            context=f"Failed {operation} operation",
        )
