# congress_api/features/crs_reports.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

# --- MCP Resources ---

@mcp.resource("congress://crs-reports/latest")
async def get_latest_crs_reports(ctx: Context) -> str:
    """
    Get the most recent CRS reports.
    Returns the 10 most recently published reports by default.
    """
    context = mcp.get_context()
    logger.debug("Getting latest CRS reports")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': 10
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint="/crsreport",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving CRS reports: {data['error']}"
    
    # Format the response
    return format_crs_reports_list(data)

@mcp.resource("congress://crs-reports/{report_number}")
async def get_crs_report_detail(ctx: Context, report_number: str) -> str:
    """
    Get detailed information for a specific CRS report.
    
    Args:
        report_number: The report number or ID (e.g., "R47175").
    """
    context = mcp.get_context()
    logger.debug(f"Getting CRS report details for report number: {report_number}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json'
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint=f"/crsreport/{report_number}",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving CRS report details: {data['error']}"
    
    # Format the response
    return format_crs_report_detail(data)

# --- MCP Tools ---

@mcp.tool("search_crs_reports")
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
    context = mcp.get_context()
    logger.debug(f"Searching for CRS reports with keywords: {keywords}, report_number: {report_number}, limit: {limit}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': limit
    }
    
    # If a specific report number is provided, get that report directly
    if report_number:
        return await get_crs_report_detail(ctx, report_number)
    
    # Make the API request to get the latest reports (no specific search endpoint available)
    data = await make_api_request(
        endpoint="/crsreport",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error searching for CRS reports: {data['error']}"
    
    # If keywords are provided, filter the results client-side
    if keywords and 'CRSReports' in data and data['CRSReports']:
        filtered_reports = []
        keywords_lower = keywords.lower()
        
        for report in data['CRSReports']:
            # Check if keywords are in the title
            title = report.get('title', '').lower()
            if keywords_lower in title:
                filtered_reports.append(report)
                continue
        
        # Replace the original reports with the filtered ones
        if filtered_reports:
            data['CRSReports'] = filtered_reports
        else:
            return f"No CRS reports found matching keywords: {keywords}"
    
    # Format the response
    return format_crs_reports_list(data)
