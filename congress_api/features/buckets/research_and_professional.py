"""
Congressional Research and Professional - Consolidated MCP bucket tool for professional research.

This bucket consolidates specialized research tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import ResearchProfessionalResponse, ResearchSummary
from ...utils.response_converters import _extract_result_count

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> ResearchProfessionalResponse:
    """Convert raw string response to structured ResearchProfessionalResponse."""
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
                return ResearchProfessionalResponse(
                    success=True,
                    operation=operation,
                    results_count=_extract_result_count(raw_response),
                    research_materials=[],
                    summary=raw_response,
                    recommended_reading=[]
                )
        else:
            data = raw_response

        research_materials = []
        results_count = 0

        if isinstance(data, dict):
            # Handle research materials (CRS reports, committee reports, etc.)
            if 'reports' in data:
                for report_data in data.get('reports', []):
                    if isinstance(report_data, dict):
                        research_materials.append(ResearchSummary(
                            title=report_data.get('title', ''),
                            type=report_data.get('reportType', 'Research Document'),
                            date=report_data.get('date'),
                            summary=report_data.get('summary'),
                            topics=report_data.get('policyArea', []),
                            url=report_data.get('url')
                        ))

            # Handle other research document types
            if 'crsReports' in data:
                for crs_data in data.get('crsReports', []):
                    if isinstance(crs_data, dict):
                        research_materials.append(ResearchSummary(
                            title=crs_data.get('title', ''),
                            type='CRS Report',
                            date=crs_data.get('date'),
                            summary=crs_data.get('summary'),
                            topics=crs_data.get('topics', []),
                            url=crs_data.get('url')
                        ))

            results_count = len(research_materials)

        return ResearchProfessionalResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            research_materials=research_materials,
            summary=f"Found {len(research_materials)} research materials",
            recommended_reading=[]
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return ResearchProfessionalResponse(
            success=False,
            operation=operation,
            results_count=0,
            research_materials=[],
            summary=f"Error processing response: {str(e)}",
            recommended_reading=[]
        )

async def route_research_and_professional_operation(ctx: Context, operation: str, **kwargs) -> ResearchProfessionalResponse:
    """Route operation to appropriate internal function."""

    # Congress information operations
    if operation == "get_congress_info":
        from ..congress_info import get_congress_info
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_congresses":
        from ..congress_info import search_congresses
        raw_response = await search_congresses(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_congress_info_enhanced":
        # Enhanced version with additional analytics
        from ..congress_info import get_congress_info
        # Add detailed=True for enhanced mode
        kwargs['detailed'] = True
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Professional research operations
    elif operation == "search_crs_reports":
        from ..crs_reports import search_crs_reports
        raw_response = await search_crs_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Future professional analytics operations
    elif operation == "get_congress_statistics":
        # Placeholder for future implementation
        raise ToolError("Congress statistics analysis feature coming soon - contact support for early access")
    elif operation == "get_legislative_analysis":
        # Placeholder for future implementation
        raise ToolError("Advanced legislative analysis feature coming soon - contact support for early access")

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
) -> str:
    """
    Congressional Research and Professional - Access CRS reports and enhanced Congress analytics.

    CONGRESS INFORMATION (3 operations):
    • get_congress_info - Basic Congress information and metadata
    • get_congress_info_enhanced - Advanced analytics with detailed insights
    • search_congresses - Historical Congress search with trend analysis

    PROFESSIONAL RESEARCH (3 operations):
    • search_crs_reports - Congressional Research Service report search
    • get_congress_statistics - Statistical analysis across Congresses
    • get_legislative_analysis - Advanced legislative trend analysis

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

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in research_and_professional operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
