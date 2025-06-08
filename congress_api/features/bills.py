from typing import Dict, List, Any, Optional, Union
import logging
from fastmcp import Context
import httpx
import re
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Reliability framework imports
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper, safe_bills_request
from ..core.exceptions import APIErrorResponse, CommonErrors, format_error_response
from ..core.response_utils import BillsProcessor, clean_bills_response

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Core API Helpers ---

async def _fetch_bill_data(ctx: Context, congress: Optional[int] = None, bill_type: Optional[str] = None, 
                          bill_number: Optional[int] = None, sub_endpoint: str = "", **params) -> Dict[str, Any]:
    """
    Core helper to fetch bill data from Congress.gov API with reliability framework.
    
    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 117)
        bill_type: Bill type (e.g., 'hr', 's')
        bill_number: Bill number
        sub_endpoint: Additional endpoint path (e.g., 'actions', 'cosponsors')
        **params: Additional query parameters (limit, sort, etc.)
        
    Returns:
        API response data or error response
    """
    try:
        # Validate parameters
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                logger.warning(f"Invalid congress number: {congress}")
                return {"error": congress_validation.error_message}
        
        if bill_type is not None:
            bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_type_validation.is_valid:
                logger.warning(f"Invalid bill type: {bill_type}")
                return {"error": bill_type_validation.error_message}
        
        if bill_number is not None:
            if not isinstance(bill_number, int) or bill_number <= 0:
                logger.warning(f"Invalid bill number: {bill_number}")
                return {"error": "Bill number must be a positive integer"}
        
        # Validate limit parameter if provided
        if 'limit' in params:
            limit_validation = ParameterValidator.validate_limit_range(params['limit'])
            if not limit_validation.is_valid:
                logger.warning(f"Invalid limit: {params['limit']}")
                return {"error": limit_validation.error_message}
            params['limit'] = limit_validation.sanitized_value
        
        # Build endpoint
        endpoint = _build_bill_endpoint(congress, bill_type, bill_number, sub_endpoint)
        logger.debug(f"Fetching bill data from endpoint: {endpoint}")
        
        # Set default parameters
        query_params = {'format': 'json'}
        query_params.update(params)
        
        # Use defensive API wrapper for the request
        return await safe_bills_request(endpoint, ctx, query_params)
        
    except Exception as e:
        logger.error(f"Error in _fetch_bill_data: {str(e)}")
        error_response = CommonErrors.api_server_error(f"bills endpoint: {endpoint if 'endpoint' in locals() else 'unknown'}")
        return {"error": format_error_response(error_response)}

def _build_bill_endpoint(congress: Optional[int] = None, bill_type: Optional[str] = None, 
                        bill_number: Optional[int] = None, sub_endpoint: str = "") -> str:
    """
    Build the appropriate Congress.gov API endpoint based on parameters.
    
    Args:
        congress: Congress number
        bill_type: Bill type (hr, s, hjres, sjres, hconres, sconres, hres, sres)
        bill_number: Bill number
        sub_endpoint: Additional endpoint path
    
    Returns:
        Constructed endpoint path
    """
    if congress and bill_type and bill_number:
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}"
    elif congress and bill_type:
        endpoint = f"/bill/{congress}/{bill_type.lower()}"
    elif congress:
        endpoint = f"/bill/{congress}"
    else:
        endpoint = "/bill"
    
    if sub_endpoint:
        endpoint += f"/{sub_endpoint}"
    
    return endpoint

async def _filter_bills_by_keywords(bills: List[Dict[str, Any]], keywords: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Filter bills by keywords in title and policy area with enhanced reliability.
    
    Args:
        bills: List of bill dictionaries
        keywords: Keywords to search for
        limit: Maximum number of results to return
    
    Returns:
        Filtered and deduplicated list of bills
    """
    try:
        # Validate inputs
        if not isinstance(bills, list):
            logger.warning("Bills parameter must be a list")
            return []
        
        if not keywords or not bills:
            # Apply deduplication even for unfiltered results
            deduplicated = BillsProcessor.deduplicate_bills(bills)
            return deduplicated[:limit]
        
        # Validate limit
        limit_validation = ParameterValidator.validate_limit_range(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit in filter: {limit}, using default")
            limit = 10
        else:
            limit = limit_validation.sanitized_value
        
        keywords_lower = keywords.lower().strip()
        if not keywords_lower:
            deduplicated = BillsProcessor.deduplicate_bills(bills)
            return deduplicated[:limit]
        
        filtered_bills = []
        
        for bill in bills:
            if not isinstance(bill, dict):
                continue
                
            # Check title
            title = bill.get('title', '').lower()
            # Check policy area
            policy_area = bill.get('policyArea', {}).get('name', '').lower() if bill.get('policyArea') else ''
            
            # Search in multiple fields
            keyword_list = [kw.strip() for kw in keywords_lower.split() if kw.strip()]
            
            title_match = any(keyword in title for keyword in keyword_list)
            policy_match = any(keyword in policy_area for keyword in keyword_list)
            
            if title_match or policy_match:
                filtered_bills.append(bill)
                if len(filtered_bills) >= limit * 2:  # Get extra for deduplication
                    break
        
        # Apply deduplication to filtered results
        deduplicated = BillsProcessor.deduplicate_bills(filtered_bills)
        
        logger.debug(f"Filtered {len(bills)} bills to {len(filtered_bills)}, deduplicated to {len(deduplicated)}")
        
        return deduplicated[:limit]
        
    except Exception as e:
        logger.error(f"Error in _filter_bills_by_keywords: {str(e)}")
        # Return original bills (up to limit) on error
        return bills[:limit] if isinstance(bills, list) else []

# --- Formatting Helpers ---

def format_bill_summary(bill: Dict[str, Any]) -> str:
    """Format a bill into a brief readable summary."""
    result = []
    
    # Basic info
    bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
    result.append(f"**{bill_id}** (Congress {bill.get('congress', 'Unknown')})")
    
    if "title" in bill:
        result.append(f"**Title:** {bill['title']}")
    
    # Latest action
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"**Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    # URL
    if "url" in bill:
        result.append(f"**URL:** {bill['url']}")
    
    return "\n".join(result)

def format_bill_detail(bill: Dict[str, Any]) -> str:
    """Format a bill into comprehensive detailed information."""
    result = []
    
    # Header
    bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
    result.append(f"# {bill_id} - Congress {bill.get('congress', 'Unknown')}")
    result.append("")
    
    # Title
    if "title" in bill:
        result.append(f"**Title:** {bill['title']}")
    
    # Sponsors
    if "sponsors" in bill and bill["sponsors"]:
        sponsors = bill["sponsors"]
        sponsor_names = [s.get("fullName", "Unknown") for s in sponsors]
        result.append(f"**Sponsor{'s' if len(sponsor_names) > 1 else ''}:** {', '.join(sponsor_names)}")
    
    # Cosponsors
    if "cosponsors" in bill and "count" in bill["cosponsors"]:
        result.append(f"**Cosponsors:** {bill['cosponsors']['count']}")
    
    # Latest Action
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"**Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    # Committees
    if "committees" in bill and "count" in bill["committees"]:
        result.append(f"**Committees:** {bill['committees']['count']}")
    
    # Policy Area
    if "policyArea" in bill and "name" in bill["policyArea"]:
        result.append(f"**Policy Area:** {bill['policyArea']['name']}")
    
    # Subjects
    if "subjects" in bill and "count" in bill["subjects"]:
        result.append(f"**Subjects:** {bill['subjects']['count']}")
    
    # Text Versions
    if "textVersions" in bill and "count" in bill["textVersions"] and bill["textVersions"]["count"] > 0:
        result.append("**Text Versions Available:** Use get_bill_text_versions tool for text versions.")
    
    # URL
    if "url" in bill:
        result.append(f"\n**URL:** {bill['url']}")
    
    return "\n".join(result)

def format_bill_actions(actions: List[Dict[str, Any]], congress: int, bill_type: str, bill_number: int) -> str:
    """Format bill actions into a readable timeline."""
    if not actions:
        return f"No actions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"## Legislative Actions Timeline for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
    
    for action in actions:
        action_date = action.get('actionDate', 'Unknown date')
        action_text = action.get('text', 'No description')
        action_type = action.get('type', '')
        
        result.append(f"**{action_date}** - {action_text}")
        if action_type:
            result.append(f"  *Type: {action_type}*")
        result.append("")
    
    return "\n".join(result)

def format_bill_text_versions(versions: List[Dict[str, Any]]) -> str:
    """Format bill text versions into a readable list."""
    if not versions:
        return "No text versions found."
    
    result = ["## Available Text Versions", ""]
    
    for version in versions:
        version_type = version.get('type', 'Unknown')
        date = version.get('date', 'Unknown date')
        
        result.append(f"**{version_type}** ({date})")
        
        if 'formats' in version:
            for format_info in version['formats']:
                format_type = format_info.get('type', 'Unknown format')
                url = format_info.get('url', 'No URL')
                result.append(f"  - {format_type}: {url}")
        
        result.append("")
    
    return "\n".join(result)

# --- Tools ---

async def search_bills(
    ctx: Context,
    keywords: str, 
    congress: Optional[int] = None, 
    bill_type: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """
    Search for bills based on keywords with smart search strategy and reliability framework.
    
    This function implements a multi-tier search strategy:
    1. Direct lookup if congress/bill_type/bill_number pattern detected
    2. Targeted search with congress + bill_type for smaller dataset
    3. Broad search with keywords only for larger dataset
    
    Args:
        keywords: Keywords to search for in bill titles and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    try:
        # Validate parameters using reliability framework
        if not keywords or not keywords.strip():
            error_response = CommonErrors.invalid_parameter(
                "keywords", 
                keywords, 
                "Keywords parameter is required and cannot be empty"
            )
            return format_error_response(error_response)
        
        # Validate congress parameter
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        if bill_type is not None:
            bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_type_validation.is_valid:
                return format_error_response(CommonErrors.invalid_bill_type(bill_type))
            bill_type = bill_type_validation.sanitized_value
        
        # Validate limit parameter
        limit_validation = ParameterValidator.validate_limit_range(limit)
        if not limit_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("limit", limit, limit_validation.error_message))
        limit = limit_validation.sanitized_value
        
        # Sanitize keywords
        keywords = keywords.strip()
        
        # Check for direct bill number pattern (e.g., "hr 1", "s 2", "HR1", "S2")
        import re
        bill_pattern = re.match(r'^([a-zA-Z]+)\s*(\d+)$', keywords)
        
        if bill_pattern and congress:
            # Direct lookup strategy
            detected_type = bill_pattern.group(1).lower()
            detected_number = int(bill_pattern.group(2))
            
            # Validate detected bill type
            type_validation = ParameterValidator.validate_bill_type(detected_type)
            if type_validation.is_valid:
                logger.debug(f"Direct lookup detected: {detected_type} {detected_number} in Congress {congress}")
                
                try:
                    return await get_bill_details(ctx, congress, detected_type, detected_number)
                except Exception as e:
                    logger.warning(f"Direct lookup failed: {e}")
                    # Fall through to keyword search
        
        # Build search parameters with validation
        params = {
            'limit': min(limit * 5, 250),  # Fetch more for better filtering
            'sort': sort
        }
        
        # Validate date parameters if provided
        if from_date:
            # Basic date format validation
            if not re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', from_date):
                error_response = CommonErrors.invalid_parameter(
                    "from_date", 
                    from_date, 
                    "Date must be in format YYYY-MM-DDTHH:MM:SSZ"
                )
                return format_error_response(error_response)
            params['fromDateTime'] = from_date
            
        if to_date:
            if not re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', to_date):
                error_response = CommonErrors.invalid_parameter(
                    "to_date", 
                    to_date, 
                    "Date must be in format YYYY-MM-DDTHH:MM:SSZ"
                )
                return format_error_response(error_response)
            params['toDateTime'] = to_date
        
        # Smart endpoint selection based on search strategy
        if congress and bill_type:
            # Strategy 2: Targeted search (congress + bill_type)
            logger.debug(f"Targeted search: Congress {congress}, Type {bill_type}")
            data = await _fetch_bill_data(ctx, congress=congress, bill_type=bill_type, **params)
            search_scope = f"bills of type {bill_type.upper()} in the {congress}th Congress"
        elif congress:
            # Strategy 2.5: Congress-specific search
            logger.debug(f"Congress-specific search: Congress {congress}")
            data = await _fetch_bill_data(ctx, congress=congress, **params)
            search_scope = f"bills in the {congress}th Congress"
        else:
            # Strategy 3: Broad search (all bills)
            logger.debug("Broad search: All bills")
            data = await _fetch_bill_data(ctx, **params)
            search_scope = "all recent bills"
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bills search endpoint")
            error_response.details = {"api_error": data["error"]}
            return format_error_response(error_response)
        
        # Process response using reliability framework
        bills = data.get("bills", [])
        if not bills:
            error_response = CommonErrors.data_not_found("bills", {
                "keywords": keywords,
                "congress": congress,
                "bill_type": bill_type,
                "search_scope": search_scope
            })
            return format_error_response(error_response)
        
        logger.debug(f"Found {len(bills)} bills from API before filtering")
        
        # Filter bills by keywords with enhanced processing
        filtered_bills = await _filter_bills_by_keywords(bills, keywords, limit)
        
        if not filtered_bills:
            guidance = []
            guidance.append(f"No bills found matching '{keywords}' in {search_scope}.")
            guidance.append(f"\n**Search Results:** Found {len(bills)} total bills but none matched keywords")
            
            if bills:
                # Show sample bill titles for debugging
                sample_titles = [bill.get('title', 'No title')[:100] + "..." for bill in bills[:3]]
                guidance.append(f"**Sample titles:** {sample_titles}")
            
            guidance.append(f"\n**Search Scope:** Comprehensive search across:")
            guidance.append("• Bill titles and policy areas")
            guidance.append("• (Optimized for performance)")
            guidance.append(f"\n**Search Limitations:** This search is limited to {search_scope}.")
            guidance.append("**Suggestions:**")
            guidance.append("• Try different or broader keywords")
            guidance.append("• Remove congress or bill_type filters for wider search")
            guidance.append("• Use specific bill identifiers (e.g., 'HR 1') for direct lookup")
            return "\n".join(guidance)
        
        # Format results
        result = [f"Found {len(filtered_bills)} bills matching '{keywords}' in {search_scope}:"]
        
        for bill in filtered_bills:
            result.append("\n" + format_bill_summary(bill))
        
        # Add search metadata
        if len(filtered_bills) == limit and len(bills) > len(filtered_bills):
            result.append(f"\n*Showing top {limit} results. Use higher limit for more results.*")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in search_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("bills search")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

# @require_paid_access
async def get_bill_details(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get detailed information about a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill details endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        bill = data.get("bill", {})
        if not bill:
            error_response = CommonErrors.data_not_found("bill", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        return format_bill_detail(bill)
        
    except Exception as e:
        logger.error(f"Error in get_bill_details: {str(e)}")
        error_response = CommonErrors.api_server_error("bill details")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_actions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 10
) -> str:
    """
    Get actions for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        limit: Maximum number of actions to return (default: 10)
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Validate limit parameter
        limit_validation = ParameterValidator.validate_limit_range(limit)
        if not limit_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("limit", limit, limit_validation.error_message))
        limit = limit_validation.sanitized_value
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/actions"
        data = await safe_bills_request(endpoint, ctx, {"limit": limit})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill actions endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        actions = data.get("actions", [])
        if not actions:
            error_response = CommonErrors.data_not_found("bill actions", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        return format_bill_actions(actions, congress, bill_type, bill_number)
        
    except Exception as e:
        logger.error(f"Error in get_bill_actions: {str(e)}")
        error_response = CommonErrors.api_server_error("bill actions")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_titles(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get titles for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/titles"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill titles endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        titles = data.get("titles", [])
        if not titles:
            error_response = CommonErrors.data_not_found("bill titles", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"Titles for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
        for i, title in enumerate(titles, 1):
            title_text = title.get("title", "Unknown title")
            title_type = title.get("titleType", "Unknown type")
            
            result.append(f"\n{i}. **{title_type}:** {title_text}")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_titles: {str(e)}")
        error_response = CommonErrors.api_server_error("bill titles")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_cosponsors(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get cosponsors for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/cosponsors"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill cosponsors endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        cosponsors = data.get("cosponsors", [])
        if not cosponsors:
            error_response = CommonErrors.data_not_found("bill cosponsors", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"Cosponsors for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
        for i, cosponsor in enumerate(cosponsors, 1):
            name = cosponsor.get("fullName", "Unknown")
            party = cosponsor.get("party", "")
            state = cosponsor.get("state", "")
            date = cosponsor.get("sponsorshipDate", "Unknown date")
            
            party_state = ""
            if party and state:
                party_state = f" [{party}-{state}]"
            elif party:
                party_state = f" [{party}]"
            elif state:
                party_state = f" [{state}]"
            
            result.append(f"\n{i}. {name}{party_state} - Date: {date}")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_cosponsors: {str(e)}")
        error_response = CommonErrors.api_server_error("bill cosponsors")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_subjects(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get legislative subjects for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/subjects"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill subjects endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        subjects = data.get("subjects", {})
        if not subjects:
            error_response = CommonErrors.data_not_found("bill subjects", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"Subjects for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
        
        # Policy Area
        if "policyArea" in subjects and "name" in subjects["policyArea"]:
            result.append(f"\n**Policy Area:** {subjects['policyArea']['name']}")
        
        # Legislative Subjects
        if "legislativeSubjects" in subjects and subjects["legislativeSubjects"]:
            result.append("\n**Legislative Subjects:**")
            for subject in subjects["legislativeSubjects"]:
                result.append(f"- {subject.get('name', 'Unknown')}")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_subjects: {str(e)}")
        error_response = CommonErrors.api_server_error("bill subjects")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_text_versions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get text versions for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/text"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill text versions endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        text_versions = data.get("textVersions", [])
        if not text_versions:
            error_response = CommonErrors.data_not_found("bill text versions", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        return format_bill_text_versions(text_versions)
        
    except Exception as e:
        logger.error(f"Error in get_bill_text_versions: {str(e)}")
        error_response = CommonErrors.api_server_error("bill text versions")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_related_bills(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get related bills for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/relatedbills"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill related bills endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        related_bills = data.get("relatedBills", [])
        if not related_bills:
            error_response = CommonErrors.data_not_found("related bills", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"Related bills for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
        for i, bill in enumerate(related_bills, 1):
            bill_num = bill.get("number", "Unknown")
            bill_title = bill.get("title", "No title")
            
            relationship = "Related bill"
            if "relationshipDetails" in bill and bill["relationshipDetails"]:
                rel_details = bill["relationshipDetails"][0]
                if "type" in rel_details:
                    relationship = rel_details["type"]
            
            result.append(f"\n{i}. **{bill_num}** - {relationship}")
            result.append(f"   Title: {bill_title}")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_related_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("bill related bills")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_amendments(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get amendments for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/amendments"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill amendments endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        amendments = data.get("amendments", [])
        if not amendments:
            error_response = CommonErrors.data_not_found("bill amendments", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"## Amendments for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
        result.append("*Note: This endpoint provides basic amendment information (number, description, latest action).*")
        result.append("*For detailed amendment information including sponsors and purpose, use the dedicated amendment tools.*")
        result.append("")
        
        for i, amendment in enumerate(amendments, 1):
            amend_number = amendment.get("number", "Unknown")
            amend_type = amendment.get("type", "Unknown")
            description = amendment.get("description", "No description available")
            
            result.append(f"**{i}. Amendment {amend_number}**")
            if amend_type != "Unknown":
                result.append(f"   **Type:** {amend_type}")
            result.append(f"   **Description:** {description}")
            
            if "latestAction" in amendment:
                action = amendment["latestAction"]
                result.append(f"   **Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
            
            result.append("")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_amendments: {str(e)}")
        error_response = CommonErrors.api_server_error("bill amendments")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_summaries(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get summaries for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/summaries"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill summaries endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        summaries = data.get("summaries", [])
        if not summaries:
            error_response = CommonErrors.data_not_found("bill summaries", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"## Summaries for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
        
        for i, summary in enumerate(summaries, 1):
            action_desc = summary.get("actionDesc", "Summary")
            action_date = summary.get("actionDate", "Unknown date")
            text = summary.get("text", "No summary text available")
            
            result.append(f"**{i}. {action_desc}** ({action_date})")
            result.append("")
            result.append(text)
            result.append("")
            result.append("---")
            result.append("")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_summaries: {str(e)}")
        error_response = CommonErrors.api_server_error("bill summaries")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_committees(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get committees for a specific bill with reliability framework.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/committees"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill committees endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        committees = data.get("committees", [])
        if not committees:
            error_response = CommonErrors.data_not_found("bill committees", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Format results
        result = [f"## Committees for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
        
        for i, committee in enumerate(committees, 1):
            name = committee.get("name", "Unknown committee")
            chamber = committee.get("chamber", "Unknown chamber")
            
            result.append(f"**{i}. {name}** ({chamber})")
            
            # Subcommittees
            if "subcommittees" in committee and committee["subcommittees"]:
                result.append("   **Subcommittees:**")
                for subcom in committee["subcommittees"]:
                    subcom_name = subcom.get("name", "Unknown subcommittee")
                    result.append(f"   - {subcom_name}")
            
            result.append("")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_bill_committees: {str(e)}")
        error_response = CommonErrors.api_server_error("bill committees")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_text(
    ctx: Context,
    congress: int, 
    bill_type: str, 
    bill_number: int,
    version: str = "latest"
) -> str:
    """
    Get available text versions and download URLs for a specific bill (metadata only).
    For actual bill text content, use get_bill_content() instead.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        version: Text version to retrieve ('latest', 'introduced', 'reported', or specific version code)
        
    Returns:
        Formatted list of available text formats (HTML, PDF, XML) with download URLs
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Validate version parameter
        valid_versions = ["latest", "introduced", "reported"]
        if version and not isinstance(version, str):
            error_response = CommonErrors.invalid_parameter(
                "version", 
                version, 
                f"Version must be a string. Valid options: {', '.join(valid_versions)} or specific version code"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/text"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill text endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        text_versions = data.get("textVersions", [])
        if not text_versions:
            error_response = CommonErrors.data_not_found("bill text versions", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Select the appropriate version
        selected_version = None
        if version == "latest":
            # Get the most recent version (first in the list)
            selected_version = text_versions[0]
        elif version == "introduced":
            # Look for introduced version
            for tv in text_versions:
                if "ih" in tv.get("type", "").lower() or "introduced" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        elif version == "reported":
            # Look for reported version
            for tv in text_versions:
                if "rh" in tv.get("type", "").lower() or "reported" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        else:
            # Look for specific version code
            for tv in text_versions:
                if version.lower() in tv.get("type", "").lower():
                    selected_version = tv
                    break
        
        if not selected_version:
            available_versions = [tv.get("type", "Unknown") for tv in text_versions]
            error_response = CommonErrors.data_not_found(f"bill text version '{version}'", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number,
                "available_versions": available_versions
            })
            return format_error_response(error_response)
        
        # Format the bill text information with direct links
        result = [
            f"# {bill_type.upper()} {bill_number} - {congress}th Congress",
            f"**Version:** {selected_version.get('type', 'Unknown')} ({selected_version.get('date', 'Unknown date')})",
            "",
            "## Available Text Formats",
            ""
        ]
        
        formats = selected_version.get("formats", [])
        if formats:
            for fmt in formats:
                format_type = fmt.get("type", "Unknown format")
                url = fmt.get("url", "No URL")
                result.append(f"**{format_type}:** {url}")
        else:
            result.append("No text formats available for this version.")
        
        result.extend([
            "",
            "## Usage Instructions",
            "• Click on any URL above to view or download the bill text",
            "• **Formatted Text** provides the most readable version",
            "• **PDF** is best for printing or offline reading", 
            "• **XML** contains structured data for processing",
            "",
            f"**Tip:** Use `get_bill_content` to retrieve the actual bill text content, or `get_bill_text_versions` to see all available versions for {bill_type.upper()} {bill_number}."
        ])
        
        return "\n".join(result)
    
    except Exception as e:
        logger.error(f"Error in get_bill_text: {str(e)}")
        error_response = CommonErrors.api_server_error("bill text")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

async def get_bill_content(
    ctx: Context,
    congress: int, 
    bill_type: str, 
    bill_number: int,
    version: str = "latest",
    chunk_number: int = 1,
    chunk_size: int = 8000
) -> str:
    """
    Get the actual text content of a specific bill (full text, not just URLs).
    Use this function to retrieve readable bill text with chunking support for large bills.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        version: Text version to retrieve ('latest', 'introduced', 'reported', or specific version code)
        chunk_number: Chunk number to retrieve (1-based, default: 1)
        chunk_size: Size of each chunk in characters (default: 8000)
        
    Returns:
        Formatted bill text content, stripped of HTML tags and cleaned for readability
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))
        
        # Validate bill_type parameter
        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value
        
        # Validate bill_number parameter
        if not isinstance(bill_number, int) or bill_number <= 0:
            error_response = CommonErrors.invalid_parameter(
                "bill_number", 
                bill_number, 
                "Bill number must be a positive integer"
            )
            return format_error_response(error_response)
        
        # Validate version parameter
        valid_versions = ["latest", "introduced", "reported"]
        if version and not isinstance(version, str):
            error_response = CommonErrors.invalid_parameter(
                "version", 
                version, 
                f"Version must be a string. Valid options: {', '.join(valid_versions)} or specific version code"
            )
            return format_error_response(error_response)
        
        # Validate chunk_number parameter
        if not isinstance(chunk_number, int) or chunk_number < 1:
            error_response = CommonErrors.invalid_parameter(
                "chunk_number", 
                chunk_number, 
                "Chunk number must be a positive integer (1-based)"
            )
            return format_error_response(error_response)
        
        # Validate chunk_size parameter
        if not isinstance(chunk_size, int) or chunk_size < 1000 or chunk_size > 50000:
            error_response = CommonErrors.invalid_parameter(
                "chunk_size", 
                chunk_size, 
                "Chunk size must be between 1000 and 50000 characters"
            )
            return format_error_response(error_response)
        
        # Use defensive API wrapper for the request
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/text"
        data = await safe_bills_request(endpoint, ctx, {})
        
        # Handle API errors
        if "error" in data:
            error_response = CommonErrors.api_server_error("bill text content endpoint")
            error_response.details = {"api_error": data["error"], "endpoint": endpoint}
            return format_error_response(error_response)
        
        # Process response
        text_versions = data.get("textVersions", [])
        if not text_versions:
            error_response = CommonErrors.data_not_found("bill text versions", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number
            })
            return format_error_response(error_response)
        
        # Select the appropriate version (same logic as get_bill_text)
        selected_version = None
        if version == "latest":
            # Get the most recent version (first in the list)
            selected_version = text_versions[0]
        elif version == "introduced":
            # Look for introduced version
            for tv in text_versions:
                if "ih" in tv.get("type", "").lower() or "introduced" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        elif version == "reported":
            # Look for reported version
            for tv in text_versions:
                if "rh" in tv.get("type", "").lower() or "reported" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        else:
            # Look for specific version code
            for tv in text_versions:
                if version.lower() in tv.get("type", "").lower():
                    selected_version = tv
                    break
        
        if not selected_version:
            available_versions = [tv.get("type", "Unknown") for tv in text_versions]
            error_response = CommonErrors.data_not_found(f"bill text version '{version}'", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number,
                "available_versions": available_versions
            })
            return format_error_response(error_response)
        
        # Get the formatted text URL (prefer HTML format)
        text_url = None
        formats = selected_version.get("formats", [])
        for fmt in formats:
            if fmt.get("type") == "Formatted Text":
                text_url = fmt.get("url")
                break
        
        if not text_url:
            error_response = CommonErrors.data_not_found("formatted text", {
                "congress": congress,
                "bill_type": bill_type.upper(),
                "bill_number": bill_number,
                "version": selected_version.get('type', 'Unknown'),
                "available_formats": [fmt.get("type", "Unknown") for fmt in formats]
            })
            return format_error_response(error_response)
        
        # Fetch the actual bill text content
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(text_url)
                if response.status_code != 200:
                    error_response = CommonErrors.api_server_error("bill content retrieval")
                    error_response.details = {
                        "http_status": response.status_code,
                        "url": text_url
                    }
                    return format_error_response(error_response)
                
                html_content = response.text
                
                # Extract text from HTML and clean it up
                # Remove script and style elements
                html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove HTML tags but preserve some structure
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                
                # Clean up whitespace and formatting
                clean_text = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)  # Multiple newlines to double
                clean_text = re.sub(r'[ \t]+', ' ', clean_text)  # Multiple spaces to single
                clean_text = clean_text.strip()
                
                # Calculate chunking
                total_chars = len(clean_text)
                total_chunks = (total_chars + chunk_size - 1) // chunk_size  # Ceiling division
                
                if chunk_number < 1 or chunk_number > total_chunks:
                    error_response = CommonErrors.invalid_parameter(
                        "chunk_number", 
                        chunk_number, 
                        f"Invalid chunk number. Bill has {total_chunks} chunks of {chunk_size} characters each"
                    )
                    return format_error_response(error_response)
                
                # Extract the requested chunk
                start_pos = (chunk_number - 1) * chunk_size
                end_pos = min(start_pos + chunk_size, total_chars)
                chunk_text = clean_text[start_pos:end_pos]
                
                # Add some overlap context if not the first chunk
                if chunk_number > 1 and start_pos > 200:
                    overlap_start = max(0, start_pos - 200)
                    overlap_text = clean_text[overlap_start:start_pos]
                    chunk_text = f"[...previous context: {overlap_text[-200:]}]\n\n{chunk_text}"
                
                result = [
                    f"# {bill_type.upper()} {bill_number} - {congress}th Congress",
                    f"**Version:** {selected_version.get('type', 'Unknown')} ({selected_version.get('date', 'Unknown date')})",
                    f"**Chunk:** {chunk_number} of {total_chunks} (characters {start_pos+1:,}-{end_pos:,} of {total_chars:,})",
                    f"**Source:** {text_url}",
                    "",
                    "## Bill Content",
                    "",
                    chunk_text
                ]
                
                if chunk_number < total_chunks:
                    result.extend([
                        "",
                        f"**Next:** Use `get_bill_content(congress={congress}, bill_type='{bill_type}', bill_number={bill_number}, version='{version}', chunk_number={chunk_number + 1})` for the next chunk."
                    ])
                
                return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Error fetching bill content from URL: {str(e)}")
            error_response = CommonErrors.api_server_error("bill content fetch")
            error_response.details = {"url": text_url, "exception": str(e)}
            return format_error_response(error_response)
    
    except Exception as e:
        logger.error(f"Error in get_bill_content: {str(e)}")
        error_response = CommonErrors.api_server_error("bill content")
        error_response.details = {"exception": str(e)}
        return format_error_response(error_response)

# --- Resources ---

@mcp.resource("congress://bills/types")
async def get_bill_types_reference(ctx: Context) -> str:
    """
    Get reference information about Congressional bill types.
    
    Returns static reference data about the 8 types of Congressional bills
    and resolutions, including their codes, full names, and descriptions.
    """
    return """# Congressional Bill Types Reference

## Overview
The U.S. Congress considers 8 different types of bills and resolutions, each with specific purposes and legislative processes.

## Bill Types

### **Bills** (Require Presidential Signature)

#### **HR - House Bill**
- **Origin**: House of Representatives
- **Purpose**: General legislation affecting the public
- **Process**: Requires passage by both chambers and Presidential signature
- **Example**: HR 1 - "For the People Act"

#### **S - Senate Bill** 
- **Origin**: Senate
- **Purpose**: General legislation affecting the public
- **Process**: Requires passage by both chambers and Presidential signature
- **Example**: S 1 - "For the People Act"

### **Joint Resolutions** (Require Presidential Signature)

#### **HJRES - House Joint Resolution**
- **Origin**: House of Representatives  
- **Purpose**: Limited matters, constitutional amendments, continuing appropriations
- **Process**: Same as bills - requires both chambers and Presidential signature
- **Special**: Constitutional amendments need 2/3 majority in both chambers

#### **SJRES - Senate Joint Resolution**
- **Origin**: Senate
- **Purpose**: Limited matters, constitutional amendments, continuing appropriations  
- **Process**: Same as bills - requires both chambers and Presidential signature
- **Special**: Constitutional amendments need 2/3 majority in both chambers

### **Concurrent Resolutions** (No Presidential Signature Required)

#### **HCONRES - House Concurrent Resolution**
- **Origin**: House of Representatives
- **Purpose**: Rules for both chambers, Congressional sentiments, budget resolutions
- **Process**: Requires passage by both chambers only
- **Example**: Setting time for Congressional adjournment

#### **SCONRES - Senate Concurrent Resolution**
- **Origin**: Senate  
- **Purpose**: Rules for both chambers, Congressional sentiments, budget resolutions
- **Process**: Requires passage by both chambers only
- **Example**: Annual budget resolution

### **Simple Resolutions** (Single Chamber Only)

#### **HRES - House Simple Resolution**
- **Origin**: House of Representatives
- **Purpose**: House rules, House sentiments, House internal matters
- **Process**: House passage only
- **Example**: Expressing condolences, House procedural rules

#### **SRES - Senate Simple Resolution**
- **Origin**: Senate
- **Purpose**: Senate rules, Senate sentiments, Senate internal matters  
- **Process**: Senate passage only
- **Example**: Expressing congratulations, Senate procedural rules

## Search Tips
- Use lowercase when searching: "hr", "s", "hjres", etc.
- Bills and Joint Resolutions become law if signed by the President
- Resolutions express Congressional opinion or set internal rules
- Constitutional amendments use Joint Resolutions but don't require Presidential signature

## API Usage
When using the Bills API tools, specify bill types using these exact codes:
`hr`, `s`, `hjres`, `sjres`, `hconres`, `sconres`, `hres`, `sres`
"""

@mcp.resource("congress://bills/congress-ranges")
async def get_congress_ranges_reference(ctx: Context) -> str:
    """
    Get reference information about Congress number ranges and coverage.
    
    Returns information about available Congress numbers, date ranges,
    and data coverage limitations for different Congressional periods.
    """
    return """# Congressional Number Ranges & Data Coverage

## Current Congress Information
- **Current Congress**: 119th Congress (2025-2026)
- **Previous Congress**: 118th Congress (2023-2024)
- **API Coverage**: Comprehensive data from 103rd Congress (1993) forward

## Congress Numbering System
- **First Congress**: 1st Congress (1789-1791)
- **Current Range**: 1-119 (as of 2025)
- **Duration**: Each Congress lasts 2 years (2 sessions)
- **Numbering**: Sequential since 1789

## Data Coverage by Period

### **Modern Era (103rd Congress - Present)**
- **Years**: 1993-Present
- **Congress Range**: 103-119
- **Data Quality**: Complete
- **Available Data**: Full metadata, text, actions, sponsors, summaries, amendments

### **Digital Transition (93rd-102nd Congress)**  
- **Years**: 1973-1992
- **Congress Range**: 93-102
- **Data Quality**: Limited
- **Available Data**: Basic metadata, some text versions

### **Historical Period (6th-92nd Congress)**
- **Years**: 1799-1972  
- **Congress Range**: 6-92
- **Data Quality**: Very Limited
- **Available Data**: Basic records, limited searchability
- **Note**: Bills from 6th-14th Congress (1799-1817) were not numbered

## Search Recommendations

### **For Current Research**
- **Use**: Congress 119 (current) or 118 (recent)
- **Best Results**: Full data availability, active legislation

### **For Historical Research**
- **Use**: Congress 103+ (1993+) for comprehensive data
- **Limited**: Congress 93-102 for basic information only

### **Special Notes**
- **Reserved Bills**: Leadership reserves low numbers (HR 1, S 1, etc.)
- **Numbering Gaps**: Some numbers may be skipped or reserved
- **Update Frequency**: New bills added daily during Congressional sessions

## API Usage Tips
- Specify Congress number for targeted searches: `congress=119`
- Use recent Congress numbers (115+) for best search results
- Combine with bill types for efficient filtering
- Check data availability before deep historical searches

## Congress Calendar
- **Odd Years**: First session of each Congress
- **Even Years**: Second session of each Congress  
- **Elections**: Even years (House every 2 years, Senate staggered)
- **New Congress**: Begins January 3rd of odd years
"""

@mcp.resource("congress://bills/status-definitions")
async def get_bill_status_definitions(ctx: Context) -> str:
    """
    Get reference definitions for bill statuses and legislative process stages.
    
    Returns explanations of common bill statuses, action types, and
    legislative process terminology used in bill tracking.
    """
    return """# Bill Status Definitions & Legislative Process

## Common Bill Statuses

### **Introduction & Referral**
- **Introduced**: Bill formally submitted to chamber
- **Referred to Committee**: Assigned to relevant committee for review
- **Subcommittee Referral**: Sent to specialized subcommittee

### **Committee Actions**
- **Committee Consideration**: Under active committee review
- **Markup**: Committee reviews and potentially amends bill text
- **Reported**: Committee approves bill and sends to full chamber
- **Committee Discharged**: Bill removed from committee without action

### **Floor Actions**
- **Placed on Calendar**: Scheduled for floor consideration
- **Floor Consideration**: Debated by full chamber
- **Passed Chamber**: Approved by originating chamber
- **Received in [Other Chamber]**: Sent to other chamber for consideration

### **Final Actions**
- **Passed Congress**: Approved by both House and Senate
- **Presented to President**: Sent to White House for signature
- **Became Public Law**: Signed by President, now law
- **Pocket Veto**: Unsigned by President when Congress adjourns
- **Veto Override**: Congress overrides Presidential veto

## Action Types Explained

### **Legislative Actions**
- **BecameLaw**: Bill signed into law by President
- **Introduced**: Initial submission to chamber
- **Passed**: Approved by a chamber
- **Failed**: Rejected by vote or procedural action

### **Committee Actions**
- **Referred**: Sent to committee
- **Reported**: Committee sends bill to floor
- **Discharged**: Removed from committee

### **Presidential Actions**
- **ToPresident**: Bill sent to White House
- **Signed**: President approves bill
- **Vetoed**: President rejects bill

## Bill Lifecycle Stages

### **Stage 1: Introduction**
1. Bill drafted by member or staff
2. Introduced in House or Senate
3. Assigned bill number
4. Referred to committee(s)

### **Stage 2: Committee Review**
1. Committee consideration
2. Hearings (optional)
3. Markup sessions
4. Committee vote
5. Report to full chamber

### **Stage 3: Floor Action**
1. Placed on calendar
2. Floor debate
3. Amendments considered
4. Final passage vote

### **Stage 4: Other Chamber**
1. Received from first chamber
2. Committee process (may be expedited)
3. Floor consideration
4. Passage or amendment

### **Stage 5: Resolution**
1. If amended, return to first chamber
2. Conference committee (if needed)
3. Final passage by both chambers
4. Sent to President

### **Stage 6: Presidential Action**
1. President signs (becomes law)
2. President vetoes (returns to Congress)
3. Pocket veto (if Congress adjourns)
4. Veto override (2/3 majority in both chambers)

## Status Interpretation Tips

### **Active Bills**
- Look for recent action dates
- "Passed" in one chamber means still active
- Committee activity indicates ongoing work

### **Stalled Bills**
- No recent actions (6+ months)
- Stuck in committee
- End of Congress approaching

### **Dead Bills**
- Failed vote
- End of Congress (bills die if not passed)
- Withdrawn by sponsor

## Search Strategy
- Use `get_bill_actions` for complete legislative history
- Check `latestAction` for current status
- Recent `updateDate` indicates active consideration
- Multiple chambers in actions = bill progressing
"""

@mcp.resource("congress://bills/usage-guide")
async def get_bills_api_usage_guide(ctx: Context) -> str:
    """
    Get usage guidelines and best practices for the Bills API.
    
    Returns information about search strategies, parameter combinations,
    rate limits, and tips for effective bill research.
    """
    return """# Bills API Usage Guide & Best Practices

## Search Strategies

### **1. Direct Bill Lookup**
**Best for**: Known bill numbers
```
search_bills("HR 1", congress=119)
search_bills("S 2025", congress=118)
```
- Use exact bill format: "HR 1", "S 1234"
- Include Congress number for precision
- Fastest method for specific bills

### **2. Keyword Search**
**Best for**: Topic-based research
```
search_bills("infrastructure", congress=119, limit=20)
search_bills("climate change", bill_type="hr")
```
- Use specific keywords for better results
- Searches bill titles and policy areas
- Combine with Congress/type filters

### **3. Targeted Filtering**
**Best for**: Focused research
```
search_bills("healthcare", congress=119, bill_type="hr", limit=10)
```
- Combine multiple filters for precision
- Use recent Congress numbers (118, 119)
- Limit results to manageable numbers

## Parameter Optimization

### **Congress Numbers**
- **Current Research**: Use 119 (current) or 118 (recent)
- **Recent Research**: Use 118 (2023-2024) 
- **Historical**: Use 103+ for comprehensive data
- **Avoid**: Very old Congress numbers (<100) unless necessary

### **Bill Types**
- **All Legislation**: Don't specify (searches all types)
- **Major Bills**: Use "hr" or "s" 
- **Resolutions**: Use "hres", "sres", "hconres", "sconres"
- **Constitutional**: Use "hjres", "sjres"

### **Limits & Sorting**
- **Default Limit**: 10 results (good starting point)
- **Research**: 20-50 results for comprehensive review
- **Default Sort**: updateDate+desc (most recent first)
- **Historical**: updateDate+asc for chronological order

## Effective Research Workflows

### **Topic Research Workflow**
1. **Broad Search**: `search_bills("topic", congress=119)`
2. **Review Results**: Identify relevant bills
3. **Deep Dive**: `get_bill_details()` for promising bills
4. **Track Progress**: `get_bill_actions()` for status
5. **Related Research**: `get_bill_related_bills()` for connections

### **Bill Tracking Workflow**
1. **Find Bill**: Direct lookup or keyword search
2. **Get Overview**: `get_bill_details()` for summary
3. **Check Status**: `get_bill_actions()` for latest activity
4. **Review Content**: `get_bill_summaries()` for analysis
5. **Monitor Changes**: `get_bill_text_versions()` for amendments

### **Legislative History Workflow**
1. **Identify Bill**: Search or direct lookup
2. **Full Actions**: `get_bill_actions()` for complete timeline
3. **Committee Work**: `get_bill_committees()` for review process
4. **Support Analysis**: `get_bill_cosponsors()` for backing
5. **Related Bills**: `get_bill_related_bills()` for context

## Common Use Cases

### **Journalists**
- Track breaking legislative news
- Research bill sponsors and supporters
- Monitor committee activities
- Find related legislation

### **Policy Researchers**
- Analyze legislative trends
- Compare similar bills across Congresses
- Study policy area development
- Track amendment patterns

### **Legal Professionals**
- Research legislative intent
- Track bill text changes
- Analyze procedural history
- Find related statutes

### **Government Affairs**
- Monitor client-relevant legislation
- Track bill progress and timing
- Identify key decision makers
- Prepare testimony and comments

## Performance Tips

### **Efficient Searches**
- Start with specific keywords
- Use Congress filters for recent data
- Limit initial results, expand if needed
- Cache frequently accessed bill details

### **Rate Limiting**
- Space out API calls for large research projects
- Use batch processing for multiple bills
- Implement retry logic for failed requests
- Monitor response times

### **Data Quality**
- Use Congress 103+ for reliable data
- Verify bill numbers with direct lookup
- Cross-reference with multiple data points
- Check update dates for freshness

## Troubleshooting

### **No Results Found**
- Check spelling of keywords
- Try broader search terms
- Verify Congress number is valid
- Remove filters and search again

### **Too Many Results**
- Add Congress number filter
- Specify bill type
- Use more specific keywords
- Reduce limit parameter

### **Outdated Information**
- Use recent Congress numbers
- Check bill update dates
- Verify bill is still active
- Look for newer related bills

## Advanced Techniques

### **Cross-Congress Comparison**
```
# Compare similar bills across Congresses
search_bills("infrastructure", congress=118)
search_bills("infrastructure", congress=119)
```

### **Comprehensive Bill Analysis**
```
# Get complete bill picture
get_bill_details(congress, bill_type, number)
get_bill_actions(congress, bill_type, number)
get_bill_summaries(congress, bill_type, number)
get_bill_related_bills(congress, bill_type, number)
```

### **Legislative Trend Analysis**
- Search same keywords across multiple Congresses
- Track policy area evolution
- Monitor sponsor patterns
- Analyze success rates by bill type
"""