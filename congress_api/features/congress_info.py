# congress_info.py
from typing import Dict, Any
import json

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Resources
@mcp.resource("congress://info/current")
async def get_current_congress() -> str:
    """
    Get information about the current Congress.
    
    Returns detailed information about the currently active Congress,
    including session dates, chamber information, and leadership.
    """
    ctx = mcp.get_context()
    data = await make_api_request("/congress/current", ctx)
    
    if "error" in data:
        return f"Error retrieving current Congress information: {data['error']}"
    
    congress = data.get("congress", {})
    if not congress:
        return "No information found about the current Congress."
    
    result = []
    
    # Congress number and dates
    number = congress.get("number", "Unknown")
    result.append(f"## {number}th Congress")
    
    if "startDate" in congress and "endDate" in congress:
        start_date = congress["startDate"]
        end_date = congress["endDate"]
        result.append(f"Term: {start_date} to {end_date}")
    
    # Sessions
    if "sessions" in congress and congress["sessions"]:
        result.append("\n### Sessions:")
        for session in congress["sessions"]:
            session_num = session.get("number", "Unknown")
            session_type = session.get("type", "Regular")
            session_start = session.get("startDate", "Unknown")
            session_end = session.get("endDate", "Unknown")
            
            result.append(f"- Session {session_num} ({session_type}): {session_start} to {session_end}")
    
    # Chambers
    if "chambers" in congress and congress["chambers"]:
        for chamber in congress["chambers"]:
            chamber_name = chamber.get("name", "Unknown")
            result.append(f"\n### {chamber_name}")
            
            # Leadership
            if "leadership" in chamber and chamber["leadership"]:
                result.append("Leadership:")
                for leader in chamber["leadership"]:
                    title = leader.get("title", "Unknown")
                    name = leader.get("name", "Unknown")
                    party = leader.get("party", "")
                    state = leader.get("state", "")
                    
                    party_state = ""
                    if party and state:
                        party_state = f" [{party}-{state}]"
                    elif party:
                        party_state = f" [{party}]"
                    elif state:
                        party_state = f" [{state}]"
                    
                    result.append(f"- {title}: {name}{party_state}")
            
            # Party composition
            if "partyComposition" in chamber and chamber["partyComposition"]:
                result.append("\nParty Composition:")
                for party in chamber["partyComposition"]:
                    party_name = party.get("name", "Unknown")
                    members = party.get("members", "Unknown")
                    result.append(f"- {party_name}: {members} members")
    
    return "\n".join(result)

@mcp.resource("congress://{congress_num}")
async def get_congress(congress_num: str) -> str:
    """Get information about a specific Congress by number."""
    ctx = mcp.get_context()
    data = await make_api_request(f"/congress/{congress_num}", ctx)
    
    if "error" in data:
        return f"Error retrieving information for the {congress_num}th Congress: {data['error']}"
    
    congress = data.get("congress", {})
    if not congress:
        return f"No information found for the {congress_num}th Congress."
    
    return json.dumps(congress, indent=2)
