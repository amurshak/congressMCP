# mcp_app.py - Backward compatibility shim
# All 30+ feature files import `mcp` from here. Delegates to mcp_server.py.

from .mcp_server import mcp, initialize_mcp_features

# Legacy alias
initialize_features = initialize_mcp_features

__all__ = ['mcp', 'initialize_features']
