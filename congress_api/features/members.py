# members.py
from typing import Dict, List, Any, Optional
import json
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import DefensiveAPIWrapper, safe_members_request
from ..core.exceptions import CommonErrors, format_error_response, APIErrorResponse
from ..core.response_utils import ResponseProcessor
import logging

logger = logging.getLogger(__name__)

# Initialize framework components
validator = ParameterValidator()
api_wrapper = DefensiveAPIWrapper()
response_processor = ResponseProcessor()

# Resources (Static data only - no user parameters)
@mcp.resource("congress://members/current")
async def get_current_members(ctx: Context) -> str:
    """
    Get a list of current members of Congress.
    
    Returns a sample of 20 current members from both chambers of Congress,
    including their biographical information and contact details.
    """
    data = await safe_members_request("/member", ctx, {"limit": 20, "currentMember": "true"})
    
    if "error" in data:
        return f"Error retrieving members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return "No current members found."
    
    result = ["# Current Members of Congress (Sample)"]
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
    data = await safe_members_request("/member", ctx, {"limit": 20})
    
    if "error" in data:
        return f"Error retrieving members: {data['error']}"
    
    members = data.get("members", [])
    if not members:
        return "No members found."
    
    result = ["# Congressional Members (Sample)"]
    for member in members:
        result.append("\n" + format_member_summary(member))
    
    return "\n".join(result)

# Tools (Interactive functions with parameters)
async def get_member_details(ctx: Context, bioguide_id: str) -> str:
    """
    Get detailed information about a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "A000055")
        
    Returns comprehensive information about the specified member,
    including biographical data, terms of service, and committee assignments.
    """
    try:
        # Validate bioguide_id parameter
        if not bioguide_id or not isinstance(bioguide_id, str):
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID must be a non-empty string (e.g., 'A000055')"
            ))
        
        bioguide_id = bioguide_id.strip().upper()
        if not bioguide_id:
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID cannot be empty"
            ))
        
        data = await safe_members_request(f"/member/{bioguide_id}", ctx, {})
        
        if "error" in data:
            if "404" in str(data["error"]):
                return format_error_response(CommonErrors.data_not_found(
                    resource_type="Member", identifier=bioguide_id
                ))
            return format_error_response(CommonErrors.api_server_error(f"/member/{bioguide_id}", message=str(data["error"])))
        
        member = data.get("member", {})
        if not member:
            return format_error_response(CommonErrors.data_not_found(
                resource_type="Member", identifier=bioguide_id
            ))
        
        # Format detailed member information
        result = [format_member_summary(member)]
        
        # Add detailed biographical information
        result.append("\n## Detailed Information")
        
        # Terms of service
        if "terms" in member:
            terms = member["terms"]
            if isinstance(terms, dict) and "item" in terms:
                terms = terms["item"]
            
            if terms and isinstance(terms, list):
                result.append("\n### Terms of Service")
                for i, term in enumerate(terms[:5]):  # Show up to 5 most recent terms
                    if isinstance(term, dict):
                        congress = term.get("congress", "Unknown")
                        chamber = term.get("chamber", "Unknown")
                        start_year = term.get("startYear", "Unknown")
                        end_year = term.get("endYear", "Unknown")
                        result.append(f"{i+1}. Congress {congress} ({chamber}): {start_year}-{end_year}")
        
        # Committee assignments
        if "committeeAssignments" in member and member["committeeAssignments"]:
            committees = member["committeeAssignments"]
            
            if isinstance(committees, dict) and "item" in committees:
                committees = committees["item"]
            
            if committees and isinstance(committees, list):
                result.append("\n### Committee Assignments")
                for committee in committees:
                    name = committee.get("name", "Unknown committee")
                    code = committee.get("systemCode", "")
                    chamber = committee.get("chamber", "")
                    result.append(f"- {name} ({chamber}, {code})")
        
        # Sponsored legislation count
        if "sponsoredLegislation" in member and "count" in member["sponsoredLegislation"]:
            count = member["sponsoredLegislation"]["count"]
            result.append(f"\n### Legislative Activity")
            result.append(f"Total bills sponsored: {count}")
            result.append("Use get_member_sponsored_legislation to see specific bills.")
        
        # Contact and social media information
        result.append("\n### Contact Information")
        if "officialWebsiteUrl" in member:
            result.append(f"Official Website: {member['officialWebsiteUrl']}")
        if "twitterAccount" in member:
            result.append(f"Twitter: @{member['twitterAccount']}")
        if "youtubeAccount" in member:
            result.append(f"YouTube: {member['youtubeAccount']}")
        if "facebookAccount" in member:
            result.append(f"Facebook: {member['facebookAccount']}")
        
        # Additional biographical details
        if "birthDate" in member:
            result.append(f"Birth Date: {member['birthDate']}")
        if "deathDate" in member:
            result.append(f"Death Date: {member['deathDate']}")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_member_details: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

async def get_member_sponsored_legislation(ctx: Context, bioguide_id: str) -> str:
    """
    Get legislation sponsored by a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "L000174")
        
    Returns a list of legislation sponsored by the specified member.
    """
    try:
        # Validate bioguide_id parameter
        if not bioguide_id or not isinstance(bioguide_id, str):
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID must be a non-empty string"
            ))
        
        bioguide_id = bioguide_id.strip().upper()
        if not bioguide_id:
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID cannot be empty"
            ))
        
        data = await safe_members_request(f"/member/{bioguide_id}/sponsored-legislation", ctx, {"limit": 20})
        
        if "error" in data:
            if "404" in str(data["error"]):
                return format_error_response(CommonErrors.data_not_found(
                    resource_type="Member", identifier=bioguide_id
                ))
            return format_error_response(CommonErrors.api_server_error(f"/member/{bioguide_id}/sponsored-legislation", message=str(data["error"])))
        
        legislation = data.get("sponsoredLegislation", [])
        if not legislation:
            return f"No sponsored legislation found for member {bioguide_id}."
        
        # Process and deduplicate results
        if isinstance(legislation, list):
            legislation = response_processor.deduplicate_results(
                legislation, 
                key_fields=["congress", "type", "number"]
            )
        
        result = [f"# Sponsored Legislation for Member {bioguide_id}"]
        result.append(f"Found {len(legislation)} bills:")
        
        for bill in legislation:
            congress = bill.get("congress", "Unknown")
            bill_type = bill.get("type", "Unknown") or "Unknown"
            number = bill.get("number", "Unknown")
            title = bill.get("title", "No title available")
            
            # Ensure bill_type is not None before calling upper()
            bill_type_display = bill_type.upper() if bill_type and bill_type != "Unknown" else "UNKNOWN"
            
            result.append(f"\n## {bill_type_display} {number} (Congress {congress})")
            result.append(f"{title}")
            
            if "url" in bill:
                result.append(f"[View Details]({bill['url']})")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_member_sponsored_legislation: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

async def get_member_cosponsored_legislation(ctx: Context, bioguide_id: str) -> str:
    """
    Get legislation cosponsored by a specific member of Congress.
    
    Args:
        bioguide_id: The Bioguide ID for the member (e.g., "L000174")
        
    Returns a list of legislation cosponsored by the specified member.
    """
    try:
        # Validate bioguide_id parameter
        if not bioguide_id or not isinstance(bioguide_id, str):
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID must be a non-empty string"
            ))
        
        bioguide_id = bioguide_id.strip().upper()
        if not bioguide_id:
            return format_error_response(CommonErrors.invalid_parameter(
                "bioguide_id", bioguide_id, "Bioguide ID cannot be empty"
            ))
        
        data = await safe_members_request(f"/member/{bioguide_id}/cosponsored-legislation", ctx, {"limit": 20})
        
        if "error" in data:
            if "404" in str(data["error"]):
                return format_error_response(CommonErrors.data_not_found(
                    resource_type="Member", identifier=bioguide_id
                ))
            return format_error_response(CommonErrors.api_server_error(f"/member/{bioguide_id}/cosponsored-legislation", message=str(data["error"])))
        
        legislation = data.get("cosponsoredLegislation", [])
        if not legislation:
            return f"No cosponsored legislation found for member {bioguide_id}."
        
        # Process and deduplicate results
        if isinstance(legislation, list):
            legislation = response_processor.deduplicate_results(
                legislation, 
                key_fields=["congress", "type", "number"]
            )
        
        result = [f"# Cosponsored Legislation for Member {bioguide_id}"]
        result.append(f"Found {len(legislation)} bills:")
        
        for bill in legislation:
            congress = bill.get("congress", "Unknown")
            bill_type = bill.get("type", "Unknown") or "Unknown"
            number = bill.get("number", "Unknown")
            title = bill.get("title", "No title available")
            
            # Ensure bill_type is not None before calling upper()
            bill_type_display = bill_type.upper() if bill_type and bill_type != "Unknown" else "UNKNOWN"
            
            result.append(f"\n## {bill_type_display} {number} (Congress {congress})")
            result.append(f"{title}")
            
            if "url" in bill:
                result.append(f"[View Details]({bill['url']})")
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_member_cosponsored_legislation: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

async def get_members_by_congress(ctx: Context, congress: int) -> str:
    """
    Get members of a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 118)
        
    Returns a list of members who served in the specified Congress.
    """
    try:
        # Validate congress parameter
        congress_validation = validator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            ))
        
        data = await safe_members_request(f"/member/congress/{congress}", ctx, {"limit": 20})
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving members for Congress {congress}: {data['error']}"))
        
        members = data.get("members", [])
        if not members:
            return f"No members found for Congress {congress}."
        
        # Process and deduplicate results
        members = response_processor.deduplicate_results(
            members, 
            key_fields=["bioguideId"]
        )
        
        result = [f"# Members of the {congress}th Congress"]
        result.append(f"Found {len(members)} members:")
        
        for member in members:
            result.append("\n" + format_member_summary(member))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_members_by_congress: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

async def get_members_by_state(ctx: Context, state_code: str) -> str:
    """
    Get members from a specific state.
    
    Args:
        state_code: The two-letter state code (e.g., "MI" for Michigan)
        
    Returns a list of members who represent the specified state.
    """
    try:
        # Validate state_code parameter
        state_validation = validator.validate_state_code(state_code)
        if not state_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "state_code", state_code, state_validation.error_message
            ))
        
        state_code = state_validation.sanitized_value
        
        data = await safe_members_request(f"/member/{state_code}", ctx, {"currentMember": "true"})
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving members for state {state_code}: {data['error']}"))
        
        members = data.get("members", [])
        if not members:
            return f"No members found for state {state_code}."
        
        # Process and deduplicate results
        members = response_processor.deduplicate_results(
            members, 
            key_fields=["bioguideId"]
        )
        
        result = [f"# Members from {state_code}"]
        result.append(f"Found {len(members)} current members:")
        
        for member in members:
            result.append("\n" + format_member_summary(member))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_members_by_state: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

async def get_members_by_district(ctx: Context, state_code: str, district: int) -> str:
    """
    Get members from a specific congressional district.
    
    Args:
        state_code: The two-letter state code (e.g., "MI" for Michigan)
        district: The district number (e.g., 10)
        
    Returns a list of members who represent the specified district.
    """
    try:
        # Validate state_code parameter
        state_validation = validator.validate_state_code(state_code)
        if not state_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "state_code", state_code, state_validation.error_message
            ))
        
        state_code = state_validation.sanitized_value
        
        # Validate district parameter
        if not isinstance(district, int) or district < 1:
            return format_error_response(CommonErrors.invalid_parameter(
                "district", district, "District must be a positive integer (e.g., 1, 2, 10)"
            ))
        
        data = await safe_members_request(f"/member/{state_code}/{district}", ctx, {"currentMember": "true"})
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving members for {state_code}-{district}: {data['error']}"))
        
        members = data.get("members", [])
        if not members:
            return f"No members found for {state_code} district {district}."
        
        # Process and deduplicate results
        members = response_processor.deduplicate_results(
            members, 
            key_fields=["bioguideId"]
        )
        
        result = [f"# Members from {state_code} District {district}"]
        result.append(f"Found {len(members)} current members:")
        
        for member in members:
            result.append("\n" + format_member_summary(member))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_members_by_district: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

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
    
    Returns:
        A formatted list of members matching the search criteria.
    """
    try:
        # Validate limit parameter
        limit_validation = validator.validate_limit_range(limit, 250)
        if not limit_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "limit", limit, limit_validation.error_message
            ))
        
        # Validate congress parameter if provided
        if congress is not None:
            congress_validation = validator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(CommonErrors.invalid_parameter(
                    "congress", congress, congress_validation.error_message
                ))
        
        # Validate state parameter if provided
        if state is not None:
            state_validation = validator.validate_state_code(state)
            if not state_validation.is_valid:
                return format_error_response(CommonErrors.invalid_parameter(
                    "state", state, state_validation.error_message
                ))
            state = state_validation.sanitized_value
        
        # Validate chamber parameter if provided
        if chamber is not None:
            chamber = chamber.lower().strip()
            if chamber not in ["house", "senate"]:
                return format_error_response(CommonErrors.invalid_parameter(
                    "chamber", chamber, "Chamber must be 'house' or 'senate'"
                ))
        
        # Validate party parameter if provided
        if party is not None:
            party = party.upper().strip()
            if party not in ["D", "R", "I", "DEMOCRATIC", "REPUBLICAN", "INDEPENDENT"]:
                return format_error_response(CommonErrors.invalid_parameter(
                    "party", party, "Party must be 'D', 'R', 'I', 'Democratic', 'Republican', or 'Independent'"
                ))
            # Normalize party names
            if party in ["DEMOCRATIC"]:
                party = "D"
            elif party in ["REPUBLICAN"]:
                party = "R"
            elif party in ["INDEPENDENT"]:
                party = "I"
        
        # Validate district parameter if provided
        if district is not None:
            if not isinstance(district, int) or district < 1:
                return format_error_response(CommonErrors.invalid_parameter(
                    "district", district, "District must be a positive integer (e.g., 1, 2, 10)"
                ))
        
        # Build search parameters
        params = {"limit": limit}
        if current_member:
            params["currentMember"] = "true"
        
        # Determine the best API endpoint based on provided parameters
        endpoint = "/member"
        
        # If we have specific state and district, use the district endpoint
        if state and district:
            endpoint = f"/member/{state}/{district}"
        # If we have state but no district, use the state endpoint
        elif state and not district:
            endpoint = f"/member/{state}"
        # If we have congress, use the congress endpoint
        elif congress:
            endpoint = f"/member/congress/{congress}"
        
        # Make the API request
        data = await safe_members_request(endpoint, ctx, params)
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(f"Error searching members: {data['error']}"))
        
        members = data.get("members", [])
        if not members:
            return "No members found matching the specified criteria."
        
        # Apply client-side filtering for parameters not supported by the API endpoint
        filtered_members = []
        
        for member in members:
            # Filter by name if provided
            if name:
                member_name = ""
                if "directOrderName" in member:
                    member_name = member["directOrderName"].lower()
                elif "invertedOrderName" in member:
                    member_name = member["invertedOrderName"].lower()
                elif isinstance(member.get("name"), str):
                    member_name = member["name"].lower()
                elif isinstance(member.get("name"), dict):
                    first = member["name"].get("firstName", "")
                    last = member["name"].get("lastName", "")
                    member_name = f"{first} {last}".lower()
                
                if name.lower() not in member_name:
                    continue
            
            # Filter by party if provided
            if party:
                member_party = ""
                if "partyHistory" in member and isinstance(member["partyHistory"], list) and member["partyHistory"]:
                    party_history = member["partyHistory"][0]
                    if isinstance(party_history, dict):
                        member_party = party_history.get("partyAbbreviation", "")
                elif "partyName" in member:
                    member_party = member["partyName"]
                elif "party" in member:
                    member_party = member["party"]
                
                # Normalize member party for comparison
                if member_party.lower() in ["democratic", "d"]:
                    member_party = "D"
                elif member_party.lower() in ["republican", "r"]:
                    member_party = "R"
                elif member_party.lower() in ["independent", "i"]:
                    member_party = "I"
                
                if party != member_party:
                    continue
            
            # Filter by chamber if provided
            if chamber:
                member_chamber = ""
                if "terms" in member:
                    terms = member["terms"]
                    if isinstance(terms, dict) and "item" in terms:
                        terms = terms["item"]
                    if terms and isinstance(terms, list) and terms:
                        # Get the most recent term
                        latest_term = terms[-1]
                        member_chamber = latest_term.get("chamber", "").lower()
                
                if chamber != member_chamber:
                    continue
            
            filtered_members.append(member)
        
        # Process and deduplicate results
        filtered_members = response_processor.deduplicate_results(
            filtered_members, 
            key_fields=["bioguideId"]
        )
        
        # Apply limit to filtered results
        if len(filtered_members) > limit:
            filtered_members = filtered_members[:limit]
        
        if not filtered_members:
            return "No members found matching the specified criteria after filtering."
        
        # Format results
        result = ["# Member Search Results"]
        result.append(f"Found {len(filtered_members)} members:")
        
        for member in filtered_members:
            result.append("\n" + format_member_summary(member))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in search_members: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

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
    
    Returns:
        A formatted list of members matching the specified criteria.
    """
    try:
        # Validate congress parameter
        congress_validation = validator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            ))
        
        # Validate state_code parameter
        state_validation = validator.validate_state_code(state_code)
        if not state_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter(
                "state_code", state_code, state_validation.error_message
            ))
        
        state_code = state_validation.sanitized_value
        
        # Validate district parameter if provided
        if district is not None:
            if not isinstance(district, int) or district < 1:
                return format_error_response(CommonErrors.invalid_parameter(
                    "district", district, "District must be a positive integer (e.g., 1, 2, 10)"
                ))
        
        # Build parameters
        params = {}
        if current_member:
            params["currentMember"] = "true"
        
        # Determine endpoint based on whether district is provided
        if district is not None:
            endpoint = f"/member/{state_code}/{district}"
        else:
            endpoint = f"/member/{state_code}"
        
        # Make the API request
        data = await safe_members_request(endpoint, ctx, params)
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving members: {data['error']}"))
        
        members = data.get("members", [])
        if not members:
            district_str = f" district {district}" if district else ""
            return f"No members found for {state_code}{district_str} in Congress {congress}."
        
        # Filter by congress if the API doesn't handle it directly
        filtered_members = []
        for member in members:
            # Check if member served in the specified congress
            if "terms" in member:
                terms = member["terms"]
                # Handle case where terms might be wrapped in an object with 'item' key
                if isinstance(terms, dict) and "item" in terms:
                    terms = terms["item"]
                
                if terms and isinstance(terms, list):
                    # Check if any term matches the specified congress
                    for term in terms:
                        if isinstance(term, dict) and term.get("congress") == congress:
                            filtered_members.append(member)
                            break
        
        # Process and deduplicate results
        filtered_members = response_processor.deduplicate_results(
            filtered_members, 
            key_fields=["bioguideId"]
        )
        
        if not filtered_members:
            district_str = f" district {district}" if district else ""
            return f"No members found for {state_code}{district_str} in the {congress}th Congress."
        
        # Format results
        district_str = f" District {district}" if district else ""
        result = [f"# Members from {state_code}{district_str} - {congress}th Congress"]
        result.append(f"Found {len(filtered_members)} members:")
        
        for member in filtered_members:
            result.append("\n" + format_member_summary(member))
        
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_members_by_congress_state_district: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(f"Unexpected error: {str(e)}"))

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
