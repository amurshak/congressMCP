"""
Comprehensive Bills Tool - Focused legislation tool for bills operations

Replaces legislation_hub.py bucket with a single comprehensive bills tool
that handles all bill-related operations through a clean, structured interface.
"""

import logging
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from ..core.exceptions import CongressionalAPIError, format_error_response
from ..mcp_app import mcp
from ..core.operation_routing import validate_operation_kwargs
from ..utils.bill_parser import parse_bill_reference, validate_bill_params

logger = logging.getLogger(__name__)


async def route_bills_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate bills function."""

    if operation == "search_bills":
        from .buckets.bills import search_bills
        validate_operation_kwargs(search_bills, kwargs, operation)
        return await search_bills(ctx, **kwargs)
    elif operation == "get_bills":
        from .buckets.bills import get_bills
        validate_operation_kwargs(get_bills, kwargs, operation)
        return await get_bills(ctx, **kwargs)
    elif operation == "get_bill_details":
        from .buckets.bills import get_bill_details
        validate_operation_kwargs(get_bill_details, kwargs, operation)
        return await get_bill_details(ctx, **kwargs)
    elif operation == "get_bill_text":
        from .buckets.bills import get_bill_text
        validate_operation_kwargs(get_bill_text, kwargs, operation)
        return await get_bill_text(ctx, **kwargs)
    elif operation == "get_bill_text_versions":
        from .buckets.bills import get_bill_text_versions
        validate_operation_kwargs(get_bill_text_versions, kwargs, operation)
        return await get_bill_text_versions(ctx, **kwargs)
    elif operation == "get_bill_titles":
        from .buckets.bills import get_bill_titles
        validate_operation_kwargs(get_bill_titles, kwargs, operation)
        return await get_bill_titles(ctx, **kwargs)
    elif operation == "get_bill_summaries":
        from .buckets.bills import get_bill_summaries
        validate_operation_kwargs(get_bill_summaries, kwargs, operation)
        return await get_bill_summaries(ctx, **kwargs)
    elif operation == "get_recent_bills":
        from .buckets.bills import get_recent_bills
        validate_operation_kwargs(get_recent_bills, kwargs, operation)
        return await get_recent_bills(ctx, **kwargs)
    elif operation == "get_bills_by_date_range":
        from .buckets.bills import get_bills_by_date_range
        validate_operation_kwargs(get_bills_by_date_range, kwargs, operation)
        return await get_bills_by_date_range(ctx, **kwargs)
    elif operation == "get_bill_actions":
        from .buckets.bills import get_bill_actions
        validate_operation_kwargs(get_bill_actions, kwargs, operation)
        return await get_bill_actions(ctx, **kwargs)
    elif operation == "get_bill_amendments":
        from .buckets.bills import get_bill_amendments
        validate_operation_kwargs(get_bill_amendments, kwargs, operation)
        return await get_bill_amendments(ctx, **kwargs)
    elif operation == "get_bill_committees":
        from .buckets.bills import get_bill_committees
        validate_operation_kwargs(get_bill_committees, kwargs, operation)
        return await get_bill_committees(ctx, **kwargs)
    elif operation == "get_bill_cosponsors":
        from .buckets.bills import get_bill_cosponsors
        validate_operation_kwargs(get_bill_cosponsors, kwargs, operation)
        return await get_bill_cosponsors(ctx, **kwargs)
    elif operation == "get_bill_related_bills":
        from .buckets.bills import get_bill_related_bills
        validate_operation_kwargs(get_bill_related_bills, kwargs, operation)
        return await get_bill_related_bills(ctx, **kwargs)
    elif operation == "get_bill_subjects":
        from .buckets.bills import get_bill_subjects
        validate_operation_kwargs(get_bill_subjects, kwargs, operation)
        return await get_bill_subjects(ctx, **kwargs)
    else:
        raise ToolError(f"Unknown bills operation: {operation}")

@mcp.tool(
    "bills",
    title="Congressional Bills - Comprehensive bill operations",
)
async def bills(
    ctx: Context,
    operation: str,
    # Flexible bill identification (NEW)
    bill_id: Optional[str] = None,
    # Core bill identification
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    bill_number: Optional[int] = None,
    # Filtering and pagination
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    format: Optional[str] = None,
    offset: Optional[int] = None,
    page_token: Optional[str] = None,
    # Date filtering
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    days_back: Optional[int] = None,
    # search_bills only: Q11 snippet warming budget
    snippet_fetch: Optional[int] = None,
) -> str:
    """
    Comprehensive Bills Tool - All bill operations in one focused interface.
    
    FLEXIBLE BILL IDENTIFICATION (NEW):
    Use bill_id for natural language references like 'HR 1234',
    'H.R. 1234, 118th Congress', 'hr1234-118', 'S 456', etc. Always parses
    to bill_type/bill_number; parses to congress too only when the
    reference embeds one (see REQUIRED PARAMETERS below).
    
    CORE OPERATIONS:
    • Search & Discovery: search_bills, get_bills, get_recent_bills
    • Details & Metadata: get_bill_details, get_bill_titles, get_bill_subjects
    • Text & Content: get_bill_text, get_bill_text_versions
      (for FULL bill text search/retrieval use the dedicated search_bill_text,
      get_bill_section and get_bill_toc tools)
    • Summaries: get_bill_summaries
    • Relationships: get_bill_related_bills, get_bill_amendments
    • Legislative Process: get_bill_actions, get_bill_committees, get_bill_cosponsors
    • Date-Based: get_bills_by_date_range

    SEARCH_BILLS (GovInfo full-text corpus search):
    search_bills searches the full text of congressional bills -- every
    version of every bill in the GovInfo BILLS collection -- ranked by
    relevance. Parameters: keywords (required), congress, bill_type, limit,
    page_token, fromDateTime, toDateTime, snippet_fetch. It does NOT take
    offset/sort/format.
    - Matching semantics: words are ANDed -- every term must appear in
      the SAME document, so each added word strictly shrinks the result
      set and can never grow it. Start with the distinctive minimum: the
      fewest words that name the thing, and add terms only to cut a set
      that came back too large. Do NOT add words describing the topic,
      category, or what the bill does -- that is the natural way to
      phrase a search and the usual cause of a starved result. Worked
      example: "Radiation Exposure Compensation Act amendments
      downwinders" returns 1 bill; dropping the two description words
      returns 26, including the enacted vehicle. A small count means the
      terms rarely co-occur, NOT that few such bills exist -- re-query
      broader (drop words) before concluding anything. Synonyms do NOT
      broaden here:
      unlike search_bill_text, which ORs its queries array and rewards
      adding alternate phrasings, an added synonym on this path
      intersects and discards.
    - Do NOT quote bill names (quoted phrases measured to miss title
      text); title:"..." / shorttitle:"..." for exact titles; OR / NOT
      available.
    - Fielded operators -- the full supported set, each measured live
      (value form exactly as measured): congress:119; billtype:hr (hr s
      hjres sjres hconres sconres hres sres); docnumber:4631;
      billversion:enr (a version code); chamber:house / chamber:senate;
      member:schumer (member last name); memberparty:r (single party
      letter); memberstate:mo (two-letter state code);
      committee:judiciary (a committee-name word);
      actiondate:2025-01-03 (YYYY-MM-DD); publishdate:2025-07-23
      (YYYY-MM-DD -- the fromDateTime/toDateTime parameters are the
      range form); isprivate:false and isappropriation:false (boolean);
      uscodecitation:"42 U.S.C. 2210"; statutecitation:"133 Stat. 1198";
      plawcitation:"Public Law 101-426" (the three citation fields take
      the quoted citation string). field:range(a,b) works on date
      fields. A field name NOT on this list is a query error upstream
      (measured HTTP 500, the malformed-request family) -- the tool
      answers govinfo_query_error, so do not invent field names.
      NOTE TRAP: uscodecitation matches the CODE SECTION, not notes
      published under it. A note-codified Act (RECA at 42 U.S.C. 2210
      note) does NOT match uscodecitation:"42 U.S.C. 2210" -- that
      returns the section's own bills. Measured in Congress 119: that
      query returns 7 bills, ZERO of them RECA (all Price-Anderson /
      nuclear-energy bills amending the section proper), while
      plawcitation:"Public Law 101-426" returns the 7-bill RECA answer
      set. The two citation fields silently DISAGREE about the same
      statute with no signal to try the other: for a note-codified Act
      use plawcitation:"Public Law NNN-NNN"; when both forms exist,
      prefer plawcitation.
    - keywords is required: blank or whitespace-only keywords are rejected
      (invalid_parameters), never sent.
    - Version discovery: each hit fronts the most authoritative matched
      version (package_id, version, date_issued) and carries
      matched_versions -- ONLY the versions whose text matched this query,
      not the bill's complete version set. For a specific bill's COMPLETE
      version set, call search_bills with fielded terms and no text words,
      e.g. keywords="congress:119 billtype:s docnumber:1071" -- that
      returns exactly the bill's versions. A pinned version that does not
      exist still answers version_not_available (bill-text tools).
    - Count semantics: total_version_matches counts matching VERSION
      PACKAGES upstream and can exceed the number of distinct bills;
      results_count counts the bills actually returned in this page.
    - Pagination: pass next_page_token back verbatim as page_token; null
      means the result set is exhausted. Pages can legally run short of
      limit (version-heavy pages dedup below it). A bill whose version
      records straddle a page boundary can rarely reappear on the next
      page with the same identity -- dedup by congress/bill_type/
      bill_number if walking pages.
    - Snippets: a hit whose fronted version package is already in the
      local bill-text cache carries snippet_status and snippet, localized
      from the cached text per-term (zero network). snippet_fetch: N
      (default 0, hard cap 5) additionally downloads and enrolls the top-N
      UNCACHED hits in rank order so they get snippets too. Three states:
      snippet_status "localized" with a snippet object; "not_localized"
      with snippet null (the cached text was searched and the terms did
      not match locally -- the upstream match still stands, the local
      stemming just missed it); BOTH fields absent means localization was
      not attempted (uncached with no fetch budget). Every snippet object
      carries the matched unit's section_id and match_contexts, and
      "quoted" governs: a snippet drawn from quoted material is language
      the bill is inserting or striking -- delimited in the snippet text
      -- NOT what current law says.
    - Diagnostics: a starved result diagnoses itself. When the query has
      2+ text terms and total_version_matches < 10, the response carries
      diagnostics.term_ladder: the query re-run with text terms chopped
      from the right, one per rung, down to a single term. Each rung
      lists the terms kept and the upstream count, so the rung where the
      count jumps names the term that starved the query -- and each rung
      is itself the broader re-query to take. A final rung with terms []
      is the constraints-only count: the size of the universe the
      fielded/scope constraints allow, the ladder's denominator. Caveat:
      right-chopping isolates trailing added words (the usual failure);
      when the rare term sits FIRST, every rung stays small down to the
      single-term rung -- which is the correct reading: the core term is
      rare. A small count can be a CORRECT answer -- the ladder is
      evidence for judging a result, not a verdict against it. On a
      zero-total query carrying droppable constraints (fielded
      operators, congress/bill_type scope, date bounds), the response
      carries diagnostics.leave_one_out: the query re-run omitting one
      constraint per probe -- the omission that restores hits names the
      dead constraint (e.g. a version the bill never had). A probe that
      errors reports count null with status "probe_failed", never 0.
      Absence of diagnostics means it did not fire, never that it ran
      and found nothing.
    - Fallback: when search_source is "recency_window_fallback", GovInfo
      was unavailable (read fallback_trigger) and results are a
      title/policy-area filter over the most recently updated bills, NOT
      the corpus -- a zero there is not evidence a bill does not exist;
      the window metadata says what was scanned.
    - Time-bounding: fromDateTime/toDateTime bound the VERSION'S
      PUBLICATION DATE on the corpus path (inclusive both ends; either
      side may be given alone; ISO date or datetime, datetimes truncated
      to the date) -- NOT congress.gov's update date. In fallback mode
      the same bounds filter updateDate over the window instead, and the
      response says so.

    REQUIRED PARAMETERS (the schema marks every parameter optional because
    one shared schema covers every operation -- these operations fail
    without the values below):
    • congress + bill_type + bill_number -- get_bill_details,
      get_bill_titles, get_bill_subjects, get_bill_text,
      get_bill_text_versions, get_bill_summaries, get_bill_related_bills,
      get_bill_amendments, get_bill_actions, get_bill_committees,
      get_bill_cosponsors. bill_id can substitute for bill_type +
      bill_number, but only supplies congress itself when the reference
      embeds one ('hr1234-118', 'HR 1234, 118th Congress') -- a bare
      'HR 1234' still needs an explicit congress or the call fails the
      same as if bill_id were omitted entirely.
    • fromDateTime -- get_bills_by_date_range
    • keywords -- search_bills (see SEARCH_BILLS above)
    (get_bills, get_recent_bills need none of the above)

    Args:
        operation: Specific operation to perform (see list above)
        bill_id: Flexible bill reference (e.g., 'HR 1234', 'H.R. 1234, 118th Congress', 'hr1234-118')
                 Parsed to populate bill_type and bill_number always, and
                 congress only if the reference embeds one -- pass congress
                 explicitly otherwise
        keywords: search_bills: required full-text query (see
                  SEARCH_BILLS above for matching semantics)
        congress: Congress number (118 for current, 119 for next)
        bill_type: hr, s, hjres, sjres, hconres, sconres, hres, sres
        bill_number: Specific bill number within type and congress
        limit: Results limit (max 250 for API compliance)
        page_token: search_bills only -- opaque pagination cursor from a
                    previous response's next_page_token, passed back verbatim
        snippet_fetch: search_bills only -- Q11 warming budget: download and
                    enroll up to N uncached hits (cap 5) for local snippets
        sort: updateDate+desc (newest first) or updateDate+asc (not for
              search_bills, which is relevance-ranked)
        fromDateTime/toDateTime: Date range (YYYY-MM-DDTHH:MM:SSZ;
              search_bills: inclusive bounds on version publication date,
              see SEARCH_BILLS above)
        
    Returns:
        Formatted results specific to requested operation
        
    Examples:
        Using flexible bill_id (congress embedded in the reference itself):
        {"operation": "get_bill_details", "bill_id": "H.R. 1234, 118th Congress"}
        {"operation": "get_bill_details", "bill_id": "hr1234-118"}

        bill_id without an embedded congress still needs one explicitly:
        {"operation": "get_bill_details", "bill_id": "HR 1234", "congress": 118}
        
        Traditional parameters still work:
        {"operation": "get_bill_details", "congress": 118, "bill_type": "hr", "bill_number": 1234}
    """
    try:
        # Handle flexible bill_id parsing
        parsed_congress = congress
        parsed_bill_type = bill_type
        parsed_bill_number = bill_number

        if bill_id:
            # Parse the flexible bill reference
            parse_result = parse_bill_reference(bill_id, default_congress=congress)

            if not parse_result['parse_success']:
                raise ToolError(f"Bill ID parsing failed: {parse_result['error_message']}")

            # Use parsed values if the explicit parameters weren't provided
            if parsed_congress is None and parse_result['congress'] is not None:
                parsed_congress = parse_result['congress']
            if parsed_bill_type is None and parse_result['bill_type'] is not None:
                parsed_bill_type = parse_result['bill_type']
            if parsed_bill_number is None and parse_result['bill_number'] is not None:
                parsed_bill_number = parse_result['bill_number']

            # Validate parsed parameters
            if parsed_bill_type and parsed_bill_number:
                is_valid, error_msg = validate_bill_params(parsed_bill_type, parsed_bill_number, parsed_congress)
                if not is_valid:
                    raise ToolError(f"Invalid bill parameters from '{bill_id}': {error_msg}")

        # Build kwargs dict from all provided parameters, using parsed values where appropriate
        operation_kwargs = {}
        for param_name, param_value in {
            'keywords': keywords,
            'congress': parsed_congress,
            'bill_type': parsed_bill_type,
            'bill_number': parsed_bill_number,
            'limit': limit,
            'sort': sort,
            'format': format,
            'offset': offset,
            'page_token': page_token,
            'fromDateTime': fromDateTime,
            'toDateTime': toDateTime,
            'days_back': days_back,
            'snippet_fetch': snippet_fetch
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value

        # Route to appropriate internal function
        raw_response = await route_bills_operation(ctx, operation, **operation_kwargs)
        return raw_response

    except CongressionalAPIError as e:
        # Typed Congress.gov error from a handler with no try/except of its
        # own: return the section-9 envelope instead of a ToolError string.
        return format_error_response(e.error_response)
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in bills operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing bills operation '{operation}': {str(e)}")
