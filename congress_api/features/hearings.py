# congress_api/features/hearings.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_hearing_item(hearing_item: Dict[str, Any]) -> str:
    """Formats a single hearing item for display in a list."""
    lines = [
        f"Chamber: {hearing_item.get('chamber', 'N/A')}",
        f"Congress: {hearing_item.get('congress', 'N/A')}",
        f"Jacket Number: {hearing_item.get('jacketNumber', 'N/A')}",
        f"Update Date: {hearing_item.get('updateDate', 'N/A')}",
        f"URL: {hearing_item.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_hearing_detail(hearing_item: Dict[str, Any]) -> str:
    """Formats detailed information for a single hearing."""
    lines = [
        f"Title: {hearing_item.get('title', 'N/A')}",
        f"Chamber: {hearing_item.get('chamber', 'N/A')}",
        f"Congress: {hearing_item.get('congress', 'N/A')}",
        f"Citation: {hearing_item.get('citation', 'N/A')}",
        f"Jacket Number: {hearing_item.get('jacketNumber', 'N/A')}",
        f"Library of Congress Identifier: {hearing_item.get('libraryOfCongressIdentifier', 'N/A')}",
        f"Update Date: {hearing_item.get('updateDate', 'N/A')}"
    ]
    
    # Add dates if available
    if 'dates' in hearing_item and hearing_item['dates']:
        dates = [date.get('date', 'N/A') for date in hearing_item['dates']]
        lines.append(f"Dates: {', '.join(dates)}")
    
    # Add associated meeting if available
    if 'associatedMeeting' in hearing_item and hearing_item['associatedMeeting']:
        meeting = hearing_item['associatedMeeting']
        lines.append(f"Associated Meeting: Event ID {meeting.get('eventId', 'N/A')}")
        lines.append(f"  URL: {meeting.get('url', 'N/A')}")
    
    # Add committees if available
    if 'committees' in hearing_item and hearing_item['committees']:
        lines.append("\nCommittees:")
        for committee in hearing_item['committees']:
            lines.append(f"  - {committee.get('name', 'N/A')} (System Code: {committee.get('systemCode', 'N/A')})")
            lines.append(f"    URL: {committee.get('url', 'N/A')}")
    
    # Add formats if available
    if 'formats' in hearing_item and hearing_item['formats']:
        lines.append("\nFormats:")
        for format_item in hearing_item['formats']:
            lines.append(f"  - {format_item.get('type', 'N/A')}")
            lines.append(f"    URL: {format_item.get('url', 'N/A')}")
        
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://hearings/latest")
async def get_latest_hearings() -> str:
    """
    Get a list of the most recent hearings.
    Returns the 10 most recently updated hearings by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug("Fetching latest hearings")
    data = await make_api_request("/hearing", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest hearings: {data['error']}")
        return f"Error retrieving latest hearings: {data['error']}"
    
    hearings = data.get("hearings", [])
    if not hearings:
        logger.info("No hearings found")
        return "No hearings found."
    
    logger.info(f"Found {len(hearings)} hearings")
    lines = ["Latest Hearings:"]
    for hearing_item in hearings:
        lines.append("")
        lines.append(format_hearing_item(hearing_item))
    
    return "\n".join(lines)

@mcp.resource("congress://hearings/{congress}")
async def get_hearings_by_congress(congress: int) -> str:
    """
    Get hearings for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 116).
    """
    ctx = mcp.get_context()
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching hearings for Congress {congress}")
    data = await make_api_request(f"/hearing/{congress}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving hearings for Congress {congress}: {data['error']}")
        return f"Error retrieving hearings for Congress {congress}: {data['error']}"
    
    hearings = data.get("hearings", [])
    if not hearings:
        logger.info(f"No hearings found for Congress {congress}")
        return f"No hearings found for Congress {congress}."
    
    logger.info(f"Found {len(hearings)} hearings for Congress {congress}")
    lines = [f"Hearings for Congress {congress}:"]
    for hearing_item in hearings:
        lines.append("")
        lines.append(format_hearing_item(hearing_item))
    
    return "\n".join(lines)

@mcp.resource("congress://hearings/{congress}/{chamber}")
async def get_hearings_by_congress_and_chamber(congress: int, chamber: str) -> str:
    """
    Get hearings for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 116).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
    """
    ctx = mcp.get_context()
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching hearings for Congress {congress}, Chamber {chamber}")
    data = await make_api_request(f"/hearing/{congress}/{chamber}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving hearings for Congress {congress}, Chamber {chamber}: {data['error']}")
        return f"Error retrieving hearings for Congress {congress}, Chamber {chamber}: {data['error']}"
    
    hearings = data.get("hearings", [])
    if not hearings:
        logger.info(f"No hearings found for Congress {congress}, Chamber {chamber}")
        return f"No hearings found for Congress {congress}, Chamber {chamber}."
    
    logger.info(f"Found {len(hearings)} hearings for Congress {congress}, Chamber {chamber}")
    lines = [f"Hearings for Congress {congress}, Chamber {chamber}:"]
    for hearing_item in hearings:
        lines.append("")
        lines.append(format_hearing_item(hearing_item))
    
    return "\n".join(lines)

@mcp.resource("congress://hearings/{congress}/{chamber}/{jacket_number}")
async def get_hearing_details(congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get detailed information for a specific hearing.
    
    Args:
        congress: The Congress number (e.g., 116).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
        jacket_number: The jacket number for the hearing.
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching details for hearing {congress}/{chamber}/{jacket_number}")
    data = await make_api_request(f"/hearing/{congress}/{chamber}/{jacket_number}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving hearing details: {data['error']}")
        return f"Error retrieving hearing details: {data['error']}"
    
    if "hearing" not in data:
        logger.warning(f"No hearing field in response for {congress}/{chamber}/{jacket_number}")
        return f"No hearing found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
    
    hearing_data = data.get("hearing", {})
    if not hearing_data:
        logger.warning(f"Empty hearing data for {congress}/{chamber}/{jacket_number}")
        return f"No hearing data found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
    
    logger.info(f"Successfully retrieved hearing details for {congress}/{chamber}/{jacket_number}")
    return format_hearing_detail(hearing_data)

# --- MCP Tools ---

@mcp.tool("search_hearings")
async def search_hearings(
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc"
) -> str:
    """
    Search for hearings based on various criteria.
    
    Args:
        keywords: Keywords to search for in hearing information.
        congress: Optional Congress number (e.g., 116).
        chamber: Optional chamber of Congress ("house", "senate", or "nochamber").
        from_date_time: Optional start date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        to_date_time: Optional end date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        limit: Maximum number of results to return (default: 10).
        sort: Sort order (default: "updateDate+desc").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json",
        "limit": limit,
        "sort": sort
    }
    
    # Add optional parameters if provided
    if keywords:
        params["q"] = keywords
    if from_date_time:
        params["fromDateTime"] = from_date_time
    if to_date_time:
        params["toDateTime"] = to_date_time
    
    # Determine the endpoint based on provided parameters
    endpoint = "/hearing"
    if congress:
        endpoint = f"{endpoint}/{congress}"
        if chamber:
            endpoint = f"{endpoint}/{chamber}"
    
    logger.debug(f"Searching hearings with endpoint: {endpoint}, params: {params}")
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching hearings: {data['error']}")
        return f"Error searching hearings: {data['error']}"
    
    hearings = data.get("hearings", [])
    if not hearings:
        logger.info("No hearings found matching the search criteria")
        return "No hearings found matching the search criteria."
    
    logger.info(f"Found {len(hearings)} hearings matching the search criteria")
    lines = ["Search Results - Hearings:"]
    for hearing_item in hearings:
        lines.append("")
        lines.append(format_hearing_item(hearing_item))
    
    return "\n".join(lines)
