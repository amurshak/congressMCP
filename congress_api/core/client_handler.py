# client_handler.py
import json
import httpx
import logging
import time
from typing import Dict, Any, Optional, AsyncIterator, Tuple
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from datetime import datetime

from mcp.server.mcpserver import MCPServer, Context
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

# MCP SDK v2 disallows Context injection on static (non-templated) resources,
# so static resource handlers can't reach ctx.request_context.lifespan_context.
# This module-level reference lets them reach the same AppContext directly.
_current_app_context: Optional[AppContext] = None

def get_app_context() -> AppContext:
    """Access the running server's AppContext without a Context parameter.

    For use by static resource handlers, which MCP SDK v2 does not permit
    to declare a `ctx: Context` parameter.
    """
    if _current_app_context is None:
        raise RuntimeError("Server not properly initialized - lifespan context unavailable")
    return _current_app_context

@asynccontextmanager
async def app_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    """Manage API client lifecycle with proper error handling and connection testing."""
    global _current_app_context
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
            if API_KEY:
                logger.info("API key configured - skipping startup connection test")
            else:
                logger.error("No API key provided. The server will start, but API requests will fail")

            # Initialize and yield context to server
            context = AppContext(api_key=API_KEY or "MISSING_API_KEY", client=client)
            _current_app_context = context
            logger.info("Server context initialized successfully")
            yield context
    except Exception as e:
        logger.critical(f"Failed to initialize API client: {e}")
        # Re-raise to prevent server from starting with a broken client
        raise
    finally:
        _current_app_context = None
        # Ensure clean shutdown even if there are errors
        try:
            logger.info("Cleaning up HTTP client resources...")
            # The async context manager should handle cleanup automatically
            # but we add this for explicit logging
        except Exception as cleanup_error:
            # Log cleanup errors but don't re-raise them during shutdown
            logger.error(f"Error during HTTP client cleanup: {cleanup_error}")

def generate_cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    """Generate a cache key from endpoint and parameters."""
    # Sort params to ensure consistent keys regardless of dict order
    param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "api_key")
    return f"{endpoint}?{param_str}"

# Helper function for API requests
async def make_api_request(endpoint: str, ctx: Optional[Context] = None, params: Optional[Dict[str, Any]] = None,
                            timeout: Optional[float] = None) -> Dict[str, Any]:
    """Make a request to the Congress.gov API with caching and proper error handling.

    `ctx` is the request's MCP Context, used by tools and templated resources.
    Static resource handlers can't declare a Context parameter under MCP SDK v2,
    so they pass `ctx=None` and the AppContext is pulled from `get_app_context()` instead.

    `timeout` overrides the client's default httpx timeout for this request only
    (issue #58: per-endpoint timeouts from DefensiveAPIWrapper were computed but
    never reached httpx). Omitted/None keeps the client's own default -- passing
    `timeout=None` straight to httpx would instead disable the timeout entirely,
    so it is only forwarded when the caller supplied a value.
    """
    start_time = time.time()

    try:
        logger.debug(f"Starting make_api_request for endpoint: {endpoint}")
        # Access the lifespan context to get the HTTP client with error handling
        if ctx is None:
            app_ctx = get_app_context()
        else:
            try:
                app_ctx = ctx.request_context.lifespan_context
                if app_ctx is None:
                    raise ValueError("Lifespan context is None - server may not be fully initialized")
            except AttributeError as e:
                logger.error(f"Failed to access lifespan context: {e}")
                raise RuntimeError("Server not properly initialized - lifespan context unavailable") from e

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

        request_kwargs = {"params": request_params}
        if timeout is not None:
            # A bare float would set connect/write/pool to it too, loosening
            # the 5s connect timeout the client was built with (line ~90) and
            # tying write/pool to a value meant to vary per-endpoint for
            # reads. Only the read timeout is meant to vary; connect/write/
            # pool stay at the client's own defaults (10.0/10.0, line ~90).
            request_kwargs["timeout"] = httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=10.0)
        response = await client.get(endpoint, **request_kwargs)
        response.raise_for_status()
        
        # Parse the response
        try:
            data = response.json()
        except json.JSONDecodeError:
            error_message = f"API returned non-JSON response for endpoint {endpoint}: {response.text[:100]}..."
            logger.error(error_message)
            if ctx is not None:
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

        if ctx is not None:
            ctx.error(ctx_error_message)

        # Return an error response with enough detail for clients. Retry-After
        # and X-RateLimit-Remaining (issue #58) let DefensiveAPIWrapper pace
        # 429 retries off the server's own guidance instead of blind backoff.
        return {
            "error": f"API request failed: {e.response.status_code}",
            "status_code": e.response.status_code,
            "request_time": request_time,
            "retry_after": e.response.headers.get("Retry-After"),
            "rate_limit_remaining": e.response.headers.get("X-RateLimit-Remaining"),
        }
    except httpx.TimeoutException as e:
        request_time = time.time() - start_time

        log_error_message = f"API request to {endpoint} exceeded its timeout"
        logger.error(log_error_message)

        # Must contain "timeout" -- DefensiveAPIWrapper._classify_api_error
        # matches on it to report API_TIMEOUT instead of a generic failure.
        ctx_error_message = f"API request timeout after {request_time:.2f}s"
        if ENV != "production":
            ctx_error_message += f": {str(e)}"

        if ctx is not None:
            ctx.error(ctx_error_message)

        # No endpoint/digits in the returned message (endpoint is only in the
        # log line above): DefensiveAPIWrapper's no-status-code fallback does
        # a substring scan for "400"/"404" on str(error), and an endpoint
        # like /bill/118/hr/404 would false-positive that scan and skip
        # retries on a plain timeout.
        return {
            "error": f"API request timeout after {request_time:.2f}s",
            "request_time": request_time,
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

        if ctx is not None:
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

        if ctx is not None:
            ctx.error(ctx_error_message)

        return {
            "error": f"Unexpected error during API request to endpoint: {endpoint}",
            "request_time": request_time
        }
