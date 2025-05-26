# congress_api/features/house_requirements.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_house_requirement_item(item: Dict[str, Any]) -> str:
    """Formats a single house requirement item for display in a list."""
    lines = [
        f"Requirement Number: {item.get('number', 'N/A')}",
        f"Update Date: {item.get('updateDate', 'N/A')}"
    ]
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_house_requirement_detail(req_data: Dict[str, Any]) -> str:
    """Formats detailed information for a house requirement."""
    if not req_data:
        return "No house requirement data available."
    
    # Check if the expected key is present
    if 'houseRequirement' not in req_data:
        # Try to determine if this is a valid response in a different format
        if isinstance(req_data, dict) and len(req_data) > 0:
            # Log what keys we did receive
            logging.debug(f"Received keys in response: {list(req_data.keys())}")
            return f"Received house requirement data, but in an unexpected format. Keys: {list(req_data.keys())}"
        return "No house requirement data available."
    
    req = req_data['houseRequirement']
    
    lines = [
        f"House Requirement - Number: {req.get('number', 'N/A')}",
        f"Active Record: {req.get('activeRecord', 'N/A')}",
        f"Nature: {req.get('nature', 'N/A')}",
        f"Frequency: {req.get('frequency', 'N/A')}"
    ]
    
    # Add legal authority if available
    if 'legalAuthority' in req:
        lines.append(f"Legal Authority: {req.get('legalAuthority', 'N/A')}")
    
    # Add submitting agency and official if available
    if 'submittingAgency' in req:
        lines.append(f"Submitting Agency: {req.get('submittingAgency', 'N/A')}")
    if 'parentAgency' in req:
        lines.append(f"Parent Agency: {req.get('parentAgency', 'N/A')}")
    if 'submittingOfficial' in req and req['submittingOfficial']:
        lines.append(f"Submitting Official: {req.get('submittingOfficial', 'N/A')}")
    
    # Add matching communications if available
    if 'matchingCommunications' in req:
        match_comms = req['matchingCommunications']
        lines.append(f"\nMatching Communications: {match_comms.get('count', 'N/A')}")
        if 'url' in match_comms:
            lines.append(f"Matching Communications URL: {match_comms.get('url', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in req:
        lines.append(f"\nUpdate Date: {req.get('updateDate', 'N/A')}")
    
    return "\n".join(lines)

def format_matching_communications(comms_data: Dict[str, Any]) -> str:
    """Formats matching communications for a house requirement."""
    if not comms_data or 'matchingCommunications' not in comms_data:
        return "No matching communications available."
    
    comms = comms_data['matchingCommunications']
    if not comms:
        return "No matching communications found."
    
    lines = ["Matching Communications:"]
    
    for comm in comms:
        lines.append("")
        lines.append(f"Congress: {comm.get('congress', 'N/A')}")
        lines.append(f"Chamber: {comm.get('chamber', 'N/A')}")
        lines.append(f"Number: {comm.get('number', 'N/A')}")
        
        # Add communication type if available
        if 'communicationType' in comm:
            comm_type = comm['communicationType']
            lines.append(f"Type: {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
        
        # Add URL if available
        if 'url' in comm:
            lines.append(f"URL: {comm.get('url', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://house-requirements/latest")
async def get_latest_house_requirements() -> str:
    """
    Get the most recent house requirements.
    Returns the 10 most recently updated requirements by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "format": "json"
    }
    
    logger.debug("Fetching latest house requirements")
    data = await make_api_request("/house-requirement", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest house requirements: {data['error']}")
        return f"Error retrieving latest house requirements: {data['error']}"
    
    if 'houseRequirements' not in data:
        logger.warning("No houseRequirements field in response")
        return "No house requirements found."
    
    reqs = data['houseRequirements']
    if not reqs:
        logger.info("No house requirements found")
        return "No house requirements found."
    
    logger.info(f"Found {len(reqs)} house requirements")
    lines = ["Latest House Requirements:"]
    for req in reqs:
        lines.append("")
        lines.append(format_house_requirement_item(req))
    
    return "\n".join(lines)

@mcp.resource("congress://house-requirements/{requirement_number}")
async def get_house_requirement_detail(requirement_number: int) -> str:
    """
    Get detailed information for a specific house requirement.
    
    Args:
        requirement_number: The requirement number (e.g., 8070).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching house requirement {requirement_number}")
    data = await make_api_request(f"/house-requirement/{requirement_number}", ctx, params=params)
    
    # Log the entire response structure for debugging
    logger.debug(f"API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
    
    if "error" in data:
        logger.error(f"Error retrieving house requirement {requirement_number}: {data['error']}")
        return f"Error retrieving house requirement {requirement_number}: {data['error']}"
    
    logger.info(f"Retrieved house requirement {requirement_number}")
    return format_house_requirement_detail(data)

@mcp.resource("congress://house-requirements/{requirement_number}/matching-communications")
async def get_house_requirement_matching_communications(requirement_number: int) -> str:
    """
    Get matching communications for a specific house requirement.
    
    Args:
        requirement_number: The requirement number (e.g., 8070).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching matching communications for house requirement {requirement_number}")
    data = await make_api_request(f"/house-requirement/{requirement_number}/matching-communications", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving matching communications for house requirement {requirement_number}: {data['error']}")
        return f"Error retrieving matching communications for house requirement {requirement_number}: {data['error']}"
    
    logger.info(f"Retrieved matching communications for house requirement {requirement_number}")
    return format_matching_communications(data)

# --- MCP Tools ---

@mcp.tool("search_house_requirements")
async def search_house_requirements(
    requirement_number: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search for house requirements based on various criteria.
    
    Args:
        requirement_number: Optional specific requirement number to search for.
        limit: Maximum number of results to return (default: 10).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json",
        "limit": limit
    }
    
    # Construct the endpoint based on provided parameters
    if requirement_number:
        endpoint = f"/house-requirement/{requirement_number}"
        logger.debug(f"Fetching specific house requirement {requirement_number}")
        data = await make_api_request(endpoint, ctx, params=params)
        
        if "error" in data:
            logger.error(f"Error retrieving house requirement {requirement_number}: {data['error']}")
            return f"Error retrieving house requirement {requirement_number}: {data['error']}"
        
        logger.info(f"Retrieved house requirement {requirement_number}")
        return format_house_requirement_detail(data)
    else:
        endpoint = "/house-requirement"
        logger.debug(f"Searching house requirements with limit={limit}")
        data = await make_api_request(endpoint, ctx, params=params)
        
        if "error" in data:
            logger.error(f"Error searching house requirements: {data['error']}")
            return f"Error searching house requirements: {data['error']}"
        
        if 'houseRequirements' not in data:
            logger.warning("No houseRequirements field in response")
            return "No house requirements found matching the search criteria."
        
        reqs = data['houseRequirements']
        if not reqs:
            logger.info("No house requirements found matching the search criteria")
            return "No house requirements found matching the search criteria."
        
        logger.info(f"Found {len(reqs)} house requirements matching the search criteria")
        
        # Format the results
        lines = ["House Requirements Search Results:"]
        for req in reqs:
            lines.append("")
            lines.append(format_house_requirement_item(req))
        
        return "\n".join(lines)
