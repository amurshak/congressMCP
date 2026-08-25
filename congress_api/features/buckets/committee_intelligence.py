"""
Congressional Committee Intelligence - Consolidated MCP bucket tool for committee documents.

This bucket consolidates ~30 individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from ...core.exceptions import CongressionalAPIError, error_envelope, format_error_response
from ...mcp_app import mcp
from ...core.operation_routing import validate_operation_kwargs
from ...models.responses import CommitteeIntelligenceResponse, CommitteeActivitySummary, ErrorInfo
from ...utils.response_converters import _extract_result_count, structured_items_of

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> CommitteeIntelligenceResponse:
    """Build the structured response; typed lists come from the impl's real items."""
    try:
        typed_error = getattr(raw_response, "error_response", None)
        if typed_error is not None:
            payload = error_envelope(typed_error)["error"]
            return CommitteeIntelligenceResponse(
                success=False, operation=operation,
                error=ErrorInfo(**payload), results_count=0,
                activities=[],
                summary=f"{payload['code']}: {payload['message']}")

        kind, items = structured_items_of(raw_response)
        if items is not None:
            activities = []
            kind_map = {"committee_report": "report", "committee_print": "print",
                        "committee_meeting": "meeting"}
            activity_type = kind_map.get(kind or "", kind or "activity")
            for a in items:
                identifier = a.get("number") or a.get("jacketNumber") or a.get("eventId")
                activities.append(CommitteeActivitySummary(
                    activity_type=activity_type,
                    citation=a.get("citation"),
                    identifier=str(identifier) if identifier is not None else None,
                    congress=a.get("congress"),
                    chamber=a.get("chamber"),
                    committee_name=(a.get("committees") or [{}])[0].get("name")
                    if isinstance(a.get("committees"), list) else None,
                    title=a.get("title"),
                    date=a.get("updateDate") or a.get("date"),
                    url=a.get("url"),
                ))
            return CommitteeIntelligenceResponse(
                success=True, operation=operation, results_count=len(items),
                activities=activities, summary=str(raw_response))

        return CommitteeIntelligenceResponse(
            success=True, operation=operation,
            results_count=_extract_result_count(raw_response),
            activities=[], summary=str(raw_response))
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return CommitteeIntelligenceResponse(
            success=False, operation=operation, results_count=0,
            activities=[], summary=f"Error processing response: {str(e)}")

async def route_committee_intelligence_operation(ctx: Context, operation: str, **kwargs) -> CommitteeIntelligenceResponse:
    """Route operation to appropriate internal function."""

    # Committee report operations
    if operation == "get_latest_committee_reports":
        from ..committee_reports import get_latest_committee_reports
        validate_operation_kwargs(get_latest_committee_reports, kwargs, operation)
        raw_response = await get_latest_committee_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_reports_by_congress":
        from ..committee_reports import get_committee_reports_by_congress
        validate_operation_kwargs(get_committee_reports_by_congress, kwargs, operation)
        raw_response = await get_committee_reports_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_reports_by_congress_and_type":
        from ..committee_reports import get_committee_reports_by_congress_and_type
        validate_operation_kwargs(get_committee_reports_by_congress_and_type, kwargs, operation)
        raw_response = await get_committee_reports_by_congress_and_type(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_details":
        from ..committee_reports import get_committee_report_details
        validate_operation_kwargs(get_committee_report_details, kwargs, operation)
        raw_response = await get_committee_report_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_text_versions":
        from ..committee_reports import get_committee_report_text_versions
        validate_operation_kwargs(get_committee_report_text_versions, kwargs, operation)
        raw_response = await get_committee_report_text_versions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_content":
        from ..committee_reports import get_committee_report_content
        validate_operation_kwargs(get_committee_report_content, kwargs, operation)
        raw_response = await get_committee_report_content(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_reports":
        from ..committee_reports import search_committee_reports
        validate_operation_kwargs(search_committee_reports, kwargs, operation)
        raw_response = await search_committee_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee print operations
    elif operation == "get_latest_committee_prints":
        from ..committee_prints import get_latest_committee_prints
        validate_operation_kwargs(get_latest_committee_prints, kwargs, operation)
        raw_response = await get_latest_committee_prints(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_prints_by_congress":
        from ..committee_prints import get_committee_prints_by_congress
        validate_operation_kwargs(get_committee_prints_by_congress, kwargs, operation)
        raw_response = await get_committee_prints_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_prints_by_congress_and_chamber":
        from ..committee_prints import get_committee_prints_by_congress_and_chamber
        validate_operation_kwargs(get_committee_prints_by_congress_and_chamber, kwargs, operation)
        raw_response = await get_committee_prints_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_print_details":
        from ..committee_prints import get_committee_print_details
        validate_operation_kwargs(get_committee_print_details, kwargs, operation)
        raw_response = await get_committee_print_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_print_text_versions":
        from ..committee_prints import get_committee_print_text_versions
        validate_operation_kwargs(get_committee_print_text_versions, kwargs, operation)
        raw_response = await get_committee_print_text_versions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_prints":
        from ..committee_prints import search_committee_prints
        validate_operation_kwargs(search_committee_prints, kwargs, operation)
        raw_response = await search_committee_prints(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee meeting operations
    elif operation == "get_latest_committee_meetings":
        from ..committee_meetings import get_latest_committee_meetings
        validate_operation_kwargs(get_latest_committee_meetings, kwargs, operation)
        raw_response = await get_latest_committee_meetings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_congress":
        from ..committee_meetings import get_committee_meetings_by_congress
        validate_operation_kwargs(get_committee_meetings_by_congress, kwargs, operation)
        raw_response = await get_committee_meetings_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_congress_and_chamber":
        from ..committee_meetings import get_committee_meetings_by_congress_and_chamber
        validate_operation_kwargs(get_committee_meetings_by_congress_and_chamber, kwargs, operation)
        raw_response = await get_committee_meetings_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_committee":
        from ..committee_meetings import get_committee_meetings_by_committee
        validate_operation_kwargs(get_committee_meetings_by_committee, kwargs, operation)
        raw_response = await get_committee_meetings_by_committee(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meeting_details":
        from ..committee_meetings import get_committee_meeting_details
        validate_operation_kwargs(get_committee_meeting_details, kwargs, operation)
        raw_response = await get_committee_meeting_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_meetings":
        from ..committee_meetings import search_committee_meetings
        validate_operation_kwargs(search_committee_meetings, kwargs, operation)
        raw_response = await search_committee_meetings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool(
    "committee_intelligence",
    title="Congressional Committee Intelligence - Committee documents and activities",
)
async def committee_intelligence(
    ctx: Context,
    operation: str,
    # General parameters
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    committee_code: Optional[str] = None,
    limit: Optional[int] = None,
    # Report parameters
    report_type: Optional[str] = None,
    report_number: Optional[int] = None,
    conference: Optional[str] = None,
    chunk_number: Optional[int] = None,
    chunk_size: Optional[int] = None,
    # Print parameters
    jacket_number: Optional[int] = None,
    # Meeting parameters
    event_id: Optional[int] = None,
    keywords: Optional[str] = None,
    scheduled_from: Optional[str] = None,
    scheduled_to: Optional[str] = None,
    sort: Optional[str] = None,
    # Search parameters
    offset: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None
) -> CommitteeIntelligenceResponse:
    """
    Congressional Committee Intelligence - Professional access to committee documents and activities.

    COMMITTEE REPORTS (7 operations):
    • get_latest/by_congress/by_type, get_report_details/text_versions/content
    • search_committee_reports - Advanced analytics with chunking support

    COMMITTEE PRINTS (6 operations):
    • get_latest/by_congress/by_chamber, get_print_details/text_versions
    • search_committee_prints - Document intelligence with filtering

    COMMITTEE MEETINGS (6 operations):
    • get_latest/by_congress/by_chamber/by_committee, get_meeting_details
    • search_committee_meetings - Process intelligence with scheduling data

    REQUIRED PARAMETERS (the schema marks every parameter optional because
    one shared schema covers every operation -- these operations fail
    without the values below):
    • congress -- get_committee_reports_by_congress,
      get_committee_prints_by_congress, get_committee_meetings_by_congress
    • congress + chamber -- get_committee_prints_by_congress_and_chamber,
      get_committee_meetings_by_congress_and_chamber
    • congress + report_type -- get_committee_reports_by_congress_and_type
    • congress + report_type + report_number -- get_committee_report_details,
      get_committee_report_text_versions, get_committee_report_content
    • congress + chamber + jacket_number -- get_committee_print_details,
      get_committee_print_text_versions
    • congress + chamber + committee_code --
      get_committee_meetings_by_committee
    • congress + chamber + event_id -- get_committee_meeting_details
    (get_latest_committee_reports/prints/meetings and every search_*
    operation need none of the above)

    Key params: operation, congress, chamber, committee_code, report_type, event_id
    Returns structured committee data with enhanced metadata and content chunking.
    """
    try:
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'congress': congress,
            'chamber': chamber,
            'committee_code': committee_code,
            'limit': limit,
            'report_type': report_type,
            'report_number': report_number,
            'conference': conference,
            'chunk_number': chunk_number,
            'chunk_size': chunk_size,
            'jacket_number': jacket_number,
            'event_id': event_id,
            'keywords': keywords,
            'scheduled_from': scheduled_from,
            'scheduled_to': scheduled_to,
            'sort': sort,
            'offset': offset,
            'from_date_time': from_date_time,
            'to_date_time': to_date_time
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value

        # Route to appropriate internal function. route_committee_intelligence_operation
        # already returns a fully-converted CommitteeIntelligenceResponse (it calls
        # _convert_to_structured_response internally) — re-converting it here fails the
        # isinstance(raw_response, str) check and silently discards all data, always
        # returning empty/zero results regardless of what the API actually returned.
        return await route_committee_intelligence_operation(ctx, operation, **operation_kwargs)

    except CongressionalAPIError as e:
        # Typed Congress.gov error from a handler with no try/except of its
        # own: return the model carrying the section-9 envelope.
        return _convert_to_structured_response(format_error_response(e.error_response), operation)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in committee_intelligence operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
