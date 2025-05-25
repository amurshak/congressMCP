# congress_api/features/congressional_record.py
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

# --- MCP Resources ---

@mcp.resource("congress://congressional-record/latest")
async def get_latest_congressional_record() -> str:
    """
    Get the most recent congressional record issues.
    Returns the 10 most recently published issues by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "format": "json"
    }
    
    logger.debug("Fetching latest congressional record issues")
    data = await make_api_request("/congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest congressional record issues: {data['error']}")
        return f"Error retrieving latest congressional record issues: {data['error']}"
    
    if 'Results' not in data or 'Issues' not in data['Results']:
        logger.warning("No Results.Issues field in response")
        return "No congressional record issues found."
    
    issues = data['Results']['Issues']
    if not issues:
        logger.info("No congressional record issues found")
        return "No congressional record issues found."
    
    logger.info(f"Found {len(issues)} congressional record issues")
    lines = ["Latest Congressional Record Issues:"]
    for issue in issues:
        lines.append("")
        lines.append(format_record_issue(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://congressional-record/date/{year}/{month}/{day}")
async def get_congressional_record_by_date(year: int, month: int, day: int) -> str:
    """
    Get congressional record issues for a specific date.
    
    Args:
        year: The year (e.g., 2022).
        month: The month (1-12).
        day: The day (1-31).
    """
    ctx = mcp.get_context()
    params = {
        "y": year,
        "m": month,
        "d": day,
        "format": "json"
    }
    
    date_str = f"{year}-{month:02d}-{day:02d}"
    logger.debug(f"Fetching congressional record issues for date {date_str}")
    data = await make_api_request("/congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving congressional record issues for date {date_str}: {data['error']}")
        return f"Error retrieving congressional record issues for date {date_str}: {data['error']}"
    
    if 'Results' not in data or 'Issues' not in data['Results']:
        logger.warning(f"No Results.Issues field in response for date {date_str}")
        return f"No congressional record issues found for date {date_str}."
    
    issues = data['Results']['Issues']
    if not issues:
        logger.info(f"No congressional record issues found for date {date_str}")
        return f"No congressional record issues found for date {date_str}."
    
    logger.info(f"Found {len(issues)} congressional record issues for date {date_str}")
    lines = [f"Congressional Record Issues for {date_str}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_record_issue(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://congressional-record/congress/{congress}")
async def get_congressional_record_by_congress(congress: int) -> str:
    """
    Get congressional record issues for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    ctx = mcp.get_context()
    params = {
        "congress": congress,
        "limit": 20,
        "format": "json"
    }
    
    logger.debug(f"Fetching congressional record issues for Congress {congress}")
    data = await make_api_request("/congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving congressional record issues for Congress {congress}: {data['error']}")
        return f"Error retrieving congressional record issues for Congress {congress}: {data['error']}"
    
    if 'Results' not in data or 'Issues' not in data['Results']:
        logger.warning(f"No Results.Issues field in response for Congress {congress}")
        return f"No congressional record issues found for Congress {congress}."
    
    issues = data['Results']['Issues']
    if not issues:
        logger.info(f"No congressional record issues found for Congress {congress}")
        return f"No congressional record issues found for Congress {congress}."
    
    logger.info(f"Found {len(issues)} congressional record issues for Congress {congress}")
    lines = [f"Congressional Record Issues for Congress {congress}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_record_issue(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://congressional-record/issue/{id}")
async def get_congressional_record_by_id(id: int) -> str:
    """
    Get detailed information for a specific congressional record issue.
    
    Args:
        id: The ID of the congressional record issue.
    """
    ctx = mcp.get_context()
    params = {
        "id": id,
        "format": "json"
    }
    
    logger.debug(f"Fetching details for congressional record issue {id}")
    data = await make_api_request("/congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving congressional record issue {id}: {data['error']}")
        return f"Error retrieving congressional record issue {id}: {data['error']}"
    
    return format_record_detail(data)

# --- MCP Tools ---

@mcp.tool("search_congressional_record")
async def search_congressional_record(
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
    ctx = mcp.get_context()
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
    
    date_str = ""
    if year and month and day:
        date_str = f" for date {year}-{month:02d}-{day:02d}"
    elif congress:
        date_str = f" for Congress {congress}"
    
    logger.debug(f"Searching congressional record issues{date_str} with params: {params}")
    data = await make_api_request("/congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching congressional record issues{date_str}: {data['error']}")
        return f"Error searching congressional record issues{date_str}: {data['error']}"
    
    if 'Results' not in data or 'Issues' not in data['Results']:
        logger.warning(f"No Results.Issues field in response{date_str}")
        return f"No congressional record issues found{date_str}."
    
    issues = data['Results']['Issues']
    if not issues:
        logger.info(f"No congressional record issues found{date_str}")
        return f"No congressional record issues found{date_str}."
    
    logger.info(f"Found {len(issues)} congressional record issues{date_str}")
    lines = [f"Search Results - Congressional Record Issues{date_str}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_record_issue(issue))
    
    return "\n".join(lines)
