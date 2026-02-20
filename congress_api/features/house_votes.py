"""
Handles fetching and processing House of Representatives roll call vote data from the Congress.gov API.
"""

from typing import Dict, List, Any, Optional
import logging
import json
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import safe_congressional_request
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor
from ..core.auth.auth import require_paid_access

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
        
        # Extract vote metadata
        metadata = root.find('vote-metadata')
        if metadata is None:
            return f"Could not parse XML structure from {source_url}"
        
        # Basic vote information
        congress = metadata.find('congress')
        congress_text = congress.text if congress is not None else 'N/A'
        
        session = metadata.find('session')
        session_text = session.text if session is not None else 'N/A'
        
        rollcall_num = metadata.find('rollcall-num')
        rollcall_text = rollcall_num.text if rollcall_num is not None else 'N/A'
        
        legis_num = metadata.find('legis-num')
        legis_text = legis_num.text if legis_num is not None else 'N/A'
        
        vote_question = metadata.find('vote-question')
        question_text = vote_question.text if vote_question is not None else 'N/A'
        
        vote_type = metadata.find('vote-type')
        type_text = vote_type.text if vote_type is not None else 'N/A'
        
        vote_result = metadata.find('vote-result')
        result_text = vote_result.text if vote_result is not None else 'N/A'
        
        action_date = metadata.find('action-date')
        date_text = action_date.text if action_date is not None else 'N/A'
        
        action_time = metadata.find('action-time')
        time_text = action_time.text if action_time is not None else 'N/A'
        
        vote_desc = metadata.find('vote-desc')
        desc_text = vote_desc.text if vote_desc is not None else 'N/A'
        
        lines = [
            f"# House Vote {congress_text}-{session_text}-{rollcall_text} - Member Votes (XML Data)",
            "",
            f"**Source**: {source_url}",
            f"**Legislation**: {legis_text}",
            f"**Question**: {question_text}",
            f"**Vote Type**: {type_text}",
            f"**Result**: {result_text}",
            f"**Date**: {date_text}",
            f"**Time**: {time_text}",
            f"**Description**: {desc_text}",
            ""
        ]
        
        # Extract vote totals
        vote_totals = metadata.find('vote-totals')
        if vote_totals is not None:
            lines.append("## Vote Totals")
            
            # Party breakdown
            party_totals = vote_totals.findall('totals-by-party')
            if party_totals:
                lines.append("### By Party")
                for party_total in party_totals:
                    party = party_total.find('party')
                    party_name = party.text if party is not None else 'Unknown'
                    
                    yea = party_total.find('yea-total')
                    yea_count = yea.text if yea is not None else '0'
                    
                    nay = party_total.find('nay-total')
                    nay_count = nay.text if nay is not None else '0'
                    
                    present = party_total.find('present-total')
                    present_count = present.text if present is not None else '0'
                    
                    not_voting = party_total.find('not-voting-total')
                    not_voting_count = not_voting.text if not_voting is not None else '0'
                    
                    lines.append(f"**{party_name}**: Yes: {yea_count}, No: {nay_count}, Present: {present_count}, Not Voting: {not_voting_count}")
            
            # Overall totals
            overall_totals = vote_totals.find('totals-by-vote')
            if overall_totals is not None:
                lines.append("")
                lines.append("### Overall Totals")
                
                yea = overall_totals.find('yea-total')
                yea_count = yea.text if yea is not None else '0'
                
                nay = overall_totals.find('nay-total')
                nay_count = nay.text if nay is not None else '0'
                
                present = overall_totals.find('present-total')
                present_count = present.text if present is not None else '0'
                
                not_voting = overall_totals.find('not-voting-total')
                not_voting_count = not_voting.text if not_voting is not None else '0'
                
                lines.extend([
                    f"- **Yes**: {yea_count}",
                    f"- **No**: {nay_count}",
                    f"- **Present**: {present_count}",
                    f"- **Not Voting**: {not_voting_count}"
                ])
        
        # Extract member votes (limited sample)
        vote_data = root.find('vote-data')
        if vote_data is not None:
            recorded_votes = vote_data.findall('recorded-vote')
            if recorded_votes:
                lines.extend([
                    "",
                    "## Sample Member Votes (First 20)"
                ])
                
                # Group votes by vote type for better organization
                vote_groups = {'Yea': [], 'Nay': [], 'Present': [], 'Not Voting': []}
                
                for recorded_vote in recorded_votes[:50]:  # Process first 50 to get good samples
                    legislator = recorded_vote.find('legislator')
                    vote = recorded_vote.find('vote')
                    
                    if legislator is not None and vote is not None:
                        name = legislator.text or 'Unknown'
                        party = legislator.get('party', 'Unknown')
                        state = legislator.get('state', 'Unknown')
                        vote_choice = vote.text or 'Unknown'
                        
                        if vote_choice in vote_groups:
                            vote_groups[vote_choice].append(f"{name} ({party}-{state})")
                
                # Display sample votes by type
                for vote_type, members in vote_groups.items():
                    if members:
                        lines.append(f"### {vote_type} Votes (Sample)")
                        # Show first 10 of each type
                        for member in members[:10]:
                            lines.append(f"- {member}")
                        if len(members) > 10:
                            lines.append(f"- ... and {len(members) - 10} more")
                        lines.append("")
        
        lines.extend([
            "",
            "**Note**: This data is parsed from the official House Clerk XML file.",
            f"**Full XML available at**: {source_url}"
        ])
        
        return "\n".join(lines)
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error: {e}")
        return f"Error parsing XML from {source_url}: {str(e)}"
    except Exception as e:
        logger.error(f"Error formatting XML content: {e}")
        return f"Error processing XML data from {source_url}: {str(e)}"

# @require_paid_access
@mcp.resource("congress://house-votes/latest")
async def get_latest_house_votes(ctx: Context) -> str:
    """Get the latest House of Representatives roll call votes."""
    try:
        endpoint = "house-vote"
        params = {"format": "json", "limit": 10, "sort": "updateDate+desc"}
        
        logger.debug("Fetching latest house votes")
        
        # Make the API request
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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

# @require_paid_access
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
        data = await safe_congressional_request(endpoint, ctx, params, endpoint_type='house-votes')
        
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
