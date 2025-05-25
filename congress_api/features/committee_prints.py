# congress_api/features/committee_prints.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Minimal Test Resource ---

@mcp.resource("congress://committee-prints/test")
async def test_committee_prints() -> str:
    """
    A simple test resource for committee prints.
    This is a minimal implementation to test if the server can handle committee prints resources.
    """
    logger.debug("Test committee prints resource called")
    return "Committee Prints Test Resource - Working!"

def format_committee_print_item(print_item: Dict[str, Any]) -> str:
    """Formats a single committee print item for display in a list."""
    lines = [
        f"Chamber: {print_item.get('chamber', 'N/A')}",
        f"Congress: {print_item.get('congress', 'N/A')}",
        f"Jacket Number: {print_item.get('jacketNumber', 'N/A')}",
        f"Update Date: {print_item.get('updateDate', 'N/A')}",
        f"URL: {print_item.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_committee_print_detail(print_item: Dict[str, Any]) -> str:
    """Formats detailed information for a single committee print."""
    lines = [
        f"Title: {print_item.get('title', 'N/A')}",
        f"Citation: {print_item.get('citation', 'N/A')}",
        f"Congress: {print_item.get('congress', 'N/A')}",
        f"Chamber: {print_item.get('chamber', 'N/A')}",
        f"Jacket Number: {print_item.get('jacketNumber', 'N/A')}",
        f"Number: {print_item.get('number', 'N/A')}",
        f"Update Date: {print_item.get('updateDate', 'N/A')}"
    ]
    
    if 'associatedBills' in print_item and print_item['associatedBills']:
        lines.append("Associated Bills:")
        for bill in print_item['associatedBills']:
            lines.append(f"  - {bill.get('type', '')}{bill.get('number', '')} (Congress {bill.get('congress', '')}) - URL: {bill.get('url', 'N/A')}")
    
    if 'committees' in print_item and print_item['committees']:
        lines.append("Committees:")
        for committee in print_item['committees']:
            lines.append(f"  - {committee.get('name', 'N/A')} (System Code: {committee.get('systemCode', 'N/A')}) - URL: {committee.get('url', 'N/A')}")
    
    if 'text' in print_item and print_item['text'].get('url'):
        lines.append(f"Text Versions URL: {print_item['text']['url']} (Count: {print_item['text'].get('count', 'N/A')})")
        
    return "\n".join(lines)

def format_committee_print_text_version(text_item: Dict[str, Any]) -> str:
    """Formats a single text version item."""
    lines = [
        f"  Type: {text_item.get('type', 'N/A')}",
        f"    URL: {text_item.get('url', 'N/A')}",
        f"    Is Errata: {text_item.get('isErrata', 'N/A')}"
    ]
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://committee-prints/latest")
async def get_latest_committee_prints() -> str:
    """
    Get a list of the most recent committee prints.
    Returns the 10 most recently updated prints by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug("Fetching latest committee prints")
    data = await make_api_request("/committee-print", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest committee prints: {data['error']}")
        return f"Error retrieving latest committee prints: {data['error']}"
    
    prints = data.get("committeePrints", [])
    if not prints:
        logger.info("No committee prints found")
        return "No committee prints found."
    
    logger.info(f"Found {len(prints)} committee prints")
    lines = ["Latest Committee Prints:"]
    for print_item in prints:
        lines.append("")
        lines.append(format_committee_print_item(print_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-prints/{congress}")
async def get_committee_prints_by_congress(congress: int) -> str:
    """
    Get committee prints for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    ctx = mcp.get_context()
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee prints for Congress {congress}")
    data = await make_api_request(f"/committee-print/{congress}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee prints for Congress {congress}: {data['error']}")
        return f"Error retrieving committee prints for Congress {congress}: {data['error']}"
    
    prints = data.get("committeePrints", [])
    if not prints:
        logger.info(f"No committee prints found for Congress {congress}")
        return f"No committee prints found for Congress {congress}."
    
    logger.info(f"Found {len(prints)} committee prints for Congress {congress}")
    lines = [f"Committee Prints for Congress {congress}:"]
    for print_item in prints:
        lines.append("")
        lines.append(format_committee_print_item(print_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-prints/{congress}/{chamber}")
async def get_committee_prints_by_congress_and_chamber(congress: int, chamber: str) -> str:
    """
    Get committee prints for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
    """
    ctx = mcp.get_context()
    params = {
        "limit": 20,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee prints for Congress {congress}, Chamber {chamber}")
    data = await make_api_request(f"/committee-print/{congress}/{chamber}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving committee prints for Congress {congress}, Chamber {chamber}: {data['error']}")
        return f"Error retrieving committee prints for Congress {congress}, Chamber {chamber}: {data['error']}"
    
    prints = data.get("committeePrints", [])
    if not prints:
        logger.info(f"No committee prints found for Congress {congress}, Chamber {chamber}")
        return f"No committee prints found for Congress {congress}, Chamber {chamber}."
    
    logger.info(f"Found {len(prints)} committee prints for Congress {congress}, Chamber {chamber}")
    lines = [f"Committee Prints for Congress {congress}, Chamber {chamber}:"]
    for print_item in prints:
        lines.append("")
        lines.append(format_committee_print_item(print_item))
    
    return "\n".join(lines)

@mcp.resource("congress://committee-prints/{congress}/{chamber}/{jacket_number}")
async def get_committee_print_details(congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get detailed information for a specific committee print.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
        jacket_number: The jacket number for the print.
    """
    ctx = mcp.get_context()
    
    logger.debug(f"Fetching details for committee print {congress}/{chamber}/{jacket_number}")
    data = await make_api_request(f"/committee-print/{congress}/{chamber}/{jacket_number}", ctx)
    
    if "error" in data:
        logger.error(f"Error retrieving committee print details: {data['error']}")
        return f"Error retrieving committee print details: {data['error']}"
    
    # According to the API documentation, the response contains a 'committeePrint' key with an array
    if "committeePrint" not in data:
        logger.warning(f"No committeePrint field in response for {congress}/{chamber}/{jacket_number}")
        return f"No committee print found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
    
    committee_print_data = data.get("committeePrint", [])
    if not committee_print_data:
        logger.warning(f"Empty committeePrint data for {congress}/{chamber}/{jacket_number}")
        return f"No committee print found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
    
    # The API returns an array with a single item
    print_item = committee_print_data[0] if isinstance(committee_print_data, list) else committee_print_data
    logger.info(f"Successfully retrieved committee print details for {congress}/{chamber}/{jacket_number}")
    
    return format_committee_print_detail(print_item)

@mcp.resource("congress://committee-prints/{congress}/{chamber}/{jacket_number}/text")
async def get_committee_print_text_versions(congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get text versions for a specific committee print.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
        jacket_number: The jacket number for the print.
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching text versions for committee print {congress}/{chamber}/{jacket_number}")
    data = await make_api_request(f"/committee-print/{congress}/{chamber}/{jacket_number}/text", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving text versions: {data['error']}")
        return f"Error retrieving text versions: {data['error']}"
    
    # According to the API documentation, check for formats array
    if "formats" not in data:
        logger.warning(f"No formats field in response for {congress}/{chamber}/{jacket_number}/text")
        return f"No text versions found for Committee Print {congress}/{chamber}/{jacket_number}."
    
    text_versions = data.get("formats", [])
    if not text_versions:
        logger.info(f"No text versions found for Committee Print {congress}/{chamber}/{jacket_number}")
        return f"No text versions found for Committee Print {congress}/{chamber}/{jacket_number}."
    
    logger.info(f"Found {len(text_versions)} text versions for Committee Print {congress}/{chamber}/{jacket_number}")
    lines = [f"Text Versions for Committee Print {congress}/{chamber}/{jacket_number}:"]
    
    for text_item in text_versions:
        lines.append("")
        lines.append(format_committee_print_text_version(text_item))
    
    return "\n".join(lines)

# --- MCP Tools ---

@mcp.tool()
async def search_committee_prints(
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None,
) -> str:
    """
    Search for committee prints based on various criteria.
    
    Args:
        offset: The starting record for pagination.
        limit: The number of records to return (max 250).
        from_date_time: Start date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        to_date_time: End date for filtering by update date (YYYY-MM-DDT00:00:00Z).
    """
    ctx = mcp.get_context()
    params = {}
    endpoint = "/committee-print"
    
    # Add query parameters if provided
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    if from_date_time is not None:
        params["fromDateTime"] = from_date_time
    if to_date_time is not None:
        params["toDateTime"] = to_date_time
    
    # Default limit if not provided
    if "limit" not in params:
        params["limit"] = 10
    
    # Always request JSON format
    params["format"] = "json"
    
    logger.debug(f"Searching committee prints with params: {params}")
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching committee prints: {data['error']}")
        return f"Error searching committee prints: {data['error']}"
    
    prints = data.get("committeePrints", [])
    if not prints:
        logger.info("No committee prints found matching search criteria")
        return "No committee prints found matching your search criteria."
    
    logger.info(f"Found {len(prints)} committee prints matching search criteria")
    lines = ["Search Results - Committee Prints:"]
    for print_item in prints:
        lines.append("\n" + format_committee_print_item(print_item))
    
    return "\n".join(lines)
