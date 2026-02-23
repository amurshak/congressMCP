"""
Comprehensive Bills Tool - Focused legislation tool for bills operations

Replaces legislation_hub.py bucket with a single comprehensive bills tool
that handles all bill-related operations through a clean, structured interface.
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

async def route_bills_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route operation to appropriate bills function."""
    
    if operation == "search_bills":
        from .buckets.bills import search_bills
        return await search_bills(ctx, **kwargs)
    elif operation == "get_bills":
        from .buckets.bills import get_bills
        return await get_bills(ctx, **kwargs)
    elif operation == "get_bill_details":
        from .buckets.bills import get_bill_details
        return await get_bill_details(ctx, **kwargs)
    elif operation == "get_bill_text":
        from .buckets.bills import get_bill_text
        return await get_bill_text(ctx, **kwargs)
    elif operation == "get_bill_text_versions":
        from .buckets.bills import get_bill_text_versions
        return await get_bill_text_versions(ctx, **kwargs)
    elif operation == "get_bill_titles":
        from .buckets.bills import get_bill_titles
        return await get_bill_titles(ctx, **kwargs)
    elif operation == "get_bill_content":
        from .buckets.bills import get_bill_content
        return await get_bill_content(ctx, **kwargs)
    elif operation == "get_bill_summaries":
        from .buckets.bills import get_bill_summaries
        return await get_bill_summaries(ctx, **kwargs)
    elif operation == "get_recent_bills":
        from .buckets.bills import get_recent_bills
        return await get_recent_bills(ctx, **kwargs)
    elif operation == "get_bills_by_date_range":
        from .buckets.bills import get_bills_by_date_range
        return await get_bills_by_date_range(ctx, **kwargs)
    elif operation == "get_bill_actions":
        from .buckets.bills import get_bill_actions
        return await get_bill_actions(ctx, **kwargs)
    elif operation == "get_bill_amendments":
        from .buckets.bills import get_bill_amendments
        return await get_bill_amendments(ctx, **kwargs)
    elif operation == "get_bill_committees":
        from .buckets.bills import get_bill_committees
        return await get_bill_committees(ctx, **kwargs)
    elif operation == "get_bill_cosponsors":
        from .buckets.bills import get_bill_cosponsors
        return await get_bill_cosponsors(ctx, **kwargs)
    elif operation == "get_bill_related_bills":
        from .buckets.bills import get_bill_related_bills
        return await get_bill_related_bills(ctx, **kwargs)
    elif operation == "get_bill_subjects":
        from .buckets.bills import get_bill_subjects
        return await get_bill_subjects(ctx, **kwargs)
    else:
        raise ToolError(f"Unknown bills operation: {operation}")

@mcp.tool(
    "bills",
    title="Congressional Bills - Comprehensive bill operations",
    outputSchema=LegislationHubResponse
)
async def bills(
    ctx: Context,
    operation: str,
    # Core bill identification
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    bill_number: Optional[int] = None,
    # Filtering and pagination
    limit: Optional[int] = None,
    sort: Optional[str] = None,
    format: Optional[str] = None,
    offset: Optional[int] = None,
    # Date filtering
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    days_back: Optional[int] = None,
    # Text and content
    version: Optional[str] = None,
    chunk_number: Optional[int] = None,
    chunk_size: Optional[int] = None,
) -> str:
    """
    Comprehensive Bills Tool - All bill operations in one focused interface.
    
    CORE OPERATIONS:
    • Search & Discovery: search_bills, get_bills, get_recent_bills
    • Details & Metadata: get_bill_details, get_bill_titles, get_bill_subjects
    • Text & Content: get_bill_text, get_bill_text_versions, get_bill_content
    • Summaries: get_bill_summaries
    • Relationships: get_bill_related_bills, get_bill_amendments
    • Legislative Process: get_bill_actions, get_bill_committees, get_bill_cosponsors
    • Date-Based: get_bills_by_date_range
    
    SEARCH OPERATIONS:
    - search_bills: Find bills by keywords and filters
    - get_bills: Core API access with flexible filtering
    - get_recent_bills: Recently active bills without keywords
    - get_bills_by_date_range: Bills within specific date range
    
    DETAILS OPERATIONS:
    - get_bill_details: Complete bill information and status
    - get_bill_titles: Official and short titles
    - get_bill_subjects: Policy areas and legislative subjects
    
    CONTENT OPERATIONS:
    - get_bill_text: Full bill text with version control
    - get_bill_text_versions: Available text versions
    - get_bill_content: Actual content with chunking support
    - get_bill_summaries: Professional summaries
    
    RELATIONSHIP OPERATIONS:
    - get_bill_related_bills: Companion and related legislation
    - get_bill_amendments: Amendments to this bill
    - get_bill_committees: Committee assignments and activity
    - get_bill_cosponsors: Sponsors and cosponsors
    - get_bill_actions: Complete legislative history
    
    Args:
        operation: Specific operation to perform (see list above)
        keywords: Search keywords for content and metadata
        congress: Congress number (118 for current, 119 for next)
        bill_type: hr, s, hjres, sjres, hconres, sconres, hres, sres
        bill_number: Specific bill number within type and congress
        limit: Results limit (max 250 for API compliance)
        sort: updateDate+desc (newest first) or updateDate+asc
        fromDateTime/toDateTime: Date range (YYYY-MM-DDTHH:MM:SSZ)
        version: Text version for content operations
        
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
        raw_response = await route_bills_operation(ctx, operation, **operation_kwargs)
        return raw_response
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in bills operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing bills operation '{operation}': {str(e)}")