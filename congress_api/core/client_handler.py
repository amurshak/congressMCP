# client_handler.py
import sys
import json
import httpx
import logging
import time
from typing import Dict, List, Any, Optional, AsyncIterator, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP, Context
from .api_config import API_KEY, BASE_URL, ENABLE_CACHING, CACHE_TIMEOUT, DEFAULT_REQUEST_PARAMS, ENV

# Configure logger
logger = logging.getLogger(__name__)

# Simple in-memory cache
class SimpleCache:
    """A simple in-memory cache for API responses."""
    
    def __init__(self, timeout_seconds: int = 300):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.timeout_seconds = timeout_seconds
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and hasn't expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.timeout_seconds:
                self.hits += 1
                return value
            else:
                # Remove expired item
                del self.cache[key]
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with the current timestamp."""
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all items from the cache."""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
            "timeout_seconds": self.timeout_seconds
        }

# Application context for handling API connection
@dataclass
class AppContext:
    """Application context for the Congress.gov API server."""
    api_key: str
    client: httpx.AsyncClient
    cache: SimpleCache = field(default_factory=lambda: SimpleCache(CACHE_TIMEOUT))
    request_count: int = 0
    start_time: datetime = field(default_factory=datetime.now)

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage API client lifecycle with proper error handling and connection testing."""
    logger.info("Initializing Congress.gov API client...")
    
    # Configure httpx client with timeouts and limits for production use
    timeout = httpx.Timeout(10.0, connect=5.0)  # 10s timeout, 5s connect timeout
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    
    try:
        async with httpx.AsyncClient(
            base_url=BASE_URL, 
            timeout=timeout, 
            limits=limits,
            follow_redirects=True
        ) as client:
            # Test connection if API key is available
            if API_KEY:
                try:
                    logger.info("Testing API connection")
                    response = await client.get("/congress", params={"api_key": API_KEY})
                    response.raise_for_status()
                    logger.info("API connection successful")
                except httpx.HTTPStatusError as e:
                    # Don't log the full error details which might contain sensitive info
                    logger.error(f"API connection failed with status code: {e.response.status_code}")
                    logger.warning("The server will start, but API requests may fail")
                except httpx.RequestError as e:
                    # Log generic error without specific connection details
                    logger.error("Network error when connecting to API")
                    logger.warning("The server will start, but API requests may fail")
            else:
                logger.error("No API key provided. The server will start, but API requests will fail")
            
            # Initialize and yield context to server
            context = AppContext(api_key=API_KEY or "MISSING_API_KEY", client=client)
            logger.info("Server context initialized successfully")
            yield context
    except Exception as e:
        logger.critical(f"Failed to initialize API client: {e}")
        # Re-raise to prevent server from starting with a broken client
        raise

def generate_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    """Generate a cache key from endpoint and parameters."""
    # Sort params to ensure consistent keys regardless of dict order
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "api_key")
    return f"{endpoint}?{param_str}"

# Helper function for API requests
async def make_api_request(endpoint: str, ctx: Context, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a request to the Congress.gov API with caching and proper error handling."""
    start_time = time.time()
    
    try:
        logger.debug(f"Starting make_api_request for endpoint: {endpoint}")
        app_ctx = ctx.request_context.lifespan_context
        client = app_ctx.client
        api_key = app_ctx.api_key
        
        # Track request count
        app_ctx.request_count += 1
        
        # Prepare parameters with defaults
        request_params = DEFAULT_REQUEST_PARAMS.copy()
        if params:
            request_params.update(params)
        request_params["api_key"] = api_key
        
        # Check cache if enabled
        if ENABLE_CACHING:
            cache_key = generate_cache_key(endpoint, request_params)
            cached_response = app_ctx.cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache hit for {endpoint}")
                return cached_response
        
        # Make the request - don't log full params which may contain API key
        safe_params = {k: v for k, v in request_params.items() if k != "api_key"}
        safe_params["api_key"] = "[REDACTED]" if "api_key" in request_params else "[MISSING]"
        
        logger.debug(f"Making request to {endpoint}")
        if ENV != "production":  # Only log params in non-production
            logger.debug(f"Request parameters: {safe_params}")
            
        response = await client.get(endpoint, params=request_params)
        response.raise_for_status()
        
        # Parse the response
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            error_message = f"API returned non-JSON response for endpoint {endpoint}: {response.text[:100]}..."
            logger.error(error_message)
            ctx.error(error_message)
            return {"error": error_message}
        
        # Cache the successful response if caching is enabled
        if ENABLE_CACHING:
            app_ctx.cache.set(cache_key, data)
        
        # Log request timing
        request_time = time.time() - start_time
        logger.debug(f"Request to {endpoint} completed in {request_time:.2f}s with status: {response.status_code}")
        
        return data
    except httpx.HTTPStatusError as e:
        request_time = time.time() - start_time
        
        # Create a sanitized error message for logging
        log_error_message = f"API request to {endpoint} failed with status code: {e.response.status_code}"
        logger.error(log_error_message)
        
        # Create a more detailed error message for the context (not logged)
        ctx_error_message = f"API request failed after {request_time:.2f}s: {e.response.status_code}"
        
        # Only include response text in development mode
        if ENV != "production" and e.response.text:
            # Limit the response text to avoid large error messages
            ctx_error_message += f" - {e.response.text[:100]}"
            if len(e.response.text) > 100:
                ctx_error_message += "..."
        
        ctx.error(ctx_error_message)
        
        # Return an error response with enough detail for clients
        # We'll keep the original error message but sanitize it for logging
        return {
            "error": f"API request failed: {e.response.status_code}", 
            "status_code": e.response.status_code,
            "request_time": request_time
        }
    except httpx.RequestError as e:
        request_time = time.time() - start_time
        
        # Create a sanitized error message without network details
        log_error_message = f"Network error during API request to {endpoint}"
        logger.error(log_error_message)
        
        # More detailed message for context
        ctx_error_message = f"Request failed after {request_time:.2f}s"
        if ENV != "production":
            ctx_error_message += f": {str(e)}"
        
        ctx.error(ctx_error_message)
        
        return {
            "error": "Network error during API request to Congress.gov API",
            "request_time": request_time
        }
    except Exception as e:
        request_time = time.time() - start_time
        
        # Generic error message for logs
        log_error_message = f"Unexpected error during API request to {endpoint}"
        logger.error(log_error_message)
        
        # More detailed message for context
        ctx_error_message = f"An unexpected error occurred during API request after {request_time:.2f}s"
        if ENV != "production":
            ctx_error_message += f": {str(e)}"
        
        ctx.error(ctx_error_message)
        
        return {
            "error": f"Unexpected error during API request to endpoint: {endpoint}",
            "request_time": request_time
        }
