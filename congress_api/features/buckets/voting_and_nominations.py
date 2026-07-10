"""
Congressional Voting and Nominations - Consolidated MCP bucket tool for voting and nominations.

This bucket consolidates 13+ individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import VotingNominationsResponse, VoteSummary, NominationSummary
from ...utils.response_converters import _extract_result_count

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> VotingNominationsResponse:
    """Convert raw string response to structured VotingNominationsResponse."""
    import json

    try:
        # Parse the raw response
        if isinstance(raw_response, str):
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # The underlying impls return pre-formatted markdown, not JSON, so this
                # is the normal path for every operation, not a fallback for malformed
                # data — it must preserve the full response, not truncate it.
                return VotingNominationsResponse(
                    success=True,
                    operation=operation,
                    results_count=_extract_result_count(raw_response),
                    votes=[],
                    nominations=[],
                    summary=raw_response
                )
        else:
            data = raw_response

        votes = []
        nominations = []
        results_count = 0

        if isinstance(data, dict):
            # Handle votes
            if 'votes' in data:
                for vote_data in data.get('votes', []):
                    if isinstance(vote_data, dict):
                        votes.append(VoteSummary(
                            vote_number=vote_data.get('voteNumber', 0),
                            chamber=vote_data.get('chamber', ''),
                            date=vote_data.get('date', ''),
                            description=vote_data.get('question', ''),
                            result=vote_data.get('result', ''),
                            vote_counts=vote_data.get('totals', {}),
                            url=vote_data.get('url')
                        ))

            # Handle nominations
            if 'nominations' in data:
                for nom_data in data.get('nominations', []):
                    if isinstance(nom_data, dict):
                        nominations.append(NominationSummary(
                            nomination_number=nom_data.get('nominationNumber', ''),
                            nominee=nom_data.get('nominee', ''),
                            position=nom_data.get('position', ''),
                            organization=nom_data.get('organization', ''),
                            received_date=nom_data.get('receivedDate'),
                            status=nom_data.get('latestAction'),
                            url=nom_data.get('url')
                        ))

            results_count = len(votes) + len(nominations)

        return VotingNominationsResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            votes=votes,
            nominations=nominations,
            summary=f"Found {len(votes)} votes and {len(nominations)} nominations"
        )

    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return VotingNominationsResponse(
            success=False,
            operation=operation,
            results_count=0,
            votes=[],
            nominations=[],
            summary=f"Error processing response: {str(e)}"
        )

async def route_voting_and_nominations_operation(ctx: Context, operation: str, **kwargs) -> VotingNominationsResponse:
    """Route operation to appropriate internal function."""

    # House voting operations
    if operation == "get_house_votes_by_congress":
        from ..house_votes import get_house_votes_by_congress
        raw_response = await get_house_votes_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_votes_by_session":
        from ..house_votes import get_house_votes_by_session
        raw_response = await get_house_votes_by_session(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_details":
        from ..house_votes import get_house_vote_details
        raw_response = await get_house_vote_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_details_enhanced":
        from ..house_votes import get_house_vote_details_enhanced
        raw_response = await get_house_vote_details_enhanced(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_member_votes":
        from ..house_votes import get_house_vote_member_votes
        raw_response = await get_house_vote_member_votes(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_member_votes_xml":
        from ..house_votes import get_house_vote_member_votes_xml
        raw_response = await get_house_vote_member_votes_xml(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Nomination operations
    elif operation == "search_nominations":
        from ..nominations import search_nominations
        raw_response = await search_nominations(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_latest_nominations":
        from ..nominations import get_latest_nominations
        raw_response = await get_latest_nominations(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_details":
        from ..nominations import get_nomination_details
        raw_response = await get_nomination_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_actions":
        from ..nominations import get_nomination_actions
        raw_response = await get_nomination_actions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_committees":
        from ..nominations import get_nomination_committees
        raw_response = await get_nomination_committees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_hearings":
        from ..nominations import get_nomination_hearings
        raw_response = await get_nomination_hearings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_nominees":
        from ..nominations import get_nomination_nominees
        raw_response = await get_nomination_nominees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nominations_by_congress":
        from ..nominations import get_nominations_by_congress
        raw_response = await get_nominations_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool(
    "voting_and_nominations",
    title="Congressional Voting and Nominations - House votes and presidential nominations",
)
async def voting_and_nominations(
    ctx: Context,
    operation: str,
    # Voting parameters
    congress: Optional[int] = None,
    session: Optional[int] = None,
    vote_number: Optional[int] = None,
    limit: Optional[int] = None,
    # Nomination parameters
    keywords: Optional[str] = None,
    nomination_number: Optional[int] = None,
    ordinal: Optional[int] = None,
    sort: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> VotingNominationsResponse:
    """
    Congressional Voting and Nominations - Access House votes and presidential nominations.

    HOUSE VOTING (6 operations):
    • get_house_votes_by_congress/session, get_house_vote_details/enhanced
    • get_house_vote_member_votes/xml - Individual member vote records

    NOMINATIONS (7 operations):
    • search_nominations, get_latest_nominations, get_nomination_details
    • get_nomination_actions/committees/hearings/nominees, get_nominations_by_congress

    Key params: operation, congress, session, vote_number, keywords, nomination_number
    Returns structured vote/nomination data with member details and legislative actions.
    """
    try:
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'congress': congress,
            'session': session,
            'vote_number': vote_number,
            'limit': limit,
            'keywords': keywords,
            'nomination_number': nomination_number,
            'ordinal': ordinal,
            'sort': sort,
            'from_date': from_date,
            'to_date': to_date
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value

        # Route to appropriate internal function. route_voting_and_nominations_operation
        # already returns a fully-converted VotingNominationsResponse (it calls
        # _convert_to_structured_response internally) — re-converting it here fails the
        # isinstance(raw_response, str) check and silently discards all data, always
        # returning empty/zero results regardless of what the API actually returned.
        return await route_voting_and_nominations_operation(ctx, operation, **operation_kwargs)

    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in voting_and_nominations operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
