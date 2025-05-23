# client_handler.py
import sys
import json
import httpx
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP, Context
from .api_config import API_KEY, BASE_URL

# Application context for handling API connection
@dataclass
class AppContext:
    """Application context for the Congress.gov API server."""
    api_key: str
    client: httpx.AsyncClient

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage API client lifecycle."""
    print("Initializing Congress.gov API client...", file=sys.stderr)
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Test connection if API key is available
        if API_KEY:
            try:
                print(f"Testing connection to Congress.gov API...", file=sys.stderr)
                response = await client.get(f"/congress?api_key={API_KEY}")
                response.raise_for_status()
                print("Successfully connected to Congress.gov API", file=sys.stderr)
            except httpx.HTTPStatusError as e:
                print(f"WARNING: Failed to connect to Congress.gov API: {e}", file=sys.stderr)
                print("The server will start, but API requests may fail.", file=sys.stderr)
        else:
            print("No API key provided. The server will start, but API requests will fail.", file=sys.stderr)
        
        # Yield context to server
        context = AppContext(api_key=API_KEY or "MISSING_API_KEY", client=client)
        print("Server context initialized successfully", file=sys.stderr)
        yield context

# Helper function for API requests
async def make_api_request(endpoint: str, ctx: Context, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Make a request to the Congress.gov API with proper error handling."""
    try:
        print(f"DEBUG: Starting make_api_request for endpoint: {endpoint}", file=sys.stderr)
        app_ctx = ctx.request_context.lifespan_context
        client = app_ctx.client
        api_key = app_ctx.api_key
        
        # Prepare parameters
        request_params = params or {}
        request_params["api_key"] = api_key

        # Ensure we always request JSON format
        if "format" not in request_params:
            request_params["format"] = "json"
        
        print(f"DEBUG: Making request to {endpoint} with params: {request_params}", file=sys.stderr)
        response = await client.get(endpoint, params=request_params)
        response.raise_for_status()
        print(f"DEBUG: Request successful with status: {response.status_code}", file=sys.stderr)
        return response.json()
    except httpx.HTTPStatusError as e:
        error_message = f"API request failed: {e.response.status_code} - {e.response.text}"
        ctx.error(error_message) # Log the error to the MCP context
        # Return a dictionary indicating an error
        return {"error": error_message, "status_code": e.response.status_code}
    except httpx.RequestError as e:
        error_message = f"Request failed: {str(e)}"
        ctx.error(error_message) # Log the error to the MCP context
        # Return a dictionary indicating a request error
        return {"error": error_message}
    except json.JSONDecodeError:
        error_message = f"API returned non-JSON response for endpoint {endpoint}: {response.text}"
        ctx.error(error_message)
        return {"error": error_message}
    except Exception as e:
        error_message = f"An unexpected error occurred during API request to {endpoint}: {str(e)}"
        ctx.error(error_message)
        return {"error": error_message}
