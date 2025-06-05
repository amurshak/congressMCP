# congress_api/features/house_requirements.py

import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Response Processing ---

class HouseRequirementsProcessor(ResponseProcessor):
    """Specialized processor for house requirements responses."""
    
    @staticmethod
    def deduplicate_requirements(requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate requirements based on number."""
        if not requirements:
            return []
        
        seen = set()
        unique_requirements = []
        
        for req in requirements:
            # Use requirement number as the deduplication key
            req_number = req.get('number')
            if req_number and req_number not in seen:
                seen.add(req_number)
                unique_requirements.append(req)
        
        return unique_requirements
    
    @staticmethod
    def sort_by_update_date(requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort requirements by update date (most recent first)."""
        return sorted(
            requirements,
            key=lambda x: x.get('updateDate', ''),
            reverse=True
        )

# --- API Wrapper ---

async def safe_house_requirements_request(endpoint: str, params: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """Safe API request wrapper for house requirements endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint=endpoint,
        ctx=ctx,
        params=params,
        timeout_override=10.0
    )

# --- Response Processing Helper ---

def clean_house_requirements_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Clean and process house requirements response data."""
    if 'houseRequirements' not in data:
        return []
    
    requirements = data['houseRequirements']
    if not requirements:
        return []
    
    # Apply custom deduplication and sorting
    processed_requirements = HouseRequirementsProcessor.deduplicate_requirements(requirements)
    processed_requirements = HouseRequirementsProcessor.sort_by_update_date(processed_requirements)
    
    return processed_requirements

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
    
    # req_data is now the requirement object directly
    req = req_data
    
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
    if 'submittingOfficial' in req:
        lines.append(f"Submitting Official: {req.get('submittingOfficial', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in req:
        lines.append(f"\nUpdate Date: {req.get('updateDate', 'N/A')}")
    
    return "\n".join(lines)

def format_matching_communications(comms_data: Dict[str, Any]) -> str:
    """Formats matching communications for a house requirement."""
    if not comms_data or 'houseCommunications' not in comms_data:
        return "No matching communications found."
    
    communications = comms_data['houseCommunications']
    if not communications:
        return "No matching communications found."
    
    lines = ["Matching Communications:"]
    for comm in communications:
        lines.append("")
        lines.append(f"Congress: {comm.get('congressNumber', comm.get('congress', 'N/A'))}")
        lines.append(f"Communication Number: {comm.get('communicationNumber', comm.get('number', 'N/A'))}")
        
        # Add communication type if available
        if 'communicationType' in comm:
            comm_type = comm['communicationType']
            lines.append(f"Type: {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})")
        
        # Add update date if available
        if 'updateDate' in comm:
            lines.append(f"Update Date: {comm.get('updateDate', 'N/A')}")
        
        # Add URL if available
        if 'url' in comm:
            lines.append(f"URL: {comm.get('url', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://house-requirements/latest")
async def get_latest_house_requirements(ctx: Context) -> str:
    """
    Get the most recent house requirements.
    Returns the 10 most recently updated requirements by default.
    """
    try:
        params = {
            "format": "json",
            "limit": 10
        }
        
        logger.debug("Fetching latest house requirements")
        
        # Make the API request
        data = await safe_house_requirements_request("/house-requirement", params, ctx)
        
        if "error" in data:
            logger.error(f"Error fetching latest house requirements: {data['error']}")
            return format_error_response(CommonErrors.api_server_error("/house-requirement", message=data['error']))
        
        # Process the response
        requirements = clean_house_requirements_response(data)
        
        if not requirements:
            logger.info("No house requirements found")
            return "No house requirements found."
        
        logger.info(f"Found {len(requirements)} house requirements")
        
        # Format the results
        lines = ["# Latest House Requirements", ""]
        for req in requirements:
            lines.append(format_house_requirement_item(req))
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Unexpected error fetching latest house requirements: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("/house-requirement", message=str(e)))

# --- MCP Tools ---

@mcp.tool()
async def search_house_requirements(
    ctx: Context,
    limit: int = 10
) -> str:
    """
    Search for house requirements.
    
    Args:
        limit: Maximum number of results to return (default: 10).
    """
    # Parameter validation
    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not limit_validation.is_valid:
        logger.warning(f"Invalid limit parameter: {limit}")
        return format_error_response(CommonErrors.invalid_parameter(
            "limit",
            limit,
            limit_validation.error_message
        ))
    
    try:
        params = {
            "format": "json",
            "limit": limit
        }
        
        endpoint = "/house-requirement"
        
        # Log the search parameters
        search_params = []
        if limit != 10:
            search_params.append(f"limit={limit}")
        
        search_str = ", ".join(search_params) if search_params else "default parameters"
        logger.debug(f"Searching house requirements with {search_str}")
        
        # Make the API request
        data = await safe_house_requirements_request(endpoint, params, ctx)
        
        if "error" in data:
            logger.error(f"Error searching house requirements: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Handle general search
        requirements = clean_house_requirements_response(data)
        
        if not requirements:
            logger.info("No house requirements found matching the search criteria")
            return "No house requirements found matching the search criteria."
        
        logger.info(f"Found {len(requirements)} house requirements matching the search criteria")
        
        # Format the results
        lines = ["# House Requirements Search Results", ""]
        for req in requirements[:limit]:
            lines.append(format_house_requirement_item(req))
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Unexpected error searching house requirements: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(endpoint, message=str(e)))

@mcp.tool()
async def get_house_requirement_details(
    ctx: Context,
    requirement_number: int
) -> str:
    """
    Get detailed information for a specific house requirement.
    
    Args:
        requirement_number: The requirement number (e.g., 8070).
    """
    # Parameter validation
    if not isinstance(requirement_number, int) or requirement_number <= 0:
        logger.warning(f"Invalid requirement_number parameter: {requirement_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "requirement_number",
            requirement_number,
            "Must be a positive integer"
        ))
    
    try:
        params = {"format": "json"}
        endpoint = f"/house-requirement/{requirement_number}"
        
        logger.debug(f"Fetching details for house requirement {requirement_number}")
        
        # Make the API request
        data = await safe_house_requirements_request(endpoint, params, ctx)
        
        if "error" in data:
            logger.error(f"Error fetching house requirement details: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Check for the correct response key
        if 'houseRequirement' in data:
            requirement = data['houseRequirement']
        elif 'house-requirement' in data:
            requirement = data['house-requirement']
        else:
            logger.warning(f"House requirement {requirement_number} not found in response")
            return f"House requirement {requirement_number} not found."
        
        logger.info(f"Found house requirement {requirement_number}")
        return format_house_requirement_detail(requirement)
        
    except Exception as e:
        logger.error(f"Unexpected error fetching house requirement details: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(endpoint, message=str(e)))

@mcp.tool()
async def get_house_requirement_matching_communications(
    ctx: Context,
    requirement_number: int
) -> str:
    """
    Get matching communications for a specific house requirement.
    
    Args:
        requirement_number: The requirement number (e.g., 8070).
    """
    # Parameter validation
    if not isinstance(requirement_number, int) or requirement_number <= 0:
        logger.warning(f"Invalid requirement_number parameter: {requirement_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "requirement_number",
            requirement_number,
            "Must be a positive integer"
        ))
    
    try:
        params = {"format": "json"}
        endpoint = f"/house-requirement/{requirement_number}/matching-communications"
        
        logger.debug(f"Fetching matching communications for house requirement {requirement_number}")
        
        # Make the API request
        data = await safe_house_requirements_request(endpoint, params, ctx)
        
        if "error" in data:
            logger.error(f"Error fetching matching communications: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        logger.info(f"Found matching communications for house requirement {requirement_number}")
        return format_matching_communications(data)
        
    except Exception as e:
        logger.error(f"Unexpected error fetching matching communications: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(endpoint, message=str(e)))
