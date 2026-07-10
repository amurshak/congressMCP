"""
Congressional Records and Hearings - Consolidated MCP bucket tool for records and communications.

This bucket consolidates ~20 individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import RecordsHearingsResponse, HearingSummary, RecordSummary
from ...utils.response_converters import _extract_result_count

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> RecordsHearingsResponse:
    """Convert raw string response to structured RecordsHearingsResponse."""
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
                return RecordsHearingsResponse(
                    success=True,
                    operation=operation,
                    results_count=_extract_result_count(raw_response),
                    hearings=[],
                    records=[],
                    summary=raw_response
                )
        else:
            data = raw_response

        hearings = []
        records = []
        results_count = 0

        if isinstance(data, dict):
            # Handle hearings
            if 'hearings' in data:
                for hearing_data in data.get('hearings', []):
                    if isinstance(hearing_data, dict):
                        hearings.append(HearingSummary(
                            congress=hearing_data.get('congress', 0),
                            chamber=hearing_data.get('chamber', ''),
                            jacket_number=hearing_data.get('jacketNumber', ''),
                            title=hearing_data.get('title', ''),
                            committee=hearing_data.get('committee', ''),
                            date=hearing_data.get('date'),
                            url=hearing_data.get('url')
                        ))

            # Handle congressional records
            if 'records' in data:
                for record_data in data.get('records', []):
                    if isinstance(record_data, dict):
                        records.append(RecordSummary(
                            volume=record_data.get('volume', 0),
                            issue=record_data.get('issue', 0),
                            date=record_data.get('date', ''),
                            section=record_data.get('section', ''),
                            title=record_data.get('title', ''),
                            url=record_data.get('url')
                        ))

            results_count = len(hearings) + len(records)

        return RecordsHearingsResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            hearings=hearings,
            records=records,
            summary=f"Found {len(hearings)} hearings and {len(records)} records"
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return RecordsHearingsResponse(
            success=False,
            operation=operation,
            results_count=0,
            hearings=[],
            records=[],
            summary=f"Error processing response: {str(e)}"
        )

async def route_records_and_hearings_operation(ctx: Context, operation: str, **kwargs) -> RecordsHearingsResponse:
    """Route operation to appropriate internal function."""

    # Congressional Record operations
    if operation == "search_congressional_record":
        from ..congressional_record import search_congressional_record
        raw_response = await search_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_daily_congressional_record":
        from ..daily_congressional_record import search_daily_congressional_record
        raw_response = await search_daily_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_bound_congressional_record":
        from ..bound_congressional_record import search_bound_congressional_record
        raw_response = await search_bound_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # House communication operations
    elif operation == "search_house_communications":
        from ..house_communications import search_house_communications
        raw_response = await search_house_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_communication_details":
        from ..house_communications import get_house_communication_details
        raw_response = await get_house_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # House requirements operations
    elif operation == "search_house_requirements":
        from ..house_requirements import search_house_requirements
        raw_response = await search_house_requirements(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_details":
        from ..house_requirements import get_house_requirement_details
        raw_response = await get_house_requirement_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_matching_communications":
        from ..house_requirements import get_house_requirement_matching_communications
        raw_response = await get_house_requirement_matching_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Senate communication operations
    elif operation == "search_senate_communications":
        from ..senate_communications import search_senate_communications
        raw_response = await search_senate_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_senate_communication_details":
        from ..senate_communications import get_senate_communication_details
        raw_response = await get_senate_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Committee communication operations
    elif operation == "get_committee_communication_details":
        from ..committees import get_committee_communication_details
        raw_response = await get_committee_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Hearing operations
    elif operation == "search_hearings":
        from ..hearings import search_hearings
        raw_response = await search_hearings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress":
        from ..hearings import get_hearings_by_congress
        raw_response = await get_hearings_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress_and_chamber":
        from ..hearings import get_hearings_by_congress_and_chamber
        raw_response = await get_hearings_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_details":
        from ..hearings import get_hearing_details
        raw_response = await get_hearing_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_content":
        from ..hearings import get_hearing_content
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

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in records_and_hearings operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
