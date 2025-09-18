"""
Amendments Module - Clean API-faithful amendments operations.

This module provides API-faithful access to Congress.gov amendments endpoints
with proper separation of concerns between API calls, data processing,
and response formatting.

Key functions:
- get_amendments: Core /amendment endpoint access (the missing foundation)
- search_amendments: Enhanced with optional keyword filtering
- get_amendment_details: Specific amendment information
- get_amendment_actions: Amendment legislative timeline
"""

# Export only the public API functions
from .api import (
    # Core API-faithful functions
    get_amendments,
    search_amendments,

    # Specific amendment functions
    get_amendment_details,

    # Sub-resource functions
    get_amendment_actions,
    get_amendment_sponsors,
    get_amendment_amendments,
    get_amendment_text,
)

# Define what gets imported with "from amendments import *"
__all__ = [
    # Core functions
    'get_amendments',
    'search_amendments',

    # Specific amendment functions
    'get_amendment_details',

    # Sub-resource functions
    'get_amendment_actions',
    'get_amendment_sponsors',
    'get_amendment_amendments',
    'get_amendment_text',
]

# Module metadata
__version__ = "2.0.0"  # Version 2.0 to reflect API-faithful refactor
__description__ = "API-faithful Congress.gov amendments operations"