# committees.py
from typing import Dict, List, Any, Optional
from fastmcp import Context
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
async def get_committees(ctx: Context) -> str:
    """
    Get a list of congressional committees.
    
    Returns a comprehensive list of committees in the House and Senate,
    including their names, chambers, and system codes.
    """
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
async def get_committees_by_chamber(ctx: Context, chamber: str) -> str:
    """
    Get committees for a specific chamber.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        
    Returns a list of committees in the specified chamber.
    """
    
    # Validate chamber parameter
    if chamber.lower() not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    # Make API request to get committees
    data = await make_api_request("/committee", ctx)
    
    if "error" in data:
        return f"Error retrieving committees: {data['error']}"
    
    all_committees = data.get("committees", [])
    if not all_committees:
        return f"No committees found."
    
    # Filter committees by chamber
    chamber_lower = chamber.lower()
    committees = [comm for comm in all_committees if comm.get("chamber", "").lower() == chamber_lower]
    
    if not committees:
        return f"No committees found for the {chamber.capitalize()}."
    
    result = [f"{chamber.capitalize()} Committees:"]
    for committee in committees:
        result.append("\n" + format_committee_summary(committee))
    
    return "\n".join(result)

@mcp.resource("congress://committees/{chamber}/{committee_code}")
async def get_committee_details(ctx: Context, chamber: str, committee_code: str) -> str:
    """
    Get detailed information about a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hsag", "ssap")
        
    Returns detailed information about the specified committee.
    """
    # Add temporary logging for debugging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Validate chamber parameter
    if chamber.lower() not in ["house", "senate"]:
        return f"Invalid chamber: {chamber}. Must be 'house' or 'senate'."
    
    endpoint = f"/committee/{chamber.lower()}/{committee_code}"
    committee_data = await make_api_request(endpoint, ctx)
    
    if "error" in committee_data:
        return f"Error retrieving committee: {committee_data['error']}"
    
    committee = committee_data.get("committee", {})
    if not committee:
        return f"No committee found with code {committee_code} in the {chamber.capitalize()}."
    
    # Log the raw committee data for debugging
    import logging
    logging.info(f"Raw committee data: {committee}")
    
    result = []
    
    # Committee name and code
    # Extract committee name using multiple possible locations in the response
    name = "Unknown"
    
    # Option 1: Direct name field
    if "name" in committee:
        name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                name = subcommittee.get("name", "Unknown")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        name = committee["fullName"]
        
    committee_type = committee.get("type", "Unknown")
    result.append(f"## {name}")
    result.append(f"Chamber: {chamber.capitalize()}")
    result.append(f"Committee Code: {committee_code}")
    result.append(f"Type: {committee_type}")
    
    # Add update date if available
    if "updateDate" in committee:
        result.append(f"Last Updated: {committee['updateDate']}")
        
    # Add current status if available
    if "isCurrent" in committee:
        is_current = "Yes" if committee["isCurrent"] else "No"
        result.append(f"Current Committee: {is_current}")
    
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

@mcp.resource("congress://committees/{chamber}/{committee_code}/reports")
async def get_committee_reports_resource(ctx: Context, chamber: str, committee_code: str) -> str:
    """
    Get reports for a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hspw00", "ssas00")
        
    Returns a list of reports issued by the specified committee.
    """
    
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
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Now get reports for this committee
    reports_data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}/reports", ctx)
    
    if "error" in reports_data:
        return f"Error retrieving committee reports: {reports_data['error']}"
    
    reports = reports_data.get("reports", [])
    if not reports:
        return f"No reports found for the {committee_name} committee."
    
    result = [f"Reports from the {committee_name} committee:"]
    
    for report in reports:
        citation = report.get("citation", "Unknown citation")
        congress = report.get("congress", "Unknown")
        number = report.get("number", "Unknown")
        report_type = report.get("type", "Unknown").upper()
        
        result.append(f"\n### {citation}")
        result.append(f"Congress: {congress}")
        result.append(f"Report Number: {number}")
        result.append(f"Type: {report_type}")
        
        if "updateDate" in report:
            result.append(f"Update Date: {report['updateDate']}")
        
        if "url" in report:
            result.append(f"URL: {report['url']}")
    
    return "\n".join(result)

@mcp.resource("congress://committees/{chamber}/{committee_code}/nominations")
async def get_committee_nominations_resource(ctx: Context, chamber: str, committee_code: str) -> str:
    """
    Get nominations for a specific Senate committee.
    
    Args:
        chamber: The chamber of Congress (must be "senate")
        committee_code: The committee code (e.g., "ssas00")
        
    Returns a list of nominations referred to the specified Senate committee.
    """
    
    # Validate chamber parameter
    if chamber.lower() != "senate":
        return f"Invalid chamber: {chamber}. Nominations are only available for Senate committees."
    
    # First get committee details to verify it exists and get the name
    committee_data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}", ctx)
    
    if "error" in committee_data:
        return f"Error retrieving committee: {committee_data['error']}"
    
    committee = committee_data.get("committee", {})
    if not committee:
        return f"No committee found with code {committee_code} in the Senate."
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Now get nominations for this committee
    nominations_data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}/nominations", ctx)
    
    if "error" in nominations_data:
        return f"Error retrieving committee nominations: {nominations_data['error']}"
    
    nominations = nominations_data.get("nominations", [])
    if not nominations:
        return f"No nominations found for the {committee_name} committee."
    
    result = [f"Nominations referred to the {committee_name} committee:"]
    
    for nomination in nominations:
        citation = nomination.get("citation", "Unknown citation")
        congress = nomination.get("congress", "Unknown")
        number = nomination.get("number", "Unknown")
        
        result.append(f"\n### {citation}")
        result.append(f"Congress: {congress}")
        result.append(f"Nomination Number: {number}")
        
        if "description" in nomination and nomination["description"].strip():
            result.append(f"Description: {nomination['description']}")
        
        if "latestAction" in nomination:
            action = nomination["latestAction"]
            action_text = action.get("text", "Unknown action")
            action_date = action.get("actionDate", "Unknown date")
            result.append(f"Latest Action: {action_text} ({action_date})")
        
        if "receivedDate" in nomination:
            result.append(f"Received Date: {nomination['receivedDate']}")
        
        if "url" in nomination:
            result.append(f"URL: {nomination['url']}")
    
    return "\n".join(result)

@mcp.resource("congress://committees/{chamber}/{committee_code}/communications")
async def get_committee_communications_resource(ctx: Context, chamber: str, committee_code: str) -> str:
    """
    Get communications for a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hspw00", "ssas00")
        
    Returns a list of communications referred to the specified committee.
    """
    
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
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Determine the communications endpoint based on the chamber
    if chamber.lower() == "house":
        comm_endpoint = f"/committee/{chamber.lower()}/{committee_code}/house-communication"
        comm_key = "houseCommunications"
    else:
        comm_endpoint = f"/committee/{chamber.lower()}/{committee_code}/senate-communication"
        comm_key = "senateCommunications"
    
    # Now get communications for this committee
    communications_data = await make_api_request(comm_endpoint, ctx)
    
    if "error" in communications_data:
        return f"Error retrieving committee communications: {communications_data['error']}"
    
    communications = communications_data.get(comm_key, [])
    if not communications:
        return f"No communications found for the {committee_name} committee."
    
    result = [f"Communications referred to the {committee_name} committee:"]
    
    for comm in communications:
        congress = comm.get("congress", "Unknown")
        number = comm.get("number", "Unknown")
        comm_type = ""
        if "communicationType" in comm:
            comm_type = comm["communicationType"].get("name", "Unknown")
        
        result.append(f"\n### {comm_type} {number} ({congress}th Congress)")
        
        if "referralDate" in comm:
            result.append(f"Referral Date: {comm['referralDate']}")
        
        if "updateDate" in comm:
            result.append(f"Update Date: {comm['updateDate']}")
        
        if "url" in comm:
            result.append(f"URL: {comm['url']}")
    
    return "\n".join(result)

# Tools
@mcp.tool()
async def get_committee_bills(
    ctx: Context,
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
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
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

@mcp.tool()
async def get_committee_reports(
    ctx: Context,
    chamber: str,
    committee_code: str,
    limit: int = 10
) -> str:
    """
    Get reports for a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hspw00", "ssas00")
        limit: Maximum number of reports to return (default: 10)
    """
    
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
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Now get reports for this committee
    reports_data = await make_api_request(f"/committee/{chamber.lower()}/{committee_code}/reports", ctx, {
        "limit": limit,
        "sort": "updateDate+desc"
    })
    
    if "error" in reports_data:
        return f"Error retrieving committee reports: {reports_data['error']}"
    
    reports = reports_data.get("reports", [])
    if not reports:
        return f"No reports found for the {committee_name} committee."
    
    result = [f"Reports from the {committee_name} committee:"]
    
    for report in reports:
        citation = report.get("citation", "Unknown citation")
        congress = report.get("congress", "Unknown")
        number = report.get("number", "Unknown")
        report_type = report.get("type", "Unknown").upper()
        
        result.append(f"\n### {citation}")
        result.append(f"Congress: {congress}")
        result.append(f"Report Number: {number}")
        result.append(f"Type: {report_type}")
        
        if "updateDate" in report:
            result.append(f"Update Date: {report['updateDate']}")
        
        if "url" in report:
            result.append(f"URL: {report['url']}")
    
    return "\n".join(result)

@mcp.tool()
async def get_committee_nominations(
    ctx: Context,
    committee_code: str,
    limit: int = 10
) -> str:
    """
    Get nominations for a specific Senate committee.
    
    Args:
        committee_code: The committee code (e.g., "ssas00")
        limit: Maximum number of nominations to return (default: 10)
    """
    chamber = "senate"  # Nominations are only available for Senate committees
    
    # First get committee details to verify it exists and get the name
    committee_data = await make_api_request(f"/committee/{chamber}/{committee_code}", ctx)
    
    if "error" in committee_data:
        return f"Error retrieving committee: {committee_data['error']}"
    
    committee = committee_data.get("committee", {})
    if not committee:
        return f"No committee found with code {committee_code} in the Senate."
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Now get nominations for this committee
    nominations_data = await make_api_request(f"/committee/{chamber}/{committee_code}/nominations", ctx, {
        "limit": limit
    })
    
    if "error" in nominations_data:
        return f"Error retrieving committee nominations: {nominations_data['error']}"
    
    nominations = nominations_data.get("nominations", [])
    if not nominations:
        return f"No nominations found for the {committee_name} committee."
    
    result = [f"Nominations referred to the {committee_name} committee:"]
    
    for nomination in nominations:
        citation = nomination.get("citation", "Unknown citation")
        congress = nomination.get("congress", "Unknown")
        number = nomination.get("number", "Unknown")
        
        result.append(f"\n### {citation}")
        result.append(f"Congress: {congress}")
        result.append(f"Nomination Number: {number}")
        
        if "description" in nomination and nomination["description"].strip():
            result.append(f"Description: {nomination['description']}")
        
        if "latestAction" in nomination:
            action = nomination["latestAction"]
            action_text = action.get("text", "Unknown action")
            action_date = action.get("actionDate", "Unknown date")
            result.append(f"Latest Action: {action_text} ({action_date})")
        
        if "receivedDate" in nomination:
            result.append(f"Received Date: {nomination['receivedDate']}")
        
        if "url" in nomination:
            result.append(f"URL: {nomination['url']}")
    
    return "\n".join(result)

@mcp.tool()
async def get_committee_communications(
    ctx: Context,
    chamber: str,
    committee_code: str,
    limit: int = 10
) -> str:
    """
    Get communications for a specific committee.
    
    Args:
        chamber: The chamber of Congress ("house" or "senate")
        committee_code: The committee code (e.g., "hspw00", "ssas00")
        limit: Maximum number of communications to return (default: 10)
    """
    
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
    
    # Extract committee name using multiple possible locations in the response
    committee_name = "Unknown Committee"
    
    # Option 1: Direct name field
    if "name" in committee:
        committee_name = committee["name"]
    
    # Option 2: History array with libraryOfCongressName or officialName
    elif "history" in committee and committee["history"] and len(committee["history"]) > 0:
        history_item = committee["history"][0]
        if "libraryOfCongressName" in history_item and history_item["libraryOfCongressName"]:
            committee_name = history_item["libraryOfCongressName"]
        elif "officialName" in history_item and history_item["officialName"]:
            committee_name = history_item["officialName"]
    
    # Option 3: For subcommittees, the name might be in the parent committee's subcommittees array
    elif "parent" in committee and committee["parent"] and "subcommittees" in committee["parent"]:
        for subcommittee in committee["parent"]["subcommittees"]:
            if subcommittee.get("systemCode") == committee_code:
                committee_name = subcommittee.get("name", "Unknown Committee")
                break
    
    # Option 4: Check for a 'title' field that some committee responses might have
    elif "title" in committee:
        committee_name = committee["title"]
        
    # Option 5: Check for 'fullName' field
    elif "fullName" in committee:
        committee_name = committee["fullName"]
    
    # Determine the communications endpoint based on the chamber
    if chamber.lower() == "house":
        comm_endpoint = f"/committee/{chamber.lower()}/{committee_code}/house-communication"
        comm_key = "houseCommunications"
    else:
        comm_endpoint = f"/committee/{chamber.lower()}/{committee_code}/senate-communication"
        comm_key = "senateCommunications"
    
    # Now get communications for this committee
    communications_data = await make_api_request(comm_endpoint, ctx, {
        "limit": limit
    })
    
    if "error" in communications_data:
        return f"Error retrieving committee communications: {communications_data['error']}"
    
    communications = communications_data.get(comm_key, [])
    if not communications:
        return f"No communications found for the {committee_name} committee."
    
    result = [f"Communications referred to the {committee_name} committee:"]
    
    for comm in communications:
        congress = comm.get("congress", "Unknown")
        number = comm.get("number", "Unknown")
        comm_type = ""
        if "communicationType" in comm:
            comm_type = comm["communicationType"].get("name", "Unknown")
        
        result.append(f"\n### {comm_type} {number} ({congress}th Congress)")
        
        if "referralDate" in comm:
            result.append(f"Referral Date: {comm['referralDate']}")
        
        if "updateDate" in comm:
            result.append(f"Update Date: {comm['updateDate']}")
        
        if "url" in comm:
            result.append(f"URL: {comm['url']}")
    
    return "\n".join(result)

from typing import Optional

@mcp.tool()
async def search_committees(
    ctx: Context,
    keywords: str,
    chamber: Optional[str] = None,
    congress: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search for committees based on keywords.
    
    Args:
        keywords: Keywords to search for in committee information
        chamber: Optional chamber of Congress ("house", "senate", or "joint")
        congress: Optional Congress number (e.g., 117)
        limit: Maximum number of results to return (default: 10)
    """
    
    # Determine initial fetch limit
    fetch_limit = limit
    if not chamber and not congress:
        # If searching all committees for keywords, fetch a larger initial set
        fetch_limit = 200 # Or API max, e.g., 250

    # Build query parameters
    params = {
        "limit": fetch_limit, # Use the potentially larger fetch_limit here
        "sort": "updateDate+desc"
    }
    
    # Add optional parameters if provided
    if chamber:
        if chamber.lower() not in ["house", "senate", "joint"]:
            return f"Invalid chamber: {chamber}. Must be 'house', 'senate', or 'joint'."
        params["chamber"] = chamber.lower()
    
    # Determine the endpoint based on provided parameters
    if congress and chamber:
        endpoint = f"/committee/{congress}/{chamber.lower()}"
    elif congress:
        endpoint = f"/committee/{congress}"
    elif chamber:
        endpoint = f"/committee" # Chamber is already in params
    else:
        endpoint = f"/committee"
    
    import sys # Required for print to stderr
    print(f"DEBUG search_committees: Requesting endpoint='{endpoint}', params={params}", file=sys.stderr)
    
    # Make the API request
    committees_data = await make_api_request(endpoint, ctx, params)
    
    if "error" in committees_data:
        return f"Error searching committees: {committees_data['error']}"
    
    raw_committees = committees_data.get("committees", [])
    print(f"DEBUG search_committees: API returned {len(raw_committees)} committees before filtering.", file=sys.stderr)
    if raw_committees:
        sample_names = [c.get('name', 'N/A') for c in raw_committees[:5]] # Show 5 samples
        print(f"DEBUG search_committees: Sample names from API: {sample_names}", file=sys.stderr)

    committees_to_filter = raw_committees
    
    # Filter by keywords
    if keywords:
        filtered_committees = []
        keywords_lower = keywords.lower()
        
        for committee in committees_to_filter:
            name = committee.get("name", "").lower()
            # Consider adding other descriptive fields if 'name' alone is insufficient
            # For now, focusing on 'name' as the primary search field for keywords.
            if keywords_lower in name:
                filtered_committees.append(committee)
        
        committees = filtered_committees
    else: # If no keywords, use all committees returned (respecting fetch_limit)
        committees = committees_to_filter

    print(f"DEBUG search_committees: {len(committees)} committees after filtering by keywords '{keywords}'.", file=sys.stderr)

    if not committees:
        return f"No committees found matching your search criteria."
    
    # Limit the number of results *after* filtering
    committees = committees[:limit]
    
    result = [f"Found {len(committees)} committees matching your search:"]
    
    for committee in committees:
        result.append("\n" + format_committee_summary(committee))
    
    return "\n".join(result)
