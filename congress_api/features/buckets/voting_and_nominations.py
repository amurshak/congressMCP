"""
Congressional Voting and Nominations - Consolidated MCP bucket tool for voting and nominations.

This bucket consolidates 13+ individual tools into a single interface with operation-based routing.
All operations are available to all users.
"""

import logging
from typing import Optional
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from ...core.exceptions import CongressionalAPIError, error_envelope, format_error_response
from ...mcp_app import mcp
from ...core.operation_routing import validate_operation_kwargs
from ...models.responses import VotingNominationsResponse, VoteSummary, NominationSummary, ErrorInfo
from ...utils.response_converters import _extract_result_count, structured_items_of

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> VotingNominationsResponse:
    """Build the structured response; typed lists come from the impl's real items."""
    try:
        typed_error = getattr(raw_response, "error_response", None)
        if typed_error is not None:
            payload = error_envelope(typed_error)["error"]
            return VotingNominationsResponse(
                success=False, operation=operation,
                error=ErrorInfo(**payload), results_count=0,
                votes=[], nominations=[],
                summary=f"{payload['code']}: {payload['message']}")

        kind, items = structured_items_of(raw_response)
        if items is not None:
            votes, nominations, generic = [], [], []
            if kind == "house_vote":
                for v in items:
                    leg_type = v.get("legislationType") or ""
                    leg_num = v.get("legislationNumber") or ""
                    legislation = f"{leg_type} {leg_num}".strip() or None
                    votes.append(VoteSummary(
                        vote_number=int(v.get("rollCallNumber") or 0),
                        congress=v.get("congress"),
                        session=v.get("sessionNumber"),
                        chamber="House",
                        legislation=legislation,
                        vote_type=v.get("voteType"),
                        result=v.get("result"),
                        date=v.get("startDate"),
                        url=v.get("url"),
                    ))
            elif kind == "nomination":
                for n in items:
                    latest = n.get("latestAction") or {}
                    latest_text = latest.get("text") if isinstance(latest, dict) else str(latest)
                    ntype = n.get("nominationType") or {}
                    nominees = n.get("nominees")
                    first = nominees[0] if isinstance(nominees, list) and nominees else {}
                    nominations.append(NominationSummary(
                        nomination_number=str(n.get("number", "")),
                        citation=n.get("citation"),
                        congress=n.get("congress"),
                        organization=n.get("organization"),
                        is_military=ntype.get("isMilitary") if isinstance(ntype, dict) else None,
                        nominee=(f"{first.get('firstName', '')} {first.get('lastName', '')}".strip()
                                 or None) if first.get("firstName") else None,
                        position=first.get("positionTitle") if isinstance(first, dict) else None,
                        received_date=n.get("receivedDate"),
                        latest_action=latest_text,
                        update_date=n.get("updateDate"),
                        url=n.get("url"),
                    ))
            if kind not in ("house_vote", "nomination"):
                generic = items
            return VotingNominationsResponse(
                success=True, operation=operation, results_count=len(items),
                votes=votes, nominations=nominations, items=generic,
                item_kind=kind, summary=str(raw_response))

        return VotingNominationsResponse(
            success=True, operation=operation,
            results_count=_extract_result_count(raw_response),
            votes=[], nominations=[], summary=str(raw_response))
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return VotingNominationsResponse(
            success=False, operation=operation, results_count=0,
            votes=[], nominations=[], summary=f"Error processing response: {str(e)}")

async def route_voting_and_nominations_operation(ctx: Context, operation: str, **kwargs) -> VotingNominationsResponse:
    """Route operation to appropriate internal function."""

    # House voting operations
    if operation == "get_house_votes_by_congress":
        from ..house_votes import get_house_votes_by_congress
        validate_operation_kwargs(get_house_votes_by_congress, kwargs, operation)
        raw_response = await get_house_votes_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_votes_by_session":
        from ..house_votes import get_house_votes_by_session
        validate_operation_kwargs(get_house_votes_by_session, kwargs, operation)
        raw_response = await get_house_votes_by_session(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_details":
        from ..house_votes import get_house_vote_details
        validate_operation_kwargs(get_house_vote_details, kwargs, operation)
        raw_response = await get_house_vote_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_details_enhanced":
        from ..house_votes import get_house_vote_details_enhanced
        validate_operation_kwargs(get_house_vote_details_enhanced, kwargs, operation)
        raw_response = await get_house_vote_details_enhanced(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_member_votes":
        from ..house_votes import get_house_vote_member_votes
        validate_operation_kwargs(get_house_vote_member_votes, kwargs, operation)
        raw_response = await get_house_vote_member_votes(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_vote_member_votes_xml":
        from ..house_votes import get_house_vote_member_votes_xml
        validate_operation_kwargs(get_house_vote_member_votes_xml, kwargs, operation)
        raw_response = await get_house_vote_member_votes_xml(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)

    # Nomination operations
    elif operation == "search_nominations":
        from ..nominations import search_nominations
        validate_operation_kwargs(search_nominations, kwargs, operation)
        raw_response = await search_nominations(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_latest_nominations":
        from ..nominations import get_latest_nominations
        validate_operation_kwargs(get_latest_nominations, kwargs, operation)
        raw_response = await get_latest_nominations(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_details":
        from ..nominations import get_nomination_details
        validate_operation_kwargs(get_nomination_details, kwargs, operation)
        raw_response = await get_nomination_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_actions":
        from ..nominations import get_nomination_actions
        validate_operation_kwargs(get_nomination_actions, kwargs, operation)
        raw_response = await get_nomination_actions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_committees":
        from ..nominations import get_nomination_committees
        validate_operation_kwargs(get_nomination_committees, kwargs, operation)
        raw_response = await get_nomination_committees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_hearings":
        from ..nominations import get_nomination_hearings
        validate_operation_kwargs(get_nomination_hearings, kwargs, operation)
        raw_response = await get_nomination_hearings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nomination_nominees":
        from ..nominations import get_nomination_nominees
        validate_operation_kwargs(get_nomination_nominees, kwargs, operation)
        raw_response = await get_nomination_nominees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_nominations_by_congress":
        from ..nominations import get_nominations_by_congress
        validate_operation_kwargs(get_nominations_by_congress, kwargs, operation)
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

    except CongressionalAPIError as e:
        # Typed Congress.gov error from a handler with no try/except of its
        # own: return the model carrying the section-9 envelope.
        return _convert_to_structured_response(format_error_response(e.error_response), operation)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in voting_and_nominations operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
