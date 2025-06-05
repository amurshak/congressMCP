"""
Handles fetching and processing House of Representatives roll call vote data from the Congress.gov API.
"""

from typing import Dict, List, Any, Optional
import logging
import json
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import safe_house_votes_request
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor

logger = logging.getLogger(__name__)

def validate_session_number(session: int) -> ValidationResult:
    """
    Validate session numbers for House votes.
    
    Args:
        session: Session number to validate (1 or 2)
        
    Returns:
        ValidationResult with validation status and error details
    """
    try:
        session_int = int(session)
        if session_int not in [1, 2]:
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid session number: {session}. Sessions must be 1 or 2.",
                suggestions=[
                    "Session 1 is the first session of a Congress",
                    "Session 2 is the second session of a Congress",
                    "Each Congress has exactly 2 sessions"
                ]
            )
        return ValidationResult(is_valid=True, sanitized_value=session_int)
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid session format: {session}. Please provide 1 or 2.",
            suggestions=["Session numbers must be integers: 1 or 2"]
        )

class HouseVotesProcessor(ResponseProcessor):
    """Custom response processor for house votes data."""
    
    def process_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process house votes response with deduplication and sorting."""
        if "houseRollCallVotes" not in data:
            return data
            
        votes = data["houseRollCallVotes"]
        if not isinstance(votes, list):
            return data
            
        # Deduplicate by congress + session + rollCallNumber
        seen_votes = set()
        deduplicated_votes = []
        
        for vote in votes:
            if not isinstance(vote, dict):
                continue
                
            vote_key = (
                vote.get('congress'),
                vote.get('sessionNumber'),
                vote.get('rollCallNumber')
            )
            
            if vote_key not in seen_votes:
                seen_votes.add(vote_key)
                deduplicated_votes.append(vote)
        
        # Sort by congress (desc), session (desc), then roll call number (desc)
        deduplicated_votes.sort(
            key=lambda x: (
                x.get('congress', 0),
                x.get('sessionNumber', 0),
                x.get('rollCallNumber', 0)
            ),
            reverse=True
        )
        
        original_count = len(votes)
        final_count = len(deduplicated_votes)
        
        if original_count != final_count:
            logger.info(f"House votes deduplication: {original_count} → {final_count} votes")
        
        data["houseRollCallVotes"] = deduplicated_votes
        return data

def clean_house_votes_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Clean and process house votes response data."""
    processor = HouseVotesProcessor()
    processed_data = processor.process_response(data)
    return processed_data.get("houseRollCallVotes", [])

def format_house_vote_summary(vote: Dict[str, Any]) -> str:
    """Formats a single House vote summary for display."""
    congress = vote.get('congress', 'N/A')
    session = vote.get('sessionNumber', 'N/A')
    roll_call = vote.get('rollCallNumber', 'N/A')
    legislation_type = vote.get('legislationType', '')
    legislation_number = vote.get('legislationNumber', '')
    vote_type = vote.get('voteType', 'N/A')
    result = vote.get('result', 'N/A')
    date = vote.get('startDate', 'N/A')
    url = vote.get('url', 'N/A')
    
    legislation = f"{legislation_type} {legislation_number}".strip() if legislation_type or legislation_number else "N/A"
    
    return f"""**House Vote {congress}-{session}-{roll_call}**
- **Legislation**: {legislation}
- **Vote Type**: {vote_type}
- **Result**: {result}
- **Date**: {date}
- **API URL**: {url}"""

def format_house_vote_detail(vote_data: Dict[str, Any]) -> str:
    """Formats detailed information for a single House vote."""
    if not vote_data:
        return "No house vote data available."
    
    # Handle the array structure from the API response
    if isinstance(vote_data, list):
        if not vote_data:
            return "No house vote data available."
        vote_details = vote_data[0]  # Get the first (and only) vote object from array
    else:
        # Direct vote object
        vote_details = vote_data
    
    congress = vote_details.get('congress', 'N/A')
    session = vote_details.get('sessionNumber', 'N/A')
    roll_call = vote_details.get('rollCallNumber', 'N/A')
    legislation_type = vote_details.get('legislationType', '')
    legislation_number = vote_details.get('legislationNumber', '')
    vote_type = vote_details.get('voteType', 'N/A')
    result = vote_details.get('result', 'N/A')
    date = vote_details.get('startDate', 'N/A')
    description = vote_details.get('description', 'N/A')
    question = vote_details.get('voteQuestion', 'N/A')  # Changed from 'question' to 'voteQuestion'
    
    # Calculate vote totals from votePartyTotal array
    vote_party_totals = vote_details.get('votePartyTotal', [])
    yes_count = 0
    no_count = 0
    present_count = 0
    not_voting_count = 0
    
    for party_total in vote_party_totals:
        yes_count += party_total.get('yeaTotal', 0)
        no_count += party_total.get('nayTotal', 0)
        present_count += party_total.get('presentTotal', 0)
        not_voting_count += party_total.get('notVotingTotal', 0)
    
    # If no party totals, show N/A
    yes_count = yes_count if yes_count > 0 else 'N/A'
    no_count = no_count if no_count > 0 else 'N/A'
    present_count = present_count if present_count > 0 else 'N/A'
    not_voting_count = not_voting_count if not_voting_count > 0 else 'N/A'
    
    legislation = f"{legislation_type} {legislation_number}".strip() if legislation_type or legislation_number else "N/A"
    
    lines = [
        f"# House Roll Call Vote {congress}-{session}-{roll_call}",
        "",
        f"**Legislation**: {legislation}",
        f"**Vote Type**: {vote_type}",
        f"**Result**: {result}",
        f"**Date**: {date}",
        f"**Question**: {question}",
        f"**Description**: {description}",
        "",
        "## Vote Counts",
        f"- **Yes**: {yes_count}",
        f"- **No**: {no_count}",
        f"- **Present**: {present_count}",
        f"- **Not Voting**: {not_voting_count}"
    ]
    
    return "\n".join(lines)

def format_house_vote_xml_content(xml_content: str, source_url: str) -> str:
    """Formats XML content from House Clerk's roll call vote data."""
    try:
        import xml.etree.ElementTree as ET
        
        root = ET.fromstring(xml_content)
        
        # Debug: Log the root element and its immediate children
        logger.info(f"XML Root tag: {root.tag}")
        logger.info(f"XML Root children: {[child.tag for child in root]}")
        
        # Try multiple possible XML structures
        # Structure 1: Standard expected structure
        vote_metadata = root.find('.//vote-metadata')
        if vote_metadata is None:
            # Structure 2: Try direct children
            vote_metadata = root.find('vote-metadata')
        
        # Extract metadata with fallbacks
        congress = 'N/A'
        session = 'N/A'
        roll_call = 'N/A'
        
        if vote_metadata is not None:
            congress_elem = vote_metadata.find('congress')
            session_elem = vote_metadata.find('session')
            roll_call_elem = vote_metadata.find('rollcall-num')
            
            congress = congress_elem.text if congress_elem is not None else 'N/A'
            session = session_elem.text if session_elem is not None else 'N/A'
            roll_call = roll_call_elem.text if roll_call_elem is not None else 'N/A'
        else:
            # Try alternative paths
            for elem in root.iter():
                if 'congress' in elem.tag.lower():
                    congress = elem.text or 'N/A'
                elif 'session' in elem.tag.lower():
                    session = elem.text or 'N/A'
                elif 'roll' in elem.tag.lower():
                    roll_call = elem.text or 'N/A'
        
        # Extract vote data with multiple fallback strategies
        vote_data = root.find('.//vote-data') or root.find('vote-data')
        recorded_vote = None
        
        if vote_data is not None:
            recorded_vote = vote_data.find('recorded-vote')
        
        if recorded_vote is None:
            # Try finding recorded-vote directly
            recorded_vote = root.find('.//recorded-vote') or root.find('recorded-vote')
        
        # Extract basic info with fallbacks
        date_time = 'N/A'
        location = 'N/A'
        result = 'N/A'
        vote_question = 'N/A'
        vote_desc = 'N/A'
        legis_num = 'N/A'
        
        if recorded_vote is not None:
            # Try to extract fields with multiple possible tag names
            for elem in recorded_vote:
                tag_lower = elem.tag.lower()
                if 'date' in tag_lower and date_time == 'N/A':
                    date_time = elem.text or 'N/A'
                elif 'time' in tag_lower and location == 'N/A':
                    location = elem.text or 'N/A'
                elif 'result' in tag_lower and result == 'N/A':
                    result = elem.text or 'N/A'
                elif 'question' in tag_lower and vote_question == 'N/A':
                    vote_question = elem.text or 'N/A'
                elif 'desc' in tag_lower and vote_desc == 'N/A':
                    vote_desc = elem.text or 'N/A'
                elif 'legis' in tag_lower and legis_num == 'N/A':
                    legis_num = elem.text or 'N/A'
        
        # Extract vote totals with fallbacks
        vote_totals = {}
        
        # Try to find vote totals in various locations
        totals_elem = root.find('.//vote-totals') or root.find('vote-totals')
        if totals_elem is not None:
            for total in totals_elem:
                vote_type = total.tag.replace('-', ' ').title()
                count = total.text or '0'
                vote_totals[vote_type] = count
        
        # If no totals found, try counting individual votes
        if not vote_totals:
            yea_count = len(root.findall('.//member[@vote="Yea"]') or root.findall('.//member[@vote="Yes"]'))
            nay_count = len(root.findall('.//member[@vote="Nay"]') or root.findall('.//member[@vote="No"]'))
            present_count = len(root.findall('.//member[@vote="Present"]'))
            not_voting_count = len(root.findall('.//member[@vote="Not Voting"]'))
            
            if yea_count > 0 or nay_count > 0:
                vote_totals = {
                    'Yea': str(yea_count),
                    'Nay': str(nay_count),
                    'Present': str(present_count),
                    'Not Voting': str(not_voting_count)
                }
        
        # Extract member votes (limit to first 10 per category for readability)
        member_votes = {}
        for vote_type in ['Yea', 'Yes', 'Nay', 'No', 'Present', 'Not Voting']:
            members = root.findall(f'.//member[@vote="{vote_type}"]')[:10]
            if members:
                member_votes[vote_type] = [
                    f"{member.get('name', 'Unknown')} ({member.get('party', 'Unknown')}-{member.get('state', 'Unknown')})"
                    for member in members
                ]
        
        # Build the formatted output
        lines = [
            f"# House Vote {congress}-{session}-{roll_call} - Member Votes (XML Data)",
            "",
            f"**Source**: {source_url}",
            f"**Date/Time**: {date_time}",
            f"**Location**: {location}",
            f"**Result**: {result}",
            f"**Legislation**: {legis_num}",
            "",
            f"**Question**: {vote_question}",
            f"**Description**: {vote_desc}",
            "",
            "## Vote Totals"
        ]
        
        if vote_totals:
            for vote_type, count in vote_totals.items():
                lines.append(f"- **{vote_type}**: {count}")
        else:
            lines.append("- No vote totals found in XML")
        
        # Add member vote samples
        if member_votes:
            lines.extend(["", "## Sample Member Votes (First 10 per category)"])
            for vote_type, members in member_votes.items():
                if members:
                    lines.append(f"### {vote_type} ({len(members)} shown)")
                    for member in members:
                        lines.append(f"- {member}")
        
        lines.extend([
            "",
            "**Note**: This data is parsed from the official House Clerk XML file.",
            f"**Full XML available at**: {source_url}"
        ])
        
        return "\n".join(lines)
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        return f"Error parsing XML content: {e}\n\nSource: {source_url}"
    except Exception as e:
        logger.error(f"Error formatting XML content: {e}")
        return f"Error formatting XML content: {e}\n\nSource: {source_url}"

@mcp.resource("congress://house-votes/latest")
async def get_latest_house_votes(ctx: Context) -> str:
    """Get the latest House of Representatives roll call votes."""
    try:
        endpoint = "house-vote"
        params = {"format": "json", "limit": 10, "sort": "updateDate+desc"}
        
        logger.debug("Fetching latest house votes")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching latest house votes: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Process response
        votes = clean_house_votes_response(data)
        
        if not votes:
            return "No house votes found."
        
        # Format results
        lines = ["# Latest House Votes", ""]
        for i, vote in enumerate(votes, 1):
            lines.append(f"## {i}. {format_house_vote_summary(vote)}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Exception in get_latest_house_votes: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_latest_house_votes: {str(e)}", ["Try again in a few moments", "Check if the Congressional API is available"]))

@mcp.tool()
async def get_house_votes_by_congress(ctx: Context, congress: int, limit: int = 20) -> str:
    """Get House of Representatives roll call votes for a specific Congress.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        limit: Maximum number of votes to return (1-250, default: 20)
    """
    # Parameter validation
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("limit", limit, validation_result.error_message))
    limit = validation_result.sanitized_value or limit
    
    try:
        endpoint = f"house-vote/{congress}"
        params = {"format": "json", "limit": limit, "sort": "updateDate+desc"}
        
        logger.debug(f"Fetching house votes for Congress {congress}")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching house votes for Congress {congress}: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Process response
        votes = clean_house_votes_response(data)
        
        if not votes:
            return f"No house votes found for Congress {congress}."
        
        # Format results
        lines = [f"# House Votes - Congress {congress}", ""]
        for i, vote in enumerate(votes, 1):
            lines.append(f"## {i}. {format_house_vote_summary(vote)}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Exception in get_house_votes_by_congress: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_house_votes_by_congress: {str(e)}", ["Try again in a few moments", "Check your congress parameter"]))

@mcp.tool()
async def get_house_votes_by_session(ctx: Context, congress: int, session: int, limit: int = 20) -> str:
    """Get House of Representatives roll call votes for a specific Congress and session.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        session: Session number (1 or 2)
        limit: Maximum number of votes to return (1-250, default: 20)
    """
    # Parameter validation
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = validate_session_number(session)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("session", session, validation_result.error_message))
    session = validation_result.sanitized_value or session
    
    validation_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("limit", limit, validation_result.error_message))
    limit = validation_result.sanitized_value or limit
    
    try:
        endpoint = f"house-vote/{congress}/{session}"
        params = {"format": "json", "limit": limit, "sort": "updateDate+desc"}
        
        logger.debug(f"Fetching house votes for Congress {congress}, Session {session}")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching house votes for Congress {congress}, Session {session}: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Process response
        votes = clean_house_votes_response(data)
        
        if not votes:
            return f"No house votes found for Congress {congress}, Session {session}."
        
        # Format results
        lines = [f"# House Votes - Congress {congress}, Session {session}", ""]
        for i, vote in enumerate(votes, 1):
            lines.append(f"## {i}. {format_house_vote_summary(vote)}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Exception in get_house_votes_by_session: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_house_votes_by_session: {str(e)}", ["Try again in a few moments", "Check your congress and session parameters"]))

@mcp.tool()
async def get_house_vote_details(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """Get detailed information for a specific House roll call vote.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        session: Session number (1 or 2)
        vote_number: Roll call vote number
    """
    # Parameter validation
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = validate_session_number(session)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("session", session, validation_result.error_message))
    session = validation_result.sanitized_value or session
    
    if not isinstance(vote_number, int) or vote_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter("vote_number", vote_number, "Must be a positive integer"))
    
    try:
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {"format": "json"}
        
        logger.debug(f"Fetching details for house vote {congress}-{session}-{vote_number}")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching house vote details: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Check for the correct response key
        if 'houseRollCallVote' not in data:
            return f"House vote {congress}-{session}-{vote_number} not found."
        
        vote = data['houseRollCallVote']
        return format_house_vote_detail(vote)
        
    except Exception as e:
        logger.error(f"Exception in get_house_vote_details: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_house_vote_details: {str(e)}", ["Try again in a few moments", "Check your vote parameters"]))

@mcp.tool()
async def get_house_vote_details_enhanced(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """
    Get enhanced detailed information about a specific House roll call vote with additional metadata.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        session: Session number (1 or 2)
        vote_number: Roll call vote number
    """
    # Use same validation as working function
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = validate_session_number(session)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("session", session, validation_result.error_message))
    session = validation_result.sanitized_value or session
    
    if not isinstance(vote_number, int) or vote_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter("vote_number", vote_number, "Must be a positive integer"))
    
    try:
        # Use exact same API call as working function
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {"format": "json"}
        
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        if 'houseRollCallVote' not in data:
            return f"House vote {congress}-{session}-{vote_number} not found."
        
        # Use the working formatter first, then enhance it
        vote = data['houseRollCallVote']
        basic_result = format_house_vote_detail(vote)
        
        # Add enhanced information safely
        vote_details = data['houseRollCallVote'][0] if isinstance(data['houseRollCallVote'], list) else data['houseRollCallVote']
        
        # Add URLs if available
        api_url = vote_details.get('url', 'N/A')
        source_data_url = vote_details.get('sourceDataURL', 'N/A')
        
        enhanced_section = f"""

## Enhanced Information
- **API URL**: {api_url}
- **Source Data URL (XML)**: {source_data_url}
- **Last Updated**: {vote_details.get('updateDate', 'N/A')}
"""
        
        return f"# Enhanced House Vote Details\n\n{basic_result}{enhanced_section}"
        
    except Exception as e:
        logger.error(f"Enhanced function error: {type(e).__name__}: {e}")
        return format_error_response(CommonErrors.general_error(f"Error getting enhanced vote details: {str(e)}", ["Try again in a few moments", "Check your vote parameters"]))

@mcp.tool()
async def get_house_vote_member_votes(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """Get information about how individual members voted on a specific House roll call vote.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        session: Session number (1 or 2)
        vote_number: Roll call vote number
    """
    # Parameter validation
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = validate_session_number(session)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("session", session, validation_result.error_message))
    session = validation_result.sanitized_value or session
    
    if not isinstance(vote_number, int) or vote_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter("vote_number", vote_number, "Must be a positive integer"))
    
    try:
        # First get the vote details to find the XML URL
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {"format": "json"}
        
        logger.debug(f"Fetching house vote details to get XML URL for {congress}-{session}-{vote_number}")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching house vote details: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Check for the correct response key
        if 'houseRollCallVote' not in data:
            return f"House vote {congress}-{session}-{vote_number} not found."
        
        vote = data['houseRollCallVote']
        source_data_url = vote.get('sourceDataURL')
        
        if not source_data_url:
            return f"No XML member vote data URL available for House vote {congress}-{session}-{vote_number}."
        
        lines = [
            f"# Member Votes - House Vote {congress}-{session}-{vote_number}",
            "",
            f"**Source Data URL**: {source_data_url}",
            "",
            "**Note**: Member vote data is available in XML format from the House Clerk's website.",
            "This data contains detailed voting information for each member including their vote choice (Yes/No/Present/Not Voting)."
        ]
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Exception in get_house_vote_member_votes: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_house_vote_member_votes: {str(e)}", ["Try again in a few moments", "Check your vote parameters"]))

@mcp.tool()
async def get_house_vote_member_votes_xml(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """Get the actual XML member vote data from the House Clerk's website for a specific roll call vote.
    
    Args:
        congress: Congress number (e.g., 118 for 118th Congress)
        session: Session number (1 or 2)
        vote_number: Roll call vote number
    """
    # Parameter validation
    validation_result = ParameterValidator.validate_congress_number(congress)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("congress", congress, validation_result.error_message))
    congress = validation_result.sanitized_value or congress
    
    validation_result = validate_session_number(session)
    if not validation_result.is_valid:
        return format_error_response(CommonErrors.invalid_parameter("session", session, validation_result.error_message))
    session = validation_result.sanitized_value or session
    
    if not isinstance(vote_number, int) or vote_number <= 0:
        return format_error_response(CommonErrors.invalid_parameter("vote_number", vote_number, "Must be a positive integer"))
    
    try:
        # First get the vote details to find the XML URL
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {"format": "json"}
        
        logger.debug(f"Fetching house vote details to get XML URL for {congress}-{session}-{vote_number}")
        
        # Make the API request
        data = await safe_house_votes_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error fetching house vote details: {data['error']}")
            return format_error_response(CommonErrors.api_server_error(endpoint, message=data['error']))
        
        # Check for the correct response key
        if 'houseRollCallVote' not in data:
            return f"House vote {congress}-{session}-{vote_number} not found."
        
        vote = data['houseRollCallVote']
        source_data_url = vote.get('sourceDataURL')
        
        if not source_data_url:
            return f"No XML member vote data URL available for House vote {congress}-{session}-{vote_number}."
        
        # Fetch the actual XML content from the House Clerk's website
        logger.debug(f"Fetching XML member vote data from URL: {source_data_url}")
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(source_data_url)
                if response.status_code == 200:
                    xml_content = response.text
                    
                    # Parse and format the XML content
                    return format_house_vote_xml_content(xml_content, source_data_url)
                else:
                    logger.error(f"Failed to fetch XML content: HTTP {response.status_code}")
                    return format_error_response(CommonErrors.api_server_error(
                        f"Failed to fetch XML content from House Clerk website: HTTP {response.status_code}"
                    ))
        except Exception as fetch_error:
            logger.error(f"Error fetching XML content: {str(fetch_error)}")
            return format_error_response(CommonErrors.api_server_error(
                f"Failed to fetch XML content: {str(fetch_error)}"
            ))
        
    except Exception as e:
        logger.error(f"Exception in get_house_vote_member_votes_xml: {type(e).__name__}: {e}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error in get_house_vote_member_votes_xml: {str(e)}", ["Try again in a few moments", "Check your vote parameters"]))
