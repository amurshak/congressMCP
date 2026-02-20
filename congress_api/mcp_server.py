# mcp_server.py - Pure MCP server with tool registrations only
from mcp.server.fastmcp import FastMCP
from .core.client_handler import app_lifespan

# Create the MCP server with metadata and stateless HTTP transport
mcp = FastMCP(
    "Congress MCP",
    description="Access legislative data from the Congress.gov API",
    version="1.1.0",
    dependencies=["httpx", "python-dotenv"],
    lifespan=app_lifespan,
    transport="streamable-http",  # Use streamable HTTP transport (correct per FastMCP docs)
    stateless_http=True  # Enable stateless mode to handle concurrent requests properly
)

def initialize_mcp_features():
    """Initialize all MCP tool features - called after server setup to avoid circular imports"""
    # Initialize individual tools (replaces bucket system)
    from .features import legislation_tools, members_committees_tools
    
    # Initialize remaining bucket tools (to be converted in future tasks)
    from .features.buckets import (
        # legislation_hub,  # DEPRECATED: Replaced by individual tools in legislation_tools.py
        # members_and_committees,  # DEPRECATED: Replaced by individual tools in members_committees_tools.py
        voting_and_nominations, 
        records_and_hearings,
        committee_intelligence,
        research_and_professional
    )