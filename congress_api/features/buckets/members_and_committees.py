"""
Congressional Members and Committees - DEPRECATED

⚠️  DEPRECATION NOTICE ⚠️
This bucket system has been replaced by individual MCP tools in congress_api/features/members_committees_tools.py
Each operation is now its own @mcp.tool() with proper typing and structured Pydantic responses.

This file is kept for backward compatibility but should not be used for new development.
Individual tools provide better discoverability and type safety for AI agents.
"""

import logging
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...models.responses import MembersCommitteesResponse
from ...utils.response_converters import convert_members_committees_response as _convert_to_structured_response

logger = logging.getLogger(__name__)

# Define operation access levels - CURRENTLY ALL OPERATIONS AVAILABLE TO ALL TIERS
# Note: Both FREE_OPERATIONS and PAID_OPERATIONS contain the same operations
# This reflects the current universal access model while preserving infrastructure for future changes
FREE_OPERATIONS = {
    # All member and committee operations currently available for free tier
    "search_members",
    "get_member_details", 
    "search_committees",
    # Advanced member features
    "get_member_sponsored_legislation",
    "get_member_cosponsored_legislation",
    "get_members_by_congress",
    "get_members_by_state",
    "get_members_by_district", 
    "get_members_by_congress_state_district",
    # Committee operations
    "get_committee_bills",
    "get_committee_reports",
    "get_committee_communications",
    "get_committee_nominations"
}

# Copy all operations to paid tier (universal access model)
PAID_OPERATIONS = FREE_OPERATIONS.copy()

async def route_members_and_committees_operation(ctx: Context, operation: str, **kwargs) -> MembersCommitteesResponse:
    """Route operation to appropriate internal function."""
    
    # Member operations
    if operation == "search_members":
        from ..members import search_members
        raw_response = await search_members(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_member_details":
        from ..members import get_member_details
        raw_response = await get_member_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_member_sponsored_legislation":
        from ..members import get_member_sponsored_legislation
        raw_response = await get_member_sponsored_legislation(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_member_cosponsored_legislation":
        from ..members import get_member_cosponsored_legislation
        raw_response = await get_member_cosponsored_legislation(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_members_by_congress":
        from ..members import get_members_by_congress
        raw_response = await get_members_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_members_by_state":
        from ..members import get_members_by_state
        raw_response = await get_members_by_state(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_members_by_district":
        from ..members import get_members_by_district
        raw_response = await get_members_by_district(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_members_by_congress_state_district":
        from ..members import get_members_by_congress_state_district
        raw_response = await get_members_by_congress_state_district(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Committee operations
    elif operation == "search_committees":
        from ..committees import search_committees
        raw_response = await search_committees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_bills":
        from ..committees import get_committee_bills
        raw_response = await get_committee_bills(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_reports":
        from ..committees import get_committee_reports
        raw_response = await get_committee_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_communications":
        from ..committees import get_committee_communications
        raw_response = await get_committee_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_committee_nominations":
        from ..committees import get_committee_nominations
        raw_response = await get_committee_nominations(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")