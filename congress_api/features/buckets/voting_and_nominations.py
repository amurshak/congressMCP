"""
Congressional Voting and Nominations - Consolidated MCP bucket tool for voting and nominations.

This bucket consolidates 13+ individual tools into a single interface with operation-based routing.
ALL operations are currently available to ALL users regardless of tier - only usage limits differ:
- FREE Tier: All operations, 500 calls/month
- PRO Tier: All operations, 5,000 calls/month  
- ENTERPRISE Tier: All operations

Access control infrastructure maintained for potential future tier differentiation.
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
    # All voting and nomination operations now available for free tier
    "get_house_votes_by_congress",
    "search_nominations",
    # Advanced voting operations
    "get_house_votes_by_session", 
    "get_house_vote_details",
    "get_house_vote_details_enhanced",
    "get_house_vote_member_votes",
    "get_house_vote_member_votes_xml",
    # Nomination operations
    "get_latest_nominations",
    "get_nomination_details",
    "get_nomination_actions",
    "get_nomination_committees", 
    "get_nomination_hearings",
    "get_nomination_nominees",
    "get_nominations_by_congress"
}

PAID_OPERATIONS = {
    # Advanced voting operations
    "get_house_votes_by_session", 
    "get_house_vote_details",
    "get_house_vote_details_enhanced",
    "get_house_vote_member_votes",
    "get_house_vote_member_votes_xml",
    
    # Nomination operations (all paid)
    "get_latest_nominations",
    "get_nomination_details",
    "get_nomination_actions",
    "get_nomination_committees", 
    "get_nomination_hearings",
    "get_nomination_nominees",
    "get_nominations_by_congress"
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

async def route_voting_and_nominations_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate internal function."""
    
    # House voting operations  
    if operation == "get_house_votes_by_congress":
        from ..house_votes import get_house_votes_by_congress
        return await get_house_votes_by_congress(ctx, **kwargs)
    elif operation == "get_house_votes_by_session":
        from ..house_votes import get_house_votes_by_session
        return await get_house_votes_by_session(ctx, **kwargs)
    elif operation == "get_house_vote_details":
        from ..house_votes import get_house_vote_details
        return await get_house_vote_details(ctx, **kwargs)
    elif operation == "get_house_vote_details_enhanced":
        from ..house_votes import get_house_vote_details_enhanced
        return await get_house_vote_details_enhanced(ctx, **kwargs)
    elif operation == "get_house_vote_member_votes":
        from ..house_votes import get_house_vote_member_votes
        return await get_house_vote_member_votes(ctx, **kwargs)
    elif operation == "get_house_vote_member_votes_xml":
        from ..house_votes import get_house_vote_member_votes_xml
        return await get_house_vote_member_votes_xml(ctx, **kwargs)
    
    # Nomination operations
    elif operation == "search_nominations":
        from ..nominations import search_nominations
        return await search_nominations(ctx, **kwargs)
    elif operation == "get_latest_nominations":
        from ..nominations import get_latest_nominations
        return await get_latest_nominations(ctx, **kwargs)
    elif operation == "get_nomination_details":
        from ..nominations import get_nomination_details
        return await get_nomination_details(ctx, **kwargs)
    elif operation == "get_nomination_actions":
        from ..nominations import get_nomination_actions
        return await get_nomination_actions(ctx, **kwargs)
    elif operation == "get_nomination_committees":
        from ..nominations import get_nomination_committees
        return await get_nomination_committees(ctx, **kwargs)
    elif operation == "get_nomination_hearings":
        from ..nominations import get_nomination_hearings
        return await get_nomination_hearings(ctx, **kwargs)
    elif operation == "get_nomination_nominees":
        from ..nominations import get_nomination_nominees
        return await get_nomination_nominees(ctx, **kwargs)
    elif operation == "get_nominations_by_congress":
        from ..nominations import get_nominations_by_congress
        return await get_nominations_by_congress(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool("voting_and_nominations")
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
) -> str:
    """
    Congressional Voting and Nominations - Unified access to voting and nominations.
    
    ALL operations are available to ALL users regardless of tier - only usage limits differ:
    - FREE (500), PRO (5,000), ENTERPRISE (100,000) calls/month
    
    AVAILABLE OPERATIONS:
    Basic Voting Operations:
    - get_house_votes_by_congress: Get House votes for specific Congress
    - search_nominations: Search nominations by keywords
    
    Advanced House Voting:
    - get_house_votes_by_session: Get votes by Congress and session
    - get_house_vote_details: Get detailed vote information
    - get_house_vote_details_enhanced: Get enhanced vote details with metadata
    - get_house_vote_member_votes: Get individual member votes
    - get_house_vote_member_votes_xml: Get raw XML member vote data
    
    Nomination Operations:
    - get_latest_nominations: Get most recent nominations
    - get_nomination_details: Get detailed nomination information
    - get_nomination_actions: Get actions taken on nomination
    - get_nomination_committees: Get committees handling nomination
    - get_nomination_hearings: Get hearings for nomination
    - get_nomination_nominees: Get nominees within nomination
    - get_nominations_by_congress: Get nominations by Congress
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters:
        
        Voting Parameters:
        - congress: Congress number (e.g., 118)
        - session: Session number (1 or 2)
        - vote_number: Roll call vote number
        - limit: Maximum results to return
        
        Nomination Parameters:
        - keywords: Keywords for nomination search
        - nomination_number: Specific nomination number
        - ordinal: Ordinal number for nominee position
        - sort: Sort order for results
        - from_date: Start date filter (YYYY-MM-DDT00:00:00Z)
        - to_date: End date filter (YYYY-MM-DDT00:00:00Z)
    
    Returns:
        Operation results as formatted string
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Get House votes by Congress:
        {
            "operation": "get_house_votes_by_congress",
            "congress": 118,
            "limit": 20
        }
        
        Search nominations:
        {
            "operation": "search_nominations",
            "keywords": "judge",
            "from_date": "2024-01-01T00:00:00Z",
            "to_date": "2024-12-31T00:00:00Z"
        }
        
        Get vote details:
        {
            "operation": "get_house_vote_details",
            "congress": 118,
            "session": 1,
            "vote_number": 150
        }
        
        Get nomination details:
        {
            "operation": "get_nomination_details",
            "congress": 118,
            "nomination_number": 123
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
        
        # Route to appropriate internal function
        return await route_voting_and_nominations_operation(ctx, operation, **operation_kwargs)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in voting_and_nominations operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")