# congress_info.py
from typing import Dict, Any, List, Optional, Union
import json
import logging
from datetime import datetime
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Configure logging
logger = logging.getLogger(__name__)

# Helper functions
def format_date(date_str: str) -> str:
    """
    Format a date string to a more readable format.
    """
    if not date_str or date_str == "Unknown" or date_str == "Not ended":
        return date_str
    
    try:
        # Parse ISO format date
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
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
        error_code = data.get("error", {}).get("code", "unknown")
        error_msg = data.get("error", {}).get("message", str(data["error"]))
        return f"{error_message}: [{error_code}] {error_msg}"
    return f"{error_message}: Unknown error"

# Resources
@mcp.resource("congress://all")
async def get_all_congresses(ctx: Context) -> str:
    """
    Get a list of all congresses.
    
    Returns a list of all congresses with basic information about each,
    including session dates and chamber information.
    """
    logger.info("Accessing all congresses resource")
    try:
        data = await make_api_request("/congress", ctx, {"limit": 20})
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = handle_api_error(data, "Error retrieving congresses")
            logger.error(error_msg)
            return error_msg
        
        congresses = data.get("congresses", [])
        logger.info(f"Found {len(congresses)} congresses")
        
        if not congresses:
            return "No congresses found."
        
        # Use default format type
        return format_congresses_list(congresses, "markdown")
    except Exception as e:
        error_msg = f"Error retrieving congresses: {str(e)}"
        logger.error(f"Exception in get_all_congresses: {str(e)}")
        return error_msg

@mcp.resource("congress://congress/{congress}")
async def get_congress_by_number(ctx: Context, congress: str) -> str:
    """
    Get information about a specific Congress.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        
    Returns detailed information about the specified Congress,
    including session dates, chamber information, and other details.
    """
    logger.info(f"Accessing information for Congress {congress}")
    try:
        # Use default detailed parameter
        detailed = False
        
        data = await make_api_request(f"/congress/{congress}", ctx)
        logger.info(f"API response received for Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = handle_api_error(data, f"Error retrieving information for the {congress}th Congress")
            logger.error(error_msg)
            return error_msg
        
        congress_data = data.get("congress", {})
        logger.info(f"Found data for Congress {congress}")
        
        if not congress_data:
            return f"No information found for the {congress}th Congress."
        
        return format_congress(congress_data, detailed)
    except Exception as e:
        error_msg = f"Error retrieving information for the {congress}th Congress: {str(e)}"
        logger.error(f"Exception in get_congress_by_number for Congress {congress}: {str(e)}")
        return error_msg

@mcp.resource("congress://info/current")
async def get_current_congress(ctx: Context) -> str:
    """
    Get information about the current Congress.
    
    Returns detailed information about the currently active Congress,
    including session dates, chamber information, and leadership.
    """
    logger.info("Accessing current Congress information")
    try:
        # Use default detailed parameter
        detailed = False
        
        data = await make_api_request("/congress/current", ctx)
        logger.info(f"API response received for current Congress: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            error_msg = handle_api_error(data, "Error retrieving current Congress information")
            logger.error(error_msg)
            return error_msg
        
        congress = data.get("congress", {})
        logger.info(f"Found data for current Congress")
        
        if not congress:
            return "No information found about the current Congress."
        
        return format_congress(congress, detailed)
    except Exception as e:
        error_msg = f"Error retrieving current Congress information: {str(e)}"
        logger.error(f"Exception in get_current_congress: {str(e)}")
        return error_msg

# Tools
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
        if current:
            # Get current Congress
            data = await make_api_request("/congress/current", ctx)
            if "error" in data:
                return handle_api_error(data, "Error retrieving current Congress information")
            
            congress_data = data.get("congress", {})
            if not congress_data:
                return "No information found about the current Congress."
            
            return format_congress(congress_data, detailed)
        elif congress is not None:
            # Get specific Congress
            data = await make_api_request(f"/congress/{congress}", ctx)
            if "error" in data:
                return handle_api_error(data, f"Error retrieving Congress {congress} information")
            
            congress_data = data.get("congress", {})
            if not congress_data:
                return f"No information found for the {congress}th Congress."
            
            return format_congress(congress_data, detailed)
        else:
            # Get list of congresses
            data = await make_api_request("/congress", ctx, {"limit": limit})
            if "error" in data:
                return handle_api_error(data, "Error retrieving congresses")
            
            congresses = data.get("congresses", [])
            if not congresses:
                return "No congresses found."
            
            return format_congresses_list(congresses, format_type)
    except Exception as e:
        return f"Error retrieving Congress information: {str(e)}"

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
        # Get all congresses first
        data = await make_api_request("/congress", ctx, {"limit": 50})
        
        if "error" in data:
            return handle_api_error(data, "Error retrieving congresses for search")
        
        all_congresses = data.get("congresses", [])
        if not all_congresses:
            return "No congresses found to search."
        
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
        
        # Limit results
        filtered_congresses = filtered_congresses[:limit]
        
        if not filtered_congresses:
            return f"No congresses found matching '{keywords}'."
        
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
            
            for congress in filtered_congresses:
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
            formatted_list = format_congresses_list(filtered_congresses)
            # Replace the default header with our search header
            return result_header + formatted_list[formatted_list.find("\n"):]
    except Exception as e:
        return f"Error searching congresses: {str(e)}"
