"""
Comprehensive Amendments Tool - Focused legislation tool for amendments operations

Replaces legislation_hub.py bucket with a single comprehensive amendments tool
that handles all amendment-related operations through a clean, structured interface.
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

async def route_amendments_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate amendments function."""
    
    if operation == "get_amendments":
        from .buckets.amendments import get_amendments
        return await get_amendments(ctx, **kwargs)
    elif operation == "search_amendments":
        from .buckets.amendments import search_amendments
        return await search_amendments(ctx, **kwargs)
    elif operation == "get_amendment_details":
        from .buckets.amendments import get_amendment_details
        return await get_amendment_details(ctx, **kwargs)
    elif operation == "get_amendment_actions":
        from .buckets.amendments import get_amendment_actions
        return await get_amendment_actions(ctx, **kwargs)
    elif operation == "get_amendment_sponsors":
        from .buckets.amendments import get_amendment_sponsors
        return await get_amendment_sponsors(ctx, **kwargs)
    elif operation == "get_amendment_amendments":
        from .buckets.amendments import get_amendment_amendments
        return await get_amendment_amendments(ctx, **kwargs)
    elif operation == "get_amendment_text":
        from .buckets.amendments import get_amendment_text
        return await get_amendment_text(ctx, **kwargs)
    else:
        raise ToolError(f"Unknown amendments operation: {operation}")

@mcp.tool(
    "amendments",
    title="Congressional Amendments - Comprehensive amendment operations",
    outputSchema=LegislationHubResponse
)
async def amendments(
    ctx: Context,
    operation: str,
    # Core amendment identification
    congress: Optional[int] = None,
    amendment_type: Optional[str] = None,
    amendment_number: Optional[int] = None,
    # Search and filtering
    keywords: Optional[str] = None,
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    format: Optional[str] = None,
    offset: Optional[int] = None,
    # Date filtering
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
) -> str:
    """
    Comprehensive Amendments Tool - All amendment operations in one focused interface.
    
    CORE OPERATIONS:
    • Search & Discovery: get_amendments, search_amendments
    • Details & Metadata: get_amendment_details, get_amendment_sponsors
    • Legislative Process: get_amendment_actions, get_amendment_amendments
    • Content: get_amendment_text
    
    SEARCH OPERATIONS:
    - get_amendments: Core amendments API access with filtering
    - search_amendments: Search amendments by keywords and parameters
    
    DETAILS OPERATIONS:
    - get_amendment_details: Complete amendment information and status
    - get_amendment_sponsors: Sponsor and cosponsor information
    
    PROCESS OPERATIONS:
    - get_amendment_actions: Legislative actions and history
    - get_amendment_amendments: Amendments to amendments (sub-amendments)
    
    CONTENT OPERATIONS:
    - get_amendment_text: Full amendment text and purpose
    
    Args:
        operation: Specific operation to perform (see list above)
        congress: Congress number (118 for current, 119 for next)
        amendment_type: hamdt (House) or samdt (Senate)
        amendment_number: Specific amendment number within type and congress
        keywords: Search keywords for amendment content
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
        raw_response = await route_amendments_operation(ctx, operation, **operation_kwargs)
        return raw_response
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in amendments operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing amendments operation '{operation}': {str(e)}")