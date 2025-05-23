# bills.py
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Formatting helpers
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

# Resources
@mcp.resource("congress://bills/latest")
async def get_latest_bills() -> str:
    """
    Get the most recent bills introduced in Congress.
    
    Returns a list of the 10 most recently updated bills across all
    Congresses, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/bill", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return f"Error retrieving bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        return "No bills found."
    
    result = ["Latest bills in Congress:"]
    for bill in bills:
        result.append("\n" + format_bill_summary(bill))
    
    return "\n".join(result)

@mcp.resource("congress://bills/congress/{congress_num}")
async def get_bills_by_congress(congress_num: str) -> str:
    """
    Get bills from a specific Congress.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated bills from the
    specified Congress, sorted by update date in descending order.
    """
    ctx = mcp.get_context()
    data = await make_api_request(f"/bill/{congress_num}", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return f"Error retrieving bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        return f"No bills found for the {congress_num}th Congress."
    
    result = [f"Bills from the {congress_num}th Congress:"]
    for bill in bills:
        result.append("\n" + format_bill_summary(bill))
    
    return "\n".join(result)

@mcp.resource("congress://bills/congress/{congress_num}/type/{bill_type}")
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
    data = await make_api_request(f"/bill/{congress_num}/{bill_type}", ctx, {"limit": 10, "sort": "updateDate+desc"})
    
    if "error" in data:
        return f"Error retrieving bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        return f"No {bill_type.upper()} bills found for the {congress_num}th Congress."
    
    result = [f"{bill_type.upper()} bills from the {congress_num}th Congress:"]
    for bill in bills:
        result.append("\n" + format_bill_summary(bill))
    
    return "\n".join(result)

# Tools
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
    ctx = mcp.get_context()
    
    # Build parameters
    params = {
        "query": keywords,
        "limit": limit,
        "sort": sort
    }
    
    if congress:
        params["congress"] = congress
    if bill_type:
        params["billType"] = bill_type
    if from_date:
        params["fromDateTime"] = from_date
    if to_date:
        params["toDateTime"] = to_date
    
    data = await make_api_request("/bill/search", ctx, params)
    
    if "error" in data:
        return f"Error searching bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        return f"No bills found matching '{keywords}'."
    
    result = [f"Found {len(bills)} bills matching '{keywords}':"]
    for bill in bills:
        result.append("\n" + format_bill_summary(bill))
    
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
    ctx = mcp.get_context()
    endpoint = f"/bill/{congress}/{bill_type}/{bill_number}"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill details: {data['error']}"
    
    bill = data.get("bill", {})
    if not bill:
        return f"No details found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"## {bill_type.upper()} {bill_number} - {congress}th Congress"]
    
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
    
    # Summary
    if "summaries" in bill and "count" in bill["summaries"] and bill["summaries"]["count"] > 0:
        result.append("\n**Summary Available:** Use get_bill_summaries tool for detailed summary.")
    
    # Text Versions
    if "textVersions" in bill and "count" in bill["textVersions"] and bill["textVersions"]["count"] > 0:
        result.append("**Text Versions Available:** Use get_bill_text_versions tool for text versions.")
    
    # URL
    if "url" in bill:
        result.append(f"\n**URL:** {bill['url']}")
    
    return "\n".join(result)

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
    data = await make_api_request(endpoint, ctx, {"limit": limit})
    
    if "error" in data:
        return f"Error retrieving bill actions: {data['error']}"
    
    actions = data.get("actions", [])
    if not actions:
        return f"No actions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"Actions for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
    for i, action in enumerate(actions, 1):
        date = action.get("actionDate", "Unknown date")
        text = action.get("text", "Unknown action")
        result.append(f"\n{i}. **{date}**: {text}")
    
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
    
    if "error" in data:
        return f"Error retrieving bill cosponsors: {data['error']}"
    
    cosponsors = data.get("cosponsors", [])
    if not cosponsors:
        return f"No cosponsors found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
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
    
    if "error" in data:
        return f"Error retrieving bill subjects: {data['error']}"
    
    subjects = data.get("subjects", {})
    if not subjects:
        return f"No subjects found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
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
    
    if "error" in data:
        return f"Error retrieving bill summaries: {data['error']}"
    
    summaries = data.get("summaries", [])
    if not summaries:
        return f"No summaries found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"Summaries for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
    for i, summary in enumerate(summaries, 1):
        date = summary.get("actionDate", "Unknown date")
        text = summary.get("text", "No summary text available")
        
        result.append(f"\n**Summary {i} ({date}):**")
        result.append(text)
    
    return "\n".join(result)

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
    
    if "error" in data:
        return f"Error retrieving bill text versions: {data['error']}"
    
    text_versions = data.get("textVersions", [])
    if not text_versions:
        return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"Text versions for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
    for i, version in enumerate(text_versions, 1):
        version_type = version.get("type", "Unknown version")
        date = version.get("date", "Unknown date")
        
        result.append(f"\n{i}. **{version_type}** ({date})")
        
        if "formats" in version:
            result.append("  Available formats:")
            for fmt in version["formats"]:
                format_type = fmt.get("type", "Unknown format")
                url = fmt.get("url", "No URL available")
                result.append(f"  - {format_type}: {url}")
    
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
    
    if "error" in data:
        return f"Error retrieving bill titles: {data['error']}"
    
    titles = data.get("titles", [])
    if not titles:
        return f"No titles found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"Titles for {bill_type.upper()} {bill_number} in the {congress}th Congress:"]
    for i, title in enumerate(titles, 1):
        title_text = title.get("title", "Unknown title")
        title_type = title.get("titleType", "Unknown type")
        
        result.append(f"\n{i}. **{title_type}:** {title_text}")
    
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
    
    if "error" in data:
        return f"Error retrieving related bills: {data['error']}"
    
    related_bills = data.get("relatedBills", [])
    if not related_bills:
        return f"No related bills found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
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
