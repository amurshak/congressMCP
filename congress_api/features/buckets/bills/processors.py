"""
Bills Data Processors - Business logic for processing bill data.

Contains all data processing logic including filtering, deduplication,
and validation. No formatting or API calls.
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timedelta

# Import existing processing infrastructure
from ....core.validators import ParameterValidator
from ....core.response_utils import BillsProcessor

# Set up logger
logger = logging.getLogger(__name__)


class BillsDataProcessor:
    """Handles all bill data processing logic."""

    @staticmethod
    async def filter_by_keywords(
        bills: List[Dict[str, Any]],
        keywords: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Filter bills by keywords in title and policy area with enhanced reliability.

        Args:
            bills: List of bill dictionaries from API response
            keywords: Keywords to search for
            limit: Maximum number of results to return

        Returns:
            Filtered and deduplicated list of bills
        """
        try:
            # Validate inputs
            if not isinstance(bills, list):
                logger.warning("Bills parameter must be a list")
                return []

            if not keywords or not bills:
                # Apply deduplication even for unfiltered results
                deduplicated = BillsProcessor.deduplicate_bills(bills)
                return deduplicated[:limit]

            # Validate limit
            limit_validation = ParameterValidator.validate_limit_range(limit)
            if not limit_validation.is_valid:
                logger.warning(f"Invalid limit in filter: {limit}, using default")
                limit = 10
            else:
                limit = limit_validation.sanitized_value

            keywords_lower = keywords.lower().strip()
            if not keywords_lower:
                deduplicated = BillsProcessor.deduplicate_bills(bills)
                return deduplicated[:limit]

            filtered_bills = []

            for bill in bills:
                if not isinstance(bill, dict):
                    continue

                # Check title
                title = bill.get('title', '').lower()
                # Check policy area
                policy_area = bill.get('policyArea', {}).get('name', '').lower() if bill.get('policyArea') else ''

                # Search in multiple fields
                keyword_list = [kw.strip() for kw in keywords_lower.split() if kw.strip()]

                title_match = any(keyword in title for keyword in keyword_list)
                policy_match = any(keyword in policy_area for keyword in keyword_list)

                if title_match or policy_match:
                    filtered_bills.append(bill)
                    if len(filtered_bills) >= limit * 2:  # Get extra for deduplication
                        break

            # Apply deduplication to filtered results
            deduplicated = BillsProcessor.deduplicate_bills(filtered_bills)

            logger.debug(f"Filtered {len(bills)} bills to {len(filtered_bills)}, deduplicated to {len(deduplicated)}")

            return deduplicated[:limit]

        except Exception as e:
            logger.error(f"Error in filter_by_keywords: {str(e)}")
            # Return original bills (up to limit) on error
            return bills[:limit] if isinstance(bills, list) else []

    @staticmethod
    def deduplicate_bills(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate bills from a list.

        Args:
            bills: List of bill dictionaries

        Returns:
            Deduplicated list of bills
        """
        try:
            return BillsProcessor.deduplicate_bills(bills)
        except Exception as e:
            logger.error(f"Error in deduplicate_bills: {str(e)}")
            return bills

    @staticmethod
    def calculate_date_range(days_back: int) -> str:
        """
        Convert days_back parameter to Congress.gov API fromDateTime format.

        Args:
            days_back: Number of days to look back

        Returns:
            ISO formatted datetime string for API
        """
        try:
            if not isinstance(days_back, int) or days_back < 0:
                logger.warning(f"Invalid days_back: {days_back}, using default 30")
                days_back = 30

            from_date = datetime.utcnow() - timedelta(days=days_back)
            return from_date.strftime('%Y-%m-%dT%H:%M:%SZ')

        except Exception as e:
            logger.error(f"Error calculating date range: {str(e)}")
            # Default to 30 days back
            from_date = datetime.utcnow() - timedelta(days=30)
            return from_date.strftime('%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def validate_and_clean_bill_data(bill_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean bill data structure.

        Args:
            bill_data: Raw bill data from API

        Returns:
            Validated and cleaned bill data
        """
        try:
            if not isinstance(bill_data, dict):
                logger.warning("Bill data must be a dictionary")
                return {}

            # Use existing response utils for cleaning
            # This would integrate with the existing BillsProcessor.clean_bills_response
            return bill_data

        except Exception as e:
            logger.error(f"Error validating bill data: {str(e)}")
            return {}

    @staticmethod
    def extract_bills_from_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract bills array from API response structure.

        Args:
            api_response: Raw API response

        Returns:
            List of bills or empty list if extraction fails
        """
        try:
            if not isinstance(api_response, dict):
                return []

            # Handle different response structures
            if 'bills' in api_response:
                bills = api_response['bills']
            elif 'bill' in api_response:
                # Single bill response
                bills = [api_response['bill']]
            else:
                logger.warning("No bills found in API response")
                return []

            if not isinstance(bills, list):
                logger.warning("Bills data is not a list")
                return []

            return bills

        except Exception as e:
            logger.error(f"Error extracting bills from response: {str(e)}")
            return []

    @staticmethod
    def apply_congress_filter(bills: List[Dict[str, Any]], congress: Optional[int]) -> List[Dict[str, Any]]:
        """
        Filter bills by congress number (client-side filtering for cross-congress searches).

        Args:
            bills: List of bills
            congress: Congress number to filter by

        Returns:
            Filtered bills list
        """
        try:
            if congress is None:
                return bills

            filtered = []
            for bill in bills:
                if isinstance(bill, dict) and bill.get('congress') == congress:
                    filtered.append(bill)

            return filtered

        except Exception as e:
            logger.error(f"Error filtering by congress: {str(e)}")
            return bills

    @staticmethod
    def apply_bill_type_filter(bills: List[Dict[str, Any]], bill_type: Optional[str]) -> List[Dict[str, Any]]:
        """
        Filter bills by bill type (client-side filtering for cross-type searches).

        Args:
            bills: List of bills
            bill_type: Bill type to filter by

        Returns:
            Filtered bills list
        """
        try:
            if bill_type is None:
                return bills

            bill_type_lower = bill_type.lower()
            filtered = []
            for bill in bills:
                if isinstance(bill, dict):
                    bill_type_from_data = bill.get('type', '').lower()
                    if bill_type_from_data == bill_type_lower:
                        filtered.append(bill)

            return filtered

        except Exception as e:
            logger.error(f"Error filtering by bill type: {str(e)}")
            return bills