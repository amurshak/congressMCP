"""
Bills API Helpers - Pure API interaction functions.

Contains the core infrastructure for making Congress.gov API calls
without any business logic or formatting concerns.
"""

from typing import Dict, Optional, Any
import logging
from fastmcp import Context

# Import existing validation and API infrastructure
from ....core.validators import ParameterValidator
from ....core.api_wrapper import safe_bills_request
from ....core.exceptions import CommonErrors, format_error_response

# Set up logger
logger = logging.getLogger(__name__)


async def fetch_bill_data(
    ctx: Context,
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    bill_number: Optional[int] = None,
    sub_endpoint: str = "",
    **params
) -> Dict[str, Any]:
    """
    Core helper to fetch bill data from Congress.gov API with reliability framework.

    This is a pure API proxy function - no business logic or formatting.

    Args:
        ctx: Context for API requests
        congress: Congress number (e.g., 117)
        bill_type: Bill type (e.g., 'hr', 's')
        bill_number: Bill number
        sub_endpoint: Additional endpoint path (e.g., 'actions', 'cosponsors')
        **params: Additional query parameters (limit, sort, etc.)

    Returns:
        Raw API response data or error response
    """
    try:
        # Validate parameters
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                logger.warning(f"Invalid congress number: {congress}")
                return {"error": congress_validation.error_message}

        if bill_type is not None:
            bill_type_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_type_validation.is_valid:
                logger.warning(f"Invalid bill type: {bill_type}")
                return {"error": bill_type_validation.error_message}

        if bill_number is not None:
            if not isinstance(bill_number, int) or bill_number <= 0:
                logger.warning(f"Invalid bill number: {bill_number}")
                return {"error": "Bill number must be a positive integer"}

        # Validate limit parameter if provided
        if 'limit' in params:
            limit_validation = ParameterValidator.validate_limit_range(params['limit'])
            if not limit_validation.is_valid:
                logger.warning(f"Invalid limit: {params['limit']}")
                return {"error": limit_validation.error_message}
            params['limit'] = limit_validation.sanitized_value

        # Build endpoint
        endpoint = build_bill_endpoint(congress, bill_type, bill_number, sub_endpoint)
        logger.debug(f"Fetching bill data from endpoint: {endpoint}")

        # Set default parameters
        query_params = {'format': 'json'}
        query_params.update(params)

        # Use defensive API wrapper for the request
        return await safe_bills_request(endpoint, ctx, query_params)

    except Exception as e:
        logger.error(f"Error in fetch_bill_data: {str(e)}")
        error_response = CommonErrors.api_server_error(f"bills endpoint: {endpoint if 'endpoint' in locals() else 'unknown'}")
        return {"error": format_error_response(error_response)}


def build_bill_endpoint(
    congress: Optional[int] = None,
    bill_type: Optional[str] = None,
    bill_number: Optional[int] = None,
    sub_endpoint: str = ""
) -> str:
    """
    Build the appropriate Congress.gov API endpoint based on parameters.

    Maps directly to Congress.gov API endpoint structure:
    - /bill (all bills)
    - /bill/{congress} (bills from specific congress)
    - /bill/{congress}/{billType} (bills by congress + type)
    - /bill/{congress}/{billType}/{billNumber} (specific bill)
    - /bill/{congress}/{billType}/{billNumber}/{sub_endpoint} (bill sub-resources)

    Args:
        congress: Congress number
        bill_type: Bill type (hr, s, hjres, sjres, hconres, sconres, hres, sres)
        bill_number: Bill number
        sub_endpoint: Additional endpoint path

    Returns:
        Constructed endpoint path
    """
    if congress and bill_type and bill_number:
        endpoint = f"/bill/{congress}/{bill_type.lower()}/{bill_number}"
    elif congress and bill_type:
        endpoint = f"/bill/{congress}/{bill_type.lower()}"
    elif congress:
        endpoint = f"/bill/{congress}"
    else:
        endpoint = "/bill"

    if sub_endpoint:
        endpoint += f"/{sub_endpoint}"

    return endpoint


def validate_api_parameters(**kwargs) -> Dict[str, Any]:
    """
    Validate standard Congress.gov API parameters.

    Args:
        **kwargs: API parameters to validate

    Returns:
        Dict with 'valid' boolean and 'params' dict or 'error' message
    """
    try:
        validated_params = {}

        # Validate format parameter
        if 'format' in kwargs:
            format_val = kwargs['format']
            if format_val not in ['json', 'xml']:
                return {"valid": False, "error": f"Invalid format '{format_val}'. Must be 'json' or 'xml'"}
            validated_params['format'] = format_val

        # Validate offset parameter
        if 'offset' in kwargs and kwargs['offset'] is not None:
            offset = kwargs['offset']
            if not isinstance(offset, int) or offset < 0:
                return {"valid": False, "error": f"Invalid offset '{offset}'. Must be non-negative integer"}
            validated_params['offset'] = offset

        # Validate limit parameter
        if 'limit' in kwargs and kwargs['limit'] is not None:
            limit_validation = ParameterValidator.validate_limit_range(kwargs['limit'])
            if not limit_validation.is_valid:
                return {"valid": False, "error": limit_validation.error_message}
            validated_params['limit'] = limit_validation.sanitized_value

        # Validate sort parameter
        if 'sort' in kwargs:
            sort_val = kwargs['sort']
            if sort_val not in ['updateDate+asc', 'updateDate+desc']:
                return {"valid": False, "error": f"Invalid sort '{sort_val}'. Must be 'updateDate+asc' or 'updateDate+desc'"}
            validated_params['sort'] = sort_val

        # Pass through date parameters (validated elsewhere if needed)
        for date_param in ['fromDateTime', 'toDateTime']:
            if date_param in kwargs:
                validated_params[date_param] = kwargs[date_param]

        return {"valid": True, "params": validated_params}

    except Exception as e:
        logger.error(f"Error validating API parameters: {str(e)}")
        return {"valid": False, "error": f"Parameter validation error: {str(e)}"}