# members.py
from typing import Dict, List, Any, Optional
import json
from fastmcp import Context
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
    if "partyName" in member and member["partyName"]:
        party = member["partyName"]
    elif "party" in member and member["party"]:
        party = member["party"]
    # Map party codes to full names if needed
    if party == "D" or party.lower() == "d":
        party = "Democratic"
    elif party == "R" or party.lower() == "r":
        party = "Republican"
    elif party == "I" or party.lower() == "i":
        party = "Independent"
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
async def get_current_members(ctx: Context) -> str:
    """
    Get a list of current members of Congress.
    
    Returns a sample of 20 current members from both chambers of Congress,
    including their biographical information and contact details.
    """
    data = await make_api_request("/member", ctx, {"limit": 20, "currentMember": "true"})
    
    if "error" in data:
        return f"Error retrieving members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return "No members found."
    
    result = ["Current members of Congress:"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.resource("congress://members/all")
async def get_all_members(ctx: Context) -> str:
    """
    Get a list of congressional members.
    
    Returns a list of congressional members with basic information about each,
    including their biographical information and contact details.
    """
    data = await make_api_request("/member", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return "No members found."
    
    result = ["Members of Congress:"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.resource("congress://members/{bioguide_id}")
async def get_member_details(ctx: Context, bioguide_id: str) -> str:
    """
    Get detailed information about a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "A000055")
        
    Returns comprehensive information about the specified member,
    including biographical data, terms of service, and committee assignments.
    """
    data = await make_api_request(f"/member/{bioguide_id}", ctx)
    
    if "error" in data:
        return f"Error retrieving member details: {data['error']}"
    
    member = data.get("member", {})
    if not member:
        return f"No member found with Bioguide ID: {bioguide_id}"
    
    # Get detailed information
    result = []
    
    # Handle name field
    name_str = "Unknown"
    # Prioritize directOrderName and invertedOrderName if they exist
    if "directOrderName" in member and member["directOrderName"]:
        name_str = member["directOrderName"]
    elif "invertedOrderName" in member and member["invertedOrderName"]:
        name_str = member["invertedOrderName"]
        # If using invertedOrderName, it might be "Last, First". Reformat.
        if "," in name_str:
            parts = name_str.split(",", 1)
            if len(parts) == 2:
                name_str = f"{parts[1].strip()} {parts[0].strip()}"
    elif "name" in member:  # Fallback to existing logic
        if isinstance(member["name"], str):
            name_str = member["name"]
        elif isinstance(member["name"], dict):
            first = member["name"].get("firstName", "")
            middle = member["name"].get("middleName", "")
            last = member["name"].get("lastName", "")
            name_str = f"{first} {middle} {last}".strip()
            name_str = " ".join(name_str.split())  # Clean up extra spaces

    result.append(f"## {name_str if name_str else 'Unknown'}")
    result.append(f"Bioguide ID: {bioguide_id}") # Use function argument for robustness
    
    # Handle party information - try multiple possible fields
    party = "Unknown"
    
    # First check partyHistory if available
    if "partyHistory" in member and isinstance(member["partyHistory"], list) and member["partyHistory"]:
        # Get the most recent party (first in the list)
        party_history = member["partyHistory"][0]
        if isinstance(party_history, dict):
            if "partyName" in party_history:
                party = party_history["partyName"]
            elif "partyAbbreviation" in party_history:
                party_abbr = party_history["partyAbbreviation"]
                # Map abbreviation to full name
                if party_abbr == "D":
                    party = "Democratic"
                elif party_abbr == "R":
                    party = "Republican"
                elif party_abbr == "I":
                    party = "Independent"
                else:
                    party = party_abbr
    
    # If party is still unknown, check other fields
    if party == "Unknown":
        if "partyName" in member and member["partyName"]:
            party = member["partyName"]
        elif "party" in member and member["party"]:
            party = member["party"]
        
        # Map party codes to full names if needed
        if party == "D" or party.lower() == "d":
            party = "Democratic"
        elif party == "R" or party.lower() == "r":
            party = "Republican"
        elif party == "I" or party.lower() == "i":
            party = "Independent"
    
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
            # API returns terms chronologically (earliest first).
            earliest_term = terms[0]
            latest_term = terms[-1]
            
            chamber = latest_term.get('chamber', 'Unknown') # Chamber from the latest term
            result.append(f"Chamber: {chamber}")

            service_start_year = earliest_term.get('startYear', 'Unknown')
            # Get endYear from the latest term; if it's null, member is 'Present' for that term
            latest_term_end_year_val = latest_term.get('endYear') 
            service_end_year_display = latest_term_end_year_val if latest_term_end_year_val is not None else "Present"

            if service_start_year != 'Unknown':
                if len(terms) == 1:
                    # For a single term, display that term's start and end
                    single_term_start = latest_term.get('startYear', 'Unknown') # Should be earliest_term or latest_term, same for single term
                    single_term_end_val = latest_term.get('endYear')
                    single_term_end_display = single_term_end_val if single_term_end_val is not None else "Present"
                    result.append(f"Term: {single_term_start} - {single_term_end_display}")
                else:
                    result.append(f"Service Span: {service_start_year} - {service_end_year_display}")
            else:
                result.append("Service Span: Unknown")

            # Display individual terms if needed (optional, can be verbose)
            # result.append("\n## Terms of Service")
            # for term_item in terms:
            #     term_start = term_item.get('startYear', 'N/A')
            #     term_end = term_item.get('endYear', 'Present')
            #     term_chamber = term_item.get('chamber', 'N/A')
            #     term_congress = term_item.get('congress', 'N/A')
            #     term_district = term_item.get('district', '')
            #     district_str = f", District {term_district}" if term_district else ""
            #     result.append(f"- {term_congress}th Congress ({term_start}-{term_end}): {term_chamber}{district_str}, {term_item.get('stateCode', '')}")
        else:
            result.append("Chamber: Unknown")
            result.append("Service Span: No term data available")
    else:
        result.append("Chamber: Unknown")
        result.append("Service Span: No term data available")

    # Sponsored legislation count
    sponsored_legislation = member.get("sponsoredLegislation", {})
    count = sponsored_legislation.get("count", 0)
    result.append("\n## Sponsored Legislation")
    result.append(f"Total bills sponsored: {count}")
    result.append("Use the search_bills tool with this member's name to find specific legislation.")

    # Cosponsored legislation count
    # cosponsored_legislation = member.get("cosponsoredLegislation", {})
    # count_cosponsored = cosponsored_legislation.get("count", 0)
    # result.append(f"Total bills cosponsored: {count_cosponsored}")

    # Committee assignments (simplified)
    # committees = member.get("committeeAssignments", [])
    # if committees:
    #     result.append("\n## Committee Assignments (Current)")
    #     # The API might return all assignments, need to filter for current if possible
    #     # For simplicity, listing first few or based on a flag if available
    #     for committee in committees[:3]: # Limiting to 3 for brevity
    #         if isinstance(committee, dict):
    #            result.append(f"- {committee.get('name', 'N/A')}")

    # Biographical Information
    result.append("\n## Biographical Information")
    # Add other relevant biographical details if available and desired
    # For example, birth date, education, etc.
    # result.append(f"Birth Date: {member.get('birthDate', 'N/A')}")
    official_url = member.get('officialWebsiteUrl', 'No URL available')
    result.append(f"Official Website: {official_url}")

    return "\n".join(result)

@mcp.resource("congress://members/{bioguide_id}/sponsored")
async def get_member_sponsored_legislation(ctx: Context, bioguide_id: str) -> str:
    """
    Get legislation sponsored by a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "L000174")
        
    Returns a list of legislation sponsored by the specified member.
    """
    data = await make_api_request(f"/member/{bioguide_id}/sponsored-legislation", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving sponsored legislation: {data['error']}"
    
    legislation = data.get("sponsoredLegislation", [])
    if not legislation:
        return f"No sponsored legislation found for member with Bioguide ID: {bioguide_id}"
    
    result = [f"# Legislation Sponsored by Member {bioguide_id}"]
    
    for bill in legislation:
        congress = bill.get("congress", "Unknown")
        bill_type = bill.get("type", "Unknown")
        bill_number = bill.get("number", "Unknown")
        title = bill.get("title", "No title available")
        
        result.append(f"\n## {bill_type} {bill_number} ({congress}th Congress)")
        result.append(f"**Title**: {title}")
        
        if "introducedDate" in bill:
            result.append(f"**Introduced**: {bill['introducedDate']}")
        
        if "latestAction" in bill and isinstance(bill["latestAction"], dict):
            action_date = bill["latestAction"].get("actionDate", "Unknown")
            action_text = bill["latestAction"].get("text", "Unknown")
            result.append(f"**Latest Action** ({action_date}): {action_text}")
    
    return "\n".join(result)

@mcp.resource("congress://members/{bioguide_id}/cosponsored")
async def get_member_cosponsored_legislation(ctx: Context, bioguide_id: str) -> str:
    """
    Get legislation cosponsored by a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "L000174")
        
    Returns a list of legislation cosponsored by the specified member.
    """
    data = await make_api_request(f"/member/{bioguide_id}/cosponsored-legislation", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving cosponsored legislation: {data['error']}"
    
    legislation = data.get("cosponsoredLegislation", [])
    if not legislation:
        return f"No cosponsored legislation found for member with Bioguide ID: {bioguide_id}"
    
    result = [f"# Legislation Cosponsored by Member {bioguide_id}"]
    
    for bill in legislation:
        congress = bill.get("congress", "Unknown")
        bill_type = bill.get("type", "Unknown")
        bill_number = bill.get("number", "Unknown")
        title = bill.get("title", "No title available")
        
        result.append(f"\n## {bill_type} {bill_number} ({congress}th Congress)")
        result.append(f"**Title**: {title}")
        
        if "introducedDate" in bill:
            result.append(f"**Introduced**: {bill['introducedDate']}")
        
        if "latestAction" in bill and isinstance(bill["latestAction"], dict):
            action_date = bill["latestAction"].get("actionDate", "Unknown")
            action_text = bill["latestAction"].get("text", "Unknown")
            result.append(f"**Latest Action** ({action_date}): {action_text}")
    
    return "\n".join(result)

@mcp.resource("congress://members/congress/{congress}")
async def get_members_by_congress(ctx: Context, congress: str) -> str:
    """
    Get members of a specific Congress.
    
    Args:
        congress: The Congress number (e.g., "118")
        
    Returns a list of members who served in the specified Congress.
    """
    data = await make_api_request(f"/member/congress/{congress}", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving members for Congress {congress}: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return f"No members found for the {congress}th Congress."
    
    result = [f"# Members of the {congress}th Congress"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.resource("congress://members/state/{state_code}")
async def get_members_by_state(ctx: Context, state_code: str) -> str:
    """
    Get members from a specific state.
    
    Args:
        state_code: The two-letter state code (e.g., "MI" for Michigan)
        
    Returns a list of members who represent the specified state.
    """
    data = await make_api_request(f"/member/{state_code}", ctx, {"currentMember": "true"})
    
    if "error" in data:
        return f"Error retrieving members for state {state_code}: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return f"No members found for state {state_code}."
    
    result = [f"# Members from {state_code}"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

@mcp.resource("congress://members/state/{state_code}/district/{district}")
async def get_members_by_district(ctx: Context, state_code: str, district: str) -> str:
    """
    Get members from a specific congressional district.
    
    Args:
        state_code: The two-letter state code (e.g., "MI" for Michigan)
        district: The district number (e.g., "10")
        
    Returns a list of members who represent the specified district.
    """
    data = await make_api_request(f"/member/{state_code}/{district}", ctx, {"currentMember": "true"})
    
    if "error" in data:
        return f"Error retrieving members for {state_code}-{district}: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return f"No members found for district {state_code}-{district}."
    
    result = [f"# Members from {state_code} District {district}"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

# Tools
@mcp.tool()
async def search_members(
    ctx: Context,
    name: Optional[str] = None,
    state: Optional[str] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    congress: Optional[int] = None,
    current_member: bool = True,
    limit: int = 10,
    district: Optional[int] = None
) -> str:
    """
    Search for members of Congress based on various criteria.
    
    Args:
        name: Optional name to search for
        state: Optional state abbreviation (e.g., 'CA', 'TX')
        party: Optional party affiliation ('D', 'R', 'I')
        chamber: Optional chamber ('house' or 'senate')
        congress: Optional Congress number (e.g., 117)
        current_member: Whether to only include current members (default: True)
        limit: Maximum number of results to return (default: 10)
        district: Optional district number for the district (e.g., 10)
    """
    
    try:
        # Determine which API endpoint to use based on the provided parameters
        
        # Case 1: Search by congress, state, and district
        if congress and state and district:
            endpoint = f"/member/congress/{congress}/{state}/{district}"
            params = {"currentMember": str(current_member).lower()}
            
            data = await make_api_request(endpoint, ctx, params)
            if "error" in data:
                return f"Error retrieving members: {data['error']}"
            
            members = data.get("members", [])
            if not members:
                return f"No members found for Congress {congress}, state {state}, district {district}."
            
            # Apply additional filters client-side if needed
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return f"No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Members from Congress {congress}, state {state}, district {district}:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
        
        # Case 2: Search by state and district
        elif state and district:
            endpoint = f"/member/{state}/{district}"
            params = {"currentMember": str(current_member).lower()}
            
            data = await make_api_request(endpoint, ctx, params)
            if "error" in data:
                return f"Error retrieving members: {data['error']}"
            
            members = data.get("members", [])
            if not members:
                return f"No members found for state {state}, district {district}."
            
            # Apply additional filters client-side if needed
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                # Filter by congress if specified
                if congress and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list):
                        in_congress = False
                        for term in terms:
                            if isinstance(term, dict) and term.get('congress') == str(congress):
                                in_congress = True
                                break
                        if not in_congress:
                            include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return f"No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Members from state {state}, district {district}:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
        
        # Case 3: Search by congress and state
        elif congress and state:
            endpoint = f"/member/congress/{congress}/{state}"
            params = {"currentMember": str(current_member).lower()}
            
            try:
                data = await make_api_request(endpoint, ctx, params)
                if "error" in data and "404" in str(data["error"]):
                    # Endpoint might not exist, fall back to congress endpoint and filter by state
                    data = await make_api_request(f"/member/congress/{congress}", ctx, 
                                                {"currentMember": str(current_member).lower(), "limit": 250})
                    
                    members = data.get("members", [])
                    # Filter by state
                    members = [m for m in members if m.get("state", "").lower() == state.lower()]
                else:
                    members = data.get("members", [])
            except Exception:
                # Fall back to congress endpoint and filter by state
                data = await make_api_request(f"/member/congress/{congress}", ctx, 
                                            {"currentMember": str(current_member).lower(), "limit": 250})
                
                members = data.get("members", [])
                # Filter by state
                members = [m for m in members if m.get("state", "").lower() == state.lower()]
            
            if not members:
                return f"No members found for Congress {congress}, state {state}."
            
            # Apply additional filters client-side if needed
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return f"No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Members from Congress {congress}, state {state}:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
        
        # Case 4: Search by congress
        elif congress:
            endpoint = f"/member/congress/{congress}"
            params = {"currentMember": str(current_member).lower()}
            
            data = await make_api_request(endpoint, ctx, params)
            if "error" in data:
                return f"Error retrieving members: {data['error']}"
            
            members = data.get("members", [])
            if not members:
                return f"No members found for Congress {congress}."
            
            # Apply additional filters client-side if needed
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by state if specified
                if state and include:
                    if state.lower() != member.get("state", "").lower():
                        include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return f"No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Members from Congress {congress}:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
        
        # Case 5: Search by state
        elif state:
            endpoint = f"/member/{state}"
            params = {"currentMember": str(current_member).lower()}
            
            data = await make_api_request(endpoint, ctx, params)
            if "error" in data:
                return f"Error retrieving members: {data['error']}"
            
            members = data.get("members", [])
            if not members:
                return f"No members found for state {state}."
            
            # Apply additional filters client-side if needed
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                # Filter by congress if specified
                if congress and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list):
                        in_congress = False
                        for term in terms:
                            if isinstance(term, dict) and term.get('congress') == str(congress):
                                in_congress = True
                                break
                        if not in_congress:
                            include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return f"No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Members from state {state}:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
        
        # Case 6: General search using /member endpoint with client-side filtering
        else:
            # Use the /member endpoint with supported parameters
            params = {
                "limit": 250,  # Get more results for filtering
                "currentMember": str(current_member).lower()
            }
            
            data = await make_api_request("/member", ctx, params)
            if "error" in data:
                return f"Error searching members: {data['error']}"
            
            members = data.get("members", [])
            if not members:
                return "No members found."
            
            # Apply filters client-side
            filtered_members = []
            for member in members:
                include = True
                
                # Filter by name if specified
                if name and name.lower() not in str(member.get("name", "")).lower():
                    include = False
                
                # Filter by state if specified
                if state and include:
                    if state.lower() != member.get("state", "").lower():
                        include = False
                
                # Filter by party if specified
                if party and include:
                    member_party = member.get("partyName", "").lower()
                    if party.lower() == "d" and "democratic" not in member_party:
                        include = False
                    elif party.lower() == "r" and "republican" not in member_party:
                        include = False
                    elif party.lower() == "i" and "independent" not in member_party:
                        include = False
                
                # Filter by chamber if specified
                if chamber and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list) and len(terms) > 0:
                        latest_term = terms[0]
                        if isinstance(latest_term, dict):
                            member_chamber = latest_term.get('chamber', '').lower()
                            if chamber.lower() != member_chamber:
                                include = False
                
                # Filter by congress if specified
                if congress and include:
                    terms = member.get("terms", {})
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    
                    if terms and isinstance(terms, list):
                        in_congress = False
                        for term in terms:
                            if isinstance(term, dict) and term.get('congress') == str(congress):
                                in_congress = True
                                break
                        if not in_congress:
                            include = False
                
                if include:
                    filtered_members.append(member)
            
            if not filtered_members:
                return "No members found matching the specified criteria."
            
            # Limit results
            filtered_members = filtered_members[:limit]
            
            result = [f"Found {len(filtered_members)} members of Congress:"]
            for member in filtered_members:
                result.append("\n" + format_member_summary(member))
            
            return "\n".join(result)
    
    except Exception as e:
        return f"Error searching members: {str(e)}"
        
async def get_member_info(ctx: Context, bioguide_id: str) -> str:
    """
    Get detailed information about a member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member
    """
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
@mcp.tool()
async def get_members_by_congress_state_district(
    ctx: Context,
    congress: int,
    state_code: str,
    district: Optional[int] = None,
    current_member: bool = True
) -> str:
    """
    Get members filtered by congress, state and optionally district.
    
    Args:
        congress: The Congress number (e.g., 118)
        state_code: The two letter identifier for the state (e.g., 'MI' for Michigan)
        district: Optional district number for the district (e.g., 10)
        current_member: Whether to only include current members (default: True)
    """
    
    # Build the endpoint based on parameters
    if district is not None:
        endpoint = f"/member/congress/{congress}/{state_code}/{district}"
    else:
        endpoint = f"/member/{state_code}"
        
    # Build parameters
    params = {"currentMember": str(current_member).lower()}
    
    # Make the API request
    data = await make_api_request(endpoint, ctx, params)
    
    if "error" in data:
        if district is not None:
            return f"Error retrieving members for Congress {congress}, state {state_code}, district {district}: {data['error']}"
        else:
            return f"Error retrieving members for state {state_code}: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        if district is not None:
            return f"No members found for Congress {congress}, state {state_code}, district {district}."
        else:
            return f"No members found for state {state_code}."
    
    # Format the result
    if district is not None:
        result = [f"# Members from {state_code} District {district} in the {congress}th Congress"]
    else:
        result = [f"# Members from {state_code} in the {congress}th Congress"]
    
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)
