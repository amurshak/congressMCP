# congress_api/features/crs_reports.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
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

async def safe_crs_reports_request(endpoint: str, params: Dict[str, Any], ctx: Context) -> Dict[str, Any]:
    """
    Safe API request wrapper for CRS Reports with timeout and retry logic.
    
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
        endpoint_type="crs-reports"
    )

# --- Formatting Helpers ---

def format_crs_report_item(item: Dict[str, Any]) -> str:
    """Formats a single CRS report item for display in a list."""
    lines = [
        f"ID: {item.get('id', 'N/A')}",
        f"Title: {item.get('title', 'N/A')}",
        f"Status: {item.get('status', 'N/A')}",
        f"Content Type: {item.get('contentType', 'N/A')}"
    ]
    
    # Add publish date if available
    if 'publishDate' in item:
        lines.append(f"Publish Date: {item.get('publishDate', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in item:
        lines.append(f"Update Date: {item.get('updateDate', 'N/A')}")
    
    # Add version if available
    if 'version' in item:
        lines.append(f"Version: {item.get('version', 'N/A')}")
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_crs_report_detail(report_data: Dict[str, Any]) -> str:
    """Formats detailed information for a CRS report."""
    if not report_data:
        return "No CRS report data available."
    
    # Check if the expected key is present
    if 'CRSReport' not in report_data:
        # Try to determine if this is a valid response in a different format
        if isinstance(report_data, dict) and len(report_data) > 0:
            # Log what keys we did receive
            logging.debug(f"Received keys in response: {list(report_data.keys())}")
            return f"Received CRS report data, but in an unexpected format. Keys: {list(report_data.keys())}"
        return "No CRS report data available."
    
    report = report_data['CRSReport']
    
    lines = [
        f"ID: {report.get('id', 'N/A')}",
        f"Title: {report.get('title', 'N/A')}",
        f"Status: {report.get('status', 'N/A')}",
        f"Content Type: {report.get('contentType', 'N/A')}",
        f"Publish Date: {report.get('publishDate', 'N/A')}",
        f"Update Date: {report.get('updateDate', 'N/A')}",
        f"Version: {report.get('version', 'N/A')}",
        f"URL: {report.get('url', 'N/A')}"
    ]
    
    # Add authors if available
    if 'authors' in report and report['authors']:
        authors = [author.get('author', 'Unknown') for author in report['authors']]
        lines.append(f"Authors: {', '.join(authors)}")
    
    # Add topics if available
    if 'topics' in report and report['topics']:
        topics = [topic.get('topic', 'Unknown') for topic in report['topics']]
        lines.append(f"Topics: {', '.join(topics)}")
    
    # Add formats if available
    if 'formats' in report and report['formats']:
        lines.append("\nAvailable Formats:")
        for fmt in report['formats']:
            lines.append(f"  - {fmt.get('format', 'Unknown')}: {fmt.get('url', 'N/A')}")
    
    # Add related materials if available
    if 'relatedMaterials' in report and report['relatedMaterials']:
        lines.append("\nRelated Materials:")
        for material in report['relatedMaterials']:
            material_type = material.get('type', 'Unknown')
            congress = material.get('congress', 'N/A')
            number = material.get('number', 'N/A')
            title = material.get('title', 'N/A')
            url = material.get('URL', 'N/A')
            
            material_info = f"  - {material_type} {congress}-{number}"
            if title and title != "null":
                material_info += f": {title}"
            material_info += f"\n    URL: {url}"
            lines.append(material_info)
    
    # Add summary if available
    if 'summary' in report and report['summary']:
        lines.append("\nSummary:")
        lines.append(report['summary'])
    
    return "\n".join(lines)

def format_crs_reports_list(data: Dict[str, Any]) -> str:
    """Formats a list of CRS reports."""
    if not data or 'CRSReports' not in data or not data['CRSReports']:
        return "No CRS reports available."
    
    reports = data['CRSReports']
    formatted_reports = []
    
    for report in reports:
        formatted_reports.append(format_crs_report_item(report))
    
    return "\n\n".join(formatted_reports)

# --- MCP Resources (Static/Reference Data Only) ---

# @require_paid_access
@mcp.resource("congress://crs-reports/latest")
async def get_latest_crs_reports(ctx: Context) -> str:
    """
    Get the most recent CRS reports.
    Returns the 10 most recently published reports by default.
    """
    try:
        logger.debug("Getting latest CRS reports")
        
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': 10
        }
        
        # Make the API request
        data = await safe_crs_reports_request(
            endpoint="/crsreport",
            params=params,
            ctx=ctx
        )
        
        # Check if there was an error in the response
        if isinstance(data, dict) and 'error' in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving CRS reports: {data['error']}"))
        
        # Apply response deduplication
        if 'CRSReports' in data and data['CRSReports']:
            deduplicated_reports = ResponseProcessor.deduplicate_results(
                data['CRSReports'], 
                key_fields=['id']
            )
            data['CRSReports'] = deduplicated_reports
            logger.debug(f"Retrieved {len(deduplicated_reports)} latest CRS reports")
        
        # Format the response
        return format_crs_reports_list(data)
        
    except Exception as e:
        logger.error(f"Exception in get_latest_crs_reports: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error retrieving latest CRS reports: {str(e)}"))

# --- MCP Tools (Interactive/Parameterized Functions) ---

# @require_paid_access
async def search_crs_reports(
    ctx: Context,
    keywords: Optional[str] = None,
    report_number: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for CRS reports based on keywords or report number.
    
    Args:
        keywords: Optional keywords to search for in report titles and content.
        report_number: Optional specific report number to search for.
        limit: Maximum number of results to return (default: 10).
    """
    try:
        logger.debug(f"Searching for CRS reports with keywords: {keywords}, report_number: {report_number}, limit: {limit}")
        
        # Parameter validation
        validator = ParameterValidator()
        
        # Validate limit parameter
        limit_validation = validator.validate_limit_range(limit, max_limit=250)
        if not limit_validation.is_valid:
            return format_error_response(CommonErrors.invalid_parameter("limit", limit_validation.error_message))
        
        # Use sanitized limit value (auto-corrected if needed)
        sanitized_limit = limit_validation.sanitized_value
        if sanitized_limit != limit:
            logger.info(f"Limit auto-corrected from {limit} to {sanitized_limit}")
        
        # Validate report number if provided
        if report_number:
            if not report_number.strip():
                return format_error_response(CommonErrors.invalid_parameter("report_number", "Report number cannot be empty"))
        
        # Option A: Report Number Search Priority
        if report_number:
            logger.debug(f"Searching for specific CRS report: {report_number}")
            
            # Set up parameters for the API request
            params = {
                'format': 'json'
            }
            
            # Make the API request
            data = await safe_crs_reports_request(
                endpoint=f"/crsreport/{report_number}",
                params=params,
                ctx=ctx
            )
            
            # Check if there was an error in the response
            if isinstance(data, dict) and 'error' in data:
                return format_error_response(CommonErrors.data_not_found(f"CRS report '{report_number}' not found"))
            
            # Format the response
            return format_crs_report_detail(data)
        
        # If no keywords provided, guide user
        if not keywords:
            return format_error_response(CommonErrors.invalid_parameter("keywords", "Please provide either 'keywords' for searching recent reports or 'report_number' for a specific report (e.g., 'R47175')"))
        
        # Option B: Keyword Search - search larger batch of recent reports
        search_limit = min(250, max(sanitized_limit * 5, 50))  # Search more than requested to improve filtering
        params = {
            'format': 'json',
            'limit': search_limit
        }
        
        logger.debug(f"Searching CRS reports with keywords '{keywords}' (search_limit: {search_limit}, return_limit: {sanitized_limit})")
        
        # Make the API request to get recent reports
        data = await safe_crs_reports_request(
            endpoint="/crsreport",
            params=params,
            ctx=ctx
        )
        
        # Check if there was an error in the response
        if isinstance(data, dict) and 'error' in data:
            return format_error_response(CommonErrors.api_server_error(f"Error retrieving CRS reports: {data['error']}"))
        
        # Filter results by keywords and apply limit
        if 'CRSReports' in data and data['CRSReports']:
            filtered_reports = []
            keywords_lower = keywords.lower()
            
            for report in data['CRSReports']:
                title = report.get('title', '').lower()
                if keywords_lower in title:
                    filtered_reports.append(report)
                    if len(filtered_reports) >= sanitized_limit:
                        break
            
            if filtered_reports:
                # Apply response deduplication
                deduplicated_reports = ResponseProcessor.deduplicate_results(
                    filtered_reports, 
                    key_fields=['id']
                )
                
                logger.debug(f"Found {len(filtered_reports)} matching reports (after deduplication: {len(deduplicated_reports)})")
                
                # Format the filtered results
                formatted_reports = []
                for report in deduplicated_reports:
                    formatted_reports.append(format_crs_report_item(report))
                
                return f"Search Results - CRS Reports matching '{keywords}':\n\n" + "\n\n".join(formatted_reports)
            else:
                return format_error_response(CommonErrors.data_not_found(f"No CRS reports found matching keywords: '{keywords}'"))
        else:
            return format_error_response(CommonErrors.data_not_found("No CRS reports available"))
            
    except Exception as e:
        logger.error(f"Exception in search_crs_reports: {str(e)}")
        return format_error_response(CommonErrors.general_error(f"Error searching CRS reports: {str(e)}"))
