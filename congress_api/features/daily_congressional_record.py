# congress_api/features/daily_congressional_record.py
import logging
from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.validators import ParameterValidator
from ..core.api_wrapper import DefensiveAPIWrapper
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import ResponseProcessor
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Defensive API Wrapper ---

async def safe_daily_congressional_record_request(endpoint: str, params: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """
    Safe API request wrapper for Daily Congressional Record with timeout and retry logic.
    
    Args:
        endpoint: API endpoint to call
        params: Parameters for the API request
        ctx: FastMCP context
        
    Returns:
        API response data
        
    Raises:
        Exception: If API request fails after retries
    """
    return await DefensiveAPIWrapper.safe_api_request(
        endpoint=endpoint,
        ctx=ctx,
        params=params or {},
        endpoint_type="daily-congressional-record"
    )

# --- Formatting Helpers ---

def format_daily_record_item(item: Dict[str, Any]) -> str:
    """Formats a single daily congressional record item for display in a list."""
    lines = [
        f"Congress: {item.get('congress', 'N/A')}",
        f"Volume: {item.get('volumeNumber', 'N/A')}",
        f"Issue: {item.get('issueNumber', 'N/A')}",
        f"Session: {item.get('sessionNumber', 'N/A')}",
        f"Issue Date: {item.get('issueDate', 'N/A')}",
        f"Update Date: {item.get('updateDate', 'N/A')}"
    ]
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_daily_record_detail(record_data: Dict[str, Any]) -> str:
    """Formats detailed information for a daily congressional record issue."""
    if not record_data:
        return "No daily congressional record data available."
    
    # Extract volume and issue numbers from the response
    volume_number = record_data.get('volumeNumber', 'N/A')
    issue_number = record_data.get('issueNumber', 'N/A')
    
    # Basic information
    lines = [
        f"Daily Congressional Record - Volume {volume_number}, Issue {issue_number}",
        f"Congress: {record_data.get('congress', 'N/A')}",
        f"Issue Date: {record_data.get('issueDate', 'N/A')}",
        f"Session: {record_data.get('sessionNumber', 'N/A')}",
        f"Update Date: {record_data.get('updateDate', 'N/A')}"
    ]
    
    # Check if 'issue' key exists in the response
    if 'issue' in record_data and record_data['issue']:
        issue = record_data['issue'][0]  # Get the first issue
        
        # Add issue-specific details
        lines.extend([
            f"Full Issue Date: {issue.get('fullIssueDate', 'N/A')}",
            f"PDF URL: {issue.get('pdfUrl', 'N/A')}",
            f"ZIP URL: {issue.get('zipUrl', 'N/A')}"
        ])
        
        # Add links if available
        if 'links' in issue and issue['links']:
            lines.append("\nAvailable Links:")
            for link in issue['links']:
                name = link.get('name', 'Unknown')
                url = link.get('url', 'N/A')
                lines.append(f"  - {name}: {url}")
    
    # Add articles count if available
    if 'articles' in record_data and record_data['articles']:
        article_count = len(record_data['articles'])
        lines.append(f"\nArticles Available: {article_count}")
    
    return "\n".join(lines)

def format_daily_record_articles(articles_data: Dict[str, Any]) -> str:
    """Formats articles from a daily congressional record issue."""
    if not articles_data or 'articles' not in articles_data:
        return "No articles available for this daily congressional record issue."
    
    articles = articles_data['articles']
    if not articles:
        return "No articles found for this daily congressional record issue."
    
    lines = [f"Daily Congressional Record Articles ({len(articles)} found):\n"]
    
    for i, article in enumerate(articles, 1):
        lines.extend([
            f"{i}. {article.get('title', 'Untitled Article')}",
            f"   Type: {article.get('articleType', 'N/A')}",
            f"   Chamber: {article.get('chamber', 'N/A')}",
            f"   URL: {article.get('url', 'N/A')}",
            ""
        ])
    
    return "\n".join(lines)

# =============================================================================
# MCP RESOURCES (Static/Reference Data Only - No User Parameters)
# =============================================================================

# @require_paid_access
@mcp.resource("congress://daily-congressional-record/latest")
async def get_latest_daily_congressional_record(ctx: Context) -> str:
    """
    Get the most recent daily congressional record issues.
    Returns the 10 most recently published issues by default.
    """
    try:
        logger.debug("Retrieving latest daily congressional record issues")
        
        # Make API request with defensive wrapper
        data = await safe_daily_congressional_record_request(
            endpoint="/daily-congressional-record",
            params={"limit": 10},
            ctx=ctx
        )
        
        # Check for error response from API
        if isinstance(data, dict) and 'error' in data:
            error_msg = data.get('error', 'Unknown API error')
            status_code = data.get('status_code', 'Unknown')
            logger.warning(f"API returned error for /daily-congressional-record: {error_msg} (status: {status_code})")
            
            # Handle specific error cases
            if status_code == 404 or 'not found' in error_msg.lower():
                error_response = CommonErrors.data_not_found(
                    "Daily Congressional Record Issues",
                    search_criteria={"search_type": "latest"}
                )
                return format_error_response(error_response)
            else:
                # General API error
                error_response = CommonErrors.general_error(f"API error: {error_msg}")
                return format_error_response(error_response)
        
        # Process and deduplicate results
        if 'dailyCongressionalRecord' in data and data['dailyCongressionalRecord']:
            deduplicated_records = ResponseProcessor.deduplicate_results(
                data['dailyCongressionalRecord'],
                key_fields=['volumeNumber', 'issueNumber']
            )
            data['dailyCongressionalRecord'] = deduplicated_records
            logger.debug(f"Retrieved {len(deduplicated_records)} latest daily congressional record issues")
            
            # Format the results
            formatted_items = []
            for item in deduplicated_records:
                formatted_items.append(format_daily_record_item(item))
            
            return "\n\n".join(formatted_items)
        else:
            logger.warning("No daily congressional record issues found in API response")
            error_response = CommonErrors.data_not_found(
                "Daily Congressional Record Issues",
                search_criteria={"search_type": "latest"}
            )
            return format_error_response(error_response)
            
    except Exception as e:
        logger.error(f"Error retrieving latest daily congressional record issues: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: '{str(e)}'")
        logger.error(f"Exception bool: {bool(e)}")
        error_response = CommonErrors.general_error(
            f"Error retrieving latest daily congressional record issues: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)

# =============================================================================
# MCP TOOLS (Interactive/Parameterized Functions)
# =============================================================================

# @require_paid_access
async def search_daily_congressional_record(
    ctx: Context,
    volume_number: Optional[str] = None,
    issue_number: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for daily congressional record issues based on various criteria.
    Can also retrieve specific issues, volumes, or articles with detailed information.
    
    Args:
        volume_number: Optional volume number to filter by (e.g., "169").
        issue_number: Optional issue number to filter by (e.g., "118"). Requires volume_number.
        limit: Maximum number of results to return (default: 10, max: 250).
    """
    try:
        logger.debug(f"Searching daily congressional record with volume={volume_number}, issue={issue_number}, limit={limit}")
        
        # Parameter validation
        validation_errors = []
        
        # Validate limit
        limit_result = ParameterValidator.validate_limit_range(limit, max_limit=250)
        if not limit_result.is_valid:
            validation_errors.append(limit_result.error_message)
        else:
            if limit_result.sanitized_value != limit:
                logger.debug(f"Auto-corrected limit from {limit} to {limit_result.sanitized_value}")
            limit = limit_result.sanitized_value
        
        # Validate volume number format if provided
        if volume_number is not None:
            if not isinstance(volume_number, str) or not volume_number.strip():
                validation_errors.append("volume_number must be a non-empty string")
            else:
                volume_number = volume_number.strip()
        
        # Validate issue number format if provided
        if issue_number is not None:
            if volume_number is None:
                validation_errors.append("issue_number requires volume_number to be specified")
            elif not isinstance(issue_number, str) or not issue_number.strip():
                validation_errors.append("issue_number must be a non-empty string")
            else:
                issue_number = issue_number.strip()
        
        # Return validation errors if any
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            logger.warning(f"Parameter validation failed: {error_msg}")
            error_response = CommonErrors.invalid_parameter(
                "search_parameters", 
                {"volume_number": volume_number, "issue_number": issue_number, "limit": limit},
                error_msg
            )
            return format_error_response(error_response)
        
        # Build endpoint and parameters based on search criteria
        if volume_number and issue_number:
            # Specific issue detail request
            endpoint = f"/daily-congressional-record/{volume_number}/{issue_number}"
            params = {}
            search_type = "issue_detail"
        elif volume_number:
            # Volume-specific search - use the correct API endpoint
            endpoint = f"/daily-congressional-record/{volume_number}"
            params = {"limit": limit}
            search_type = "volume_search"
        else:
            # General search
            endpoint = "/daily-congressional-record"
            params = {"limit": limit}
            search_type = "general_search"
        
        # Make API request with defensive wrapper
        data = await safe_daily_congressional_record_request(
            endpoint=endpoint,
            params=params,
            ctx=ctx
        )
        
        # Check for error response from API
        if isinstance(data, dict) and 'error' in data:
            error_msg = data.get('error', 'Unknown API error')
            status_code = data.get('status_code', 'Unknown')
            logger.warning(f"API returned error for {endpoint}: {error_msg} (status: {status_code})")
            
            # Handle specific error cases
            if status_code == 404 or 'not found' in error_msg.lower():
                if search_type == "issue_detail":
                    error_response = CommonErrors.data_not_found(
                        "Daily Congressional Record Issue",
                        identifier=f"volume {volume_number}, issue {issue_number}"
                    )
                else:
                    search_desc = f"volume {volume_number}" if volume_number else "your search criteria"
                    error_response = CommonErrors.data_not_found(
                        "Daily Congressional Record Issues",
                        search_criteria={"volume_number": volume_number} if volume_number else {}
                    )
                return format_error_response(error_response)
            else:
                # General API error
                error_response = CommonErrors.general_error(f"API error: {error_msg}")
                return format_error_response(error_response)
        
        # Add debug logging for issue detail requests
        if search_type == "issue_detail":
            logger.debug(f"API Response for {endpoint}: {data}")
            logger.debug(f"Response type: {type(data)}")
            if isinstance(data, dict):
                logger.debug(f"Response keys: {list(data.keys())}")
                logger.debug(f"Full response content: {data}")
            else:
                logger.debug(f"Response content: {data}")
        
        # Process results based on search type
        if search_type == "issue_detail":
            # Return detailed issue information
            # Check for valid response structure instead of just truthiness
            if data and isinstance(data, dict) and ('issue' in data or 'issueDate' in data):
                logger.debug(f"Retrieved detailed information for volume {volume_number}, issue {issue_number}")
                return format_daily_record_detail(data)
            else:
                logger.warning(f"No data found for volume {volume_number}, issue {issue_number}")
                error_response = CommonErrors.data_not_found(
                    "Daily Congressional Record Issue",
                    identifier=f"volume {volume_number}, issue {issue_number}"
                )
                return format_error_response(error_response)
        
        elif search_type in ["volume_search", "general_search"]:
            # Process list results
            if 'dailyCongressionalRecord' in data and data['dailyCongressionalRecord']:
                records = data['dailyCongressionalRecord']
                
                # Apply response deduplication
                deduplicated_records = ResponseProcessor.deduplicate_results(
                    records,
                    key_fields=['volumeNumber', 'issueNumber']
                )
                
                if deduplicated_records:
                    logger.debug(f"Found {len(deduplicated_records)} matching daily congressional record issues")
                    
                    # Format results
                    formatted_items = []
                    for item in deduplicated_records:
                        formatted_items.append(format_daily_record_item(item))
                    
                    search_desc = f"volume {volume_number}" if volume_number else "your search criteria"
                    result_header = f"Daily Congressional Record Issues matching {search_desc}:\n\n"
                    return result_header + "\n\n".join(formatted_items)
                else:
                    search_desc = f"volume {volume_number}" if volume_number else "your search criteria"
                    logger.warning(f"No daily congressional record issues found matching {search_desc}")
                    search_criteria = {"volume_number": volume_number} if volume_number else {}
                    error_response = CommonErrors.data_not_found(
                        "Daily Congressional Record Issues",
                        search_criteria=search_criteria
                    )
                    return format_error_response(error_response)
            else:
                logger.warning("No daily congressional record issues found in API response")
                error_response = CommonErrors.data_not_found(
                    "Daily Congressional Record Issues",
                    search_criteria={"search_type": search_type}
                )
                return format_error_response(error_response)
        
    except Exception as e:
        logger.error(f"Error searching daily congressional record: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception repr: {repr(e)}")
        logger.error(f"Exception args: {e.args}")
        logger.error(f"Exception str: '{str(e)}'")
        logger.error(f"Exception bool: {bool(e)}")
        error_response = CommonErrors.general_error(
            f"Error searching daily congressional record: {str(e) if str(e) else 'Unknown error occurred'}"
        )
        return format_error_response(error_response)
