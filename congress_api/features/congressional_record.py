# congress_api/features/congressional_record.py
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Reliability Framework Imports
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor
from ..core.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Defensive API wrapper for Congressional Record endpoints
async def safe_congressional_record_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Makes a defensive API request to Congressional Record endpoints with timeout handling,
    retry logic, and standardized error responses.
    
    Args:
        endpoint: The API endpoint to call
        ctx: The MCP context
        params: Optional query parameters
        
    Returns:
        Dict containing the API response or error information
    """
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint=endpoint,
        ctx=ctx,
        params=params or {},
        endpoint_type="congressional-record"
    )

# --- Formatting Helpers ---

def format_record_issue(issue: Dict[str, Any]) -> str:
    """Formats a single congressional record issue for display in a list."""
    lines = [
        f"Congress: {issue.get('Congress', 'N/A')}",
        f"Issue: {issue.get('Issue', 'N/A')}",
        f"Volume: {issue.get('Volume', 'N/A')}",
        f"Session: {issue.get('Session', 'N/A')}",
        f"Publish Date: {issue.get('PublishDate', 'N/A')}",
        f"ID: {issue.get('Id', 'N/A')}"
    ]
    
    # Add links if available
    if 'Links' in issue:
        links = issue['Links']
        lines.append("\nAvailable Sections:")
        
        for section_key, section_data in links.items():
            if section_data and 'Label' in section_data:
                lines.append(f"  - {section_data.get('Label', 'N/A')}")
                
                if 'PDF' in section_data and section_data['PDF']:
                    for pdf in section_data['PDF']:
                        part = pdf.get('Part', '')
                        part_text = f" (Part {part})" if part else ""
                        lines.append(f"    URL{part_text}: {pdf.get('Url', 'N/A')}")
    
    return "\n".join(lines)

def format_record_detail(record_data: Dict[str, Any]) -> str:
    """Formats detailed information for a congressional record."""
    if not record_data or 'Issues' not in record_data.get('Results', {}):
        return "No congressional record data available."
    
    issues = record_data['Results']['Issues']
    if not issues:
        return "No congressional record issues found."
    
    # For detailed view, we'll just format the first issue in detail
    issue = issues[0]
    
    lines = [
        f"Congressional Record - {issue.get('PublishDate', 'N/A')}",
        f"Congress: {issue.get('Congress', 'N/A')}",
        f"Volume: {issue.get('Volume', 'N/A')}",
        f"Issue: {issue.get('Issue', 'N/A')}",
        f"Session: {issue.get('Session', 'N/A')}",
        f"ID: {issue.get('Id', 'N/A')}"
    ]
    
    # Add links if available
    if 'Links' in issue:
        links = issue['Links']
        lines.append("\nAvailable Sections:")
        
        # Sort sections by Ordinal if available
        sections = []
        for section_key, section_data in links.items():
            if section_data and 'Label' in section_data:
                ordinal = section_data.get('Ordinal', 999)  # Default high value if no ordinal
                sections.append((ordinal, section_key, section_data))
        
        sections.sort()  # Sort by ordinal
        
        for _, section_key, section_data in sections:
            lines.append(f"  - {section_data.get('Label', 'N/A')}")
            
            if 'PDF' in section_data and section_data['PDF']:
                for pdf in section_data['PDF']:
                    part = pdf.get('Part', '')
                    part_text = f" (Part {part})" if part else ""
                    lines.append(f"    PDF{part_text}: {pdf.get('Url', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources (Static/Reference Data) ---

@require_paid_access
@mcp.resource("congress://congressional-record/latest")
async def get_latest_congressional_record(ctx: Context) -> str:
    """
    Get the most recent congressional record issues.
    Returns the 10 most recently published issues by default.
    """
    logger.info("Accessing latest congressional record issues resource")
    try:
        params = {
            "limit": 10,
            "format": "json"
        }
        
        data = await safe_congressional_record_request("/congressional-record", ctx, params=params)
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = f"Error retrieving latest congressional record issues: {data['error']}"
            logger.error(error_msg)
            error = CommonErrors.api_server_error(error_msg)
            return format_error_response(error)
        
        if 'Results' not in data or 'Issues' not in data['Results']:
            logger.warning("No Results.Issues field in response")
            error = CommonErrors.data_not_found("congressional record issues", "latest")
            return format_error_response(error)
        
        issues = data['Results']['Issues']
        if not issues:
            logger.info("No congressional record issues found")
            error = CommonErrors.data_not_found("congressional record issues", "latest")
            return format_error_response(error)
        
        # Deduplicate results
        deduplicated_issues = ResponseProcessor.deduplicate_results(
            issues, 
            key_fields=["Id", "PublishDate"]
        )
        
        logger.info(f"Found {len(deduplicated_issues)} congressional record issues")
        lines = ["Latest Congressional Record Issues:"]
        for issue in deduplicated_issues:
            lines.append("")
            lines.append(format_record_issue(issue))
        
        return "\n".join(lines)
    except Exception as e:
        error = CommonErrors.general_error(f"Error retrieving latest congressional record issues: {str(e)}")
        logger.error(f"Exception in get_latest_congressional_record: {str(e)}")
        return format_error_response(error)

# --- MCP Tools (Interactive/Parameterized Functions) ---

@require_paid_access
@mcp.tool("search_congressional_record")
async def search_congressional_record(
    ctx: Context,
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    congress: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search for congressional record issues based on various criteria.
    
    Args:
        year: Optional year the issue was published (e.g., 2022).
        month: Optional month the issue was published (1-12).
        day: Optional day the issue was published (1-31).
        congress: Optional Congress number (e.g., 117).
        limit: Maximum number of results to return (default: 10).
    """
    logger.info(f"Searching congressional record issues with criteria: year={year}, month={month}, day={day}, congress={congress}, limit={limit}")
    try:
        # Parameter validation
        limit_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
        if not limit_result.is_valid:
            error = CommonErrors.invalid_parameter("limit", limit, limit_result.error_message)
            return format_error_response(error)
        
        # Use sanitized limit value (auto-corrected if needed)
        if limit_result.sanitized_value is not None:
            limit = limit_result.sanitized_value
            if limit_result.error_message:  # There was an auto-correction
                logger.info(f"Limit auto-corrected: {limit_result.error_message}")
        
        # Validate congress number if provided
        if congress is not None:
            congress_result = ParameterValidator.validate_congress_number(congress)
            if not congress_result.is_valid:
                error = CommonErrors.invalid_parameter("congress", congress, congress_result.error_message)
                return format_error_response(error)
        
        # Validate date parameters if provided
        if any([year, month, day]):
            # Convert to strings for validation (the validator expects strings)
            year_str = str(year) if year is not None else None
            month_str = str(month) if month is not None else None
            day_str = str(day) if day is not None else None
            
            # Use the date components validator
            date_result = ParameterValidator.validate_date_components(year_str, month_str, day_str)
            if not date_result.is_valid:
                error = CommonErrors.invalid_parameter("date", f"{year}-{month}-{day}", date_result.error_message)
                return format_error_response(error)
        
        params = {
            "format": "json",
            "limit": limit
        }
        
        # Add optional parameters if provided
        if year:
            params["y"] = year
        if month:
            params["m"] = month
        if day:
            params["d"] = day
        if congress:
            params["congress"] = congress
        
        # Build descriptive search context
        search_context = []
        if year and month and day:
            search_context.append(f"date {year}-{month:02d}-{day:02d}")
        elif year:
            search_context.append(f"year {year}")
        if congress:
            search_context.append(f"Congress {congress}")
        
        context_str = f" for {' and '.join(search_context)}" if search_context else ""
        
        data = await safe_congressional_record_request("/congressional-record", ctx, params=params)
        logger.info(f"API response received{context_str}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = f"Error searching congressional record issues{context_str}: {data['error']}"
            logger.error(error_msg)
            error = CommonErrors.api_server_error(error_msg)
            return format_error_response(error)
        
        if 'Results' not in data or 'Issues' not in data['Results']:
            logger.warning(f"No Results.Issues field in response{context_str}")
            error = CommonErrors.data_not_found("congressional record issues", context_str.strip(" for ") if context_str else "search criteria")
            return format_error_response(error)
        
        issues = data['Results']['Issues']
        if not issues:
            logger.info(f"No congressional record issues found{context_str}")
            error = CommonErrors.data_not_found("congressional record issues", context_str.strip(" for ") if context_str else "search criteria")
            return format_error_response(error)
        
        # Deduplicate results
        deduplicated_issues = ResponseProcessor.deduplicate_results(
            issues, 
            key_fields=["Id", "PublishDate"]
        )
        
        logger.info(f"Found {len(deduplicated_issues)} congressional record issues{context_str}")
        lines = [f"Search Results - Congressional Record Issues{context_str}:"]
        for issue in deduplicated_issues:
            lines.append("")
            lines.append(format_record_issue(issue))
        
        return "\n".join(lines)
    except Exception as e:
        error = CommonErrors.general_error(f"Error searching congressional record issues: {str(e)}")
        logger.error(f"Exception in search_congressional_record: {str(e)}")
        return format_error_response(error)
