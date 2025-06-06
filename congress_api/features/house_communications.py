# congress_api/features/house_communications.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Import reliability framework components
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import HouseCommunicationsProcessor
from ..core.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize defensive API wrapper for house communications
defensive_wrapper = DefensiveAPIWrapper()

async def safe_house_communications_request(endpoint: str, params: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """Make a safe API request for house communications with defensive wrapper."""
    return await defensive_wrapper.safe_api_request(
        endpoint=endpoint,
        params=params,
        ctx=ctx
    )

# --- Formatting Helpers ---

def format_house_communication_item(item: Dict[str, Any]) -> str:
    """Formats a single house communication item for display in a list."""
    # Handle both field name formats (list vs detail endpoints)
    congress_number = item.get('congressNumber') or item.get('congress', 'N/A')
    comm_number = item.get('communicationNumber') or item.get('number', 'N/A')
    
    lines = [
        f"Congress: {congress_number}",
        f"Chamber: {item.get('chamber', 'N/A')}",
        f"Communication Number: {comm_number}"
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
    
    # comm_data is now the communication object directly
    comm = comm_data
    
    # Handle both field name formats (list vs detail endpoints)
    comm_number = comm.get('number') or comm.get('communicationNumber', 'N/A')
    congress_number = comm.get('congressNumber') or comm.get('congress', 'N/A')
    
    lines = [
        f"House Communication - {congress_number}/{comm.get('communicationType', {}).get('code', 'N/A')}/{comm_number}",
        f"Congress: {congress_number}",
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

# --- Helper Functions ---

async def get_latest_house_communications(ctx: Context, limit: int = 10) -> List[Dict[str, Any]]:
    """Helper function to get latest house communications."""
    try:
        params = {
            "format": "json",
            "limit": limit
        }
        
        logger.debug("Fetching latest house communications")
        data = await safe_house_communications_request("/house-communication", params, ctx)
        
        if "error" in data:
            logger.error(f"Error retrieving latest house communications: {data['error']}")
            return []
        
        if 'houseCommunications' not in data:
            logger.warning("No houseCommunications field in response")
            return []
        
        communications = data['houseCommunications']
        if not communications:
            logger.info("No house communications found")
            return []
        
        # Apply response processing
        processed_communications = HouseCommunicationsProcessor.deduplicate_communications(communications)
        processed_communications = HouseCommunicationsProcessor.sort_by_update_date(processed_communications)
        
        logger.info(f"Retrieved {len(processed_communications)} latest house communications")
        return processed_communications[:limit]
        
    except Exception as e:
        logger.error(f"Unexpected error getting latest house communications: {str(e)}")
        return []

# --- MCP Resources ---

# @require_paid_access
@mcp.resource("congress://house-communications/latest")
async def latest_house_communications_resource(ctx: Context) -> str:
    """Static resource providing the 10 most recent house communications."""
    try:
        communications = await get_latest_house_communications(ctx, limit=10)
        
        if not communications:
            return "No recent house communications available."
        
        lines = ["# Latest House Communications", ""]
        for comm in communications:
            lines.append(format_house_communication_item(comm))
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error in latest house communications resource: {str(e)}")
        return format_error_response(CommonErrors.api_server_error("/house-communication", message=str(e)))

# --- MCP Tools ---

# @require_paid_access
async def get_house_communication_details(
    ctx: Context,
    congress: int,
    communication_type: str,
    communication_number: int
) -> str:
    """
    Get detailed information about a specific house communication.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        communication_type: Communication type (e.g., "ec", "ml", "pm", "pt")
        communication_number: Communication number
    """
    # Parameter validation
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        logger.warning(f"Invalid congress parameter: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Validate communication type
    valid_types = ["ec", "ml", "pm", "pt"]
    if communication_type.lower() not in valid_types:
        logger.warning(f"Invalid communication_type parameter: {communication_type}")
        return format_error_response(CommonErrors.invalid_communication_type(communication_type))
    
    # Validate communication number
    if not isinstance(communication_number, int) or communication_number < 1:
        logger.warning(f"Invalid communication_number parameter: {communication_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "communication_number", 
            communication_number, 
            "Communication number must be a positive integer"
        ))
    
    try:
        params = {
            "format": "json"
        }
        
        logger.debug(f"Fetching house communication {congress}/{communication_type}/{communication_number}")
        data = await safe_house_communications_request(f"/house-communication/{congress}/{communication_type}/{communication_number}", params, ctx)
        
        # Log the entire response structure for debugging
        logger.debug(f"API response structure: {list(data.keys()) if isinstance(data, dict) else 'Not a dictionary'}")
        
        if "error" in data:
            logger.error(f"Error retrieving house communication {congress}/{communication_type}/{communication_number}: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(f"/house-communication/{congress}/{communication_type}/{communication_number}", message=data['error']))
        
        # Check for house communication data
        if 'house-communication' in data:
            comm_data = data['house-communication']
        elif 'houseCommunication' in data:
            comm_data = data['houseCommunication']
        elif 'houseCommunications' in data and data['houseCommunications']:
            comm_data = data['houseCommunications'][0]
        else:
            logger.warning(f"No house communication data found for {congress}/{communication_type}/{communication_number}")
            return f"House communication {congress}/{communication_type}/{communication_number} not found."
        
        logger.info(f"Retrieved details for house communication {congress}/{communication_type}/{communication_number}")
        return format_house_communication_detail(comm_data)
        
    except Exception as e:
        logger.error(f"Unexpected error getting house communication details {congress}/{communication_type}/{communication_number}: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"/house-communication/{congress}/{communication_type}/{communication_number}", message=str(e)))

# @require_paid_access
async def search_house_communications(
    ctx: Context,
    congress: Optional[int] = None,
    communication_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for house communications based on various criteria.
    
    Args:
        congress: Optional Congress number (e.g., 117)
        communication_type: Optional communication type (e.g., "ec", "ml", "pm", "pt")
        limit: Maximum number of results to return (default: 10)
    """
    # Parameter validation
    if congress is not None:
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress parameter: {congress}")
            return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    if communication_type is not None:
        valid_types = ["ec", "ml", "pm", "pt"]
        if communication_type.lower() not in valid_types:
            logger.warning(f"Invalid communication_type parameter: {communication_type}")
            return format_error_response(CommonErrors.invalid_communication_type(communication_type))
    
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
        data = await safe_house_communications_request(endpoint, params, ctx)
        
        if "error" in data:
            logger.error(f"Error searching house communications: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        if 'houseCommunications' not in data:
            logger.warning("No houseCommunications field in response")
            return "No house communications found matching the search criteria."
        
        communications = data['houseCommunications']
        if not communications:
            logger.info("No house communications found matching the search criteria")
            return "No house communications found matching the search criteria."
        
        # Apply response processing
        processed_communications = HouseCommunicationsProcessor.deduplicate_communications(communications)
        processed_communications = HouseCommunicationsProcessor.sort_by_update_date(processed_communications)
        
        # Debug logging to see what fields are present
        if processed_communications:
            sample_comm = processed_communications[0]
            logger.debug(f"Sample communication fields: {list(sample_comm.keys())}")
            logger.debug(f"Sample communication data: {sample_comm}")
        
        logger.info(f"Found {len(processed_communications)} house communications matching the search criteria")
        
        # Format the results
        lines = ["# House Communications Search Results", ""]
        for comm in processed_communications[:limit]:
            lines.append(format_house_communication_item(comm))
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Unexpected error searching house communications: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(endpoint, message=str(e)))
