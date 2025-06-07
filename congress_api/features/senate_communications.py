import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.api_wrapper import safe_senate_communications_request
from ..core.validators import ParameterValidator
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import SenateCommunicationsProcessor, clean_senate_communications_response
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_senate_communication_item(item: Dict[str, Any]) -> str:
    """Formats a single senate communication item for display in a list."""
    lines = [
        f"**Congress:** {item.get('congress', 'N/A')}",
        f"**Chamber:** {item.get('chamber', 'N/A')}",
        f"**Communication Number:** {item.get('communicationNumber', item.get('number', 'N/A'))}"
    ]
    
    # Add communication type if available
    if 'communicationType' in item:
        comm_type = item['communicationType']
        lines.append(f"**Type:** {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
    
    # Add update date if available
    if 'updateDate' in item:
        lines.append(f"**Update Date:** {item.get('updateDate', 'N/A')}")
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"**URL:** {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_senate_communication_detail(comm_data: Dict[str, Any]) -> str:
    """Formats detailed information for a senate communication."""
    if not comm_data:
        return "No senate communication data available."
    
    # Check if the expected key is present
    if 'senateCommunication' not in comm_data:
        # Try to determine if this is a valid response in a different format
        if isinstance(comm_data, dict) and len(comm_data) > 0:
            # Log what keys we did receive
            logger.debug(f"Received keys in response: {list(comm_data.keys())}")
            return f"Received senate communication data, but in an unexpected format. Keys: {list(comm_data.keys())}"
        return "No senate communication data available."
    
    comm = comm_data['senateCommunication']
    
    lines = [
        f"# Senate Communication - {comm.get('congress', 'N/A')}/{comm.get('communicationType', {}).get('code', 'N/A')}/{comm.get('number', 'N/A')}",
        "",
        f"**Congress:** {comm.get('congress', 'N/A')}",
        f"**Chamber:** {comm.get('chamber', 'N/A')}",
        f"**Session:** {comm.get('sessionNumber', 'N/A')}"
    ]
    
    # Add communication type if available
    if 'communicationType' in comm:
        comm_type = comm['communicationType']
        lines.append(f"**Type:** {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
    
    # Add abstract if available
    if 'abstract' in comm:
        lines.extend(["", f"**Abstract:** {comm.get('abstract', 'N/A')}"])
    
    # Add congressional record date if available
    if 'congressionalRecordDate' in comm:
        lines.append(f"**Congressional Record Date:** {comm.get('congressionalRecordDate', 'N/A')}")
    
    # Add committees if available
    if 'committees' in comm and comm['committees']:
        lines.extend(["", "**Referred to Committees:**"])
        for committee in comm['committees']:
            lines.append(f"  - {committee.get('name', 'N/A')}")
            lines.append(f"    Referral Date: {committee.get('referralDate', 'N/A')}")
            if 'systemCode' in committee:
                lines.append(f"    System Code: {committee.get('systemCode', 'N/A')}")
            if 'url' in committee:
                lines.append(f"    URL: {committee.get('url', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in comm:
        lines.extend(["", f"**Update Date:** {comm.get('updateDate', 'N/A')}"])
    
    return "\n".join(lines)

def format_senate_communications_list(communications: List[Dict[str, Any]], title: str = "Senate Communications") -> str:
    """Format a list of senate communications with enhanced markdown formatting."""
    if not communications:
        return f"No {title.lower()} found."
    
    lines = [f"# {title}", f"", f"Found **{len(communications)}** communications:", ""]
    
    for i, comm in enumerate(communications, 1):
        lines.extend([f"## {i}. Communication {comm.get('congress', 'N/A')}/{comm.get('communicationType', {}).get('code', 'N/A')}/{comm.get('communicationNumber', comm.get('number', 'N/A'))}", ""])
        lines.append(format_senate_communication_item(comm))
        lines.append("")
    
    return "\n".join(lines)

# --- MCP Resources ---

# @require_paid_access
@mcp.resource("congress://senate-communications/latest")
async def get_latest_senate_communications(ctx: Context) -> str:
    """
    Get the most recent senate communications.
    Returns the 10 most recently published communications by default.
    """
    try:
        params = {
            "limit": 10,
            "format": "json"
        }
        
        logger.debug("Fetching latest senate communications")
        data = await safe_senate_communications_request("/senate-communication", ctx, params)
        
        # Process response using reliability framework
        processed_communications = clean_senate_communications_response(data, limit=10)
        
        if not processed_communications:
            logger.info("No senate communications found")
            return "No senate communications found."
        
        logger.info(f"Found {len(processed_communications)} senate communications")
        return format_senate_communications_list(processed_communications, "Latest Senate Communications")
        
    except Exception as e:
        logger.error(f"Error in get_latest_senate_communications: {str(e)}")
        return CommonErrors.api_server_error("/senate-communication", str(e))

# --- MCP Tools ---

# @require_paid_access
async def get_senate_communication_details(
    ctx: Context,
    congress: int,
    communication_type: str,
    communication_number: int
) -> str:
    """
    Get detailed information for a specific senate communication.
    
    Args:
        congress: The Congress number (e.g., 117).
        communication_type: The type of communication (e.g., "ec", "pm", "pom").
        communication_number: The communication number (e.g., 2561).
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        type_validation = ParameterValidator.validate_senate_communication_type(communication_type)
        if not type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("communication_type", communication_type, type_validation.error_message))
        
        number_validation = ParameterValidator.validate_communication_number(communication_number)
        if not number_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("communication_number", communication_number, number_validation.error_message))
        
        # Use sanitized values
        congress_clean = congress_validation.sanitized_value or congress
        type_clean = type_validation.sanitized_value or communication_type
        number_clean = number_validation.sanitized_value or communication_number
        
        params = {"format": "json"}
        
        logger.debug(f"Fetching senate communication {congress_clean}/{type_clean}/{number_clean}")
        data = await safe_senate_communications_request(f"/senate-communication/{congress_clean}/{type_clean}/{number_clean}", ctx, params)
        
        # Check for different possible response formats
        if 'senateCommunication' in data:
            logger.info(f"Retrieved senate communication using 'senateCommunication' key")
            return format_senate_communication_detail(data)
        else:
            # If the expected key is not found, log the keys and return a formatted version of whatever we got
            logger.warning(f"Unexpected response format. Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
            return f"Retrieved senate communication {congress_clean}/{type_clean}/{number_clean}, but in an unexpected format:\n\n{str(data)[:500]}..."
            
    except Exception as e:
        logger.error(f"Error in get_senate_communication_details: {str(e)}")
        return CommonErrors.api_server_error(f"/senate-communication/{congress}/{communication_type}/{communication_number}", str(e))

# @require_paid_access
async def search_senate_communications(
    ctx: Context,
    congress: Optional[int] = None,
    communication_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for senate communications based on various criteria.
    
    Args:
        congress: Optional Congress number (e.g., 117).
        communication_type: Optional communication type (e.g., "ec", "pm", "pom").
        limit: Maximum number of results to return (default: 10).
    """
    try:
        # Validate parameters
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(CommonErrors.invalid_congress_number(congress))
            congress = congress_validation.sanitized_value or congress
        
        if communication_type is not None:
            type_validation = ParameterValidator.validate_senate_communication_type(communication_type)
            if not type_validation.is_valid:
                return format_error_response(CommonErrors.invalid_parameter("communication_type", communication_type, type_validation.error_message))
            communication_type = type_validation.sanitized_value or communication_type
        
        limit_validation = ParameterValidator.validate_limit_range(limit, 250)
        if not limit_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("limit", limit, limit_validation.error_message))
        
        params = {
            "format": "json",
            "limit": limit
        }
        
        # Construct the endpoint based on provided parameters
        endpoint = "/senate-communication"
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
        logger.debug(f"Searching senate communications with {search_str}")
        
        # Make the API request using defensive wrapper
        data = await safe_senate_communications_request(endpoint, ctx, params)
        
        # Process response using reliability framework
        processed_communications = clean_senate_communications_response(data, limit=limit)
        
        if not processed_communications:
            logger.info("No senate communications found matching the search criteria")
            return "No senate communications found matching the search criteria."
        
        logger.info(f"Found {len(processed_communications)} senate communications matching the search criteria")
        
        # Format the results with enhanced markdown
        title = "Senate Communications Search Results"
        if congress and communication_type:
            title = f"Senate Communications for Congress {congress}, Type: {communication_type.upper()}"
        elif congress:
            title = f"Senate Communications for Congress {congress}"
        elif communication_type:
            title = f"Senate Communications - Type: {communication_type.upper()}"
        
        return format_senate_communications_list(processed_communications, title)
        
    except Exception as e:
        logger.error(f"Error in search_senate_communications: {str(e)}")
        return CommonErrors.api_server_error("/senate-communication", str(e))
