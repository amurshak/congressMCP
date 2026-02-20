"""
Amendments API - API-faithful public functions for Congressional amendments.

This module provides the public API for amendments operations, combining
helpers, processors, and formatters to create API-faithful functions.
"""

import logging
from typing import Optional
from mcp.server.fastmcp import Context
from .processors import AmendmentsDataProcessor
from .formatters import AmendmentsFormatter
from ....core.validators import ParameterValidator
from ....core.exceptions import format_error_response, APIErrorResponse
from ....core.response_utils import ResponseProcessor
from ....core.api_wrapper import DefensiveAPIWrapper

logger = logging.getLogger(__name__)

# Core API-faithful functions

async def get_amendments(
    ctx: Context,
    format: str = "json",
    offset: Optional[int] = None,
    limit: int = 20,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    sort: str = "updateDate+desc",
    congress: Optional[int] = None,
    amendment_type: Optional[str] = None
) -> str:
    """
    Get amendments from Congress.gov API - Core /amendment endpoint access.

    This is the missing foundation function that provides direct access to the
    Congress.gov /amendment endpoint with full API parameter support.

    Args:
        format: Response format (json or xml) - API-faithful parameter
        offset: Starting record for pagination (0-based) - API-faithful parameter
        limit: Maximum number of results (max 250 for API compliance)
        fromDateTime: Start date filter (YYYY-MM-DDTHH:MM:SSZ) - API-faithful parameter
        toDateTime: End date filter (YYYY-MM-DDTHH:MM:SSZ) - API-faithful parameter
        sort: Sort order (updateDate+asc or updateDate+desc)
        congress: Congress number (e.g., 118, 119)
        amendment_type: Amendment type (samdt, hamdt)

    Returns:
        Formatted amendment results
    """
    try:
        # Build API parameters - all Congress.gov native parameters
        api_params = {
            'format': format,
            'limit': limit,
            'sort': sort
        }

        # Add optional API parameters if provided
        if offset is not None:
            api_params['offset'] = offset
        if fromDateTime is not None:
            api_params['fromDateTime'] = fromDateTime
        if toDateTime is not None:
            api_params['toDateTime'] = toDateTime

        # Build endpoint - API-faithful approach
        endpoint = "/amendment"
        if congress is not None:
            endpoint = f"/amendment/{congress}"
            if amendment_type is not None:
                endpoint = f"/amendment/{congress}/{amendment_type}"

        # Fetch data using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, api_params, timeout_override=15.0)

        # Extract amendments from response
        amendments = AmendmentsDataProcessor.extract_amendments_from_response(data)

        if not amendments:
            return "No amendments found for the specified criteria."

        # Apply deduplication (business logic)
        amendments = AmendmentsDataProcessor.deduplicate_amendments(amendments)

        # Format response (presentation logic)
        return AmendmentsFormatter.format_amendments_list(
            amendments,
            title="Congressional Amendments"
        )

    except Exception as e:
        logger.error(f"Error in get_amendments: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendments due to an unexpected error",
            suggestions=["Check your parameters", "Try again in a few moments"],
            error_code="AMENDMENTS_RETRIEVAL_FAILED"
        ))

async def search_amendments(
    ctx: Context,
    keywords: Optional[str] = None,  # Made optional for API fidelity
    congress: Optional[int] = None,
    amendment_type: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc",
    # API-faithful parameters
    format: str = "json",
    offset: Optional[int] = None,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None
) -> str:
    """
    Search for amendments with optional keyword filtering.

    This function combines the core get_amendments API access with optional
    keyword enhancement, making keywords optional for API fidelity.

    Args:
        keywords: Optional keywords to search for in amendment purpose and text
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        amendment_type: Optional amendment type (e.g., 'samdt', 'hamdt')
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        format: Response format (json or xml) - API-faithful parameter
        offset: Starting record for pagination - API-faithful parameter
        fromDateTime: Start date filter - API-faithful parameter
        toDateTime: End date filter - API-faithful parameter
    """
    # Parameter validation using reliability framework
    if congress is not None:
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(APIErrorResponse(
                error_type="validation",
                message=f"Invalid congress number: {congress_validation.error_message}",
                suggestions=congress_validation.suggestions,
                error_code="INVALID_CONGRESS_NUMBER"
            ))

    if amendment_type is not None:
        amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
        if not amendment_validation.is_valid:
            return format_error_response(APIErrorResponse(
                error_type="validation",
                message=f"Invalid amendment type: {amendment_validation.error_message}",
                suggestions=amendment_validation.suggestions,
                error_code="INVALID_AMENDMENT_TYPE"
            ))

    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))

    try:
        # Build API parameters - Congress.gov native parameters
        api_params = {
            'format': format,
            'limit': limit,
            'sort': sort
        }

        # Add optional API parameters
        if offset is not None:
            api_params['offset'] = offset
        if fromDateTime is not None:
            api_params['fromDateTime'] = fromDateTime
        if toDateTime is not None:
            api_params['toDateTime'] = toDateTime

        # If keywords provided, add as query parameter for Congress.gov API
        if keywords:
            api_params['query'] = keywords

        # Build endpoint - API-faithful approach
        endpoint = "/amendment"
        if congress is not None:
            endpoint = f"/amendment/{congress}"
            if amendment_type is not None:
                endpoint = f"/amendment/{congress}/{amendment_type}"

        # Fetch data using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, api_params, timeout_override=15.0)

        # Extract amendments from response
        amendments = AmendmentsDataProcessor.extract_amendments_from_response(data)

        if not amendments:
            search_term = f"'{keywords}'" if keywords else "the specified criteria"
            return f"No amendments found matching {search_term}."

        # Apply deduplication and processing
        original_count = len(amendments)
        amendments = AmendmentsDataProcessor.deduplicate_amendments(amendments)
        duplicates_removed = original_count - len(amendments)

        # Apply pagination
        amendments = ResponseProcessor.paginate_results(amendments, limit)

        # Format results
        title = f"Amendments Matching '{keywords}'" if keywords else "Congressional Amendments"
        return AmendmentsFormatter.format_amendments_list(
            amendments,
            title=title,
            duplicates_removed=duplicates_removed
        )

    except Exception as e:
        logger.error(f"Error in search_amendments: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to search amendments due to an unexpected error",
            suggestions=["Try simplifying your search terms", "Check your internet connection", "Try again in a few moments"],
            error_code="SEARCH_FAILED"
        ))

# Specific amendment functions

async def get_amendment_details(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> str:
    """
    Get detailed information about a specific amendment.

    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))

    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))

    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))

    try:
        # Build endpoint for specific amendment
        endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}"

        # Fetch amendment details using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {}, timeout_override=10.0)

        # Handle different data structures for amendment
        amendment_data = data.get("amendment", {})

        # If amendment_data is empty, try to use the data directly
        if not amendment_data and isinstance(data, dict):
            # Some API responses don't have an 'amendment' wrapper
            if 'number' in data or 'type' in data or 'congress' in data:
                amendment_data = data

        if not amendment_data:
            return format_error_response(APIErrorResponse(
                error_type="not_found",
                message=f"Amendment {amendment_type.upper()} {amendment_number} not found in Congress {congress}",
                suggestions=[
                    "Verify the amendment number is correct",
                    "Check if the amendment type (samdt/hamdt) is correct",
                    "Try searching for amendments to find the correct number"
                ],
                error_code="AMENDMENT_NOT_FOUND"
            ))

        return AmendmentsFormatter.format_amendment_details(amendment_data)

    except Exception as e:
        logger.error(f"Error in get_amendment_details: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment details due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check your internet connection",
                "Try again in a few moments"
            ],
            error_code="DETAILS_RETRIEVAL_FAILED"
        ))

# Sub-resource functions

async def get_amendment_actions(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int,
    limit: int = 10
) -> str:
    """
    Get actions for a specific amendment.

    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
        limit: Maximum number of actions to return (default: 10)
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))

    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))

    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))

    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=100)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))

    try:
        # Build endpoint for amendment actions
        endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/actions"

        # Fetch amendment actions using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {"limit": limit}, timeout_override=10.0)

        actions = data.get("actions", [])
        if not actions:
            return f"No actions found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."

        # Apply deduplication and pagination
        original_count = len(actions)
        actions = ResponseProcessor.deduplicate_results(actions, ["actionDate", "text"])
        actions = ResponseProcessor.paginate_results(actions, limit)
        duplicates_removed = original_count - len(actions)

        return AmendmentsFormatter.format_amendment_actions_list(
            actions, amendment_type, amendment_number, congress, duplicates_removed
        )

    except Exception as e:
        logger.error(f"Error in get_amendment_actions: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment actions due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_ACTIONS_RETRIEVAL_FAILED"
        ))

async def get_amendment_sponsors(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int
) -> str:
    """
    Get cosponsors for a specific amendment.

    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))

    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))

    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))

    try:
        # Build endpoint for amendment sponsors
        endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/cosponsors"

        # Fetch amendment sponsors using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {}, timeout_override=10.0)

        # Handle different data structures for cosponsors
        cosponsors_data = data.get("cosponsors", {})

        # Extract cosponsor items based on the data structure
        if isinstance(cosponsors_data, list):
            cosponsors = cosponsors_data
        elif isinstance(cosponsors_data, dict) and "item" in cosponsors_data:
            items = cosponsors_data["item"]
            if isinstance(items, list):
                cosponsors = items
            else:
                cosponsors = [items] if items else []
        else:
            cosponsors = []

        if not cosponsors:
            return f"No cosponsors found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."

        # Apply deduplication
        original_count = len(cosponsors)
        cosponsors = ResponseProcessor.deduplicate_results(cosponsors, ["bioguideId", "name"])
        duplicates_removed = original_count - len(cosponsors)

        return AmendmentsFormatter.format_amendment_sponsors_list(
            cosponsors, amendment_type, amendment_number, congress, duplicates_removed
        )

    except Exception as e:
        logger.error(f"Error in get_amendment_sponsors: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment sponsors due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_SPONSORS_RETRIEVAL_FAILED"
        ))

async def get_amendment_amendments(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int,
    limit: int = 10
) -> str:
    """
    Get amendments to a specific amendment.

    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
        limit: Maximum number of amendments to return (default: 10)
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))

    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))

    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))

    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))

    try:
        # Build endpoint for amendments to amendment
        endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/amendments"

        # Fetch amendment amendments using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {"limit": limit}, timeout_override=10.0)

        # Extract amendments from response
        amendments = AmendmentsDataProcessor.extract_amendments_from_response(data)

        if not amendments:
            return f"No amendments found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."

        # Apply deduplication and pagination
        original_count = len(amendments)
        amendments = AmendmentsDataProcessor.deduplicate_amendments(amendments)
        duplicates_removed = original_count - len(amendments)

        # Format results
        title = f"Amendments to {amendment_type.upper()} {amendment_number} - {congress}th Congress"
        return AmendmentsFormatter.format_amendments_list(
            amendments,
            title=title,
            duplicates_removed=duplicates_removed
        )

    except Exception as e:
        logger.error(f"Error in get_amendment_amendments: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendments to amendment due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_AMENDMENTS_RETRIEVAL_FAILED"
        ))

async def get_amendment_text(
    ctx: Context,
    congress: int,
    amendment_type: str,
    amendment_number: int,
    limit: int = 10
) -> str:
    """
    Get text versions for a specific amendment (117th Congress and onwards).

    Args:
        congress: Congress number (117th Congress and onwards, e.g., 117)
        amendment_type: Amendment type (e.g., 'samdt' for Senate Amendment, 'hamdt' for House Amendment)
        amendment_number: Amendment number
        limit: Maximum number of text versions to return (default: 10)
    """
    # Parameter validation using reliability framework
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid congress number: {congress_validation.error_message}",
            suggestions=congress_validation.suggestions,
            error_code="INVALID_CONGRESS_NUMBER"
        ))

    # Special validation for amendment text endpoint (117th Congress onwards)
    if congress < 117:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment text is only available for the 117th Congress and onwards",
            suggestions=["Use congress number 117 or higher"],
            error_code="CONGRESS_TOO_OLD_FOR_TEXT"
        ))

    amendment_validation = ParameterValidator.validate_amendment_type(amendment_type)
    if not amendment_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid amendment type: {amendment_validation.error_message}",
            suggestions=amendment_validation.suggestions,
            error_code="INVALID_AMENDMENT_TYPE"
        ))

    if amendment_number <= 0:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message="Amendment number must be a positive integer",
            suggestions=["Use a positive number like 1, 2, 3, etc."],
            error_code="INVALID_AMENDMENT_NUMBER"
        ))

    limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
    if not limit_validation.is_valid:
        return format_error_response(APIErrorResponse(
            error_type="validation",
            message=f"Invalid limit: {limit_validation.error_message}",
            suggestions=limit_validation.suggestions,
            error_code="INVALID_LIMIT"
        ))

    try:
        # Build endpoint for amendment text
        endpoint = f"/amendment/{congress}/{amendment_type}/{amendment_number}/text"

        # Fetch amendment text using defensive API wrapper
        data = await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, {"limit": limit}, timeout_override=10.0)

        # Extract text versions from response
        text_versions = data.get("textVersions", [])
        if not text_versions:
            return f"No text versions found for {amendment_type.upper()} {amendment_number} in the {congress}th Congress."

        # Apply deduplication and pagination
        original_count = len(text_versions)
        text_versions = ResponseProcessor.deduplicate_results(text_versions, ["type", "date"])
        text_versions = ResponseProcessor.paginate_results(text_versions, limit)
        duplicates_removed = original_count - len(text_versions)

        # Format results
        result = [f"# Text Versions for {amendment_type.upper()} {amendment_number} - {congress}th Congress"]
        if duplicates_removed > 0:
            result.append(f"*({duplicates_removed} duplicate text versions removed)*")
        result.append(f"Total: {len(text_versions)} text versions\n")

        for text_version in text_versions:
            version_type = text_version.get("type", "Unknown")
            date = text_version.get("date", "Unknown date")
            url = text_version.get("url", "No URL available")

            result.append(f"- **{version_type}** ({date})")
            result.append(f"  URL: {url}")

        return "\n".join(result)

    except Exception as e:
        logger.error(f"Error in get_amendment_text: {str(e)}")
        return format_error_response(APIErrorResponse(
            error_type="api_failure",
            message="Failed to retrieve amendment text due to an unexpected error",
            suggestions=[
                "Verify the amendment exists",
                "Check amendment type and number are correct",
                "Ensure congress is 117 or higher",
                "Try again in a few moments"
            ],
            error_code="AMENDMENT_TEXT_RETRIEVAL_FAILED"
        ))