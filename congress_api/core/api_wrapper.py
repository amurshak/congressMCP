"""Defensive API request wrapper for Congressional MCP APIs."""

import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, replace
from mcp.server.fastmcp import Context
from .client_handler import make_api_request
from .exceptions import APIErrorResponse

@dataclass
class APIEndpointConfig:
    timeout: float = 10.0; retry_count: int = 1; retry_delay: float = 1.0; max_retry_delay: float = 5.0
    backoff_multiplier: float = 2.0; sanitize_params: bool = True; remove_empty_params: bool = True

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
    async def safe_api_request(endpoint: str, ctx: Context, params: Optional[Dict[str, Any]] = None,
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
                    error_msg = response.get('error', 'Unknown API error'); status_code = response.get('status_code', 'Unknown')
                    if status_code == 404: raise Exception(f"404 Not Found: {error_msg}")
                    elif status_code == 400: raise Exception(f"400 Bad Request: {error_msg}")
                    else: raise Exception(f"API Error ({status_code}): {error_msg}")
                return response
            except Exception as e:
                last_error = e
                if any(x in str(e).lower() for x in ["404", "not found", "400", "bad request"]): break
        
        error_response = DefensiveAPIWrapper._format_api_error(endpoint, last_error, config.retry_count)
        raise Exception(error_response.message)
    
    @staticmethod
    def _format_api_error(endpoint: str, error: Exception, retry_count: int) -> APIErrorResponse:
        error_str = str(error).lower()
        if "timeout" in error_str: return APIErrorResponse("timeout", f"API request timed out after {retry_count + 1} attempts", ["Try again"], "API_TIMEOUT")
        elif "404" in error_str or "not found" in error_str: return APIErrorResponse("not_found", "Data not found. Check parameters.", ["Verify parameters"], "DATA_NOT_FOUND")
        elif "400" in error_str or "bad request" in error_str: return APIErrorResponse("validation", "Invalid parameters.", ["Check format"], "INVALID_PARAMETERS")
        elif "500" in error_str: return APIErrorResponse("server_error", "API issues.", ["Try later"], "SERVER_ERROR")
        else: return APIErrorResponse("api_failure", f"Failed after {retry_count + 1} attempts: {error}", ["Try later"], "GENERAL_API_FAILURE")

async def safe_congressional_request(endpoint: str, ctx: Context, params: Optional[Dict[str, Any]] = None, endpoint_type: Optional[str] = None) -> Dict[str, Any]:
    """Generic convenience function for all Congressional API requests."""
    return await DefensiveAPIWrapper.safe_api_request(endpoint, ctx, params or {}, endpoint_type=endpoint_type)