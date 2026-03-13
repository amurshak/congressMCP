"""
Congressional Legislation Hub - DEPRECATED

⚠️  DEPRECATION NOTICE - REPLACED BY FOCUSED TOOLS ⚠️
This bucket system has been fully replaced by 3 focused MCP tools:
• bills_tool.py - All bill-related operations (~16 operations)
• amendments_tool.py - All amendment-related operations (~7 operations)  
• treaties_and_summaries_tool.py - Treaties and summaries operations (~4 operations)

Each focused tool provides:
- Clean, structured docstrings optimized for AI agent tool selection
- Better discoverability with focused operation sets
- Proper typing and structured Pydantic responses
- Under 15 lines of documentation per tool

This file should no longer be imported or used. The legislation_hub tool has been
removed from MCP server registration.
"""

import logging
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...models.responses import LegislationHubResponse
from ...core.auth import get_user_tier_from_context, SubscriptionTier
from ...utils.response_converters import convert_legislation_response as _convert_to_structured_response

logger = logging.getLogger(__name__)

# Define operation access levels - CURRENTLY ALL OPERATIONS AVAILABLE TO ALL TIERS
# Note: Both FREE_OPERATIONS and PAID_OPERATIONS contain the same operations
# This reflects the current universal access model while preserving infrastructure for future changes
ALL_OPERATIONS = {
    # Complete Bill Operations Suite
    "get_bills",  # ADDED: Core missing function
    "search_bills",
    "get_bill_details",
    "get_bill_text",
    "get_bill_text_versions",
    "get_bill_titles",
    "get_bill_content",
    "get_bill_summaries",
    "get_recent_bills",
    "get_bills_by_date_range",
    "get_bill_actions",
    "get_bill_amendments",
    "get_bill_committees",
    "get_bill_cosponsors",
    "get_bill_related_bills",
    "get_bill_subjects",
    
    # Complete Amendment Operations Suite
    "get_amendments",  # NEW: Core missing function
    "search_amendments",
    "get_amendment_details",
    "get_amendment_actions",
    "get_amendment_sponsors",
    "get_amendment_amendments",
    "get_amendment_text",
    
    # Complete Summary Operations Suite
    "search_summaries",
    
    # Complete Treaty Operations Suite
    "search_treaties",
    "get_treaty_actions",
    "get_treaty_committees", 
    "get_treaty_text"
}

# Legacy compatibility - maintained for existing code that references these
FREE_OPERATIONS = ALL_OPERATIONS  # All operations available to free tier
PAID_OPERATIONS = ALL_OPERATIONS  # All operations available to paid tiers

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

async def route_legislation_operation(ctx: Context, operation: str, **kwargs) -> LegislationHubResponse:
    """Route operation to appropriate internal function."""
    
    # For now, we'll import and call the original functions directly
    # Later we'll refactor these to be internal functions
    
    # Bills operations - using new bills module
    if operation == "search_bills":
        from .bills import search_bills
        raw_response = await search_bills(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bills":  # NEW: Core missing function
        from .bills import get_bills
        raw_response = await get_bills(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_details":
        from .bills import get_bill_details
        raw_response = await get_bill_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_text":
        from .bills import get_bill_text
        raw_response = await get_bill_text(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_actions":
        from .bills import get_bill_actions
        raw_response = await get_bill_actions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_amendments":
        from .bills import get_bill_amendments
        raw_response = await get_bill_amendments(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_committees":
        from .bills import get_bill_committees
        raw_response = await get_bill_committees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_cosponsors":
        from .bills import get_bill_cosponsors
        raw_response = await get_bill_cosponsors(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_related_bills":
        from .bills import get_bill_related_bills
        raw_response = await get_bill_related_bills(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_subjects":
        from .bills import get_bill_subjects
        raw_response = await get_bill_subjects(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_summaries":
        from .bills import get_bill_summaries
        raw_response = await get_bill_summaries(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_text_versions":
        from .bills import get_bill_text_versions
        raw_response = await get_bill_text_versions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_titles":
        from .bills import get_bill_titles
        raw_response = await get_bill_titles(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bill_content":
        from .bills import get_bill_content
        raw_response = await get_bill_content(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_recent_bills":
        from .bills import get_recent_bills
        raw_response = await get_recent_bills(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_bills_by_date_range":
        from .bills import get_bills_by_date_range
        raw_response = await get_bills_by_date_range(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Amendment operations
    elif operation == "get_amendments":  # NEW: Core missing function
        from .amendments import get_amendments
        raw_response = await get_amendments(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_amendments":
        from .amendments import search_amendments
        raw_response = await search_amendments(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_amendment_details":
        from .amendments import get_amendment_details
        raw_response = await get_amendment_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_amendment_actions":
        from .amendments import get_amendment_actions
        raw_response = await get_amendment_actions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_amendment_sponsors":
        from .amendments import get_amendment_sponsors
        raw_response = await get_amendment_sponsors(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_amendment_amendments":
        from .amendments import get_amendment_amendments
        raw_response = await get_amendment_amendments(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_amendment_text":
        from .amendments import get_amendment_text
        raw_response = await get_amendment_text(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Summary operations
    elif operation == "search_summaries":
        from ..summaries import search_summaries
        raw_response = await search_summaries(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Treaty operations
    elif operation == "search_treaties":
        from ..treaties import search_treaties
        raw_response = await search_treaties(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_treaty_actions":
        from ..treaties import get_treaty_actions
        raw_response = await get_treaty_actions(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_treaty_committees":
        from ..treaties import get_treaty_committees
        raw_response = await get_treaty_committees(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_treaty_text":
        from ..treaties import get_treaty_text
        raw_response = await get_treaty_text(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    else:
        raise ToolError(f"Unknown operation: {operation}")
