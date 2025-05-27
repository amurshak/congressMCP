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
            "server_type": str(type(server)),
            "server_dir": str(dir(server)[:100]) + "..."
        }
        
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
    
    async def event_stream():
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'message': 'MCP Server Connected', 'timestamp': datetime.datetime.now().isoformat()})}\n\n"
            
            # Get server info for initial handshake
            try:
                tools_info = []
                if hasattr(server, 'tools'):
                    tools_info = [{"name": name, "description": getattr(tool, 'description', 'No description')} 
                                 for name, tool in server.tools.items()]
                
                resources_info = []
                if hasattr(server, 'resources'):
                    resources_info = [{"name": name} for name in server.resources.keys()]
                
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
    Route("/sse", sse_endpoint),  # Add SSE endpoint for mcp-remote
    Route("/", health_check),     # Add root endpoint that redirects to health
]

# Define middleware
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
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