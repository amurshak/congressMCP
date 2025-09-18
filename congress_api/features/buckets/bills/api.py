"""
Bills API - Clean, API-faithful public functions.

This module provides the public API for bills operations that map directly
to Congress.gov endpoints while maintaining enhancement capabilities.
"""

from typing import Optional
import logging
from fastmcp import Context

# Import our modular components
from .helpers import fetch_bill_data, build_bill_endpoint, validate_api_parameters
from .processors import BillsDataProcessor
from .formatters import BillsFormatter

# Import existing reliability framework
from ....core.validators import ParameterValidator
from ....core.exceptions import CommonErrors, format_error_response

# Set up logger
logger = logging.getLogger(__name__)


# --- Core API-Faithful Functions ---

async def get_bills(
    ctx: Context,
    format: str = "json",
    offset: Optional[int] = None,
    limit: int = 20,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    sort: str = "updateDate+desc",
    congress: Optional[int] = None,
    bill_type: Optional[str] = None
) -> str:
    """
    Get bills using the core /bill endpoint - the MISSING foundation function.
    Maps directly to Congress.gov GET /bill API with zero abstraction.

    This function provides access to the core Congress.gov /bill endpoint
    that was missing from the original implementation.

    Args:
        ctx: Context for API requests
        format: Response format ('json' or 'xml')
        offset: Starting record (0-based pagination)
        limit: Maximum number of results (max 250)
        fromDateTime: Start date filter (YYYY-MM-DDTHH:MM:SSZ)
        toDateTime: End date filter (YYYY-MM-DDTHH:MM:SSZ)
        sort: Sort order ('updateDate+asc' or 'updateDate+desc')
        congress: Optional congress filter (changes endpoint to /bill/{congress})
        bill_type: Optional bill type filter (changes endpoint to /bill/{congress}/{billType})

    Returns:
        Formatted bills list or error message
    """
    try:
        # Validate API parameters
        api_validation = validate_api_parameters(
            format=format,
            offset=offset,
            limit=limit,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime,
            sort=sort
        )

        if not api_validation["valid"]:
            return format_error_response(CommonErrors.invalid_parameter(
                "api_params", api_validation, api_validation["error"]
            ))

        # Validate congress parameter if provided
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(CommonErrors.invalid_congress_number(congress))

        # Validate bill_type parameter if provided
        if bill_type is not None:
            bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_type_validation.is_valid:
                return format_error_response(CommonErrors.invalid_bill_type(bill_type))
            bill_type = bill_type_validation.sanitized_value

        # Use validated parameters
        api_params = api_validation["params"]

        # Core API call - direct Congress.gov endpoint mapping
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            **api_params
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Standard response formatting
        return BillsFormatter.format_bills_list(response, "Bills")

    except Exception as e:
        logger.error(f"Error in get_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bills")
        return format_error_response(error_response)


async def search_bills(
    ctx: Context,
    keywords: Optional[str] = None,
    format: str = "json",
    offset: Optional[int] = None,
    limit: int = 10,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
    sort: str = "updateDate+desc"
) -> str:
    """
    Enhanced /bill endpoint with optional keyword filtering.
    Maps to Congress.gov API + optional client-side keyword search.

    This function provides the same core API access as get_bills() but adds
    optional client-side keyword filtering for enhanced search capabilities.

    Args:
        ctx: Context for API requests
        keywords: Optional keywords for client-side filtering
        format: Response format ('json' or 'xml')
        offset: Starting record (0-based pagination)
        limit: Maximum number of results (max 250)
        congress: Optional Congress number
        bill_type: Optional bill type
        fromDateTime: Start date filter (YYYY-MM-DDTHH:MM:SSZ)
        toDateTime: End date filter (YYYY-MM-DDTHH:MM:SSZ)
        sort: Sort order ('updateDate+asc' or 'updateDate+desc')

    Returns:
        Formatted bills list or error message
    """
    try:
        # If no keywords provided, use core API function
        if not keywords:
            return await get_bills(
                ctx=ctx,
                format=format,
                offset=offset,
                limit=limit,
                fromDateTime=fromDateTime,
                toDateTime=toDateTime,
                sort=sort,
                congress=congress,
                bill_type=bill_type
            )

        # For keyword search, get more results to filter from
        search_limit = min(limit * 5, 250)  # Get extra for keyword filtering

        # Core API call
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            format=format,
            offset=offset,
            limit=search_limit,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime,
            sort=sort
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Extract bills for processing
        bills = BillsDataProcessor.extract_bills_from_response(response)

        # Apply keyword filtering
        filtered_bills = await BillsDataProcessor.filter_by_keywords(bills, keywords, limit)

        # Update response with filtered bills
        response["bills"] = filtered_bills

        # Format and return
        return BillsFormatter.format_bills_list(response, f"Bills matching '{keywords}'")

    except Exception as e:
        logger.error(f"Error in search_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("search_bills")
        return format_error_response(error_response)


async def get_recent_bills(
    ctx: Context,
    limit: int = 20,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    days_back: int = 30
) -> str:
    """
    Convenience wrapper for get_bills() with recent date filtering.
    Converts days_back to fromDateTime and calls core API.

    Args:
        ctx: Context for API requests
        limit: Maximum number of results
        congress: Optional Congress number
        bill_type: Optional bill type
        days_back: Number of days to look back for activity

    Returns:
        Formatted recent bills list or error message
    """
    try:
        # Convert days_back to API parameter
        from_date = BillsDataProcessor.calculate_date_range(days_back)

        # Call core API function
        return await get_bills(
            ctx=ctx,
            limit=limit,
            fromDateTime=from_date,
            sort="updateDate+desc",
            congress=congress,
            bill_type=bill_type
        )

    except Exception as e:
        logger.error(f"Error in get_recent_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_recent_bills")
        return format_error_response(error_response)


# --- Specific Bill Functions ---

async def get_bill_details(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get detailed information for a specific bill.
    Maps to GET /bill/{congress}/{billType}/{billNumber}

    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type (hr, s, etc.)
        bill_number: Bill number

    Returns:
        Formatted bill details or error message
    """
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))

        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value

        if not isinstance(bill_number, int) or bill_number <= 0:
            return format_error_response(CommonErrors.invalid_parameter(
                "bill_number", bill_number, "Bill number must be a positive integer"
            ))

        # API call
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Extract bill data
        bill = response.get('bill', {})
        if not bill:
            return f"Bill {bill_type.upper()} {bill_number} not found in Congress {congress}"

        # Format and return
        return BillsFormatter.format_bill_detail(bill)

    except Exception as e:
        logger.error(f"Error in get_bill_details: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_details")
        return format_error_response(error_response)


# --- Bill Sub-Resource Functions ---

async def get_bill_actions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """
    Get actions for a specific bill.
    Maps to GET /bill/{congress}/{billType}/{billNumber}/actions

    Args:
        ctx: Context for API requests
        congress: Congress number
        bill_type: Bill type
        bill_number: Bill number
        limit: Maximum number of results
        offset: Starting record

    Returns:
        Formatted actions list or error message
    """
    try:
        # Validate parameters (reuse validation logic)
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(CommonErrors.invalid_congress_number(congress))

        bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_type_validation.is_valid:
            return format_error_response(CommonErrors.invalid_bill_type(bill_type))
        bill_type = bill_type_validation.sanitized_value

        # Build parameters
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        # API call
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="actions",
            **params
        )

        # Handle API errors
        if "error" in response:
            return str(response["error"])

        # Extract actions
        actions = response.get('actions', [])

        # Format and return
        return BillsFormatter.format_bill_actions(actions, congress, bill_type, bill_number)

    except Exception as e:
        logger.error(f"Error in get_bill_actions: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_actions")
        return format_error_response(error_response)


# Additional sub-resource functions would follow the same pattern:
# get_bill_text_versions, get_bill_titles, get_bill_cosponsors, etc.
# For brevity, I'll add a few key ones...

async def get_bill_text_versions(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get text versions for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="text"
        )

        if "error" in response:
            return str(response["error"])

        text_versions = response.get('textVersions', [])
        return BillsFormatter.format_bill_text_versions(text_versions)

    except Exception as e:
        logger.error(f"Error in get_bill_text_versions: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_text_versions")
        return format_error_response(error_response)


async def get_bill_summaries(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get summaries for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="summaries"
        )

        if "error" in response:
            return str(response["error"])

        summaries = response.get('summaries', [])
        return BillsFormatter.format_bill_summaries(summaries)

    except Exception as e:
        logger.error(f"Error in get_bill_summaries: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_summaries")
        return format_error_response(error_response)


# All remaining sub-resource functions following the same pattern

async def get_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """Get text information for a specific bill."""
    try:
        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="text"
        )

        if "error" in response:
            return str(response["error"])

        text_versions = response.get('textVersions', [])
        return BillsFormatter.format_bill_text_versions(text_versions)

    except Exception as e:
        logger.error(f"Error in get_bill_text: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_text")
        return format_error_response(error_response)


async def get_bill_amendments(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get amendments for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="amendments",
            **params
        )

        if "error" in response:
            return str(response["error"])

        amendments = response.get('amendments', [])
        return BillsFormatter.format_bill_amendments(amendments)

    except Exception as e:
        logger.error(f"Error in get_bill_amendments: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_amendments")
        return format_error_response(error_response)


async def get_bill_committees(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get committees for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="committees",
            **params
        )

        if "error" in response:
            return str(response["error"])

        committees = response.get('committees', [])
        return BillsFormatter.format_bill_committees(committees)

    except Exception as e:
        logger.error(f"Error in get_bill_committees: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_committees")
        return format_error_response(error_response)


async def get_bill_cosponsors(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get cosponsors for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="cosponsors",
            **params
        )

        if "error" in response:
            return str(response["error"])

        cosponsors = response.get('cosponsors', [])
        return BillsFormatter.format_bill_cosponsors(cosponsors)

    except Exception as e:
        logger.error(f"Error in get_bill_cosponsors: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_cosponsors")
        return format_error_response(error_response)


async def get_bill_related_bills(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get related bills for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="relatedbills",
            **params
        )

        if "error" in response:
            return str(response["error"])

        related_bills = response.get('relatedBills', [])
        return BillsFormatter.format_bill_related_bills(related_bills)

    except Exception as e:
        logger.error(f"Error in get_bill_related_bills: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_related_bills")
        return format_error_response(error_response)


async def get_bill_subjects(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get subjects for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="subjects",
            **params
        )

        if "error" in response:
            return str(response["error"])

        subjects = response.get('subjects', [])
        return BillsFormatter.format_bill_subjects(subjects)

    except Exception as e:
        logger.error(f"Error in get_bill_subjects: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_subjects")
        return format_error_response(error_response)


async def get_bill_titles(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    limit: int = 20,
    offset: Optional[int] = None
) -> str:
    """Get titles for a specific bill."""
    try:
        params = {'limit': limit}
        if offset is not None:
            params['offset'] = offset

        response = await fetch_bill_data(
            ctx=ctx,
            congress=congress,
            bill_type=bill_type,
            bill_number=bill_number,
            sub_endpoint="titles",
            **params
        )

        if "error" in response:
            return str(response["error"])

        titles = response.get('titles', [])
        return BillsFormatter.format_bill_titles(titles)

    except Exception as e:
        logger.error(f"Error in get_bill_titles: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_titles")
        return format_error_response(error_response)


async def get_bill_content(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int,
    chunk_number: Optional[int] = None,
    chunk_size: int = 5000
) -> str:
    """Get content for a specific bill with chunking support."""
    try:
        # For now, delegate to get_bill_text_versions
        # This can be enhanced with actual content processing later
        return await get_bill_text_versions(ctx, congress, bill_type, bill_number)

    except Exception as e:
        logger.error(f"Error in get_bill_content: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bill_content")
        return format_error_response(error_response)


async def get_bills_by_date_range(
    ctx: Context,
    fromDateTime: str,
    toDateTime: Optional[str] = None,
    limit: int = 20,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None
) -> str:
    """
    Get bills within a specific date range.
    This is now a simple wrapper around get_bills() - no longer redundant.
    """
    try:
        return await get_bills(
            ctx=ctx,
            limit=limit,
            fromDateTime=fromDateTime,
            toDateTime=toDateTime,
            sort="updateDate+desc",
            congress=congress,
            bill_type=bill_type
        )

    except Exception as e:
        logger.error(f"Error in get_bills_by_date_range: {str(e)}")
        error_response = CommonErrors.api_server_error("get_bills_by_date_range")
        return format_error_response(error_response)