"""
Response converters - build structured Pydantic responses from impl output.

Impls return pre-formatted markdown. When they attach the real item dicts
via congress_api.utils.structured.structured(), the converter here maps
them into the typed lists and derives results_count with len(). Plain
strings fall back to the legacy count-phrase regex with empty lists
(accurate for error/empty messages; a lie-free zero otherwise only when
the impl genuinely returned nothing).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..core.exceptions import error_envelope
from ..models.responses import (
    CommitteeSummary,
    ErrorInfo,
    MemberSummary,
    MembersCommitteesResponse,
)

logger = logging.getLogger(__name__)

# Legacy fallback only (plain-str responses): impls report their count in
# prose. "Found 191 bills:" (members.py, committees.py, ...) and
# "(10 found)" (committee_reports.py, ...).
_COUNT_PATTERNS = (
    re.compile(r"Found\s+(\d+)", re.IGNORECASE),
    re.compile(r"\((\d+)\s+found\)", re.IGNORECASE),
)


def _extract_result_count(text: str) -> int:
    """Best-effort count recovery from a plain string's count phrase."""
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


def structured_items_of(raw_response: str) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]]]:
    """Return (item_kind, items) if the impl attached real data, else (None, None)."""
    items = getattr(raw_response, "structured_items", None)
    kind = getattr(raw_response, "item_kind", None)
    if isinstance(items, list):
        return kind, items
    return None, None


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _latest_term(member: Dict[str, Any]) -> Dict[str, Any]:
    """Most recent term dict from a member record (greatest startYear)."""
    terms = member.get("terms")
    if isinstance(terms, dict):
        terms = terms.get("item")
    if not isinstance(terms, list):
        return {}
    dict_terms = [t for t in terms if isinstance(t, dict)]
    if not dict_terms:
        return {}

    def _key(t):
        start = _int_or_none(t.get("startYear"))
        open_ended = 1 if t.get("endYear") in (None, "", "Present") else 0
        return (start if start is not None else -1, open_ended)

    return max(dict_terms, key=_key)


def _member_name(member: Dict[str, Any]) -> str:
    name = member.get("name")
    if isinstance(name, str) and name:
        return name
    if isinstance(name, dict):
        first, last = name.get("firstName", ""), name.get("lastName", "")
        if first or last:
            return f"{last}, {first}".strip(", ")
    return member.get("invertedOrderName") or member.get("directOrderName") \
        or member.get("bioguideId", "")


def map_member(member: Dict[str, Any]) -> MemberSummary:
    """Map a Congress.gov member list dict to MemberSummary."""
    party = member.get("partyName") or member.get("party")
    if not party:
        history = member.get("partyHistory")
        if isinstance(history, list) and history and isinstance(history[0], dict):
            party = history[0].get("partyName") or history[0].get("partyAbbreviation")
    term = _latest_term(member)
    current = None
    if term:
        current = term.get("endYear") in (None, "", "Present")
    district = member.get("district")
    return MemberSummary(
        bioguide_id=member.get("bioguideId", ""),
        name=_member_name(member),
        party=party,
        state=member.get("state"),
        district=str(district) if district is not None else None,
        chamber=term.get("chamber") or member.get("chamber"),
        current_member=current,
        url=member.get("url"),
    )


def map_committee(committee: Dict[str, Any]) -> CommitteeSummary:
    """Map a Congress.gov committee list dict to CommitteeSummary."""
    return CommitteeSummary(
        committee_code=committee.get("systemCode", ""),
        name=committee.get("name", ""),
        chamber=committee.get("chamber"),
        committee_type=committee.get("committeeTypeCode") or committee.get("type"),
        url=committee.get("url"),
    )


def convert_members_committees_response(raw_response: str, operation: str) -> MembersCommitteesResponse:
    """Convert impl output to a structured MembersCommitteesResponse.

    The summary is ALWAYS the impl's full markdown (a prior bug truncated
    it to 500 chars). When the impl attached real items, the typed lists
    are populated from them and results_count == len(items); member/
    committee dicts map to their models, anything else (bills, reports,
    communications, nominations) passes through in `items` labeled by
    `item_kind`.
    """
    try:
        typed_error = getattr(raw_response, "error_response", None)
        if typed_error is not None:
            payload = error_envelope(typed_error)["error"]
            return MembersCommitteesResponse(
                success=False,
                operation=operation,
                error=ErrorInfo(**payload),
                results_count=0,
                summary=f"{payload['code']}: {payload['message']}",
                context=f"Failed {operation} operation",
            )

        kind, items = structured_items_of(raw_response)
        if items is not None:
            members: List[MemberSummary] = []
            committees: List[CommitteeSummary] = []
            generic: List[Dict[str, Any]] = []
            if kind == "member":
                members = [map_member(i) for i in items]
            elif kind == "committee":
                committees = [map_committee(i) for i in items]
            else:
                generic = items
            return MembersCommitteesResponse(
                success=True,
                operation=operation,
                results_count=len(items),
                members=members,
                committees=committees,
                items=generic,
                item_kind=kind,
                summary=str(raw_response),
                context=f"Performed {operation} operation",
            )

        # Legacy path: plain markdown with no attached data (error and
        # empty-result messages, and impls not yet converted). Preserve the
        # full text; recover a count from the count phrase if present.
        return MembersCommitteesResponse(
            success=True,
            operation=operation,
            results_count=_extract_result_count(raw_response),
            members=[],
            committees=[],
            summary=str(raw_response),
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
