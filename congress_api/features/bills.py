from typing import Dict, List, Any, Optional
import logging
from fastmcp import Context
import httpx
import re
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Core API Helpers ---

async def _fetch_bill_data(ctx: Context, congress: Optional[int] = None, bill_type: Optional[str] = None, 
                          bill_number: Optional[int] = None, sub_endpoint: str = "", **params) -> Dict[str, Any]:
    """
    Core helper to fetch bill data from Congress.gov API.
    
    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 117)
        bill_type: Bill type (e.g., 'hr', 's')
        bill_number: Bill number
        sub_endpoint: Additional endpoint path (e.g., 'actions', 'cosponsors')
        **params: Additional query parameters (limit, sort, etc.)
    """
    endpoint = _build_bill_endpoint(congress, bill_type, bill_number, sub_endpoint)
    logger.debug(f"Fetching bill data from endpoint: {endpoint}")
    
    # Set default parameters
    query_params = {'format': 'json'}
    query_params.update(params)
    
    return await make_api_request(endpoint=endpoint, params=query_params, ctx=ctx)

def _build_bill_endpoint(congress: Optional[int] = None, bill_type: Optional[str] = None, 
                        bill_number: Optional[int] = None, sub_endpoint: str = "") -> str:
    """
    Build the appropriate Congress.gov API endpoint based on parameters.
    
    Args:
        congress: Congress number
        bill_type: Bill type (hr, s, hjres, sjres, hconres, sconres, hres, sres)
        bill_number: Bill number
        sub_endpoint: Additional endpoint path
    
    Returns:
        Constructed endpoint path
    """
    if congress and bill_type and bill_number:
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}"
    elif congress and bill_type:
        endpoint = f"/bill/{congress}/{bill_type.lower()}"
    elif congress:
        endpoint = f"/bill/{congress}"
    else:
        endpoint = "/bill"
    
    if sub_endpoint:
        endpoint += f"/{sub_endpoint}"
    
    return endpoint

async def _filter_bills_by_keywords(bills: List[Dict[str, Any]], keywords: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Filter bills by keywords in title and policy area.
    
    Args:
        bills: List of bill dictionaries
        keywords: Keywords to search for
        limit: Maximum number of results to return
    
    Returns:
        Filtered list of bills
    """
    if not keywords or not bills:
        return bills[:limit]
    
    keywords_lower = keywords.lower()
    filtered_bills = []
    
    for bill in bills:
        # Check title
        title = bill.get('title', '').lower()
        # Check policy area
        policy_area = bill.get('policyArea', {}).get('name', '').lower() if bill.get('policyArea') else ''
        
        # Search in multiple fields
        if (any(keyword.strip().lower() in title for keyword in keywords_lower.split()) or
            any(keyword.strip().lower() in policy_area for keyword in keywords_lower.split())):
            filtered_bills.append(bill)
            if len(filtered_bills) >= limit:
                break
    
    return filtered_bills

# --- Formatting Helpers ---

def format_bill_summary(bill: Dict[str, Any]) -> str:
    """Format a bill into a brief readable summary."""
    result = []
    
    # Basic info
    bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
    result.append(f"**{bill_id}** (Congress {bill.get('congress', 'Unknown')})")
    
    if "title" in bill:
        result.append(f"**Title:** {bill['title']}")
    
    # Latest action
    if "latestAction" in bill:
        action = bill["latestAction"]
        result.append(f"**Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
    
    # URL
    if "url" in bill:
        result.append(f"**URL:** {bill['url']}")
    
    return "\n".join(result)

def format_bill_detail(bill: Dict[str, Any]) -> str:
    """Format a bill into comprehensive detailed information."""
    result = []
    
    # Header
    bill_id = f"{bill.get('type', 'Unknown')} {bill.get('number', 'Unknown')}"
    result.append(f"# {bill_id} - Congress {bill.get('congress', 'Unknown')}")
    result.append("")
    
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
    
    # Text Versions
    if "textVersions" in bill and "count" in bill["textVersions"] and bill["textVersions"]["count"] > 0:
        result.append("**Text Versions Available:** Use get_bill_text_versions tool for text versions.")
    
    # URL
    if "url" in bill:
        result.append(f"\n**URL:** {bill['url']}")
    
    return "\n".join(result)

def format_bill_actions(actions: List[Dict[str, Any]]) -> str:
    """Format bill actions into a readable timeline."""
    if not actions:
        return "No actions found."
    
    result = ["## Legislative Actions Timeline", ""]
    
    for action in actions:
        action_date = action.get('actionDate', 'Unknown date')
        action_text = action.get('text', 'No description')
        action_type = action.get('type', '')
        
        result.append(f"**{action_date}** - {action_text}")
        if action_type:
            result.append(f"  *Type: {action_type}*")
        result.append("")
    
    return "\n".join(result)

def format_bill_text_versions(versions: List[Dict[str, Any]]) -> str:
    """Format bill text versions into a readable list."""
    if not versions:
        return "No text versions found."
    
    result = ["## Available Text Versions", ""]
    
    for version in versions:
        version_type = version.get('type', 'Unknown')
        date = version.get('date', 'Unknown date')
        
        result.append(f"**{version_type}** ({date})")
        
        if 'formats' in version:
            for format_info in version['formats']:
                format_type = format_info.get('type', 'Unknown format')
                url = format_info.get('url', 'No URL')
                result.append(f"  - {format_type}: {url}")
        
        result.append("")
    
    return "\n".join(result)

# --- Resources ---

@mcp.resource("congress://bills/latest")
async def get_latest_bills(ctx: Context) -> str:
    """
    Get the most recent bills introduced in Congress.
    
    Returns a list of the 10 most recently updated bills across all
    Congresses, sorted by update date in descending order.
    """
    data = await _fetch_bill_data(ctx, limit=10, sort="updateDate+desc")
    
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
async def get_bills_by_congress(ctx: Context, congress_num: str) -> str:
    """
    Get bills from a specific Congress.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated bills from the
    specified Congress, sorted by update date in descending order.
    """
    data = await _fetch_bill_data(ctx, congress=int(congress_num), limit=10, sort="updateDate+desc")
    
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
async def get_bills_by_type(ctx: Context, congress_num: str, bill_type: str) -> str:
    """
    Get bills from a specific Congress and bill type.
    
    Args:
        congress_num: The number of the Congress (e.g., "117")
        bill_type: The type of bill (e.g., "hr", "s")
        
    Returns a list of the 10 most recently updated bills of the specified
    type from the specified Congress, sorted by update date in descending order.
    """
    data = await _fetch_bill_data(ctx, congress=int(congress_num), bill_type=bill_type, limit=10, sort="updateDate+desc")
    
    if "error" in data:
        return f"Error retrieving bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        return f"No {bill_type.upper()} bills found for the {congress_num}th Congress."
    
    result = [f"{bill_type.upper()} bills from the {congress_num}th Congress:"]
    for bill in bills:
        result.append("\n" + format_bill_summary(bill))
    
    return "\n".join(result)

# --- Tools ---

@mcp.tool()
async def search_bills(
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
    Search for bills based on keywords with smart search strategy.
    
    This function implements a multi-tier search strategy:
    1. Direct lookup if congress/bill_type/bill_number pattern detected
    2. Targeted search with congress + bill_type for smaller dataset
    3. Broad search with keywords only for larger dataset
    
    Args:
        keywords: Keywords to search for in bill titles and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    # Check for direct bill number pattern (e.g., "hr 1", "s 2", "HR1", "S2")
    import re
    bill_pattern = re.match(r'^([a-zA-Z]+)\s*(\d+)$', keywords.strip())
    
    if bill_pattern and congress:
        # Direct lookup strategy
        detected_type = bill_pattern.group(1).lower()
        detected_number = int(bill_pattern.group(2))
        
        logger.debug(f"Direct lookup detected: {detected_type} {detected_number} in Congress {congress}")
        
        try:
            return await get_bill_details(ctx, congress, detected_type, detected_number)
        except Exception as e:
            logger.warning(f"Direct lookup failed: {e}")
            # Fall through to keyword search
    
    # Build search parameters
    params = {
        'limit': min(limit * 5, 250),  # Fetch more for better filtering
        'sort': sort
    }
    
    if from_date:
        params['fromDateTime'] = from_date
    if to_date:
        params['toDateTime'] = to_date
    
    # Smart endpoint selection based on search strategy
    if congress and bill_type:
        # Strategy 2: Targeted search (congress + bill_type)
        logger.debug(f"Targeted search: Congress {congress}, Type {bill_type}")
        data = await _fetch_bill_data(ctx, congress=congress, bill_type=bill_type, **params)
        search_scope = f"bills of type {bill_type.upper()} in the {congress}th Congress"
    elif congress:
        # Strategy 2.5: Congress-specific search
        logger.debug(f"Congress-specific search: Congress {congress}")
        data = await _fetch_bill_data(ctx, congress=congress, **params)
        search_scope = f"bills in the {congress}th Congress"
    else:
        # Strategy 3: Broad search (all bills)
        logger.debug("Broad search: All bills")
        data = await _fetch_bill_data(ctx, **params)
        search_scope = "all recent bills"
    
    if "error" in data:
        return f"Error searching bills: {data['error']}"
    
    bills = data.get("bills", [])
    if not bills:
        guidance = []
        guidance.append(f"No bills found in {search_scope}.")
        guidance.append(f"\n**Debug Info:** API returned {len(data)} keys: {list(data.keys())}")
        guidance.append("\n**Search Tips:**")
        guidance.append("• Try broader keywords or remove filters")
        guidance.append("• For specific bills, use format 'HR 1' or 'S 2' with congress number")
        guidance.append("• Use get_bill_details tool if you know the exact bill number")
        return "\n".join(guidance)
    
    logger.debug(f"Found {len(bills)} bills from API before filtering")
    
    # Filter bills by keywords
    filtered_bills = await _filter_bills_by_keywords(bills, keywords, limit)
    
    if not filtered_bills:
        guidance = []
        guidance.append(f"No bills found matching '{keywords}' in {search_scope}.")
        guidance.append(f"\n**Debug Info:** Found {len(bills)} total bills but none matched keywords")
        if bills:
            # Show sample bill titles for debugging
            sample_titles = [bill.get('title', 'No title')[:100] + "..." for bill in bills[:3]]
            guidance.append(f"**Sample titles:** {sample_titles}")
        guidance.append(f"\n**Search Scope:** Comprehensive search across:")
        guidance.append("• Bill titles and policy areas")
        guidance.append("• (Optimized for performance)")
        guidance.append(f"\n**Search Limitations:** This search is limited to {search_scope}.")
        guidance.append("**Suggestions:**")
        guidance.append("• Try different or broader keywords")
        guidance.append("• Remove congress or bill_type filters for wider search")
        guidance.append("• Use specific bill identifiers (e.g., 'HR 1') for direct lookup")
        return "\n".join(guidance)
    
    # Format results
    result = [f"## Search Results: '{keywords}' in {search_scope}"]
    result.append(f"Found {len(filtered_bills)} of {len(bills)} bills")
    result.append("**Search includes:** titles, policy areas")
    
    for i, bill in enumerate(filtered_bills, 1):
        result.append(f"### {i}. {format_bill_summary(bill)}")
        result.append("")
    
    # Add search guidance
    if len(bills) >= params['limit']:
        result.append("---")
        result.append("**Note:** Search limited to recent bills. For comprehensive results:")
        result.append("• Specify congress number for targeted search")
        result.append("• Use get_bill_details for specific bills")
        result.append("• Try more specific keywords to narrow results")
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_details(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill details: {data['error']}"
    
    bill = data.get("bill", {})
    if not bill:
        return f"No details found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    return format_bill_detail(bill)

@mcp.tool()
async def get_bill_actions(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/actions"
    data = await make_api_request(endpoint, ctx, {"limit": limit})
    
    if "error" in data:
        return f"Error retrieving bill actions: {data['error']}"
    
    actions = data.get("actions", [])
    if not actions:
        return f"No actions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    return format_bill_actions(actions)

@mcp.tool()
async def get_bill_cosponsors(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/cosponsors"
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
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/subjects"
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
async def get_bill_text_versions(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/text"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill text: {data['error']}"
    
    text_versions = data.get("textVersions", [])
    if not text_versions:
        return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    return format_bill_text_versions(text_versions)

@mcp.tool()
async def get_bill_titles(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/titles"
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
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/relatedbills"
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

@mcp.tool()
async def get_bill_amendments(
    ctx: Context,
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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/amendments"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill amendments: {data['error']}"
    
    amendments = data.get("amendments", [])
    if not amendments:
        return f"No amendments found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"## Amendments for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
    result.append("*Note: This endpoint provides basic amendment information (number, description, latest action).*")
    result.append("*For detailed amendment information including sponsors and purpose, use the dedicated amendment tools.*")
    result.append("")
    
    for i, amendment in enumerate(amendments, 1):
        amend_number = amendment.get("number", "Unknown")
        amend_type = amendment.get("type", "Unknown")
        description = amendment.get("description", "No description available")
        
        result.append(f"**{i}. Amendment {amend_number}**")
        if amend_type != "Unknown":
            result.append(f"   **Type:** {amend_type}")
        result.append(f"   **Description:** {description}")
        
        if "latestAction" in amendment:
            action = amendment["latestAction"]
            result.append(f"   **Latest Action:** {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")
        
        result.append("")
    
    return "\n".join(result)

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
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/summaries"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill summaries: {data['error']}"
    
    summaries = data.get("summaries", [])
    if not summaries:
        return f"No summaries found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"## Summaries for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
    
    for i, summary in enumerate(summaries, 1):
        action_desc = summary.get("actionDesc", "Unknown action")
        action_date = summary.get("actionDate", "Unknown date")
        text = summary.get("text", "No summary text available")
        
        result.append(f"**{i}. {action_desc}** ({action_date})")
        result.append("")
        result.append(text)
        result.append("")
        result.append("---")
        result.append("")
    
    return "\n".join(result)

@mcp.tool()
async def get_bill_committees(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get committees for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}/committees"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving bill committees: {data['error']}"
    
    committees = data.get("committees", [])
    if not committees:
        return f"No committee information found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    result = [f"## Committees for {bill_type.upper()} {bill_number} - {congress}th Congress", ""]
    
    for i, committee in enumerate(committees, 1):
        name = committee.get("name", "Unknown committee")
        chamber = committee.get("chamber", "Unknown chamber")
        
        result.append(f"**{i}. {name}** ({chamber})")
        
        # Subcommittees
        if "subcommittees" in committee and committee["subcommittees"]:
            result.append("   **Subcommittees:**")
            for subcom in committee["subcommittees"]:
                subcom_name = subcom.get("name", "Unknown subcommittee")
                result.append(f"   - {subcom_name}")
        
        result.append("")
    
    return "\n".join(result)

@mcp.tool("get_bill_text")
async def get_bill_text(
    ctx: Context,
    congress: int, 
    bill_type: str, 
    bill_number: int,
    version: str = "latest"
) -> str:
    """
    Get the text versions and URLs for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        version: Text version to retrieve ('latest', 'introduced', 'reported', or specific version code)
    """
    try:
        # First get available text versions
        data = await _fetch_bill_data(ctx, congress, bill_type, bill_number, "text")
        
        if "error" in data:
            return f"Error retrieving bill text: {data['error']}"
        
        text_versions = data.get("textVersions", [])
        if not text_versions:
            return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
        
        # Select the appropriate version
        selected_version = None
        if version == "latest":
            # Get the most recent version (first in the list)
            selected_version = text_versions[0]
        elif version == "introduced":
            # Look for introduced version
            for tv in text_versions:
                if "ih" in tv.get("type", "").lower() or "introduced" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        elif version == "reported":
            # Look for reported version
            for tv in text_versions:
                if "rh" in tv.get("type", "").lower() or "reported" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        else:
            # Look for specific version code
            for tv in text_versions:
                if version.lower() in tv.get("type", "").lower():
                    selected_version = tv
                    break
        
        if not selected_version:
            available_versions = [tv.get("type", "Unknown") for tv in text_versions]
            return f"Version '{version}' not found for {bill_type.upper()} {bill_number}. Available versions: {', '.join(available_versions)}"
        
        # Format the bill text information with direct links
        result = [
            f"# {bill_type.upper()} {bill_number} - {congress}th Congress",
            f"**Version:** {selected_version.get('type', 'Unknown')} ({selected_version.get('date', 'Unknown date')})",
            "",
            "## Available Text Formats",
            ""
        ]
        
        formats = selected_version.get("formats", [])
        if formats:
            for fmt in formats:
                format_type = fmt.get("type", "Unknown format")
                url = fmt.get("url", "No URL available")
                result.append(f"**{format_type}:** {url}")
        else:
            result.append("No text formats available for this version.")
        
        result.extend([
            "",
            "## Usage Instructions",
            "• Click on any URL above to view or download the bill text",
            "• **Formatted Text** provides the most readable version",
            "• **PDF** is best for printing or offline reading", 
            "• **XML** contains structured data for processing",
            "",
            f"**Tip:** Use `get_bill_content` to retrieve the actual bill text content, or `get_bill_text_versions` to see all available versions for {bill_type.upper()} {bill_number}."
        ])
        
        return "\n".join(result)
    
    except Exception as e:
        return f"Error retrieving bill text: {str(e)}"


@mcp.tool("get_bill_content")
async def get_bill_content(
    ctx: Context,
    congress: int, 
    bill_type: str, 
    bill_number: int,
    version: str = "latest",
    chunk_number: int = 1,
    chunk_size: int = 8000
) -> str:
    """
    Get the actual text content of a specific bill, with chunking support for large bills.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
        version: Text version to retrieve ('latest', 'introduced', 'reported', or specific version code)
        chunk_number: Chunk number to retrieve (1-based, default: 1)
        chunk_size: Size of each chunk in characters (default: 8000)
    """
    try:
        # First get available text versions
        data = await _fetch_bill_data(ctx, congress, bill_type, bill_number, "text")
        
        if "error" in data:
            return f"Error retrieving bill content: {data['error']}"
        
        text_versions = data.get("textVersions", [])
        if not text_versions:
            return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
        
        # Select the appropriate version (same logic as get_bill_text)
        selected_version = None
        if version == "latest":
            selected_version = text_versions[0]
        elif version == "introduced":
            for tv in text_versions:
                if "ih" in tv.get("type", "").lower() or "introduced" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        elif version == "reported":
            for tv in text_versions:
                if "rh" in tv.get("type", "").lower() or "reported" in tv.get("type", "").lower():
                    selected_version = tv
                    break
        else:
            for tv in text_versions:
                if version.lower() in tv.get("type", "").lower():
                    selected_version = tv
                    break
        
        if not selected_version:
            available_versions = [tv.get("type", "Unknown") for tv in text_versions]
            return f"Version '{version}' not found for {bill_type.upper()} {bill_number}. Available versions: {', '.join(available_versions)}"
        
        # Get the formatted text URL (prefer HTML format)
        text_url = None
        formats = selected_version.get("formats", [])
        for fmt in formats:
            if fmt.get("type") == "Formatted Text":
                text_url = fmt.get("url")
                break
        
        if not text_url:
            return f"No formatted text available for {bill_type.upper()} {bill_number} version '{selected_version.get('type', 'Unknown')}'."
        
        # Fetch the actual bill text content
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(text_url)
                if response.status_code != 200:
                    return f"Failed to retrieve bill content: HTTP {response.status_code}"
                
                html_content = response.text
                
                # Extract text from HTML and clean it up
                # Remove script and style elements
                html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove HTML tags but preserve some structure
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                
                # Clean up whitespace and formatting
                clean_text = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)  # Multiple newlines to double
                clean_text = re.sub(r'[ \t]+', ' ', clean_text)  # Multiple spaces to single
                clean_text = clean_text.strip()
                
                # Calculate chunking
                total_chars = len(clean_text)
                total_chunks = (total_chars + chunk_size - 1) // chunk_size  # Ceiling division
                
                if chunk_number < 1 or chunk_number > total_chunks:
                    return f"Invalid chunk number {chunk_number}. Bill has {total_chunks} chunks of {chunk_size} characters each."
                
                # Extract the requested chunk
                start_pos = (chunk_number - 1) * chunk_size
                end_pos = min(start_pos + chunk_size, total_chars)
                chunk_text = clean_text[start_pos:end_pos]
                
                # Add some overlap context if not the first chunk
                if chunk_number > 1 and start_pos > 200:
                    overlap_start = max(0, start_pos - 200)
                    overlap_text = clean_text[overlap_start:start_pos]
                    chunk_text = f"[...previous context: {overlap_text[-200:]}]\n\n{chunk_text}"
                
                result = [
                    f"# {bill_type.upper()} {bill_number} - {congress}th Congress",
                    f"**Version:** {selected_version.get('type', 'Unknown')} ({selected_version.get('date', 'Unknown date')})",
                    f"**Chunk:** {chunk_number} of {total_chunks} (characters {start_pos+1:,}-{end_pos:,} of {total_chars:,})",
                    f"**Source:** {text_url}",
                    "",
                    "## Bill Content",
                    "",
                    chunk_text
                ]
                
                if chunk_number < total_chunks:
                    result.extend([
                        "",
                        f"**Next:** Use `get_bill_content(congress={congress}, bill_type='{bill_type}', bill_number={bill_number}, version='{version}', chunk_number={chunk_number + 1})` for the next chunk."
                    ])
                
                return "\n".join(result)
                
        except Exception as e:
            return f"Error fetching bill content: {str(e)}. Direct URL: {text_url}"
    
    except Exception as e:
        return f"Error retrieving bill content: {str(e)}"

# --- Additional Resources ---

@mcp.resource("congress://bills/{congress}/{bill_type}/{bill_number}")
async def get_bill_details_resource(ctx: Context, congress: str, bill_type: str, bill_number: str) -> str:
    """
    Get detailed information about a specific bill.
    
    Args:
        congress: Congress number (e.g., "117")
        bill_type: Bill type (e.g., "hr", "s")
        bill_number: Bill number (e.g., "1")
    """
    data = await _fetch_bill_data(ctx, int(congress), bill_type, int(bill_number))
    
    if "error" in data:
        return f"Error retrieving bill details: {data['error']}"
    
    bill = data.get("bill")
    if not bill:
        return f"No details found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    return format_bill_detail(bill)

@mcp.resource("congress://bills/{congress}/{bill_type}/{bill_number}/summary")
async def get_bill_summary_resource(ctx: Context, congress: str, bill_type: str, bill_number: str) -> str:
    """
    Get summary for a specific bill.
    
    Args:
        congress: Congress number (e.g., "117")
        bill_type: Bill type (e.g., "hr", "s")
        bill_number: Bill number (e.g., "1")
    """
    data = await _fetch_bill_data(ctx, int(congress), bill_type, int(bill_number), "summaries")
    
    if "error" in data:
        return f"Error retrieving bill summary: {data['error']}"
    
    summaries = data.get("summaries", [])
    if not summaries:
        return f"No summary found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    # Return the most recent summary
    latest_summary = summaries[0]
    action_desc = latest_summary.get("actionDesc", "Summary")
    action_date = latest_summary.get("actionDate", "Unknown date")
    text = latest_summary.get("text", "No summary text available")
    
    result = [
        f"# Summary: {bill_type.upper()} {bill_number} - {congress}th Congress",
        f"**{action_desc}** ({action_date})",
        "",
        text
    ]
    
    return "\n".join(result)

@mcp.resource("congress://bills/{congress}/{bill_type}/{bill_number}/text")
async def get_bill_text_resource(ctx: Context, congress: str, bill_type: str, bill_number: str) -> str:
    """
    Get text versions for a specific bill.
    
    Args:
        congress: Congress number (e.g., "117")
        bill_type: Bill type (e.g., "hr", "s")
        bill_number: Bill number (e.g., "1")
    """
    data = await _fetch_bill_data(ctx, int(congress), bill_type, int(bill_number), "text")
    
    if "error" in data:
        return f"Error retrieving bill text: {data['error']}"
    
    text_versions = data.get("textVersions", [])
    if not text_versions:
        return f"No text versions found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
    
    return format_bill_text_versions(text_versions)
