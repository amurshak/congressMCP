# house_votes.py

"""
Handles fetching and processing House of Representatives roll call vote data from the Congress.gov API.
"""

from typing import Dict, List, Any, Optional
import logging
import json
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

logger = logging.getLogger(__name__)

def _format_house_vote_summary(vote: Dict[str, Any]) -> str:
    """Formats a single House vote summary for display."""
    details = [
        f"  Congress: {vote.get('congress', 'N/A')}",
        f"  Session: {vote.get('sessionNumber', 'N/A')}",
        f"  Roll Call: {vote.get('rollCallNumber', 'N/A')}",
        f"  Legislation: {vote.get('legislationType', '')} {vote.get('legislationNumber', '')}",
        f"  Vote Type: {vote.get('voteType', 'N/A')}",
        f"  Result: {vote.get('result', 'N/A')}",
        f"  Date: {vote.get('startDate', 'N/A')}",
        f"  API URL: {vote.get('url', 'N/A')}"
    ]
    return "\n".join(details)

def _format_house_vote_summary_list(votes: List[Dict[str, Any]]) -> str:
    """Formats a list of House vote summaries for display."""
    if not votes:
        return "No House votes found."
    formatted_votes = []
    for i, vote in enumerate(votes):
        formatted_votes.append(f"Vote {i+1}:\n{_format_house_vote_summary(vote)}")
    return "\n\n".join(formatted_votes)

def _format_house_vote_details(vote_data: Dict[str, Any]) -> str:
    """Formats detailed information for a single House vote."""
    try:
        details = [
            f"Congress: {vote_data.get('congress', 'N/A')}",
            f"Session: {vote_data.get('sessionNumber', 'N/A')}",
            f"Roll Call: {vote_data.get('rollCallNumber', 'N/A')}",
            f"Legislation: {vote_data.get('legislationType', '')} {vote_data.get('legislationNumber', '')}",
            f"Vote Type: {vote_data.get('voteType', 'N/A')}",
            f"Result: {vote_data.get('result', 'N/A')}",
            f"Date: {vote_data.get('startDate', 'N/A')}",
        ]
        return "\n".join(details)
    except Exception as e:
        logger.error(f"Error formatting house vote details: {e}", exc_info=True)
        return "Failed to format house vote details."

def _format_house_vote_member_votes_list(member_votes_data: List[Dict[str, Any]]) -> str:
    """Formats a list of member votes for a House roll call vote."""
    if not member_votes_data:
        return "No member vote information available."

    formatted_votes = ["Member Votes:"]
    for vote_info in member_votes_data:
        if isinstance(vote_info, dict):
            member_obj = vote_info.get('member', {})
            if not isinstance(member_obj, dict):
                member_obj = {}
            member_name = member_obj.get('name', 'Unknown Member')
            state = member_obj.get('state', 'N/A')
            party = member_obj.get('party', 'N/A')
            vote_cast = vote_info.get('voteCast', 'N/A')
            formatted_votes.append(f"  {member_name} ({party}-{state}): {vote_cast}")
    
    return "\n".join(formatted_votes)

@mcp.resource("congress://house-votes/latest")
async def get_latest_house_votes(ctx: Context) -> str:
    """Fetches the latest House of Representatives roll call votes."""
    endpoint = "house-vote"
    params = {"limit": 20, "sort": "updateDate+desc"} # Assuming sort order, adjust if needed
    try:
        logger.info(f"Fetching latest House votes from {endpoint} with params: {params}")
        data = await make_api_request(endpoint, ctx, params=params)
        
        if not data or "houseRollCallVotes" not in data:
            logger.warning("No 'houseRollCallVotes' field in API response or data is empty.")
            return "Could not retrieve latest House votes or no votes found."
        
        votes = data["houseRollCallVotes"]
        if not votes:
            return "No House votes found."

        return _format_house_vote_summary_list(votes)
    except Exception as e:
        logger.error(f"Failed to fetch latest House votes: {e}", exc_info=True)
        return "Failed to retrieve latest House votes."

@mcp.resource("congress://house-votes/{congress}")
async def get_house_votes_by_congress(ctx: Context, congress: int) -> str:
    """Fetches House of Representatives roll call votes for a specific Congress."""
    endpoint = f"house-vote/{congress}"
    params = {"limit": 20, "sort": "updateDate+desc"}
    try:
        logger.info(f"Fetching House votes for Congress {congress} from {endpoint} with params: {params}")
        data = await make_api_request(endpoint, ctx, params=params)

        if not data or "houseRollCallVotes" not in data:
            logger.warning(f"No 'houseRollCallVotes' field in API response for Congress {congress} or data is empty.")
            return f"Could not retrieve House votes for Congress {congress} or no votes found."
        
        votes = data["houseRollCallVotes"]
        if not votes:
            return f"No House votes found for Congress {congress}."

        return _format_house_vote_summary_list(votes)
    except Exception as e:
        logger.error(f"Failed to fetch House votes for Congress {congress}: {e}", exc_info=True)
        return f"Failed to retrieve House votes for Congress {congress}."

@mcp.resource("congress://house-votes/{congress}/{session}")
async def get_house_votes_by_session(ctx: Context, congress: int, session: int) -> str:
    """Fetches House of Representatives roll call votes for a specific Congress and session."""
    endpoint = f"house-vote/{congress}/{session}"
    params = {"limit": 20, "sort": "updateDate+desc"}
    try:
        logger.info(f"Fetching House votes for Congress {congress}, Session {session} from {endpoint} with params: {params}")
        data = await make_api_request(endpoint, ctx, params=params)

        if not data or "houseRollCallVotes" not in data:
            logger.warning(f"No 'houseRollCallVotes' field in API response for Congress {congress}, Session {session} or data is empty.")
            return f"Could not retrieve House votes for Congress {congress}, Session {session} or no votes found."
        
        votes = data["houseRollCallVotes"]
        if not votes:
            return f"No House votes found for Congress {congress}, Session {session}."

        return _format_house_vote_summary_list(votes)
    except Exception as e:
        logger.error(f"Failed to fetch House votes for Congress {congress}, Session {session}: {e}", exc_info=True)
        return f"Failed to retrieve House votes for Congress {congress}, Session {session}."

@mcp.resource("congress://house-votes/{congress}/{session}/{vote_number}")
async def get_house_vote_details(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """Retrieve and format details for a specific House roll call vote."""
    logger.info(f"Fetching details for House vote {congress}-{session}-{vote_number}")
    
    try:
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {}
        data = await make_api_request(endpoint, ctx, params=params)
        
        if data is None:
            logger.warning(f"No data returned (None) for House vote {congress}-{session}-{vote_number}.")
            return f"Could not retrieve details for House vote {congress}-{session}-{vote_number} (no data)."
        
        if not isinstance(data, dict):
            logger.warning(f"API response is not a dictionary for House vote {congress}-{session}-{vote_number}. Type: {type(data)}")
            return f"Could not retrieve details due to unexpected API response format for House vote {congress}-{session}-{vote_number}."
        
        if 'error' in data:
            logger.warning(f"Error in API response for House vote {congress}-{session}-{vote_number}. API Response: {data}")
            return f"Could not retrieve details for House vote {congress}-{session}-{vote_number} (API error)."
        
        # Process the vote data
        if 'houseRollCallVote' not in data:
            logger.warning(f"Missing 'houseRollCallVote' key in response for {congress}-{session}-{vote_number}.")
            return f"Could not retrieve details because 'houseRollCallVote' key is missing for House vote {congress}-{session}-{vote_number}."
        
        vote_payload = data['houseRollCallVote']
        
        if not isinstance(vote_payload, dict):
            if vote_payload is None:
                logger.warning(f"'houseRollCallVote' is null for {congress}-{session}-{vote_number}.")
                return f"No detailed vote information found (payload was null) for House vote {congress}-{session}-{vote_number}."
            else:
                logger.warning(f"'houseRollCallVote' is not a dictionary for {congress}-{session}-{vote_number}. Type: {type(vote_payload)}")
                return f"Unexpected data type for 'houseRollCallVote' for House vote {congress}-{session}-{vote_number}."
        
        # Format and return the vote details
        return _format_house_vote_details(vote_payload)
        
    except Exception as e:
        logger.error(f"Error processing vote data for {congress}-{session}-{vote_number}: {e}", exc_info=True)
        return f"Failed to retrieve details for House vote {congress}-{session}-{vote_number} due to an internal processing error."

@mcp.resource("congress://house-votes/{congress}/{session}/{vote_number}/members")
async def get_house_vote_member_votes(ctx: Context, congress: int, session: int, vote_number: int) -> str:
    """Fetches how individual members voted on a specific House roll call vote."""
    logger.info(f"Fetching member votes for House vote {congress}-{session}-{vote_number}")
    
    try:
        # First, get the main vote details to extract the sourceDataURL
        endpoint = f"house-vote/{congress}/{session}/{vote_number}"
        params = {}
        vote_data = await make_api_request(endpoint, ctx, params=params)
        
        if vote_data is None:
            logger.warning(f"No data returned (None) for House vote {congress}-{session}-{vote_number}.")
            return f"Could not retrieve member votes for House vote {congress}-{session}-{vote_number} (no data)."
        
        if not isinstance(vote_data, dict):
            logger.warning(f"API response is not a dictionary for House vote {congress}-{session}-{vote_number}. Type: {type(vote_data)}")
            return f"Could not retrieve member votes due to unexpected API response format for House vote {congress}-{session}-{vote_number}."
        
        if 'error' in vote_data:
            logger.warning(f"Error in API response for House vote {congress}-{session}-{vote_number}. API Response: {vote_data}")
            return f"Could not retrieve member votes for House vote {congress}-{session}-{vote_number} (API error)."
        
        # Extract sourceDataURL from the vote data
        if 'houseRollCallVote' not in vote_data:
            logger.warning(f"Missing 'houseRollCallVote' key in response for {congress}-{session}-{vote_number}.")
            return f"Could not retrieve member votes for House vote {congress}-{session}-{vote_number} (missing data)."
        
        house_roll_call_vote = vote_data['houseRollCallVote']
        
        if not isinstance(house_roll_call_vote, dict):
            logger.warning(f"'houseRollCallVote' is not a dictionary for {congress}-{session}-{vote_number}. Type: {type(house_roll_call_vote)}")
            return f"Could not retrieve member votes for House vote {congress}-{session}-{vote_number} (invalid data format)."
        
        if 'sourceDataURL' not in house_roll_call_vote:
            logger.warning(f"Missing 'sourceDataURL' in 'houseRollCallVote' for {congress}-{session}-{vote_number}.")
            return f"Could not retrieve member votes for House vote {congress}-{session}-{vote_number} (missing source URL)."
        
        source_data_url = house_roll_call_vote['sourceDataURL']
        logger.info(f"Found sourceDataURL for {congress}-{session}-{vote_number}: {source_data_url}")
        
        # Return a message with the source URL
        return f"Member votes for House vote {congress}-{session}-{vote_number} are available at: {source_data_url}\n\nThis data is in XML format from the House Clerk's website and contains detailed voting information for each member."
        
    except Exception as e:
        logger.error(f"Error processing vote data for {congress}-{session}-{vote_number}: {e}", exc_info=True)
        return f"Failed to retrieve member votes for House vote {congress}-{session}-{vote_number} due to an internal processing error."
