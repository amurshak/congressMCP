# congress_api/features/committee_prints.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.api_wrapper import safe_committee_prints_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.exceptions import APIErrorResponse, ErrorType, format_error_response, CommonErrors
from ..core.response_utils import CommitteePrintsProcessor, clean_committee_prints_response
from ..core.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Functions ---

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

# --- MCP Tools ---

@require_paid_access
@mcp.tool("get_latest_committee_prints")
async def get_latest_committee_prints(ctx: Context) -> str:
    """
    Get a list of the most recent committee prints.
    Returns the 10 most recently updated prints by default.
    """
    # Parameter validation
    limit = 10
    limit_result = ParameterValidator.validate_limit_range(limit)
    if not limit_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "limit", limit, limit_result.error_message
        )
        logger.error(f"Parameter validation failed: {limit_result.error_message}")
        return format_error_response(error)
    
    params = {
        "limit": limit,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug("Fetching latest committee prints with reliability framework")
    try:
        data = await safe_committee_prints_request("/committee-print", ctx, params)
        
        if "error" in data:
            error = CommonErrors.api_server_error(
                f"Failed to retrieve latest committee prints: {data.get('error', 'Unknown API error')}"
            )
            logger.error(f"API request failed: {data['error']}")
            return format_error_response(error)
        
        prints = data.get("committeePrints", [])
        if not prints:
            logger.info("No committee prints found")
            return "No committee prints found."
        
        # Process response with deduplication and sorting
        processed_prints = CommitteePrintsProcessor.deduplicate_committee_prints(prints)
        processed_prints = CommitteePrintsProcessor.sort_prints_by_update_date(processed_prints)
        
        logger.info(f"Found {len(processed_prints)} committee prints")
        lines = ["Latest Committee Prints:"]
        for print_item in processed_prints:
            lines.append("")
            lines.append(format_committee_print_item(print_item))
        
        return "\n".join(lines)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to retrieve latest committee prints: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)

@require_paid_access
@mcp.tool("get_committee_prints_by_congress")
async def get_committee_prints_by_congress(ctx: Context, congress: int) -> str:
    """
    Get committee prints for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    # Parameter validation
    congress_result = ParameterValidator.validate_congress_number(congress)
    if not congress_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "congress", congress, congress_result.error_message
        )
        logger.error(f"Parameter validation failed: {congress_result.error_message}")
        return format_error_response(error)
    
    limit = 20
    limit_result = ParameterValidator.validate_limit_range(limit)
    if not limit_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "limit", limit, limit_result.error_message
        )
        logger.error(f"Parameter validation failed: {limit_result.error_message}")
        return format_error_response(error)
    
    params = {
        "limit": limit,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee prints for Congress {congress} with reliability framework")
    try:
        data = await safe_committee_prints_request(f"/committee-print/{congress}", ctx, params)
        
        if "error" in data:
            error = CommonErrors.api_server_error(
                f"Failed to retrieve committee prints for Congress {congress}: {data.get('error', 'Unknown API error')}"
            )
            logger.error(f"API request failed: {data['error']}")
            return format_error_response(error)
        
        prints = data.get("committeePrints", [])
        if not prints:
            logger.info(f"No committee prints found for Congress {congress}")
            return f"No committee prints found for Congress {congress}."
        
        # Process response with deduplication and sorting
        processed_prints = CommitteePrintsProcessor.deduplicate_committee_prints(prints)
        processed_prints = CommitteePrintsProcessor.sort_prints_by_update_date(processed_prints)
        
        logger.info(f"Found {len(processed_prints)} committee prints for Congress {congress}")
        lines = [f"Committee Prints for Congress {congress}:"]
        for print_item in processed_prints:
            lines.append("")
            lines.append(format_committee_print_item(print_item))
        
        return "\n".join(lines)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to retrieve committee prints for Congress {congress}: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)

@require_paid_access
@mcp.tool("get_committee_prints_by_congress_and_chamber")
async def get_committee_prints_by_congress_and_chamber(ctx: Context, congress: int, chamber: str) -> str:
    """
    Get committee prints for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
    """
    # Parameter validation
    congress_result = ParameterValidator.validate_congress_number(congress)
    if not congress_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "congress", congress, congress_result.error_message
        )
        logger.error(f"Parameter validation failed: {congress_result.error_message}")
        return format_error_response(error)
    
    chamber_result = ParameterValidator.validate_chamber(chamber)
    if not chamber_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "chamber", chamber, chamber_result.error_message
        )
        logger.error(f"Parameter validation failed: {chamber_result.error_message}")
        return format_error_response(error)
    
    limit = 20
    limit_result = ParameterValidator.validate_limit_range(limit)
    if not limit_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "limit", limit, limit_result.error_message
        )
        logger.error(f"Parameter validation failed: {limit_result.error_message}")
        return format_error_response(error)
    
    params = {
        "limit": limit,
        "sort": "updateDate+desc",
        "format": "json"
    }
    
    logger.debug(f"Fetching committee prints for Congress {congress}, chamber {chamber} with reliability framework")
    try:
        data = await safe_committee_prints_request(f"/committee-print/{congress}/{chamber}", ctx, params)
        
        if "error" in data:
            error = CommonErrors.api_server_error(
                f"Failed to retrieve committee prints for Congress {congress}, {chamber}: {data.get('error', 'Unknown API error')}"
            )
            logger.error(f"API request failed: {data['error']}")
            return format_error_response(error)
        
        prints = data.get("committeePrints", [])
        if not prints:
            logger.info(f"No committee prints found for Congress {congress}, chamber {chamber}")
            return f"No committee prints found for Congress {congress}, chamber {chamber}."
        
        # Process response with deduplication and sorting
        processed_prints = CommitteePrintsProcessor.deduplicate_committee_prints(prints)
        processed_prints = CommitteePrintsProcessor.sort_prints_by_update_date(processed_prints)
        
        logger.info(f"Found {len(processed_prints)} committee prints for Congress {congress}, chamber {chamber}")
        lines = [f"Committee Prints for Congress {congress}, Chamber {chamber.title()}:"]
        for print_item in processed_prints:
            lines.append("")
            lines.append(format_committee_print_item(print_item))
        
        return "\n".join(lines)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to retrieve committee prints for Congress {congress}, {chamber}: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)

@require_paid_access
@mcp.tool("get_committee_print_details")
async def get_committee_print_details(ctx: Context, congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get detailed information about a specific committee print.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        jacket_number: The jacket number for the committee print.
    """
    # Parameter validation
    congress_result = ParameterValidator.validate_congress_number(congress)
    if not congress_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "congress", congress, congress_result.error_message
        )
        logger.error(f"Parameter validation failed: {congress_result.error_message}")
        return format_error_response(error)
    
    chamber_result = ParameterValidator.validate_chamber(chamber)
    if not chamber_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "chamber", chamber, chamber_result.error_message
        )
        logger.error(f"Parameter validation failed: {chamber_result.error_message}")
        return format_error_response(error)
    
    jacket_result = ParameterValidator.validate_jacket_number(jacket_number)
    if not jacket_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "jacket_number", jacket_number, jacket_result.error_message
        )
        logger.error(f"Parameter validation failed: {jacket_result.error_message}")
        return format_error_response(error)
    
    logger.debug(f"Fetching committee print details for Congress {congress}, chamber {chamber}, jacket {jacket_number} with reliability framework")
    try:
        data = await safe_committee_prints_request(f"/committee-print/{congress}/{chamber}/{jacket_number}", ctx)
        
        # Handle different response structures
        if isinstance(data, list):
            # If response is a list, check if it's empty or has error info
            if not data:
                error = CommonErrors.data_not_found(
                    "committee print",
                    identifier=f"Congress {congress}, chamber {chamber}, jacket number {jacket_number}"
                )
                logger.info(f"Committee print not found: Congress {congress}, chamber {chamber}, jacket {jacket_number}")
                return format_error_response(error)
            # If it's a list with one item, use that item
            print_item = data[0] if data else None
        else:
            # If response is a dict, check for error or committeePrint
            if "error" in data:
                error = CommonErrors.api_server_error(
                    f"Failed to retrieve committee print details: {data.get('error', 'Unknown API error')}"
                )
                logger.error(f"API request failed: {data['error']}")
                return format_error_response(error)
            
            print_item = data.get("committeePrint")
        
        if not print_item:
            error = CommonErrors.data_not_found(
                "committee print",
                identifier=f"Congress {congress}, chamber {chamber}, jacket number {jacket_number}"
            )
            logger.info(f"Committee print not found: Congress {congress}, chamber {chamber}, jacket {jacket_number}")
            return format_error_response(error)
        
        logger.debug(f"Committee print data type: {type(print_item)}")
        logger.debug(f"Committee print data: {print_item}")
        logger.info(f"Found committee print details for Congress {congress}, chamber {chamber}, jacket {jacket_number}")
        
        # Ensure print_item is a dictionary before passing to format function
        if isinstance(print_item, list):
            if len(print_item) > 0:
                print_item = print_item[0]
            else:
                error = CommonErrors.data_not_found(
                    "committee print",
                    identifier=f"Congress {congress}, chamber {chamber}, jacket number {jacket_number}"
                )
                logger.info(f"Empty committee print list: Congress {congress}, chamber {chamber}, jacket {jacket_number}")
                return format_error_response(error)
        
        return format_committee_print_detail(print_item)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to retrieve committee print details: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)

@require_paid_access
@mcp.tool("get_committee_print_text_versions")
async def get_committee_print_text_versions(ctx: Context, congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get text versions for a specific committee print.
    
    Args:
        congress: The Congress number (e.g., 117).
        chamber: The chamber name (e.g., "house", "senate").
        jacket_number: The jacket number for the committee print.
    """
    # Parameter validation
    congress_result = ParameterValidator.validate_congress_number(congress)
    if not congress_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "congress", congress, congress_result.error_message
        )
        logger.error(f"Parameter validation failed: {congress_result.error_message}")
        return format_error_response(error)
    
    chamber_result = ParameterValidator.validate_chamber(chamber)
    if not chamber_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "chamber", chamber, chamber_result.error_message
        )
        logger.error(f"Parameter validation failed: {chamber_result.error_message}")
        return format_error_response(error)
    
    jacket_result = ParameterValidator.validate_jacket_number(jacket_number)
    if not jacket_result.is_valid:
        error = CommonErrors.invalid_parameter(
            "jacket_number", jacket_number, jacket_result.error_message
        )
        logger.error(f"Parameter validation failed: {jacket_result.error_message}")
        return format_error_response(error)
    
    logger.debug(f"Fetching committee print text versions for Congress {congress}, chamber {chamber}, jacket {jacket_number} with reliability framework")
    try:
        data = await safe_committee_prints_request(f"/committee-print/{congress}/{chamber}/{jacket_number}/text", ctx)
        
        logger.debug(f"Text versions API response type: {type(data)}")
        logger.debug(f"Text versions API response: {data}")
        
        # Handle different response structures
        if isinstance(data, list):
            # If response is a list, it should contain text versions directly
            text_versions = data
        else:
            # If response is a dict, check for error or textVersions
            if "error" in data:
                error = CommonErrors.api_server_error(
                    f"Failed to retrieve committee print text versions: {data.get('error', 'Unknown API error')}"
                )
                logger.error(f"API request failed: {data['error']}")
                return format_error_response(error)
            
            text_versions = data.get("textVersions", [])
        
        logger.debug(f"Extracted text_versions: {text_versions}")
        
        if not text_versions:
            error = CommonErrors.data_not_found(
                "text versions",
                identifier=f"committee print Congress {congress}, chamber {chamber}, jacket number {jacket_number}"
            )
            logger.info(f"No text versions found for committee print: Congress {congress}, chamber {chamber}, jacket {jacket_number}")
            return format_error_response(error)
        
        logger.info(f"Found {len(text_versions)} text versions for committee print Congress {congress}, chamber {chamber}, jacket {jacket_number}")
        lines = [f"Text Versions for Committee Print {congress}/{chamber}/{jacket_number}:"]
        for version in text_versions:
            lines.append("")
            lines.append(format_committee_print_text_version(version))
        
        return "\n".join(lines)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to retrieve committee print text versions: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)

@require_paid_access
@mcp.tool()
async def search_committee_prints(
    ctx: Context,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None
) -> str:
    """
    Search for committee prints based on various criteria.
    
    Args:
        offset: The starting record for pagination (optional)
        limit: The number of records to return (max 250, optional)
        from_date_time: Start date for filtering by update date (YYYY-MM-DDT00:00:00Z, optional)
        to_date_time: End date for filtering by update date (YYYY-MM-DDT00:00:00Z, optional)
    """
    # Validate parameters
    if offset is not None:
        if not isinstance(offset, int) or offset < 0:
            error = CommonErrors.invalid_parameter(
                "offset", offset, "Offset must be a non-negative integer"
            )
            logger.error(f"Parameter validation failed: Invalid offset {offset}")
            return format_error_response(error)
    
    if limit is not None:
        limit_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
        if not limit_result.is_valid:
            error = CommonErrors.invalid_parameter(
                "limit", limit, limit_result.error_message
            )
            logger.error(f"Parameter validation failed: {limit_result.error_message}")
            return format_error_response(error)
    
    if from_date_time is not None:
        # Basic date format validation - should be ISO format like YYYY-MM-DDTHH:MM:SSZ
        if not isinstance(from_date_time, str) or len(from_date_time) < 10:
            error = CommonErrors.invalid_parameter(
                "from_date_time", from_date_time, "Date must be in ISO format (YYYY-MM-DDTHH:MM:SSZ)"
            )
            logger.error(f"Parameter validation failed: Invalid from_date_time format")
            return format_error_response(error)
    
    if to_date_time is not None:
        # Basic date format validation - should be ISO format like YYYY-MM-DDTHH:MM:SSZ
        if not isinstance(to_date_time, str) or len(to_date_time) < 10:
            error = CommonErrors.invalid_parameter(
                "to_date_time", to_date_time, "Date must be in ISO format (YYYY-MM-DDTHH:MM:SSZ)"
            )
            logger.error(f"Parameter validation failed: Invalid to_date_time format")
            return format_error_response(error)
    
    # Build parameters
    params = {
        "format": "json"
    }
    
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    if from_date_time is not None:
        params["fromDateTime"] = from_date_time
    if to_date_time is not None:
        params["toDateTime"] = to_date_time
    
    logger.debug(f"Searching committee prints with reliability framework: offset={offset}, limit={limit}, from_date={from_date_time}, to_date={to_date_time}")
    try:
        data = await safe_committee_prints_request("/committee-print", ctx, params)
        
        if "error" in data:
            error = CommonErrors.api_server_error(
                f"Failed to search committee prints: {data.get('error', 'Unknown API error')}"
            )
            logger.error(f"API request failed: {data['error']}")
            return format_error_response(error)
        
        prints = data.get("committeePrints", [])
        if not prints:
            logger.info("No committee prints found for search criteria")
            return "No committee prints found for the specified criteria."
        
        # Process response with deduplication and sorting
        processed_prints = CommitteePrintsProcessor.deduplicate_committee_prints(prints)
        processed_prints = CommitteePrintsProcessor.sort_prints_by_update_date(processed_prints)
        
        # Apply limit to processed results
        if limit and len(processed_prints) > limit:
            processed_prints = processed_prints[:limit]
        
        logger.info(f"Found {len(processed_prints)} committee prints matching search criteria")
        lines = ["Committee Prints Search Results:"]
        for print_item in processed_prints:
            lines.append("")
            lines.append(format_committee_print_item(print_item))
        
        return "\n".join(lines)
        
    except Exception as e:
        error = CommonErrors.api_server_error(
            f"Failed to search committee prints: {str(e)}"
        )
        logger.error(f"API request failed: {str(e)}")
        return format_error_response(error)
