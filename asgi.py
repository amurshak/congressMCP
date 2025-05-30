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

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the server from the congress_api package
from congress_api.main import server

# Import prompts
from congress_api import prompts_module

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Define endpoint functions first
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
        # Get server info using correct FastMCP API
        tools_count = 0
        resources_count = 0
        tools_list = []
        resources_list = []
        
        # Use the proper FastMCP API to get tools and resources
        try:
            tools_dict = await server.get_tools()
            tools_count = len(tools_dict)
            tools_list = list(tools_dict.keys())[:10]
        except Exception as e:
            tools_count = 0
            tools_list = [f"Error getting tools: {e}"]
        
        try:
            resources_dict = await server.get_resources()
            resources_count = len(resources_dict)
            resources_list = list(resources_dict.keys())[:10]
        except Exception as e:
            resources_count = 0
            resources_list = [f"Error getting resources: {e}"]
        
        return JSONResponse({
            "status": "ok",
            "server_type": str(type(server)),
            "tools_count": tools_count,
            "resources_count": resources_count,
            "tools_sample": tools_list,
            "resources_sample": resources_list,
            "has_tool_manager": hasattr(server, '_tool_manager'),
            "has_resource_manager": hasattr(server, '_resource_manager'),
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "traceback": str(e.__traceback__)
        }, status_code=500)

async def mcp_info(request):
    """Information about the MCP server."""
    try:
        # Get tools and resources using internal managers
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
        return JSONResponse({
            "status": "error",
            "error": str(e),
        }, status_code=500)

async def not_found(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        {"error": "Not found", "path": request.url.path},
        status_code=404
    )

async def server_error(request, exc):
    """Handle 500 errors."""
    return JSONResponse(
        {"error": "Internal server error"},
        status_code=500
    )

# Get the FastMCP ASGI app using new FastMCP 2.3.2+ API
try:
    # Use default path for FastMCP app - it handles /mcp internally
    fastmcp_asgi_app = server.http_app()
    print(f"Successfully created FastMCP http ASGI app")
    print(f"App type: {type(fastmcp_asgi_app)}")
    
    # Add custom routes directly to the FastMCP app
    from starlette.routing import Route
    
    # Get the existing routes from the FastMCP app
    existing_routes = list(fastmcp_asgi_app.router.routes)
    
    # Add our custom routes
    custom_routes = [
        Route("/", endpoint=health_check, methods=["GET"]),
        Route("/health", endpoint=health_check, methods=["GET"]),
        Route("/mcp-debug", endpoint=mcp_debug, methods=["GET"]),
        Route("/mcp-info", endpoint=mcp_info, methods=["GET"]),
    ]
    
    # Combine routes (custom routes first, then FastMCP routes)
    fastmcp_asgi_app.router.routes = custom_routes + existing_routes
    
    # Initialize the API config
    config = get_api_config()
    
    # Add middleware to the FastMCP app
    fastmcp_asgi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add exception handlers to the FastMCP app
    fastmcp_asgi_app.add_exception_handler(404, not_found)
    fastmcp_asgi_app.add_exception_handler(500, server_error)
    
    # Set the FastMCP app as the main app
    app = fastmcp_asgi_app
    
except Exception as e:
    print(f"Error creating FastMCP http app: {e}")
    import traceback
    traceback.print_exc()
    raise