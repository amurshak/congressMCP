# congress_info.py
from typing import Dict, Any, List, Optional, Union
import json
import logging
import datetime
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor

# Configure logging
logger = logging.getLogger(__name__)

# Defensive API wrapper for Congress Info requests
async def safe_congress_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Defensive wrapper for Congress Info API requests with:
    - Parameter sanitization
    - Timeout handling
    - Retry logic
    - Standardized error responses
    """
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint=endpoint,
        ctx=ctx,
        params=params or {},
        endpoint_type="congress"
    )

# Helper functions
def format_date(date_str: str) -> str:
    """
    Format a date string to a more readable format.
    """
    if not date_str or date_str == "Unknown" or date_str == "Not ended":
        return date_str
    
    try:
        # Parse ISO format date
        dt = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y")
    except ValueError:
        # If parsing fails, return the original string
        return date_str

def format_congress(congress: Dict[str, Any], detailed: bool = False) -> str:
    """
    Format a single congress into a readable format.
    
    Args:
        congress: Dictionary containing congress data
        detailed: Whether to include more detailed information
    """
    result = []
    
    # Congress number and dates
    number = congress.get("number", congress.get("name", "Unknown").split()[0])
    name = congress.get("name", f"{number}th Congress")
    result.append(f"# {name}")
    
    # Years
    start_year = congress.get("startYear", "Unknown")
    end_year = congress.get("endYear", "Unknown")
    result.append(f"Years: {start_year} - {end_year}")
    
    # Update date
    if "updateDate" in congress:
        formatted_date = format_date(congress['updateDate'])
        result.append(f"Last Updated: {formatted_date}")
    
    # Sessions
    if "sessions" in congress and congress["sessions"]:
        result.append("\n## Sessions")
        for session in congress["sessions"]:
            chamber = session.get("chamber", "Unknown")
            session_num = session.get("number", "Unknown")
            session_type = session.get("type", "R")
            session_type_full = "Regular" if session_type == "R" else "Special"
            
            result.append(f"### {chamber} - Session {session_num} ({session_type_full})")
            
            session_start = format_date(session.get("startDate", "Unknown"))
            session_end = format_date(session.get("endDate", "Not ended") if session.get("endDate") else "Not ended")
            result.append(f"Duration: {session_start} to {session_end}")
            
            # Add more session details if available and detailed mode is on
            if detailed and "committees" in session:
                result.append("\n#### Committees:")
                for committee in session.get("committees", []):
                    committee_name = committee.get("name", "Unknown Committee")
                    committee_type = committee.get("type", "")
                    result.append(f"- {committee_name} ({committee_type})")
    
    # URL
    if "url" in congress:
        result.append(f"\n[API Link]({congress['url']})")
    
    return "\n".join(result)

def format_congresses_list(congresses: List[Dict[str, Any]], format_type: str = "markdown") -> str:
    """
    Format a list of congresses into a readable format.
    
    Args:
        congresses: List of congress dictionaries
        format_type: Output format type ("markdown" or "table")
    """
    if not congresses:
        return "No congresses found."
    
    if format_type == "table":
        # Table format
        result = ["# Congresses", "", "| Congress | Years | Sessions |", "|---------|-------|---------|"]
        
        for congress in congresses:
            name = congress.get("name", "Unknown Congress")
            start_year = congress.get("startYear", "Unknown")
            end_year = congress.get("endYear", "Unknown")
            
            # Count sessions by chamber
            sessions_count = {}
            for session in congress.get("sessions", []):
                chamber = session.get("chamber", "Unknown")
                if chamber in sessions_count:
                    sessions_count[chamber] += 1
                else:
                    sessions_count[chamber] = 1
            
            sessions_str = ", ".join([f"{count} {chamber}" for chamber, count in sessions_count.items()])
            if not sessions_str:
                sessions_str = "None"
            
            result.append(f"| {name} | {start_year} - {end_year} | {sessions_str} |")
        
        return "\n".join(result)
    else:
        # Default markdown format
        result = ["# Congresses"]
        
        for congress in congresses:
            result.append("---\n")
            name = congress.get("name", "Unknown Congress")
            start_year = congress.get("startYear", "Unknown")
            end_year = congress.get("endYear", "Unknown")
            
            result.append(f"## {name}")
            result.append(f"Years: {start_year} - {end_year}")
            
            # Sessions summary
            if "sessions" in congress and congress["sessions"]:
                result.append("\n### Sessions:")
                for session in congress["sessions"]:
                    chamber = session.get("chamber", "Unknown")
                    session_num = session.get("number", "Unknown")
                    session_type = session.get("type", "R")
                    session_type_full = "Regular" if session_type == "R" else "Special"
                    
                    session_start = format_date(session.get("startDate", "Unknown"))
                    session_end = format_date(session.get("endDate", "Not ended") if session.get("endDate") else "Not ended")
                    
                    result.append(f"- {chamber} Session {session_num} ({session_type_full}): {session_start} to {session_end}")
        
        return "\n\n".join(result)

def handle_api_error(data: Dict[str, Any], error_message: str) -> str:
    """
    Handle API error responses consistently.
    
    Args:
        data: API response data
        error_message: Custom error message prefix
    """
    if "error" in data:
        error = CommonErrors.api_server_error(f"{error_message}: {data.get('error', 'Unknown API error')}")
        return format_error_response(error)
    error = CommonErrors.general_error(f"{error_message}: Unknown error")
    return format_error_response(error)

# Resources (Static/Reference Data Only)
@mcp.resource("congress://all")
async def get_all_congresses(ctx: Context) -> str:
    """
    Get a list of all congresses.
    
    Returns a list of all congresses with basic information about each,
    including session dates and chamber information.
    """
    logger.info("Accessing all congresses resource")
    try:
        data = await safe_congress_request("/congress", ctx, {"limit": 20})
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = handle_api_error(data, "Error retrieving congresses")
            logger.error(error_msg)
            return error_msg
        
        congresses = data.get("congresses", [])
        logger.info(f"Found {len(congresses)} congresses")
        
        if not congresses:
            error = CommonErrors.data_not_found("congresses", "list")
            return format_error_response(error)
        
        # Deduplicate results
        deduplicated_congresses = ResponseProcessor.deduplicate_results(
            congresses, 
            key_fields=["number", "name"]
        )
        
        # Use default format type
        return format_congresses_list(deduplicated_congresses, "markdown")
    except Exception as e:
        error = CommonErrors.general_error(f"Error retrieving congresses: {str(e)}")
        logger.error(f"Exception in get_all_congresses: {str(e)}")
        return format_error_response(error)

# Tools (Interactive/Parameterized Functions)
@mcp.tool()
async def get_congress_info(
    ctx: Context,
    congress: Optional[int] = None,
    current: bool = False,
    limit: int = 10,
    detailed: bool = False,
    format_type: str = "markdown"
) -> str:
    """
    Get information about a Congress.
    
    Args:
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        current: If True, get information about the current Congress
        limit: Maximum number of congresses to return if no specific congress is requested
        detailed: If True, include more detailed information about the Congress
        format_type: Output format type ("markdown" or "table") for list of congresses
    """
    
    try:
        # Parameter validation
        if congress is not None:
            congress_result = ParameterValidator.validate_congress_number(congress)
            if not congress_result.is_valid:
                error = CommonErrors.invalid_parameter("congress", congress, congress_result.error_message)
                return format_error_response(error)
        
        if limit is not None:
            limit_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
            if not limit_result.is_valid:
                error = CommonErrors.invalid_parameter("limit", limit, limit_result.error_message)
                return format_error_response(error)
        
        if format_type not in ["markdown", "table"]:
            error = CommonErrors.invalid_parameter("format_type", format_type, "Must be 'markdown' or 'table'")
            return format_error_response(error)
        
        logger.info(f"Getting congress info - congress: {congress}, current: {current}, limit: {limit}, detailed: {detailed}, format: {format_type}")
        
        if current:
            # Get current Congress
            data = await safe_congress_request("/congress/current", ctx)
            if "error" in data:
                return handle_api_error(data, "Error retrieving current Congress information")
            
            congress_data = data.get("congress", {})
            if not congress_data:
                error = CommonErrors.data_not_found("current Congress", "current")
                return format_error_response(error)
            
            return format_congress(congress_data, detailed)
        elif congress is not None:
            # Get specific Congress
            data = await safe_congress_request(f"/congress/{congress}", ctx)
            if "error" in data:
                return handle_api_error(data, f"Error retrieving Congress {congress} information")
            
            congress_data = data.get("congress", {})
            if not congress_data:
                error = CommonErrors.data_not_found("Congress", str(congress))
                return format_error_response(error)
            
            return format_congress(congress_data, detailed)
        else:
            # Get list of congresses
            data = await safe_congress_request("/congress", ctx, {"limit": limit})
            if "error" in data:
                return handle_api_error(data, "Error retrieving congresses")
            
            congresses = data.get("congresses", [])
            if not congresses:
                error = CommonErrors.data_not_found("congresses", "list")
                return format_error_response(error)
            
            # Deduplicate results
            deduplicated_congresses = ResponseProcessor.deduplicate_results(
                congresses, 
                key_fields=["number", "name"]
            )
            
            return format_congresses_list(deduplicated_congresses, format_type)
    except Exception as e:
        error = CommonErrors.general_error(f"Error retrieving Congress information: {str(e)}")
        return format_error_response(error)

@mcp.tool()
async def search_congresses(
    ctx: Context,
    keywords: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    limit: int = 10,
    format_type: str = "markdown"
) -> str:
    """
    Search for congresses based on keywords and date ranges.
    
    Args:
        keywords: Keywords to search for in congress information
        start_year: Optional start year to filter congresses
        end_year: Optional end year to filter congresses
        limit: Maximum number of results to return (default: 10)
        format_type: Output format type ("markdown" or "table")
    """
    
    try:
        # Parameter validation
        if not keywords or not keywords.strip():
            error = CommonErrors.invalid_parameter("keywords", keywords, "Keywords cannot be empty")
            return format_error_response(error)
        
        if start_year is not None:
            if start_year < 1789 or start_year > 2100:
                error = CommonErrors.invalid_parameter("start_year", start_year, "Start year must be between 1789 and 2100")
                return format_error_response(error)
        
        if end_year is not None:
            if end_year < 1789 or end_year > 2100:
                error = CommonErrors.invalid_parameter("end_year", end_year, "End year must be between 1789 and 2100")
                return format_error_response(error)
        
        if start_year is not None and end_year is not None and start_year > end_year:
            error = CommonErrors.invalid_parameter("date_range", f"{start_year}-{end_year}", "Start year cannot be greater than end year")
            return format_error_response(error)
        
        if limit is not None:
            limit_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
            if not limit_result.is_valid:
                error = CommonErrors.invalid_parameter("limit", limit, limit_result.error_message)
                return format_error_response(error)
        
        if format_type not in ["markdown", "table"]:
            error = CommonErrors.invalid_parameter("format_type", format_type, "Must be 'markdown' or 'table'")
            return format_error_response(error)
        
        logger.info(f"Searching congresses - keywords: '{keywords}', start_year: {start_year}, end_year: {end_year}, limit: {limit}, format: {format_type}")
        
        # Get all congresses first
        data = await safe_congress_request("/congress", ctx, {"limit": 50})
        
        if "error" in data:
            return handle_api_error(data, "Error retrieving congresses for search")
        
        all_congresses = data.get("congresses", [])
        if not all_congresses:
            error = CommonErrors.data_not_found("congresses", "search")
            return format_error_response(error)
        
        # Filter by keywords and date range
        filtered_congresses = []
        keywords_lower = keywords.lower()
        
        for congress in all_congresses:
            # Convert congress data to string for keyword search
            congress_str = json.dumps(congress).lower()
            
            # Check if keywords match
            if keywords_lower in congress_str:
                # Check date range if provided
                congress_start = int(congress.get("startYear", 0))
                congress_end = int(congress.get("endYear", 9999))
                
                start_year_match = start_year is None or congress_start >= start_year
                end_year_match = end_year is None or congress_end <= end_year
                
                if start_year_match and end_year_match:
                    filtered_congresses.append(congress)
        
        # Deduplicate results
        deduplicated_congresses = ResponseProcessor.deduplicate_results(
            filtered_congresses, 
            key_fields=["number", "name"]
        )
        
        # Limit results
        limited_congresses = deduplicated_congresses[:limit]
        
        if not limited_congresses:
            error = CommonErrors.data_not_found("congresses", f"search term '{keywords}'")
            return format_error_response(error)
        
        # Format results
        result_header = f"# Search Results for '{keywords}'"
        if start_year or end_year:
            year_range = ""
            if start_year:
                year_range += f"from {start_year} "
            if end_year:
                year_range += f"to {end_year}"
            result_header += f" ({year_range.strip()})"
        
        if format_type == "table":
            result = [result_header, "", "| Congress | Years | Sessions |", "|---------|-------|---------|"]
            
            for congress in limited_congresses:
                name = congress.get("name", "Unknown Congress")
                start_year = congress.get("startYear", "Unknown")
                end_year = congress.get("endYear", "Unknown")
                
                # Count sessions by chamber
                sessions_count = {}
                for session in congress.get("sessions", []):
                    chamber = session.get("chamber", "Unknown")
                    if chamber in sessions_count:
                        sessions_count[chamber] += 1
                    else:
                        sessions_count[chamber] = 1
                
                sessions_str = ", ".join([f"{count} {chamber}" for chamber, count in sessions_count.items()])
                if not sessions_str:
                    sessions_str = "None"
                
                result.append(f"| {name} | {start_year} - {end_year} | {sessions_str} |")
            
            return "\n".join(result)
        else:
            # Use the existing format_congresses_list function
            formatted_list = format_congresses_list(limited_congresses)
            # Replace the default header with our search header
            return result_header + formatted_list[formatted_list.find("\n"):]
    except Exception as e:
        error = CommonErrors.general_error(f"Error searching congresses: {str(e)}")
        return format_error_response(error)
