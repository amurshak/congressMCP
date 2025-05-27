#!/usr/bin/env python3
"""
ASGI wrapper for the Congress.gov API MCP server.
This provides compatibility with ASGI servers like Uvicorn.
"""
import os
import sys
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the MCP server
from run_server import server

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Simple health check endpoint
async def health_check(request):
    """Health check endpoint for the ASGI server."""
    config = get_api_config()
    import datetime
    return JSONResponse({
        "status": "ok",
        "environment": ENV,
        "api_key_configured": config["api_key_configured"],
        "caching_enabled": config["caching_enabled"],
        "timestamp": datetime.datetime.now().isoformat()
    })

# MCP info endpoint
async def mcp_info(request):
    """Information about the MCP server."""
    # Get basic information about the MCP server
    resources_count = 0
    tools_count = 0
    
    # Try to get resource and tool counts safely
    try:
        if hasattr(server, 'resources'):
            resources_count = len(server.resources)
        if hasattr(server, 'tools'):
            tools_count = len(server.tools)
    except Exception:
        pass
    
    return JSONResponse({
        "name": "Congress MCP",
        "description": "Congressional API MCP Server",
        "version": "1.0.0",
        "resources_count": resources_count,
        "tools_count": tools_count
    })

# Simple 404 handler
async def not_found(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        {"error": "Not found", "path": request.url.path},
        status_code=404
    )

# Simple 500 handler
async def server_error(request, exc):
    """Handle 500 errors."""
    return JSONResponse(
        {"error": "Internal server error"},
        status_code=500
    )

# Define routes
routes = [
    Route("/health", health_check),
    Route("/mcp-info", mcp_info),
]

# Define middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    ),
]

# Create the ASGI application
app = Starlette(
    debug=(ENV != "production"),
    routes=routes,
    middleware=middleware,
    exception_handlers={
        404: not_found,
        500: server_error,
    },
)
