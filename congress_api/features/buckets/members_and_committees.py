"""
Congressional Members and Committees - Consolidated MCP bucket tool for members and committees.

This bucket consolidates ~20 individual tools into a single interface with operation-based routing:
- FREE Operations (3): Basic member search, member details, committee search
- PAID Operations (17): Advanced member features, committee operations, relationship analysis

Operation-level access control ensures granular tier-based access within the bucket.
"""

import logging
from typing import Optional, Dict, Any
from fastmcp import Context
from fastmcp.exceptions import ToolError
from ...mcp_app import mcp

# Import access control utilities
from ...core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

# Define operation access levels
FREE_OPERATIONS = {
    # Basic member and committee operations for free tier
    "search_members",
    "get_member_details", 
    "search_committees"
}

PAID_OPERATIONS = {
    # Advanced member features
    "get_member_sponsored_legislation",
    "get_member_cosponsored_legislation",
    "get_members_by_congress",
    "get_members_by_state",
    "get_members_by_district", 
    "get_members_by_congress_state_district",
    
    # Committee operations (all paid)
    "get_committee_bills",
    "get_committee_reports",
    "get_committee_communications", 
    "get_committee_nominations"
}

ALL_OPERATIONS = FREE_OPERATIONS | PAID_OPERATIONS

def check_operation_access(ctx: Context, operation: str) -> None:
    """Check if user has access to the requested operation based on tier."""
    if operation not in ALL_OPERATIONS:
        raise ToolError(f"Unknown operation: {operation}")
    
    if operation in FREE_OPERATIONS:
        # Free operations - all users have access
        return
    
    if operation in PAID_OPERATIONS:
        # Paid operations - check user tier
        user_tier = get_user_tier_from_context(ctx)
        
        # Handle both enum and string tier values
        if isinstance(user_tier, SubscriptionTier):
            is_paid = user_tier in [SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]
        else:
            tier_value = str(user_tier).lower()
            is_paid = tier_value in ['pro', 'enterprise']
        
        if not is_paid:
            tier_name = user_tier.value if isinstance(user_tier, SubscriptionTier) else str(user_tier).title()
            raise ToolError(
                f"Access denied: Operation '{operation}' requires a paid subscription (Pro or Enterprise). "
                f"Your current tier: {tier_name}. "
                f"Please upgrade your subscription to access this feature."
            )

async def route_members_and_committees_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate internal function."""
    
    # Member operations
    if operation == "search_members":
        from ..members import search_members
        return await search_members(ctx, **kwargs)
    elif operation == "get_member_details":
        from ..members import get_member_details
        return await get_member_details(ctx, **kwargs)
    elif operation == "get_member_sponsored_legislation":
        from ..members import get_member_sponsored_legislation
        return await get_member_sponsored_legislation(ctx, **kwargs)
    elif operation == "get_member_cosponsored_legislation":
        from ..members import get_member_cosponsored_legislation
        return await get_member_cosponsored_legislation(ctx, **kwargs)
    elif operation == "get_members_by_congress":
        from ..members import get_members_by_congress
        return await get_members_by_congress(ctx, **kwargs)
    elif operation == "get_members_by_state":
        from ..members import get_members_by_state
        return await get_members_by_state(ctx, **kwargs)
    elif operation == "get_members_by_district":
        from ..members import get_members_by_district
        return await get_members_by_district(ctx, **kwargs)
    elif operation == "get_members_by_congress_state_district":
        from ..members import get_members_by_congress_state_district
        return await get_members_by_congress_state_district(ctx, **kwargs)
    
    # Committee operations
    elif operation == "search_committees":
        from ..committees import search_committees
        return await search_committees(ctx, **kwargs)
    elif operation == "get_committee_bills":
        from ..committees import get_committee_bills
        return await get_committee_bills(ctx, **kwargs)
    elif operation == "get_committee_reports":
        from ..committees import get_committee_reports
        return await get_committee_reports(ctx, **kwargs)
    elif operation == "get_committee_communications":
        from ..committees import get_committee_communications
        return await get_committee_communications(ctx, **kwargs)
    elif operation == "get_committee_nominations":
        from ..committees import get_committee_nominations
        return await get_committee_nominations(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

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
    district: Optional[int] = None,
    current_member: Optional[bool] = None,
    limit: Optional[int] = None,
    # Committee parameters
    keywords: Optional[str] = None,
    committee_code: Optional[str] = None
) -> str:
    """
    Congressional Members and Committees - Unified access to members and committees.
    
    This bucket provides access to congressional members and committees with 
    tier-based access control:
    
    FREE TIER OPERATIONS (3):
    - search_members: Search for members by name, state, party, chamber
    - get_member_details: Get detailed member information
    - search_committees: Search committees by keywords
    
    PAID TIER OPERATIONS (17):
    Member Legislation:
    - get_member_sponsored_legislation: Get legislation sponsored by member
    - get_member_cosponsored_legislation: Get legislation cosponsored by member
    
    Advanced Member Searches:
    - get_members_by_congress: Get all members from specific Congress
    - get_members_by_state: Get members from specific state
    - get_members_by_district: Get members from specific district
    - get_members_by_congress_state_district: Get members by Congress, state, and district
    
    Committee Operations:
    - get_committee_bills: Get bills referred to committee
    - get_committee_reports: Get reports from committee
    - get_committee_communications: Get committee communications
    - get_committee_nominations: Get nominations referred to committee
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters:
        
        Member Parameters:
        - name: Member name to search for
        - bioguide_id: Member's Bioguide ID
        - state: State name or abbreviation
        - state_code: Two-letter state code
        - party: Party affiliation ('D', 'R', 'I')
        - chamber: Chamber ('house' or 'senate')
        - congress: Congress number
        - district: District number
        - current_member: Filter to current members only
        - limit: Maximum results to return
        
        Committee Parameters:
        - keywords: Keywords to search committees
        - committee_code: Specific committee code
        - chamber: Committee chamber
    
    Returns:
        Operation results as formatted string
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Search for members by name:
        {
            "operation": "search_members",
            "name": "Pelosi",
            "limit": 5
        }
        
        Get member details:
        {
            "operation": "get_member_details",
            "bioguide_id": "P000197"
        }
        
        Search committees:
        {
            "operation": "search_committees",
            "keywords": "intelligence"
        }
        
        Get member's sponsored legislation (requires paid tier):
        {
            "operation": "get_member_sponsored_legislation",
            "bioguide_id": "S000033"
        }
        
        Note: All parameters are provided at the same level. The 'operation' 
        parameter determines which function to call, and other parameters are 
        passed to that function.
    """
    try:
        # Check operation access based on user tier
        check_operation_access(ctx, operation)
        
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'name': name,
            'bioguide_id': bioguide_id,
            'state': state,
            'state_code': state_code,
            'party': party,
            'chamber': chamber,
            'congress': congress,
            'district': district,
            'current_member': current_member,
            'limit': limit,
            'keywords': keywords,
            'committee_code': committee_code
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
