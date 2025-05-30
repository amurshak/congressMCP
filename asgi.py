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

# Initialize the API config
from congress_api.core.api_config import get_api_config
config = get_api_config()

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Get the Starlette app from FastMCP for streamable_http transport with proper configuration
# For production, we need to ensure the FastMCP app is properly configured
# Using streamable_http instead of SSE as per FastMCP v2.3.0+ recommendations
try:
    # For streamable_http, we need to get the streamable HTTP ASGI app
    fastmcp_asgi_app = server.streamable_http_app()
    print(f"Successfully created FastMCP streamable_http ASGI app")
    print(f"App type: {type(fastmcp_asgi_app)}")
except Exception as e:
    print(f"Error creating FastMCP streamable_http app: {e}")
    # Fallback: create a simple FastMCP app
    from fastmcp import FastMCP
    
    fallback_server = FastMCP(
        "Congress MCP Fallback",
        description="Fallback Congressional API MCP Server",
        version="1.0.0"
    )
    fastmcp_asgi_app = fallback_server.streamable_http_app()

# Simple health check endpoint
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

# MCP debug endpoint to test server functionality
async def mcp_debug(request):
    """Debug endpoint to test MCP server functionality."""
    try:
        # Test if we can list tools and resources
        tools_result = await server.list_tools()
        resources_result = await server.list_resources()
        
        return JSONResponse({
            "status": "ok",
            "server_type": str(type(server)),
            "tools_count": len(tools_result.tools) if hasattr(tools_result, 'tools') else 0,
            "resources_count": len(resources_result.resources) if hasattr(resources_result, 'resources') else 0,
            "tools_sample": [tool.name for tool in tools_result.tools[:5]] if hasattr(tools_result, 'tools') else [],
            "resources_sample": [resource.uri for resource in resources_result.resources[:5]] if hasattr(resources_result, 'resources') else [],
            "fastmcp_app_type": str(type(fastmcp_asgi_app))
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "server_type": str(type(server)),
            "fastmcp_app_type": str(type(fastmcp_asgi_app))
        }, status_code=500)

# MCP info endpoint
async def mcp_info(request):
    """Information about the MCP server."""
    # Get basic information about the MCP server
    resources_count = 0
    tools_count = 0
    resources_list = []
    tools_list = []
    server_attrs = {}
    
    # Try to get resource and tool counts safely
    try:
        # Check server attributes
        server_attrs = {
            "has_resources_attr": hasattr(server, 'resources'),
            "has_tools_attr": hasattr(server, 'tools'),
            "has_list_tools": hasattr(server, 'list_tools'),
            "has_list_resources": hasattr(server, 'list_resources'),
            "server_type": str(type(server)),
            "server_dir": str(dir(server)[:100]) + "..."
        }
        
        # For FastMCP servers, use the list methods
        if hasattr(server, 'list_tools'):
            try:
                tools_result = await server.list_tools()
                print(f"Tools result: {tools_result}")  # Debug logging
                if hasattr(tools_result, 'tools'):
                    tools_count = len(tools_result.tools)
                    tools_list = [tool.name for tool in tools_result.tools[:10]]
                else:
                    server_attrs["tools_result_attrs"] = str(dir(tools_result))
            except Exception as e:
                server_attrs["tools_error"] = str(e)
                print(f"Error listing tools: {e}")  # Debug logging
        
        if hasattr(server, 'list_resources'):
            try:
                resources_result = await server.list_resources()
                print(f"Resources result: {resources_result}")  # Debug logging
                if hasattr(resources_result, 'resources'):
                    resources_count = len(resources_result.resources)
                    resources_list = [resource.uri for resource in resources_result.resources[:10]]
                else:
                    server_attrs["resources_result_attrs"] = str(dir(resources_result))
            except Exception as e:
                server_attrs["resources_error"] = str(e)
                print(f"Error listing resources: {e}")  # Debug logging
                
        # Also try to access internal managers directly using the correct attribute
        if hasattr(server, '_tool_manager'):
            try:
                tool_manager = server._tool_manager
                # Use _tools instead of tools (based on the logs showing it works)
                if hasattr(tool_manager, '_tools'):
                    direct_tools_count = len(tool_manager._tools)
                    server_attrs["direct_tools_count"] = direct_tools_count
                    if direct_tools_count > 0:
                        tools_count = direct_tools_count
                        tools_list = list(tool_manager._tools.keys())[:10]
                        print(f"Found {direct_tools_count} tools via direct _tools access")
                elif hasattr(tool_manager, 'tools'):
                    direct_tools_count = len(tool_manager.tools)
                    server_attrs["direct_tools_count"] = direct_tools_count
                    if direct_tools_count > 0:
                        tools_count = direct_tools_count
                        tools_list = list(tool_manager.tools.keys())[:10]
            except Exception as e:
                server_attrs["direct_tools_error"] = str(e)
                
        if hasattr(server, '_resource_manager'):
            try:
                resource_manager = server._resource_manager
                # Use _resources instead of resources 
                if hasattr(resource_manager, '_resources'):
                    direct_resources_count = len(resource_manager._resources)
                    server_attrs["direct_resources_count"] = direct_resources_count
                    if direct_resources_count > 0:
                        resources_count = direct_resources_count
                        resources_list = list(resource_manager._resources.keys())[:10]
                        print(f"Found {direct_resources_count} resources via direct _resources access")
                elif hasattr(resource_manager, 'resources'):
                    direct_resources_count = len(resource_manager.resources)
                    server_attrs["direct_resources_count"] = direct_resources_count
                    if direct_resources_count > 0:
                        resources_count = direct_resources_count
                        resources_list = list(resource_manager.resources.keys())[:10]
            except Exception as e:
                server_attrs["direct_resources_error"] = str(e)
        
        # Fallback to old method if available
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
            "error": str(e),
            "server_attrs": server_attrs
        })
    
    return JSONResponse({
        "name": "Congress MCP",
        "description": "Congressional API MCP Server",
        "version": "1.0.0",
        "resources_count": resources_count,
        "tools_count": tools_count,
        "resources_sample": resources_list,
        "tools_sample": tools_list,
        "server_attrs": server_attrs
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
    Route("/mcp-debug", mcp_debug),
    Route("/", health_check),     # Add root endpoint that redirects to health
    Mount("/mcp", fastmcp_asgi_app), # Mount FastMCP app for streamable_http transport
]

# Define middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],  # Add POST method
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
    lifespan=fastmcp_asgi_app.lifespan if hasattr(fastmcp_asgi_app, 'lifespan') else None
)