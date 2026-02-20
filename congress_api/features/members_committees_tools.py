"""
Individual Members & Committees Tools - Replaces members_and_committees.py bucket system

Each member and committee operation is now its own MCP tool with proper typing,
structured Pydantic responses, and clear documentation.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..models.responses import MembersCommitteesResponse, MemberSummary, CommitteeSummary

logger = logging.getLogger(__name__)

# Member Tools

@mcp.tool("search_members")
async def search_members(
    ctx: Context,
    name: Optional[str] = None,
    state: Optional[str] = None,
    party: Optional[str] = None,
    chamber: Optional[str] = None,
    current_member: Optional[bool] = None,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Search for members of Congress by various criteria.
    
    Args:
        ctx: Context for API requests
        name: Member name to search for (partial matches supported)
        state: State code (e.g., 'CA', 'NY', 'TX')
        party: Political party ('D', 'R', 'I')
        chamber: Chamber ('House' or 'Senate')
        current_member: Whether to only show current members (True/False)
        limit: Maximum number of results to return
    
    Returns:
        Structured response with member information and metadata
    """
    try:
        from .members import search_members as _search_members
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _search_members(
            ctx,
            name=name,
            state=state,
            party=party,
            chamber=chamber,
            current_member=current_member,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "search_members")
    except Exception as e:
        logger.error(f"Error in search_members: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="search_members",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error searching members: {str(e)}",
            context="Search members operation failed"
        )

@mcp.tool("get_member_details")
async def get_member_details(
    ctx: Context,
    bioguide_id: str
) -> MembersCommitteesResponse:
    """
    Get detailed information about a specific member of Congress.
    
    Args:
        ctx: Context for API requests
        bioguide_id: Unique bioguide identifier for the member (e.g., 'B000944')
    
    Returns:
        Detailed member information including biographical data, terms served, etc.
    """
    try:
        from .members import get_member_details as _get_member_details
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_member_details(ctx, bioguide_id=bioguide_id)
        return _convert_to_structured_response(raw_response, "get_member_details")
    except Exception as e:
        logger.error(f"Error in get_member_details: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_member_details",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving member details: {str(e)}",
            context=f"Get details for member {bioguide_id} failed"
        )

@mcp.tool("get_member_sponsored_legislation")
async def get_member_sponsored_legislation(
    ctx: Context,
    bioguide_id: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get legislation sponsored by a specific member of Congress.
    
    Args:
        ctx: Context for API requests
        bioguide_id: Unique bioguide identifier for the member
        limit: Maximum number of sponsored bills to return
    
    Returns:
        List of bills and resolutions sponsored by the member
    """
    try:
        from .members import get_member_sponsored_legislation as _get_member_sponsored_legislation
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_member_sponsored_legislation(
            ctx, 
            bioguide_id=bioguide_id,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_member_sponsored_legislation")
    except Exception as e:
        logger.error(f"Error in get_member_sponsored_legislation: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_member_sponsored_legislation",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving sponsored legislation: {str(e)}",
            context=f"Get sponsored legislation for member {bioguide_id} failed"
        )

@mcp.tool("get_member_cosponsored_legislation")
async def get_member_cosponsored_legislation(
    ctx: Context,
    bioguide_id: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get legislation cosponsored by a specific member of Congress.
    
    Args:
        ctx: Context for API requests
        bioguide_id: Unique bioguide identifier for the member
        limit: Maximum number of cosponsored bills to return
    
    Returns:
        List of bills and resolutions cosponsored by the member
    """
    try:
        from .members import get_member_cosponsored_legislation as _get_member_cosponsored_legislation
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_member_cosponsored_legislation(
            ctx,
            bioguide_id=bioguide_id,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_member_cosponsored_legislation")
    except Exception as e:
        logger.error(f"Error in get_member_cosponsored_legislation: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_member_cosponsored_legislation", 
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving cosponsored legislation: {str(e)}",
            context=f"Get cosponsored legislation for member {bioguide_id} failed"
        )

@mcp.tool("get_members_by_congress")
async def get_members_by_congress(
    ctx: Context,
    congress: int,
    current_member: Optional[bool] = None,
    limit: int = 50
) -> MembersCommitteesResponse:
    """
    Get members who served in a specific Congress.
    
    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 118 for 118th Congress)
        current_member: Whether to only show current members
        limit: Maximum number of members to return
    
    Returns:
        List of members who served in the specified Congress
    """
    try:
        from .members import get_members_by_congress as _get_members_by_congress
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_members_by_congress(
            ctx,
            congress=congress,
            current_member=current_member,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_members_by_congress")
    except Exception as e:
        logger.error(f"Error in get_members_by_congress: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_members_by_congress",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving members by congress: {str(e)}",
            context=f"Get members for Congress {congress} failed"
        )

@mcp.tool("get_members_by_state")
async def get_members_by_state(
    ctx: Context,
    state_code: str,
    current_member: Optional[bool] = True,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get members of Congress from a specific state.
    
    Args:
        ctx: Context for API requests
        state_code: Two-letter state code (e.g., 'CA', 'TX', 'NY')
        current_member: Whether to only show current members (defaults to True)
        limit: Maximum number of members to return
    
    Returns:
        List of members from the specified state
    """
    try:
        from .members import get_members_by_state as _get_members_by_state
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_members_by_state(
            ctx,
            state_code=state_code,
            current_member=current_member,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_members_by_state")
    except Exception as e:
        logger.error(f"Error in get_members_by_state: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_members_by_state",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving members by state: {str(e)}",
            context=f"Get members for state {state_code} failed"
        )

@mcp.tool("get_members_by_district")
async def get_members_by_district(
    ctx: Context,
    state_code: str,
    district: int,
    current_member: Optional[bool] = True
) -> MembersCommitteesResponse:
    """
    Get the member representing a specific congressional district.
    
    Args:
        ctx: Context for API requests
        state_code: Two-letter state code (e.g., 'CA', 'TX', 'NY')
        district: Congressional district number within the state
        current_member: Whether to only show current member (defaults to True)
    
    Returns:
        Member(s) representing the specified district
    """
    try:
        from .members import get_members_by_district as _get_members_by_district
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_members_by_district(
            ctx,
            state_code=state_code,
            district=district,
            current_member=current_member
        )
        return _convert_to_structured_response(raw_response, "get_members_by_district")
    except Exception as e:
        logger.error(f"Error in get_members_by_district: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_members_by_district",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving member by district: {str(e)}",
            context=f"Get member for {state_code}-{district} failed"
        )

@mcp.tool("get_members_by_congress_state_district")
async def get_members_by_congress_state_district(
    ctx: Context,
    congress: int,
    state_code: str,
    district: int
) -> MembersCommitteesResponse:
    """
    Get the member representing a specific congressional district in a specific Congress.
    
    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 118 for 118th Congress)
        state_code: Two-letter state code (e.g., 'CA', 'TX', 'NY')
        district: Congressional district number within the state
    
    Returns:
        Member who represented the specified district in the specified Congress
    """
    try:
        from .members import get_members_by_congress_state_district as _get_members_by_congress_state_district
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_members_by_congress_state_district(
            ctx,
            congress=congress,
            state_code=state_code,
            district=district
        )
        return _convert_to_structured_response(raw_response, "get_members_by_congress_state_district")
    except Exception as e:
        logger.error(f"Error in get_members_by_congress_state_district: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_members_by_congress_state_district",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving member by congress/state/district: {str(e)}",
            context=f"Get member for Congress {congress}, {state_code}-{district} failed"
        )

# Committee Tools

@mcp.tool("search_committees")
async def search_committees(
    ctx: Context,
    chamber: Optional[str] = None,
    committee_type: Optional[str] = None,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Search for congressional committees.
    
    Args:
        ctx: Context for API requests
        chamber: Chamber ('House', 'Senate', or 'Joint')
        committee_type: Type of committee ('Standing', 'Select', etc.)
        limit: Maximum number of committees to return
    
    Returns:
        List of matching committees with basic information
    """
    try:
        from .committees import search_committees as _search_committees
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _search_committees(
            ctx,
            chamber=chamber,
            committee_type=committee_type,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "search_committees")
    except Exception as e:
        logger.error(f"Error in search_committees: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="search_committees",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error searching committees: {str(e)}",
            context="Search committees operation failed"
        )

@mcp.tool("get_committee_bills")
async def get_committee_bills(
    ctx: Context,
    committee_code: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get bills referred to or reported by a specific committee.
    
    Args:
        ctx: Context for API requests
        committee_code: Official committee code (e.g., 'HSJU', 'SSJU')
        limit: Maximum number of bills to return
    
    Returns:
        List of bills associated with the committee
    """
    try:
        from .committees import get_committee_bills as _get_committee_bills
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_committee_bills(
            ctx,
            committee_code=committee_code,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_committee_bills")
    except Exception as e:
        logger.error(f"Error in get_committee_bills: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_committee_bills",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving committee bills: {str(e)}",
            context=f"Get bills for committee {committee_code} failed"
        )

@mcp.tool("get_committee_reports")
async def get_committee_reports(
    ctx: Context,
    committee_code: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get reports issued by a specific committee.
    
    Args:
        ctx: Context for API requests
        committee_code: Official committee code (e.g., 'HSJU', 'SSJU')
        limit: Maximum number of reports to return
    
    Returns:
        List of reports issued by the committee
    """
    try:
        from .committees import get_committee_reports as _get_committee_reports
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_committee_reports(
            ctx,
            committee_code=committee_code,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_committee_reports")
    except Exception as e:
        logger.error(f"Error in get_committee_reports: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_committee_reports",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving committee reports: {str(e)}",
            context=f"Get reports for committee {committee_code} failed"
        )

@mcp.tool("get_committee_communications")
async def get_committee_communications(
    ctx: Context,
    committee_code: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get communications (letters, statements) from a specific committee.
    
    Args:
        ctx: Context for API requests
        committee_code: Official committee code (e.g., 'HSJU', 'SSJU')
        limit: Maximum number of communications to return
    
    Returns:
        List of communications from the committee
    """
    try:
        from .committees import get_committee_communications as _get_committee_communications
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_committee_communications(
            ctx,
            committee_code=committee_code,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_committee_communications")
    except Exception as e:
        logger.error(f"Error in get_committee_communications: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_committee_communications",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving committee communications: {str(e)}",
            context=f"Get communications for committee {committee_code} failed"
        )

@mcp.tool("get_committee_nominations")
async def get_committee_nominations(
    ctx: Context,
    committee_code: str,
    limit: int = 20
) -> MembersCommitteesResponse:
    """
    Get nominations referred to a specific committee.
    
    Args:
        ctx: Context for API requests
        committee_code: Official committee code (e.g., 'HSJU', 'SSJU')
        limit: Maximum number of nominations to return
    
    Returns:
        List of nominations referred to the committee
    """
    try:
        from .committees import get_committee_nominations as _get_committee_nominations
        from .buckets.members_and_committees import _convert_to_structured_response
        
        raw_response = await _get_committee_nominations(
            ctx,
            committee_code=committee_code,
            limit=limit
        )
        return _convert_to_structured_response(raw_response, "get_committee_nominations")
    except Exception as e:
        logger.error(f"Error in get_committee_nominations: {e}")
        return MembersCommitteesResponse(
            success=False,
            operation="get_committee_nominations",
            results_count=0,
            members=[],
            committees=[],
            summary=f"Error retrieving committee nominations: {str(e)}",
            context=f"Get nominations for committee {committee_code} failed"
        )