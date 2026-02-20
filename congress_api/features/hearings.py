# congress_api/features/hearings.py
import logging
from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_hearing_item(hearing_item: Dict[str, Any]) -> str:
    """Formats a single hearing item for display in a list."""
    lines = [
        f"Chamber: {hearing_item.get('chamber', 'N/A')}",
        f"Congress: {hearing_item.get('congress', 'N/A')}",
        f"Jacket Number: {hearing_item.get('jacketNumber', 'N/A')}",
        f"Update Date: {hearing_item.get('updateDate', 'N/A')}",
        f"URL: {hearing_item.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_hearing_detail(hearing_item: Dict[str, Any]) -> str:
    """Formats detailed information for a single hearing."""
    lines = [
        f"Title: {hearing_item.get('title', 'N/A')}",
        f"Chamber: {hearing_item.get('chamber', 'N/A')}",
        f"Congress: {hearing_item.get('congress', 'N/A')}",
        f"Citation: {hearing_item.get('citation', 'N/A')}",
        f"Jacket Number: {hearing_item.get('jacketNumber', 'N/A')}",
        f"Library of Congress Identifier: {hearing_item.get('libraryOfCongressIdentifier', 'N/A')}",
        f"Update Date: {hearing_item.get('updateDate', 'N/A')}"
    ]
    
    # Add dates if available
    if 'dates' in hearing_item and hearing_item['dates']:
        dates = [date.get('date', 'N/A') for date in hearing_item['dates']]
        lines.append(f"Dates: {', '.join(dates)}")
    
    # Add associated meeting if available
    if 'associatedMeeting' in hearing_item and hearing_item['associatedMeeting']:
        meeting = hearing_item['associatedMeeting']
        lines.append(f"Associated Meeting: Event ID {meeting.get('eventId', 'N/A')}")
        lines.append(f"  URL: {meeting.get('url', 'N/A')}")
    
    # Add committees if available
    if 'committees' in hearing_item and hearing_item['committees']:
        lines.append("\nCommittees:")
        for committee in hearing_item['committees']:
            lines.append(f"  - {committee.get('name', 'N/A')} (System Code: {committee.get('systemCode', 'N/A')})")
            lines.append(f"    URL: {committee.get('url', 'N/A')}")
    
    # Add formats if available
    if 'formats' in hearing_item and hearing_item['formats']:
        lines.append("\nFormats:")
        for format_item in hearing_item['formats']:
            lines.append(f"  - {format_item.get('type', 'N/A')}")
            lines.append(f"    URL: {format_item.get('url', 'N/A')}")
        
    return "\n".join(lines)

# --- Defensive API Wrapper ---

async def safe_hearings_request(endpoint: str, params: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """
    Safe API request wrapper for hearings endpoints with retry logic and error handling.
    
    Args:
        endpoint: API endpoint to call
        params: Parameters for the API request
        ctx: Context for the API request
        
    Returns:
        API response data or error dictionary
    """
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint=endpoint,
        params=params,
        ctx=ctx,
        endpoint_type="hearings"
    )

# --- Helper Functions ---

async def get_latest_hearings(ctx: Context) -> str:
    """
    Get a list of the most recent hearings.
    Returns the 10 most recently updated hearings by default.
    """
    try:
        params = {
            "limit": 10,
            "sort": "updateDate+desc",
            "format": "json"
        }
        
        logger.debug("Fetching latest hearings")
        data = await safe_hearings_request("/hearing", params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error retrieving latest hearings: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to retrieve latest hearings: {data['error']}"
            )
            return format_error_response(error_response)
        
        hearings = data.get("hearings", [])
        if not hearings:
            logger.info("No hearings found")
            return "No hearings found."
        
        # Deduplicate and clean results
        deduplicated_hearings = HearingsProcessor.deduplicate_hearings(hearings)
        logger.info(f"Found {len(hearings)} hearings ({len(hearings) - len(deduplicated_hearings)} duplicates removed)")
        
        lines = ["Latest Hearings:"]
        for hearing_item in deduplicated_hearings:
            lines.append("")
            lines.append(format_hearing_item(HearingsProcessor.clean_hearing_response(hearing_item)))
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error retrieving latest hearings: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error retrieving latest hearings: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# --- Response Processing ---

class HearingsProcessor:
    """Processor for hearings API responses with deduplication and formatting."""
    
    @staticmethod
    def deduplicate_hearings(hearings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate hearings based on congress, chamber, and jacketNumber."""
        return ResponseProcessor.deduplicate_results(
            results=hearings,
            key_fields=['congress', 'chamber', 'jacketNumber']
        )
    
    @staticmethod
    def clean_hearing_response(hearing: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and standardize a single hearing response."""
        # Ensure required fields exist
        if 'congress' not in hearing:
            hearing['congress'] = 'Unknown'
        if 'chamber' not in hearing:
            hearing['chamber'] = 'Unknown'
        if 'jacketNumber' not in hearing:
            hearing['jacketNumber'] = 'Unknown'
            
        return hearing

# --- MCP Resources ---

# @require_paid_access
@mcp.resource("congress://hearings/latest")
async def latest_hearings_resource(ctx: Context) -> str:
    """Static resource providing the latest hearings."""
    return await get_latest_hearings(ctx)

# --- MCP Tools ---

# @require_paid_access
async def get_hearings_by_congress(ctx: Context, congress: int) -> str:
    """
    Get hearings for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 116).
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            error_response = CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            )
            return format_error_response(error_response)
        
        # Use sanitized value
        congress = congress_validation.sanitized_value
        
        params = {
            "limit": 20,
            "sort": "updateDate+desc",
            "format": "json"
        }
        
        logger.debug(f"Fetching hearings for Congress {congress}")
        data = await safe_hearings_request(f"/hearing/{congress}", params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error retrieving hearings for Congress {congress}: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to retrieve hearings for Congress {congress}: {data['error']}"
            )
            return format_error_response(error_response)
        
        hearings = data.get("hearings", [])
        if not hearings:
            logger.info(f"No hearings found for Congress {congress}")
            return f"No hearings found for Congress {congress}."
        
        # Deduplicate and clean results
        deduplicated_hearings = HearingsProcessor.deduplicate_hearings(hearings)
        logger.info(f"Found {len(hearings)} hearings for Congress {congress} ({len(hearings) - len(deduplicated_hearings)} duplicates removed)")
        
        lines = [f"Hearings for Congress {congress}:"]
        for hearing_item in deduplicated_hearings:
            lines.append("")
            lines.append(format_hearing_item(HearingsProcessor.clean_hearing_response(hearing_item)))
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error retrieving hearings for Congress {congress}: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error retrieving hearings for Congress {congress}: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def get_hearings_by_congress_and_chamber(ctx: Context, congress: int, chamber: str) -> str:
    """
    Get hearings for a specific Congress and chamber.
    
    Args:
        congress: The Congress number (e.g., 116).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            error_response = CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            )
            return format_error_response(error_response)
        
        # Validate chamber parameter
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            error_response = CommonErrors.invalid_parameter(
                "chamber", chamber, chamber_validation.error_message
            )
            return format_error_response(error_response)
        
        # Use sanitized values
        congress = congress_validation.sanitized_value
        chamber = chamber_validation.sanitized_value
        
        params = {
            "limit": 20,
            "sort": "updateDate+desc",
            "format": "json"
        }
        
        logger.debug(f"Fetching hearings for Congress {congress}, Chamber {chamber}")
        data = await safe_hearings_request(f"/hearing/{congress}/{chamber}", params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error retrieving hearings for Congress {congress}, Chamber {chamber}: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to retrieve hearings for Congress {congress}, Chamber {chamber}: {data['error']}"
            )
            return format_error_response(error_response)
        
        hearings = data.get("hearings", [])
        if not hearings:
            logger.info(f"No hearings found for Congress {congress}, Chamber {chamber}")
            return f"No hearings found for Congress {congress}, Chamber {chamber}."
        
        # Deduplicate and clean results
        deduplicated_hearings = HearingsProcessor.deduplicate_hearings(hearings)
        logger.info(f"Found {len(hearings)} hearings for Congress {congress}, Chamber {chamber} ({len(hearings) - len(deduplicated_hearings)} duplicates removed)")
        
        lines = [f"Hearings for Congress {congress}, Chamber {chamber}:"]
        for hearing_item in deduplicated_hearings:
            lines.append("")
            lines.append(format_hearing_item(HearingsProcessor.clean_hearing_response(hearing_item)))
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error retrieving hearings for Congress {congress}, Chamber {chamber}: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error retrieving hearings for Congress {congress}, Chamber {chamber}: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def get_hearing_details(ctx: Context, congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get detailed information for a specific hearing.
    
    Args:
        congress: The Congress number (e.g., 116).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
        jacket_number: The jacket number for the hearing.
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            error_response = CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            )
            return format_error_response(error_response)
        
        # Validate chamber parameter
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            error_response = CommonErrors.invalid_parameter(
                "chamber", chamber, chamber_validation.error_message
            )
            return format_error_response(error_response)
        
        # Validate jacket number parameter
        jacket_number_validation = ParameterValidator.validate_jacket_number(jacket_number)
        if not jacket_number_validation.is_valid:
            logger.warning(f"Invalid jacket number: {jacket_number}")
            error_response = CommonErrors.invalid_parameter(
                "jacket_number", jacket_number, jacket_number_validation.error_message
            )
            return format_error_response(error_response)
        
        # Use sanitized values
        congress = congress_validation.sanitized_value
        chamber = chamber_validation.sanitized_value
        jacket_number = jacket_number_validation.sanitized_value
        
        params = {
            "format": "json"
        }
        
        logger.debug(f"Fetching details for hearing {congress}/{chamber}/{jacket_number}")
        data = await safe_hearings_request(f"/hearing/{congress}/{chamber}/{jacket_number}", params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error retrieving hearing details: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to retrieve hearing details: {data['error']}"
            )
            return format_error_response(error_response)
        
        if "hearing" not in data:
            logger.warning(f"No hearing field in response for {congress}/{chamber}/{jacket_number}")
            return f"No hearing found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
        
        hearing_data = data.get("hearing", {})
        if not hearing_data:
            logger.warning(f"Empty hearing data for {congress}/{chamber}/{jacket_number}")
            return f"No hearing data found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
        
        logger.info(f"Successfully retrieved hearing details for {congress}/{chamber}/{jacket_number}")
        return format_hearing_detail(HearingsProcessor.clean_hearing_response(hearing_data))
        
    except Exception as e:
        logger.error(f"Error retrieving hearing details for {congress}/{chamber}/{jacket_number}: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error retrieving hearing details for {congress}/{chamber}/{jacket_number}: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def get_hearing_content(ctx: Context, congress: int, chamber: str, jacket_number: int) -> str:
    """
    Get the actual content/text of a specific hearing.
    
    Args:
        congress: The Congress number (e.g., 116).
        chamber: The chamber name (e.g., "house", "senate", "nochamber").
        jacket_number: The jacket number for the hearing.
    """
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            logger.warning(f"Invalid congress number: {congress}")
            error_response = CommonErrors.invalid_parameter(
                "congress", congress, congress_validation.error_message
            )
            return format_error_response(error_response)
        
        # Validate chamber parameter
        chamber_validation = ParameterValidator.validate_chamber(chamber)
        if not chamber_validation.is_valid:
            logger.warning(f"Invalid chamber: {chamber}")
            error_response = CommonErrors.invalid_parameter(
                "chamber", chamber, chamber_validation.error_message
            )
            return format_error_response(error_response)
        
        # Validate jacket number parameter
        jacket_number_validation = ParameterValidator.validate_jacket_number(jacket_number)
        if not jacket_number_validation.is_valid:
            logger.warning(f"Invalid jacket number: {jacket_number}")
            error_response = CommonErrors.invalid_parameter(
                "jacket_number", jacket_number, jacket_number_validation.error_message
            )
            return format_error_response(error_response)
        
        # Use sanitized values
        congress = congress_validation.sanitized_value
        chamber = chamber_validation.sanitized_value
        jacket_number = jacket_number_validation.sanitized_value
        
        # First get the hearing details to find the content URL
        params = {
            "format": "json"
        }
        
        logger.debug(f"Fetching hearing details for content URL: {congress}/{chamber}/{jacket_number}")
        data = await safe_hearings_request(f"/hearing/{congress}/{chamber}/{jacket_number}", params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error retrieving hearing details: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to retrieve hearing details: {data['error']}"
            )
            return format_error_response(error_response)
        
        if "hearing" not in data:
            logger.warning(f"No hearing field in response for {congress}/{chamber}/{jacket_number}")
            return f"No hearing found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
        
        hearing_data = data.get("hearing", {})
        if not hearing_data:
            logger.warning(f"Empty hearing data for {congress}/{chamber}/{jacket_number}")
            return f"No hearing data found for Congress {congress}, Chamber {chamber}, Jacket Number {jacket_number}."
        
        # Look for the formatted text URL in the formats
        formats = hearing_data.get("formats", [])
        content_url = None
        
        for format_item in formats:
            if format_item.get("type") == "Formatted Text":
                content_url = format_item.get("url")
                break
        
        if not content_url:
            logger.warning(f"No formatted text URL found for hearing {congress}/{chamber}/{jacket_number}")
            return f"No content URL available for hearing {congress}/{chamber}/{jacket_number}. Available formats: {[f.get('type') for f in formats]}"
        
        # Fetch the actual content from the URL
        logger.debug(f"Fetching hearing content from URL: {content_url}")
        
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(content_url)
                if response.status_code == 200:
                    content = response.text
                    
                    # Extract the main content from HTML (basic text extraction)
                    import re
                    from html import unescape
                    
                    # Remove script and style elements
                    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
                    
                    # Remove HTML tags but keep the text
                    content = re.sub(r'<[^>]+>', '', content)
                    
                    # Clean up whitespace and decode HTML entities
                    content = unescape(content)
                    content = re.sub(r'\n\s*\n', '\n\n', content)  # Normalize line breaks
                    content = content.strip()
                    
                    if content:
                        # Truncate if too long (keep first 8000 characters)
                        if len(content) > 8000:
                            content = content[:8000] + "\n\n[Content truncated - full content available at: " + content_url + "]"
                        
                        logger.info(f"Successfully retrieved hearing content for {congress}/{chamber}/{jacket_number}")
                        return f"Hearing Content for Congress {congress}, Chamber {chamber.title()}, Jacket Number {jacket_number}:\n\n{content}"
                    else:
                        logger.warning(f"Empty content extracted from {content_url}")
                        return f"No readable content found at {content_url}"
                else:
                    logger.error(f"HTTP {response.status_code} error fetching content from {content_url}")
                    return f"Error fetching content: HTTP {response.status_code}. URL: {content_url}"
                        
        except Exception as fetch_error:
            logger.error(f"Error fetching content from {content_url}: {fetch_error}")
            return f"Error fetching hearing content from {content_url}: {str(fetch_error)}"
        
    except Exception as e:
        logger.error(f"Error retrieving hearing content for {congress}/{chamber}/{jacket_number}: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error retrieving hearing content for {congress}/{chamber}/{jacket_number}: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def search_hearings(
    ctx: Context,
    keywords: Optional[str] = None,
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    from_date_time: Optional[str] = None,
    to_date_time: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc"
) -> str:
    """
    Search for hearings based on various criteria.
    
    Args:
        keywords: Keywords to search for in hearing information.
        congress: Optional Congress number (e.g., 116).
        chamber: Optional chamber of Congress ("house", "senate", or "nochamber").
        from_date_time: Optional start date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        to_date_time: Optional end date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        limit: Maximum number of results to return (default: 10).
        sort: Sort order (default: "updateDate+desc").
    """
    try:
        # Validate limit parameter
        limit_validation = ParameterValidator.validate_limit_range(limit)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit: {limit}")
            error_response = CommonErrors.invalid_parameter(
                "limit", limit, limit_validation.error_message
            )
            return format_error_response(error_response)
        
        # Use sanitized values
        limit = limit_validation.sanitized_value
        
        params = {
            "format": "json",
            "limit": limit,
            "sort": sort
        }
        
        # Add optional parameters if provided
        if keywords:
            params["q"] = keywords
        if from_date_time:
            params["fromDateTime"] = from_date_time
        if to_date_time:
            params["toDateTime"] = to_date_time
        
        # Determine the endpoint based on provided parameters
        endpoint = "/hearing"
        if congress:
            endpoint = f"{endpoint}/{congress}"
            if chamber:
                endpoint = f"{endpoint}/{chamber}"
        
        logger.debug(f"Searching hearings with endpoint: {endpoint}, params: {params}")
        data = await safe_hearings_request(endpoint, params, ctx)
        
        if isinstance(data, dict) and 'error' in data:
            logger.error(f"Error searching hearings: {data['error']}")
            error_response = CommonErrors.api_server_error(
                f"Failed to search hearings: {data['error']}"
            )
            return format_error_response(error_response)
        
        hearings = data.get("hearings", [])
        if not hearings:
            logger.info("No hearings found matching the search criteria")
            return "No hearings found matching the search criteria."
        
        # Deduplicate and clean results
        deduplicated_hearings = HearingsProcessor.deduplicate_hearings(hearings)
        logger.info(f"Found {len(hearings)} hearings matching the search criteria ({len(hearings) - len(deduplicated_hearings)} duplicates removed)")
        
        lines = ["Search Results - Hearings:"]
        for hearing_item in deduplicated_hearings:
            lines.append("")
            lines.append(format_hearing_item(HearingsProcessor.clean_hearing_response(hearing_item)))
        
        return "\n".join(lines)
        
    except Exception as e:
        logger.error(f"Error searching hearings: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        error_response = CommonErrors.general_error(
            f"Error searching hearings: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)
