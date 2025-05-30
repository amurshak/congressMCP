#!/usr/bin/env python3
"""
ASGI wrapper for the Congress.gov API MCP server.
This follows the FastMCP ASGI integration documentation.
"""
import os
import sys
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Force single worker for MCP compatibility (set early)
os.environ['WEB_CONCURRENCY'] = '1'
os.environ['GUNICORN_CMD_ARGS'] = '--workers=1'

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

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
        "timestamp": "2025-05-30T14:43:00Z"
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

try:
    logger.info("Creating FastMCP HTTP app...")
    
    # Step 1: Create the FastMCP ASGI app with custom middleware
    custom_middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    
    # Create the MCP app with middleware and mount path
    mcp_app = server.http_app(middleware=custom_middleware, path='/mcp')
    logger.info(f"FastMCP HTTP app created: {type(mcp_app)}")
    
    # Step 2: Create main Starlette app and mount MCP app
    # THE KEY: Pass the MCP app's lifespan to the parent app
    app = Starlette(
        routes=[
            Route("/", endpoint=health_check, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/mcp-debug", endpoint=mcp_debug, methods=["GET"]),
            Mount("/mcp", app=mcp_app),  # Mount MCP app at /mcp
        ],
        lifespan=mcp_app.lifespan,  # CRITICAL: Use MCP app's lifespan
    )
    
    # Initialize the API config
    config = get_api_config()
    
    # Log server info
    tools_count = 0
    resources_count = 0
    if hasattr(server, '_tool_manager') and hasattr(server._tool_manager, '_tools'):
        tools_count = len(server._tool_manager._tools)
    if hasattr(server, '_resource_manager') and hasattr(server._resource_manager, '_resources'):
        resources_count = len(server._resource_manager._resources)
    
    logger.info(f"Congress MCP server ready with {tools_count} tools and {resources_count} resources")
    logger.info("MCP endpoint will be available at /mcp/")
    
except Exception as e:
    logger.error(f"Error creating FastMCP HTTP app: {e}")
    import traceback
    traceback.print_exc()
    
    # Fallback: create a simple error app
    async def error_response(request):
        return JSONResponse({
            "error": "FastMCP server failed to initialize",
            "details": str(e),
        }, status_code=500)
    
    app = Starlette(
        routes=[
            Route("/", endpoint=health_check, methods=["GET"]),
            Route("/health", endpoint=health_check, methods=["GET"]),
            Route("/mcp", endpoint=error_response, methods=["GET", "POST"]),
            Route("/mcp/", endpoint=error_response, methods=["GET", "POST"]),
        ]
    )
    
    logger.error("Created fallback error app")
    raise