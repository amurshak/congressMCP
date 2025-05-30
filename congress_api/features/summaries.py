# summaries.py
from typing import Dict, Any, Optional, List
import json
import logging
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Configure logging
logger = logging.getLogger(__name__)

# Formatting helpers
def format_summary(summary: Dict[str, Any]) -> str:
    """Format a summary into a readable format."""
    result = []
    
    # Basic information about the bill
    bill = summary.get("bill", {})
    bill_type = bill.get("type", "Unknown")
    bill_number = bill.get("number", "Unknown")
    congress = bill.get("congress", "Unknown")
    title = bill.get("title", "Untitled")
    
    result.append(f"# {title}")
    result.append(f"Bill: {bill_type.upper()} {bill_number} ({congress}th Congress)")
    
    # Action information
    action_date = summary.get("actionDate", "Unknown date")
    action_desc = summary.get("actionDesc", "Unknown action")
    result.append(f"Action: {action_desc} on {action_date}")
    
    # Chamber information
    current_chamber = summary.get("currentChamber", "Unknown")
    result.append(f"Current Chamber: {current_chamber}")
    
    # Summary text
    if "text" in summary:
        result.append("\n## Summary")
        result.append(summary["text"])
    
    # Update information
    update_date = summary.get("updateDate", "Unknown")
    result.append(f"\nLast Updated: {update_date}")
    
    return "\n".join(result)

def format_summaries_list(summaries: List[Dict[str, Any]], title: str) -> str:
    """Format a list of summaries into a readable format."""
    if not summaries:
        return "No summaries found."
    
    result = [f"# {title}\n"]
    
    for summary in summaries:
        result.append("---\n")
        
        # Basic information about the bill
        bill = summary.get("bill", {})
        bill_type = bill.get("type", "Unknown")
        bill_number = bill.get("number", "Unknown")
        congress = bill.get("congress", "Unknown")
        title = bill.get("title", "Untitled")
        
        result.append(f"## {title}")
        result.append(f"Bill: {bill_type.upper()} {bill_number} ({congress}th Congress)")
        
        # Action information
        action_date = summary.get("actionDate", "Unknown date")
        action_desc = summary.get("actionDesc", "Unknown action")
        result.append(f"Action: {action_desc} on {action_date}")
        
        # Update information
        update_date = summary.get("updateDate", "Unknown")
        result.append(f"Last Updated: {update_date}")
        
        # Add URL to view full summary
        bill_url = bill.get("url", "")
        if bill_url:
            result.append(f"\n[View Bill Details]({bill_url})")
    
    return "\n\n".join(result)

# Resources
@mcp.resource("congress://summaries/latest")
async def get_latest_summaries(ctx: Context) -> str:
    """
    Get the most recent bill summaries.
    
    Returns a list of the 10 most recently updated summaries across all
    Congresses, sorted by update date in descending order.
    """
    logger.info("Accessing latest summaries resource")
    try:
        data = await make_api_request("/summaries", ctx, {"limit": 10, "sort": "updateDate+desc"})
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")  
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        summaries = data.get("summaries", [])
        logger.info(f"Found {len(summaries)} summaries")
        
        if not summaries:
            return "No summaries found."
        
        return format_summaries_list(summaries, "Latest Bill Summaries")
    except Exception as e:
        logger.error(f"Exception in get_latest_summaries: {str(e)}")
        return f"Error retrieving latest summaries: {str(e)}"

@mcp.resource("congress://summaries/{congress}")
async def get_summaries_by_congress(ctx: Context, congress: str) -> str:
    """
    Get summaries from a specific Congress.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated summaries from the
    specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing summaries for Congress {congress}")
    try:
        data = await make_api_request(f"/summaries/{congress}", ctx, {"limit": 10, "sort": "updateDate+desc"})
        logger.info(f"API response received for Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            logger.error(f"Error in API response for Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        summaries = data.get("summaries", [])
        logger.info(f"Found {len(summaries)} summaries for Congress {congress}")
        
        if not summaries:
            return f"No summaries found for the {congress}th Congress."
        
        return format_summaries_list(summaries, f"Bill Summaries from the {congress}th Congress")
    except Exception as e:
        logger.error(f"Exception in get_summaries_by_congress for Congress {congress}: {str(e)}")
        return f"Error retrieving summaries for the {congress}th Congress: {str(e)}"

@mcp.resource("congress://summaries/{congress}/{bill_type}")
async def get_summaries_by_type(ctx: Context, congress: str, bill_type: str) -> str:
    """
    Get summaries from a specific Congress and bill type.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        bill_type: The type of bill (e.g., "hr", "s")
        
    Returns a list of the 10 most recently updated summaries of the specified
    bill type from the specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing {bill_type} summaries for Congress {congress}")
    try:
        data = await make_api_request(f"/summaries/{congress}/{bill_type}", ctx, {"limit": 10, "sort": "updateDate+desc"})
        logger.info(f"API response received for {bill_type} summaries in Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        
        if "error" in data:
            logger.error(f"Error in API response for {bill_type} summaries in Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})
        
        summaries = data.get("summaries", [])
        logger.info(f"Found {len(summaries)} {bill_type} summaries for Congress {congress}")
        
        if not summaries:
            return f"No {bill_type.upper()} summaries found for the {congress}th Congress."
        
        return format_summaries_list(summaries, f"{bill_type.upper()} Bill Summaries from the {congress}th Congress")
    except Exception as e:
        logger.error(f"Exception in get_summaries_by_type for {bill_type} summaries in Congress {congress}: {str(e)}")
        return f"Error retrieving {bill_type.upper()} summaries for the {congress}th Congress: {str(e)}"

# Tools
@mcp.tool()
async def search_summaries(
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
    Search for bill summaries based on keywords.
    
    Args:
        keywords: Keywords to search for in bill summaries
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    logger.info(f"Searching for summaries with keywords: {keywords}")
    
    # Note: The Congress.gov Summaries API doesn't support keyword searching via query parameters
    # So we'll retrieve summaries and filter them client-side
    params = {
        # Increase the limit to get more results for filtering
        # We'll trim it back down to the requested limit after filtering
        "limit": min(100, limit * 5),  # Get more results but cap at 100
        "sort": sort
    }
    
    # Add optional date filters if provided
    if from_date:
        params["fromDateTime"] = from_date
    if to_date:
        params["toDateTime"] = to_date
    
    endpoint = "/summaries"
    if congress is not None:
        endpoint = f"/summaries/{congress}"
        if bill_type is not None:
            endpoint = f"/summaries/{congress}/{bill_type}"
    
    data = await make_api_request(endpoint, ctx, params)
    
    if "error" in data:
        return f"Error searching summaries: {data['error']}"
    
    summaries = data.get("summaries", [])
    if not summaries:
        return f"No summaries found for the specified criteria."
    
    # Client-side filtering based on keywords
    # Convert keywords to lowercase for case-insensitive matching
    keywords_lower = keywords.lower()
    filtered_summaries = []
    
    for summary in summaries:
        # Check if keywords appear in the title, text, or action description
        bill = summary.get("bill", {})
        title = bill.get("title", "").lower()
        text = summary.get("text", "").lower()
        action_desc = summary.get("actionDesc", "").lower()
        
        # If keywords appear in any of these fields, include the summary
        if (keywords_lower in title or 
            keywords_lower in text or 
            keywords_lower in action_desc):
            filtered_summaries.append(summary)
    
    # Limit the results to the requested number
    filtered_summaries = filtered_summaries[:limit]
    
    if not filtered_summaries:
        return f"No summaries found matching '{keywords}'."
    
    logger.info(f"Found {len(filtered_summaries)} summaries matching '{keywords}'")
    return format_summaries_list(filtered_summaries, f"Bill Summaries Matching '{keywords}'")


@mcp.tool()
async def get_bill_summaries(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get summaries for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    
    # Use the existing bill summaries endpoint
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/summaries"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill summaries: {data['error']}"
    
    # Handle different data structures for summaries
    summaries_data = data.get("summaries", {})
    
    # Extract summary items based on the data structure
    if isinstance(summaries_data, list):
        summaries = summaries_data
    elif isinstance(summaries_data, dict) and "item" in summaries_data:
        items = summaries_data["item"]
        if isinstance(items, list):
            summaries = items
        else:
            # If there's only one item, wrap it in a list
            summaries = [items]
    else:
        # If we can't determine the structure, just use an empty list
        logger.warning(f"Unexpected summaries structure: {type(summaries_data)}")
        summaries = []
    
    if not summaries:
        return f"No summaries found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Summaries for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    for summary in summaries:
        result.append("---\n")
        
        # Get version code and date
        version_code = summary.get("versionCode", "Unknown")
        version_date = summary.get("updateDate", "Unknown date")
        
        result.append(f"## Summary Version: {version_code}")
        result.append(f"Date: {version_date}")
        
        # Get summary text
        if "text" in summary:
            result.append("\n### Content")
            result.append(summary["text"])
    
    return "\n\n".join(result)
