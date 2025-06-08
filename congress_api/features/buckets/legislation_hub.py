"""
Congressional Legislation Hub - Consolidated MCP bucket tool for all legislation-related operations.

This bucket consolidates 32 individual tools into a single interface with operation-based routing:
- FREE Operations (9): Basic bill search, details, text, recent bills, basic member lookup
- PAID Operations (23): Advanced bills, amendments, summaries, treaties, full member features

Operation-level access control ensures granular tier-based access within the bucket.
"""

import logging
from typing import Optional, Dict, Any
from fastmcp import Context
from fastmcp.exceptions import ToolError
from ...mcp_app import mcp

# Import existing tool functions - we'll import them directly to convert to internal callables
# Note: We'll need to refactor these imports after we modify the original files

# Import access control utilities
from ...core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

# Define operation access levels
FREE_OPERATIONS = {
    # Basic bill operations for free tier
    "search_bills",
    "get_bill_details", 
    "get_bill_text",
    "get_bill_text_versions",
    "get_bill_titles",
    "get_bill_content",
    "get_bill_summaries",
    "get_recent_bills",
    "get_bills_by_date_range"
}

PAID_OPERATIONS = {
    # Advanced bill features
    "get_bill_actions",
    "get_bill_amendments", 
    "get_bill_committees",
    "get_bill_cosponsors",
    "get_bill_related_bills",
    "get_bill_subjects",
    
    # Amendment features (all paid)
    "search_amendments",
    "get_amendment_details",
    "get_amendment_actions", 
    "get_amendment_sponsors",
    
    # Summary features (paid)
    "search_summaries",
    
    # Treaty features (all paid)
    "search_treaties",
    "get_treaty_actions",
    "get_treaty_committees", 
    "get_treaty_text"
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

async def route_legislation_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate internal function."""
    
    # For now, we'll import and call the original functions directly
    # Later we'll refactor these to be internal functions
    
    # Bills operations
    if operation == "search_bills":
        from ..bills import search_bills
        return await search_bills(ctx, **kwargs)
    elif operation == "get_bill_details":
        from ..bills import get_bill_details
        return await get_bill_details(ctx, **kwargs)
    elif operation == "get_bill_text":
        from ..bills import get_bill_text
        return await get_bill_text(ctx, **kwargs)
    elif operation == "get_bill_actions":
        from ..bills import get_bill_actions
        return await get_bill_actions(ctx, **kwargs)
    elif operation == "get_bill_amendments":
        from ..bills import get_bill_amendments
        return await get_bill_amendments(ctx, **kwargs)
    elif operation == "get_bill_committees":
        from ..bills import get_bill_committees
        return await get_bill_committees(ctx, **kwargs)
    elif operation == "get_bill_cosponsors":
        from ..bills import get_bill_cosponsors
        return await get_bill_cosponsors(ctx, **kwargs)
    elif operation == "get_bill_related_bills":
        from ..bills import get_bill_related_bills
        return await get_bill_related_bills(ctx, **kwargs)
    elif operation == "get_bill_subjects":
        from ..bills import get_bill_subjects
        return await get_bill_subjects(ctx, **kwargs)
    elif operation == "get_bill_summaries":
        from ..bills import get_bill_summaries
        return await get_bill_summaries(ctx, **kwargs)
    elif operation == "get_bill_text_versions":
        from ..bills import get_bill_text_versions
        return await get_bill_text_versions(ctx, **kwargs)
    elif operation == "get_bill_titles":
        from ..bills import get_bill_titles
        return await get_bill_titles(ctx, **kwargs)
    elif operation == "get_bill_content":
        from ..bills import get_bill_content
        return await get_bill_content(ctx, **kwargs)
    elif operation == "get_recent_bills":
        from ..bills import get_recent_bills
        return await get_recent_bills(ctx, **kwargs)
    elif operation == "get_bills_by_date_range":
        from ..bills import get_bills_by_date_range
        return await get_bills_by_date_range(ctx, **kwargs)
    
    # Amendment operations
    elif operation == "search_amendments":
        from ..amendments import search_amendments
        return await search_amendments(ctx, **kwargs)
    elif operation == "get_amendment_details":
        from ..amendments import get_amendment_details
        return await get_amendment_details(ctx, **kwargs)
    elif operation == "get_amendment_actions":
        from ..amendments import get_amendment_actions
        return await get_amendment_actions(ctx, **kwargs)
    elif operation == "get_amendment_sponsors":
        from ..amendments import get_amendment_sponsors
        return await get_amendment_sponsors(ctx, **kwargs)
    
    # Summary operations
    elif operation == "search_summaries":
        from ..summaries import search_summaries
        return await search_summaries(ctx, **kwargs)
    
    # Treaty operations
    elif operation == "search_treaties":
        from ..treaties import search_treaties
        return await search_treaties(ctx, **kwargs)
    elif operation == "get_treaty_actions":
        from ..treaties import get_treaty_actions
        return await get_treaty_actions(ctx, **kwargs)
    elif operation == "get_treaty_committees":
        from ..treaties import get_treaty_committees
        return await get_treaty_committees(ctx, **kwargs)
    elif operation == "get_treaty_text":
        from ..treaties import get_treaty_text
        return await get_treaty_text(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool("legislation_hub")
async def legislation_hub(
    ctx: Context,
    operation: str,
    # Bill parameters
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    bill_number: Optional[int] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    days_back: Optional[int] = None,
    version: Optional[str] = None,
    chunk_number: Optional[int] = None,
    chunk_size: Optional[int] = None,
    # Amendment parameters
    amendment_type: Optional[str] = None,
    amendment_number: Optional[int] = None,
    # Treaty parameters
    treaty_number: Optional[int] = None,
    treaty_suffix: Optional[str] = None,
    topic: Optional[str] = None
) -> str:
    """
    Congressional Legislation Hub - Unified access to all legislation-related operations.
    
    This bucket provides access to bills, amendments, summaries, and treaties with 
    tier-based access control:
    
    FREE TIER OPERATIONS (9):
    - search_bills: Search for bills by keywords
    - get_bill_details: Get detailed bill information
    - get_bill_text: Get bill text and URLs
    - get_bill_text_versions: Get available text versions
    - get_bill_titles: Get bill titles
    - get_bill_content: Get actual bill content with chunking
    - get_bill_summaries: Get bill summaries
    - get_recent_bills: Get recently active bills without keywords
    - get_bills_by_date_range: Get bills within specific date range
    
    PAID TIER OPERATIONS (23):
    Bills (Advanced):
    - get_bill_actions: Get bill actions/history
    - get_bill_amendments: Get bill amendments
    - get_bill_committees: Get bill committees
    - get_bill_cosponsors: Get bill cosponsors
    - get_bill_related_bills: Get related bills
    - get_bill_subjects: Get bill subjects/topics
    
    Amendments (All Paid):
    - search_amendments: Search amendments by keywords
    - get_amendment_details: Get amendment details
    - get_amendment_actions: Get amendment actions
    - get_amendment_sponsors: Get amendment sponsors
    
    Summaries (Paid):
    - search_summaries: Search bill summaries
    
    Treaties (All Paid):
    - search_treaties: Search treaties
    - get_treaty_actions: Get treaty actions
    - get_treaty_committees: Get treaty committees
    - get_treaty_text: Get treaty text/resolution
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters (see individual operations for details)
    
    Returns:
        Operation results as formatted string
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Search for bills:
        {
            "operation": "search_bills",
            "keywords": "healthcare",
            "congress": 118,
            "limit": 10
        }
        
        Get bill details:
        {
            "operation": "get_bill_details",
            "congress": 118,
            "bill_type": "hr",
            "bill_number": 1234
        }
        
        Search amendments (requires paid tier):
        {
            "operation": "search_amendments",
            "keywords": "budget",
            "congress": 118
        }
        
        Get treaty details (requires paid tier):
        {
            "operation": "get_treaty_text",
            "congress": 118,
            "treaty_number": 5
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
            'keywords': keywords,
            'congress': congress,
            'bill_type': bill_type,
            'bill_number': bill_number,
            'limit': limit,
            'sort': sort,
            'from_date': from_date,
            'to_date': to_date,
            'days_back': days_back,
            'version': version,
            'chunk_number': chunk_number,
            'chunk_size': chunk_size,
            'amendment_type': amendment_type,
            'amendment_number': amendment_number,
            'treaty_number': treaty_number,
            'treaty_suffix': treaty_suffix,
            'topic': topic
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        return await route_legislation_operation(ctx, operation, **operation_kwargs)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in legislation_hub operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
