"""
Amendments Data Processors - Business logic for amendment data processing.

This module contains business logic only:
- Data filtering and enhancement
- Search functionality
- Date range calculations
- No API calls or response formatting
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from ....core.response_utils import ResponseProcessor

logger = logging.getLogger(__name__)

class AmendmentsDataProcessor:
    """
    Handles business logic for amendment data processing.

    This class contains pure business logic without API calls or formatting.
    """

    @staticmethod
    def filter_by_keywords(amendments: List[Dict[str, Any]], keywords: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """
        Filter amendments by keywords in purpose and description.

        This is an enhancement feature that provides smart search capabilities
        beyond the basic Congress.gov API filtering.

        Args:
            amendments: List of amendment data from API
            keywords: Keywords to search for (None for no filtering)
            limit: Maximum number of results to return

        Returns:
            Filtered and limited list of amendments
        """
        if not keywords:
            return amendments[:limit]

        keywords_lower = keywords.lower().split()
        filtered = []

        for amendment in amendments:
            # Search in amendment purpose
            purpose = amendment.get('purpose', '').lower()
            description = amendment.get('description', '').lower()

            # Check if any keyword matches
            matches = any(
                keyword in purpose or keyword in description
                for keyword in keywords_lower
            )

            if matches:
                filtered.append(amendment)

            # Stop when we have enough results
            if len(filtered) >= limit:
                break

        return filtered

    @staticmethod
    def calculate_date_range(days_back: int) -> tuple[str, str]:
        """
        Calculate fromDateTime and toDateTime for recent amendments.

        Args:
            days_back: Number of days to look back

        Returns:
            Tuple of (fromDateTime, toDateTime) in Congress.gov API format
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Congress.gov API expects this exact datetime format
        from_dt = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_dt = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        return from_dt, to_dt

    @staticmethod
    def deduplicate_amendments(amendments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate amendments based on key fields.

        Args:
            amendments: List of amendment data

        Returns:
            Deduplicated list of amendments
        """
        return ResponseProcessor.deduplicate_results(
            amendments,
            ["number", "type", "congress"]
        )

    @staticmethod
    def extract_amendments_from_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract amendment list from various API response structures.

        The Congress.gov API can return amendments in different structures
        depending on the endpoint. This function normalizes the extraction.

        Args:
            data: Raw API response data

        Returns:
            List of amendment dictionaries
        """
        # Try different possible structures
        if "amendments" in data:
            amendments = data["amendments"]

            # Handle list vs dict with 'item' key
            if isinstance(amendments, list):
                return amendments
            elif isinstance(amendments, dict) and "item" in amendments:
                items = amendments["item"]
                return items if isinstance(items, list) else [items]

        # Fallback: check if data itself is the amendment
        if isinstance(data, dict) and ("number" in data or "type" in data):
            return [data]

        return []

    @staticmethod
    def apply_api_pagination(amendments: List[Dict[str, Any]], limit: int, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Apply pagination to amendment results.

        Args:
            amendments: List of amendments
            limit: Maximum number of results
            offset: Starting position (0-based)

        Returns:
            Paginated list of amendments
        """
        start_idx = offset
        end_idx = offset + limit
        return amendments[start_idx:end_idx]