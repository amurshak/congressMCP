"""GovInfo /search engine for search_bills (govinfo-search-spec section 6).

This module owns the corpus-search side of search_bills: request validation
and query assembly (section 6.1). Response mapping, pagination, and the
failure flow land in later steps of the same work order.

Assembly rules (all measured, section 2b of the spec):

- The caller's ``keywords`` pass through verbatim (outer whitespace
  stripped); the JSON transport escape is the only server-side
  transformation. Blank keywords are rejected client-side -- an empty
  upstream query matches the entire ~8.76M-document corpus with HTTP 200.
- Scoping terms are appended, never merged into the caller's text:
  ``collection:bills`` always, ``congress:{n}`` / ``billtype:{t}`` when set.
  ``congress`` is validated as a positive integer HERE because a non-numeric
  value 500s upstream with the outage-shaped body; ``billtype`` is validated
  against the eight documented values.
- ``sorts: [{score, DESC}]`` is always explicit: the upstream default sort
  is NOT relevance (measured -- package-id-shaped ordering without it).
- ``pageSize = min(3 * limit, 300)``: overfetch absorbs bill-level dedup
  shrinkage (most bills carry 1-4 version records).
- ``resultLevel`` and ``historical`` are omitted: both are measured no-ops
  for the BILLS collection. Nothing is sent that does nothing.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ....core.exceptions import (
    APIErrorResponse,
    CommonErrors,
    CongressionalAPIError,
    ErrorType,
)
from ....core.validators import ParameterValidator

logger = logging.getLogger(__name__)

# The eight documented GovInfo billtype: values (govinfo.gov/help/bills).
BILL_TYPES = ("hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres")

# pageSize policy (spec section 6.3): one upstream fetch per tool call.
OVERFETCH_FACTOR = 3
MAX_PAGE_SIZE = 300

# Q9: every request carries this explicitly; there is no caller-facing sort.
SCORE_SORTS = ({"field": "score", "sortOrder": "DESC"},)


def _reject(error: APIErrorResponse) -> None:
    raise CongressionalAPIError(error)


def validate_keywords(keywords: Optional[str]) -> str:
    """Section 6.1: required; stripped; blank -> invalid_parameters, never
    sent upstream. Otherwise returned verbatim (outer whitespace only)."""
    stripped = str(keywords).strip() if keywords is not None else ""
    if not stripped:
        _reject(APIErrorResponse(
            error_type=ErrorType.VALIDATION,
            message=(
                "keywords is required and must contain at least one "
                "non-whitespace character."
            ),
            suggestions=[
                "Pass plain search words (they are ANDed by GovInfo), "
                "e.g. keywords='radiation exposure compensation'",
                "An empty query would match the entire GovInfo corpus "
                "(~8.76M documents), so it is rejected here and never sent",
            ],
            error_code="invalid_parameters",
            details={"parameter": "keywords",
                     "provided_value": repr(keywords)},
        ))
    return stripped


def validate_congress(congress: Any) -> Optional[int]:
    """Positive-integer guard, client-side: a non-numeric congress: term
    500s upstream wearing the outage body (spec section 2b item 3)."""
    if congress is None:
        return None
    if isinstance(congress, bool):
        _reject(CommonErrors.invalid_congress_number(congress))
    if isinstance(congress, float) and not congress.is_integer():
        # The shared validator would int()-truncate 12.5 to 12 and scope the
        # query to the wrong congress; a fractional value is not an integer.
        _reject(CommonErrors.invalid_congress_number(congress))
    result = ParameterValidator.validate_congress_number(congress)
    if not result.is_valid:
        _reject(CommonErrors.invalid_congress_number(congress))
    return result.sanitized_value


def validate_bill_type(bill_type: Optional[str]) -> Optional[str]:
    """Validated against the eight documented billtype: values."""
    if bill_type is None:
        return None
    result = ParameterValidator.validate_bill_type(bill_type)
    if not result.is_valid or result.sanitized_value not in BILL_TYPES:
        _reject(CommonErrors.invalid_bill_type(bill_type))
    return result.sanitized_value


def clamp_limit(limit: Any) -> "tuple[int, Optional[str]]":
    """Existing clamp discipline: out-of-range clamps with the shared
    validator's advisory wording; non-integers are rejected."""
    result = ParameterValidator.validate_limit_range(limit)
    if not result.is_valid:
        _reject(CommonErrors.invalid_parameter(
            "limit", limit, result.error_message))
    # On a clamp the validator reports valid + sanitized + advisory text.
    return result.sanitized_value, result.error_message


_DATE_SHAPE_RE = None
_TIME_SHAPE_RE = None


def validate_date_bound(name: str, value: Any) -> Optional[str]:
    """Q10: ISO date or ISO datetime; a datetime is TRUNCATED to its date
    before assembly (tolerated upstream, but the canonical date form keeps
    the description honest). Returns the YYYY-MM-DD string, or None.

    Shape is gated by explicit regexes BEFORE fromisoformat: newer
    Pythons' fromisoformat also accepts compact forms (20250101), which
    would make validation depend on the interpreter version -- the 3.10
    floor and 3.14 must reject identically. fromisoformat then supplies
    the range checking the regexes cannot (25:99, 2025-13-01).
    """
    if value is None:
        return None
    import datetime as _dt
    import re
    global _DATE_SHAPE_RE, _TIME_SHAPE_RE
    if _DATE_SHAPE_RE is None:
        _DATE_SHAPE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        _TIME_SHAPE_RE = re.compile(
            r"^\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?$")
    text = str(value).strip()
    date_part, sep, time_part = text.partition("T")
    parsed = None
    if _DATE_SHAPE_RE.match(date_part) and \
            (not sep or _TIME_SHAPE_RE.match(time_part)):
        candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            if sep:
                parsed = _dt.datetime.fromisoformat(candidate).date()
            else:
                parsed = _dt.date.fromisoformat(date_part)
        except ValueError:
            parsed = None
    if parsed is None:
        _reject(CommonErrors.invalid_parameter(
            name, value,
            "Must be an ISO date (YYYY-MM-DD) or ISO datetime "
            "(YYYY-MM-DDTHH:MM:SSZ); datetimes are truncated to the date."))
    return parsed.isoformat()


def validate_date_order(from_date: Optional[str],
                        to_date: Optional[str]) -> None:
    """Q10: ``from <= to`` enforced when both bounds are present (ISO date
    strings compare lexicographically). Equal bounds are the measured
    single-day form -- the range is inclusive both ends."""
    if from_date is not None and to_date is not None and from_date > to_date:
        _reject(CommonErrors.invalid_parameter(
            "fromDateTime", f"{from_date} > {to_date}",
            "fromDateTime must not be after toDateTime."))


def build_query(keywords: str, congress: Optional[int],
                bill_type: Optional[str],
                from_date: Optional[str] = None,
                to_date: Optional[str] = None) -> str:
    """``"{keywords} collection:bills[ congress:{n}][ billtype:{t}]
    [ publishdate:range(from,to)]"``.

    ``keywords`` must already be validated; scoping values must already be
    sanitized (this function assembles, it does not judge). The time bound
    maps to ``publishdate:range`` (Q10, M5-measured): inclusive both ends,
    one-sided forms native -- ``range(from,)`` / ``range(,to)``.
    """
    parts = [keywords, "collection:bills"]
    if congress is not None:
        parts.append(f"congress:{congress}")
    if bill_type is not None:
        parts.append(f"billtype:{bill_type}")
    if from_date is not None or to_date is not None:
        parts.append(
            f"publishdate:range({from_date or ''},{to_date or ''})")
    return " ".join(parts)


def build_search_body(query: str, limit: int,
                      offset_mark: str = "*") -> "dict[str, Any]":
    """The exact upstream request body. ``resultLevel`` and ``historical``
    are deliberately absent (measured no-ops for BILLS, section 2b)."""
    return {
        "query": query,
        "pageSize": min(OVERFETCH_FACTOR * limit, MAX_PAGE_SIZE),
        "offsetMark": offset_mark,
        "sorts": [dict(sort) for sort in SCORE_SORTS],
    }


# ---------------------------------------------------------------------------
# Response mapping (spec section 6.2)
# ---------------------------------------------------------------------------

# Package ids follow BILLS-{congress}{billtype}{docnumber}{billversion}
# (section 2a). The billtype alternation is the eight documented values,
# longest-first so 'hres' can never be read as 'hr' + 'es...', and the
# version code must start with a letter (the shipped bill_text rule), so a
# longer docnumber can never bleed digits into the code.
_PACKAGE_ID_RE = None  # built lazily below to keep the alternation in one place


def _package_id_re():
    global _PACKAGE_ID_RE
    if _PACKAGE_ID_RE is None:
        import re
        from ...bill_text.client import VERSION_CODE_PATTERN
        types = "|".join(sorted(BILL_TYPES, key=len, reverse=True))
        _PACKAGE_ID_RE = re.compile(
            rf"^BILLS-(\d{{1,3}})({types})(\d+)({VERSION_CODE_PATTERN})$",
            re.IGNORECASE,
        )
    return _PACKAGE_ID_RE


def parse_package_id(package_id: Any) -> "Optional[tuple[int, str, int, str]]":
    """(congress, bill_type, number, version) parsed from a BILLS package
    id, or None when the id is not a well-formed BILLS id. The id is the
    authoritative value (carry, don't reconstruct): grouping and the hit's
    identity fields come from here, never re-derived from other fields."""
    match = _package_id_re().match(str(package_id or ""))
    if not match:
        return None
    congress, bill_type, number, version = match.groups()
    return int(congress), bill_type.lower(), int(number), version.lower()


def _version_sort_key(code: str, date: "Optional[str]") -> "tuple[int, str, str]":
    """Precedence-primary ordering, mirroring the shipped bill_text rule:
    the 53-code table ranks first, date (nullable, weaker) breaks ties
    within a tier, the code string makes the order total. Unknown codes get
    UNKNOWN_PRECEDENCE and lose to any known text stage; a missing date
    simply sorts last within its own tier instead of being special-cased."""
    from ...bill_text.client import UNKNOWN_PRECEDENCE, VERSION_PRECEDENCE
    return (VERSION_PRECEDENCE.get(code, UNKNOWN_PRECEDENCE), date or "", code)


def group_records(records: "list[dict[str, Any]]") \
        -> "tuple[list[dict[str, Any]], list[Any]]":
    """Bill-level dedup of upstream version-package records, in rank order.

    Returns (bills, skipped_package_ids). Bills are ordered by the rank of
    each bill's FIRST record (first occurrence wins -- the property A5's
    monotonicity rests on). Each bill dict fronts the most authoritative
    version among ITS fetched records and carries every fetched version in
    ``matched_versions``, precedence-ordered. Records whose packageId does
    not parse as a BILLS id are skipped from grouping (and reported) --
    they cannot be attributed to a bill without reconstructing identity
    from weaker fields, which the carry-don't-reconstruct rule forbids.
    """
    order: "list[tuple[int, str, int]]" = []
    by_bill: "dict[tuple[int, str, int], list[tuple[str, dict[str, Any]]]]" = {}
    skipped: "list[Any]" = []
    for record in records:
        if not isinstance(record, dict):
            skipped.append(record)
            continue
        parsed = parse_package_id(record.get("packageId"))
        if parsed is None:
            skipped.append(record.get("packageId"))
            continue
        congress, bill_type, number, version = parsed
        key = (congress, bill_type, number)
        if key not in by_bill:
            by_bill[key] = []
            order.append(key)
        by_bill[key].append((version, record))
    if skipped:
        logger.warning(
            "govinfo /search returned %d record(s) without a parseable "
            "BILLS packageId; they were skipped from bill grouping: %r",
            len(skipped), skipped[:5])

    bills = []
    for key in order:
        congress, bill_type, number = key
        versioned = sorted(
            by_bill[key],
            key=lambda pair: _version_sort_key(
                pair[0], str(pair[1].get("dateIssued") or "") or None),
            reverse=True,
        )
        front_version, front_record = versioned[0]
        seen = set()
        matched_versions = []
        for version, _ in versioned:
            if version not in seen:
                seen.add(version)
                matched_versions.append(version)
        bills.append({
            "bill": f"{bill_type.upper()} {number}",
            "congress": congress,
            "bill_type": bill_type,
            "bill_number": number,
            "title": front_record.get("title"),
            "package_id": front_record.get("packageId"),
            "version": front_version,
            "date_issued": front_record.get("dateIssued"),
            "matched_versions": matched_versions,
        })
    return bills, skipped


def zero_diagnostics(upstream_query: str, congress: Optional[int],
                     bill_type: Optional[str]) -> "dict[str, Any]":
    """Corpus-level readable zero (the search_bill_text query_diagnostics
    discipline applied at corpus level): says what corpus was searched,
    with which upstream query, and what to try -- so 'no match in the
    corpus' cannot be misread as noise or as an error."""
    return {
        "corpus": ("full text of congressional bills, all versions "
                   "(GovInfo BILLS collection)"),
        "upstream_query": upstream_query,
        "scope": {"congress": congress, "bill_type": bill_type},
        "note": (
            "0 version packages matched this query in the corpus. Words "
            "are ANDed. Quoted phrases are unreliable against bill titles "
            "-- retry with plain unquoted words, or use "
            'title:"..." / shorttitle:"..." for an exact title.'
        ),
    }


def build_corpus_response(
    bills: "list[dict[str, Any]]",
    total_version_matches: int,
    upstream_query: str,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    next_page_token: Optional[str] = None,
    request_note: Optional[str] = None,
) -> "dict[str, Any]":
    """The corpus-path response shape (section 6.2).

    results_count counts the returned list (#65), never the upstream
    total; total_version_matches is the upstream count under its honest
    name -- it counts version packages and can exceed the number of
    distinct bills. search_source is the machine-readable origin marker.
    """
    response: "dict[str, Any]" = {
        "search_source": "govinfo_fulltext",
        "results_count": len(bills),
        "total_version_matches": total_version_matches,
        "results": bills,
        "next_page_token": next_page_token,
    }
    if request_note:
        response["request_note"] = request_note
    if not bills:
        response["query_diagnostics"] = zero_diagnostics(
            upstream_query, congress, bill_type)
    return response


# ---------------------------------------------------------------------------
# Pagination (spec section 6.3)
# ---------------------------------------------------------------------------
#
# The token is server-encoded and opaque. Its spec-named components are
# offsetMark (the upstream cursor to fetch next) and records_consumed (the
# exhaustion numerator against upstream count). It carries one additional
# implementation component, ``skip``: the intra-page resume point. Reason,
# recorded for the completion report: whole-page consumption plus the
# ``limit`` output cap would LOSE bills whenever a page dedups to more
# than ``limit`` bills (single-version bills make this the common case --
# a 3x-limit page of one-version bills dedups to 3x limit), and A6 demands
# enumeration without loss. Cursors are measured stable and replayable
# (section 2b), so a partially-consumed page is resumed by replaying the
# SAME cursor and skipping the records already consumed. skip=0 whenever a
# page was fully consumed, in which case the token is exactly the spec's
# two-field shape. The one tolerated duplication class (a bill whose
# version records straddle a boundary reappears, same identity) covers the
# resume boundary the same way it covers the upstream page boundary.

_TOKEN_KEYS = {"offsetMark", "records_consumed", "skip"}


def default_page_state() -> "dict[str, Any]":
    return {"offsetMark": "*", "records_consumed": 0, "skip": 0}


def encode_page_token(offset_mark: str, records_consumed: int,
                      skip: int = 0) -> str:
    import base64
    import json
    payload: "dict[str, Any]" = {
        "offsetMark": offset_mark,
        "records_consumed": records_consumed,
    }
    if skip:
        payload["skip"] = skip
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_page_token(token: Any) -> "Optional[dict[str, Any]]":
    """Decode and validate a page token; None on any malformation. (An
    undecodable token cannot even produce an offsetMark to send upstream,
    so the caller answers it directly instead of burning a doomed call.)"""
    import base64
    import binascii
    import json
    if not isinstance(token, str) or not token:
        return None
    padded = token + "=" * (-len(token) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(payload, dict) or not set(payload) <= _TOKEN_KEYS:
        return None
    offset_mark = payload.get("offsetMark")
    records_consumed = payload.get("records_consumed")
    skip = payload.get("skip", 0)
    if not isinstance(offset_mark, str) or not offset_mark:
        return None
    if not isinstance(records_consumed, int) or isinstance(records_consumed, bool) \
            or records_consumed < 0:
        return None
    if not isinstance(skip, int) or isinstance(skip, bool) or skip < 0:
        return None
    return {"offsetMark": offset_mark, "records_consumed": records_consumed,
            "skip": skip}


def paginate_records(records: "list[dict[str, Any]]", skip: int,
                     limit: int) -> "tuple[list[dict[str, Any]], int, bool]":
    """Consume one fetched page from ``skip``, selecting at most ``limit``
    bills in rank order.

    Returns (bills, consumed, page_exhausted). ``consumed`` counts the
    effective records actually consumed this call: everything up to (not
    including) the first record of the (limit+1)-th distinct bill, so no
    record is ever silently dropped -- unconsumed records are resumed by
    replaying this page. matched_versions comes from the consumed slice
    only, so a full walk partitions the record stream exactly (the A6
    set property across pages); a bill straddling the boundary reappears
    on the next call with its remaining versions -- the one tolerated,
    disclosed duplication class, same bill identity both times.
    """
    effective = records[skip:]
    boundary = len(effective)
    keys: "set[tuple[int, str, int]]" = set()
    for index, record in enumerate(effective):
        parsed = parse_package_id(record.get("packageId")) \
            if isinstance(record, dict) else None
        if parsed is None:
            continue
        key = parsed[:3]
        if key not in keys:
            if len(keys) == limit:
                boundary = index
                break
            keys.add(key)
    bills, _ = group_records(effective[:boundary])
    return bills, boundary, boundary == len(effective)


def compute_next_token(
    count: int,
    prior_consumed: int,
    prior_skip: int,
    consumed_now: int,
    page_exhausted: bool,
    request_cursor: str,
    response_cursor: Optional[str],
) -> "tuple[Optional[str], int]":
    """(next_page_token, total_records_consumed).

    Exhaustion is COMPUTED -- records_consumed >= count -- never inferred
    from cursor nullness: an exhausted page still returns a non-null
    offsetMark upstream (measured, section 2b); only that computation may
    null the token.
    """
    total = prior_consumed + consumed_now
    if total >= count:
        return None, total
    if not page_exhausted:
        # Resume the same (measured-replayable) page past what was consumed.
        return encode_page_token(request_cursor, total,
                                 prior_skip + consumed_now), total
    if response_cursor is None:
        # Defensive: upstream owes a cursor when records remain; without one
        # the walk cannot honestly continue. Log loudly rather than loop.
        logger.warning(
            "govinfo /search returned no offsetMark with %d of %d records "
            "consumed; ending pagination early.", total, count)
        return None, total
    return encode_page_token(str(response_cursor), total, 0), total


# ---------------------------------------------------------------------------
# Failure flow (spec section 6.4)
# ---------------------------------------------------------------------------

# Trigger classes that put on the recency-window fallback. Keyless and
# key-rejected are NOT here: those are operator-actionable configuration
# states, and a fallback would bury the defect (F31).
FALLBACK_TRIGGERS = (
    "govinfo_search_error",     # 500 family, canary also failed
    "govinfo_unreachable",      # transport error / timeout
    "govinfo_rate_limited",     # 429 after the client's own backoff
)


def canary_body() -> "dict[str, Any]":
    """The 500-disambiguation canary: one server-built constant query,
    known valid, ZERO caller input (a bare fielded term is measured to
    return 200 over the collection). A malformed request and an outage
    both wear the same generic 500 upstream (measured); only a request
    containing none of the caller's bytes can tell them apart."""
    return {
        "query": "collection:bills",
        "pageSize": 1,
        "offsetMark": "*",
        "sorts": [dict(sort) for sort in SCORE_SORTS],
    }


def keyless_error() -> APIErrorResponse:
    """F31: a keyless server answers api_key_missing -- never a fallback
    (the operator must act) and never govinfo_key_rejected (there is no
    key to have been rejected)."""
    return APIErrorResponse(
        error_type=ErrorType.AUTHENTICATION,
        message=(
            "No api.data.gov key is configured; the GovInfo corpus search "
            "cannot run."
        ),
        suggestions=[
            "Set CONGRESS_API_KEY in the server's environment "
            "(api.congress.gov and api.govinfo.gov share one api.data.gov "
            "key), or GOVINFO_API_KEY to use a separate GovInfo key",
        ],
        error_code="api_key_missing",
        details=None,
    )


def key_rejected_error(status_code: int) -> APIErrorResponse:
    """401/403 with a key configured. Not one of the five 6.4 rows:
    operator-actionable, so no fallback -- it would bury a config defect."""
    return APIErrorResponse(
        error_type=ErrorType.AUTHENTICATION,
        message="The configured api.data.gov key was rejected by GovInfo.",
        suggestions=[
            "api.congress.gov and api.govinfo.gov normally share one "
            "api.data.gov key; set GOVINFO_API_KEY to override with a "
            "separate GovInfo key",
        ],
        error_code="govinfo_key_rejected",
        details={"status_code": status_code},
    )


def query_error(status_code: int, page_token_supplied: bool) -> APIErrorResponse:
    """The canary-succeeded branch of the 500 row: the service accepted a
    known-good query, so the caller's input is implicated -- no fallback."""
    remediation = [
        "Simplify keywords to plain words without operators or quotes "
        "(words are ANDed; quoted phrases are unreliable against titles)",
    ]
    details: "dict[str, Any]" = {
        "status_code": status_code,
        "canary": "succeeded",
    }
    if page_token_supplied:
        remediation.append(
            "The supplied page_token is the other suspect -- it may be "
            "malformed or expired; re-run the query without page_token and "
            "walk next_page_token from the start"
        )
        details["page_token_supplied"] = True
    return APIErrorResponse(
        error_type=ErrorType.VALIDATION,
        message=(
            f"GovInfo /search rejected this request (HTTP {status_code}) "
            "while accepting a known-good canary query, so the request "
            "input is implicated rather than the service."
        ),
        suggestions=remediation,
        error_code="govinfo_query_error",
        details=details,
    )
