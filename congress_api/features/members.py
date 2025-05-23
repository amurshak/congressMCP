# members.py
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Formatting helpers
def format_member_summary(member: Dict[str, Any]) -> str:
    """Format a member into a readable summary."""
    # Handle name field - can be string or nested object
    name_str = "Unknown"
    if "name" in member:
        if isinstance(member["name"], str):
            name_str = member["name"]
        elif isinstance(member["name"], dict):
            first = member["name"].get("firstName", "")
            middle = member["name"].get("middleName", "")
            last = member["name"].get("lastName", "")
            name_str = f"{first} {middle} {last}".strip()
            # Clean up extra spaces
            name_str = " ".join(name_str.split())
    
    result = []
    result.append(f"## {name_str}")
    result.append(f"Bioguide ID: {member.get('bioguideId', 'Unknown')}")
    
    # Handle party information - try multiple possible fields
    party = "Unknown"
    if "partyName" in member:
        party = member["partyName"]
    elif "party" in member:
        party = member["party"]
    result.append(f"Party: {party}")
    
    result.append(f"State: {member.get('state', 'Unknown')}")
    
    # District (only for House members)
    if "district" in member and member["district"]:
        result.append(f"District: {member['district']}")
    
    # Handle terms information
    if "terms" in member:
        terms = member["terms"]
        # Handle case where terms might be wrapped in an object with 'item' key
        if isinstance(terms, dict) and "item" in terms:
            terms = terms["item"]
        
        if terms and isinstance(terms, list) and len(terms) > 0:
            latest_term = terms[0]
            if isinstance(latest_term, dict):
                chamber = latest_term.get('chamber', 'Unknown')
                result.append(f"Chamber: {chamber}")
                
                # Add term years if available
                start_year = latest_term.get('startYear', 'Unknown')
                end_year = latest_term.get('endYear', 'Present')
                if start_year != 'Unknown':
                    result.append(f"Term: {start_year} - {end_year}")
    
    # URL
    url = member.get("url", "No URL available")
    result.append(f"URL: {url}")
    
    return "\n".join(result)

# Resources
@mcp.resource("congress://members/current")
async def get_current_members() -> str:
    """
    Get a list of current members of Congress.
    
    Returns a sample of 20 current members from both chambers of Congress,
    including their biographical information and contact details.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/member", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return "No members found."
    
    result = ["Current members of Congress:"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.resource("congress://members/{bioguide_id}")
async def get_member_details(bioguide_id: str) -> str:
    """
    Get detailed information about a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "A000055")
        
    Returns comprehensive information about the specified member,
    including biographical data, terms of service, and committee assignments.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/member/{bioguide_id}", ctx)
    
    if "error" in data:
        return f"Error retrieving member details: {data['error']}"
    
    member = data.get("member", {})
    if not member:
        return f"No member found with Bioguide ID: {bioguide_id}"
    
    return format_member_summary(member)

# Tools
@mcp.tool()
async def search_members(
    name: Optional[str] = None,
    state: Optional[str] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    congress: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search for members of Congress based on various criteria.
    
    Args:
        name: Optional name to search for
        state: Optional state abbreviation (e.g., 'CA', 'TX')
        party: Optional party affiliation ('D', 'R', 'I')
        chamber: Optional chamber ('house' or 'senate')
        congress: Optional Congress number (e.g., 117)
        limit: Maximum number of results to return (default: 10)
    """
    ctx = mcp.get_context()
    
    # Build parameters
    params = {"limit": limit}
    
    if name:
        params["name"] = name
    if state:
        params["state"] = state
    if party:
        params["party"] = party
    if chamber:
        params["chamber"] = chamber
    if congress:
        params["congress"] = congress
    
    data = await make_api_request("/member", ctx, params)
    
    if "error" in data:
        return f"Error searching members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        # Build search criteria string for error message
        criteria = []
        if name:
            criteria.append(f"name: {name}")
        if state:
            criteria.append(f"state: {state}")
        if party:
            criteria.append(f"party: {party}")
        if chamber:
            criteria.append(f"chamber: {chamber}")
        if congress:
            criteria.append(f"congress: {congress}")
        
        criteria_str = ", ".join(criteria) if criteria else "the provided criteria"
        return f"No members found matching {criteria_str}."
    
    result = [f"Found {len(members)} members of Congress:"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.tool()
async def get_member_info(bioguide_id: str) -> str:
    """
    Get detailed information about a member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/member/{bioguide_id}", ctx)
    
    if "error" in data:
        return f"Error retrieving member information: {data['error']}"
    
    member = data.get("member", {})
    if not member:
        return f"No member found with Bioguide ID: {bioguide_id}"
    
    # Start with basic information
    result = [format_member_summary(member)]
    
    # Add committee assignments if available
    if "committeeAssignments" in member and member["committeeAssignments"]:
        committees = member["committeeAssignments"]
        
        # Handle case where committees might be wrapped in an object with 'item' key
        if isinstance(committees, dict) and "item" in committees:
            committees = committees["item"]
        
        if committees and isinstance(committees, list):
            result.append("\n## Committee Assignments")
            for committee in committees:
                name = committee.get("name", "Unknown committee")
                code = committee.get("systemCode", "")
                chamber = committee.get("chamber", "")
                result.append(f"- {name} ({chamber}, {code})")
    
    # Add sponsored legislation if available
    if "sponsoredLegislation" in member and "count" in member["sponsoredLegislation"]:
        count = member["sponsoredLegislation"]["count"]
        result.append(f"\n## Sponsored Legislation\nTotal bills sponsored: {count}")
        result.append("Use the search_bills tool with this member's name to find specific legislation.")
    
    # Add biographical information if available
    result.append("\n## Biographical Information")
    if "birthDate" in member:
        result.append(f"Birth Date: {member['birthDate']}")
    if "officialWebsiteUrl" in member:
        result.append(f"Official Website: {member['officialWebsiteUrl']}")
    if "twitterAccount" in member:
        result.append(f"Twitter: @{member['twitterAccount']}")
    if "youtubeAccount" in member:
        result.append(f"YouTube: {member['youtubeAccount']}")
    if "facebookAccount" in member:
        result.append(f"Facebook: {member['facebookAccount']}")
    
    return "\n".join(result)
