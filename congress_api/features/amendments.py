# amendments.py
from typing import Dict, Any, Optional, List
import json
import logging
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import format_error_response, APIErrorResponse
from ..core.response_utils import ResponseProcessor
from ..core.auth import require_paid_access

# Configure logging
logger = logging.getLogger(__name__)

# Formatting helpers
def format_amendment_summary(amendment: Dict[str, Any]) -> str:
    """Format an amendment into a readable summary."""
    result = []
    result.append(f"Amendment: {amendment.get('number', 'Unknown')}")
    result.append(f"Type: {amendment.get('type', 'Unknown')}")
    result.append(f"Congress: {amendment.get('congress', 'Unknown')}")
    
    if "purpose" in amendment:
        result.append(f"Purpose: {amendment.get('purpose', 'Not specified')}")
    
    if "latestAction" in amendment:
        action = amendment["latestAction"]
        result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    result.append(f"URL: {amendment.get('url', 'No URL available')}")
    return "\n".join(result)

def format_amendment_details(amendment: Dict[str, Any]) -> str:
    """Format detailed amendment information."""
    result = []
    
    # Basic information
    result.append(f"# Amendment {amendment.get('number', 'Unknown')} - {amendment.get('congress', 'Unknown')}th Congress\n")
    
    if "type" in amendment:
        result.append(f"## Type\n{amendment['type']}\n")
    
    if "purpose" in amendment:
        result.append(f"## Purpose\n{amendment['purpose']}\n")
    
    if "description" in amendment:
        result.append(f"## Description\n{amendment['description']}\n")
    
    if "sponsors" in amendment and amendment["sponsors"]:
        sponsors = amendment["sponsors"]
        result.append("## Sponsors")
        for sponsor in sponsors:
            name = sponsor.get("name", "Unknown")
            party = sponsor.get("party", "")
            state = sponsor.get("state", "")
            bioguide_id = sponsor.get("bioguideId", "")
            result.append(f"- {name} ({party}-{state}), Bioguide ID: {bioguide_id}")
        result.append("")
    
    if "actions" in amendment and amendment["actions"]:
        actions = amendment["actions"]
        result.append("## Recent Actions")
        
        # Handle different data structures for actions
        if isinstance(actions, list):
            # If actions is a list, take up to 5 items
            action_items = actions[:5] if len(actions) > 5 else actions
        elif isinstance(actions, dict) and "item" in actions:
            # If actions is a dict with an 'item' key (common in Congress.gov API)
            items = actions["item"]
            if isinstance(items, list):
                action_items = items[:5] if len(items) > 5 else items
            else:
                # If there's only one item, wrap it in a list
                action_items = [items]
        else:
            # If we can't determine the structure, just use an empty list
            logger.warning(f"Unexpected actions structure: {type(actions)}")
            action_items = []
        
        for action in action_items:
            date = action.get("actionDate", "Unknown date")
            text = action.get("text", "Unknown action")
            result.append(f"- {date}: {text}")
        result.append("")
    
    return "\n".join(result)

def format_amendment_action(action: Dict[str, Any]) -> str:
    """Format an amendment action into a readable string."""
    result = []
    date = action.get("actionDate", "Unknown date")
    text = action.get("text", "Unknown action")
    result.append(f"- {date}: {text}")
    
    if "recordedVotes" in action and action["recordedVotes"]:
        votes = action["recordedVotes"]
        for vote in votes:
            chamber = vote.get("chamber", "Unknown")
            roll_number = vote.get("rollNumber", "Unknown")
            result.append(f"  - Recorded Vote: {chamber} Roll Call #{roll_number}")
    
    return "\n".join(result)

# Resources
@mcp.resource("congress://amendments/latest")
async def get_latest_amendments(ctx: Context) -> str:
    """
    Get the most recent amendments introduced in Congress.
    
    Returns a list of the 10 most recently updated amendments across all
    Congresses, sorted by update date in descending order.
    """
    logger.info("Accessing latest amendments resource")
    try:
        data = await DefensiveAPIWrapper.safe_api_request("/amendment", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")  
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} amendments")
        
        if not amendments:
            return "No amendments found."
        
        result = ["# Latest Amendments in Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))
        
        return "\n\n".join(result)
    except Exception as e:
        logger.error(f"Exception in get_latest_amendments: {str(e)}")
        return f"Error retrieving latest amendments: {str(e)}"

@mcp.resource("congress://amendments/{congress}")
async def get_amendments_by_congress(ctx: Context, congress: str) -> str:
    """
    Get amendments from a specific Congress.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated amendments from the
    specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing amendments for Congress {congress}")
    try:
        data = await DefensiveAPIWrapper.safe_api_request(f"/amendment/{congress}", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received for Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            logger.error(f"Error in API response for Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} amendments for Congress {congress}")
        
        if not amendments:
            return f"No amendments found for the {congress}th Congress."
        
        result = [f"# Amendments in the {congress}th Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))
        
        return "\n\n".join(result)
    except Exception as e:
        logger.error(f"Exception in get_amendments_by_congress for Congress {congress}: {str(e)}")
        return f"Error retrieving amendments for the {congress}th Congress: {str(e)}"

@mcp.resource("congress://amendments/{congress}/{amendment_type}")
async def get_amendments_by_type(ctx: Context,congress: str, amendment_type: str) -> str:
    """
    Get amendments from a specific Congress and amendment type.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        amendment_type: The type of amendment (e.g., "samdt", "hamdt")
        
    Returns a list of the 10 most recently updated amendments of the specified
    type from the specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing {amendment_type} amendments for Congress {congress}")

    try:
        data = await DefensiveAPIWrapper.safe_api_request(f"/amendment/{congress}/{amendment_type}", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received for {amendment_type} amendments in Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            logger.error(f"Error in API response for {amendment_type} amendments in Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} {amendment_type} amendments for Congress {congress}")
        
        if not amendments:
            return f"No {amendment_type.upper()} amendments found for the {congress}th Congress."
        
        result = [f"# {amendment_type.upper()} Amendments in the {congress}th Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))
        
        return "\n\n".join(result)
        
    except Exception as e:
        logger.error(f"Exception in get_amendments_by_type for {amendment_type} amendments in Congress {congress}: {str(e)}")
        return f"Error retrieving {amendment_type.upper()} amendments for the {congress}th Congress: {str(e)}"

# Tools
# @require_paid_access
async def get_bill_amendments(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get amendments for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))
    
    bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
    if not bill_type_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid bill type: {bill_type_validation.error_message}",
            suggestions=bill_type_validation.suggestions,
            error_code="INVALID_BILL_TYPE"
        ))
    
    if bill_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Bill number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_BILL_NUMBER"
        ))
    
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/amendments"
    
    # Use defensive API wrapper
    try:
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {}, timeout_override=10.0)
        
        amendments = data.get("amendments", [])
        if not amendments:
            return f"No amendments found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
        
        # Apply deduplication
        original_count = len(amendments)
        amendments = ResponseProcessor.deduplicate_results(amendments, ["number", "type", "congress"])
        duplicates_removed = original_count - len(amendments)
        
        result = [f"Found {len(amendments)} amendments for {bill_type.upper()} {bill_number} in the {congress}th Congress"]
        if duplicates_removed > 0:
            result[0] += f" ({duplicates_removed} duplicates removed)"
        result[0] += ":"
        
        for amendment in amendments:
            result.append("\n" + format_amendment_summary(amendment))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_amendments: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve bill amendments due to an unexpected error",
            suggestions=[
                "Verify the bill exists",
                "Check bill type and number are correct",
                "Try again in a few moments"
            ],
            error_code="BILL_AMENDMENTS_RETRIEVAL_FAILED"
        ))

# @require_paid_access
async def search_amendments(
    ctx: Context,
    keywords: str, 
    congress: Optional[int] = None, 
    amendment_type: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc"
) -> str:
    """
    Search for amendments based on keywords.
    
    Args:
        keywords: Keywords to search for in amendment purpose and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        amendment_type: Optional amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
    """
    # Parameter validation using reliability framework
    if congress is not None:
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(APIErrorResponse(
                error_type="validation",
                message=f"Invalid congress number: {congress_validation.error_message}",
                suggestions=congress_validation.suggestions,
                error_code="INVALID_CONGRESS_NUMBER"
            ))
    
    if amendment_type is not None:
        amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
        if not amendment_validation.is_valid:
            return format_error_response(APIErrorResponse(
                error_type="validation", 
                message=f"Invalid amendment type: {amendment_validation.error_message}",
                suggestions=amendment_validation.suggestions,
                error_code="INVALID_AMENDMENT_TYPE"
            ))
    
    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))
    
    # Build endpoint and parameters
    params = {
        "query": keywords,
        "limit": limit,
        "sort": sort
    }
    
    endpoint = "/amendment"
    if congress is not None:
        endpoint = f"/amendment/{congress}"
        if amendment_type is not None:
            endpoint = f"/amendment/{congress}/{amendment_type}"
    
    # Use defensive API wrapper
    try:
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, params, timeout_override=15.0)
        
        amendments = data.get("amendments", [])
        if not amendments:
            return f"No amendments found matching '{keywords}'."
        
        # Apply deduplication
        original_count = len(amendments)
        amendments = ResponseProcessor.deduplicate_results(amendments, ["number", "type", "congress"])
        duplicates_removed = original_count - len(amendments)
        
        # Apply pagination
        amendments = ResponseProcessor.paginate_results(amendments, limit)
        
        # Format results
        result = [f"# Amendments Matching '{keywords}'\n"]
        if duplicates_removed > 0:
            result.append(f"*Found {original_count} results ({duplicates_removed} duplicates removed)*\n")
        
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))
        
        return "\n\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in search_amendments: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to search amendments due to an unexpected error",
            suggestions=["Try simplifying your search terms", "Check your internet connection", "Try again in a few moments"],
            error_code="SEARCH_FAILED"
        ))

# @require_paid_access
async def get_amendment_details(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> str:
    """
    Get detailed information about a specific amendment.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))
    
    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))
    
    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))
    
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}"
    
    # Use defensive API wrapper
    try:
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {}, timeout_override=10.0)
        
        # Log the data structure to help debug
        logger.debug(f"Amendment details data structure: {data.keys() if isinstance(data, dict) else type(data)}")
        
        # Handle different data structures for amendment
        amendment_data = data.get("amendment", {})
        
        # If amendment_data is empty, try to use the data directly
        if not amendment_data and isinstance(data, dict):
            # Some API responses don't have an 'amendment' wrapper
            if 'number' in data or 'type' in data or 'congress' in data:
                amendment_data = data
        
        if not amendment_data:
            return format_error_response(APIErrorResponse(
                error_type="not_found",
                message=f"Amendment {amendment_type.upper()} {amendment_number} not found in Congress {congress}",
                suggestions=[
                    "Verify the amendment number is correct",
                    "Check if the amendment type (samdt/hamdt) is correct",
                    "Try searching for amendments to find the correct number"
                ],
                error_code="AMENDMENT_NOT_FOUND"
            ))
        
        return format_amendment_details(amendment_data)
        
    except Exception as e:
        logger.error(f"Error in get_amendment_details: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment details due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check your internet connection", 
                "Try again in a few moments"
            ],
            error_code="DETAILS_RETRIEVAL_FAILED"
        ))

# @require_paid_access
async def get_amendment_actions(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int,
    limit: int = 10
) -> str:
    """
    Get actions for a specific amendment.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
        limit: Maximum number of actions to return (default: 10)
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))
    
    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))
    
    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))
    
    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=100)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))
    
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/actions"
    
    # Use defensive API wrapper
    try:
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {"limit": limit}, timeout_override=10.0)
        
        actions = data.get("actions", [])
        if not actions:
            return f"No actions found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."
        
        # Apply deduplication and pagination
        original_count = len(actions)
        actions = ResponseProcessor.deduplicate_results(actions, ["actionDate", "text"])
        actions = ResponseProcessor.paginate_results(actions, limit)
        duplicates_removed = original_count - len(actions)
        
        result = [f"# Actions for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]
        if duplicates_removed > 0:
            result.append(f"*({duplicates_removed} duplicate actions removed)*")
        
        for action in actions:
            result.append(format_amendment_action(action))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_amendment_actions: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment actions due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_ACTIONS_RETRIEVAL_FAILED"
        ))

# @require_paid_access
async def get_amendment_sponsors(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> str:
    """
    Get cosponsors for a specific amendment.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))
    
    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))
    
    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))
    
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/cosponsors"
    
    # Use defensive API wrapper
    try:
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {}, timeout_override=10.0)
        
        # Handle different data structures for cosponsors
        cosponsors_data = data.get("cosponsors", {})
        
        # Extract cosponsor items based on the data structure
        if isinstance(cosponsors_data, list):
            cosponsors = cosponsors_data
        elif isinstance(cosponsors_data, dict) and "item" in cosponsors_data:
            items = cosponsors_data["item"]
            if isinstance(items, list):
                cosponsors = items
            else:
                cosponsors = [items] if items else []
        else:
            cosponsors = []
        
        if not cosponsors:
            return f"No cosponsors found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."
        
        # Apply deduplication
        original_count = len(cosponsors)
        cosponsors = ResponseProcessor.deduplicate_results(cosponsors, ["bioguideId", "name"])
        duplicates_removed = original_count - len(cosponsors)
        
        result = [f"# Cosponsors for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]
        if duplicates_removed > 0:
            result.append(f"*({duplicates_removed} duplicate cosponsors removed)*")
        result.append(f"Total: {len(cosponsors)} cosponsors\n")
        
        for cosponsor in cosponsors:
            name = cosponsor.get("name", "Unknown")
            party = cosponsor.get("party", "")
            state = cosponsor.get("state", "")
            district = cosponsor.get("district", "")
            
            sponsor_info = f"- **{name}**"
            if party:
                sponsor_info += f" ({party}"
                if state:
                    sponsor_info += f"-{state}"
                    if district:
                        sponsor_info += f"-{district}"
                sponsor_info += ")"
            elif state:
                sponsor_info += f" ({state})"
            
            if "sponsorshipDate" in cosponsor:
                sponsor_info += f" - Sponsored: {cosponsor['sponsorshipDate']}"
            
            result.append(sponsor_info)
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_amendment_sponsors: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment sponsors due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_SPONSORS_RETRIEVAL_FAILED"
        ))
