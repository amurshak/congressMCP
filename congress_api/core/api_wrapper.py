"""
Defensive API request wrapper for Congressional MCP APIs.

This module provides enhanced API request handling with retries, timeout controls,
parameter sanitization, and standardized error responses.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from fastmcp import Context

from .client_handler import make_api_request
from .exceptions import APIErrorResponse, format_error_response

logger = logging.getLogger(__name__)

@dataclass
class APIEndpointConfig:
    """Configuration for specific API endpoints."""
    timeout: float = 10.0
    retry_count: int = 1
    retry_delay: float = 1.0
    max_retry_delay: float = 5.0
    backoff_multiplier: float = 2.0
    
    # Endpoint-specific parameter sanitization
    sanitize_params: bool = True
    remove_empty_params: bool = True

class DefensiveAPIWrapper:
    """Enhanced API request wrapper with reliability features."""
    
    # Default configurations for different endpoint types
    ENDPOINT_CONFIGS = {
        'bound_congressional_record': APIEndpointConfig(
            timeout=15.0,  # Bound records can be slow
            retry_count=2,
            retry_delay=2.0
        ),
        'bills': APIEndpointConfig(
            timeout=10.0,
            retry_count=3,
            retry_delay=1.0
        ),
        'amendments': APIEndpointConfig(
            timeout=10.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'members': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'committees': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'committee-meetings': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'committee-prints': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'committee-reports': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'crs-reports': APIEndpointConfig(
            timeout=10.0,
            retry_count=3,
            retry_delay=1.0
        ),
        'daily-congressional-record': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'house-votes': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'nominations': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'senate_communications': APIEndpointConfig(
            timeout=8.0,
            retry_count=2,
            retry_delay=1.0
        ),
        'default': APIEndpointConfig()
    }
    
    @staticmethod
    def _sanitize_parameters(params: Dict[str, Any], config: APIEndpointConfig) -> Dict[str, Any]:
        """
        Sanitize API parameters to prevent issues.
        
        Args:
            params: Raw parameters dictionary
            config: Endpoint configuration
            
        Returns:
            Sanitized parameters dictionary
        """
        if not config.sanitize_params:
            return params
        
        sanitized = {}
        
        for key, value in params.items():
            if value is None:
                if not config.remove_empty_params:
                    sanitized[key] = value
                continue
            
            # Convert to string and strip whitespace
            if isinstance(value, str):
                value = value.strip()
                if value == "" and config.remove_empty_params:
                    continue
            
            # Convert numeric strings to proper format
            if isinstance(value, (int, float)):
                value = str(value)
            
            sanitized[key] = value
        
        logger.debug(f"Sanitized parameters: {params} -> {sanitized}")
        return sanitized
    
    @staticmethod
    def _get_endpoint_config(endpoint: str) -> APIEndpointConfig:
        """
        Get configuration for a specific endpoint.
        
        Args:
            endpoint: API endpoint path
            
        Returns:
            APIEndpointConfig for the endpoint
        """
        # Extract endpoint type from path
        endpoint_parts = endpoint.strip('/').split('/')
        
        if 'bound-congressional-record' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['bound_congressional_record']
        elif 'bill' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['bills']
        elif 'amendment' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['amendments']
        elif 'member' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['members']
        elif 'committee' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['committees']
        elif 'committee-meetings' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['committee-meetings']
        elif 'committee-prints' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['committee-prints']
        elif 'committee-reports' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['committee-reports']
        elif 'crsreport' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['crs-reports']
        elif 'daily-congressional-record' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['daily-congressional-record']
        elif 'house-votes' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['house-votes']
        elif 'nominations' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['nominations']
        elif 'senate-communications' in endpoint:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['senate_communications']
        else:
            return DefensiveAPIWrapper.ENDPOINT_CONFIGS['default']
    
    @staticmethod
    async def safe_api_request(
        endpoint: str,
        ctx: Context,
        params: Optional[Dict[str, Any]] = None,
        timeout_override: Optional[float] = None,
        retry_count_override: Optional[int] = None,
        endpoint_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make a safe API request with retries, timeout controls, and error handling.
        
        Args:
            endpoint: API endpoint to call
            ctx: MCP context for session management
            params: Request parameters
            timeout_override: Override default timeout
            retry_count_override: Override default retry count
            endpoint_type: Force specific endpoint configuration
            
        Returns:
            API response dictionary
            
        Raises:
            APIErrorResponse: On validation or API failures
        """
        if params is None:
            params = {}
        
        # Get endpoint configuration
        if endpoint_type:
            config = DefensiveAPIWrapper.ENDPOINT_CONFIGS.get(endpoint_type, DefensiveAPIWrapper.ENDPOINT_CONFIGS['default'])
        else:
            config = DefensiveAPIWrapper._get_endpoint_config(endpoint)
        
        # Apply overrides
        if timeout_override:
            config.timeout = timeout_override
        if retry_count_override is not None:
            config.retry_count = retry_count_override
        
        # Sanitize parameters
        sanitized_params = DefensiveAPIWrapper._sanitize_parameters(params, config)
        
        logger.info(f"Making API request to {endpoint} with config: timeout={config.timeout}s, retries={config.retry_count}")
        logger.debug(f"Request parameters: {sanitized_params}")
        
        last_error = None
        retry_delay = config.retry_delay
        
        for attempt in range(config.retry_count + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{config.retry_count} for {endpoint}")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * config.backoff_multiplier, config.max_retry_delay)
                
                # Make the actual API request
                response = await make_api_request(endpoint, ctx, sanitized_params)
                
                # Check if make_api_request returned an error response
                if isinstance(response, dict) and 'error' in response:
                    error_msg = response.get('error', 'Unknown API error')
                    status_code = response.get('status_code', 'Unknown')
                    
                    # Create an exception with the error details
                    if status_code == 404:
                        raise Exception(f"404 Not Found: {error_msg}")
                    elif status_code == 400:
                        raise Exception(f"400 Bad Request: {error_msg}")
                    else:
                        raise Exception(f"API Error ({status_code}): {error_msg}")
                
                logger.info(f"API request to {endpoint} succeeded on attempt {attempt + 1}")
                return response
                
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Timeout on attempt {attempt + 1} for {endpoint} (timeout: {config.timeout}s)")
                
            except Exception as e:
                last_error = e
                logger.warning(f"Error on attempt {attempt + 1} for {endpoint}: {str(e)}")
                
                # Don't retry on certain error types
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.info(f"Not retrying {endpoint} due to 404/not found error")
                    break
                
                if "400" in str(e) or "bad request" in str(e).lower():
                    logger.info(f"Not retrying {endpoint} due to 400/bad request error")
                    break
        
        # All retries exhausted, format error response
        error_response = DefensiveAPIWrapper._format_api_error(endpoint, last_error, config.retry_count)
        logger.error(f"API request to {endpoint} failed after {config.retry_count + 1} attempts: {error_response.message}")
        
        raise Exception(error_response.message)
    
    @staticmethod
    def _format_api_error(endpoint: str, error: Exception, retry_count: int) -> APIErrorResponse:
        """
        Format API errors into standardized error responses.
        
        Args:
            endpoint: Failed endpoint
            error: The exception that occurred
            retry_count: Number of retries attempted
            
        Returns:
            Formatted APIErrorResponse
        """
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return APIErrorResponse(
                error_type="timeout",
                message=f"The API request timed out after {retry_count + 1} attempts. The Congressional API may be experiencing delays.",
                suggestions=[
                    "Try again in a few moments",
                    "Check if your parameters are valid",
                    "Consider using a smaller date range or limit"
                ],
                error_code="API_TIMEOUT"
            )
        
        elif "404" in error_str or "not found" in error_str:
            return APIErrorResponse(
                error_type="not_found",
                message="The requested data was not found. This may indicate invalid parameters or that the data doesn't exist.",
                suggestions=[
                    "Check your congress number, bill number, or date parameters",
                    "Verify the data exists for the time period you're searching",
                    "Try broadening your search criteria"
                ],
                error_code="DATA_NOT_FOUND"
            )
        
        elif "400" in error_str or "bad request" in error_str:
            return APIErrorResponse(
                error_type="validation",
                message="The API rejected the request due to invalid parameters.",
                suggestions=[
                    "Check that all parameters are in the correct format",
                    "Verify congress numbers, dates, and other values are valid",
                    "Review the parameter requirements for this endpoint"
                ],
                error_code="INVALID_PARAMETERS"
            )
        
        elif "500" in error_str or "internal server error" in error_str:
            return APIErrorResponse(
                error_type="server_error",
                message="The Congressional API is experiencing internal issues.",
                suggestions=[
                    "Try again in a few minutes",
                    "The issue is on the API server side, not your request",
                    "Consider trying a different endpoint or simpler query"
                ],
                error_code="SERVER_ERROR"
            )
        
        else:
            return APIErrorResponse(
                error_type="api_failure",
                message=f"The API request failed after {retry_count + 1} attempts: {str(error)}",
                suggestions=[
                    "Try again in a few moments",
                    "Check your internet connection",
                    "Verify your parameters are correct"
                ],
                error_code="GENERAL_API_FAILURE"
            )

# Convenience functions for common use cases
async def safe_bound_record_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to bound congressional record endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='bound_congressional_record'
    )

async def safe_bills_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to bills endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='bills'
    )

async def safe_amendments_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to amendments endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='amendments'
    )

async def safe_members_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to members endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='members'
    )

async def safe_committees_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to committees endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='committees'
    )

async def safe_committee_meetings_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to committee meetings endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='committee-meetings'
    )

async def safe_committee_prints_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make a safe request to committee prints endpoints."""
    if params is None:
        params = {}
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='committee-prints'
    )

async def safe_committee_reports_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make a safe request to committee reports endpoints."""
    if params is None:
        params = {}
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='committee-reports'
    )

async def safe_crs_reports_request(endpoint: str, ctx: Context, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make a safe request to CRS reports endpoints."""
    if params is None:
        params = {}
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='crs-reports'
    )

async def safe_house_votes_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to house votes endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='house-votes'
    )

async def safe_nominations_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to nominations endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='nominations'
    )

async def safe_senate_communications_request(endpoint: str, ctx: Context, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a safe request to senate communications endpoints."""
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint, ctx, params, endpoint_type='senate_communications'
    )
