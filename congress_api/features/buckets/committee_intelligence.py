"""
Congressional Committee Intelligence - Consolidated MCP bucket tool for committee documents.

This bucket consolidates ~30 individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import CommitteeIntelligenceResponse, CommitteeActivitySummary
from ...utils.response_converters import _extract_result_count

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> CommitteeIntelligenceResponse:
    """Convert raw string response to structured CommitteeIntelligenceResponse."""
    import json

    try:
        if isinstance(raw_response, str):
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # The underlying impls return pre-formatted markdown, not JSON, so this
                # is the normal path for every operation, not a fallback for malformed
                # data — it must preserve the full response, not truncate it.
                return CommitteeIntelligenceResponse(
                    success=True,
                    operation=operation,
                    results_count=_extract_result_count(raw_response),
                    activities=[],
                    summary=raw_response,
                    insights=[]
                )
        else:
            data = raw_response

        activities = []
        results_count = 0

        if isinstance(data, dict):
            # Handle committee activities
            if 'activities' in data:
                for activity_data in data.get('activities', []):
                    if isinstance(activity_data, dict):
                        activities.append(CommitteeActivitySummary(
                            committee_name=activity_data.get('committee', ''),
                            activity_type=activity_data.get('activityType', ''),
                            title=activity_data.get('title', ''),
                            date=activity_data.get('date'),
                            status=activity_data.get('status', ''),
                            url=activity_data.get('url')
                        ))

            # Handle meetings as activities
            if 'meetings' in data:
                for meeting_data in data.get('meetings', []):
                    if isinstance(meeting_data, dict):
                        activities.append(CommitteeActivitySummary(
                            committee_name=meeting_data.get('committee', ''),
                            activity_type='meeting',
                            title=meeting_data.get('title', ''),
                            date=meeting_data.get('date'),
                            status=meeting_data.get('status', ''),
                            url=meeting_data.get('url')
                        ))

            results_count = len(activities)

        return CommitteeIntelligenceResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            activities=activities,
            summary=f"Found {len(activities)} committee activities",
            insights=[]
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return CommitteeIntelligenceResponse(
            success=False,
            operation=operation,
            results_count=0,
            activities=[],
            summary=f"Error processing response: {str(e)}",
            insights=[]
        )

async def route_committee_intelligence_operation(ctx: Context, operation: str, **kwargs) -> CommitteeIntelligenceResponse:
    """Route operation to appropriate internal function."""

    # Committee report operations
    if operation == "get_latest_committee_reports":
        from ..committee_reports import get_latest_committee_reports
        raw_response = await get_latest_committee_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_reports_by_congress":
        from ..committee_reports import get_committee_reports_by_congress
        raw_response = await get_committee_reports_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_reports_by_congress_and_type":
        from ..committee_reports import get_committee_reports_by_congress_and_type
        raw_response = await get_committee_reports_by_congress_and_type(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_details":
        from ..committee_reports import get_committee_report_details
        raw_response = await get_committee_report_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_text_versions":
        from ..committee_reports import get_committee_report_text_versions
        raw_response = await get_committee_report_text_versions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_report_content":
        from ..committee_reports import get_committee_report_content
        raw_response = await get_committee_report_content(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_reports":
        from ..committee_reports import search_committee_reports
        raw_response = await search_committee_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee print operations
    elif operation == "get_latest_committee_prints":
        from ..committee_prints import get_latest_committee_prints
        raw_response = await get_latest_committee_prints(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_prints_by_congress":
        from ..committee_prints import get_committee_prints_by_congress
        raw_response = await get_committee_prints_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_prints_by_congress_and_chamber":
        from ..committee_prints import get_committee_prints_by_congress_and_chamber
        raw_response = await get_committee_prints_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_print_details":
        from ..committee_prints import get_committee_print_details
        raw_response = await get_committee_print_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_print_text_versions":
        from ..committee_prints import get_committee_print_text_versions
        raw_response = await get_committee_print_text_versions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_prints":
        from ..committee_prints import search_committee_prints
        raw_response = await search_committee_prints(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee meeting operations
    elif operation == "get_latest_committee_meetings":
        from ..committee_meetings import get_latest_committee_meetings
        raw_response = await get_latest_committee_meetings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_congress":
        from ..committee_meetings import get_committee_meetings_by_congress
        raw_response = await get_committee_meetings_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_congress_and_chamber":
        from ..committee_meetings import get_committee_meetings_by_congress_and_chamber
        raw_response = await get_committee_meetings_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meetings_by_committee":
        from ..committee_meetings import get_committee_meetings_by_committee
        raw_response = await get_committee_meetings_by_committee(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_meeting_details":
        from ..committee_meetings import get_committee_meeting_details
        raw_response = await get_committee_meeting_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_committee_meetings":
        from ..committee_meetings import search_committee_meetings
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

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in committee_intelligence operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
