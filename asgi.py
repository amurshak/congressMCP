#!/usr/bin/env python3
"""
ASGI deployment with separated MCP and REST API apps.
Mounts FastMCP server and REST API as separate applications.
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

try:
    logger.info("Initializing separated MCP server and REST API...")
    
    # Import separated components
    from congress_api.mcp_server import mcp as mcp_server, initialize_mcp_features
    from congress_api.rest_api import rest_app
    
    # Initialize MCP features
    logger.info("Initializing MCP features...")
    initialize_mcp_features()
    
    # Create the FastMCP HTTP app
    logger.info("Creating FastMCP HTTP app...")
    fastmcp_app = mcp_server.http_app()
    
    # Apply authentication middleware to FastMCP app
    from congress_api.core.auth.auth_middleware import AuthenticationMiddleware
    logger.info("Applying authentication middleware to MCP app...")
    authenticated_mcp_app = AuthenticationMiddleware(fastmcp_app)
    
    # Create the main ASGI app by mounting both applications
    from starlette.applications import Starlette
    from starlette.routing import Mount
    
    logger.info("Mounting MCP server at /mcp/ and REST API at /...")
    
    app = Starlette(routes=[
        Mount("/mcp", authenticated_mcp_app),  # MCP server at /mcp/
        Mount("/", rest_app),  # REST API at root
    ])
    
    # Initialize config and log info
    from congress_api.core.api_config import get_api_config
    config = get_api_config()
    
    tools_count = 0
    resources_count = 0
    if hasattr(mcp_server, '_tool_manager') and hasattr(mcp_server._tool_manager, '_tools'):
        tools_count = len(mcp_server._tool_manager._tools)
    if hasattr(mcp_server, '_resource_manager') and hasattr(mcp_server._resource_manager, '_resources'):
        resources_count = len(mcp_server._resource_manager._resources)

    logger.info(f"Congress MCP server ready with {tools_count} tools and {resources_count} resources")
    logger.info("MCP endpoint available at /mcp/ - REST API available at /")
    logger.info(f"Application mounted successfully: {type(app)}")

except Exception as e:
    error_message = str(e)
    logger.error(f"Failed to create mounted app: {error_message}")
    import traceback
    traceback.print_exc()

    # Fallback error app
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    
    async def error_handler(request):
        return JSONResponse({
            "error": "Application failed to initialize",
            "details": error_message
        }, status_code=500)

    app = Starlette(routes=[
        Route("/", error_handler, methods=["GET", "POST"]),
        Route("/mcp", error_handler, methods=["GET", "POST"]),
        Route("/mcp/", error_handler, methods=["GET", "POST"]),
        Route("/api/health", error_handler, methods=["GET"]),
    ])