#!/usr/bin/env python3
"""
Production server script for the Congress.gov API MCP server.
This script provides a production-ready ASGI server using uvicorn.
"""
import os
import sys
import argparse
import uvicorn
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Congress.gov API MCP server in production mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), 
                        help="Port to bind the server to (defaults to PORT env var or 8000)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (keep at 1 for MCP servers)")
    parser.add_argument("--env", default="production", help="Environment (production, staging, development)")
    parser.add_argument("--log-level", default="info", help="Log level (debug, info, warning, error, critical)")
    return parser.parse_args()

def main():
    """Main entry point for the production server."""
    args = parse_args()
    
    # Force single worker for MCP server compatibility
    if args.workers > 1:
        print(f"Warning: MCP servers work best with single worker. Forcing workers=1 (was {args.workers})")
        args.workers = 1
    
    # Set environment variable for the API config
    os.environ["CONGRESS_API_ENV"] = args.env
    os.environ["LOG_LEVEL"] = args.log_level.upper()
    
    # Load environment variables from the appropriate .env file
    if args.env == "production":
        load_dotenv(".env.production", override=True)
    elif args.env == "staging":
        load_dotenv(".env.staging", override=True)
    else:
        load_dotenv(".env", override=True)
    
    print(f"Starting Congress.gov API MCP server in {args.env} mode...")
    print(f"Server will run on {args.host}:{args.port} with {args.workers} worker(s)")
    
    # Run the server using uvicorn with our ASGI wrapper
    uvicorn.run(
        "asgi:app",  # Use the ASGI app from asgi.py
        host=args.host,
        port=args.port,
        workers=args.workers,  # Keep at 1 for MCP compatibility
        log_level=args.log_level,
        reload=args.env == "development",  # Only enable auto-reload in development
        access_log=True,  # Enable access logging
    )

if __name__ == "__main__":
    main()