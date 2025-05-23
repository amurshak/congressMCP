# amendments.py
from typing import Dict, Any, Optional, List
import json

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

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
        for action in actions[:5]:  # Show only the 5 most recent actions
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
async def get_latest_amendments() -> str:
    """
    Get the most recent amendments introduced in Congress.
    
    Returns a list of the 10 most recently updated amendments across all
    Congresses, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/amendment", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return json.dumps({"error": data["error"]})
    
    amendments = data.get("amendments", [])
    if not amendments:
        return "No amendments found."
    
    result = ["# Latest Amendments in Congress\n"]
    for amendment in amendments:
        result.append("---\n")
        result.append(format_amendment_summary(amendment))
    
    return "\n\n".join(result)

@mcp.resource("congress://amendments/{congress}")
async def get_amendments_by_congress(congress: str) -> str:
    """
    Get amendments from a specific Congress.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated amendments from the
    specified Congress, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/amendment/{congress}", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return json.dumps({"error": data["error"]})
    
    amendments = data.get("amendments", [])
    if not amendments:
        return f"No amendments found for the {congress}th Congress."
    
    result = [f"# Amendments in the {congress}th Congress\n"]
    for amendment in amendments:
        result.append("---\n")
        result.append(format_amendment_summary(amendment))
    
    return "\n\n".join(result)

@mcp.resource("congress://amendments/{congress}/{amendment_type}")
async def get_amendments_by_type(congress: str, amendment_type: str) -> str:
    """
    Get amendments from a specific Congress and amendment type.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        amendment_type: The type of amendment (e.g., "samdt", "hamdt")
        
    Returns a list of the 10 most recently updated amendments of the specified
    type from the specified Congress, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/amendment/{congress}/{amendment_type}", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return json.dumps({"error": data["error"]})
    
    amendments = data.get("amendments", [])
    if not amendments:
        return f"No {amendment_type.upper()} amendments found for the {congress}th Congress."
    
    result = [f"# {amendment_type.upper()} Amendments in the {congress}th Congress\n"]
    for amendment in amendments:
        result.append("---\n")
        result.append(format_amendment_summary(amendment))
    
    return "\n\n".join(result)

# Tools
@mcp.tool()
async def get_bill_amendments(
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
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/amendments"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving amendments: {data['error']}"
    
    amendments = data.get("amendments", [])
    if not amendments:
        return f"No amendments found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"Found {len(amendments)} amendments for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
    for amendment in amendments:
        result.append("\n" + format_amendment_summary(amendment))
    
    return "\n".join(result)

@mcp.tool()
async def search_amendments(
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
    ctx = mcp.get_context()
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
    
    data = await make_api_request(endpoint, ctx, params)
    
    if "error" in data:
        return f"Error searching amendments: {data['error']}"
    
    amendments = data.get("amendments", [])
    if not amendments:
        return f"No amendments found matching '{keywords}'."
    
    result = [f"# Amendments Matching '{keywords}'\n"]
    for amendment in amendments:
        result.append("---\n")
        result.append(format_amendment_summary(amendment))
    
    return "\n\n".join(result)

@mcp.tool()
async def get_amendment_details(
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
    ctx = mcp.get_context()
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving amendment details: {data['error']}"
    
    amendment = data.get("amendment", {})
    if not amendment:
        return f"No details found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."
    
    return format_amendment_details(amendment)

@mcp.tool()
async def get_amendment_actions(
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
    ctx = mcp.get_context()
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/actions"
    data = await make_api_request(endpoint, ctx, {"limit": limit})
    
    if "error" in data:
        return f"Error retrieving amendment actions: {data['error']}"
    
    actions = data.get("actions", [])
    if not actions:
        return f"No actions found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."
    
    result = [f"# Actions for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]
    for action in actions:
        result.append(format_amendment_action(action))
    
    return "\n".join(result)

@mcp.tool()
async def get_amendment_sponsors(
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> str:
    """
    Get sponsors for a specific amendment.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
    """
    ctx = mcp.get_context()
    endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/sponsors"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving amendment sponsors: {data['error']}"
    
    sponsors = data.get("sponsors", [])
    if not sponsors:
        return f"No sponsors found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."
    
    result = [f"# Sponsors for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]
    result.append(f"Total Sponsors: {len(sponsors)}")
    
    for sponsor in sponsors:
        name = sponsor.get("name", "Unknown")
        party = sponsor.get("party", "")
        state = sponsor.get("state", "")
        bioguide_id = sponsor.get("bioguideId", "")
        sponsor_type = sponsor.get("sponsorType", "Sponsor")
        result.append(f"- {name} ({party}-{state}), {sponsor_type}, Bioguide ID: {bioguide_id}")
    
    return "\n".join(result)
