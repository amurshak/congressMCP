"""
Comprehensive Treaties and Summaries Tool - Focused legislation tool for treaties and summaries

Replaces legislation_hub.py bucket with a single comprehensive tool that handles
all treaty and summary-related operations through a clean, structured interface.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ..mcp_app import mcp
from ..models.responses import LegislationHubResponse
from ..core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

def check_operation_access(ctx: Context, operation: str) -> None:
    """Check if user has access to the requested operation based on tier."""
    # All operations available to all tiers for now
    return

async def route_treaties_summaries_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate treaties or summaries function."""
    
    # Summary operations
    if operation == "search_summaries":
        from .summaries import search_summaries
        return await search_summaries(ctx, **kwargs)
    
    # Treaty operations
    elif operation == "search_treaties":
        from .treaties import search_treaties
        return await search_treaties(ctx, **kwargs)
    elif operation == "get_treaty_actions":
        from .treaties import get_treaty_actions
        return await get_treaty_actions(ctx, **kwargs)
    elif operation == "get_treaty_committees":
        from .treaties import get_treaty_committees
        return await get_treaty_committees(ctx, **kwargs)
    elif operation == "get_treaty_text":
        from .treaties import get_treaty_text
        return await get_treaty_text(ctx, **kwargs)
    
    else:
        raise ToolError(f"Unknown treaties/summaries operation: {operation}")

@mcp.tool(
    "treaties_and_summaries", 
    title="Treaties and Summaries - Legislative treaties and bill summaries",
    outputSchema=LegislationHubResponse
)
async def treaties_and_summaries(
    ctx: Context,
    operation: str,
    # Core identification
    congress: Optional[int] = None,
    treaty_number: Optional[int] = None,
    treaty_suffix: Optional[str] = None,
    # Search and filtering
    keywords: Optional[str] = None,
    topic: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    format: Optional[str] = None,
    offset: Optional[int] = None,
    # Date filtering
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
) -> str:
    """
    Treaties and Summaries Tool - Focused access to treaties and bill summaries.
    
    TREATIES OPERATIONS:
    • Search & Discovery: search_treaties
    • Legislative Process: get_treaty_actions, get_treaty_committees
    • Content: get_treaty_text
    
    SUMMARIES OPERATIONS:
    • Search & Discovery: search_summaries
    
    TREATIES:
    - search_treaties: Find treaties by congress and parameters
    - get_treaty_actions: Legislative actions on treaties
    - get_treaty_committees: Committee assignments for treaties
    - get_treaty_text: Full treaty text and resolutions
    
    SUMMARIES:
    - search_summaries: Search bill summaries by keywords and congress
    
    Args:
        operation: Specific operation to perform (see list above)
        congress: Congress number (118 for current, 119 for next)
        treaty_number: Specific treaty number within congress
        treaty_suffix: Treaty suffix identifier
        keywords: Search keywords for content
        topic: Topic filter for summaries
        limit: Results limit (max 250 for API compliance)
        sort: updateDate+desc (newest first) or updateDate+asc
        fromDateTime/toDateTime: Date range (YYYY-MM-DDTHH:MM:SSZ)
        
    Returns:
        Formatted results specific to requested operation
    """
    try:
        # Check operation access based on user tier
        check_operation_access(ctx, operation)
        
        # Build kwargs dict from all provided parameters
        operation_kwargs = {
            k: v for k, v in locals().items() 
            if k not in ['ctx', 'operation'] and v is not None
        }
        
        # Route to appropriate internal function
        raw_response = await route_treaties_summaries_operation(ctx, operation, **operation_kwargs)
        return raw_response
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in treaties/summaries operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing treaties/summaries operation '{operation}': {str(e)}")