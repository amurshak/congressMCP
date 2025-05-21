# congress_mcp_server_improved.py
import os
import json
import httpx
from datetime import datetime
from typing import Optional, Dict, List, Any, AsyncIterator, Union
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
mcp = FastMCP(
    "Congress.gov API", 
    description="Access legislative data from the Congress.gov API",
    version="1.0.0",
    lifespan=app_lifespan
)

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
        error_msg = f"API request failed: {e.response.status_code} - {e.response.text}"
        ctx.error(error_msg)
        raise ValueError(error_msg)
    except httpx.RequestError as e:
        error_msg = f"Request failed: {str(e)}"
        ctx.error(error_msg)
        raise ValueError(error_msg)

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

@mcp.resource("congress://info/{congress_num}")
async def get_congress(congress_num: str) -> str:
    """
    Get information about a specific Congress by number.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns detailed information about the specified Congress,
    including session dates, chamber information, and leadership.
    """
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

@mcp.resource("congress://bills/{congress_num}/{bill_type}/{bill_number}")
async def get_bill_details(congress_num: str, bill_type: str, bill_number: str) -> str:
    """
    Get detailed information about a specific bill.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        bill_type: The type of bill (e.g., "hr", "s", "hjres", "sjres")
        bill_number: The bill number (e.g., "3076")
        
    Returns comprehensive information about the specified bill,
    including title, sponsor, actions, and related data.
    """
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress_num}/{bill_type}/{bill_number}"
    data = await make_api_request(endpoint, ctx)
    bill = data.get("bill", {})
    
    if not bill:
        return f"No details found for {bill_type.upper()} {bill_number} in the {congress_num}th Congress."
    
    result = [f"# {bill_type.upper()} {bill_number} - {congress_num}th Congress"]
    
    # Basic information
    result.append(f"## Title\n{bill.get('title', 'No title available')}")
    result.append(f"## Introduction Date\n{bill.get('introducedDate', 'Unknown')}")
    
    # Sponsor
    if "sponsors" in bill and bill["sponsors"]:
        sponsor = bill["sponsors"][0]
        name = sponsor.get("fullName", "Unknown")
        state = sponsor.get("state", "")
        party = sponsor.get("party", "")
        result.append(f"## Sponsor\n{name} ({party}-{state})")
    
    # Latest action
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"## Latest Action\n{action.get('actionDate', 'Unknown date')}: {action.get('text', 'Unknown')}")
    
    # Policy area
    if "policyArea" in bill:
        policy_area = bill["policyArea"]
        result.append(f"## Policy Area\n{policy_area.get('name', 'Unknown')}")
    
    return "\n\n".join(result)

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
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/subjects"
    
    data = await make_api_request(endpoint, ctx)
    subjects_data = data.get("subjects", {})
    
    if not subjects_data:
        return f"No subjects found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Legislative Subjects for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
    # Policy area
    policy_area = subjects_data.get("policyArea", {})
    if policy_area:
        result.append(f"## Policy Area\n{policy_area.get('name', 'Unknown')}")
    
    # Legislative subjects
    legislative_subjects = subjects_data.get("legislativeSubjects", [])
    if legislative_subjects:
        result.append("## Legislative Subjects")
        for subject in legislative_subjects:
            result.append(f"- {subject.get('name', 'Unknown')}")
    
    return "\n".join(result)

# ============================================================================
# PROMPTS
# ============================================================================

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
I'd like to analyze a specific bill in detail. Please provide information about:

1. The bill's basic information (title, number, sponsor)
2. Current status and latest actions
3. Key provisions and summary
4. Committee assignments
5. Related bills or amendments
6. Policy areas and subjects

Bill information:
- Congress: (e.g., 117)
- Bill Type: (e.g., HR, S, HJRES)
- Bill Number: (e.g., 3076)
    """

@mcp.prompt()
def member_legislation_prompt() -> str:
    """Create a prompt for analyzing a member's legislative activities."""
    return """
I'd like to analyze the legislative activities of a specific member of Congress. Please provide information about:

1. The member's basic information (name, party, state/district)
2. Committee assignments
3. Sponsored and cosponsored legislation
4. Voting record on key issues
5. Leadership positions

Member Bioguide ID: (e.g., A000055)
    """

@mcp.prompt()
def committee_activity_prompt() -> str:
    """Create a prompt for analyzing committee activities."""
    return """
I'd like to analyze the activities of a specific congressional committee. Please provide information about:

1. The committee's jurisdiction and purpose
2. Current leadership and membership
3. Recent hearings and markups
4. Bills referred to the committee
5. Subcommittees and their activities

Committee information:
- Chamber: (e.g., house, senate)
- Committee Code: (e.g., hsag, ssap)
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
    
    print("Starting Improved Congress.gov MCP Server...", file=sys.stderr)
    print("Make sure to set the CONGRESS_API_KEY environment variable!", file=sys.stderr)
    
    # Run the server
    mcp.run()
