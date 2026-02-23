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
from ..utils.bill_parser import parse_bill_reference, validate_bill_params

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
    # Flexible bill identification (NEW)
    bill_id: Optional[str] = None,
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
    
    FLEXIBLE BILL IDENTIFICATION (NEW):
    Use bill_id for natural language references like 'HR 1234', 'H.R. 1234, 118th Congress', 
    'hr1234-118', 'S 456', etc. Automatically parses to congress/bill_type/bill_number.
    
    CORE OPERATIONS:
    • Search & Discovery: search_bills, get_bills, get_recent_bills
    • Details & Metadata: get_bill_details, get_bill_titles, get_bill_subjects
    • Text & Content: get_bill_text, get_bill_text_versions, get_bill_content
    • Summaries: get_bill_summaries
    • Relationships: get_bill_related_bills, get_bill_amendments
    • Legislative Process: get_bill_actions, get_bill_committees, get_bill_cosponsors
    • Date-Based: get_bills_by_date_range
    
    Args:
        operation: Specific operation to perform (see list above)
        bill_id: Flexible bill reference (e.g., 'HR 1234', 'H.R. 1234, 118th Congress', 'hr1234-118')
                 Automatically parsed to populate congress, bill_type, bill_number
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
        
    Examples:
        Using flexible bill_id:
        {"operation": "get_bill_details", "bill_id": "HR 1234"}
        {"operation": "get_bill_details", "bill_id": "H.R. 1234, 118th Congress"}  
        {"operation": "get_bill_details", "bill_id": "hr1234-118"}
        
        Traditional parameters still work:
        {"operation": "get_bill_details", "congress": 118, "bill_type": "hr", "bill_number": 1234}
    """
    try:
        # Check operation access based on user tier
        check_operation_access(ctx, operation)
        
        # Handle flexible bill_id parsing
        parsed_congress = congress
        parsed_bill_type = bill_type
        parsed_bill_number = bill_number
        
        if bill_id:
            # Parse the flexible bill reference
            parse_result = parse_bill_reference(bill_id, default_congress=congress)
            
            if not parse_result['parse_success']:
                raise ToolError(f"Bill ID parsing failed: {parse_result['error_message']}")
            
            # Use parsed values if the explicit parameters weren't provided
            if parsed_congress is None and parse_result['congress'] is not None:
                parsed_congress = parse_result['congress']
            if parsed_bill_type is None and parse_result['bill_type'] is not None:
                parsed_bill_type = parse_result['bill_type']
            if parsed_bill_number is None and parse_result['bill_number'] is not None:
                parsed_bill_number = parse_result['bill_number']
            
            # Validate parsed parameters
            if parsed_bill_type and parsed_bill_number:
                is_valid, error_msg = validate_bill_params(parsed_bill_type, parsed_bill_number, parsed_congress)
                if not is_valid:
                    raise ToolError(f"Invalid bill parameters from '{bill_id}': {error_msg}")
        
        # Build kwargs dict from all provided parameters, using parsed values where appropriate
        operation_kwargs = {}
        for param_name, param_value in {
            'keywords': keywords,
            'congress': parsed_congress,
            'bill_type': parsed_bill_type,
            'bill_number': parsed_bill_number,
            'limit': limit,
            'sort': sort,
            'format': format,
            'offset': offset,
            'fromDateTime': fromDateTime,
            'toDateTime': toDateTime,
            'days_back': days_back,
            'version': version,
            'chunk_number': chunk_number,
            'chunk_size': chunk_size
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        raw_response = await route_bills_operation(ctx, operation, **operation_kwargs)
        return raw_response
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in bills operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing bills operation '{operation}': {str(e)}")