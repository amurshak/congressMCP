"""
Bills Module - Clean API-faithful bills operations.

This module provides API-faithful access to Congress.gov bills endpoints
with proper separation of concerns between API calls, data processing,
and response formatting.

Key functions:
- get_bills: Core /bill endpoint access (the missing foundation)
- search_bills: Enhanced with optional keyword filtering
- get_bill_details: Specific bill information
- get_bill_actions: Bill legislative timeline
- get_recent_bills: Convenience function for recent activity
"""

# Export only the public API functions
from .api import (
    # Core API-faithful functions
    get_bills,
    search_bills,
    get_recent_bills,
    get_bills_by_date_range,

    # Specific bill functions
    get_bill_details,

    # Sub-resource functions
    get_bill_actions,
    get_bill_text,
    get_bill_text_versions,
    get_bill_titles,
    get_bill_summaries,
    get_bill_amendments,
    get_bill_committees,
    get_bill_cosponsors,
    get_bill_related_bills,
    get_bill_subjects,
    get_bill_content,
)

# Define what gets imported with "from bills import *"
__all__ = [
    # Core functions
    'get_bills',
    'search_bills',
    'get_recent_bills',
    'get_bills_by_date_range',

    # Specific bill functions
    'get_bill_details',

    # Sub-resource functions
    'get_bill_actions',
    'get_bill_text',
    'get_bill_text_versions',
    'get_bill_titles',
    'get_bill_summaries',
    'get_bill_amendments',
    'get_bill_committees',
    'get_bill_cosponsors',
    'get_bill_related_bills',
    'get_bill_subjects',
    'get_bill_content',
]

# Module metadata
__version__ = "2.0.0"  # Version 2.0 to reflect API-faithful refactor
__description__ = "API-faithful Congress.gov bills operations"