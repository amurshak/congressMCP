# committees.py
from typing import Dict, List, Any, Optional
import logging
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor

# Set up logging
logger = logging.getLogger(__name__)

# Initialize defensive API wrapper
defensive_api = DefensiveAPIWrapper()

async def safe_committees_request(endpoint: str, ctx: Context, params: Dict[str, Any] = {}) -> Dict[str, Any]:
    """Safe API request wrapper for committees endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, params, endpoint_type="committees")

# Formatting helpers
def format_committee_summary(committee: Dict[str, Any]) -> str:
    """Format a committee into a readable summary."""
    result = []
    result.append(f"Committee: {committee.get('name', 'Unknown')}")
    result.append(f"Chamber: {committee.get('chamber', 'Unknown')}")
    result.append(f"Committee Code: {committee.get('systemCode', 'Unknown')}")
    result.append(f"URL: {committee.get('url', 'No URL available')}")
    return "\n".join(result)

# Resources (Static/Reference Data)
# - get_committees: List all committees
# - get_committees_by_chamber: List committees by chamber  
# - get_committee_details: Specific committee details

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

# Tools (Interactive/Parameterized Functions)
# - get_committee_bills: Bills with limit parameter
# - get_committee_reports: Reports with limit parameter
# - get_committee_nominations: Nominations with limit parameter  
# - get_committee_communications: Communications with limit parameter
# - search_committees: Search functionality

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
    try:
        # Validate parameters
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            return chamber_validation.error_message
            
        limit_validation = ParameterValidator.validate_limit(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return limit_validation.error_message
        
        # Build endpoint
        endpoint = f"/committee/{chamber.lower()}/{committee_code}/bills"
        
        # Make API request
        response = await safe_committees_request(endpoint, ctx, {"limit": limit})
        
        if "error" in response:
            logger.warning(f"API error for committee bills: {response['error']}")
            return response["error"]
        
        bills = response.get("bills", [])
        if not bills:
            return f"No bills found for committee {committee_code} in the {chamber.capitalize()}."
        
        # Deduplicate bills
        bills = ResponseProcessor.deduplicate_results(
            bills, 
            key_fields=["congress", "number", "type"]
        )
        
        # Format results
        result = [f"Bills referred to {chamber.capitalize()} Committee {committee_code}:"]
        for bill in bills[:limit]:
            title = bill.get("title", "No title available")
            bill_type = bill.get("type", "Unknown")
            number = bill.get("number", "Unknown")
            congress = bill.get("congress", "Unknown")
            url = bill.get("url", "No URL available")
            
            # Get latest action
            latest_action = bill.get("latestAction", {})
            action_date = latest_action.get("actionDate", "Unknown")
            action_text = latest_action.get("text", "No action text")
            
            result.append(f"\n**{bill_type.upper()} {number}** (Congress {congress})")
            result.append(f"Title: {title}")
            result.append(f"Latest Action ({action_date}): {action_text}")
            result.append(f"URL: {url}")
        
        logger.info(f"Successfully retrieved {len(bills)} bills for committee {committee_code}")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_committee_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("committee bills")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)

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
    try:
        # Validate parameters
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            return chamber_validation.error_message
            
        limit_validation = ParameterValidator.validate_limit(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return limit_validation.error_message
        
        # Build endpoint
        endpoint = f"/committee/{chamber.lower()}/{committee_code}/reports"
        
        # Make API request
        response = await safe_committees_request(endpoint, ctx, {"limit": limit})
        
        if "error" in response:
            logger.warning(f"API error for committee reports: {response['error']}")
            return response["error"]
        
        reports = response.get("reports", [])
        if not reports:
            return f"No reports found for committee {committee_code} in the {chamber.capitalize()}."
        
        # Deduplicate reports
        reports = ResponseProcessor.deduplicate_results(
            reports, 
            key_fields=["congress", "number", "type"]
        )
        
        # Format results
        result = [f"Reports from {chamber.capitalize()} Committee {committee_code}:"]
        for report in reports[:limit]:
            title = report.get("title", "No title available")
            report_type = report.get("type", "Unknown")
            number = report.get("number", "Unknown")
            congress = report.get("congress", "Unknown")
            url = report.get("url", "No URL available")
            update_date = report.get("updateDate", "Unknown")
            
            result.append(f"\n**{report_type.upper()} {number}** (Congress {congress})")
            result.append(f"Title: {title}")
            result.append(f"Updated: {update_date}")
            result.append(f"URL: {url}")
        
        logger.info(f"Successfully retrieved {len(reports)} reports for committee {committee_code}")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_committee_reports: {str(e)}")
        error_response = CommonErrors.api_server_error("committee reports")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)

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
    try:
        # Validate parameters
        limit_validation = ParameterValidator.validate_limit(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return limit_validation.error_message
        
        # Build endpoint (nominations are Senate-only)
        endpoint = f"/committee/senate/{committee_code}/nominations"
        
        # Make API request
        response = await safe_committees_request(endpoint, ctx, {"limit": limit})
        
        if "error" in response:
            logger.warning(f"API error for committee nominations: {response['error']}")
            return response["error"]
        
        nominations = response.get("nominations", [])
        if not nominations:
            return f"No nominations found for Senate committee {committee_code}."
        
        # Deduplicate nominations
        nominations = ResponseProcessor.deduplicate_results(
            nominations, 
            key_fields=["congress", "number"]
        )
        
        # Format results
        result = [f"Nominations for Senate Committee {committee_code}:"]
        for nomination in nominations[:limit]:
            number = nomination.get("number", "Unknown")
            congress = nomination.get("congress", "Unknown")
            url = nomination.get("url", "No URL available")
            update_date = nomination.get("updateDate", "Unknown")
            
            # Get nominees
            nominees = nomination.get("nominees", [])
            nominee_names = []
            for nominee in nominees:
                first_name = nominee.get("firstName", "")
                last_name = nominee.get("lastName", "")
                full_name = f"{first_name} {last_name}".strip()
                if full_name:
                    nominee_names.append(full_name)
            
            nominee_text = ", ".join(nominee_names) if nominee_names else "Unknown nominees"
            
            result.append(f"\n**Nomination {number}** (Congress {congress})")
            result.append(f"Nominees: {nominee_text}")
            result.append(f"Updated: {update_date}")
            result.append(f"URL: {url}")
        
        logger.info(f"Successfully retrieved {len(nominations)} nominations for committee {committee_code}")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_committee_nominations: {str(e)}")
        error_response = CommonErrors.api_server_error("committee nominations")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)

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
    try:
        # Validate parameters
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            return chamber_validation.error_message
            
        limit_validation = ParameterValidator.validate_limit(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return limit_validation.error_message
        
        # Build endpoint
        endpoint = f"/committee/{chamber.lower()}/{committee_code}/communications"
        
        # Make API request
        response = await safe_committees_request(endpoint, ctx, {"limit": limit})
        
        if "error" in response:
            logger.warning(f"API error for committee communications: {response['error']}")
            return response["error"]
        
        communications = response.get("communications", [])
        if not communications:
            return f"No communications found for committee {committee_code} in the {chamber.capitalize()}."
        
        # Deduplicate communications
        communications = ResponseProcessor.deduplicate_results(
            communications, 
            key_fields=["congress", "number"]
        )
        
        # Format results
        result = [f"Communications for {chamber.capitalize()} Committee {committee_code}:"]
        for comm in communications[:limit]:
            number = comm.get("number", "Unknown")
            congress = comm.get("congress", "Unknown")
            url = comm.get("url", "No URL available")
            
            # Get communication type
            comm_type = comm.get("communicationType", {})
            type_name = comm_type.get("name", "Unknown")
            
            # Get committee referral info
            committees = comm.get("committees", [])
            referral_date = "Unknown"
            if committees:
                referral_date = committees[0].get("referralDate", "Unknown")
            
            result.append(f"\n**{type_name} {number}** (Congress {congress})")
            result.append(f"Referral Date: {referral_date}")
            result.append(f"URL: {url}")
        
        logger.info(f"Successfully retrieved {len(communications)} communications for committee {committee_code}")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in get_committee_communications: {str(e)}")
        error_response = CommonErrors.api_server_error("committee communications")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)

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
    try:
        # Validate parameters
        if chamber and chamber.lower() not in ["house", "senate", "joint"]:
            logger.warning(f"Invalid chamber: {chamber}")
            return f"Invalid chamber '{chamber}'. Must be 'house', 'senate', or 'joint'."
            
        if congress:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                logger.warning(f"Invalid congress number: {congress}")
                return congress_validation.error_message
                
        limit_validation = ParameterValidator.validate_limit(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            return limit_validation.error_message
        
        # Build search parameters
        params = {"q": keywords, "limit": limit}
        if chamber:
            params["chamber"] = chamber.lower()
        if congress:
            params["congress"] = congress
        
        # Make API request
        response = await safe_committees_request("/committee", ctx, params)
        
        if "error" in response:
            logger.warning(f"API error for committee search: {response['error']}")
            return response["error"]
        
        committees = response.get("committees", [])
        if not committees:
            return f"No committees found matching '{keywords}'."
        
        # Format results
        result = [f"Committees matching '{keywords}':"]
        for committee in committees[:limit]:
            result.append("\n" + format_committee_summary(committee))
        
        logger.info(f"Successfully found {len(committees)} committees for search '{keywords}'")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error in search_committees: {str(e)}")
        error_response = CommonErrors.api_server_error("committee search")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)

@mcp.tool()
async def get_committee_communication_details(
    ctx: Context,
    congress: int,
    chamber: str,
    communication_type: str,
    communication_number: int
) -> str:
    """
    Get detailed information about a specific committee communication.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        chamber: Chamber of Congress ("house" or "senate")
        communication_type: Communication type (e.g., "ec", "pm", "pom")
        communication_number: Communication number
        
    Returns:
        Detailed information about the specified communication
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            return congress_validation.error_message
            
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            return chamber_validation.error_message
            
        # Validate communication type
        valid_comm_types = ["ec", "pm", "pom", "ml", "pt"]
        if communication_type.lower() not in valid_comm_types:
            logger.warning(f"Invalid communication type: {communication_type}")
            return f"Invalid communication type '{communication_type}'. Valid types: {', '.join(valid_comm_types)}"
            
        # Validate communication number
        if communication_number <= 0:
            logger.warning(f"Invalid communication number: {communication_number}")
            return "Communication number must be a positive integer"
            
        # Build endpoint based on chamber
        if chamber.lower() == "house":
            endpoint = f"/house-communication/{congress}/{communication_type.lower()}/{communication_number}"
        elif chamber.lower() == "senate":
            endpoint = f"/senate-communication/{congress}/{communication_type.lower()}/{communication_number}"
        else:
            return f"Invalid chamber '{chamber}'. Must be 'house' or 'senate'"
            
        logger.info(f"Fetching communication details: {endpoint}")
        
        # Make API request directly (like house_communications.py)
        response = await make_api_request(endpoint, ctx, {})
        
        # Log the entire response structure for debugging
        logger.debug(f"API response structure: {list(response.keys()) if isinstance(response, dict) else 'Not a dictionary'}")
        
        if "error" in response:
            logger.warning(f"API error for communication details: {response['error']}")
            return response["error"]
            
        # Debug: Log the response structure
        logger.debug(f"Response keys: {list(response.keys())}")
        logger.debug(f"Full response: {response}")
            
        # Extract communication data based on chamber - check for different possible response formats
        if chamber.lower() == "house":
            if 'house-communication' in response:
                communication_data = response['house-communication']
            elif 'houseCommunication' in response:
                communication_data = response['houseCommunication']
            else:
                logger.warning(f"Unexpected House response format. Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dictionary'}")
                return f"Retrieved house communication but in unexpected format. Keys: {list(response.keys())}"
        else:
            if 'senateCommunication' in response:
                communication_data = response['senateCommunication']
            elif 'senate-communication' in response:
                communication_data = response['senate-communication']
            else:
                logger.warning(f"Unexpected Senate response format. Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dictionary'}")
                return f"Retrieved senate communication but in unexpected format. Keys: {list(response.keys())}"
        
        # Format detailed communication information
        result = format_communication_details(communication_data, chamber)
        
        logger.info(f"Successfully retrieved communication details for {chamber} {communication_type} {communication_number}")
        return result
        
    except Exception as e:
        logger.error(f"Error in get_committee_communication_details: {str(e)}")
        error_response = CommonErrors.api_server_error("communication details")
        error_response.details = {"error": str(e)}
        return format_error_response(error_response)


def format_communication_details(communication: Dict[str, Any], chamber: str) -> str:
    """Format detailed communication information for display."""
    lines = [
        f"# {chamber.title()} Communication Details",
        f"",
        f"**Number**: {communication.get('number', 'N/A')}",
        f"**Congress**: {communication.get('congress', communication.get('congressNumber', 'N/A'))}",
        f"**Chamber**: {communication.get('chamber', chamber.title())}",
        f"**Session**: {communication.get('sessionNumber', 'N/A')}",
        f"**Congressional Record Date**: {communication.get('congressionalRecordDate', 'N/A')}",
        f"**Update Date**: {communication.get('updateDate', 'N/A')}",
        f""
    ]
    
    # Communication type
    comm_type = communication.get('communicationType', {})
    if comm_type:
        lines.extend([
            f"**Communication Type**: {comm_type.get('name', 'N/A')} ({comm_type.get('code', 'N/A')})",
            f""
        ])
    
    # Abstract/Description
    abstract = communication.get('abstract', '')
    if abstract:
        lines.extend([
            f"**Abstract**:",
            f"{abstract}",
            f""
        ])
    
    # Submitting information (House communications)
    if chamber.lower() == "house":
        submitting_agency = communication.get('submittingAgency', '')
        submitting_official = communication.get('submittingOfficial', '')
        if submitting_agency or submitting_official:
            lines.extend([
                f"**Submitting Information**:",
                f"  - Agency: {submitting_agency or 'N/A'}",
                f"  - Official: {submitting_official or 'N/A'}",
                f""
            ])
        
        # Report nature
        report_nature = communication.get('reportNature', '')
        if report_nature:
            lines.extend([
                f"**Report Nature**: {report_nature}",
                f""
            ])
        
        # Legal authority
        legal_authority = communication.get('legalAuthority', '')
        if legal_authority:
            lines.extend([
                f"**Legal Authority**: {legal_authority}",
                f""
            ])
        
        # Rulemaking
        is_rulemaking = communication.get('isRulemaking', '')
        if is_rulemaking:
            lines.extend([
                f"**Is Rulemaking**: {is_rulemaking}",
                f""
            ])
    
    # Committee referrals
    committees = communication.get('committees', [])
    if committees:
        lines.extend([
            f"**Committee Referrals**:"
        ])
        for committee in committees:
            lines.extend([
                f"  - **{committee.get('name', 'N/A')}** ({committee.get('systemCode', 'N/A')})",
                f"    - Referral Date: {committee.get('referralDate', 'N/A')}",
                f"    - URL: {committee.get('url', 'N/A')}"
            ])
        lines.append("")
    
    # Matching requirements (House communications)
    if chamber.lower() == "house":
        requirements = communication.get('matchingRequirements', [])
        if requirements:
            lines.extend([
                f"**Matching Requirements**:"
            ])
            for req in requirements:
                lines.append(f"  - {req.get('name', 'N/A')}")
            lines.append("")
    
    return "\n".join(lines)
