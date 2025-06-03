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

# AGGRESSIVE CONCURRENCY ENFORCEMENT - Heroku buildpack overrides
# Multiple environment variables to ensure single worker
os.environ['WEB_CONCURRENCY'] = '1'
os.environ['GUNICORN_CMD_ARGS'] = '--workers=1'
os.environ['UVICORN_WORKERS'] = '1'
os.environ['PYTHON_CONCURRENCY'] = '1'  # Heroku Python buildpack specific
os.environ['PORT_CONCURRENCY'] = '1'    # Additional override
os.environ['DYNO_WORKERS'] = '1'        # Heroku-specific override
os.environ['WEB_CONCURRENCY_AGGRESSIVE'] = '1'

# Log the current configuration
logger.info(f"WEB_CONCURRENCY: {os.environ.get('WEB_CONCURRENCY', 'NOT SET')}")
logger.info(f"UVICORN_WORKERS: {os.environ.get('UVICORN_WORKERS', 'NOT SET')}")
logger.info(f"PYTHON_CONCURRENCY: {os.environ.get('PYTHON_CONCURRENCY', 'NOT SET')}")

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import server after path setup
from congress_api.mcp_app import mcp as server

# Configure environment
from congress_api.core.api_config import get_api_config, ENV

try:
    logger.info("Creating direct FastMCP HTTP app...")
    
    # Initialize features BEFORE creating the HTTP app
    from congress_api.mcp_app import initialize_features
    logger.info("Initializing MCP features...")
    initialize_features()
    
    # TEMPORARILY DISABLE AUTH MIDDLEWARE TO TEST FASTMCP STREAMING
    # Use FastMCP directly as the main ASGI app
    # No mounting, no wrapper, no complexity
    # from congress_api.core.auth_middleware import AuthenticationMiddleware
    # app = AuthenticationMiddleware(server.http_app())
    app = server.http_app()  # Test FastMCP without middleware wrapper
    
    logger.info(f"FastMCP app created successfully: {type(app)}")
    
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
