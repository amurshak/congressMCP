"""
Congressional Records and Hearings - Consolidated MCP bucket tool for records and communications.

This bucket consolidates ~20 individual tools into a single interface with operation-based routing:
- FREE Operations (3): Basic record search, communication search, hearing search
- PAID Operations (17): Advanced records, communication details, hearing content, bound records

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
    # All record and communication operations now available for free tier
    "search_congressional_record",
    "search_house_communications", 
    "search_hearings",
    # Advanced congressional record operations
    "search_daily_congressional_record",
    "search_bound_congressional_record",
    # House communication operations
    "get_house_communication_details",
    "search_house_requirements",
    "get_house_requirement_details",
    "get_house_requirement_matching_communications",
    # Senate communication operations
    "search_senate_communications",
    "get_senate_communication_details",
    # Committee communication operations
    "get_committee_communication_details",
    # Hearing operations
    "get_hearings_by_congress",
    "get_hearings_by_congress_and_chamber", 
    "get_hearing_details",
    "get_hearing_content"
}

PAID_OPERATIONS = {
    # Advanced congressional record operations
    "search_daily_congressional_record",
    "search_bound_congressional_record",
    
    # House communication operations
    "get_house_communication_details",
    "search_house_requirements",
    "get_house_requirement_details",
    "get_house_requirement_matching_communications",
    
    # Senate communication operations
    "search_senate_communications",
    "get_senate_communication_details",
    
    # Committee communication operations
    "get_committee_communication_details",
    
    # Hearing operations (all paid)
    "get_hearings_by_congress",
    "get_hearings_by_congress_and_chamber", 
    "get_hearing_details",
    "get_hearing_content"
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

async def route_records_and_hearings_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate internal function."""
    
    # Congressional Record operations
    if operation == "search_congressional_record":
        from ..congressional_record import search_congressional_record
        return await search_congressional_record(ctx, **kwargs)
    elif operation == "search_daily_congressional_record":
        from ..daily_congressional_record import search_daily_congressional_record
        return await search_daily_congressional_record(ctx, **kwargs)
    elif operation == "search_bound_congressional_record":
        from ..bound_congressional_record import search_bound_congressional_record
        return await search_bound_congressional_record(ctx, **kwargs)
    
    # House communication operations
    elif operation == "search_house_communications":
        from ..house_communications import search_house_communications
        return await search_house_communications(ctx, **kwargs)
    elif operation == "get_house_communication_details":
        from ..house_communications import get_house_communication_details
        return await get_house_communication_details(ctx, **kwargs)
    
    # House requirements operations
    elif operation == "search_house_requirements":
        from ..house_requirements import search_house_requirements
        return await search_house_requirements(ctx, **kwargs)
    elif operation == "get_house_requirement_details":
        from ..house_requirements import get_house_requirement_details
        return await get_house_requirement_details(ctx, **kwargs)
    elif operation == "get_house_requirement_matching_communications":
        from ..house_requirements import get_house_requirement_matching_communications
        return await get_house_requirement_matching_communications(ctx, **kwargs)
    
    # Senate communication operations
    elif operation == "search_senate_communications":
        from ..senate_communications import search_senate_communications
        return await search_senate_communications(ctx, **kwargs)
    elif operation == "get_senate_communication_details":
        from ..senate_communications import get_senate_communication_details
        return await get_senate_communication_details(ctx, **kwargs)
    
    # Committee communication operations
    elif operation == "get_committee_communication_details":
        from ..committees import get_committee_communication_details
        return await get_committee_communication_details(ctx, **kwargs)
    
    # Hearing operations
    elif operation == "search_hearings":
        from ..hearings import search_hearings
        return await search_hearings(ctx, **kwargs)
    elif operation == "get_hearings_by_congress":
        from ..hearings import get_hearings_by_congress
        return await get_hearings_by_congress(ctx, **kwargs)
    elif operation == "get_hearings_by_congress_and_chamber":
        from ..hearings import get_hearings_by_congress_and_chamber
        return await get_hearings_by_congress_and_chamber(ctx, **kwargs)
    elif operation == "get_hearing_details":
        from ..hearings import get_hearing_details
        return await get_hearing_details(ctx, **kwargs)
    elif operation == "get_hearing_content":
        from ..hearings import get_hearing_content
        return await get_hearing_content(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool("records_and_hearings")
async def records_and_hearings(
    ctx: Context,
    operation: str,
    # Congressional Record parameters
    year: Optional[int] = None,
    month: Optional[int] = None,
    day: Optional[int] = None,
    congress: Optional[int] = None,
    volume_number: Optional[str] = None,
    issue_number: Optional[str] = None,
    limit: Optional[int] = None,
    # Communication parameters
    communication_type: Optional[str] = None,
    communication_number: Optional[int] = None,
    chamber: Optional[str] = None,
    requirement_number: Optional[int] = None,
    # Hearing parameters
    keywords: Optional[str] = None,
    jacket_number: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None,
    sort: Optional[str] = None
) -> str:
    """
    Congressional Records and Hearings - Unified access to records and communications.
    
    This bucket provides access to congressional records, communications, and hearings with 
    tier-based access control:
    
    FREE TIER OPERATIONS (3):
    - search_congressional_record: Search congressional record issues
    - search_house_communications: Search House communications
    - search_hearings: Search committee hearings
    
    PAID TIER OPERATIONS (17):
    Congressional Records:
    - search_daily_congressional_record: Search daily record issues
    - search_bound_congressional_record: Search bound record volumes
    
    House Communications:
    - get_house_communication_details: Get detailed communication info
    - search_house_requirements: Search House requirements
    - get_house_requirement_details: Get requirement details
    - get_house_requirement_matching_communications: Get matching communications
    
    Senate Communications:
    - search_senate_communications: Search Senate communications
    - get_senate_communication_details: Get Senate communication details
    
    Committee Communications:
    - get_committee_communication_details: Get committee communication details
    
    Hearing Operations:
    - get_hearings_by_congress: Get hearings by Congress
    - get_hearings_by_congress_and_chamber: Get hearings by Congress and chamber
    - get_hearing_details: Get detailed hearing information
    - get_hearing_content: Get full hearing content/text
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters:
        
        Congressional Record Parameters:
        - year: Year of record issue
        - month: Month of record issue
        - day: Day of record issue
        - congress: Congress number
        - volume_number: Volume number for bound records
        - issue_number: Issue number for daily records
        - limit: Maximum results to return
        
        Communication Parameters:
        - communication_type: Type of communication (e.g., 'ec', 'pm', 'pom')
        - communication_number: Communication number
        - chamber: Chamber ('house' or 'senate')
        - requirement_number: House requirement number
        
        Hearing Parameters:
        - keywords: Keywords for hearing search
        - jacket_number: Hearing jacket number
        - from_date_time: Start date filter (YYYY-MM-DDT00:00:00Z)
        - to_date_time: End date filter (YYYY-MM-DDT00:00:00Z)
        - sort: Sort order for results
    
    Returns:
        Operation results as formatted string
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Search congressional record:
        {
            "operation": "search_congressional_record",
            "year": 2024,
            "month": 3,
            "limit": 10
        }
        
        Search hearings:
        {
            "operation": "search_hearings",
            "keywords": "climate change",
            "from_date_time": "2024-01-01T00:00:00Z",
            "to_date_time": "2024-12-31T00:00:00Z"
        }
        
        Get hearing details (requires paid tier):
        {
            "operation": "get_hearing_details",
            "jacket_number": 12345
        }
        
        Search House communications:
        {
            "operation": "search_house_communications",
            "communication_type": "ec",
            "limit": 5
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
            'year': year,
            'month': month,
            'day': day,
            'congress': congress,
            'volume_number': volume_number,
            'issue_number': issue_number,
            'limit': limit,
            'communication_type': communication_type,
            'communication_number': communication_number,
            'chamber': chamber,
            'requirement_number': requirement_number,
            'keywords': keywords,
            'jacket_number': jacket_number,
            'from_date_time': from_date_time,
            'to_date_time': to_date_time,
            'sort': sort
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        return await route_records_and_hearings_operation(ctx, operation, **operation_kwargs)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in records_and_hearings operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
