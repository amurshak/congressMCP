# mcp_server.py - Pure MCP server with tool registrations only
from mcp.server.mcpserver import MCPServer
from .core.client_handler import app_lifespan

mcp = MCPServer(
    "Congress MCP",
    instructions="Access 91+ congressional data tools via the Congress.gov API",
    lifespan=app_lifespan,
)

def initialize_mcp_features():
    """Initialize all MCP tool features - called after server setup to avoid circular imports"""
    # Importing these modules triggers @mcp.tool() decorator registration.
    # ruff: noqa: F401
    from .features import (  # noqa: F401
        bills_tool,
        bill_text,
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
