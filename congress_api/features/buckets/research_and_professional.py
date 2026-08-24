"""
Congressional Research and Professional - Consolidated MCP bucket tool for professional research.

This bucket consolidates specialized research tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from ...core.exceptions import CongressionalAPIError
from ...mcp_app import mcp
from ...core.operation_routing import validate_operation_kwargs
from ...models.responses import ResearchProfessionalResponse, ResearchSummary
from ...utils.response_converters import _extract_result_count, structured_items_of

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> ResearchProfessionalResponse:
    """Build the structured response; typed lists come from the impl's real items."""
    try:
        kind, items = structured_items_of(raw_response)
        if items is not None:
            materials = []
            for m in items:
                if kind == "congress":
                    start = m.get("startYear")
                    end = m.get("endYear")
                    materials.append(ResearchSummary(
                        title=m.get("name", ""), type="Congress",
                        date=f"{start}-{end}" if start else None,
                        url=m.get("url")))
                else:
                    materials.append(ResearchSummary(
                        title=m.get("title", ""), type="CRS Report",
                        date=m.get("publishDate") or m.get("updateDate"),
                        status=m.get("status"),
                        url=m.get("url")))
            return ResearchProfessionalResponse(
                success=True, operation=operation, results_count=len(items),
                research_materials=materials, summary=str(raw_response))

        return ResearchProfessionalResponse(
            success=True, operation=operation,
            results_count=_extract_result_count(raw_response),
            research_materials=[], summary=str(raw_response))
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return ResearchProfessionalResponse(
            success=False, operation=operation, results_count=0,
            research_materials=[], summary=f"Error processing response: {str(e)}")

async def route_research_and_professional_operation(ctx: Context, operation: str, **kwargs) -> ResearchProfessionalResponse:
    """Route operation to appropriate internal function."""

    # Congress information operations
    if operation == "get_congress_info":
        from ..congress_info import get_congress_info
        validate_operation_kwargs(get_congress_info, kwargs, operation)
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_congresses":
        from ..congress_info import search_congresses
        validate_operation_kwargs(search_congresses, kwargs, operation)
        raw_response = await search_congresses(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_congress_info_enhanced":
        # Enhanced version with additional analytics
        from ..congress_info import get_congress_info
        # Add detailed=True for enhanced mode
        kwargs['detailed'] = True
        validate_operation_kwargs(get_congress_info, kwargs, operation)
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Professional research operations
    elif operation == "search_crs_reports":
        from ..crs_reports import search_crs_reports
        validate_operation_kwargs(search_crs_reports, kwargs, operation)
        raw_response = await search_crs_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)


    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool(
    "research_and_professional",
    title="Congressional Research and Professional - CRS reports and Congress analytics",
)
async def research_and_professional(
    ctx: Context,
    operation: str,
    # Congress information parameters
    congress: Optional[int] = None,
    current: Optional[bool] = None,
    limit: Optional[int] = None,
    detailed: Optional[bool] = None,
    format_type: Optional[str] = None,
    # Congress search parameters
    keywords: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    # CRS report parameters
    report_number: Optional[str] = None
) -> ResearchProfessionalResponse:
    """
    Congressional Research and Professional - Access CRS reports and enhanced Congress analytics.

    CONGRESS INFORMATION (3 operations):
    • get_congress_info - Basic Congress information and metadata
    • get_congress_info_enhanced - Advanced analytics with detailed insights
    • search_congresses - Historical Congress search with trend analysis

    PROFESSIONAL RESEARCH (1 operation):
    • search_crs_reports - CRS reports: exact report_number lookup, or a
      title filter over the 250 most recently updated reports (not full-text)

    Key params: operation, congress, keywords, report_number, start_year, end_year
    Returns professional-grade research data with enhanced analytics and historical insights.
    """
    try:
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'congress': congress,
            'current': current,
            'limit': limit,
            'detailed': detailed,
            'format_type': format_type,
            'keywords': keywords,
            'start_year': start_year,
            'end_year': end_year,
            'report_number': report_number
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value

        # Route to appropriate internal function. route_research_and_professional_operation
        # already returns a fully-converted ResearchProfessionalResponse (it calls
        # _convert_to_structured_response internally) — re-converting it here fails the
        # isinstance(raw_response, str) check and silently discards all data, always
        # returning empty/zero results regardless of what the API actually returned.
        return await route_research_and_professional_operation(ctx, operation, **operation_kwargs)

    except CongressionalAPIError as e:
        # Typed Congress.gov error from a handler with no try/except of its own:
        # surface the classification instead of a generic failure.
        raise ToolError(f"{e.error_response.error_code}: {e.error_response.message}")
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in research_and_professional operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
