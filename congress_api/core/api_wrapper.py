"""Defensive API request wrapper for Congressional MCP APIs."""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, replace
from mcp.server.mcpserver import Context
from .client_handler import make_api_request
from .exceptions import APIErrorResponse, CongressionalAPIError

@dataclass
class APIEndpointConfig:
    timeout: float = 10.0; retry_count: int = 1; retry_delay: float = 1.0; max_retry_delay: float = 5.0
    backoff_multiplier: float = 2.0; sanitize_params: bool = True; remove_empty_params: bool = True

class _HTTPStatusFailure(Exception):
    """Internal: carries the HTTP status from make_api_request's error dict."""
    def __init__(self, status_code, message):
        self.status_code = status_code
        super().__init__(f"API Error ({status_code}): {message}")


class DefensiveAPIWrapper:
    ENDPOINT_CONFIGS = {
        'bound_congressional_record': APIEndpointConfig(timeout=15.0, retry_count=2, retry_delay=2.0),
        'bills': APIEndpointConfig(timeout=10.0, retry_count=3), 'amendments': APIEndpointConfig(timeout=10.0, retry_count=2),
        'members': APIEndpointConfig(timeout=8.0, retry_count=2), 'committees': APIEndpointConfig(timeout=8.0, retry_count=2),
        'committee-meetings': APIEndpointConfig(timeout=8.0, retry_count=2), 'committee-prints': APIEndpointConfig(timeout=8.0, retry_count=2),
        'committee-reports': APIEndpointConfig(timeout=8.0, retry_count=2), 'crs-reports': APIEndpointConfig(timeout=10.0, retry_count=3),
        'daily-congressional-record': APIEndpointConfig(timeout=8.0, retry_count=2), 'house-votes': APIEndpointConfig(timeout=8.0, retry_count=2),
        'nominations': APIEndpointConfig(timeout=8.0, retry_count=2), 'senate_communications': APIEndpointConfig(timeout=8.0, retry_count=2),
        'summaries': APIEndpointConfig(timeout=10.0, retry_count=2), 'treaties': APIEndpointConfig(timeout=8.0, retry_count=2),
        'default': APIEndpointConfig()
    }
    
    @staticmethod
    def _sanitize_parameters(params: Dict[str, Any], config: APIEndpointConfig) -> Dict[str, Any]:
        if not config.sanitize_params: return params
        sanitized = {}
        for key, value in params.items():
            if value is None and not config.remove_empty_params: sanitized[key] = value
            elif isinstance(value, str): 
                value = value.strip()
                if value or not config.remove_empty_params: sanitized[key] = value
            elif isinstance(value, (int, float)): sanitized[key] = str(value)
            elif value is not None: sanitized[key] = value
        return sanitized
    
    @staticmethod
    def _get_endpoint_config(endpoint: str) -> APIEndpointConfig:
        mappings = {'bound-congressional-record': 'bound_congressional_record', 'bill': 'bills', 'amendment': 'amendments',
                   'member': 'members', 'committee': 'committees', 'crsreport': 'crs-reports', 'nominations': 'nominations',
                   'summaries': 'summaries', 'treaties': 'treaties', 'house-votes': 'house-votes'}
        for key, config_key in mappings.items():
            if key in endpoint: return DefensiveAPIWrapper.ENDPOINT_CONFIGS.get(config_key, DefensiveAPIWrapper.ENDPOINT_CONFIGS['default'])
        return DefensiveAPIWrapper.ENDPOINT_CONFIGS['default']
    
    @staticmethod
    async def safe_api_request(endpoint: str, ctx: Optional[Context], params: Optional[Dict[str, Any]] = None,
                              timeout_override: Optional[float] = None, retry_count_override: Optional[int] = None,
                              endpoint_type: Optional[str] = None) -> Dict[str, Any]:
        if params is None: params = {}
        config = replace(DefensiveAPIWrapper.ENDPOINT_CONFIGS.get(endpoint_type, DefensiveAPIWrapper._get_endpoint_config(endpoint)))
        if timeout_override: config.timeout = timeout_override
        if retry_count_override is not None: config.retry_count = retry_count_override
        
        sanitized_params = DefensiveAPIWrapper._sanitize_parameters(params, config)
        last_error = None; retry_delay = config.retry_delay
        
        for attempt in range(config.retry_count + 1):
            try:
                if attempt > 0:
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * config.backoff_multiplier, config.max_retry_delay)
                
                response = await make_api_request(endpoint, ctx, sanitized_params)
                if isinstance(response, dict) and 'error' in response:
                    raise _HTTPStatusFailure(response.get('status_code'),
                                             response.get('error', 'Unknown API error'))
                return response
            except Exception as e:
                last_error = e
                # Client errors are definitive: never retry a 404/400.
                status = getattr(e, "status_code", None)
                if status in (400, 404): break
                if status is None and any(x in str(e).lower() for x in ["404", "not found", "400", "bad request"]): break
        
        error_response = DefensiveAPIWrapper._format_api_error(endpoint, last_error, config.retry_count)
        # Raise the *typed* error so handlers can report not-found / bad-request
        # faithfully instead of collapsing everything into SERVER_ERROR.
        raise CongressionalAPIError(error_response)
    
    @staticmethod
    def _format_api_error(endpoint: str, error: Exception, retry_count: int) -> APIErrorResponse:
        resp = DefensiveAPIWrapper._classify_api_error(endpoint, error, retry_count)
        resp.details = {**(resp.details or {}), "endpoint": endpoint}
        return resp

    @staticmethod
    def _not_found(endpoint: str) -> APIErrorResponse:
        return APIErrorResponse(
            "not_found",
            f"Not found: {endpoint}. The resource does not exist at Congress.gov.",
            ["Check the identifiers (congress, type, number / bioguide id) for typos",
             "Confirm the item exists with a list/search operation first",
             "This is not a server outage; retrying will not help"],
            "DATA_NOT_FOUND")

    @staticmethod
    def _classify_api_error(endpoint: str, error: Exception, retry_count: int) -> APIErrorResponse:
        # Prefer the real HTTP status when we have one; the substring fallback
        # below can misfire on endpoints whose path happens to contain '404'.
        status = getattr(error, "status_code", None)
        if status == 404:
            return DefensiveAPIWrapper._not_found(endpoint)
        if status == 400:
            return APIErrorResponse("validation", f"Congress.gov rejected the request to {endpoint} (400).",
                                    ["Check parameter names, formats and ranges"], "INVALID_PARAMETERS")
        if status == 429:
            return APIErrorResponse("rate_limit", f"Congress.gov rate limit hit on {endpoint} (429).",
                                    ["Wait a minute and retry", "Reduce request volume"], "RATE_LIMIT_EXCEEDED")
        if isinstance(status, int) and status >= 500:
            return APIErrorResponse("server_error", f"Congress.gov returned {status} for {endpoint}.",
                                    ["Try again in a few minutes"], "SERVER_ERROR")
        error_str = str(error).lower()
        if "timeout" in error_str: return APIErrorResponse("timeout", f"API request timed out after {retry_count + 1} attempts", ["Try again"], "API_TIMEOUT")
        elif "404" in error_str or "not found" in error_str:
            return DefensiveAPIWrapper._not_found(endpoint)
        elif "400" in error_str or "bad request" in error_str: return APIErrorResponse("validation", "Invalid parameters.", ["Check format"], "INVALID_PARAMETERS")
        elif "500" in error_str: return APIErrorResponse("server_error", "API issues.", ["Try later"], "SERVER_ERROR")
        else: return APIErrorResponse("api_failure", f"Failed after {retry_count + 1} attempts: {error}", ["Try later"], "GENERAL_API_FAILURE")

async def safe_congressional_request(endpoint: str, ctx: Optional[Context], params: Optional[Dict[str, Any]] = None, endpoint_type: Optional[str] = None) -> Dict[str, Any]:
    """Generic convenience function for all Congressional API requests."""
    return await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, params or {}, endpoint_type=endpoint_type)