"""
Congressional Records and Hearings - Consolidated MCP bucket tool for records and communications.

This bucket consolidates ~20 individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from ...core.exceptions import CongressionalAPIError, error_envelope, format_error_response
from ...mcp_app import mcp
from ...core.operation_routing import validate_operation_kwargs
from ...models.responses import RecordsHearingsResponse, HearingSummary, RecordSummary, ErrorInfo
from ...utils.response_converters import _extract_result_count, _int_or_none, structured_items_of

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> RecordsHearingsResponse:
    """Build the structured response; typed lists come from the impl's real items."""
    try:
        typed_error = getattr(raw_response, "error_response", None)
        if typed_error is not None:
            payload = error_envelope(typed_error)["error"]
            return RecordsHearingsResponse(
                success=False, operation=operation,
                error=ErrorInfo(**payload), results_count=0,
                hearings=[], records=[],
                summary=f"{payload['code']}: {payload['message']}")

        kind, items = structured_items_of(raw_response)
        if items is not None:
            hearings, records, generic = [], [], []
            if kind == "hearing":
                for h in items:
                    hearings.append(HearingSummary(
                        jacket_number=str(h.get("jacketNumber", "")),
                        congress=h.get("congress"),
                        chamber=h.get("chamber"),
                        title=h.get("title"),
                        committee=(h.get("committees") or [{}])[0].get("name")
                        if isinstance(h.get("committees"), list) else None,
                        date=(h.get("dates") or [{}])[0].get("date") if isinstance(h.get("dates"), list) else None,
                        update_date=h.get("updateDate"),
                        url=h.get("url"),
                    ))
            elif kind in ("record", "daily_record", "bound_record"):
                for r in items:
                    records.append(RecordSummary(
                        volume=_int_or_none(r.get("Volume") or r.get("volumeNumber") or r.get("volume")),
                        issue=_int_or_none(r.get("Issue") or r.get("issueNumber")),
                        session=_int_or_none(r.get("Session") or r.get("sessionNumber")),
                        congress=_int_or_none(r.get("Congress") or r.get("congress")),
                        date=r.get("PublishDate") or r.get("issueDate") or r.get("date"),
                        id=str(r.get("Id")) if r.get("Id") is not None else None,
                        url=r.get("url"),
                    ))
            else:
                generic = items
            return RecordsHearingsResponse(
                success=True, operation=operation, results_count=len(items),
                hearings=hearings, records=records, items=generic,
                item_kind=kind, summary=str(raw_response))

        return RecordsHearingsResponse(
            success=True, operation=operation,
            results_count=_extract_result_count(raw_response),
            hearings=[], records=[], summary=str(raw_response))
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return RecordsHearingsResponse(
            success=False, operation=operation, results_count=0,
            hearings=[], records=[], summary=f"Error processing response: {str(e)}")


async def route_records_and_hearings_operation(ctx: Context, operation: str, **kwargs) -> RecordsHearingsResponse:
    """Route operation to appropriate internal function."""

    # Congressional Record operations
    if operation == "search_congressional_record":
        from ..congressional_record import search_congressional_record
        validate_operation_kwargs(search_congressional_record, kwargs, operation)
        raw_response = await search_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_daily_congressional_record":
        from ..daily_congressional_record import search_daily_congressional_record
        validate_operation_kwargs(search_daily_congressional_record, kwargs, operation)
        raw_response = await search_daily_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_bound_congressional_record":
        from ..bound_congressional_record import search_bound_congressional_record
        validate_operation_kwargs(search_bound_congressional_record, kwargs, operation)
        raw_response = await search_bound_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # House communication operations
    elif operation == "search_house_communications":
        from ..house_communications import search_house_communications
        validate_operation_kwargs(search_house_communications, kwargs, operation)
        raw_response = await search_house_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_communication_details":
        from ..house_communications import get_house_communication_details
        validate_operation_kwargs(get_house_communication_details, kwargs, operation)
        raw_response = await get_house_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # House requirements operations
    elif operation == "search_house_requirements":
        from ..house_requirements import search_house_requirements
        validate_operation_kwargs(search_house_requirements, kwargs, operation)
        raw_response = await search_house_requirements(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_details":
        from ..house_requirements import get_house_requirement_details
        validate_operation_kwargs(get_house_requirement_details, kwargs, operation)
        raw_response = await get_house_requirement_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_matching_communications":
        from ..house_requirements import get_house_requirement_matching_communications
        validate_operation_kwargs(get_house_requirement_matching_communications, kwargs, operation)
        raw_response = await get_house_requirement_matching_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Senate communication operations
    elif operation == "search_senate_communications":
        from ..senate_communications import search_senate_communications
        validate_operation_kwargs(search_senate_communications, kwargs, operation)
        raw_response = await search_senate_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_senate_communication_details":
        from ..senate_communications import get_senate_communication_details
        validate_operation_kwargs(get_senate_communication_details, kwargs, operation)
        raw_response = await get_senate_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee communication operations
    elif operation == "get_committee_communication_details":
        from ..committees import get_committee_communication_details
        validate_operation_kwargs(get_committee_communication_details, kwargs, operation)
        raw_response = await get_committee_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Hearing operations
    elif operation == "search_hearings":
        from ..hearings import search_hearings
        validate_operation_kwargs(search_hearings, kwargs, operation)
        raw_response = await search_hearings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress":
        from ..hearings import get_hearings_by_congress
        validate_operation_kwargs(get_hearings_by_congress, kwargs, operation)
        raw_response = await get_hearings_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress_and_chamber":
        from ..hearings import get_hearings_by_congress_and_chamber
        validate_operation_kwargs(get_hearings_by_congress_and_chamber, kwargs, operation)
        raw_response = await get_hearings_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_details":
        from ..hearings import get_hearing_details
        validate_operation_kwargs(get_hearing_details, kwargs, operation)
        raw_response = await get_hearing_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_content":
        from ..hearings import get_hearing_content
        validate_operation_kwargs(get_hearing_content, kwargs, operation)
        raw_response = await get_hearing_content(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool(
    "records_and_hearings",
    title="Congressional Records and Hearings - Legislative records, communications, and hearings",
)
async def records_and_hearings(
    ctx: Context,
    operation: str,
    # Congressional Record parameters
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    congress: Optional[int] = None,
    volume_number: Optional[str] = None,
    issue_number: Optional[str] = None,
    limit: Optional[int] = None,
    # Communication parameters
    communication_type: Optional[str] = None,
    communication_number: Optional[int] = None,
    chamber: Optional[str] = None,
    requirement_number: Optional[int] = None,
    # Hearing parameters
    keywords: Optional[str] = None,
    jacket_number: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None,
    sort: Optional[str] = None
) -> RecordsHearingsResponse:
    """
    Congressional Records and Hearings - Access legislative records, communications, and hearings.

    CONGRESSIONAL RECORDS (3 operations):
    • search_congressional_record/daily/bound - Search legislative records by date/volume

    COMMUNICATIONS (8 operations):
    • House: search_house_communications/requirements, get_details/matching
    • Senate: search_senate_communications, get_senate_communication_details
    • Committee: get_committee_communication_details

    HEARINGS (5 operations):
    • search_hearings, get_hearings_by_congress/chamber, get_hearing_details/content

    REQUIRED PARAMETERS (the schema marks every parameter optional because
    one shared schema covers every operation -- these operations fail
    without the values below):
    • congress -- get_hearings_by_congress
    • congress + chamber -- get_hearings_by_congress_and_chamber
    • congress + chamber + jacket_number -- get_hearing_details,
      get_hearing_content
    • congress + communication_type + communication_number --
      get_senate_communication_details, get_house_communication_details
    • congress + chamber + communication_type + communication_number --
      get_committee_communication_details
    • requirement_number -- get_house_requirement_details,
      get_house_requirement_matching_communications
    (search_congressional_record/daily/bound and every other search_*
    operation need none of the above)

    Key params: operation, year/month/day, keywords, congress, chamber, jacket_number
    Returns structured record/hearing data with full text content and metadata.
    """
    try:
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'year': year,
            'month': month,
            'day': day,
            'congress': congress,
            'volume_number': volume_number,
            'issue_number': issue_number,
            'limit': limit,
            'communication_type': communication_type,
            'communication_number': communication_number,
            'chamber': chamber,
            'requirement_number': requirement_number,
            'keywords': keywords,
            'jacket_number': jacket_number,
            'from_date_time': from_date_time,
            'to_date_time': to_date_time,
            'sort': sort
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value

        # Route to appropriate internal function. route_records_and_hearings_operation
        # already returns a fully-converted RecordsHearingsResponse (it calls
        # _convert_to_structured_response internally) — re-converting it here fails the
        # isinstance(raw_response, str) check and silently discards all data, always
        # returning empty/zero results regardless of what the API actually returned.
        return await route_records_and_hearings_operation(ctx, operation, **operation_kwargs)

    except CongressionalAPIError as e:
        # Typed Congress.gov error from a handler with no try/except of its
        # own: return the model carrying the section-9 envelope.
        return _convert_to_structured_response(format_error_response(e.error_response), operation)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in records_and_hearings operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
