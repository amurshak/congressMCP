# congress_mcp_server.py
import os
import json
import httpx
from datetime import datetime
from typing import Optional, Dict, List, Any, AsyncIterator
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

# Create the MCP server
mcp = FastMCP(
    "Congress.gov API",
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

# Resources
@mcp.resource("congress://current")
async def get_current_congress() -> str:
    """Get information about the current Congress."""
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

@mcp.resource("bill://latest")
async def get_latest_bills() -> str:
    """Get the most recent bills introduced in Congress."""
    ctx = mcp.get_context()
    data = await make_api_request("/bill", ctx, params={"limit": 10, "sort": "updateDate+desc"})
    bills = data.get("bills", [])
    
    result = ["# Latest Bills in Congress"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

@mcp.resource("committee://list")
async def get_committees() -> str:
    """Get a list of congressional committees."""
    ctx = mcp.get_context()
    data = await make_api_request("/committee", ctx)
    committees = data.get("committees", [])
    
    result = ["# Congressional Committees"]
    for committee in committees:
        result.append("\n---\n")
        result.append(format_committee_summary(committee))
    
    return "\n".join(result)

@mcp.resource("member://current")
async def get_current_members() -> str:
    """Get a list of current members of Congress."""
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

# Tools
@mcp.tool()
async def search_bills(
    keywords: str, 
    congress: Optional[int] = None, 
    bill_type: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for bills based on keywords.
    
    Args:
        keywords: Keywords to search for in bill titles and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill)
        limit: Maximum number of results to return (default: 10)
    """
    params = {
        "query": keywords,
        "limit": limit,
        "sort": "updateDate+desc"
    }
    
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
    endpoint = f"/member/{bioguide_id}"
    ctx = mcp.get_context()
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
    
    # Get sponsored legislation
    try:
        sponsored_data = await make_api_request(f"{endpoint}/sponsored-legislation", ctx, {"limit": 5})
        sponsored = sponsored_data.get("sponsoredLegislation", [])
        if sponsored:
            result.append("\n## Recent Sponsored Legislation")
            for bill in sponsored:
                title = bill.get("title", "No title")
                number = bill.get("number", "Unknown")
                congress = bill.get("congress", "Unknown")
                result.append(f"- {number} ({congress}th Congress): {title}")
    except Exception as e:
        result.append("\n## Recent Sponsored Legislation\nFailed to retrieve sponsored legislation.")
    
    return "\n".join(result)

@mcp.tool()
async def get_committee_bills(
    chamber: str,
    committee_code: str,
    limit: int = 10
) -> str:
    """
    Get bills associated with a specific committee.
    
    Args:
        chamber: Chamber of the committee ('house' or 'senate')
        committee_code: Committee code (e.g., 'hsag', 'ssap')
        limit: Maximum number of results to return (default: 10)
    """
    ctx = mcp.get_context()
    endpoint = f"/committee/{chamber}/{committee_code}/bills"
    params = {"limit": limit}
    
    data = await make_api_request(endpoint, ctx, params)
    bills = data.get("bills", [])
    
    if not bills:
        return f"No bills found for committee {committee_code} in the {chamber}."
    
    committee_data = await make_api_request(f"/committee/{chamber}/{committee_code}", ctx)
    committee_name = committee_data.get("committee", {}).get("name", f"{chamber.capitalize()} Committee {committee_code}")
    
    result = [f"# Bills for {committee_name}"]
    for bill in bills:
        result.append("\n---\n")
        result.append(format_bill_summary(bill))
    
    return "\n".join(result)

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
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/cosponsors"
    data = await make_api_request(endpoint, ctx)
    cosponsors = data.get("cosponsors", [])
    
    if not cosponsors:
        return f"No cosponsors found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"# Cosponsors for {bill_type.upper()} {bill_number} - {congress}th Congress"]
    result.append(f"Total Cosponsors: {len(cosponsors)}")
    
    for cosponsor in cosponsors:
        name = cosponsor.get("name", "Unknown")
        state = cosponsor.get("state", "")
        party = cosponsor.get("party", "")
        date = cosponsor.get("sponsorshipDate", "Unknown date")
        result.append(f"- {name} ({party}-{state}), added {date}")
    
    return "\n".join(result)

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