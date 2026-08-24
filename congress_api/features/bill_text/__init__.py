"""Bill text retrieval and search index.

Importing a SUBMODULE of this package must not boot the MCP server stack: the
``congressmcp cache`` CLI imports ``.cache`` to administer a cache that may be
broken enough to stop the server from starting, and must not pay for (or print
the credential warnings of) ``mcp`` / ``congress_api.core``. So the tool
functions are exposed lazily (PEP 562) instead of imported here; tool
REGISTRATION happens when ``mcp_server.initialize_mcp_features`` imports
``congress_api.features.bill_text.tools`` explicitly.
"""

__all__ = ["search_bill_text", "get_bill_section", "get_bill_toc"]


def __getattr__(name: str):
    if name in __all__:
        from . import tools

        return getattr(tools, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
