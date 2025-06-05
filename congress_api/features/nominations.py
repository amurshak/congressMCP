"""
Nominations API for the Congressional MCP server.

This module provides access to nomination data from the Congress.gov API.
"""

import logging
from typing import Dict, Any, List, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.api_wrapper import safe_nominations_request
from ..core.validators import ParameterValidator
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize validator
validator = ParameterValidator()

# Base endpoint for the nominations API
BASE_ENDPOINT = "nomination"

# Formatting helpers
def format_nomination_item(nomination: Dict[str, Any]) -> str:
    """Format a nomination for display in a list."""
    lines = []
    
    # Citation (PN number)
    lines.append(f"Citation: {nomination.get('citation', 'N/A')}")
    
    # Congress
    lines.append(f"Congress: {nomination.get('congress', 'N/A')}")
    
    # Nomination Number
    lines.append(f"Nomination Number: {nomination.get('number', 'N/A')}")
    
    # Organization (e.g., Army, Navy, etc.)
    if "organization" in nomination:
        lines.append(f"Organization: {nomination['organization']}")
    
    # Is Military
    is_military = nomination.get('nominationType', {}).get('isMilitary', False)
    lines.append(f"Military Nomination: {'Yes' if is_military else 'No'}")
    
    # Received Date
    if "receivedDate" in nomination:
        lines.append(f"Received Date: {nomination['receivedDate']}")
    
    # Latest Action
    if "latestAction" in nomination:
        action = nomination["latestAction"]
        action_date = action.get("actionDate", "N/A")
        action_text = action.get("text", "N/A")
        lines.append(f"Latest Action ({action_date}): {action_text}")
    
    # Update Date
    if "updateDate" in nomination:
        lines.append(f"Update Date: {nomination['updateDate']}")
    
    # URL
    if "url" in nomination:
        lines.append(f"URL: {nomination['url']}")
    
    return "\n".join(lines)

def format_nomination_detail(nomination: Dict[str, Any]) -> str:
    """Format detailed information for a nomination."""
    lines = []
    
    # Citation (PN number)
    lines.append(f"Nomination - {nomination.get('citation', 'N/A')}")
    
    # Congress
    lines.append(f"Congress: {nomination.get('congress', 'N/A')}")
    
    # Nomination Number
    lines.append(f"Nomination Number: {nomination.get('number', 'N/A')}")
    
    # Part Number
    if "partNumber" in nomination:
        lines.append(f"Part Number: {nomination['partNumber']}")
    
    # Is List
    is_list = nomination.get('isList', False)
    lines.append(f"Is List Nomination: {'Yes' if is_list else 'No'}")
    
    # Received Date
    if "receivedDate" in nomination:
        lines.append(f"Received Date: {nomination['receivedDate']}")
    
    # Latest Action
    if "latestAction" in nomination:
        action = nomination["latestAction"]
        action_date = action.get("actionDate", "N/A")
        action_text = action.get("text", "N/A")
        lines.append(f"\nLatest Action ({action_date}): {action_text}")
    
    # Nominees
    if "nominees" in nomination and nomination["nominees"]:
        lines.append("\nNominees:")
        for idx, nominee in enumerate(nomination["nominees"], 1):
            lines.append(f"  {idx}. Position: {nominee.get('positionTitle', 'N/A')}")
            lines.append(f"     Organization: {nominee.get('organization', 'N/A')}")
            lines.append(f"     Nominee Count: {nominee.get('nomineeCount', 'N/A')}")
            if "introText" in nominee:
                intro_text = nominee.get('introText', '')
                if len(intro_text) > 100:
                    intro_text = intro_text[:97] + "..."
                lines.append(f"     Intro: {intro_text}")
    
    # Actions count and URL
    if "actions" in nomination:
        actions = nomination["actions"]
        lines.append(f"\nActions: {actions.get('count', 0)}")
        if "url" in actions:
            lines.append(f"Actions URL: {actions['url']}")
    
    # Committees count and URL
    if "committees" in nomination:
        committees = nomination["committees"]
        lines.append(f"\nCommittees: {committees.get('count', 0)}")
        if "url" in committees:
            lines.append(f"Committees URL: {committees['url']}")
    
    # Update Date
    if "updateDate" in nomination:
        lines.append(f"\nUpdate Date: {nomination['updateDate']}")
    
    return "\n".join(lines)

def format_nominees_list(nominees: List[Dict[str, Any]]) -> str:
    """Format a list of nominees."""
    if not nominees:
        return "No nominees found."
    
    lines = ["Nominees:"]
    
    for nominee in nominees:
        lines.append("")
        lines.append(f"First Name: {nominee.get('firstName', 'N/A')}")
        lines.append(f"Middle Name: {nominee.get('middleName', 'N/A')}")
        lines.append(f"Last Name: {nominee.get('lastName', 'N/A')}")
        lines.append(f"Ordinal: {nominee.get('ordinal', 'N/A')}")
    
    return "\n".join(lines)

def format_nomination_actions(actions: List[Dict[str, Any]]) -> str:
    """Format a list of actions for a nomination."""
    if not actions:
        return "No actions found."
    
    lines = ["Nomination Actions:"]
    
    for action in actions:
        lines.append("")
        lines.append(f"Date: {action.get('actionDate', 'N/A')}")
        lines.append(f"Type: {action.get('type', 'N/A')}")
        lines.append(f"Text: {action.get('text', 'N/A')}")
        
        if "committees" in action and action["committees"]:
            lines.append("Committees:")
            for committee in action["committees"]:
                lines.append(f"  - {committee.get('name', 'N/A')} ({committee.get('systemCode', 'N/A')})")
    
    return "\n".join(lines)

def format_nomination_committees(ctx: Context, committees: List[Dict[str, Any]]) -> str:
    """Format a list of committees for a nomination."""
    if not committees:
        return "No committees found."
    
    lines = ["Nomination Committees:"]
    
    for committee in committees:
        lines.append("")
        lines.append(f"Name: {committee.get('name', 'N/A')}")
        lines.append(f"Chamber: {committee.get('chamber', 'N/A')}")
        lines.append(f"Type: {committee.get('type', 'N/A')}")
        lines.append(f"System Code: {committee.get('systemCode', 'N/A')}")
        
        if "activities" in committee and committee["activities"]:
            lines.append("Activities:")
            for activity in committee["activities"]:
                lines.append(f"  - {activity.get('name', 'N/A')} ({activity.get('date', 'N/A')})")
    
    return "\n".join(lines)

def format_nomination_hearings(hearings: List[Dict[str, Any]]) -> str:
    """Format a list of hearings for a nomination."""
    if not hearings:
        return "No hearings found."
    
    lines = ["Nomination Hearings:"]
    
    for hearing in hearings:
        lines.append("")
        lines.append(f"Chamber: {hearing.get('chamber', 'N/A')}")
        lines.append(f"Citation: {hearing.get('citation', 'N/A')}")
        lines.append(f"Date: {hearing.get('date', 'N/A')}")
        lines.append(f"Jacket Number: {hearing.get('jacketNumber', 'N/A')}")
        lines.append(f"Number: {hearing.get('number', 'N/A')}")
    
    return "\n".join(lines)

# MCP Tools
@mcp.tool("get_latest_nominations")
async def get_latest_nominations(ctx: Context) -> str:
    """
    Get the most recent nominations.
    Returns the 10 most recently published nominations by default.
    """
    logger.info("Getting latest nominations")
    
    # Make safe API request
    endpoint = BASE_ENDPOINT
    data = await safe_nominations_request(endpoint, ctx, {"sort": "updateDate+desc", "limit": 10})
    
    if "error" in data:
        logger.error(f"Error getting latest nominations: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"latest nominations: {endpoint}", message=data['error']))
    
    if 'nominations' not in data:
        logger.warning("No nominations field in response")
        return "No nominations found."
    
    nominations = data['nominations']
    if not nominations:
        logger.info("No nominations found")
        return "No nominations found."
    
    # Deduplicate results
    nominations = ResponseProcessor.deduplicate_results(nominations, ['number', 'congress'])
    
    logger.info(f"Found {len(nominations)} latest nominations")
    
    # Format results
    lines = ["# Latest Nominations\n"]
    for idx, nomination in enumerate(nominations, 1):
        lines.append(f"## {idx}. {format_nomination_item(nomination)}\n")
    
    return "\n".join(lines)

@mcp.tool("get_nominations_by_congress")
async def get_nominations_by_congress(ctx: Context, congress: int) -> str:
    """
    Get nominations for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117 for the 117th Congress)
    """
    logger.info(f"Getting nominations for Congress {congress}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting nominations for Congress {congress}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nominations by congress: {endpoint}", message=data['error']))
    
    if 'nominations' not in data:
        logger.warning(f"No nominations field in response for Congress {congress}")
        return f"No nominations found for Congress {congress}."
    
    nominations = data['nominations']
    if not nominations:
        logger.info(f"No nominations found for Congress {congress}")
        return f"No nominations found for Congress {congress}."
    
    # Deduplicate results
    nominations = ResponseProcessor.deduplicate_results(nominations, ['number', 'congress'])
    
    logger.info(f"Found {len(nominations)} nominations for Congress {congress}")
    
    # Format results
    lines = [f"# Nominations for Congress {congress}\n"]
    for idx, nomination in enumerate(nominations, 1):
        lines.append(f"## {idx}. {format_nomination_item(nomination)}\n")
    
    return "\n".join(lines)

@mcp.tool("get_nomination_details")
async def get_nomination_details(ctx: Context, congress: int, nomination_number: int) -> str:
    """
    Get detailed information about a specific nomination.

    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        nomination_number: The nomination number
    """
    logger.info(f"Getting nomination details for {nomination_number}, Congress {congress}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    if nomination_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "nomination_number", nomination_number, "Nomination number must be a positive integer"
        ))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}/{nomination_number}"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting nomination details for {nomination_number}, Congress {congress}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nomination details: {endpoint}", message=data['error']))
    
    if 'nomination' not in data:
        logger.warning(f"No nomination field in response for {congress}/{nomination_number}")
        return f"No nomination found for nomination {nomination_number}, Congress {congress}."
    
    nomination = data['nomination']
    logger.info(f"Found nomination details for {nomination_number}, Congress {congress}")
    
    # Format and return the result
    return format_nomination_detail(nomination)

@mcp.tool("get_nomination_nominees")
async def get_nomination_nominees(ctx: Context, congress: int, nomination_number: int, ordinal: int) -> str:
    """
    Get nominees for a specific position within a nomination.
    
    Args:
        congress: The Congress number (e.g., 117 for the 117th Congress)
        nomination_number: The nomination number
        ordinal: The ordinal number for the position
    """
    logger.info(f"Getting nominees for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    if nomination_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "nomination_number", nomination_number, "Nomination number must be a positive integer"
        ))
    
    if ordinal <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "ordinal", ordinal, "Ordinal must be a positive integer"
        ))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}/{nomination_number}/{ordinal}"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting nominees for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nomination nominees: {endpoint}", message=data['error']))
    
    if 'nominees' not in data:
        logger.warning(f"No nominees field in response for {congress}/{nomination_number}/{ordinal}")
        return f"No nominees found for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}."
    
    nominees = data['nominees']
    if not nominees:
        logger.info(f"No nominees found for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}")
        return f"No nominees found for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}."
    
    # Deduplicate results
    nominees = ResponseProcessor.deduplicate_results(nominees, ['name', 'position'])
    
    logger.info(f"Found {len(nominees)} nominees for nomination {nomination_number}, Congress {congress}, ordinal {ordinal}")
    
    # Format the results
    return format_nominees_list(nominees)

@mcp.tool("get_nomination_actions")
async def get_nomination_actions(ctx: Context, congress: int, nomination_number: int) -> str:
    """
    Get actions for a specific nomination.
    
    Args:
        congress: The Congress number (e.g., 117 for the 117th Congress)
        nomination_number: The nomination number
    """
    logger.info(f"Getting actions for nomination {nomination_number}, Congress {congress}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(CommonErrors.invalid_parameter(
            "congress", congress, congress_validation.error_message
        ))
    
    if nomination_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "nomination_number", nomination_number, "Nomination number must be a positive integer"
        ))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}/{nomination_number}/actions"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting actions for nomination {nomination_number}, Congress {congress}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nomination actions: {endpoint}", message=data['error']))
    
    if 'actions' not in data:
        logger.warning(f"No actions field in response for {congress}/{nomination_number}/actions")
        return f"No actions found for nomination {nomination_number}, Congress {congress}."
    
    actions = data['actions']
    if not actions:
        logger.info(f"No actions found for nomination {nomination_number}, Congress {congress}")
        return f"No actions found for nomination {nomination_number}, Congress {congress}."
    
    # Deduplicate actions
    deduplicated_actions = ResponseProcessor.deduplicate_results(
        actions,
        key_fields=['actionDate', 'text']
    )
    
    logger.info(f"Found {len(deduplicated_actions)} unique actions for nomination {nomination_number}, Congress {congress}")
    
    # Format the results
    return format_nomination_actions(deduplicated_actions)

@mcp.tool("get_nomination_committees")
async def get_nomination_committees(ctx: Context, congress: int, nomination_number: int) -> str:
    """
    Get committees for a specific nomination.
    
    Args:
        congress: The Congress number (e.g., 117 for the 117th Congress)
        nomination_number: The nomination number
    """
    logger.info(f"Getting committees for nomination {nomination_number}, Congress {congress}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(CommonErrors.invalid_parameter(
            "congress", congress, congress_validation.error_message
        ))
    
    if nomination_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "nomination_number", nomination_number, "Nomination number must be a positive integer"
        ))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}/{nomination_number}/committees"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting committees for nomination {nomination_number}, Congress {congress}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nomination committees: {endpoint}", message=data['error']))
    
    if 'committees' not in data:
        logger.warning(f"No committees field in response for {congress}/{nomination_number}/committees")
        return f"No committees found for nomination {nomination_number}, Congress {congress}."
    
    committees = data['committees']
    if not committees:
        logger.info(f"No committees found for nomination {nomination_number}, Congress {congress}")
        return f"No committees found for nomination {nomination_number}, Congress {congress}."
    
    # Deduplicate committees
    deduplicated_committees = ResponseProcessor.deduplicate_results(
        committees,
        key_fields=['systemCode', 'name']
    )
    
    logger.info(f"Found {len(deduplicated_committees)} unique committees for nomination {nomination_number}, Congress {congress}")
    
    # Format the results
    return format_nomination_committees(ctx, deduplicated_committees)

@mcp.tool("get_nomination_hearings")
async def get_nomination_hearings(ctx: Context, congress: int, nomination_number: int) -> str:
    """
    Get hearings for a specific nomination.
    
    Args:
        congress: The Congress number (e.g., 117 for the 117th Congress)
        nomination_number: The nomination number
    """
    logger.info(f"Getting hearings for nomination {nomination_number}, Congress {congress}")
    
    # Validate parameters
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(CommonErrors.invalid_parameter(
            "congress", congress, congress_validation.error_message
        ))
    
    if nomination_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter(
            "nomination_number", nomination_number, "Nomination number must be a positive integer"
        ))
    
    # Make safe API request
    endpoint = f"{BASE_ENDPOINT}/{congress}/{nomination_number}/hearings"
    data = await safe_nominations_request(endpoint, ctx, {})
    
    if "error" in data:
        logger.error(f"Error getting hearings for nomination {nomination_number}, Congress {congress}: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nomination hearings: {endpoint}", message=data['error']))
    
    if 'hearings' not in data:
        logger.warning(f"No hearings field in response for {congress}/{nomination_number}/hearings")
        return f"No hearings found for nomination {nomination_number}, Congress {congress}."
    
    hearings = data['hearings']
    if not hearings:
        logger.info(f"No hearings found for nomination {nomination_number}, Congress {congress}")
        return f"No hearings found for nomination {nomination_number}, Congress {congress}."
    
    # Deduplicate hearings
    deduplicated_hearings = ResponseProcessor.deduplicate_results(
        hearings,
        key_fields=['jacketNumber', 'date']
    )
    
    logger.info(f"Found {len(deduplicated_hearings)} unique hearings for nomination {nomination_number}, Congress {congress}")
    
    # Format the results
    return format_nomination_hearings(deduplicated_hearings)

# MCP Tool
@mcp.tool("search_nominations")
async def search_nominations(
    ctx: Context,
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    limit: int = 10,
    sort: str = "updateDate+desc",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """
    Search for nominations based on keywords.
    
    Args:
        keywords: Keywords to search for in nomination information
        congress: Optional Congress number (e.g., 117)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    logger.info(f"Searching for nominations with keywords: {keywords}, congress: {congress}")
    
    # Validate parameters
    if congress is not None:
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            ))
    
    limit_validation = ParameterValidator.validate_limit_range(limit, 250)
    if not limit_validation.is_valid:
        return format_error_response(CommonErrors.invalid_parameter(
            "limit", limit, limit_validation.error_message
        ))
    
    if from_date:
        date_validation = ParameterValidator.validate_date_format(from_date)
        if not date_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "from_date", from_date, date_validation.error_message
            ))
    
    if to_date:
        date_validation = ParameterValidator.validate_date_format(to_date)
        if not date_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "to_date", to_date, date_validation.error_message
            ))
    
    params = {
        "format": "json",
        "limit": limit
    }
    
    if keywords:
        params["query"] = keywords
    if sort:
        params["sort"] = sort
    if from_date:
        params["fromDateTime"] = from_date
    if to_date:
        params["toDateTime"] = to_date
    
    # Determine endpoint based on congress parameter
    endpoint = BASE_ENDPOINT
    if congress:
        endpoint = f"{BASE_ENDPOINT}/{congress}"
    
    # Make safe API request
    data = await safe_nominations_request(endpoint, ctx, params)
    
    if "error" in data:
        logger.error(f"Error searching for nominations: {data['error']}")
        return format_error_response(CommonErrors.api_server_error(f"nominations search: {endpoint}", message=data['error']))
    
    if 'nominations' not in data:
        logger.warning("No nominations field in response")
        return "No nominations found matching the search criteria."
    
    nominations = data['nominations']
    if not nominations:
        logger.info("No nominations found matching the search criteria")
        return "No nominations found matching the search criteria."
    
    # Deduplicate results
    deduplicated_nominations = ResponseProcessor.deduplicate_results(
        nominations, 
        key_fields=['number', 'congress']
    )
    
    logger.info(f"Found {len(deduplicated_nominations)} unique nominations matching the search criteria")
    
    # Format the results
    lines = ["# Nominations Search Results"]
    lines.append("")
    for i, nomination in enumerate(deduplicated_nominations, 1):
        lines.append(f"## {i}. {format_nomination_item(nomination)}")
        lines.append("")
    
    return "\n".join(lines)
