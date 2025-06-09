"""
Congressional Committee Intelligence - Consolidated MCP bucket tool for committee documents.

This bucket consolidates ~30 individual tools into a single interface with operation-based routing:
- FREE Operations (0): All committee document operations are paid-tier
- PAID Operations (30): Committee reports, prints, meetings, and document analysis

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
    # All committee operations now available for free tier
    # Committee report operations
    "get_latest_committee_reports",
    "get_committee_reports_by_congress",
    "get_committee_reports_by_congress_and_type",
    "get_committee_report_details",
    "get_committee_report_text_versions",
    "get_committee_report_content",
    "search_committee_reports",
    # Committee print operations
    "get_latest_committee_prints",
    "get_committee_prints_by_congress",
    "get_committee_prints_by_congress_and_chamber",
    "get_committee_print_details",
    "get_committee_print_text_versions",
    "search_committee_prints",
    # Committee meeting operations
    "get_latest_committee_meetings",
    "get_committee_meetings_by_congress",
    "get_committee_meetings_by_congress_and_chamber",
    "get_committee_meetings_by_committee",
    "get_committee_meeting_details",
    "search_committee_meetings"
}

PAID_OPERATIONS = {
    # Committee report operations
    "get_latest_committee_reports",
    "get_committee_reports_by_congress",
    "get_committee_reports_by_congress_and_type",
    "get_committee_report_details",
    "get_committee_report_text_versions",
    "get_committee_report_content",
    "search_committee_reports",
    
    # Committee print operations
    "get_latest_committee_prints",
    "get_committee_prints_by_congress",
    "get_committee_prints_by_congress_and_chamber",
    "get_committee_print_details",
    "get_committee_print_text_versions",
    "search_committee_prints",
    
    # Committee meeting operations
    "get_latest_committee_meetings",
    "get_committee_meetings_by_congress",
    "get_committee_meetings_by_congress_and_chamber",
    "get_committee_meetings_by_committee",
    "get_committee_meeting_details",
    "search_committee_meetings"
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

async def route_committee_intelligence_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate internal function."""
    
    # Committee report operations
    if operation == "get_latest_committee_reports":
        from ..committee_reports import get_latest_committee_reports
        return await get_latest_committee_reports(ctx, **kwargs)
    elif operation == "get_committee_reports_by_congress":
        from ..committee_reports import get_committee_reports_by_congress
        return await get_committee_reports_by_congress(ctx, **kwargs)
    elif operation == "get_committee_reports_by_congress_and_type":
        from ..committee_reports import get_committee_reports_by_congress_and_type
        return await get_committee_reports_by_congress_and_type(ctx, **kwargs)
    elif operation == "get_committee_report_details":
        from ..committee_reports import get_committee_report_details
        return await get_committee_report_details(ctx, **kwargs)
    elif operation == "get_committee_report_text_versions":
        from ..committee_reports import get_committee_report_text_versions
        return await get_committee_report_text_versions(ctx, **kwargs)
    elif operation == "get_committee_report_content":
        from ..committee_reports import get_committee_report_content
        return await get_committee_report_content(ctx, **kwargs)
    elif operation == "search_committee_reports":
        from ..committee_reports import search_committee_reports
        return await search_committee_reports(ctx, **kwargs)
    
    # Committee print operations
    elif operation == "get_latest_committee_prints":
        from ..committee_prints import get_latest_committee_prints
        return await get_latest_committee_prints(ctx, **kwargs)
    elif operation == "get_committee_prints_by_congress":
        from ..committee_prints import get_committee_prints_by_congress
        return await get_committee_prints_by_congress(ctx, **kwargs)
    elif operation == "get_committee_prints_by_congress_and_chamber":
        from ..committee_prints import get_committee_prints_by_congress_and_chamber
        return await get_committee_prints_by_congress_and_chamber(ctx, **kwargs)
    elif operation == "get_committee_print_details":
        from ..committee_prints import get_committee_print_details
        return await get_committee_print_details(ctx, **kwargs)
    elif operation == "get_committee_print_text_versions":
        from ..committee_prints import get_committee_print_text_versions
        return await get_committee_print_text_versions(ctx, **kwargs)
    elif operation == "search_committee_prints":
        from ..committee_prints import search_committee_prints
        return await search_committee_prints(ctx, **kwargs)
    
    # Committee meeting operations
    elif operation == "get_latest_committee_meetings":
        from ..committee_meetings import get_latest_committee_meetings
        return await get_latest_committee_meetings(ctx, **kwargs)
    elif operation == "get_committee_meetings_by_congress":
        from ..committee_meetings import get_committee_meetings_by_congress
        return await get_committee_meetings_by_congress(ctx, **kwargs)
    elif operation == "get_committee_meetings_by_congress_and_chamber":
        from ..committee_meetings import get_committee_meetings_by_congress_and_chamber
        return await get_committee_meetings_by_congress_and_chamber(ctx, **kwargs)
    elif operation == "get_committee_meetings_by_committee":
        from ..committee_meetings import get_committee_meetings_by_committee
        return await get_committee_meetings_by_committee(ctx, **kwargs)
    elif operation == "get_committee_meeting_details":
        from ..committee_meetings import get_committee_meeting_details
        return await get_committee_meeting_details(ctx, **kwargs)
    elif operation == "search_committee_meetings":
        from ..committee_meetings import search_committee_meetings
        return await search_committee_meetings(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool("committee_intelligence")
async def committee_intelligence(
    ctx: Context,
    operation: str,
    # General parameters
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    committee_code: Optional[str] = None,
    limit: Optional[int] = None,
    # Report parameters
    report_type: Optional[str] = None,
    report_number: Optional[int] = None,
    conference: Optional[str] = None,
    chunk_number: Optional[int] = None,
    chunk_size: Optional[int] = None,
    # Print parameters  
    jacket_number: Optional[int] = None,
    # Meeting parameters
    event_id: Optional[int] = None,
    keywords: Optional[str] = None,
    scheduled_from: Optional[str] = None,
    scheduled_to: Optional[str] = None,
    sort: Optional[str] = None,
    # Search parameters
    offset: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None
) -> str:
    """
    Congressional Committee Intelligence - Professional committee document access.
    
    This premium bucket provides comprehensive access to committee documents, reports, 
    and meeting intelligence with advanced analysis capabilities:
    
    ALL OPERATIONS REQUIRE PAID SUBSCRIPTION (Pro or Enterprise):
    
    Committee Reports (Advanced Analytics):
    - get_latest_committee_reports: Get most recent committee reports
    - get_committee_reports_by_congress: Get reports by Congress number
    - get_committee_reports_by_congress_and_type: Get reports by Congress and type
    - get_committee_report_details: Get detailed report information
    - get_committee_report_text_versions: Get available text versions
    - get_committee_report_content: Get full report content with chunking
    - search_committee_reports: Advanced report search with filters
    
    Committee Prints (Document Intelligence):
    - get_latest_committee_prints: Get most recent committee prints
    - get_committee_prints_by_congress: Get prints by Congress
    - get_committee_prints_by_congress_and_chamber: Get prints by Congress and chamber
    - get_committee_print_details: Get detailed print information
    - get_committee_print_text_versions: Get available text versions
    - search_committee_prints: Advanced print search
    
    Committee Meetings (Process Intelligence):
    - get_latest_committee_meetings: Get most recent meetings
    - get_committee_meetings_by_congress: Get meetings by Congress
    - get_committee_meetings_by_congress_and_chamber: Get meetings by Congress and chamber
    - get_committee_meetings_by_committee: Get meetings for specific committee
    - get_committee_meeting_details: Get detailed meeting information
    - search_committee_meetings: Advanced meeting search with filters
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters:
        
        General Parameters:
        - congress: Congress number (e.g., 118)
        - chamber: Chamber ('house', 'senate')
        - committee_code: Committee system code (e.g., 'hsag00')
        - limit: Maximum results to return
        
        Report Parameters:
        - report_type: Report type ('hrpt', 'srpt', 'erpt')
        - report_number: Report number
        - conference: Filter by conference reports
        - chunk_number: Chunk number for content retrieval
        - chunk_size: Size of content chunks
        
        Print Parameters:
        - jacket_number: Print jacket number
        
        Meeting Parameters:
        - event_id: Meeting event ID
        - keywords: Keywords for meeting search
        - scheduled_from: Start date filter (YYYY-MM-DDT00:00:00Z)
        - scheduled_to: End date filter (YYYY-MM-DDT00:00:00Z)
        - sort: Sort order for results
        
        Search Parameters:
        - offset: Pagination offset
        - from_date_time: Start date filter (YYYY-MM-DDT00:00:00Z)
        - to_date_time: End date filter (YYYY-MM-DDT00:00:00Z)
    
    Returns:
        Operation results as formatted string with enhanced metadata
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Get latest committee reports:
        {
            "operation": "get_latest_committee_reports",
            "limit": 10
        }
        
        Search committee meetings:
        {
            "operation": "search_committee_meetings",
            "keywords": "infrastructure",
            "scheduled_from": "2024-01-01T00:00:00Z",
            "scheduled_to": "2024-12-31T00:00:00Z"
        }
        
        Get committee report details:
        {
            "operation": "get_committee_report_details",
            "congress": 118,
            "report_type": "hrpt",
            "report_number": 100
        }
        
        Get committee print details:
        {
            "operation": "get_committee_print_details",
            "congress": 118,
            "jacket_number": 12345
        }
        
        Note: All parameters are provided at the same level. The 'operation' 
        parameter determines which function to call, and other parameters are 
        passed to that function. All operations in this bucket require paid access.
    """
    try:
        # Check operation access based on user tier
        check_operation_access(ctx, operation)
        
        # Build kwargs dict from all provided parameters
        operation_kwargs = {}
        for param_name, param_value in {
            'congress': congress,
            'chamber': chamber,
            'committee_code': committee_code,
            'limit': limit,
            'report_type': report_type,
            'report_number': report_number,
            'conference': conference,
            'chunk_number': chunk_number,
            'chunk_size': chunk_size,
            'jacket_number': jacket_number,
            'event_id': event_id,
            'keywords': keywords,
            'scheduled_from': scheduled_from,
            'scheduled_to': scheduled_to,
            'sort': sort,
            'offset': offset,
            'from_date_time': from_date_time,
            'to_date_time': to_date_time
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        return await route_committee_intelligence_operation(ctx, operation, **operation_kwargs)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in committee_intelligence operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
