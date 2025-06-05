"""
Response processing utilities for Congressional MCP APIs.

This module provides utilities for deduplication, pagination, and response
processing to ensure consistent and clean API responses.
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Set
from collections import OrderedDict

logger = logging.getLogger(__name__)

class ResponseProcessor:
    """Utilities for processing and cleaning API responses."""
    
    @staticmethod
    def deduplicate_results(
        results: List[Dict[str, Any]], 
        key_fields: List[str],
        preserve_order: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results based on specified key fields.
        
        Args:
            results: List of result dictionaries
            key_fields: Fields to use for deduplication (e.g., ['congress', 'number'])
            preserve_order: Whether to preserve the original order
            
        Returns:
            Deduplicated list of results
        """
        if not results:
            return results
        
        seen_keys: Set[tuple] = set()
        deduplicated = []
        
        for result in results:
            # Create a tuple of key field values for comparison
            key_values = []
            for field in key_fields:
                value = result.get(field)
                # Normalize the value for comparison
                if isinstance(value, str):
                    value = value.strip().lower()
                key_values.append(value)
            
            key_tuple = tuple(key_values)
            
            if key_tuple not in seen_keys:
                seen_keys.add(key_tuple)
                deduplicated.append(result)
            else:
                logger.debug(f"Removing duplicate result with key: {key_tuple}")
        
        original_count = len(results)
        final_count = len(deduplicated)
        
        if original_count != final_count:
            logger.info(f"Deduplicated results: {original_count} -> {final_count} ({original_count - final_count} duplicates removed)")
        
        return deduplicated
    
    @staticmethod
    def paginate_results(
        results: List[Dict[str, Any]], 
        limit: int,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Apply pagination to results.
        
        Args:
            results: List of result dictionaries
            limit: Maximum number of results to return
            offset: Number of results to skip
            
        Returns:
            Paginated list of results
        """
        if not results:
            return results
        
        start_index = max(0, offset)
        end_index = start_index + limit
        
        paginated = results[start_index:end_index]
        
        logger.debug(f"Paginated results: showing {len(paginated)} of {len(results)} total results (offset: {offset}, limit: {limit})")
        
        return paginated
    
    @staticmethod
    def sort_results(
        results: List[Dict[str, Any]], 
        sort_field: str,
        reverse: bool = False,
        default_value: Any = ""
    ) -> List[Dict[str, Any]]:
        """
        Sort results by a specified field.
        
        Args:
            results: List of result dictionaries
            sort_field: Field to sort by
            reverse: Whether to sort in descending order
            default_value: Default value for missing fields
            
        Returns:
            Sorted list of results
        """
        if not results:
            return results
        
        def sort_key(item: Dict[str, Any]) -> Any:
            value = item.get(sort_field, default_value)
            # Handle different data types for sorting
            if isinstance(value, str):
                return value.lower()
            return value
        
        sorted_results = sorted(results, key=sort_key, reverse=reverse)
        
        logger.debug(f"Sorted {len(results)} results by '{sort_field}' (reverse: {reverse})")
        
        return sorted_results
    
    @staticmethod
    def filter_results(
        results: List[Dict[str, Any]], 
        filter_func: Callable[[Dict[str, Any]], bool]
    ) -> List[Dict[str, Any]]:
        """
        Filter results using a custom function.
        
        Args:
            results: List of result dictionaries
            filter_func: Function that returns True for items to keep
            
        Returns:
            Filtered list of results
        """
        if not results:
            return results
        
        filtered = [result for result in results if filter_func(result)]
        
        original_count = len(results)
        final_count = len(filtered)
        
        logger.debug(f"Filtered results: {original_count} -> {final_count} ({original_count - final_count} filtered out)")
        
        return filtered
    
    @staticmethod
    def enrich_results(
        results: List[Dict[str, Any]], 
        enrichment_func: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich results with additional data or formatting.
        
        Args:
            results: List of result dictionaries
            enrichment_func: Function to enrich each result
            
        Returns:
            Enriched list of results
        """
        if not results:
            return results
        
        enriched = []
        for result in results:
            try:
                enriched_result = enrichment_func(result)
                enriched.append(enriched_result)
            except Exception as e:
                logger.warning(f"Failed to enrich result: {e}")
                enriched.append(result)  # Keep original on error
        
        logger.debug(f"Enriched {len(results)} results")
        
        return enriched

# Convenience classes for specific API types
class BoundCongressionalRecordProcessor:
    """Specialized processor for Bound Congressional Record responses."""
    
    @staticmethod
    def deduplicate_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bound congressional record issues."""
        return ResponseProcessor.deduplicate_results(
            issues, 
            key_fields=['congress', 'volumeNumber', 'date'],
            preserve_order=True
        )
    
    @staticmethod
    def sort_by_date(issues: List[Dict[str, Any]], newest_first: bool = True) -> List[Dict[str, Any]]:
        """Sort issues by date."""
        return ResponseProcessor.sort_results(
            issues,
            sort_field='date',
            reverse=newest_first,
            default_value='1900-01-01'
        )

class BillsProcessor:
    """Specialized processor for Bills responses."""
    
    @staticmethod
    def deduplicate_bills(bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bills."""
        return ResponseProcessor.deduplicate_results(
            bills,
            key_fields=['congress', 'type', 'number'],
            preserve_order=True
        )
    
    @staticmethod
    def filter_by_congress(bills: List[Dict[str, Any]], congress: int) -> List[Dict[str, Any]]:
        """Filter bills by congress number."""
        return ResponseProcessor.filter_results(
            bills,
            lambda bill: bill.get('congress') == congress
        )
    
    @staticmethod
    def deduplicate_cosponsors(cosponsors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bill cosponsors."""
        return ResponseProcessor.deduplicate_results(
            cosponsors,
            key_fields=['bioguideId'],
            preserve_order=True
        )
    
    @staticmethod
    def deduplicate_text_versions(text_versions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bill text versions."""
        return ResponseProcessor.deduplicate_results(
            text_versions,
            key_fields=['type', 'date'],
            preserve_order=True
        )
    
    @staticmethod
    def deduplicate_titles(titles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bill titles."""
        return ResponseProcessor.deduplicate_results(
            titles,
            key_fields=['titleType', 'title'],
            preserve_order=True
        )
    
    @staticmethod
    def deduplicate_related_bills(related_bills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate related bills."""
        return ResponseProcessor.deduplicate_results(
            related_bills,
            key_fields=['congress', 'type', 'number'],
            preserve_order=True
        )
    
    @staticmethod
    def deduplicate_summaries(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bill summaries."""
        return ResponseProcessor.deduplicate_results(
            summaries,
            key_fields=['actionDesc', 'actionDate'],
            preserve_order=True
        )
    
    @staticmethod
    def deduplicate_committees(committees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate bill committees."""
        return ResponseProcessor.deduplicate_results(
            committees,
            key_fields=['name', 'chamber'],
            preserve_order=True
        )

class AmendmentsProcessor:
    """Specialized processor for Amendments responses."""
    
    @staticmethod
    def deduplicate_amendments(amendments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate amendments."""
        return ResponseProcessor.deduplicate_results(
            amendments,
            key_fields=['congress', 'type', 'number'],
            preserve_order=True
        )
    
    @staticmethod
    def sort_by_update_date(amendments: List[Dict[str, Any]], newest_first: bool = True) -> List[Dict[str, Any]]:
        """Sort amendments by update date."""
        return ResponseProcessor.sort_results(
            amendments,
            sort_field='updateDate',
            reverse=newest_first,
            default_value='1900-01-01T00:00:00Z'
        )

class MembersProcessor:
    """Specialized processor for Members API responses."""
    
    @staticmethod
    def deduplicate_members(members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate members based on bioguideId."""
        return ResponseProcessor.deduplicate_results(
            members,
            key_fields=['bioguideId'],
            preserve_order=True
        )
    
    @staticmethod
    def sort_members_by_name(members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort members by last name."""
        return ResponseProcessor.sort_results(
            members,
            sort_field='name',
            reverse=False,
            default_value='ZZZ'
        )

class CommitteePrintsProcessor:
    """Specialized processor for Committee Prints API responses."""
    
    @staticmethod
    def deduplicate_committee_prints(prints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate committee prints based on congress, chamber, and jacketNumber."""
        return ResponseProcessor.deduplicate_results(
            prints,
            key_fields=['congress', 'chamber', 'jacketNumber'],
            preserve_order=True
        )
    
    @staticmethod
    def sort_prints_by_update_date(prints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort committee prints by update date (most recent first)."""
        return ResponseProcessor.sort_results(
            prints,
            sort_field='updateDate',
            reverse=True,
            default_value='1900-01-01T00:00:00+00:00'
        )
    
    @staticmethod
    def filter_prints_by_congress(prints: List[Dict[str, Any]], congress: int) -> List[Dict[str, Any]]:
        """Filter committee prints by congress number."""
        return ResponseProcessor.filter_results(
            prints,
            lambda print_item: print_item.get('congress') == congress
        )
    
    @staticmethod
    def filter_prints_by_chamber(prints: List[Dict[str, Any]], chamber: str) -> List[Dict[str, Any]]:
        """Filter committee prints by chamber."""
        chamber_lower = chamber.lower().strip()
        return ResponseProcessor.filter_results(
            prints,
            lambda print_item: print_item.get('chamber', '').lower().strip() == chamber_lower
        )

class CommitteeReportsProcessor:
    """Specialized processor for Committee Reports responses."""
    
    @staticmethod
    def deduplicate_reports(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate committee reports."""
        return ResponseProcessor.deduplicate_results(
            reports,
            key_fields=['congress', 'type', 'number'],
            preserve_order=True
        )
    
    @staticmethod
    def filter_by_congress(reports: List[Dict[str, Any]], congress: int) -> List[Dict[str, Any]]:
        """Filter reports by congress number."""
        return ResponseProcessor.filter_results(
            reports,
            lambda report: report.get('congress') == congress
        )
    
    @staticmethod
    def filter_by_type(reports: List[Dict[str, Any]], report_type: str) -> List[Dict[str, Any]]:
        """Filter reports by type."""
        return ResponseProcessor.filter_results(
            reports,
            lambda report: report.get('type', '').lower() == report_type.lower()
        )
    
    @staticmethod
    def filter_conference_reports(reports: List[Dict[str, Any]], conference_only: bool = True) -> List[Dict[str, Any]]:
        """Filter for conference reports only."""
        return ResponseProcessor.filter_results(
            reports,
            lambda report: report.get('isConferenceReport', False) == conference_only
        )
    
    @staticmethod
    def sort_by_date(reports: List[Dict[str, Any]], newest_first: bool = True) -> List[Dict[str, Any]]:
        """Sort reports by update date."""
        return ResponseProcessor.sort_results(
            reports,
            sort_field='updateDate',
            reverse=newest_first,
            default_value='1900-01-01'
        )

# Utility functions for common response processing patterns
def process_api_response(
    data: Dict[str, Any],
    data_key: str,
    deduplication_keys: Optional[List[str]] = None,
    sort_field: Optional[str] = None,
    sort_reverse: bool = False,
    limit: Optional[int] = None,
    filter_func: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> List[Dict[str, Any]]:
    """
    Process API response with common operations.
    
    Args:
        data: Raw API response data
        data_key: Key containing the results array
        deduplication_keys: Fields to use for deduplication
        sort_field: Field to sort by
        sort_reverse: Whether to sort in descending order
        limit: Maximum number of results to return
        filter_func: Optional filter function
        
    Returns:
        Processed list of results
    """
    if data_key not in data:
        logger.warning(f"Data key '{data_key}' not found in response")
        return []
    
    results = data[data_key]
    if not isinstance(results, list):
        logger.warning(f"Data at key '{data_key}' is not a list")
        return []
    
    # Apply filter if provided
    if filter_func:
        results = ResponseProcessor.filter_results(results, filter_func)
    
    # Deduplicate if keys provided
    if deduplication_keys:
        results = ResponseProcessor.deduplicate_results(results, deduplication_keys)
    
    # Sort if field provided
    if sort_field:
        results = ResponseProcessor.sort_results(results, sort_field, sort_reverse)
    
    # Apply limit if provided
    if limit:
        results = ResponseProcessor.paginate_results(results, limit)
    
    return results

def clean_bound_congressional_record_response(data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Clean and process bound congressional record response."""
    return process_api_response(
        data=data,
        data_key='boundCongressionalRecord',
        deduplication_keys=['congress', 'volumeNumber', 'date'],
        sort_field='date',
        sort_reverse=True,
        limit=limit
    )

def clean_bills_response(data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Clean and process bills response."""
    return process_api_response(
        data=data,
        data_key='bills',
        deduplication_keys=['congress', 'type', 'number'],
        sort_field='updateDate',
        sort_reverse=True,
        limit=limit
    )

def clean_amendments_response(data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Clean and process amendments response."""
    return process_api_response(
        data=data,
        data_key='amendments',
        deduplication_keys=['congress', 'type', 'number'],
        sort_field='updateDate',
        sort_reverse=True,
        limit=limit
    )

def clean_committee_prints_response(data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Clean and process committee prints response."""
    return process_api_response(
        data=data,
        data_key='committeePrints',
        deduplication_keys=['congress', 'chamber', 'jacketNumber'],
        sort_field='updateDate',
        sort_reverse=True,
        limit=limit
    )

def clean_committee_reports_response(data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Clean and process committee reports response."""
    return process_api_response(
        data=data,
        data_key='committeeReports',
        deduplication_keys=['congress', 'type', 'number'],
        sort_field='updateDate',
        sort_reverse=True,
        limit=limit
    )
