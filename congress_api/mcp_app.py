# mcp_app.py - DEPRECATED: Split into mcp_server.py and rest_api.py
# This file is kept minimal for backward compatibility only

# Import the separated components
from .mcp_server import mcp, initialize_mcp_features
from .rest_api import rest_app

# Legacy alias for backward compatibility
initialize_features = initialize_mcp_features

# Export the main components for existing imports
__all__ = ['mcp', 'initialize_features', 'rest_app']