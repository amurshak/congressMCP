"""
Bills API - Clean, API-faithful public functions.

This module provides the public API for bills operations that map directly
to Congress.gov endpoints while maintaining enhancement capabilities.
"""

from typing import Any, Optional
import json
import logging
import time

import httpx
from mcp.server.mcpserver import Context

# Import our modular components
from . import govinfo_search
from .helpers import fetch_bill_data, build_bill_endpoint, validate_api_parameters
from .processors import BillsDataProcessor
from .formatters import BillsFormatter

# The corpus search reuses the keyed, backoff-wrapped GovInfo transport,
# and the trace mechanism binds this tool (govinfo-search-spec §2 addendum).
from ...bill_text import trace
from ...bill_text.client import govinfo_api_key, govinfo_search_post

# Import existing reliability framework
from ....core.validators import ParameterValidator
from ....core.exceptions import (
    APIErrorResponse,
    CommonErrors,
    CongressionalAPIError,
    ErrorType,
    format_error_response,
)

# Set up logger
logger = logging.getLogger(__name__)


# --- Core API-Faithful Functions ---

async def get_bills(
    ctx: Context,
    format: str = "json",
    offset: Optional[int] = None,
    limit: int = 20,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    sort: str = "updateDate+desc",
    congress: Optional[int] = None,
    bill_type: Optional[str] = None
) -> str:
    """
    Get bills using the core /bill endpoint - the MISSING foundation function.
    Maps directly to Congress.gov GET /bill API with zero abstraction.

    This function provides access to the core Congress.gov /bill endpoint
    that was missing from the original implementation.

    Args:
        ctx: Context for API requests
        format: Response format ('json' or 'xml')
        offset: Starting record (0-based pagination)
        limit: Maximum number of results (max 250)
        fromDateTime: Start date filter (YYYY-MM-DDTHH:MM:SSZ)
        toDateTime: End date filter (YYYY-MM-DDTHH:MM:SSZ)
        sort: Sort order ('updateDate+asc' or 'updateDate+desc')
        congress: Optional congress filter (changes endpoint to /bill/{congress})
        bill_type: Optional bill type filter (changes endpoint to /bill/{congress}/{billType})

    Returns:
        Formatted bills list or error message
    """
    try:
        # Validate API parameters
        api_validation = validate_api_parameters(
            format=format,
            offset=offset,
            limit=limit,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime,
            sort=sort
        )

        if not api_validation["valid"]:
            return format_error_response(CommonErrors.invalid_parameter(
                "api_params", api_validation, api_validation["error"]
            ))

        # Validate congress parameter if provided
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(CommonErrors.invalid_congress_number(congress))

        # Validate bill_type parameter if provided
        if bill_type is not None:
            bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_type_validation.is_valid:
                return format_error_response(CommonErrors.invalid_bill_type(bill_type))
            bill_type = bill_type_validation.sanitized_value

        # Use validated parameters
        api_params = api_validation["params"]

        # Core API call - direct Congress.gov endpoint mapping
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            **api_params
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Standard response formatting
        return BillsFormatter.format_bills_list(response, "Bills")

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bills")
        return format_error_response(error_response)


async def search_bills(
    ctx: Context,
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    limit: int = 10,
    page_token: Optional[str] = None,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None
) -> str:
    """
    Full-text search over the GovInfo BILLS corpus -- every version of
    every congressional bill -- ranked by relevance (govinfo-search-spec
    section 6). Replaces the D17/D18 recency-window filter: the query runs
    against the corpus, not a page of recently-updated bills.

    Args:
        ctx: Context for API requests
        keywords: Required search text, passed to GovInfo verbatim. Words
            are ANDed; do not quote bill names (title:"..."/shorttitle:"..."
            are the exact-title forms); OR/NOT and field operators pass
            through. Blank keywords are rejected.
        congress: Optional congress scope (positive integer, validated here)
        bill_type: Optional bill type scope (hr, s, hjres, sjres, hconres,
            sconres, hres, sres)
        limit: Output cap in BILLS (clamps with advisory wording)
        page_token: Opaque cursor from a previous response's
            next_page_token, passed back verbatim
        fromDateTime/toDateTime: Optional inclusive bounds on the VERSION
            PUBLICATION DATE (Q10) -- ISO date or datetime, datetimes
            truncated to the date; either side may be given alone. In
            fallback mode the same bounds filter updateDate instead, and
            the response says so.

    Returns:
        JSON envelope (str): search_source, results (bill hits fronting the
        most authoritative matched version, with matched_versions),
        results_count, total_version_matches, next_page_token, and
        corpus-level query_diagnostics on a zero. Errors return the
        section-9 error envelope.
    """
    started = time.perf_counter()
    # §2 trace addendum: which 6.4 row fired, attributable from the trace
    # alone. The key never appears here (the query carries no secret by
    # construction; trace.write redacts known key values regardless).
    flow = {"upstream_query": None, "outcome": None, "canary": None,
            "fallback_trigger": None}
    caller_args = {"keywords": keywords, "congress": congress,
                   "bill_type": bill_type, "limit": limit,
                   "page_token": page_token, "fromDateTime": fromDateTime,
                   "toDateTime": toDateTime}

    def _traced(result: str) -> str:
        if trace.enabled():
            trace.write(
                "search_bills", caller_args, result,
                round((time.perf_counter() - started) * 1000, 1), flow=flow)
        return result

    try:
        validated_keywords = govinfo_search.validate_keywords(keywords)
        congress_value = govinfo_search.validate_congress(congress)
        bill_type_value = govinfo_search.validate_bill_type(bill_type)
        limit_value, request_note = govinfo_search.clamp_limit(limit)
        from_date = govinfo_search.validate_date_bound(
            "fromDateTime", fromDateTime)
        to_date = govinfo_search.validate_date_bound(
            "toDateTime", toDateTime)
        govinfo_search.validate_date_order(from_date, to_date)

        state = govinfo_search.default_page_state()
        if page_token is not None:
            decoded = govinfo_search.decode_page_token(page_token)
            if decoded is None:
                # An undecodable token cannot produce an offsetMark to send,
                # so it is answered directly -- same code the canary path
                # gives a malformed-but-decodable token (section 6.4).
                error = APIErrorResponse(
                    error_type=ErrorType.VALIDATION,
                    message=(
                        "page_token could not be decoded. Tokens are opaque "
                        "and must be passed back verbatim from a previous "
                        "response's next_page_token."
                    ),
                    suggestions=[
                        "Re-run the original query without page_token, then "
                        "walk next_page_token verbatim page by page"
                    ],
                    error_code="govinfo_query_error",
                    details={"parameter": "page_token"},
                )
                flow["outcome"] = "page_token_undecodable"
                return _traced(format_error_response(error))
            state = decoded

        query = govinfo_search.build_query(
            validated_keywords, congress_value, bill_type_value,
            from_date=from_date, to_date=to_date)
        flow["upstream_query"] = query
        body = govinfo_search.build_search_body(
            query, limit_value, state["offsetMark"])

        # ---- Failure flow (spec 6.4) ----
        # Keyless: F31 -- api_key_missing, the operator must act. Nothing
        # is sent and the fallback does NOT fire.
        if not govinfo_api_key():
            flow["outcome"] = "keyless"
            return _traced(
                format_error_response(govinfo_search.keyless_error()))

        try:
            response = await govinfo_search_post(body)
        except httpx.HTTPError as exc:
            # Network unreachable / timeout: no canary (it cannot answer a
            # transport failure); labeled fallback.
            flow["outcome"] = f"transport_error:{type(exc).__name__}"
            flow["fallback_trigger"] = "govinfo_unreachable"
            return _traced(await _recency_window_fallback(
                ctx, validated_keywords, congress_value, bill_type_value,
                limit_value, trigger="govinfo_unreachable",
                trigger_detail=type(exc).__name__,
                from_date=from_date, to_date=to_date))

        if response.status_code == 429:
            # Spending quota to confirm quota is self-defeating: no canary.
            flow["outcome"] = "http_429"
            flow["fallback_trigger"] = "govinfo_rate_limited"
            return _traced(await _recency_window_fallback(
                ctx, validated_keywords, congress_value, bill_type_value,
                limit_value, trigger="govinfo_rate_limited",
                from_date=from_date, to_date=to_date))

        if response.status_code in (401, 403):
            # With a key configured this is key rejection: operator-
            # actionable, so no fallback (F31's sibling rule).
            flow["outcome"] = f"http_{response.status_code}"
            return _traced(format_error_response(
                govinfo_search.key_rejected_error(response.status_code)))

        if response.status_code != 200:
            # The 500 family -- also what a malformed request returns, with
            # an identical body (measured 2026-08-24). The canary
            # disambiguates: one server-built constant query, known valid,
            # zero caller input.
            flow["outcome"] = f"http_{response.status_code}"
            canary_ok = False
            try:
                canary = await govinfo_search_post(
                    govinfo_search.canary_body())
                canary_ok = canary.status_code == 200
                canary_result = f"http_{canary.status_code}"
            except httpx.HTTPError as exc:
                canary_ok = False
                canary_result = f"transport_error:{type(exc).__name__}"
            flow["canary"] = {
                "fired": True,
                "result": canary_result,
                "branch": "query_error" if canary_ok else "fallback",
            }
            if canary_ok:
                # Caller's input implicated; no fallback.
                return _traced(format_error_response(
                    govinfo_search.query_error(
                        response.status_code,
                        page_token_supplied=page_token is not None)))
            # Outage confirmed.
            flow["fallback_trigger"] = "govinfo_search_error"
            return _traced(await _recency_window_fallback(
                ctx, validated_keywords, congress_value, bill_type_value,
                limit_value, trigger="govinfo_search_error",
                trigger_detail=(
                    f"HTTP {response.status_code}; canary also failed"),
                from_date=from_date, to_date=to_date))

        data = response.json()
        records = data.get("results") or []
        count = int(data.get("count") or 0)
        bills, consumed, page_exhausted = govinfo_search.paginate_records(
            records, state["skip"], limit_value)
        next_token, _ = govinfo_search.compute_next_token(
            count=count,
            prior_consumed=state["records_consumed"],
            prior_skip=state["skip"],
            consumed_now=consumed,
            page_exhausted=page_exhausted,
            request_cursor=state["offsetMark"],
            response_cursor=data.get("offsetMark"),
        )
        flow["outcome"] = "http_200"
        return _traced(json.dumps(govinfo_search.build_corpus_response(
            bills,
            total_version_matches=count,
            upstream_query=query,
            congress=congress_value,
            bill_type=bill_type_value,
            next_page_token=next_token,
            request_note=request_note,
        ), indent=2))

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in search_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("search_bills")
        return format_error_response(error_response)


def _window_hit(bill: dict) -> dict:
    """A recency-window bill mapped onto the same identity fields corpus
    hits carry, so a consumer reads one hit shape from either source."""
    raw_number = bill.get("number")
    try:
        number = int(str(raw_number))
    except (TypeError, ValueError):
        number = raw_number
    bill_type = str(bill.get("type") or "").lower() or None
    latest = bill.get("latestAction")
    return {
        "bill": f"{str(bill.get('type') or '?').upper()} {raw_number}",
        "congress": bill.get("congress"),
        "bill_type": bill_type,
        "bill_number": number,
        "title": bill.get("title"),
        "latest_action": latest.get("text") if isinstance(latest, dict) else None,
        "update_date": bill.get("updateDate"),
        "url": bill.get("url"),
    }


def _update_date_in_bounds(update_date: Any,
                           from_date: Optional[str],
                           to_date: Optional[str]) -> bool:
    """Inclusive bound check on a window row's updateDate (date part).
    A row without an updateDate cannot establish membership under bounds
    and is excluded."""
    day = str(update_date or "")[:10]
    if not day:
        return False
    if from_date is not None and day < from_date:
        return False
    if to_date is not None and day > to_date:
        return False
    return True


async def _recency_window_fallback(
    ctx: Context,
    keywords: str,
    congress: Optional[int],
    bill_type: Optional[str],
    limit: int,
    trigger: str,
    trigger_detail: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> str:
    """#66's honest window wearing its fallback labels (spec 6.4): the
    250-row updateDate-desc page, title/policy-area filtered, with
    search_source: recency_window_fallback, the trigger class, and the
    window honesty metadata (bills_scanned / oldest updateDate /
    window_truncated) -- so a fallback zero is structurally
    distinguishable from a corpus zero, and both are distinguishable from
    an error (the three-zeros rule)."""
    scope = f" in Congress {congress}" if congress else ""
    response = await fetch_bill_data(
        ctx=ctx, congress=congress, bill_type=bill_type, format="json",
        limit=250, sort="updateDate+desc")
    if "error" in response:
        # An errored fallback is an ERROR, never an empty result set.
        return format_error_response(APIErrorResponse(
            error_type=ErrorType.SERVER_ERROR,
            message=(
                f"GovInfo corpus search failed ({trigger}) and the "
                "congress.gov recency-window fallback also failed."
            ),
            suggestions=["Retry later; both upstream sources errored"],
            error_code=trigger,
            details={"trigger_detail": trigger_detail,
                     "fallback_error": str(response.get("error"))[:300]},
        ))
    bills = BillsDataProcessor.extract_bills_from_response(response)
    bounded = from_date is not None or to_date is not None
    if bounded:
        # Q10 semantic shift, named below: the corpus path bounds the
        # version's PUBLICATION date; the window only carries congress.gov
        # updateDate, so the same bounds filter that instead.
        candidate_rows = [b for b in bills if isinstance(b, dict)
                          and _update_date_in_bounds(
                              b.get("updateDate"), from_date, to_date)]
    else:
        candidate_rows = bills
    filtered = await BillsDataProcessor.filter_by_keywords(
        candidate_rows, keywords, limit)
    dates = [str(b.get("updateDate")) for b in bills
             if isinstance(b, dict) and b.get("updateDate")]
    if filtered:
        message = (
            f"Title/policy-area filter over the {len(bills)} most recently "
            f"updated bills{scope}. GovInfo full-text search was "
            f"unavailable ({trigger}), so this is the recency window, not "
            "the corpus -- older bills are invisible here; retry later for "
            "corpus search."
        )
    else:
        message = (
            f"No match for '{keywords}' in the titles or policy areas of "
            f"the {len(bills)} most recently updated bills{scope}. GovInfo "
            f"full-text search was unavailable ({trigger}); this fallback "
            "only filters recently updated bills by title/policy area -- "
            "it is not a full-text or historical search, so this is NOT "
            "evidence the bill does not exist. Retry later for corpus "
            "search; for text inside a known bill use search_bill_text; "
            "for subject browsing use get_bill_subjects."
        )
    if bounded:
        bounds_text = (
            f" Date bounds [{from_date or '...'} .. {to_date or '...'}] "
            "were applied to congress.gov updateDate (last update) over "
            "the window rows -- NOT the version publication date the "
            "corpus path bounds."
        )
        message += bounds_text
    payload = {
        "search_source": "recency_window_fallback",
        "fallback_trigger": trigger,
        "results_count": len(filtered),
        "results": [_window_hit(b) for b in filtered
                    if isinstance(b, dict)],
        "window": {
            "bills_scanned": len(bills),
            "oldest_update_date": min(dates) if dates else None,
            "window_truncated": len(bills) >= 250,
        },
        "message": message,
        "next_page_token": None,
    }
    if bounded:
        payload["date_bounds"] = {"from": from_date, "to": to_date,
                                  "applied_to": "updateDate"}
    if trigger_detail:
        payload["fallback_detail"] = trigger_detail
    return json.dumps(payload, indent=2)


async def get_recent_bills(
    ctx: Context,
    limit: int = 20,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    days_back: int = 30,
    sort: str = "updateDate+desc"
) -> str:
    """
    Convenience wrapper for get_bills() with recent date filtering.
    Converts days_back to fromDateTime and calls core API.

    Args:
        ctx: Context for API requests
        limit: Maximum number of results
        congress: Optional Congress number
        bill_type: Optional bill type
        days_back: Number of days to look back for activity
        sort: Sort order ('updateDate+asc' or 'updateDate+desc')

    Returns:
        Formatted recent bills list or error message
    """
    try:
        # Convert days_back to API parameter
        from_date = BillsDataProcessor.calculate_date_range(days_back)

        # Call core API function
        return await get_bills(
            ctx=ctx,
            limit=limit,
            fromDateTime=from_date,
            sort=sort,
            congress=congress,
            bill_type=bill_type
        )

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_recent_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_recent_bills")
        return format_error_response(error_response)


# --- Specific Bill Functions ---

async def get_bill_details(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get detailed information for a specific bill.
    Maps to GET /bill/{congress}/{billType}/{billNumber}

    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type (hr, s, etc.)
        bill_number: Bill number

    Returns:
        Formatted bill details or error message
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))

        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value

        if not isinstance(bill_number, int) or bill_number <= 0:
            return format_error_response(CommonErrors.invalid_parameter(
                "bill_number", bill_number, "Bill number must be a positive integer"
            ))

        # API call
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Extract bill data
        bill = response.get('bill', {})
        if not bill:
            return f"Bill {bill_type.upper()} {bill_number} not found in Congress {congress}"

        # Format and return
        return BillsFormatter.format_bill_detail(bill)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_details: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_details")
        return format_error_response(error_response)


# --- Bill Sub-Resource Functions ---

async def get_bill_actions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """
    Get actions for a specific bill.
    Maps to GET /bill/{congress}/{billType}/{billNumber}/actions

    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type
        bill_number: Bill number
        limit: Maximum number of results
        offset: Starting record

    Returns:
        Formatted actions list or error message
    """
    try:
        # Validate parameters (reuse validation logic)
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))

        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value

        # Build parameters
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        # API call
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="actions",
            **params
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Extract actions
        actions = response.get('actions', [])

        # Format and return
        return BillsFormatter.format_bill_actions(actions, congress, bill_type, bill_number)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_actions: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_actions")
        return format_error_response(error_response)


# Additional sub-resource functions would follow the same pattern:
# get_bill_text_versions, get_bill_titles, get_bill_cosponsors, etc.
# For brevity, I'll add a few key ones...

async def get_bill_text_versions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get text versions for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="text"
        )

        if "error" in response:
            return str(response["error"])

        text_versions = response.get('textVersions', [])
        return BillsFormatter.format_bill_text_versions(text_versions)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_text_versions: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_text_versions")
        return format_error_response(error_response)


async def get_bill_summaries(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get summaries for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="summaries"
        )

        if "error" in response:
            return str(response["error"])

        summaries = response.get('summaries', [])
        return BillsFormatter.format_bill_summaries(summaries)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_summaries: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_summaries")
        return format_error_response(error_response)


# All remaining sub-resource functions following the same pattern

async def get_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get text information for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="text"
        )

        if "error" in response:
            return str(response["error"])

        text_versions = response.get('textVersions', [])
        return BillsFormatter.format_bill_text_versions(text_versions)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_text: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_text")
        return format_error_response(error_response)


async def get_bill_amendments(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get amendments for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="amendments",
            **params
        )

        if "error" in response:
            return str(response["error"])

        amendments = response.get('amendments', [])
        return BillsFormatter.format_bill_amendments(amendments)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_amendments: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_amendments")
        return format_error_response(error_response)


async def get_bill_committees(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get committees for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="committees",
            **params
        )

        if "error" in response:
            return str(response["error"])

        committees = response.get('committees', [])
        return BillsFormatter.format_bill_committees(committees)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_committees: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_committees")
        return format_error_response(error_response)


async def get_bill_cosponsors(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get cosponsors for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="cosponsors",
            **params
        )

        if "error" in response:
            return str(response["error"])

        cosponsors = response.get('cosponsors', [])
        return BillsFormatter.format_bill_cosponsors(cosponsors)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_cosponsors: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_cosponsors")
        return format_error_response(error_response)


async def get_bill_related_bills(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get related bills for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="relatedbills",
            **params
        )

        if "error" in response:
            return str(response["error"])

        related_bills = response.get('relatedBills', [])
        return BillsFormatter.format_bill_related_bills(related_bills)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_related_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_related_bills")
        return format_error_response(error_response)


async def get_bill_subjects(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get subjects for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="subjects",
            **params
        )

        if "error" in response:
            return str(response["error"])

        # The API returns subjects as a dict {legislativeSubjects, policyArea};
        # the formatter handles that shape (and a legacy list) directly.
        subjects = response.get('subjects', {})
        return BillsFormatter.format_bill_subjects(subjects)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_subjects: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_subjects")
        return format_error_response(error_response)


async def get_bill_titles(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get titles for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="titles",
            **params
        )

        if "error" in response:
            return str(response["error"])

        titles = response.get('titles', [])
        return BillsFormatter.format_bill_titles(titles)

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bill_titles: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_titles")
        return format_error_response(error_response)


async def get_bills_by_date_range(
    ctx: Context,
    fromDateTime: str,
    toDateTime: Optional[str] = None,
    limit: int = 20,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None
) -> str:
    """
    Get bills within a specific date range.
    This is now a simple wrapper around get_bills() - no longer redundant.
    """
    try:
        return await get_bills(
            ctx=ctx,
            limit=limit,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime,
            sort="updateDate+desc",
            congress=congress,
            bill_type=bill_type
        )

    except CongressionalAPIError as e:
        return format_error_response(e.error_response)
    except Exception as e:
        logger.error(f"Error in get_bills_by_date_range: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bills_by_date_range")
        return format_error_response(error_response)