#!/usr/bin/env python3
"""
Direct FastMCP ASGI deployment - No mounting, no complexity.
Uses the FastMCP app directly as the main ASGI app.
"""
import os
import sys
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Force single worker for MCP compatibility
os.environ['WEB_CONCURRENCY'] = '1'
os.environ['GUNICORN_CMD_ARGS'] = '--workers=1'

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the server and create_app function from the congress_api package
from congress_api.main import server, create_app

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

try:
    logger.info("Creating direct FastMCP HTTP app...")
    
    # Create the FastAPI app with authentication middleware and routers
    app = create_app(server)
    
    logger.info(f"FastMCP app created successfully with authentication middleware: {type(app)}")
    
    # Initialize config and log info
    config = get_api_config()
    
    tools_count = 0
    resources_count = 0
    if hasattr(server, '_tool_manager') and hasattr(server._tool_manager, '_tools'):
        tools_count = len(server._tool_manager._tools)
    if hasattr(server, '_resource_manager') and hasattr(server._resource_manager, '_resources'):
        resources_count = len(server._resource_manager._resources)
    
    logger.info(f"Congress MCP server ready with {tools_count} tools and {resources_count} resources")
    logger.info("MCP endpoint available at /mcp/ (FastMCP default path)")
    
except Exception as e:
    logger.error(f"Failed to create FastMCP app: {e}")
    import traceback
    traceback.print_exc()
    
    # Fallback error app
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    
    async def error_handler(request):
        return JSONResponse({
            "error": "FastMCP failed to initialize",
            "details": str(e)
        }, status_code=500)
    
    app = Starlette(routes=[
        Route("/", error_handler, methods=["GET", "POST"]),
        Route("/mcp", error_handler, methods=["GET", "POST"]),
        Route("/mcp/", error_handler, methods=["GET", "POST"]),
    ])
    raise
