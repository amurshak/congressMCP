"""
CORS configuration for CongressMCP.

Centralizes CORS headers to avoid repetition and enforce security.
In production, restricts origins to known frontends.
In development, allows all origins.
"""

import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Allowed origins for production
_ALLOWED_ORIGINS_DEFAULT = [
    "https://congressmcp.lawgiver.ai",
    "https://www.congressmcp.lawgiver.ai",
    "https://cicero.lawgiver.ai",
    "https://www.lawgiver.ai",
]

def _get_allowed_origins() -> list[str]:
    """Get allowed origins from environment or defaults."""
    env = os.getenv("CONGRESS_API_ENV", "production")
    custom = os.getenv("CORS_ALLOWED_ORIGINS", "")
    
    if env == "development":
        return ["*"]
    
    if custom:
        return [o.strip() for o in custom.split(",") if o.strip()]
    
    return _ALLOWED_ORIGINS_DEFAULT


def _origin_allowed(request_origin: str | None) -> str:
    """Check if the request origin is allowed. Returns the origin to echo back, or empty string."""
    if not request_origin:
        return ""
    
    allowed = _get_allowed_origins()
    
    if "*" in allowed:
        return "*"
    
    if request_origin in allowed:
        return request_origin
    
    logger.debug(f"CORS: rejected origin {request_origin}")
    return ""


def cors_headers(request=None) -> Dict[str, str]:
    """
    Return CORS headers dict. If a request is provided, checks the Origin header
    against the allowlist. Otherwise returns headers for the default allowed origin.
    """
    origin = None
    if request and hasattr(request, 'headers'):
        origin = request.headers.get("origin")
    
    allowed = _get_allowed_origins()
    
    if origin:
        echo_origin = _origin_allowed(origin)
    elif "*" in allowed:
        echo_origin = "*"
    elif allowed:
        echo_origin = allowed[0]
    else:
        echo_origin = ""
    
    if not echo_origin:
        return {}
    
    headers = {
        "Access-Control-Allow-Origin": echo_origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
    }
    
    # Add Vary header when not using wildcard (required by spec)
    if echo_origin != "*":
        headers["Vary"] = "Origin"
    
    return headers
