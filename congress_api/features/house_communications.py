# congress_api/features/house_communications.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_house_communication_item(item: Dict[str, Any]) -> str:
    """Formats a single house communication item for display in a list."""
    lines = [
        f"Congress: {item.get('congressNumber', 'N/A')}",
        f"Chamber: {item.get('chamber', 'N/A')}",
        f"Communication Number: {item.get('communicationNumber', item.get('number', 'N/A'))}"
    ]
    
    # Add communication type if available
    if 'communicationType' in item:
        comm_type = item['communicationType']
        lines.append(f"Type: {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
    
    # Add report nature if available
    if 'reportNature' in item:
        lines.append(f"Report Nature: {item.get('reportNature', 'N/A')}")
    
    # Add submitting agency and official if available
    if 'submittingAgency' in item:
        lines.append(f"Submitting Agency: {item.get('submittingAgency', 'N/A')}")
    if 'submittingOfficial' in item:
        lines.append(f"Submitting Official: {item.get('submittingOfficial', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in item:
        lines.append(f"Update Date: {item.get('updateDate', 'N/A')}")
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_house_communication_detail(comm_data: Dict[str, Any]) -> str:
    """Formats detailed information for a house communication."""
    if not comm_data:
        return "No house communication data available."
    
    # Check if the expected key is present
    if 'house-communication' not in comm_data:
        # Try to determine if this is a valid response in a different format
        if isinstance(comm_data, dict) and len(comm_data) > 0:
            # Log what keys we did receive
            logging.debug(f"Received keys in response: {list(comm_data.keys())}")
            return f"Received house communication data, but in an unexpected format. Keys: {list(comm_data.keys())}"
        return "No house communication data available."
    
    comm = comm_data['house-communication']
    
    lines = [
        f"House Communication - {comm.get('congressNumber', 'N/A')}/{comm.get('communicationType', {}).get('code', 'N/A')}/{comm.get('number', 'N/A')}",
        f"Congress: {comm.get('congressNumber', 'N/A')}",
        f"Chamber: {comm.get('chamber', 'N/A')}",
        f"Session: {comm.get('sessionNumber', 'N/A')}"
    ]
    
    # Add communication type if available
    if 'communicationType' in comm:
        comm_type = comm['communicationType']
        lines.append(f"Type: {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
    
    # Add abstract if available
    if 'abstract' in comm:
        lines.append(f"\nAbstract: {comm.get('abstract', 'N/A')}")
    
    # Add report nature if available
    if 'reportNature' in comm:
        lines.append(f"Report Nature: {comm.get('reportNature', 'N/A')}")
    
    # Add legal authority if available
    if 'legalAuthority' in comm:
        lines.append(f"Legal Authority: {comm.get('legalAuthority', 'N/A')}")
    
    # Add submitting agency and official if available
    if 'submittingAgency' in comm:
        lines.append(f"Submitting Agency: {comm.get('submittingAgency', 'N/A')}")
    if 'submittingOfficial' in comm:
        lines.append(f"Submitting Official: {comm.get('submittingOfficial', 'N/A')}")
    
    # Add congressional record date if available
    if 'congressionalRecordDate' in comm:
        lines.append(f"Congressional Record Date: {comm.get('congressionalRecordDate', 'N/A')}")
    
    # Add is rulemaking if available
    if 'isRulemaking' in comm:
        lines.append(f"Is Rulemaking: {comm.get('isRulemaking', 'N/A')}")
    
    # Add committees if available
    if 'committees' in comm and comm['committees']:
        lines.append("\nReferred to Committees:")
        for committee in comm['committees']:
            lines.append(f"  - {committee.get('name', 'N/A')}")
            lines.append(f"    Referral Date: {committee.get('referralDate', 'N/A')}")
            if 'systemCode' in committee:
                lines.append(f"    System Code: {committee.get('systemCode', 'N/A')}")
            if 'url' in committee:
                lines.append(f"    URL: {committee.get('url', 'N/A')}")
    
    # Add matching requirements if available
    if 'matchingRequirements' in comm and comm['matchingRequirements']:
        lines.append("\nMatching Requirements:")
        for req in comm['matchingRequirements']:
            lines.append(f"  - Number: {req.get('number', 'N/A')}")
            if 'url' in req:
                lines.append(f"    URL: {req.get('url', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in comm:
        lines.append(f"\nUpdate Date: {comm.get('updateDate', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://house-communications/latest")
async def get_latest_house_communications(ctx: Context) -> str:
    """
    Get the most recent house communications.
    Returns the 10 most recently published communications by default.
    """
    params = {
        "limit": 10,
        "format": "json"
    }
    
    logger.debug("Fetching latest house communications")
    data = await make_api_request("/house-communication", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest house communications: {data['error']}")
        return f"Error retrieving latest house communications: {data['error']}"
    
    if 'houseCommunications' not in data:
        logger.warning("No houseCommunications field in response")
        return "No house communications found."
    
    comms = data['houseCommunications']
    if not comms:
        logger.info("No house communications found")
        return "No house communications found."
    
    logger.info(f"Found {len(comms)} house communications")
    lines = ["Latest House Communications:"]
    for comm in comms:
        lines.append("")
        lines.append(format_house_communication_item(comm))
    
    return "\n".join(lines)

@mcp.resource("congress://house-communications/{congress}")
async def get_house_communications_by_congress(ctx: Context, congress: int) -> str:
    """
    Get house communications for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching house communications for Congress {congress}")
    data = await make_api_request(f"/house-communication/{congress}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving house communications for Congress {congress}: {data['error']}")
        return f"Error retrieving house communications for Congress {congress}: {data['error']}"
    
    if 'houseCommunications' not in data:
        logger.warning(f"No houseCommunications field in response for Congress {congress}")
        return f"No house communications found for Congress {congress}."
    
    comms = data['houseCommunications']
    if not comms:
        logger.info(f"No house communications found for Congress {congress}")
        return f"No house communications found for Congress {congress}."
    
    logger.info(f"Found {len(comms)} house communications for Congress {congress}")
    lines = [f"House Communications for Congress {congress}:"]
    for comm in comms:
        lines.append("")
        lines.append(format_house_communication_item(comm))
    
    return "\n".join(lines)

@mcp.resource("congress://house-communications/{congress}/{communication_type}")
async def get_house_communications_by_congress_and_type(ctx: Context, congress: int, communication_type: str) -> str:
    """
    Get house communications for a specific Congress and communication type.
    
    Args:
        congress: The Congress number (e.g., 117).
        communication_type: The type of communication (e.g., "ec", "ml", "pm", "pt").
    """
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching house communications for Congress {congress}, type {communication_type}")
    data = await make_api_request(f"/house-communication/{congress}/{communication_type}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving house communications for Congress {congress}, type {communication_type}: {data['error']}")
        return f"Error retrieving house communications for Congress {congress}, type {communication_type}: {data['error']}"
    
    if 'houseCommunications' not in data:
        logger.warning(f"No houseCommunications field in response for Congress {congress}, type {communication_type}")
        return f"No house communications found for Congress {congress}, type {communication_type}."
    
    comms = data['houseCommunications']
    if not comms:
        logger.info(f"No house communications found for Congress {congress}, type {communication_type}")
        return f"No house communications found for Congress {congress}, type {communication_type}."
    
    logger.info(f"Found {len(comms)} house communications for Congress {congress}, type {communication_type}")
    
    # Get the full name of the communication type from the first item if available
    type_name = communication_type.upper()
    if comms and 'communicationType' in comms[0] and 'name' in comms[0]['communicationType']:
        type_name = comms[0]['communicationType']['name']
    
    lines = [f"House Communications for Congress {congress}, Type: {type_name}:"]
    for comm in comms:
        lines.append("")
        lines.append(format_house_communication_item(comm))
    
    return "\n".join(lines)

@mcp.resource("congress://house-communications/{congress}/{communication_type}/{communication_number}")
async def get_house_communication_detail(ctx: Context, congress: int, communication_type: str, communication_number: int) -> str:
    """
    Get detailed information for a specific house communication.
    
    Args:
        congress: The Congress number (e.g., 117).
        communication_type: The type of communication (e.g., "ec", "ml", "pm", "pt").
        communication_number: The communication number (e.g., 3324).
    """
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching house communication {congress}/{communication_type}/{communication_number}")
    data = await make_api_request(f"/house-communication/{congress}/{communication_type}/{communication_number}", ctx, params=params)
    
    # Log the entire response structure for debugging
    logger.debug(f"API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
    
    if "error" in data:
        logger.error(f"Error retrieving house communication {congress}/{communication_type}/{communication_number}: {data['error']}")
        return f"Error retrieving house communication {congress}/{communication_type}/{communication_number}: {data['error']}"
    
    # Check for different possible response formats
    if 'house-communication' in data:
        logger.info(f"Retrieved house communication using 'house-communication' key")
        return format_house_communication_detail(data)
    elif 'houseCommunication' in data:
        logger.info(f"Retrieved house communication using 'houseCommunication' key")
        # Create a compatible structure for our formatter
        compatible_data = {'house-communication': data['houseCommunication']}
        return format_house_communication_detail(compatible_data)
    else:
        # If neither expected key is found, log the keys and return a formatted version of whatever we got
        logger.warning(f"Unexpected response format. Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
        return f"Retrieved house communication {congress}/{communication_type}/{communication_number}, but in an unexpected format:\n\n{str(data)[:500]}..."

# --- MCP Tools ---

@mcp.tool("search_house_communications")
async def search_house_communications(
    ctx: Context,
    congress: Optional[int] = None,
    communication_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for house communications based on various criteria.
    
    Args:
        congress: Optional Congress number (e.g., 117).
        communication_type: Optional communication type (e.g., "ec", "ml", "pm", "pt").
        limit: Maximum number of results to return (default: 10).
    """
    params = {
        "format": "json",
        "limit": limit
    }
    
    # Construct the endpoint based on provided parameters
    endpoint = "/house-communication"
    if congress:
        endpoint += f"/{congress}"
        if communication_type:
            endpoint += f"/{communication_type}"
    
    # Log the search parameters
    search_params = []
    if congress:
        search_params.append(f"congress={congress}")
    if communication_type:
        search_params.append(f"communication_type={communication_type}")
    if limit != 10:
        search_params.append(f"limit={limit}")
    
    search_str = ", ".join(search_params) if search_params else "default parameters"
    logger.debug(f"Searching house communications with {search_str}")
    
    # Make the API request
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching house communications: {data['error']}")
        return f"Error searching house communications: {data['error']}"
    
    if 'houseCommunications' not in data:
        logger.warning("No houseCommunications field in response")
        return "No house communications found matching the search criteria."
    
    comms = data['houseCommunications']
    if not comms:
        logger.info("No house communications found matching the search criteria")
        return "No house communications found matching the search criteria."
    
    logger.info(f"Found {len(comms)} house communications matching the search criteria")
    
    # Format the results
    lines = ["House Communications Search Results:"]
    for comm in comms:
        lines.append("")
        lines.append(format_house_communication_item(comm))
    
    return "\n".join(lines)
