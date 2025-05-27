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
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the MCP server from mcp_app
from congress_api.mcp_app import mcp

# Import all features to register them with the MCP server
from congress_api.features import bills, members, committees, congress_info, amendments, summaries
from congress_api.features import committee_reports, committee_prints, committee_meetings, hearings
from congress_api.features import congressional_record, daily_congressional_record, bound_congressional_record
from congress_api.features import house_communications, house_requirements, senate_communications, nominations, crs_reports, treaties

# Import prompts
from congress_api import prompts_module

# This is the server object that will be used by the ASGI wrapper
server = mcp

# Force initialization and check tools registration
try:
    print(f"Server type: {type(server)}")
    
    # Check tool manager directly
    if hasattr(server, '_tool_manager'):
        tool_manager = server._tool_manager
        print(f"Tool manager type: {type(tool_manager)}")
        
        # Check different possible attributes for tools (based on FastMCP docs)
        tool_attrs = ['_tools', 'tools', 'registered_tools', '_registered_tools']
        tools_found = False
        tools_count = 0
        
        for attr in tool_attrs:
            if hasattr(tool_manager, attr):
                tools_dict = getattr(tool_manager, attr)
                if tools_dict:
                    tools_count = len(tools_dict)
                    print(f"Found {tools_count} tools in {attr}: {list(tools_dict.keys())[:10]}")  # Show first 10
                    tools_found = True
                    break
                else:
                    print(f"Attribute {attr} exists but is empty")
        
        if not tools_found:
            print(f"Tool manager attributes: {[attr for attr in dir(tool_manager) if 'tool' in attr.lower()]}")
            print(f"All tool manager attributes: {[attr for attr in dir(tool_manager) if not attr.startswith('__')]}")
    else:
        print("Server has no '_tool_manager' attribute")
    
    # Also check if server itself has any tool-related attributes
    server_tool_attrs = [attr for attr in dir(server) if 'tool' in attr.lower() and not attr.startswith('__')]
    print(f"Server tool-related attributes: {server_tool_attrs}")
    
    print(f"Server initialized - found {tools_count} tools total")
    
except Exception as e:
    print(f"Error during server initialization: {e}")
    import traceback
    traceback.print_exc()

# Initialize the API config
from congress_api.core.api_config import get_api_config
config = get_api_config()

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

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

# SSE endpoint for MCP remote connections
async def sse_endpoint(request):
    """SSE endpoint for MCP remote connections."""
    
    # Handle both GET and POST requests
    method = request.method
    print(f"SSE endpoint called with method: {method}")
    
    async def event_stream():
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'MCP Server Connected', 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
            
            # Get server info for initial handshake
            try:
                tools_info = []
                resources_info = []
                
                # For FastMCP servers, use the list methods
                if hasattr(server, 'list_tools'):
                    try:
                        tools_list = await server.list_tools()
                        if hasattr(tools_list, 'tools'):
                            tools_info = [{"name": tool.name, "description": tool.description} 
                                         for tool in tools_list.tools]
                    except Exception as e:
                        tools_info = [{"error": f"Error listing tools: {str(e)}"}]
                
                if hasattr(server, 'list_resources'):
                    try:
                        resources_list = await server.list_resources()
                        if hasattr(resources_list, 'resources'):
                            resources_info = [{"uri": resource.uri, "name": resource.name} 
                                            for resource in resources_list.resources]
                    except Exception as e:
                        resources_info = [{"error": f"Error listing resources: {str(e)}"}]
                
                # Send server capabilities
                yield f"data: {json.dumps({'type': 'capabilities', 'tools': tools_info, 'resources': resources_info, 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
                
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Error getting server info: {str(e)}', 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
            
            # Keep connection alive with periodic heartbeats
            heartbeat_count = 0
            while True:
                heartbeat_count += 1
                yield f"data: {json.dumps({'type': 'heartbeat', 'count': heartbeat_count, 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
        except asyncio.CancelledError:
            # Client disconnected
            yield f"data: {json.dumps({'type': 'disconnected', 'message': 'Client disconnected', 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }
    )

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
    Route("/sse", sse_endpoint, methods=["GET", "POST"]),  # Add POST method support
    Route("/", health_check),     # Add root endpoint that redirects to health
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
)