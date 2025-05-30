# congress_api/features/committee_meetings.py
import logging
from typing import Dict, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_committee_meeting_item(meeting_item: Dict[str, Any]) -> str:
    """Formats a single committee meeting item for display in a list."""
    lines = [
        f"Chamber: {meeting_item.get('chamber', 'N/A')}",
        f"Committee: {meeting_item.get('committee', {}).get('name', 'N/A')}",
        f"Congress: {meeting_item.get('congress', 'N/A')}",
        f"Event ID: {meeting_item.get('eventId', 'N/A')}",
        f"Meeting Date: {meeting_item.get('meetingDate', 'N/A')}",
        f"Title: {meeting_item.get('title', 'N/A')}",
        f"Type: {meeting_item.get('type', 'N/A')}",
        f"Update Date: {meeting_item.get('updateDate', 'N/A')}",
        f"URL: {meeting_item.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_committee_meeting_detail(meeting_item: Dict[str, Any]) -> str:
    """Formats detailed information for a single committee meeting."""
    lines = [
        f"Chamber: {meeting_item.get('chamber', 'N/A')}",
        f"Committee: {meeting_item.get('committee', {}).get('name', 'N/A')} (System Code: {meeting_item.get('committee', {}).get('systemCode', 'N/A')})",
        f"Congress: {meeting_item.get('congress', 'N/A')}",
        f"Event ID: {meeting_item.get('eventId', 'N/A')}",
        f"Location: {meeting_item.get('location', 'N/A')}",
        f"Meeting Date: {meeting_item.get('meetingDate', 'N/A')}",
        f"Title: {meeting_item.get('title', 'N/A')}",
        f"Type: {meeting_item.get('type', 'N/A')}",
        f"Update Date: {meeting_item.get('updateDate', 'N/A')}"
    ]
    
    if 'witnesses' in meeting_item and meeting_item['witnesses']:
        lines.append("\nWitnesses:")
        for witness in meeting_item['witnesses']:
            witness_name = f"{witness.get('firstName', '')} {witness.get('lastName', '')}".strip()
            lines.append(f"  - {witness_name}")
            if witness.get('organization'):
                lines.append(f"    Organization: {witness.get('organization')}")
            if witness.get('position'):
                lines.append(f"    Position: {witness.get('position')}")
    
    if 'documents' in meeting_item and meeting_item['documents']:
        lines.append("\nDocuments:")
        for document in meeting_item['documents']:
            lines.append(f"  - {document.get('title', 'N/A')} (Type: {document.get('type', 'N/A')})")
            lines.append(f"    URL: {document.get('url', 'N/A')}")
        
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://committee-meetings/latest")
async def get_latest_committee_meetings(ctx: Context) -> str:
    """
    Get a list of the most recent committee meetings.
    Returns the 10 most recently updated meetings by default.
    """
    params = {
        "limit": 10,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug("Fetching latest committee meetings")
    data = await make_api_request("/committee-meeting", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest committee meetings: {data['error']}")
        return f"Error retrieving latest committee meetings: {data['error']}"
    
    meetings = data.get("committeeMeetings", [])
    if not meetings:
        logger.info("No committee meetings found")
        return "No committee meetings found."
    
    logger.info(f"Found {len(meetings)} committee meetings")
    lines = ["Latest Committee Meetings:"]
    for meeting_item in meetings:
        lines.append("")
        lines.append(format_committee_meeting_item(meeting_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-meetings/{congress}")
async def get_committee_meetings_by_congress(ctx: Context, congress: int) -> str:
    """
    Get committee meetings for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee meetings for Congress {congress}")
    data = await make_api_request(f"/committee-meeting/{congress}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee meetings for Congress {congress}: {data['error']}")
        return f"Error retrieving committee meetings for Congress {congress}: {data['error']}"
    
    meetings = data.get("committeeMeetings", [])
    if not meetings:
        logger.info(f"No committee meetings found for Congress {congress}")
        return f"No committee meetings found for Congress {congress}."
    
    logger.info(f"Found {len(meetings)} committee meetings for Congress {congress}")
    lines = [f"Committee Meetings for Congress {congress}:"]
    for meeting_item in meetings:
        lines.append("")
        lines.append(format_committee_meeting_item(meeting_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-meetings/{congress}/{chamber}")
async def get_committee_meetings_by_congress_and_chamber(ctx: Context, congress: int, chamber: str) -> str:
    """
    Get committee meetings for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
    """
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee meetings for Congress {congress}, Chamber {chamber}")
    data = await make_api_request(f"/committee-meeting/{congress}/{chamber}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee meetings for Congress {congress}, Chamber {chamber}: {data['error']}")
        return f"Error retrieving committee meetings for Congress {congress}, Chamber {chamber}: {data['error']}"
    
    meetings = data.get("committeeMeetings", [])
    if not meetings:
        logger.info(f"No committee meetings found for Congress {congress}, Chamber {chamber}")
        return f"No committee meetings found for Congress {congress}, Chamber {chamber}."
    
    logger.info(f"Found {len(meetings)} committee meetings for Congress {congress}, Chamber {chamber}")
    lines = [f"Committee Meetings for Congress {congress}, Chamber {chamber}:"]
    for meeting_item in meetings:
        lines.append("")
        lines.append(format_committee_meeting_item(meeting_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-meetings/{congress}/{chamber}/{committee_code}")
async def get_committee_meetings_by_committee(ctx: Context, congress: int, chamber: str, committee_code: str) -> str:
    """
    Get committee meetings for a specific committee.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        committee_code: The committee system code (e.g., "hsag00").
    """
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee meetings for Congress {congress}, Chamber {chamber}, Committee {committee_code}")
    data = await make_api_request(f"/committee-meeting/{congress}/{chamber}/{committee_code}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee meetings: {data['error']}")
        return f"Error retrieving committee meetings: {data['error']}"
    
    meetings = data.get("committeeMeetings", [])
    if not meetings:
        logger.info(f"No committee meetings found for Congress {congress}, Chamber {chamber}, Committee {committee_code}")
        return f"No committee meetings found for Congress {congress}, Chamber {chamber}, Committee {committee_code}."
    
    logger.info(f"Found {len(meetings)} committee meetings for Congress {congress}, Chamber {chamber}, Committee {committee_code}")
    lines = [f"Committee Meetings for Congress {congress}, Chamber {chamber}, Committee {committee_code}:"]
    for meeting_item in meetings:
        lines.append("")
        lines.append(format_committee_meeting_item(meeting_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-meetings/{congress}/{chamber}/{committee_code}/{event_id}")
async def get_committee_meeting_details(ctx: Context, congress: int, chamber: str, committee_code: str, event_id: int) -> str:
    """
    Get detailed information for a specific committee meeting.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        committee_code: The committee system code (e.g., "hsag00").
        event_id: The event ID for the meeting.
    """
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching details for committee meeting {congress}/{chamber}/{committee_code}/{event_id}")
    data = await make_api_request(f"/committee-meeting/{congress}/{chamber}/{committee_code}/{event_id}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee meeting details: {data['error']}")
        return f"Error retrieving committee meeting details: {data['error']}"
    
    if "committeeMeeting" not in data:
        logger.warning(f"No committeeMeeting field in response for {congress}/{chamber}/{committee_code}/{event_id}")
        return f"No committee meeting found for Congress {congress}, Chamber {chamber}, Committee {committee_code}, Event ID {event_id}."
    
    meeting_data = data.get("committeeMeeting", {})
    if not meeting_data:
        logger.warning(f"Empty committeeMeeting data for {congress}/{chamber}/{committee_code}/{event_id}")
        return f"No committee meeting data found for Congress {congress}, Chamber {chamber}, Committee {committee_code}, Event ID {event_id}."
    
    logger.info(f"Successfully retrieved committee meeting details for {congress}/{chamber}/{committee_code}/{event_id}")
    return format_committee_meeting_detail(meeting_data)

# --- MCP Tools ---

@mcp.tool("search_committee_meetings")
async def search_committee_meetings(
    ctx: Context,
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    committee_code: Optional[str] = None,
    scheduled_from: Optional[str] = None,
    scheduled_to: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc"
) -> str:
    """
    Search for committee meetings based on various criteria.
    
    Args:
        keywords: Keywords to search for in meeting information.
        congress: Optional Congress number (e.g., 117).
        chamber: Optional chamber of Congress ("house" or "senate").
        committee_code: Optional committee system code (e.g., "hsag00").
        scheduled_from: Optional start date for filtering by meeting date (YYYY-MM-DDT00:00:00Z).
        scheduled_to: Optional end date for filtering by meeting date (YYYY-MM-DDT00:00:00Z).
        limit: Maximum number of results to return (default: 10).
        sort: Sort order (default: "updateDate+desc").
    """
    params = {
        "format": "json",
        "limit": limit,
        "sort": sort
    }
    
    # Add optional parameters if provided
    if keywords:
        params["q"] = keywords
    if scheduled_from:
        params["scheduledFrom"] = scheduled_from
    if scheduled_to:
        params["scheduledTo"] = scheduled_to
    
    # Determine the endpoint based on provided parameters
    endpoint = "/committee-meeting"
    if congress:
        endpoint = f"{endpoint}/{congress}"
        if chamber:
            endpoint = f"{endpoint}/{chamber}"
            if committee_code:
                endpoint = f"{endpoint}/{committee_code}"
    
    logger.debug(f"Searching committee meetings with endpoint: {endpoint}, params: {params}")
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching committee meetings: {data['error']}")
        return f"Error searching committee meetings: {data['error']}"
    
    meetings = data.get("committeeMeetings", [])
    if not meetings:
        logger.info("No committee meetings found matching the search criteria")
        return "No committee meetings found matching the search criteria."
    
    logger.info(f"Found {len(meetings)} committee meetings matching the search criteria")
    lines = ["Search Results - Committee Meetings:"]
    for meeting_item in meetings:
        lines.append("")
        lines.append(format_committee_meeting_item(meeting_item))
    
    return "\n".join(lines)
