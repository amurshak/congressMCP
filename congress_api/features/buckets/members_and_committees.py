"""
Congressional Members and Committees - DEPRECATED

⚠️  DEPRECATION NOTICE ⚠️
This bucket system has been replaced by individual MCP tools in congress_api/features/members_committees_tools.py
Each operation is now its own @mcp.tool() with proper typing and structured Pydantic responses.

This file is kept for backward compatibility but should not be used for new development.
Individual tools provide better discoverability and type safety for AI agents.
"""

import logging
from typing import Optional, Dict, Any
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import MembersCommitteesResponse, ErrorResponse, MemberSummary, CommitteeSummary

# Import access control utilities
from ...core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> MembersCommitteesResponse:
    """Convert raw string response to structured MembersCommitteesResponse."""
    import json
    
    try:
        # Parse the raw response
        if isinstance(raw_response, str):
            # Try to extract JSON from the response if it's formatted text
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # If no JSON found, create a simple response
                return MembersCommitteesResponse(
                    success=True,
                    operation=operation,
                    results_count=0,
                    members=[],
                    committees=[],
                    summary=raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    context=f"Performed {operation} operation"
                )
        else:
            data = raw_response
        
        # Extract members and committees from the data
        members = []
        committees = []
        results_count = 0
        
        if isinstance(data, dict):
            # Handle different response structures
            if 'members' in data:
                for member_data in data.get('members', []):
                    if isinstance(member_data, dict):
                        members.append(MemberSummary(
                            bioguide_id=member_data.get('bioguideId', ''),
                            name=member_data.get('name', ''),
                            party=member_data.get('partyName'),
                            state=member_data.get('state'),
                            district=member_data.get('district'),
                            chamber=member_data.get('chamber', ''),
                            current_member=member_data.get('currentMember', False),
                            url=member_data.get('url')
                        ))
                        
            if 'committees' in data:
                for committee_data in data.get('committees', []):
                    if isinstance(committee_data, dict):
                        committees.append(CommitteeSummary(
                            committee_code=committee_data.get('systemCode', ''),
                            name=committee_data.get('name', ''),
                            chamber=committee_data.get('chamber', ''),
                            committee_type=committee_data.get('committeeTypeCode', ''),
                            url=committee_data.get('url')
                        ))
            
            results_count = len(members) + len(committees)
            
        return MembersCommitteesResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            members=members,
            committees=committees,
            summary=f"Found {len(members)} members and {len(committees)} committees",
            context=f"Performed {operation} operation"
        )
        
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation=operation,
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error processing response: {str(e)}",
            context=f"Failed {operation} operation"
        )

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

# DEPRECATED BUCKET TOOL - Kept for backward compatibility only
@mcp.tool("members_and_committees")
async def members_and_committees(
    ctx: Context,
    operation: str,
    # Member parameters
    name: Optional[str] = None,
    bioguide_id: Optional[str] = None,
    state: Optional[str] = None,
    state_code: Optional[str] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    congress: Optional[int] = None,
    current_member: Optional[bool] = None,
    district: Optional[int] = None,
    limit: Optional[int] = None,
    # Committee parameters
    committee_code: Optional[str] = None,
    committee_type: Optional[str] = None
) -> MembersCommitteesResponse:
    """
    DEPRECATED: Use individual member/committee tools instead.
    
    This bucket tool consolidates member and committee operations but has been 
    replaced by individual tools for better discoverability and type safety.
    """
    
    try:
        # Check tier access
        user_tier = get_user_tier_from_context(ctx)
        
        logger.info(f"Members and committees operation '{operation}' requested by {user_tier.value} tier")
        
        # Check if operation is allowed for user tier
        allowed_operations = FREE_OPERATIONS if user_tier == SubscriptionTier.FREE else PAID_OPERATIONS
        
        if operation not in allowed_operations:
            raise ToolError(f"Operation '{operation}' not available for {user_tier.value} tier")
        
        # Build operation kwargs from provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'name': name,
            'bioguide_id': bioguide_id,
            'state': state,
            'state_code': state_code,
            'party': party,
            'chamber': chamber,
            'congress': congress,
            'current_member': current_member,
            'district': district,
            'limit': limit,
            'committee_code': committee_code,
            'committee_type': committee_type
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        return await route_members_and_committees_operation(ctx, operation, **operation_kwargs)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in members_and_committees operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")