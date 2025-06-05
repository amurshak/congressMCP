"""
Feature Configuration for Congressional MCP Server

This module provides a simple way to enable/disable features for tool complexity management.
All changes are easily reversible by modifying the ENABLED_FEATURES list.
"""

import os
from typing import List, Dict, Any

# Environment variable to override feature configuration
FEATURE_MODE = os.getenv("CONGRESS_MCP_FEATURE_MODE", "essential").lower()

# Essential Core Tools (Top 5) - Highest ROI
ESSENTIAL_FEATURES = [
    "bills",      # search_bills, get_bill_details, get_bill_text, get_bill_content
    "members",    # search_members, get_member_details, get_member_sponsored_legislation
]

# High-Value Secondary Features (Next tier)
HIGH_VALUE_FEATURES = [
    "amendments",     # search_amendments, get_amendment_details, get_amendment_actions
    "committees",     # search_committees, get_committee_details, get_committee_bills
    "house_votes",    # get_house_vote_details, get_house_vote_member_votes
    "summaries",      # search_summaries, get_bill_summaries
]

# Specialized Features (Lower frequency but important)
SPECIALIZED_FEATURES = [
    "nominations",    # search_nominations, get_nomination_details
    "treaties",       # search_treaties, get_treaty_details, get_treaty_text
    "congress_info",  # get_congress_info
]

# Archive/Document Features (Least frequently used)
ARCHIVE_FEATURES = [
    "committee_reports",
    "committee_prints", 
    "committee_meetings",
    "hearings",
    "congressional_record",
    "daily_congressional_record",
    "bound_congressional_record",
    "house_communications",
    "house_requirements", 
    "senate_communications",
    "crs_reports",
]

# Feature mode configurations
FEATURE_MODES = {
    "essential": ESSENTIAL_FEATURES,
    "high_value": ESSENTIAL_FEATURES + HIGH_VALUE_FEATURES,
    "specialized": ESSENTIAL_FEATURES + HIGH_VALUE_FEATURES + SPECIALIZED_FEATURES,
    "full": ESSENTIAL_FEATURES + HIGH_VALUE_FEATURES + SPECIALIZED_FEATURES + ARCHIVE_FEATURES,
}

def get_enabled_features() -> List[str]:
    """
    Get the list of enabled features based on configuration.
    
    Returns:
        List of feature module names to import and register
    """
    enabled = FEATURE_MODES.get(FEATURE_MODE, ESSENTIAL_FEATURES)
    
    # Log the configuration for debugging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Congressional MCP Feature Mode: {FEATURE_MODE}")
    logger.info(f"Enabled Features ({len(enabled)}): {', '.join(enabled)}")
    
    return enabled

def get_feature_stats() -> Dict[str, Any]:
    """
    Get statistics about feature configuration.
    
    Returns:
        Dictionary with feature mode statistics
    """
    enabled = get_enabled_features()
    total_features = len(ESSENTIAL_FEATURES + HIGH_VALUE_FEATURES + SPECIALIZED_FEATURES + ARCHIVE_FEATURES)
    
    return {
        "mode": FEATURE_MODE,
        "enabled_count": len(enabled),
        "total_available": total_features,
        "enabled_features": enabled,
        "coverage_percentage": round((len(enabled) / total_features) * 100, 1)
    }

# Utility function to check if a feature is enabled
def is_feature_enabled(feature_name: str) -> bool:
    """Check if a specific feature is enabled in current configuration."""
    return feature_name in get_enabled_features()
