#!/usr/bin/env python3
"""
ASGI wrapper for the Congress.gov API MCP server.
This provides compatibility with ASGI servers like Uvicorn.
"""
import os
import sys
import asyncio
import json
import datetime
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Force single worker for MCP compatibility (set early)
os.environ['WEB_CONCURRENCY'] = '1'
os.environ['GUNICORN_CMD_ARGS'] = '--workers=1'

from starlette.responses import JSONResponse
from starlette.routing import Route

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the server from the congress_api package
from congress_api.main import server

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Define custom endpoint functions
async def health_check(request):
    """Health check endpoint for the ASGI server."""
    config = get_api_config()
    return JSONResponse({
        "status": "ok",
        "environment": ENV,
        "api_key_configured": config["api_key_configured"],
        "caching_enabled": config["caching_enabled"],
        "timestamp": datetime.datetime.now().isoformat()
    })

async def mcp_debug(request):
    """Debug endpoint to test server functionality."""
    try:
        tools_count = 0
        resources_count = 0
        tools_list = []
        resources_list = []
        
        if hasattr(server, '_tool_manager') and hasattr(server._tool_manager, '_tools'):
            tools_count = len(server._tool_manager._tools)
            tools_list = list(server._tool_manager._tools.keys())[:10]
        
        if hasattr(server, '_resource_manager') and hasattr(server._resource_manager, '_resources'):
            resources_count = len(server._resource_manager._resources)
            resources_list = list(server._resource_manager._resources.keys())[:10]
        
        return JSONResponse({
            "status": "ok",
            "server_type": str(type(server)),
            "tools_count": tools_count,
            "resources_count": resources_count,
            "tools_sample": tools_list,
            "resources_sample": resources_list,
        })
    except Exception as e:
        logger.error(f"MCP debug error: {e}")
        return JSONResponse({
            "status": "error",
            "error": str(e),
        }, status_code=500)

# Create the FastMCP HTTP app directly
try:
    logger.info("Creating FastMCP HTTP app...")
    app = server.http_app()
    logger.info(f"Successfully created FastMCP HTTP app: {type(app)}")
    
    # Add custom routes to the FastMCP app
    # The FastMCP app should be a Starlette app, so we can add routes
    if hasattr(app, 'router') and hasattr(app.router, 'routes'):
        # Add our custom routes to the beginning of the route list
        custom_routes = [
            Route("/", endpoint=health_check, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/mcp-debug", endpoint=mcp_debug, methods=["GET"]),
        ]
        
        # Insert custom routes at the beginning
        existing_routes = list(app.router.routes)
        app.router.routes = custom_routes + existing_routes
        
        logger.info("Added custom routes to FastMCP app")
    else:
        logger.warning("Could not add custom routes - FastMCP app structure unexpected")
    
    # Initialize the API config
    config = get_api_config()
    
    # Log server info
    tools_count = 0
    resources_count = 0
    if hasattr(server, '_tool_manager') and hasattr(server._tool_manager, '_tools'):
        tools_count = len(server._tool_manager._tools)
    if hasattr(server, '_resource_manager') and hasattr(server._resource_manager, '_resources'):
        resources_count = len(server._resource_manager._resources)
    
    logger.info(f"Server ready with {tools_count} tools and {resources_count} resources")
    logger.info("MCP endpoint available at /mcp/")
    
except Exception as e:
    logger.error(f"Error creating FastMCP HTTP app: {e}")
    import traceback
    traceback.print_exc()
    
    # Fallback: create a simple Starlette app that explains the error
    from starlette.applications import Starlette
    
    async def error_response(request):
        return JSONResponse({
            "error": "FastMCP server failed to initialize",
            "details": str(e),
            "traceback": traceback.format_exc()
        }, status_code=500)
    
    app = Starlette(
        routes=[
            Route("/", endpoint=error_response, methods=["GET", "POST"]),
            Route("/health", endpoint=error_response, methods=["GET", "POST"]),
            Route("/mcp", endpoint=error_response, methods=["GET", "POST"]),
            Route("/mcp/", endpoint=error_response, methods=["GET", "POST"]),
        ]
    )
    
    logger.error("Created fallback error app")