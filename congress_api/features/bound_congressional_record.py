# congress_api/features/bound_congressional_record.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_bound_record_item(item: Dict[str, Any]) -> str:
    """Formats a single bound congressional record item for display in a list."""
    lines = [
        f"Congress: {item.get('congress', 'N/A')}",
        f"Volume: {item.get('volumeNumber', 'N/A')}",
        f"Date: {item.get('date', 'N/A')}",
        f"Session: {item.get('sessionNumber', 'N/A')}",
        f"Update Date: {item.get('updateDate', 'N/A')}"
    ]
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_bound_record_detail(record_data: Dict[str, Any]) -> str:
    """Formats detailed information for a bound congressional record."""
    if not record_data or 'boundCongressionalRecord' not in record_data:
        return "No bound congressional record data available."
    
    records = record_data['boundCongressionalRecord']
    if not records:
        return "No bound congressional record found."
    
    # For detailed view, we'll format the first record in detail
    record = records[0]
    
    lines = [
        f"Bound Congressional Record - {record.get('date', 'N/A')}",
        f"Congress: {record.get('congress', 'N/A')}",
        f"Volume: {record.get('volumeNumber', 'N/A')}",
        f"Session: {record.get('sessionNumber', 'N/A')}",
        f"Update Date: {record.get('updateDate', 'N/A')}"
    ]
    
    # Add sections if available
    if 'sections' in record:
        lines.append("\nSections:")
        for section in record['sections']:
            lines.append(f"  - {section.get('name', 'N/A')}")
            lines.append(f"    Pages: {section.get('startPage', 'N/A')} - {section.get('endPage', 'N/A')}")
            
            if 'text' in section:
                lines.append("    Available formats:")
                for text_item in section['text']:
                    lines.append(f"      - {text_item.get('type', 'N/A')}: {text_item.get('url', 'N/A')}")
    
    # Add daily digest if available
    if 'dailyDigest' in record:
        digest = record['dailyDigest']
        lines.append("\nDaily Digest:")
        lines.append(f"  Pages: {digest.get('startPage', 'N/A')} - {digest.get('endPage', 'N/A')}")
        
        if 'text' in digest:
            lines.append("  Available formats:")
            for text_item in digest['text']:
                lines.append(f"    - {text_item.get('type', 'N/A')}: {text_item.get('url', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://bound-congressional-record/latest")
async def get_latest_bound_congressional_record() -> str:
    """
    Get the most recent bound congressional record issues.
    Returns the 10 most recently published issues by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "format": "json"
    }
    
    logger.debug("Fetching latest bound congressional record issues")
    data = await make_api_request("/bound-congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest bound congressional record issues: {data['error']}")
        return f"Error retrieving latest bound congressional record issues: {data['error']}"
    
    if 'boundCongressionalRecord' not in data:
        logger.warning("No boundCongressionalRecord field in response")
        return "No bound congressional record issues found."
    
    issues = data['boundCongressionalRecord']
    if not issues:
        logger.info("No bound congressional record issues found")
        return "No bound congressional record issues found."
    
    logger.info(f"Found {len(issues)} bound congressional record issues")
    lines = ["Latest Bound Congressional Record Issues:"]
    for issue in issues:
        lines.append("")
        lines.append(format_bound_record_item(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://bound-congressional-record/{year}")
async def get_bound_congressional_record_by_year(year: str) -> str:
    """
    Get bound congressional record issues for a specific year.
    
    Args:
        year: The year (e.g., "1990").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching bound congressional record issues for year {year}")
    data = await make_api_request(f"/bound-congressional-record/{year}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving bound congressional record issues for year {year}: {data['error']}")
        return f"Error retrieving bound congressional record issues for year {year}: {data['error']}"
    
    if 'boundCongressionalRecord' not in data:
        logger.warning(f"No boundCongressionalRecord field in response for year {year}")
        return f"No bound congressional record issues found for year {year}."
    
    issues = data['boundCongressionalRecord']
    if not issues:
        logger.info(f"No bound congressional record issues found for year {year}")
        return f"No bound congressional record issues found for year {year}."
    
    logger.info(f"Found {len(issues)} bound congressional record issues for year {year}")
    lines = [f"Bound Congressional Record Issues for {year}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_bound_record_item(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://bound-congressional-record/{year}/{month}")
async def get_bound_congressional_record_by_year_month(year: str, month: str) -> str:
    """
    Get bound congressional record issues for a specific year and month.
    
    Args:
        year: The year (e.g., "1990").
        month: The month (e.g., "5" for May).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching bound congressional record issues for year {year}, month {month}")
    data = await make_api_request(f"/bound-congressional-record/{year}/{month}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving bound congressional record issues for year {year}, month {month}: {data['error']}")
        return f"Error retrieving bound congressional record issues for year {year}, month {month}: {data['error']}"
    
    if 'boundCongressionalRecord' not in data:
        logger.warning(f"No boundCongressionalRecord field in response for year {year}, month {month}")
        return f"No bound congressional record issues found for year {year}, month {month}."
    
    issues = data['boundCongressionalRecord']
    if not issues:
        logger.info(f"No bound congressional record issues found for year {year}, month {month}")
        return f"No bound congressional record issues found for year {year}, month {month}."
    
    logger.info(f"Found {len(issues)} bound congressional record issues for year {year}, month {month}")
    lines = [f"Bound Congressional Record Issues for {year}-{month}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_bound_record_item(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://bound-congressional-record/{year}/{month}/{day}")
async def get_bound_congressional_record_by_date(year: str, month: str, day: str) -> str:
    """
    Get bound congressional record issues for a specific date.
    
    Args:
        year: The year (e.g., "1948").
        month: The month (e.g., "05" for May).
        day: The day (e.g., "19").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    date_str = f"{year}-{month}-{day}"
    logger.debug(f"Fetching bound congressional record issues for date {date_str}")
    data = await make_api_request(f"/bound-congressional-record/{year}/{month}/{day}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving bound congressional record issues for date {date_str}: {data['error']}")
        return f"Error retrieving bound congressional record issues for date {date_str}: {data['error']}"
    
    if 'boundCongressionalRecord' not in data:
        logger.warning(f"No boundCongressionalRecord field in response for date {date_str}")
        return f"No bound congressional record issues found for date {date_str}."
    
    issues = data['boundCongressionalRecord']
    if not issues:
        logger.info(f"No bound congressional record issues found for date {date_str}")
        return f"No bound congressional record issues found for date {date_str}."
    
    logger.info(f"Found {len(issues)} bound congressional record issues for date {date_str}")
    
    # For a specific date, we'll provide more detailed information
    lines = [f"Bound Congressional Record Issues for {date_str}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_bound_record_detail({"boundCongressionalRecord": [issue]}))
    
    return "\n".join(lines)

# --- MCP Tools ---

@mcp.tool("search_bound_congressional_record")
async def search_bound_congressional_record(
    year: Optional[str] = None,
    month: Optional[str] = None,
    day: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for bound congressional record issues based on various criteria.
    
    Args:
        year: Optional year to filter by (e.g., "1990").
        month: Optional month to filter by (e.g., "5" for May).
        day: Optional day to filter by (e.g., "19").
        limit: Maximum number of results to return (default: 10).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json",
        "limit": limit
    }
    
    # Construct the endpoint based on provided parameters
    endpoint = "/bound-congressional-record"
    if year:
        endpoint += f"/{year}"
        if month:
            endpoint += f"/{month}"
            if day:
                endpoint += f"/{day}"
    
    # Log the search parameters
    search_params = []
    if year:
        search_params.append(f"year={year}")
    if month:
        search_params.append(f"month={month}")
    if day:
        search_params.append(f"day={day}")
    if limit != 10:
        search_params.append(f"limit={limit}")
    
    search_str = ", ".join(search_params) if search_params else "default parameters"
    logger.debug(f"Searching bound congressional record with {search_str}")
    
    # Make the API request
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching bound congressional record: {data['error']}")
        return f"Error searching bound congressional record: {data['error']}"
    
    if 'boundCongressionalRecord' not in data:
        logger.warning("No boundCongressionalRecord field in response")
        return "No bound congressional record issues found matching the search criteria."
    
    issues = data['boundCongressionalRecord']
    if not issues:
        logger.info("No bound congressional record issues found matching the search criteria")
        return "No bound congressional record issues found matching the search criteria."
    
    logger.info(f"Found {len(issues)} bound congressional record issues matching the search criteria")
    
    # Format the results
    lines = ["Bound Congressional Record Search Results:"]
    for issue in issues:
        lines.append("")
        lines.append(format_bound_record_item(issue))
    
    return "\n".join(lines)
