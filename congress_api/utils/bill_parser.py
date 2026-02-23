"""
Flexible Bill ID Parser - Converts natural language bill references to API parameters.

Handles various bill reference formats and extracts congress, bill_type, and bill_number
for use with the Congress.gov API.
"""

import re
import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

def parse_bill_reference(bill_ref: str, default_congress: Optional[int] = None) -> Dict[str, Any]:
    """
    Parse a flexible bill reference into structured API parameters.
    
    Supports formats like:
    - 'HR 1234', 'H.R. 1234', 'hr1234'
    - 'S 456', 'S. 456', 's456' 
    - 'HR 1234, 118th Congress', 'H.R. 1234 (118th Congress)'
    - 'hr1234-118', 's456-119'
    - 'HJRES 1', 'SJRES 2', 'HCONRES 3', 'SCONRES 4', 'HRES 5', 'SRES 6'
    
    Args:
        bill_ref: Natural language bill reference string
        default_congress: Default congress number if none specified (e.g., 118 for current)
    
    Returns:
        Dict with parsed parameters: {
            'bill_type': str (normalized to API format),
            'bill_number': int,
            'congress': int,
            'original_reference': str,
            'parse_success': bool,
            'error_message': str (if parse failed)
        }
    
    Examples:
        >>> parse_bill_reference("HR 1234")
        {'bill_type': 'hr', 'bill_number': 1234, 'congress': None, ...}
        
        >>> parse_bill_reference("H.R. 1234, 118th Congress")
        {'bill_type': 'hr', 'bill_number': 1234, 'congress': 118, ...}
        
        >>> parse_bill_reference("s456-119")
        {'bill_type': 's', 'bill_number': 456, 'congress': 119, ...}
    """
    
    if not bill_ref or not isinstance(bill_ref, str):
        return {
            'bill_type': None,
            'bill_number': None,
            'congress': None,
            'original_reference': str(bill_ref) if bill_ref else '',
            'parse_success': False,
            'error_message': 'Bill reference is empty or invalid'
        }
    
    # Normalize input: strip whitespace, convert to lowercase for processing
    original_ref = bill_ref.strip()
    normalized = original_ref.lower().strip()
    
    try:
        # Pattern 1: Compact format with dash separator (check first for specificity)
        # Matches: "hr1234-118", "s456-119"
        compact_pattern = r'^(h\.?r\.?|s\.?|hjres|sjres|hconres|sconres|hres|sres)\.?(\d+)-(\d+)$'
        
        match = re.search(compact_pattern, normalized)
        if match:
            bill_type_raw = match.group(1).replace('.', '').replace(' ', '')
            bill_number = int(match.group(2))
            congress = int(match.group(3))
            
            # Normalize bill type to API format
            bill_type = normalize_bill_type(bill_type_raw)
            
            return {
                'bill_type': bill_type,
                'bill_number': bill_number,
                'congress': congress,
                'original_reference': original_ref,
                'parse_success': True,
                'error_message': None
            }
        
        # Pattern 2: Basic format with optional congress
        # Matches: "hr 1234", "h.r. 1234", "s 456", "hjres 1", etc.
        # With optional congress: "hr 1234, 118th congress", "h.r. 1234 (118th congress)"
        basic_pattern = r'^(h\.?r\.?|s\.?|hjres|sjres|hconres|sconres|hres|sres)\.?\s*(\d+)(?:\s*[-,]\s*(?:(\d+)(?:th|st|nd|rd)?\s*congress)|(?:\s*\((\d+)(?:th|st|nd|rd)?\s*congress\)))?'
        
        match = re.search(basic_pattern, normalized)
        if match:
            bill_type_raw = match.group(1).replace('.', '').replace(' ', '')
            bill_number = int(match.group(2))
            congress_from_suffix = match.group(3) or match.group(4)
            congress = int(congress_from_suffix) if congress_from_suffix else default_congress
            
            # Normalize bill type to API format
            bill_type = normalize_bill_type(bill_type_raw)
            
            return {
                'bill_type': bill_type,
                'bill_number': bill_number,
                'congress': congress,
                'original_reference': original_ref,
                'parse_success': True,
                'error_message': None
            }
        
        # If no patterns match, return parse failure
        return {
            'bill_type': None,
            'bill_number': None,
            'congress': None,
            'original_reference': original_ref,
            'parse_success': False,
            'error_message': f"Could not parse bill reference '{original_ref}'. Supported formats: 'HR 1234', 'H.R. 1234, 118th Congress', 'hr1234-118', 'S 456', etc."
        }
        
    except ValueError as e:
        return {
            'bill_type': None,
            'bill_number': None,
            'congress': None,
            'original_reference': original_ref,
            'parse_success': False,
            'error_message': f"Invalid number format in bill reference '{original_ref}': {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected error parsing bill reference '{original_ref}': {e}")
        return {
            'bill_type': None,
            'bill_number': None,
            'congress': None,
            'original_reference': original_ref,
            'parse_success': False,
            'error_message': f"Unexpected error parsing bill reference: {str(e)}"
        }

def normalize_bill_type(bill_type_raw: str) -> str:
    """
    Normalize bill type to standard Congress.gov API format.
    
    Args:
        bill_type_raw: Raw bill type string (e.g., 'h.r.', 'HR', 'hr', 'HJRES')
    
    Returns:
        Normalized bill type (e.g., 'hr', 's', 'hjres', 'sjres', etc.)
    """
    
    # Remove dots and convert to lowercase
    normalized = bill_type_raw.replace('.', '').replace(' ', '').lower()
    
    # Map common variations to standard API format
    type_mapping = {
        'hr': 'hr',
        'house': 'hr', 
        'hbill': 'hr',
        's': 's',
        'senate': 's',
        'sbill': 's',
        'hjres': 'hjres',
        'hjoint': 'hjres',
        'housejoint': 'hjres',
        'sjres': 'sjres',
        'sjoint': 'sjres',
        'senatejoint': 'sjres',
        'hconres': 'hconres',
        'hconcurrent': 'hconres',
        'houseconcurrent': 'hconres',
        'sconres': 'sconres',
        'sconcurrent': 'sconres',
        'senateconcurrent': 'sconres',
        'hres': 'hres',
        'houseresolution': 'hres',
        'hsimple': 'hres',
        'sres': 'sres',
        'senateresolution': 'sres',
        'ssimple': 'sres'
    }
    
    return type_mapping.get(normalized, normalized)

def validate_bill_params(bill_type: str, bill_number: int, congress: int) -> Tuple[bool, Optional[str]]:
    """
    Validate parsed bill parameters for reasonableness.
    
    Args:
        bill_type: Bill type (hr, s, etc.)
        bill_number: Bill number
        congress: Congress number
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    # Valid bill types for Congress.gov API
    valid_types = {'hr', 's', 'hjres', 'sjres', 'hconres', 'sconres', 'hres', 'sres'}
    
    if bill_type not in valid_types:
        return False, f"Invalid bill type '{bill_type}'. Valid types: {', '.join(sorted(valid_types))}"
    
    if bill_number <= 0 or bill_number > 99999:
        return False, f"Invalid bill number '{bill_number}'. Must be between 1 and 99999"
    
    if congress is not None and (congress < 1 or congress > 200):
        return False, f"Invalid congress number '{congress}'. Must be between 1 and 200"
    
    return True, None

# Example usage and testing
if __name__ == "__main__":
    # Test cases
    test_cases = [
        "HR 1234",
        "H.R. 1234", 
        "hr1234",
        "S 456",
        "s456",
        "HR 1234, 118th Congress",
        "H.R. 1234 (118th Congress)",
        "hr1234-118",
        "s456-119",
        "HJRES 1",
        "SJRES 2", 
        "HCONRES 3",
        "SCONRES 4",
        "HRES 5",
        "SRES 6",
        "invalid bill ref",
        ""
    ]
    
    for test_case in test_cases:
        result = parse_bill_reference(test_case, default_congress=118)
        print(f"'{test_case}' -> {result}")