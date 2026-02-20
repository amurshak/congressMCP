"""
Congressional Research and Professional - Consolidated MCP bucket tool for professional research.

This bucket consolidates specialized research tools into a single interface with operation-based routing.

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
from ...models.responses import ResearchProfessionalResponse, ErrorResponse, ResearchSummary

# Import access control utilities
from ...core.auth import get_user_tier_from_context, SubscriptionTier

logger = logging.getLogger(__name__)

def _convert_to_structured_response(raw_response: str, operation: str) -> ResearchProfessionalResponse:
    """Convert raw string response to structured ResearchProfessionalResponse."""
    import json
    
    try:
        if isinstance(raw_response, str):
            import re
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                return ResearchProfessionalResponse(
                    success=True,
                    operation=operation,
                    results_count=0,
                    research_materials=[],
                    summary=raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                    recommended_reading=[]
                )
        else:
            data = raw_response
        
        research_materials = []
        results_count = 0
        
        if isinstance(data, dict):
            # Handle research materials (CRS reports, committee reports, etc.)
            if 'reports' in data:
                for report_data in data.get('reports', []):
                    if isinstance(report_data, dict):
                        research_materials.append(ResearchSummary(
                            title=report_data.get('title', ''),
                            type=report_data.get('reportType', 'Research Document'),
                            date=report_data.get('date'),
                            summary=report_data.get('summary'),
                            topics=report_data.get('policyArea', []),
                            url=report_data.get('url')
                        ))
            
            # Handle other research document types
            if 'crsReports' in data:
                for crs_data in data.get('crsReports', []):
                    if isinstance(crs_data, dict):
                        research_materials.append(ResearchSummary(
                            title=crs_data.get('title', ''),
                            type='CRS Report',
                            date=crs_data.get('date'),
                            summary=crs_data.get('summary'),
                            topics=crs_data.get('topics', []),
                            url=crs_data.get('url')
                        ))
            
            results_count = len(research_materials)
            
        return ResearchProfessionalResponse(
            success=True,
            operation=operation,
            results_count=results_count,
            research_materials=research_materials,
            summary=f"Found {len(research_materials)} research materials",
            recommended_reading=[]
        )
        
    except Exception as e:
        logger.error(f"Error converting response to structured format: {e}")
        return ResearchProfessionalResponse(
            success=False,
            operation=operation,
            results_count=0,
            research_materials=[],
            summary=f"Error processing response: {str(e)}",
            recommended_reading=[]
        )

# Define operation access levels
# Note: Both FREE_OPERATIONS and PAID_OPERATIONS currently contain the same operations,
# reflecting universal access model where all operations are available to all tiers.
# Access control infrastructure maintained for potential future differentiation.
FREE_OPERATIONS = {
    # All research and professional operations now available for free tier
    "get_congress_info",
    # Professional research services
    "search_crs_reports",
    "get_congress_info_enhanced",
    "search_congresses",
    "get_congress_statistics",
    "get_legislative_analysis"
}

PAID_OPERATIONS = {
    # Professional research services
    "search_crs_reports",
    "get_congress_info_enhanced",  # Enhanced congress analytics
    "search_congresses",           # Advanced congress search
    "get_congress_statistics",     # Congress analytics (if exists)
    "get_legislative_analysis"     # Advanced legislative analysis (if exists)
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

async def route_research_and_professional_operation(ctx: Context, operation: str, **kwargs) -> ResearchProfessionalResponse:
    """Route operation to appropriate internal function."""
    
    # Congress information operations
    if operation == "get_congress_info":
        from ..congress_info import get_congress_info
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "search_congresses":
        from ..congress_info import search_congresses
        raw_response = await search_congresses(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    elif operation == "get_congress_info_enhanced":
        # Enhanced version with additional analytics
        from ..congress_info import get_congress_info
        # Add detailed=True for enhanced mode
        kwargs['detailed'] = True
        raw_response = await get_congress_info(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Professional research operations
    elif operation == "search_crs_reports":
        from ..crs_reports import search_crs_reports
        raw_response = await search_crs_reports(ctx, **kwargs)
        return _convert_to_structured_response(raw_response, operation)
    
    # Future professional analytics operations
    elif operation == "get_congress_statistics":
        # Placeholder for future implementation
        raise ToolError("Congress statistics analysis feature coming soon - contact support for early access")
    elif operation == "get_legislative_analysis":
        # Placeholder for future implementation  
        raise ToolError("Advanced legislative analysis feature coming soon - contact support for early access")
    
    else:
        raise ToolError(f"Unknown operation: {operation}")

@mcp.tool("research_and_professional")
async def research_and_professional(
    ctx: Context,
    operation: str,
    # Congress information parameters
    congress: Optional[int] = None,
    current: Optional[bool] = None,
    limit: Optional[int] = None,
    detailed: Optional[bool] = None,
    format_type: Optional[str] = None,
    # Congress search parameters
    keywords: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    # CRS report parameters
    report_number: Optional[str] = None
) -> str:
    """
    Congressional Research and Professional - Professional research and analytics.
    
    This specialized bucket provides access to professional research services and 
    enhanced congressional analytics.
    
    ALL operations are available to ALL users regardless of tier - only usage limits differ:
    - FREE (500), PRO (5,000), ENTERPRISE (100,000) calls/month
    
    AVAILABLE OPERATIONS:
    Basic Congress Operations:
    - get_congress_info: Basic Congress information
    
    Professional Research Services:
    - search_crs_reports: Search Congressional Research Service reports
    - get_congress_info_enhanced: Enhanced Congress analytics with detailed metadata
    - search_congresses: Advanced Congress search with historical analysis
    - get_congress_statistics: Statistical analysis across Congresses (coming soon)
    - get_legislative_analysis: Advanced legislative trend analysis (coming soon)
    
    Args:
        operation: The specific operation to perform
        **kwargs: Operation-specific parameters:
        
        Congress Information Parameters:
        - congress: Congress number (e.g., 118)
        - current: Get current Congress information
        - limit: Maximum results for Congress lists
        - detailed: Include detailed analytics and metadata
        - format_type: Output format ('markdown' or 'table')
        
        Congress Search Parameters:
        - keywords: Keywords for Congress search
        - start_year: Start year for historical search
        - end_year: End year for historical search
        
        CRS Report Parameters:
        - report_number: Specific CRS report number
        - keywords: Keywords for CRS report search
    
    Returns:
        Operation results as formatted string with professional-grade analysis
        
    Raises:
        ToolError: If operation is unknown or user lacks required access
    
    Examples:
        Get basic Congress information:
        {
            "operation": "get_congress_info",
            "congress": 118
        }
        
        Search CRS reports:
        {
            "operation": "search_crs_reports",
            "keywords": "climate policy",
            "limit": 10
        }
        
        Get enhanced Congress analytics:
        {
            "operation": "get_congress_info_enhanced",
            "congress": 118,
            "detailed": true,
            "format_type": "markdown"
        }
        
        Search historical Congresses:
        {
            "operation": "search_congresses",
            "start_year": 2000,
            "end_year": 2024,
            "keywords": "healthcare reform"
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
            'congress': congress,
            'current': current,
            'limit': limit,
            'detailed': detailed,
            'format_type': format_type,
            'keywords': keywords,
            'start_year': start_year,
            'end_year': end_year,
            'report_number': report_number
        }.items():
            if param_value is not None:
                operation_kwargs[param_name] = param_value
        
        # Route to appropriate internal function
        raw_response = await route_research_and_professional_operation(ctx, operation, **operation_kwargs)
        return _convert_to_structured_response(raw_response, operation)
        
    except ToolError:
        # Re-raise ToolError as-is (preserves access control messages)
        raise
    except Exception as e:
        logger.error(f"Error in research_and_professional operation '{operation}': {str(e)}")
        raise ToolError(f"Error executing operation '{operation}': {str(e)}")
