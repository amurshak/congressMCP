"""
Response converters - Extract structured Pydantic models from raw API responses.

Centralizes the conversion logic previously duplicated across deprecated bucket files.
"""

import json
import logging
import re

from ..models.responses import (
    CommitteeSummary,
    MemberSummary,
    MembersCommitteesResponse,
)

logger = logging.getLogger(__name__)

# Impls across the codebase report their count in prose rather than a
# structured field, since these converters receive pre-formatted markdown
# rather than raw JSON (see _extract_json). Two phrasings are common:
# "Found 191 bills:" (members.py, committees.py, ...) and
# "(10 found)" (committee_reports.py, hearings.py, ...).
_COUNT_PATTERNS = (
    re.compile(r"Found\s+(\d+)", re.IGNORECASE),
    re.compile(r"\((\d+)\s+found\)", re.IGNORECASE),
)


def _extract_result_count(text: str) -> int:
    """Best-effort recovery of a result count from a summary's count phrase.

    Returns 0 if no recognized count phrase is found — a limitation, not a
    regression: results_count was unconditionally 0 before this helper existed.
    """
    for pattern in _COUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return 0


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
