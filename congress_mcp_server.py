# congress_mcp_server.py
import os
import asyncio
import httpx
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncIterator, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp import Context

# Load environment variables
load_dotenv()

# API Configuration
API_KEY = os.getenv("CONGRESS_API_KEY")
BASE_URL = "https://api.congress.gov/v3"

# Create the MCP server with metadata
mcp = FastMCP(
    "Congress.gov API",
    description="Access legislative data from the Congress.gov API",
    version="1.0.0",
    dependencies=["httpx", "python-dotenv"]
)

# Application context for handling API connection
@dataclass
class AppContext:
    """Application context for the Congress.gov API server."""
    api_key: str
    client: httpx.AsyncClient

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage API client lifecycle."""
    if not API_KEY:
        raise ValueError("CONGRESS_API_KEY environment variable is not set")
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Test connection
        try:
            response = await client.get(f"/congress?api_key={API_KEY}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to connect to Congress.gov API: {e}")
        
        # Yield context to server
        yield AppContext(api_key=API_KEY, client=client)

# Initialize server with lifespan
mcp = FastMCP("Congress.gov API", lifespan=app_lifespan)

# Helper function for API requests
async def make_api_request(endpoint: str, ctx: Context, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a request to the Congress.gov API with proper error handling."""
    app_ctx = ctx.request_context.lifespan_context
    client = app_ctx.client
    api_key = app_ctx.api_key
    
    # Prepare parameters
    request_params = params or {}
    request_params["api_key"] = api_key
    
    try:
        response = await client.get(endpoint, params=request_params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        error_message = f"API request failed: {e.response.status_code} - {e.response.text}"
        ctx.error(error_message) # Log the error to the MCP context
        # Return a dictionary indicating an error
        return {"error": error_message, "status_code": e.response.status_code}
    except httpx.RequestError as e:
        error_message = f"Request failed: {str(e)}"
        ctx.error(error_message) # Log the error to the MCP context
        # Return a dictionary indicating a request error
        return {"error": error_message}
    except json.JSONDecodeError:
        error_message = f"API returned non-JSON response for endpoint {endpoint}: {response.text}"
        ctx.error(error_message)
        return {"error": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred during API request to {endpoint}: {str(e)}"
        ctx.error(error_message)
        return {"error": error_message}

# Format helpers
def format_bill_summary(bill: Dict[str, Any]) -> str:
    """Format a bill into a readable summary."""
    result = []
    result.append(f"Bill: {bill.get('number', 'Unknown')}")
    result.append(f"Type: {bill.get('type', 'Unknown')}")
    result.append(f"Title: {bill.get('title', 'No title')}")
    result.append(f"Congress: {bill.get('congress', 'Unknown')}")
    
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    result.append(f"URL: {bill.get('url', 'No URL available')}")
    return "\n".join(result)

def format_amendment_summary(amendment: Dict[str, Any]) -> str:
    """Format an amendment into a readable summary."""
    result = []
    result.append(f"Amendment: {amendment.get('number', 'Unknown')}")
    result.append(f"Type: {amendment.get('type', 'Unknown')}")
    result.append(f"Congress: {amendment.get('congress', 'Unknown')}")
    
    if "latestAction" in amendment:
        action = amendment["latestAction"]
        result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    result.append(f"URL: {amendment.get('url', 'No URL available')}")
    return "\n".join(result)

def format_committee_summary(committee: Dict[str, Any]) -> str:
    """Format a committee into a readable summary."""
    result = []
    result.append(f"Committee: {committee.get('name', 'Unknown')}")
    result.append(f"Chamber: {committee.get('chamber', 'Unknown')}")
    result.append(f"Committee Code: {committee.get('systemCode', 'Unknown')}")
    result.append(f"URL: {committee.get('url', 'No URL available')}")
    return "\n".join(result)

def format_member_summary(member: Dict[str, Any]) -> str:
    """Format a member into a readable summary."""
    result = []
    name = member.get('name', {})
    result.append(f"Member: {name.get('firstName', '')} {name.get('middleName', '')} {name.get('lastName', '')}")
    result.append(f"Bioguide ID: {member.get('bioguideId', 'Unknown')}")
    result.append(f"Chamber: {member.get('chamber', 'Unknown')}")
    result.append(f"Party: {member.get('party', 'Unknown')}")
    result.append(f"State: {member.get('state', 'Unknown')}")
    if "district" in member:
        result.append(f"District: {member['district']}")
    result.append(f"URL: {member.get('url', 'No URL available')}")
    return "\n".join(result)

# Resources
# ============================================================================
# CONGRESS RESOURCES
# ============================================================================
@mcp.resource("congress://info/current")
async def get_current_congress() -> str:
    """
    Get information about the current Congress.
    
    Returns detailed information about the currently active Congress,
    including session dates, chamber information, and leadership.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/congress/current", ctx)
    congress = data.get("congress", {})
    return json.dumps(congress, indent=2)

@mcp.resource("congress://{congress_num}")
async def get_congress(congress_num: str) -> str:
    """Get information about a specific Congress by number."""
    ctx = mcp.get_context()
    data = await make_api_request(f"/congress/{congress_num}", ctx)
    congress = data.get("congress", {})
    return json.dumps(congress, indent=2)

# ============================================================================
# BILL RESOURCES
# ============================================================================

@mcp.resource("congress://bills/latest")
async def get_latest_bills() -> str:
    """
    Get the most recent bills introduced in Congress.
    
    Returns a list of the 10 most recently updated bills across all
    Congresses, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/bill", ctx, params={"limit": 10, "sort": "updateDate+desc"})
    bills = data.get("bills", [])
    
    result = ["# Latest Bills in Congress"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

@mcp.resource("congress://bills/{congress_num}")
async def get_bills_by_congress(congress_num: str) -> str:
    """
    Get bills from a specific Congress.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated bills from the
    specified Congress, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/bill/{congress_num}", ctx, params={"limit": 10, "sort": "updateDate+desc"})
    bills = data.get("bills", [])
    
    result = [f"# Bills from the {congress_num}th Congress"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

@mcp.resource("congress://bills/{congress_num}/{bill_type}")
async def get_bills_by_type(congress_num: str, bill_type: str) -> str:
    """
    Get bills from a specific Congress and bill type.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        bill_type: The type of bill (e.g., "hr", "s", "hjres", "sjres")
        
    Returns a list of the 10 most recently updated bills of the specified
    type from the specified Congress, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/bill/{congress_num}/{bill_type}", ctx, params={"limit": 10, "sort": "updateDate+desc"})
    bills = data.get("bills", [])
    
    result = [f"# {bill_type.upper()} Bills from the {congress_num}th Congress"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

# ============================================================================
# COMMITTEE RESOURCES
# ============================================================================

@mcp.resource("congress://committees")
async def get_committees() -> str:
    """
    Get a list of congressional committees.
    
    Returns a comprehensive list of committees in the House and Senate,
    including their names, chambers, and system codes.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/committee", ctx)
    committees = data.get("committees", [])
    
    result = ["# Congressional Committees"]
    for committee in committees:
        result.append("\n---\n")
        result.append(format_committee_summary(committee))
    
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
    data = await make_api_request("/committee", ctx)
    all_committees = data.get("committees", [])
    
    # Filter by chamber
    chamber = chamber.lower()
    if chamber not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    committees = [c for c in all_committees if c.get("chamber", "").lower() == chamber]
    
    result = [f"# {chamber.capitalize()} Committees"]
    for committee in committees:
        result.append("\n---\n")
        result.append(format_committee_summary(committee))
    
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
    endpoint = f"/committee/{chamber}/{committee_code}"
    
    try:
        data = await make_api_request(endpoint, ctx)
        committee = data.get("committee", {})
        
        result = [f"# {committee.get('name', 'Committee')}"]
        result.append(f"Chamber: {committee.get('chamber', 'Unknown')}")
        result.append(f"Committee Code: {committee.get('systemCode', 'Unknown')}")
        
        if "url" in committee:
            result.append(f"URL: {committee['url']}")
            
        if "subcommittees" in committee:
            result.append("\n## Subcommittees")
            for subcommittee in committee["subcommittees"]:
                result.append(f"- {subcommittee.get('name', 'Unknown')}")
                
        return "\n".join(result)
    except ValueError:
        return f"Committee not found: {committee_code} in {chamber}"

# ============================================================================
# MEMBER RESOURCES
# ============================================================================

@mcp.resource("congress://members/current")
async def get_current_members() -> str:
    """
    Get a list of current members of Congress.
    
    Returns a sample of 20 current members from both chambers of Congress,
    including their biographical information and contact details.
    """
    ctx = mcp.get_context()
    current_congress_data = await make_api_request("/congress/current", ctx)
    current_congress = current_congress_data.get("congress", {}).get("number")
    
    data = await make_api_request(f"/member/congress/{current_congress}", ctx, params={"limit": 20})
    members = data.get("members", [])
    
    result = [f"# Current Members of the {current_congress}th Congress (Sample)"]
    for member in members:
        result.append("\n---\n")
        result.append(format_member_summary(member))
    
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
    endpoint = f"/member/{bioguide_id}"
    
    try:
        data = await make_api_request(endpoint, ctx)
        member = data.get("member", {})
        
        if not member:
            return f"No information found for member with Bioguide ID {bioguide_id}."
        
        result = ["# Member Information"]
        
        # Basic information
        name = member.get("name", {})
        full_name = f"{name.get('firstName', '')} {name.get('middleName', '')} {name.get('lastName', '')}".strip()
        result.append(f"## {full_name}")
        result.append(f"Bioguide ID: {bioguide_id}")
        result.append(f"Chamber: {member.get('chamber', 'Unknown')}")
        result.append(f"Party: {member.get('party', 'Unknown')}")
        result.append(f"State: {member.get('state', 'Unknown')}")
        
        if "district" in member:
            result.append(f"District: {member['district']}")
        
        # Terms
        if "terms" in member:
            result.append("\n## Terms of Service")
            for term in member["terms"]:
                start_date = term.get("startDate", "Unknown")
                end_date = term.get("endDate", "Unknown")
                chamber = term.get("chamber", "Unknown")
                congress = term.get("congress", "Unknown")
                result.append(f"- {start_date} to {end_date}: {chamber}, {congress}th Congress")
        
        return "\n".join(result)
    except ValueError:
        return f"Member not found with Bioguide ID: {bioguide_id}"

# ============================================================================
# SEARCH TOOLS
# ============================================================================

@mcp.tool()
async def search_bills(
    keywords: str, 
    congress: Optional[int] = None, 
    bill_type: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """
    Search for bills based on keywords.
    
    Args:
        keywords: Keywords to search for in bill titles and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    params = {
        "query": keywords,
        "limit": limit,
        "sort": sort
    }
    
    if from_date:
        params["fromDateTime"] = from_date
    
    if to_date:
        params["toDateTime"] = to_date
    
    endpoint = "/bill"
    if congress:
        endpoint = f"/bill/{congress}"
        if bill_type:
            endpoint = f"/bill/{congress}/{bill_type}"
    
    ctx = mcp.get_context()
    data = await make_api_request(endpoint, ctx, params=params)
    bills = data.get("bills", [])
    
    if not bills:
        return f"No bills found matching '{keywords}'."
    
    result = [f"# Bills Matching '{keywords}'"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

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
    params = {"limit": limit}
    
    if name:
        params["name"] = name
    
    if state:
        params["state"] = state
    
    if party:
        params["party"] = party
    
    endpoint = "/member"
    if congress:
        endpoint = f"/member/congress/{congress}"
    
    ctx = mcp.get_context()
    data = await make_api_request(endpoint, ctx, params=params)
    members = data.get("members", [])
    
    if not members:
        return "No members found matching the specified criteria."
    
    # Filter by chamber if specified
    if chamber:
        chamber = chamber.lower()
        members = [m for m in members if m.get("chamber", "").lower() == chamber]
    
    result = ["# Members of Congress"]
    for member in members:
        result.append("\n---\n")
        result.append(format_member_summary(member))
    
    return "\n".join(result)

# ============================================================================
# BILL DETAIL TOOLS
# ============================================================================

@mcp.tool()
async def get_bill_actions(
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 10
) -> str:
    """
    Get actions for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        limit: Maximum number of actions to return (default: 10)
    """
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/actions"
    params = {"limit": limit}
    
    data = await make_api_request(endpoint, ctx, params)
    actions = data.get("actions", [])
    
    if not actions:
        return f"No actions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Actions for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    result.append(f"Total Actions: {len(actions)}")
    
    for action in actions:
        date = action.get("actionDate", "Unknown date")
        text = action.get("text", "Unknown action")
        action_type = action.get("type", "")
        
        if action_type:
            result.append(f"## {date} - {action_type}")
        else:
            result.append(f"## {date}")
        
        result.append(text)
    
    return "\n\n".join(result)

@mcp.tool()
async def get_bill_details(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get detailed information about a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}"
    ctx = mcp.get_context()
    data = await make_api_request(endpoint, ctx)
    bill = data.get("bill", {})
    
    if not bill:
        return f"No details found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    # Basic information
    result.append(f"## Title\n{bill.get('title', 'No title available')}")
    result.append(f"## Introduction Date\n{bill.get('introducedDate', 'Unknown')}")
    
    # Sponsor
    if "sponsor" in bill:
        sponsor = bill["sponsor"]
        name = sponsor.get("name", "Unknown")
        state = sponsor.get("state", "")
        party = sponsor.get("party", "")
        result.append(f"## Sponsor\n{name} ({party}-{state})")
    
    # Latest action
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"## Latest Action\n{action.get('actionDate', 'Unknown date')}: {action.get('text', 'Unknown')}")
    
    # Get summaries
    try:
        summaries_data = await make_api_request(f"{endpoint}/summaries", ctx)
        summaries = summaries_data.get("summaries", [])
        if summaries:
            result.append("## Summary")
            latest_summary = summaries[0]  # Assuming first is most recent
            result.append(latest_summary.get("text", "No summary available"))
    except Exception as e:
        result.append("## Summary\nFailed to retrieve summary information.")
    
    # Get actions
    try:
        actions_data = await make_api_request(f"{endpoint}/actions", ctx)
        actions = actions_data.get("actions", [])
        if actions:
            result.append("## Recent Actions")
            for action in actions[:5]:  # Top 5 most recent actions
                result.append(f"- {action.get('actionDate', 'Unknown date')}: {action.get('text', 'Unknown')}")
    except Exception as e:
        result.append("## Actions\nFailed to retrieve action information.")
    
    return "\n\n".join(result)

@mcp.tool()
async def get_member_info(
    bioguide_id: str
) -> str:
    """
    Get detailed information about a member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member
    """
    try:
        endpoint = f"/member/{bioguide_id}"
        ctx = mcp.get_context()
        data = await make_api_request(endpoint, ctx)
        
        if not isinstance(data, dict):
            return f"Error: Unexpected response format for member with Bioguide ID {bioguide_id}."
            
        member = data.get("member", {})
        
        if not member:
            return f"No information found for member with Bioguide ID {bioguide_id}."
        
        result = ["# Member Information"]
        
        # Basic information - handle different name formats
        if "name" in member and isinstance(member["name"], dict):
            name = member["name"]
            first = name.get("firstName", "")
            middle = name.get("middleName", "")
            last = name.get("lastName", "")
            full_name = f"{first} {middle} {last}".strip()
            if not full_name:
                full_name = name.get("displayName", "")
        elif "displayName" in member:
            full_name = member.get("displayName", "")
        elif "officialName" in member:
            full_name = member.get("officialName", "")
        elif "fullName" in member:
            full_name = member.get("fullName", "")
        else:
            full_name = "Unknown"
            
        result.append(f"## {full_name}")
        result.append(f"Bioguide ID: {bioguide_id}")
        
        # Add chamber info
        chamber = member.get("chamber", "Unknown")
        if chamber != "Unknown":
            result.append(f"Chamber: {chamber}")
            
        # Add party info
        party = member.get("party", "Unknown")
        if party != "Unknown":
            result.append(f"Party: {party}")
            
        # Add state info
        state = member.get("state", "Unknown")
        if state != "Unknown":
            result.append(f"State: {state}")
        
        # Add district if available
        if "district" in member:
            result.append(f"District: {member['district']}")
        
        # Terms - with improved date formatting
        if "terms" in member and isinstance(member["terms"], list) and member["terms"]:
            result.append("\n## Terms of Service")
            for term in member["terms"]:
                # Format dates properly
                start_date = term.get("startDate", "Unknown")
                if start_date != "Unknown" and len(start_date) >= 10:
                    start_date = start_date[:10]  # Extract YYYY-MM-DD part
                    
                end_date = term.get("endDate", "Unknown")
                if end_date != "Unknown" and len(end_date) >= 10:
                    end_date = end_date[:10]  # Extract YYYY-MM-DD part
                    
                chamber = term.get("chamber", "Unknown")
                congress = term.get("congress", "Unknown")
                
                if start_date != "Unknown" and end_date != "Unknown" and chamber != "Unknown" and congress != "Unknown":
                    result.append(f"- {start_date} to {end_date}: {chamber}, {congress}th Congress")
                elif start_date != "Unknown" and chamber != "Unknown" and congress != "Unknown":
                    result.append(f"- From {start_date}: {chamber}, {congress}th Congress")
                elif chamber != "Unknown" and congress != "Unknown":
                    result.append(f"- {chamber}, {congress}th Congress")
        
        # Get sponsored legislation with better error handling
        try:
            sponsored_data = await make_api_request(f"{endpoint}/sponsored-legislation", ctx, {"limit": 5})
            if isinstance(sponsored_data, dict):
                sponsored = sponsored_data.get("sponsoredLegislation", [])
                if sponsored and isinstance(sponsored, list):
                    result.append("\n## Recent Sponsored Legislation")
                    for bill in sponsored:
                        if isinstance(bill, dict):
                            title = bill.get("title", "No title")
                            number = bill.get("number", "Unknown")
                            congress = bill.get("congress", "Unknown")
                            result.append(f"- {number} ({congress}th Congress): {title}")
        except Exception as e:
            # Don't add error message if we couldn't get legislation - it's optional info
            pass
        
        # Add committees if available
        try:
            committees_data = await make_api_request(f"{endpoint}/committees", ctx)
            if isinstance(committees_data, dict):
                committees = committees_data.get("committees", [])
                if committees and isinstance(committees, list):
                    result.append("\n## Committee Assignments")
                    for committee in committees:
                        if isinstance(committee, dict):
                            name = committee.get("name", "Unknown")
                            chamber = committee.get("chamber", "")
                            if chamber:
                                result.append(f"- {name} ({chamber})")
                            else:
                                result.append(f"- {name}")
        except Exception:
            # Don't add error message if we couldn't get committees - it's optional info
            pass
        
        return "\n".join(result)
    except Exception as e:
        return f"Error retrieving information for member with Bioguide ID {bioguide_id}: {str(e)}"

@mcp.tool()
async def get_committee_bills(
    chamber: str,
    committee_code: str,
    limit: int = 10
) -> str:
    try:
        chamber = chamber.lower()
        if chamber not in ["house", "senate"]:
            return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
        
        ctx = mcp.get_context() # Get the context once
        
        committee_codes_to_try = []
        # ... (Your existing logic to build committee_codes_to_try) ...
        
        for code in committee_codes_to_try:
            try:
                # 1. Verify the committee exists using make_api_request
                committee_endpoint = f"/committee/{chamber}/{code}"
                committee_data = await make_api_request(committee_endpoint, ctx)

                if "error" in committee_data:
                    # If there's an error, it might be a 404, so try the next code
                    if committee_data.get("status_code") == 404:
                        continue # Committee not found with this code, try next
                    else:
                        # Other API error, return it or log more specifically
                        return f"Error checking committee {code}: {committee_data['error']}"

                committee_name = committee_data.get("committee", {}).get("name", f"{chamber.capitalize()} Committee {code}")
                
                # 2. Now get the bills for this committee using make_api_request
                bills_endpoint = f"/committee/{chamber}/{code}/bills"
                bills_data = await make_api_request(bills_endpoint, ctx, {"limit": limit})
                
                if "error" in bills_data:
                    return f"Committee found: {committee_name}, but bills could not be retrieved. Error: {bills_data['error']}"

                bills = bills_data.get("bills", [])
                
                if not bills:
                    return f"No bills found for committee '{committee_name}' ({code}) in the {chamber.capitalize()}."
                
                result = [f"# Bills for {committee_name} ({chamber.capitalize()})"]
                for bill in bills:
                    result.append("\n---\n")
                    result.append(format_bill_summary(bill))
                
                return "\n".join(result)
            
            except Exception as inner_e: # Catch any remaining unexpected errors within the loop
                # This could be for issues not caught by make_api_request's error handling
                continue # Try next code format, as this one failed unexpectedly

        # If we've tried all formats and none worked
        return f"Committee not found: Could not find a valid committee with code '{committee_code}' in the {chamber.capitalize()}. Please verify the committee code."
    
    except Exception as e:
        # This outer catch is for truly unexpected errors in the tool's logic itself
        return f"Error processing committee bills request: {str(e)}"

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
    amendments = data.get("amendments", [])
    
    if not amendments:
        return f"No amendments found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Amendments to {bill_type.upper()} {bill_number} - {congress}th Congress"]
    for amendment in amendments:
        result.append("\n---\n")
        result.append(format_amendment_summary(amendment))
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_cosponsors(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get cosponsors for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        ctx = mcp.get_context()
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/cosponsors"
        
        data = await make_api_request(endpoint, ctx)
        cosponsors = data.get("cosponsors", [])
        
        if not cosponsors:
            return f"No cosponsors found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
        
        result = [f"# Cosponsors for {bill_type.upper()} {bill_number} - {congress}th Congress"]
        result.append(f"Total Cosponsors: {len(cosponsors)}")
        
        for cosponsor in cosponsors:
            # Extract name from fullName which typically has format "Rep. Smith, John [D-CA-1]"
            if "fullName" in cosponsor:
                full_name = cosponsor.get("fullName", "")
                # Try to extract the actual name from the format
                if full_name:
                    # Extract name portion (typically after "Rep. " or "Sen. " and before "[")
                    name_parts = full_name.split("[")[0].strip()
                    if ", " in name_parts:
                        # Handle "Last, First" format
                        if name_parts.startswith("Rep. ") or name_parts.startswith("Sen. "):
                            name_parts = name_parts[5:].strip()  # Remove "Rep. " or "Sen. "
                        last_name, first_name = name_parts.split(", ", 1)
                        name = f"{first_name} {last_name}"
                    else:
                        name = name_parts
                else:
                    name = "Unknown"
            else:
                name = "Unknown"
            
            # Extract party and state from fullName which has format "[D-CA-1]" at the end
            party = "Unknown"
            state = "Unknown"
            if "fullName" in cosponsor:
                full_name = cosponsor.get("fullName", "")
                if "[" in full_name and "]" in full_name:
                    bracket_content = full_name.split("[")[1].split("]")[0]
                    parts = bracket_content.split("-")
                    if len(parts) >= 2:
                        party = parts[0]
                        state = parts[1]
            
            # Fallback to direct party and state fields if available
            if party == "Unknown" and "party" in cosponsor:
                party = cosponsor.get("party")
            if state == "Unknown" and "state" in cosponsor:
                state = cosponsor.get("state")
            
            # Get date
            date = cosponsor.get("sponsorshipDate", "Unknown date")
            
            # Format the output
            if party != "Unknown" and state != "Unknown":
                result.append(f"- {name} ({party}-{state}), added {date}")
            elif party:
                result.append(f"- {name} ({party}), added {date}")
            elif state:
                result.append(f"- {name} ({state}), added {date}")
            else:
                result.append(f"- {name}, added {date}")
        
        return "\n".join(result)
    except Exception as e:
        return f"Error retrieving cosponsors for {bill_type.upper()} {bill_number} in the {congress}th Congress: {str(e)}"

@mcp.tool()
async def get_bill_subjects(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get legislative subjects for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    try:
        # Create a formatted title
        title = f"# Legislative Subjects for {bill_type.upper()} {bill_number} - {congress}th Congress"
        
        # Get the context to access API key
        ctx = mcp.get_context()
        
        # Define the endpoint according to the API documentation
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/subjects"
        
        # Make the API request
        response = await make_api_request(endpoint, ctx)
        
        # Format the response
        result = [title]
        
        # Check if the response contains the subjects key
        if isinstance(response, dict) and "subjects" in response:
            subjects_data = response["subjects"]
            
            # Add policy area if available
            if "policyArea" in subjects_data and isinstance(subjects_data["policyArea"], dict):
                policy_area = subjects_data["policyArea"]
                if "name" in policy_area:
                    result.append(f"\n## Policy Area\n{policy_area['name']}")
            
            # Add legislative subjects if available
            if "legislativeSubjects" in subjects_data and isinstance(subjects_data["legislativeSubjects"], list):
                leg_subjects = subjects_data["legislativeSubjects"]
                if leg_subjects:
                    result.append("\n## Legislative Subjects")
                    for subject in leg_subjects:
                        if isinstance(subject, dict) and "name" in subject:
                            result.append(f"- {subject['name']}")
            
            return "\n".join(result)
        
        # If we get here, there was an issue with the response format or no subjects found
        # Try to extract error message if available
        error_msg = "No subject information is available for this bill."
        if isinstance(response, dict) and "error" in response:
            error_msg = f"API Error: {response['error']}"
        
        return f"{title}\n\n{error_msg}"
    
    except Exception as e:
        # Create a formatted title for error message
        title = f"# Legislative Subjects for {bill_type.upper()} {bill_number} - {congress}th Congress"
        
        # Return error message with details to help debugging
        error_details = str(e)
        if "404" in error_details:
            return f"{title}\n\nBill not found. Please verify the congress, bill type, and bill number."
        elif "401" in error_details or "403" in error_details:
            return f"{title}\n\nAPI authentication error. Please check your API key."
        else:
            return f"{title}\n\nError retrieving subjects: {error_details}"


@mcp.tool()
async def get_bill_text_versions(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get text versions for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/text"
    
    data = await make_api_request(endpoint, ctx)
    text_versions = data.get("textVersions", [])
    
    if not text_versions:
        return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Text Versions for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    for version in text_versions:
        version_type = version.get("type", "Unknown version")
        date = version.get("date", "Unknown date")
        
        result.append(f"## {version_type}")
        if date:
            result.append(f"Date: {date}")
        
        if "formats" in version:
            result.append("Available formats:")
            for fmt in version["formats"]:
                fmt_type = fmt.get("type", "Unknown format")
                url = fmt.get("url", "No URL available")
                result.append(f"- [{fmt_type}]({url})")
        
        result.append("\n")
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_titles(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get titles for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/titles"
    
    data = await make_api_request(endpoint, ctx)
    titles = data.get("titles", [])
    
    if not titles:
        return f"No titles found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Titles for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    for title in titles:
        title_text = title.get("title", "Unknown title")
        title_type = title.get("titleType", "Unknown type")
        is_official = title.get("isOfficial", False)
        chamber_name = title.get("chamberName", "")
        
        if is_official:
            result.append(f"## Official Title: {title_type}")
        else:
            result.append(f"## {title_type}")
            
        if chamber_name:
            result.append(f"Chamber: {chamber_name}")
            
        result.append(title_text)
        result.append("\n")
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_summaries(
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
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/summaries"
    
    data = await make_api_request(endpoint, ctx)
    summaries = data.get("summaries", [])
    
    if not summaries:
        return f"No summaries found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Summaries for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    for summary in summaries:
        action_date = summary.get("actionDate", "Unknown date")
        action_desc = summary.get("actionDesc", "")
        update_date = summary.get("updateDate", "")
        version_code = summary.get("versionCode", "")
        
        if action_desc:
            result.append(f"## {action_date} - {action_desc}")
        else:
            result.append(f"## {action_date}")
            
        if version_code:
            result.append(f"Version: {version_code}")
            
        if update_date:
            result.append(f"Updated: {update_date}")
            
        result.append(summary.get("text", "No summary text available"))
        result.append("\n")
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_related_bills(
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get related bills for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/relatedbills"
    
    data = await make_api_request(endpoint, ctx)
    related_bills = data.get("relatedBills", [])
    
    if not related_bills:
        return f"No related bills found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Related Bills for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    for bill in related_bills:
        bill_congress = bill.get("congress", "Unknown")
        bill_type_rel = bill.get("type", "Unknown").upper()
        bill_number_rel = bill.get("number", "Unknown")
        title = bill.get("title", "No title available")
        
        result.append(f"## {bill_type_rel} {bill_number_rel} ({bill_congress}th Congress)")
        result.append(f"Title: {title}")
        
        if "relationshipDetails" in bill:
            result.append("Relationship:")
            for detail in bill["relationshipDetails"]:
                rel_type = detail.get("type", "Unknown relationship")
                identified_by = detail.get("identifiedBy", "")
                if identified_by:
                    result.append(f"- {rel_type} (Identified by: {identified_by})")
                else:
                    result.append(f"- {rel_type}")
        
        if "latestAction" in bill:
            action = bill["latestAction"]
            result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
            
        result.append("\n")
    
    return "\n".join(result)

# Prompts
@mcp.prompt()
def search_legislation_prompt() -> str:
    """Create a prompt for searching legislation."""
    return """
I need help finding legislation related to a specific topic. Please search for relevant bills, amendments, or committee activities.

The topic I'm interested in is: 
    """

@mcp.prompt()
def bill_analysis_prompt() -> str:
    """Create a prompt for analyzing a specific bill."""
    return """
I need help analyzing a specific bill. Please provide details about the following:

Bill Type (e.g., H.R., S.): 
Bill Number: 
Congress (e.g., 117 for 117th Congress): 

I'm particularly interested in understanding:
- The main provisions of the bill
- Key sponsors and cosponsors
- Committee activity
- Current status and recent actions
- Related amendments
    """

@mcp.prompt()
def member_legislation_prompt() -> str:
    """Create a prompt for analyzing a member's legislative activities."""
    return """
I'd like to learn about the legislative activities of a specific member of Congress.

Member Name: 
(Alternatively, if you know it) Bioguide ID: 

Please tell me about:
- Their sponsored and cosponsored legislation
- Committee assignments
- Voting patterns on major legislation
- Recent legislative activities
    """

@mcp.prompt()
def committee_activity_prompt() -> str:
    """Create a prompt for analyzing committee activities."""
    return """
I'm researching the activities of a specific congressional committee.

Chamber (House or Senate): 
Committee Name or Code: 

Please provide information about:
- Recent bills considered by this committee
- Hearings and markups
- Major actions taken
- Current leadership and membership
    """

# Main execution
if __name__ == "__main__":
    import logging
    import sys

        # Configure logging to stderr instead of stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr
    )
    
    print("Starting Congress.gov MCP Server...", file=sys.stderr)
    print("Make sure to set the CONGRESS_API_KEY environment variable!", file=sys.stderr)
    
    # Run the server
    mcp.run()