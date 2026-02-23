"""
Individual Legislation Tools - Replaces legislation_hub.py bucket system

Each legislative operation is now its own MCP tool with proper typing,
structured Pydantic responses, and clear documentation.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..models.responses import LegislationHubResponse, BillSummary, AmendmentSummary

logger = logging.getLogger(__name__)

# Bills Tools

@mcp.tool("search_bills")
async def search_bills(
    ctx: Context,
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    limit: int = 20,
    sort: str = "updateDate+desc"
) -> LegislationHubResponse:
    """
    Search for bills by keywords, congress, or type.
    
    Args:
        ctx: Context for API requests
        keywords: Keywords to search for in bill text and metadata
        congress: Congress number (e.g., 118 for 118th Congress)
        bill_type: Bill type (HR, S, HJRES, SJRES, HCONRES, SCONRES, HRES, SRES)
        limit: Maximum number of results to return (max 250)
        sort: Sort order (updateDate+desc, updateDate+asc, etc.)
    
    Returns:
        Structured response with bill summaries and metadata
    """
    try:
        from .buckets.bills import search_bills as _search_bills
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _search_bills(
            ctx, 
            keywords=keywords,
            congress=congress, 
            bill_type=bill_type,
            limit=limit,
            sort=sort
        )
        return _convert_to_structured_response(raw_response, "search_bills")
    except Exception as e:
        logger.error(f"Error in search_bills: {e}")
        return LegislationHubResponse(
            success=False,
            operation="search_bills",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error searching bills: {str(e)}",
            next_steps=[]
        )

@mcp.tool("get_bills")
async def get_bills(
    ctx: Context,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    limit: int = 20,
    sort: str = "updateDate+desc",
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None
) -> LegislationHubResponse:
    """
    Get bills with optional filtering by congress, type, and date range.
    
    Args:
        ctx: Context for API requests
        congress: Congress number to filter by
        bill_type: Bill type to filter by (HR, S, etc.)
        limit: Maximum number of results (max 250)
        sort: Sort order for results
        fromDateTime: Start date filter (YYYY-MM-DDTHH:MM:SSZ)
        toDateTime: End date filter (YYYY-MM-DDTHH:MM:SSZ)
    
    Returns:
        Structured response with bill listings
    """
    try:
        from .buckets.bills import get_bills as _get_bills
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _get_bills(
            ctx,
            congress=congress,
            bill_type=bill_type,
            limit=limit,
            sort=sort,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime
        )
        return _convert_to_structured_response(raw_response, "get_bills")
    except Exception as e:
        logger.error(f"Error in get_bills: {e}")
        return LegislationHubResponse(
            success=False,
            operation="get_bills",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error retrieving bills: {str(e)}",
            next_steps=[]
        )

@mcp.tool("get_bill_details")
async def get_bill_details(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> LegislationHubResponse:
    """
    Get detailed information about a specific bill.
    
    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 118)
        bill_type: Type of bill (HR, S, HJRES, etc.)
        bill_number: Bill number within the congress and type
    
    Returns:
        Detailed bill information including sponsors, actions, status
    """
    try:
        from .buckets.bills import get_bill_details as _get_bill_details
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _get_bill_details(
            ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number
        )
        return _convert_to_structured_response(raw_response, "get_bill_details")
    except Exception as e:
        logger.error(f"Error in get_bill_details: {e}")
        return LegislationHubResponse(
            success=False,
            operation="get_bill_details",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error retrieving bill details: {str(e)}",
            next_steps=[]
        )

@mcp.tool("get_bill_text")
async def get_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    version: Optional[str] = None
) -> LegislationHubResponse:
    """
    Get the full text of a bill.
    
    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type (HR, S, etc.)
        bill_number: Bill number
        version: Specific version of bill text (if not provided, gets latest)
    
    Returns:
        Bill text content and metadata
    """
    try:
        from .buckets.bills import get_bill_text as _get_bill_text
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _get_bill_text(
            ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            version=version
        )
        return _convert_to_structured_response(raw_response, "get_bill_text")
    except Exception as e:
        logger.error(f"Error in get_bill_text: {e}")
        return LegislationHubResponse(
            success=False,
            operation="get_bill_text",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error retrieving bill text: {str(e)}",
            next_steps=[]
        )

@mcp.tool("get_bill_actions")
async def get_bill_actions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20
) -> LegislationHubResponse:
    """
    Get legislative actions taken on a bill.
    
    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type
        bill_number: Bill number
        limit: Maximum number of actions to return
    
    Returns:
        List of legislative actions with dates and descriptions
    """
    try:
        from .buckets.bills import get_bill_actions as _get_bill_actions
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _get_bill_actions(
            ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_bill_actions")
    except Exception as e:
        logger.error(f"Error in get_bill_actions: {e}")
        return LegislationHubResponse(
            success=False,
            operation="get_bill_actions",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error retrieving bill actions: {str(e)}",
            next_steps=[]
        )

# Amendment Tools

@mcp.tool("search_amendments")
async def search_amendments(
    ctx: Context,
    congress: Optional[int] = None,
    amendment_type: Optional[str] = None,
    limit: int = 20,
    sort: str = "updateDate+desc"
) -> LegislationHubResponse:
    """
    Search for amendments by congress or type.
    
    Args:
        ctx: Context for API requests
        congress: Congress number to filter by
        amendment_type: Amendment type (HAMDT, SAMDT, etc.)
        limit: Maximum number of results
        sort: Sort order for results
    
    Returns:
        List of matching amendments with metadata
    """
    try:
        from .buckets.amendments import search_amendments as _search_amendments
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _search_amendments(
            ctx,
            congress=congress,
            amendment_type=amendment_type,
            limit=limit,
            sort=sort
        )
        return _convert_to_structured_response(raw_response, "search_amendments")
    except Exception as e:
        logger.error(f"Error in search_amendments: {e}")
        return LegislationHubResponse(
            success=False,
            operation="search_amendments",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error searching amendments: {str(e)}",
            next_steps=[]
        )

@mcp.tool("get_amendment_details")
async def get_amendment_details(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> LegislationHubResponse:
    """
    Get detailed information about a specific amendment.
    
    Args:
        ctx: Context for API requests
        congress: Congress number
        amendment_type: Type of amendment (HAMDT, SAMDT)
        amendment_number: Amendment number
    
    Returns:
        Detailed amendment information including purpose, sponsor, status
    """
    try:
        from .buckets.amendments import get_amendment_details as _get_amendment_details
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _get_amendment_details(
            ctx,
            congress=congress,
            amendment_type=amendment_type,
            amendment_number=amendment_number
        )
        return _convert_to_structured_response(raw_response, "get_amendment_details")
    except Exception as e:
        logger.error(f"Error in get_amendment_details: {e}")
        return LegislationHubResponse(
            success=False,
            operation="get_amendment_details",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error retrieving amendment details: {str(e)}",
            next_steps=[]
        )

# Treaty Tools

@mcp.tool("search_treaties")
async def search_treaties(
    ctx: Context,
    congress: Optional[int] = None,
    limit: int = 20,
    sort: str = "updateDate+desc"
) -> LegislationHubResponse:
    """
    Search for treaties by congress.
    
    Args:
        ctx: Context for API requests
        congress: Congress number to filter by
        limit: Maximum number of results
        sort: Sort order for results
    
    Returns:
        List of treaties with metadata
    """
    try:
        from .treaties import search_treaties as _search_treaties
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _search_treaties(
            ctx,
            congress=congress,
            limit=limit,
            sort=sort
        )
        return _convert_to_structured_response(raw_response, "search_treaties")
    except Exception as e:
        logger.error(f"Error in search_treaties: {e}")
        return LegislationHubResponse(
            success=False,
            operation="search_treaties",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error searching treaties: {str(e)}",
            next_steps=[]
        )

# Summary Tools

@mcp.tool("search_summaries")
async def search_summaries(
    ctx: Context,
    congress: Optional[int] = None,
    limit: int = 20,
    sort: str = "updateDate+desc"
) -> LegislationHubResponse:
    """
    Search for bill summaries.
    
    Args:
        ctx: Context for API requests
        congress: Congress number to filter by
        limit: Maximum number of results
        sort: Sort order for results
    
    Returns:
        List of bill summaries
    """
    try:
        from .summaries import search_summaries as _search_summaries
        from .buckets.legislation_hub import _convert_to_structured_response
        
        raw_response = await _search_summaries(
            ctx,
            congress=congress,
            limit=limit,
            sort=sort
        )
        return _convert_to_structured_response(raw_response, "search_summaries")
    except Exception as e:
        logger.error(f"Error in search_summaries: {e}")
        return LegislationHubResponse(
            success=False,
            operation="search_summaries",
            results_count=0,
            bills=[],
            amendments=[],
            summary=f"Error searching summaries: {str(e)}",
            next_steps=[]
        )