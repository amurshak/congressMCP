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
from contextlib import asynccontextmanager

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

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

# Global reference to the FastMCP app
fastmcp_app = None

# Define endpoint functions
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
            "fastmcp_app_available": fastmcp_app is not None,
        })
    except Exception as e:
        logger.error(f"MCP debug error: {e}")
        return JSONResponse({
            "status": "error",
            "error": str(e),
        }, status_code=500)

# Create the combined lifespan manager
@asynccontextmanager
async def lifespan(app):
    """Combined lifespan manager that properly handles FastMCP initialization."""
    global fastmcp_app
    
    logger.info("Starting application lifespan...")
    
    try:
        # Create the FastMCP HTTP app
        logger.info("Creating FastMCP HTTP app...")
        fastmcp_app = server.http_app()
        logger.info(f"FastMCP HTTP app created: {type(fastmcp_app)}")
        
        # The key insight: we need to start the FastMCP app's lifespan context
        # and keep it running during our app's lifetime
        if hasattr(fastmcp_app, 'lifespan') and fastmcp_app.lifespan is not None:
            logger.info("Starting FastMCP lifespan context...")
            async with fastmcp_app.lifespan(fastmcp_app):
                logger.info("FastMCP lifespan started successfully")
                
                # Mount the FastMCP app to our main app now that it's initialized
                app.mount("/mcp", fastmcp_app)
                logger.info("FastMCP app mounted at /mcp")
                
                # Yield control back to the application
                yield
                
                logger.info("FastMCP lifespan ending...")
        else:
            logger.warning("FastMCP app has no lifespan - trying without lifespan management")
            app.mount("/mcp", fastmcp_app)
            yield
            
    except Exception as e:
        logger.error(f"Error in lifespan management: {e}")
        import traceback
        traceback.print_exc()
        
        # Create a fallback error handler for the MCP endpoint
        async def mcp_error_handler(request):
            return JSONResponse({
                "error": "FastMCP initialization failed",
                "details": str(e)
            }, status_code=500)
        
        # Add error route
        app.router.routes.append(
            Route("/mcp", endpoint=mcp_error_handler, methods=["GET", "POST"])
        )
        app.router.routes.append(
            Route("/mcp/", endpoint=mcp_error_handler, methods=["GET", "POST"])
        )
        
        # Still yield to allow the rest of the app to work
        yield
    
    logger.info("Application lifespan ended")

# Exception handlers
async def not_found(request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        {"error": "Not found", "path": request.url.path},
        status_code=404
    )

async def server_error(request, exc):
    """Handle 500 errors."""
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        {"error": "Internal server error", "details": str(exc)},
        status_code=500
    )

# Create the main Starlette app with the combined lifespan
app = Starlette(
    debug=ENV != "production",
    routes=[
        Route("/", endpoint=health_check, methods=["GET"]),
        Route("/health", endpoint=health_check, methods=["GET"]),
        Route("/mcp-debug", endpoint=mcp_debug, methods=["GET"]),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ],
    exception_handlers={
        404: not_found,
        500: server_error,
    },
    lifespan=lifespan
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

logger.info(f"Server configured with {tools_count} tools and {resources_count} resources")
logger.info("Application ready - FastMCP will be initialized on startup")