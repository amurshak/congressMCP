# mcp_server.py - Pure MCP server with tool registrations only
import os

from mcp.server.fastmcp import FastMCP
from .core.client_handler import app_lifespan

# Transport is configurable: "stdio" (default, local) or "streamable-http" (hosted)
TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")

mcp = FastMCP(
    "Congress MCP",
    instructions="Access 91+ congressional data tools via the Congress.gov API",
    dependencies=["httpx", "python-dotenv"],
    lifespan=app_lifespan,
    stateless_http=(TRANSPORT == "streamable-http"),
)

def initialize_mcp_features():
    """Initialize all MCP tool features - called after server setup to avoid circular imports"""
    # Importing these modules triggers @mcp.tool() decorator registration.
    # ruff: noqa: F401
    from .features import (  # noqa: F401
        bills_tool,
        amendments_tool,
        treaties_and_summaries_tool,
        members_committees_tools,
    )

    from .features.buckets import (  # noqa: F401
        voting_and_nominations,
        records_and_hearings,
        committee_intelligence,
        research_and_professional,
        laws,
    )
