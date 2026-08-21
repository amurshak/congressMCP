# mcp_server.py - Pure MCP server with tool registrations only
import os

from mcp.server.mcpserver import MCPServer
from .core.client_handler import app_lifespan


def _bill_text_only() -> bool:
    # Isolation mode: expose ONLY the bill-text tools. They are self-sufficient --
    # given congress + bill_type + number they resolve the version and fetch from
    # GovInfo internally, needing no other tool (verified: get_bill_toc on S.1801/119
    # self-resolves to the `rs` version and returns a full TOC). Useful for a focused
    # bill-text deployment or for evaluating the feature in isolation.
    return os.getenv("CONGRESSMCP_BILL_TEXT_ONLY", "").strip().lower() in {"1", "true", "yes", "on"}


mcp = MCPServer(
    "Congress MCP",
    instructions=(
        "Bill-text retrieval and search only: search_bill_text, get_bill_section, "
        "get_bill_toc. Pass congress + bill_type (e.g. 's', 'hr') + number; version "
        "resolution and GovInfo fetch are automatic."
        if _bill_text_only()
        else "Access 91+ congressional data tools via the Congress.gov API"
    ),
    lifespan=app_lifespan,
)

def initialize_mcp_features():
    """Initialize all MCP tool features - called after server setup to avoid circular imports"""
    # Importing a feature module triggers its @mcp.tool() decorator registration.
    # ruff: noqa: F401
    if _bill_text_only():
        from .features import bill_text  # noqa: F401 -- the three bill-text tools only
        return

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
