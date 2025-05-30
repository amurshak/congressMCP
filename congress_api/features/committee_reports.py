# congress_api/features/committee_reports.py
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# --- Formatting Helpers ---

def format_committee_report_item(report: Dict[str, Any]) -> str:
    """Formats a single committee report item for display in a list."""
    lines = [
        f"Citation: {report.get('citation', 'N/A')}",
        f"  Congress: {report.get('congress', 'N/A')}",
        f"  Chamber: {report.get('chamber', 'N/A')}",
        f"  Type: {report.get('type', 'N/A')}",
        f"  Number: {report.get('number', 'N/A')}",
        f"  Part: {report.get('part', 'N/A')}",
        f"  Update Date: {report.get('updateDate', 'N/A')}",
        f"  URL: {report.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_committee_report_detail(report: Dict[str, Any]) -> str:
    """Formats detailed information for a single committee report."""
    lines = [
        f"Title: {report.get('title', 'N/A')}",
        f"Citation: {report.get('citation', 'N/A')}",
        f"  Congress: {report.get('congress', 'N/A')}",
        f"  Chamber: {report.get('chamber', 'N/A')}",
        f"  Report Type: {report.get('reportType', 'N/A')} ({report.get('type', 'N/A')})",
        f"  Number: {report.get('number', 'N/A')}",
        f"  Part: {report.get('part', 'N/A')}",
        f"  Issue Date: {report.get('issueDate', 'N/A')}",
        f"  Update Date: {report.get('updateDate', 'N/A')}",
        f"  Is Conference Report: {'Yes' if report.get('isConferenceReport') else 'No'}",
        f"  Session Number: {report.get('sessionNumber', 'N/A')}",
    ]
    if 'associatedBill' in report and report['associatedBill']:
        lines.append("  Associated Bills:")
        for bill in report['associatedBill']:
            lines.append(f"    - {bill.get('type', '')}{bill.get('number', '')} (Congress {bill.get('congress', '')}) - URL: {bill.get('url', 'N/A')}")
    
    if 'text' in report and report['text'].get('url'):
        lines.append(f"  Text Versions URL: {report['text']['url']} (Count: {report['text'].get('count', 'N/A')})")
        
    return "\n".join(lines)

def format_committee_report_text_version(text_version_item: Dict[str, Any]) -> str:
    """Formats a single text version format item."""
    lines = []
    for fmt in text_version_item.get('formats', []):
        lines.append(f"  Type: {fmt.get('type', 'N/A')}")
        lines.append(f"    URL: {fmt.get('url', 'N/A')}")
        lines.append(f"    Is Errata: {fmt.get('isErrata', 'N/A')}")
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://committee-reports/latest")
async def get_latest_committee_reports(ctx: Context) -> str:
    """
    Get a list of the most recent committee reports.
    Returns the 10 most recently updated reports by default.
    """
    # Default parameters for fetching latest reports
    # Assuming 'updateDate+desc' is a valid sort for /committee-report endpoint
    # If not, this might need adjustment based on API capabilities for sorting
    default_params = {"limit": 10, "sort": "updateDate+desc"} 
        
    data = await make_api_request("/committee-report", ctx, params=default_params)
    
    if "error" in data:
        return f"Error retrieving latest committee reports: {data['error']}"
    
    reports = data.get("reports", [])
    if not reports:
        return "No recent committee reports found."
        
    result = ["Latest Committee Reports:"]
    for report in reports:
        result.append("\n" + format_committee_report_item(report))
    
    return "\n".join(result)

@mcp.resource("congress://committee-reports/{congress}")
async def get_committee_reports_by_congress(ctx: Context,
    congress: int,
) -> str:
    """
    Get committee reports for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    params = {}
    # Example of how you might still want to pass these if needed, e.g., from a config or fixed values
    # if conference is not None: params["conference"] = conference 
    # if offset is not None: params["offset"] = offset
    # Default limit if not specified, or remove if API default is fine
    # params["limit"] = 10 # Or whatever default you prefer for this specific resource
    # if fromDateTime is not None: params["fromDateTime"] = fromDateTime
    # if toDateTime is not None: params["toDateTime"] = toDateTime

    data = await make_api_request(f"/committee-report/{congress}", ctx, params=params)
    
    if "error" in data:
        return f"Error retrieving committee reports for congress {congress}: {data['error']}"
    
    reports = data.get("reports", [])
    if not reports:
        return f"No committee reports found for congress {congress}."
        
    result = [f"Committee Reports for Congress {congress}:"]
    for report in reports:
        result.append("\n" + format_committee_report_item(report))
    
    return "\n".join(result)

@mcp.resource("congress://committee-reports/{congress}/{report_type}")
async def get_committee_reports_by_congress_and_type(
    ctx: Context,
    congress: int, 
    report_type: str,
) -> str:
    """
    Get committee reports for a specific Congress and report type.
    
    Args:
        congress: The Congress number (e.g., 117).
        report_type: The type of report (e.g., "hrpt", "srpt").
    """
    params = {}
    # Add any default or internally decided params here if needed
    # params["limit"] = 10 # Example

    endpoint = f"/committee-report/{congress}/{report_type.lower()}"
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        return f"Error retrieving committee reports for congress {congress}, type {report_type}: {data['error']}"
    
    reports = data.get("reports", [])
    if not reports:
        return f"No committee reports found for congress {congress}, type {report_type} matching your criteria."
        
    result = [f"Committee Reports for Congress {congress}, Type {report_type.upper()}:"]
    for report in reports:
        result.append("\n" + format_committee_report_item(report))
    
    return "\n".join(result)

@mcp.resource("congress://committee-reports/{congress}/{report_type}/{report_number}")
async def get_committee_report_details(
    ctx: Context,
    congress: int,
    report_type: str, # hrpt, srpt, or erpt
    report_number: int
) -> str:
    """
    Get detailed information for a specific committee report.
    """
    endpoint = f"/committee-report/{congress}/{report_type.lower()}/{report_number}"
    data = await make_api_request(endpoint, ctx)
    
    if "error" in data:
        return f"Error retrieving details for committee report {congress}/{report_type}/{report_number}: {data['error']}"
    
    report_details_list = data.get("committeeReports", [])
    if not report_details_list:
        return f"No details found for committee report {congress}/{report_type}/{report_number}."
    
    report_detail = report_details_list[0]
        
    return format_committee_report_detail(report_detail)


@mcp.resource("congress://committee-reports/{congress}/{report_type}/{report_number}/text")
async def get_committee_report_text_versions(
    ctx: Context,
    congress: int, 
    report_type: str, 
    report_number: int,
) -> str:
    """
    Get text versions for a specific committee report.
    
    Args:
        congress: The Congress number (e.g., 117).
        report_type: The type of report (e.g., "hrpt").
        report_number: The report number.
    """
    params = {}
    # Add any default or internally decided params here if needed
    # if offset is not None: params["offset"] = offset # If passed via other means
    # if limit is not None: params["limit"] = limit

    endpoint = f"/committee-report/{congress}/{report_type.lower()}/{report_number}/text"
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        return f"Error retrieving text versions for committee report {congress}/{report_type}/{report_number}: {data['error']}"
    
    text_versions = data.get("text", [])
    if not text_versions:
        return f"No text versions found for committee report {congress}/{report_type}/{report_number}."
        
    result = [f"Text Versions for Committee Report {congress}/{report_type.upper()}/{report_number}:"]
    for version_item_container in text_versions:
        result.append("\n" + format_committee_report_text_version(version_item_container))

    return "\n".join(result)

# --- MCP Tools ---

@mcp.tool()
async def search_committee_reports(
    ctx: Context,
    conference: Optional[str] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None,
) -> str:
    """
    Search for committee reports based on various criteria.

    Args:
        conference: Filter by conference reports (true or false).
        offset: The starting record for pagination.
        limit: The number of records to return (max 250).
        fromDateTime: Start date for filtering by update date (YYYY-MM-DDT00:00:00Z).
        toDateTime: End date for filtering by update date (YYYY-MM-DDT00:00:00Z).
    """
    params = {}
    endpoint = "/committee-report"

    if conference is not None:
        params["conference"] = conference
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    if fromDateTime is not None:
        params["fromDateTime"] = fromDateTime
    if toDateTime is not None:
        params["toDateTime"] = toDateTime
    
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        return f"Error searching committee reports: {data['error']}"
    
    reports = data.get("reports", [])
    if not reports:
        return "No committee reports found matching your search criteria."
        
    result = ["Search Results - Committee Reports:"]
    for report in reports:
        result.append("\n" + format_committee_report_item(report))
    
    return "\n".join(result)
