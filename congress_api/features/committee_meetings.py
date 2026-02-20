# congress_api/features/committee_meetings.py
import logging
from typing import Dict, Any, Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.api_wrapper import safe_committee_meetings_request
from ..core.validators import ParameterValidator
from ..core.response_utils import ResponseProcessor
from ..core.exceptions import format_error_response, CommonErrors, APIErrorResponse
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_committee_meeting_item(meeting_item: Dict[str, Any]) -> str:
    """Formats a single committee meeting item for display in a list."""
    lines = []
    
    # Always show these core fields
    if meeting_item.get('chamber'):
        lines.append(f"Chamber: {meeting_item['chamber'].title()}")
    
    if meeting_item.get('congress'):
        lines.append(f"Congress: {meeting_item['congress']}")
        
    if meeting_item.get('eventId'):
        lines.append(f"Event ID: {meeting_item['eventId']}")
    
    # Only show these fields if they have meaningful data
    committee_info = meeting_item.get('committee', {})
    if committee_info and committee_info.get('name'):
        lines.append(f"Committee: {committee_info['name']}")
    elif committee_info and committee_info.get('systemCode'):
        lines.append(f"Committee Code: {committee_info['systemCode']}")
    
    if meeting_item.get('title') and meeting_item['title'].strip():
        lines.append(f"Title: {meeting_item['title']}")
        
    if meeting_item.get('meetingDate') and meeting_item['meetingDate'].strip():
        lines.append(f"Meeting Date: {meeting_item['meetingDate']}")
        
    if meeting_item.get('type') and meeting_item['type'].strip():
        lines.append(f"Type: {meeting_item['type']}")
    
    # Always show update date and URL if available
    if meeting_item.get('updateDate'):
        lines.append(f"Update Date: {meeting_item['updateDate']}")
        
    if meeting_item.get('url'):
        lines.append(f"URL: {meeting_item['url']}")
    
    # Add note about getting more details
    if meeting_item.get('eventId') and meeting_item.get('congress') and meeting_item.get('chamber'):
        lines.append(f" Use get_committee_meeting_details for full information")
    
    return "\n".join(lines)

def format_committee_meeting_detail(meeting_item: Dict[str, Any]) -> str:
    """Formats detailed information for a single committee meeting."""
    
    # Handle committees (can be array or single object)
    committees_info = "N/A"
    committees = meeting_item.get('committees', [])
    if committees:
        # Multiple committees
        committee_names = []
        for committee in committees:
            name = committee.get('name', 'Unknown')
            system_code = committee.get('systemCode', 'N/A')
            committee_names.append(f"{name} ({system_code})")
        committees_info = ", ".join(committee_names)
    elif meeting_item.get('committee'):
        # Single committee (legacy format)
        committee = meeting_item['committee']
        name = committee.get('name', 'Unknown')
        system_code = committee.get('systemCode', 'N/A')
        committees_info = f"{name} ({system_code})"
    
    lines = [
        f"Chamber: {meeting_item.get('chamber', 'N/A')}",
        f"Committee(s): {committees_info}",
        f"Congress: {meeting_item.get('congress', 'N/A')}",
        f"Event ID: {meeting_item.get('eventId', 'N/A')}",
        f"Location: {meeting_item.get('location', 'N/A')}",
        f"Meeting Date: {meeting_item.get('date', meeting_item.get('meetingDate', 'N/A'))}",
        f"Title: {meeting_item.get('title', 'N/A')}",
        f"Type: {meeting_item.get('type', 'N/A')}",
        f"Update Date: {meeting_item.get('updateDate', 'N/A')}"
    ]
    
    if 'witnesses' in meeting_item and meeting_item['witnesses']:
        lines.append("\nWitnesses:")
        for witness in meeting_item['witnesses']:
            witness_name = f"{witness.get('firstName', '')} {witness.get('lastName', '')}".strip()
            if not witness_name:
                witness_name = witness.get('name', 'Unknown')
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

# --- MCP Tools ---

# @require_paid_access
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
    
    try:
        logger.debug("Fetching latest committee meetings")
        data = await safe_committee_meetings_request("/committee-meeting", ctx, params)
        
        if "error" in data:
            logger.error(f"Error retrieving latest committee meetings: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("committee meetings"))
        
        meetings = data.get("committeeMeetings", [])
        if not meetings:
            logger.info("No committee meetings found")
            return "No committee meetings found."
        
        # Apply deduplication
        meetings = ResponseProcessor.deduplicate_results(meetings, key_fields=["eventId"])
        
        logger.info(f"Found {len(meetings)} committee meetings")
        lines = ["Latest Committee Meetings:"]
        for meeting_item in meetings:
            lines.append("")
            lines.append(format_committee_meeting_item(meeting_item))
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_latest_committee_meetings: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meetings"))

# @require_paid_access
async def get_committee_meetings_by_congress(ctx: Context, congress: int) -> str:
    """
    Get committee meetings for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        params = {
            "limit": 250,
            "sort": "updateDate+desc", 
            "format": "json"
        }
        
        logger.debug(f"Fetching committee meetings for Congress {congress}")
        data = await safe_committee_meetings_request(f"/committee-meeting/{congress}", ctx, params)
        
        if "error" in data:
            logger.error(f"Error retrieving committee meetings for Congress {congress}: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("committee meetings"))
        
        meetings = data.get("committeeMeetings", [])
        if not meetings:
            logger.info(f"No committee meetings found for Congress {congress}")
            return f"No committee meetings found for Congress {congress}."
        
        # Apply deduplication
        meetings = ResponseProcessor.deduplicate_results(meetings, key_fields=["eventId"])
        
        logger.info(f"Found {len(meetings)} committee meetings for Congress {congress}")
        lines = [f"Committee Meetings for Congress {congress}:"]
        for meeting_item in meetings:
            lines.append("")
            lines.append(format_committee_meeting_item(meeting_item))
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_committee_meetings_by_congress: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meetings"))

# @require_paid_access
async def get_committee_meetings_by_congress_and_chamber(ctx: Context, congress: int, chamber: str) -> str:
    """
    Get committee meetings for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        if chamber not in ["house", "senate"]:
            logger.warning(f"Invalid chamber: {chamber}")
            return format_error_response(CommonErrors.invalid_parameter("chamber", chamber, "Must be 'house' or 'senate'"))
        
        params = {
            "limit": 250,
            "sort": "updateDate+desc",
            "format": "json"
        }
        
        logger.debug(f"Fetching committee meetings for Congress {congress}, Chamber {chamber}")
        data = await safe_committee_meetings_request(f"/committee-meeting/{congress}/{chamber}", ctx, params)
        
        if "error" in data:
            logger.error(f"Error retrieving committee meetings for Congress {congress}, Chamber {chamber}: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("committee meetings"))
        
        meetings = data.get("committeeMeetings", [])
        if not meetings:
            logger.info(f"No committee meetings found for Congress {congress}, Chamber {chamber}")
            return f"No committee meetings found for Congress {congress}, Chamber {chamber}."
        
        # Apply deduplication
        meetings = ResponseProcessor.deduplicate_results(meetings, key_fields=["eventId"])
        
        logger.info(f"Found {len(meetings)} committee meetings for Congress {congress}, Chamber {chamber}")
        lines = [f"Committee Meetings for Congress {congress}, Chamber {chamber}:"]
        for meeting_item in meetings:
            lines.append("")
            lines.append(format_committee_meeting_item(meeting_item))
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_committee_meetings_by_congress_and_chamber: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meetings"))

# @require_paid_access
async def get_committee_meetings_by_committee(ctx: Context, congress: int, chamber: str, committee_code: str) -> str:
    """
    Get committee meetings for a specific committee.
    
    Note: Due to Congress.gov API limitations, the list endpoints don't include committee information.
    This function would require calling detail endpoints for each meeting, which is inefficient.
    Consider using search_committee_meetings with committee name keywords instead.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        committee_code: The committee system code (e.g., "hsag00").
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        if chamber not in ["house", "senate"]:
            logger.warning(f"Invalid chamber: {chamber}")
            return format_error_response(CommonErrors.invalid_parameter("chamber", chamber, "Must be 'house' or 'senate'"))
        
        # Explain limitation and suggest alternative
        return f"""Committee meetings filtering by committee code is not efficiently supported by the Congress.gov API.

The list endpoints don't include committee information, which would require calling detail endpoints for each meeting.

**Recommended alternatives:**
1. Use `search_committee_meetings` with committee name keywords
2. Use `get_committee_meetings_by_congress_and_chamber` to get all meetings, then manually review
3. Use `get_committee_meeting_details` if you have specific event IDs

**Example:**
- Search for "veterans" committee meetings: `search_committee_meetings(keywords="veterans", congress={congress}, chamber="{chamber}")`
- Get all meetings: `get_committee_meetings_by_congress_and_chamber(congress={congress}, chamber="{chamber}")`

Committee code requested: {committee_code}"""
        
    except Exception as e:
        logger.error(f"Unexpected error in get_committee_meetings_by_committee: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meetings"))

# @require_paid_access
async def get_committee_meeting_details(ctx: Context, congress: int, chamber: str, committee_code: str, event_id: int) -> str:
    """
    Get detailed information about a specific committee meeting.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        committee_code: The committee system code (e.g., "hsag00").
        event_id: The event ID for the meeting.
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        if chamber not in ["house", "senate"]:
            logger.warning(f"Invalid chamber: {chamber}")
            return format_error_response(CommonErrors.invalid_parameter("chamber", chamber, "Must be 'house' or 'senate'"))
        
        params = {
            "format": "json"
        }
        
        logger.debug(f"Fetching details for committee meeting {congress}/{chamber}/{event_id}")
        data = await safe_committee_meetings_request(f"/committee-meeting/{congress}/{chamber}/{event_id}", ctx, params)
        
        if "error" in data:
            logger.error(f"Error retrieving committee meeting details: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("committee meeting details"))
        
        meeting_data = data.get("committeeMeeting")
        if not meeting_data:
            logger.info(f"No committee meeting found for {congress}/{chamber}/{event_id}")
            return f"No committee meeting found for {congress}/{chamber}/{event_id}."
        
        logger.info(f"Successfully retrieved committee meeting details for {congress}/{chamber}/{event_id}")
        return format_committee_meeting_detail(meeting_data)
    
    except Exception as e:
        logger.error(f"Unexpected error in get_committee_meeting_details: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meeting details"))

# @require_paid_access
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
    try:
        # Validate parameters
        limit_validation = ParameterValidator.validate_limit_range(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return format_error_response(CommonErrors.invalid_parameter("limit", limit, limit_validation.error_message))
        
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                logger.warning(f"Invalid congress number: {congress}")
                return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        if chamber is not None and chamber not in ["house", "senate"]:
            logger.warning(f"Invalid chamber: {chamber}")
            return format_error_response(CommonErrors.invalid_parameter("chamber", chamber, "Must be 'house' or 'senate'"))
        
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
        data = await safe_committee_meetings_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error searching committee meetings: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("committee meetings"))
        
        meetings = data.get("committeeMeetings", [])
        if not meetings:
            logger.info("No committee meetings found matching the search criteria")
            return "No committee meetings found matching the search criteria."
        
        # Apply deduplication
        meetings = ResponseProcessor.deduplicate_results(meetings, key_fields=["eventId"])
        
        logger.info(f"Found {len(meetings)} committee meetings matching the search criteria")
        lines = ["Search Results - Committee Meetings:"]
        for meeting_item in meetings:
            lines.append("")
            lines.append(format_committee_meeting_item(meeting_item))
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.error(f"Unexpected error in search_committee_meetings: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("committee meetings"))
