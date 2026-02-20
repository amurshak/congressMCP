"""
Congressional Records and Hearings - Consolidated MCP bucket tool for records and communications.

This bucket consolidates ~20 individual tools into a single interface with operation-based routing.

ALL operations are currently available to ALL users regardless of tier - only usage limits differ:
- FREE tier: All operations, 500 calls/month
- PRO tier: All operations, 5,000 calls/month  
- ENTERPRISE tier: All operations

Access control infrastructure maintained for potential future tier differentiation.
Operation-level access control ensures granular tier-based access within the bucket.
"""

import logging
from typing import Optional, Dict, Any
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from ...mcp_app import mcp
from ...models.responses import RecordsHearingsResponse, ErrorResponse, HearingSummary, RecordSummary

# Import access control utilities
from ...core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> RecordsHearingsResponse:
    """Convert raw string response to structured RecordsHearingsResponse."""
    import json
    
    try:
        if isinstance(raw_response, str):
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                return RecordsHearingsResponse(
                    success=True,
                    operation=operation,
                    results_count=0,
                    hearings=[],
                    records=[],
                    summary=raw_response[:500] + "..." if len(raw_response) > 500 else raw_response
                )
        else:
            data = raw_response
        
        hearings = []
        records = []
        results_count = 0
        
        if isinstance(data, dict):
            # Handle hearings
            if 'hearings' in data:
                for hearing_data in data.get('hearings', []):
                    if isinstance(hearing_data, dict):
                        hearings.append(HearingSummary(
                            congress=hearing_data.get('congress', 0),
                            chamber=hearing_data.get('chamber', ''),
                            jacket_number=hearing_data.get('jacketNumber', ''),
                            title=hearing_data.get('title', ''),
                            committee=hearing_data.get('committee', ''),
                            date=hearing_data.get('date'),
                            url=hearing_data.get('url')
                        ))
                        
            # Handle congressional records
            if 'records' in data:
                for record_data in data.get('records', []):
                    if isinstance(record_data, dict):
                        records.append(RecordSummary(
                            volume=record_data.get('volume', 0),
                            issue=record_data.get('issue', 0),
                            date=record_data.get('date', ''),
                            section=record_data.get('section', ''),
                            title=record_data.get('title', ''),
                            url=record_data.get('url')
                        ))
            
            results_count = len(hearings) + len(records)
            
        return RecordsHearingsResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            hearings=hearings,
            records=records,
            summary=f"Found {len(hearings)} hearings and {len(records)} records"
        )
        
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return RecordsHearingsResponse(
            success=False,
            operation=operation,
            results_count=0,
            hearings=[],
            records=[],
            summary=f"Error processing response: {str(e)}"
        )

# Define operation access levels
# Note: Both FREE_OPERATIONS and PAID_OPERATIONS currently contain the same operations,
# reflecting universal access model where all operations are available to all tiers.
# Access control infrastructure maintained for potential future differentiation.
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

async def route_records_and_hearings_operation(ctx: Context, operation: str, **kwargs) -> RecordsHearingsResponse:
    """Route operation to appropriate internal function."""
    
    # Congressional Record operations
    if operation == "search_congressional_record":
        from ..congressional_record import search_congressional_record
        raw_response = await search_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_daily_congressional_record":
        from ..daily_congressional_record import search_daily_congressional_record
        raw_response = await search_daily_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_bound_congressional_record":
        from ..bound_congressional_record import search_bound_congressional_record
        raw_response = await search_bound_congressional_record(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # House communication operations
    elif operation == "search_house_communications":
        from ..house_communications import search_house_communications
        raw_response = await search_house_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_communication_details":
        from ..house_communications import get_house_communication_details
        raw_response = await get_house_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # House requirements operations
    elif operation == "search_house_requirements":
        from ..house_requirements import search_house_requirements
        raw_response = await search_house_requirements(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_details":
        from ..house_requirements import get_house_requirement_details
        raw_response = await get_house_requirement_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_house_requirement_matching_communications":
        from ..house_requirements import get_house_requirement_matching_communications
        raw_response = await get_house_requirement_matching_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Senate communication operations
    elif operation == "search_senate_communications":
        from ..senate_communications import search_senate_communications
        raw_response = await search_senate_communications(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_senate_communication_details":
        from ..senate_communications import get_senate_communication_details
        raw_response = await get_senate_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Committee communication operations
    elif operation == "get_committee_communication_details":
        from ..committees import get_committee_communication_details
        raw_response = await get_committee_communication_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Hearing operations
    elif operation == "search_hearings":
        from ..hearings import search_hearings
        raw_response = await search_hearings(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress":
        from ..hearings import get_hearings_by_congress
        raw_response = await get_hearings_by_congress(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearings_by_congress_and_chamber":
        from ..hearings import get_hearings_by_congress_and_chamber
        raw_response = await get_hearings_by_congress_and_chamber(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_details":
        from ..hearings import get_hearing_details
        raw_response = await get_hearing_details(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_hearing_content":
        from ..hearings import get_hearing_content
        raw_response = await get_hearing_content(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
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
    
    This bucket provides access to congressional records, communications, and hearings.
    
    ALL operations are available to ALL users regardless of tier - only usage limits differ:
    - FREE (500), PRO (5,000), ENTERPRISE (100,000) calls/month
    
    AVAILABLE OPERATIONS:
    Congressional Records:
    - search_congressional_record: Search congressional record issues
    - search_daily_congressional_record: Search daily record issues
    - search_bound_congressional_record: Search bound record volumes
    
    House Communications:
    - search_house_communications: Search House communications
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
    - search_hearings: Search committee hearings
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
        
        Get hearing details:
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
        raw_response = await route_records_and_hearings_operation(ctx, operation, **operation_kwargs)
        return _convert_to_structured_response(raw_response, operation)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in records_and_hearings operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
