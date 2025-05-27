#!/usr/bin/env python3
"""
Special server script for Heroku deployment of the Congress.gov API MCP server.
This script ensures all resources and tools are properly registered.
"""
import os
import sys
import logging
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import and initialize the MCP server
from congress_api.mcp_app import mcp

# Import all features to register them with the MCP server
from congress_api.features import bills, members, committees, congress_info
from congress_api.features import amendments, summaries, committee_reports, committee_prints
from congress_api.features import committee_meetings, hearings, congressional_record
from congress_api.features import daily_congressional_record, bound_congressional_record
from congress_api.features import house_communications, house_requirements
from congress_api.features import senate_communications, nominations, crs_reports, treaties

# Import prompts
from congress_api import prompts_module

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Set up logging
from congress_api.main import setup_logging
logger = setup_logging()
logger.info("Starting Congress.gov API MCP server for Heroku")

# Log server health at startup
config = get_api_config()
logger.info("Server configuration loaded")
logger.info("Server is ready")

# This is the server object that will be used by the ASGI wrapper
server = mcp

# Health check endpoint
async def health_check(request):
    """Health check endpoint for the ASGI server."""
    return JSONResponse({
        "status": "ok",
        "environment": ENV,
        "api_key_configured": config["api_key_configured"],
        "caching_enabled": config["caching_enabled"],
        "timestamp": __import__("datetime").datetime.now().isoformat()
    })

# MCP info endpoint
async def mcp_info(request):
    """Information about the MCP server."""
    # Get basic information about the MCP server
    resources_count = 0
    tools_count = 0
    resources_list = []
    tools_list = []
    
    # Try to get resource and tool counts safely
    try:
        # Get resources and tools if available
        if hasattr(server, 'resources'):
            resources_count = len(server.resources)
            resources_list = list(server.resources.keys())[:10] if resources_count > 0 else []
        
        if hasattr(server, 'tools'):
            tools_count = len(server.tools)
            tools_list = list(server.tools.keys())[:10] if tools_count > 0 else []
    except Exception as e:
        return JSONResponse({
            "name": "Congress MCP",
            "description": "Congressional API MCP Server",
            "version": "1.0.0",
            "error": str(e)
        })
    
    return JSONResponse({
        "name": "Congress MCP",
        "description": "Congressional API MCP Server",
        "version": "1.0.0",
        "resources_count": resources_count,
        "tools_count": tools_count,
        "resources_sample": resources_list,
        "tools_sample": tools_list
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

# Mount the MCP server to the ASGI app
server.mount_to_app(app, path="/sse")

# When run directly, we don't need to do anything else
if __name__ == "__main__":
    # This script is meant to be imported by the ASGI server
    pass
