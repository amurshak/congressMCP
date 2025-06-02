"""
Main application setup for the Congressional MCP server.
Handles FastMCP server creation, routing, and middleware configuration.
"""

# Load environment configuration first
from congress_api.core.api_config import ENV

import logging
import sys
import os
import datetime
import re

# Add the parent directory to sys.path to enable absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

# Import the MCP app - using absolute imports instead of relative
from congress_api.mcp_app import mcp

# Import the features package to register all features with the MCP server
# The features/__init__.py file already imports all the individual modules
# Use a single import to prevent duplicate registrations
import congress_api.features as features

# Import prompts
from congress_api import prompts_module

# Import authentication middleware, Stripe webhook, and key management
from congress_api.core.auth import auth_middleware
from congress_api.core.stripe_webhook import router as stripe_router
from congress_api.core.key_management import router as key_management_router
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware import Middleware
from fastapi import FastAPI
from starlette.responses import JSONResponse

def convert_fastapi_router_to_asgi_app(router, prefix=""):
    """
    Convert a FastAPI router to a standalone FastAPI app that can be mounted.
    
    Args:
        router: FastAPI APIRouter instance
        prefix: Optional path prefix for the routes
        
    Returns:
        FastAPI app that can be mounted in Starlette
    """
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    return app

async def stripe_webhook_handler(request):
    """Wrapper to handle Stripe webhook requests directly in Starlette"""
    from congress_api.core.stripe_webhook import stripe_webhook
    # Convert Starlette request to FastAPI format and call the webhook handler
    stripe_signature = request.headers.get("stripe-signature")
    return await stripe_webhook(request, stripe_signature)

async def stripe_test_handler(request):
    """Test endpoint for Stripe webhooks"""
    return JSONResponse({"status": "test_success", "message": "Stripe test endpoint working"})

def create_app(mcp_server):
    """
    Create the main application with FastMCP and additional routes.
    
    Args:
        mcp_server: The FastMCP server instance
        
    Returns:
        The main Starlette application
    """
    # Get the FastMCP Starlette app using the correct FastMCP 2.3+ API
    fastmcp_app = mcp_server.http_app()
    
    # Convert only the key management router to FastAPI app
    keys_app = convert_fastapi_router_to_asgi_app(key_management_router)
    
    # Create main Starlette app with direct route handlers for Stripe to avoid FastAPI middleware issues
    app = Starlette(
        routes=[
            Route("/stripe/webhook", stripe_webhook_handler, methods=["POST"]),
            Route("/stripe/test", stripe_test_handler, methods=["GET"]),
            Mount("/keys", keys_app),
            Mount("/mcp", fastmcp_app),  # Mount FastMCP at /mcp
        ],
        # Temporarily comment out middleware for debugging
        # middleware=[
        #     Middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
        # ],
        # Important: Pass the lifespan from FastMCP app to handle session management
        lifespan=fastmcp_app.lifespan,
    )
    
    return app

class SensitiveInfoFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""
    
    def __init__(self, patterns=None):
        super().__init__()
        self.patterns = patterns or [
            (r'api_key=([^&\s]+)', 'api_key=REDACTED'),
            (r'"api_key_configured":\s*true', '"api_key_configured": [REDACTED]'),
            (r'"base_url":\s*"[^"]+"', '"base_url": "[REDACTED]"')
        ]
    
    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.patterns:
                record.msg = re.sub(pattern, replacement, record.msg)
        return True

def setup_logging():
    """Configure logging for the application based on environment with security considerations."""
    from congress_api.core.api_config import ENV
    import re
    
    # Determine log level based on environment
    if ENV == "production":
        default_level = logging.INFO
    elif ENV == "staging":
        default_level = logging.INFO
    else:  # development
        default_level = logging.DEBUG
    
    # Allow override via environment variable
    log_level_name = os.getenv("LOG_LEVEL", "")
    if log_level_name:
        try:
            default_level = getattr(logging, log_level_name.upper())
        except AttributeError:
            print(f"Invalid LOG_LEVEL: {log_level_name}. Using default.", file=sys.stderr)
    
    # Configure logging format - JSON in production for better parsing
    if ENV == "production":
        # Simple JSON-like format for production without file paths and line numbers
        log_format = '{"time": "%(asctime)s", "service": "congress-mcp", "level": "%(levelname)s", "message": "%(message)s"}'
    else:
        # More readable format for development and staging, still without exposing file paths
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
    
    # Create a filter for sensitive information
    sensitive_filter = SensitiveInfoFilter()
    
    # Configure handler with filter
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(sensitive_filter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(default_level)
    root_logger.handlers = [handler]  # Replace any existing handlers
    
    # Set specific logger levels
    loggers_config = {
        'congress_api': default_level,
        'congress_api.features': logging.INFO if ENV == "production" else default_level,
        'httpx': logging.WARNING,
        'uvicorn': logging.INFO,
    }
    
    for logger_name, level in loggers_config.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    
    # Log minimal startup information in production
    if ENV == "production":
        logger.info("Application starting in production mode")
    else:
        logger.info(f"Application starting in {ENV} mode with log level {logging.getLevelName(default_level)}")
    
    return logger

def main():
    """Main entry point for the Congress.gov API MCP server."""
    logger = setup_logging()
    logger.info("Starting Congress.gov API MCP server")
    
    # Log server health at startup
    from congress_api.core.api_config import get_api_config, ENV
    config = get_api_config()
    
    # Log minimal server health information
    if ENV == "production":
        # In production, only log that the server is configured
        logger.info("Server configuration loaded")
    else:
        # In development/staging, log minimal configuration details
        # The sensitive info filter will redact sensitive values
        logger.info(f"API key configured: {config['api_key_configured']}")
        logger.info(f"Caching enabled: {config['caching_enabled']}")
    
    # Note: For production monitoring, implement health checks at the infrastructure level
    # such as in the Docker container or using a separate HTTP endpoint in a wrapper application
    
    logger.info("Server is ready")
    return mcp

# This is the object that MCP will look for
server = main()

if __name__ == "__main__":
    import argparse
    import uvicorn
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the Congress.gov API MCP server')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    args = parser.parse_args()
    
    # Create the main application
    main_app = create_app(server)
    
    # Run the server
    print(f"Starting server on {args.host}:{args.port}")
    uvicorn.run(main_app, host=args.host, port=args.port)
