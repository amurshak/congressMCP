# committees.py
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Formatting helpers
def format_committee_summary(committee: Dict[str, Any]) -> str:
    """Format a committee into a readable summary."""
    result = []
    result.append(f"Committee: {committee.get('name', 'Unknown')}")
    result.append(f"Chamber: {committee.get('chamber', 'Unknown')}")
    result.append(f"Committee Code: {committee.get('systemCode', 'Unknown')}")
    result.append(f"URL: {committee.get('url', 'No URL available')}")
    return "\n".join(result)

# Resources
@mcp.resource("congress://committees")
async def get_committees() -> str:
    """
    Get a list of congressional committees.
    
    Returns a comprehensive list of committees in the House and Senate,
    including their names, chambers, and system codes.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/committee", ctx)
    
    if "error" in data:
        return f"Error retrieving committees: {data['error']}"
    
    committees = data.get("committees", [])
    if not committees:
        return "No committees found."
    
    result = ["Congressional Committees:"]
    for committee in committees:
        result.append("\n" + format_committee_summary(committee))
    
    return "\n".join(result)

@mcp.resource("congress://committees/{chamber}")
async def get_committees_by_chamber(chamber: str) -> str:
    """
    Get committees for a specific chamber.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        
    Returns a list of committees in the specified chamber.
    """
    ctx = mcp.get_context()
    
    # Validate chamber parameter
    if chamber.lower() not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    data = await make_api_request("/committee", ctx, {"chamber": chamber.lower()})
    
    if "error" in data:
        return f"Error retrieving committees: {data['error']}"
    
    committees = data.get("committees", [])
    if not committees:
        return f"No committees found for the {chamber.capitalize()}."
    
    result = [f"{chamber.capitalize()} Committees:"]
    for committee in committees:
        result.append("\n" + format_committee_summary(committee))
    
    return "\n".join(result)

@mcp.resource("congress://committees/{chamber}/{committee_code}")
async def get_committee_details(chamber: str, committee_code: str) -> str:
    """
    Get detailed information about a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hsag", "ssap")
        
    Returns detailed information about the specified committee.
    """
    ctx = mcp.get_context()
    
    # Validate chamber parameter
    if chamber.lower() not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}", ctx)
    
    if "error" in data:
        return f"Error retrieving committee details: {data['error']}"
    
    committee = data.get("committee", {})
    if not committee:
        return f"No committee found with code {committee_code} in the {chamber.capitalize()}."
    
    result = []
    
    # Committee name and code
    name = committee.get("name", "Unknown")
    result.append(f"## {name}")
    result.append(f"Chamber: {chamber.capitalize()}")
    result.append(f"Committee Code: {committee_code}")
    
    # Subcommittees
    if "subcommittees" in committee and committee["subcommittees"]:
        result.append("\n### Subcommittees:")
        for subcommittee in committee["subcommittees"]:
            sub_name = subcommittee.get("name", "Unknown")
            sub_code = subcommittee.get("systemCode", "Unknown")
            result.append(f"- {sub_name} ({sub_code})")
    
    # URL
    if "url" in committee:
        result.append(f"\nURL: {committee['url']}")
    
    return "\n".join(result)

# Tools
@mcp.tool()
async def get_committee_bills(
    chamber: str,
    committee_code: str,
    limit: int = 10
) -> str:
    """
    Get bills referred to a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hsag", "ssap")
        limit: Maximum number of bills to return (default: 10)
    """
    ctx = mcp.get_context()
    
    # Validate chamber parameter
    if chamber.lower() not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    # First get committee details to verify it exists and get the name
    committee_data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}", ctx)
    
    if "error" in committee_data:
        return f"Error retrieving committee: {committee_data['error']}"
    
    committee = committee_data.get("committee", {})
    if not committee:
        return f"No committee found with code {committee_code} in the {chamber.capitalize()}."
    
    committee_name = committee.get("name", "Unknown Committee")
    
    # Now get bills for this committee
    bills_data = await make_api_request(f"/bill", ctx, {
        "committee": committee_code,
        "limit": limit,
        "sort": "updateDate+desc"
    })
    
    if "error" in bills_data:
        return f"Error retrieving committee bills: {bills_data['error']}"
    
    bills = bills_data.get("bills", [])
    if not bills:
        return f"No bills found for the {committee_name} committee."
    
    result = [f"Recent bills referred to the {committee_name} committee:"]
    
    for bill in bills:
        bill_num = bill.get("number", "Unknown")
        bill_type = bill.get("type", "Unknown").upper()
        title = bill.get("title", "No title")
        congress = bill.get("congress", "Unknown")
        
        result.append(f"\n### {bill_type} {bill_num} ({congress}th Congress)")
        result.append(f"Title: {title}")
        
        if "latestAction" in bill:
            action = bill["latestAction"]
            action_text = action.get("text", "Unknown action")
            action_date = action.get("actionDate", "Unknown date")
            result.append(f"Latest Action: {action_text} ({action_date})")
        
        if "url" in bill:
            result.append(f"URL: {bill['url']}")
    
    return "\n".join(result)
