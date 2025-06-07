# congress_api/features/committee_reports.py
import logging
import re
from typing import Dict, List, Any, Optional
import httpx
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.api_wrapper import safe_committee_reports_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.exceptions import APIErrorResponse, ErrorType, format_error_response, CommonErrors
from ..core.response_utils import CommitteeReportsProcessor, clean_committee_reports_response
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Functions ---

def format_committee_report_item(report: Dict[str, Any]) -> str:
    """Formats a single committee report item for display in a list."""
    lines = [
        f"**Citation**: {report.get('citation', 'N/A')}",
        f"  **Congress**: {report.get('congress', 'N/A')}",
        f"  **Chamber**: {report.get('chamber', 'N/A')}",
        f"  **Type**: {report.get('type', 'N/A')}",
        f"  **Number**: {report.get('number', 'N/A')}",
        f"  **Part**: {report.get('part', 'N/A')}",
        f"  **Update Date**: {report.get('updateDate', 'N/A')}",
        f"  **URL**: {report.get('url', 'N/A')}"
    ]
    return "\n".join(lines)

def format_committee_report_detail(report: Dict[str, Any]) -> str:
    """Formats detailed information for a single committee report."""
    lines = [
        f"# Committee Report Details",
        f"",
        f"**Title**: {report.get('title', 'N/A')}",
        f"**Citation**: {report.get('citation', 'N/A')}",
        f"**Congress**: {report.get('congress', 'N/A')}",
        f"**Chamber**: {report.get('chamber', 'N/A')}",
        f"**Report Type**: {report.get('reportType', 'N/A')} ({report.get('type', 'N/A')})",
        f"**Number**: {report.get('number', 'N/A')}",
        f"**Part**: {report.get('part', 'N/A')}",
        f"**Issue Date**: {report.get('issueDate', 'N/A')}",
        f"**Update Date**: {report.get('updateDate', 'N/A')}",
        f"**Is Conference Report**: {'Yes' if report.get('isConferenceReport') else 'No'}",
        f"**Session Number**: {report.get('sessionNumber', 'N/A')}",
    ]
    
    if 'associatedBill' in report and report['associatedBill']:
        lines.append("")
        lines.append("## Associated Bills:")
        for bill in report['associatedBill']:
            lines.append(f"- **{bill.get('type', '')}{bill.get('number', '')}** (Congress {bill.get('congress', '')}) - [View Bill]({bill.get('url', 'N/A')})")
    
    if 'text' in report and report['text'].get('url'):
        lines.append("")
        lines.append(f"## Text Versions")
        lines.append(f"**URL**: {report['text']['url']}")
        lines.append(f"**Count**: {report['text'].get('count', 'N/A')}")
        
    return "\n".join(lines)

def format_committee_report_text_version(text_version_item: Dict[str, Any]) -> str:
    """Formats a single text version format item."""
    lines = []
    for fmt in text_version_item.get('formats', []):
        lines.append(f"**Format**: {fmt.get('type', 'N/A')}")
        lines.append(f"  **URL**: {fmt.get('url', 'N/A')}")
    return "\n".join(lines)

# --- MCP Tools ---

# @require_paid_access
async def get_latest_committee_reports(ctx: Context) -> str:
    """
    Get a list of the most recent committee reports.
    Returns the 10 most recently updated reports by default.
    """
    logger.debug("Fetching latest committee reports")
    
    try:
        # Make defensive API request
        data = await safe_committee_reports_request("/committee-report", ctx, {})
        
        if not data or 'reports' not in data:
            logger.warning("No committee reports data received from API")
            return format_error_response(CommonErrors.data_not_found("committee reports"))
        
        # Process and clean response - use reports data directly since base endpoint returns 'reports'
        reports_data = data['reports']
        if not reports_data:
            logger.info("No committee reports found")
            return "No committee reports found."
        
        # Apply deduplication and sorting manually since clean_committee_reports_response expects 'committeeReports'
        from congress_api.core.response_utils import CommitteeReportsProcessor
        
        # Deduplicate and sort
        deduplicated_reports = CommitteeReportsProcessor.deduplicate_reports(reports_data)
        sorted_reports = sorted(deduplicated_reports, key=lambda x: x.get('updateDate', ''), reverse=True)
        limited_reports = sorted_reports[:10]  # Limit to 10 most recent
        
        logger.info(f"Found {len(limited_reports)} committee reports")
        
        # Format results
        formatted_reports = []
        for report in limited_reports:
            formatted_reports.append(format_committee_report_item(report))
        
        result = f"# Latest Committee Reports ({len(limited_reports)} found)\n\n"
        result += "\n\n---\n\n".join(formatted_reports)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching latest committee reports: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            "Failed to fetch latest committee reports",
            message=str(e)
        ))

# @require_paid_access
async def get_committee_reports_by_congress(ctx: Context, congress: int) -> str:
    """
    Get committee reports for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    logger.debug(f"Fetching committee reports for Congress {congress}")
    
    # Validate congress parameter
    validation = ParameterValidator.validate_congress_number(congress)
    if not validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    try:
        endpoint = f"/committee-report/{congress}"
        data = await safe_committee_reports_request(endpoint, ctx, {})
        
        if not data or 'reports' not in data:
            logger.warning(f"No committee reports data received for Congress {congress}")
            return format_error_response(CommonErrors.data_not_found(
                "committee reports", 
                {"congress": congress}
            ))
        
        # Process and clean response - use reports data directly since congress endpoint returns 'reports'
        reports_data = data['reports']
        if not reports_data:
            logger.info(f"No committee reports found for Congress {congress}")
            return format_error_response(CommonErrors.data_not_found(
                "committee reports", 
                {"congress": congress}
            ))
        
        # Apply deduplication and sorting manually since clean_committee_reports_response expects 'committeeReports'
        from congress_api.core.response_utils import CommitteeReportsProcessor
        
        # Deduplicate and sort
        deduplicated_reports = CommitteeReportsProcessor.deduplicate_reports(reports_data)
        sorted_reports = sorted(deduplicated_reports, key=lambda x: x.get('updateDate', ''), reverse=True)
        limited_reports = sorted_reports[:10]  # Limit to 10 most recent
        
        logger.info(f"Found {len(limited_reports)} committee reports for Congress {congress}")
        
        # Format results
        formatted_reports = []
        for report in limited_reports:
            formatted_reports.append(format_committee_report_item(report))
        
        result = f"# Committee Reports for Congress {congress} ({len(limited_reports)} found)\n\n"
        result += "\n\n---\n\n".join(formatted_reports)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching committee reports for Congress {congress}: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            f"Failed to fetch committee reports for Congress {congress}",
            message=str(e)
        ))

# @require_paid_access
async def get_committee_reports_by_congress_and_type(
    ctx: Context,
    congress: int, 
    report_type: str
) -> str:
    """
    Get committee reports for a specific Congress and report type.
    
    Args:
        congress: The Congress number (e.g., 117).
        report_type: The type of report (e.g., "hrpt", "srpt").
    """
    logger.debug(f"Fetching committee reports for Congress {congress}, type {report_type}")
    
    # Validate congress parameter
    validation = ParameterValidator.validate_congress_number(congress)
    if not validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Validate report type
    report_type_validation = ParameterValidator.validate_report_type(report_type)
    if not report_type_validation.is_valid:
        logger.warning(f"Invalid report type: {report_type}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_type", 
            report_type, 
            report_type_validation.error_message
        ))
    
    try:
        endpoint = f"/committee-report/{congress}/{report_type}"
        data = await safe_committee_reports_request(endpoint, ctx, {})
        
        if not data or 'reports' not in data:
            logger.warning(f"No committee reports data received for Congress {congress}, type {report_type}")
            return format_error_response(CommonErrors.data_not_found(
                "committee reports", 
                {"congress": congress, "report_type": report_type}
            ))
        
        # Process and clean response - use reports data directly since congress/type endpoint returns 'reports'
        reports_data = data['reports']
        if not reports_data:
            logger.info(f"No committee reports found for Congress {congress}, type {report_type}")
            return format_error_response(CommonErrors.data_not_found(
                "committee reports", 
                {"congress": congress, "report_type": report_type}
            ))
        
        # Apply deduplication and sorting manually since clean_committee_reports_response expects 'committeeReports'
        from congress_api.core.response_utils import CommitteeReportsProcessor
        
        # Deduplicate and sort
        deduplicated_reports = CommitteeReportsProcessor.deduplicate_reports(reports_data)
        sorted_reports = sorted(deduplicated_reports, key=lambda x: x.get('updateDate', ''), reverse=True)
        limited_reports = sorted_reports[:50]  # Limit to 50 most recent
        
        logger.info(f"Found {len(limited_reports)} committee reports for Congress {congress}, type {report_type}")
        
        # Format results
        formatted_reports = []
        for report in limited_reports:
            formatted_reports.append(format_committee_report_item(report))
        
        result = f"# Committee Reports for Congress {congress}, Type {report_type} ({len(limited_reports)} found)\n\n"
        result += "\n\n---\n\n".join(formatted_reports)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching committee reports for Congress {congress}, type {report_type}: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            f"Failed to fetch committee reports for Congress {congress}, type {report_type}",
            message=str(e)
        ))

# @require_paid_access
async def get_committee_report_details(
    ctx: Context,
    congress: int,
    report_type: str,
    report_number: int
) -> str:
    """
    Get detailed information for a specific committee report.
    
    Args:
        congress: The Congress number (e.g., 117).
        report_type: The type of report (e.g., "hrpt", "srpt", "erpt").
        report_number: The report number.
    """
    logger.debug(f"Fetching details for committee report {congress}/{report_type}/{report_number}")
    
    # Validate congress parameter
    validation = ParameterValidator.validate_congress_number(congress)
    if not validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Validate report type
    report_type_validation = ParameterValidator.validate_report_type(report_type)
    if not report_type_validation.is_valid:
        logger.warning(f"Invalid report type: {report_type}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_type", 
            report_type, 
            report_type_validation.error_message
        ))
    
    # Validate report number
    report_number_validation = ParameterValidator.validate_report_number(report_number)
    if not report_number_validation.is_valid:
        logger.warning(f"Invalid report number: {report_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_number", 
            report_number, 
            report_number_validation.error_message
        ))
    
    try:
        endpoint = f"/committee-report/{congress}/{report_type}/{report_number}"
        data = await safe_committee_reports_request(endpoint, ctx, {})
        
        if not data or 'committeeReports' not in data:
            logger.warning(f"No committee report data received for {congress}/{report_type}/{report_number}")
            return format_error_response(CommonErrors.data_not_found(
                "committee report", 
                {"congress": congress, "report_type": report_type, "report_number": report_number}
            ))
        
        reports = data['committeeReports']
        if not reports:
            logger.warning(f"Empty committee reports list for {congress}/{report_type}/{report_number}")
            return format_error_response(CommonErrors.data_not_found(
                "committee report", 
                {"congress": congress, "report_type": report_type, "report_number": report_number}
            ))
        
        report_item = reports[0]  # Get the first (and likely only) report
        
        logger.info(f"Successfully retrieved committee report details for {congress}/{report_type}/{report_number}")
        
        return format_committee_report_detail(report_item)
        
    except Exception as e:
        logger.error(f"Error fetching committee report details for {congress}/{report_type}/{report_number}: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            f"Failed to fetch committee report details for {congress}/{report_type}/{report_number}",
            message=str(e)
        ))

# @require_paid_access
async def get_committee_report_text_versions(
    ctx: Context,
    congress: int, 
    report_type: str, 
    report_number: int
) -> str:
    """
    Get text versions for a specific committee report.
    
    Args:
        congress: The Congress number (e.g., 117).
        report_type: The type of report (e.g., "hrpt").
        report_number: The report number.
    """
    logger.debug(f"Fetching text versions for committee report {congress}/{report_type}/{report_number}")
    
    # Validate congress parameter
    validation = ParameterValidator.validate_congress_number(congress)
    if not validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Validate report type
    report_type_validation = ParameterValidator.validate_report_type(report_type)
    if not report_type_validation.is_valid:
        logger.warning(f"Invalid report type: {report_type}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_type", 
            report_type, 
            report_type_validation.error_message
        ))
    
    # Validate report number
    report_number_validation = ParameterValidator.validate_report_number(report_number)
    if not report_number_validation.is_valid:
        logger.warning(f"Invalid report number: {report_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_number", 
            report_number, 
            report_number_validation.error_message
        ))
    
    try:
        endpoint = f"/committee-report/{congress}/{report_type}/{report_number}/text"
        data = await safe_committee_reports_request(endpoint, ctx, {})
        
        if not data or 'text' not in data:
            logger.warning(f"No text versions data received for committee report {congress}/{report_type}/{report_number}")
            return format_error_response(CommonErrors.data_not_found(
                "committee report text versions", 
                {"congress": congress, "report_type": report_type, "report_number": report_number}
            ))
        
        text_versions = data['text']
        
        if not text_versions:
            logger.info(f"No text versions found for committee report {congress}/{report_type}/{report_number}")
            return f"No text versions found for committee report {congress}/{report_type}/{report_number}."
        
        logger.info(f"Found {len(text_versions)} text versions for committee report {congress}/{report_type}/{report_number}")
        
        # Format results
        formatted_versions = []
        for version in text_versions:
            formatted_versions.append(format_committee_report_text_version(version))
        
        result = f"# Text Versions for Committee Report {congress}/{report_type}/{report_number} ({len(text_versions)} found)\n\n"
        result += "\n\n---\n\n".join(formatted_versions)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching text versions for committee report {congress}/{report_type}/{report_number}: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            f"Failed to fetch text versions for committee report {congress}/{report_type}/{report_number}",
            message=str(e)
        ))

# @require_paid_access
async def search_committee_reports(
    ctx: Context,
    conference: Optional[str] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    fromDateTime: Optional[str] = None,
    toDateTime: Optional[str] = None
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
    logger.debug(f"Searching committee reports with criteria: conference={conference}, offset={offset}, limit={limit}")
    
    # Validate parameters
    params = {}
    
    if conference is not None:
        conference_validation = ParameterValidator.validate_conference_filter(conference)
        if not conference_validation.is_valid:
            logger.warning(f"Invalid conference parameter: {conference}")
            return format_error_response(CommonErrors.invalid_parameter(
                "conference", 
                conference, 
                conference_validation.error_message
            ))
        params['conference'] = conference
    
    if offset is not None:
        offset_validation = ParameterValidator.validate_offset(offset)
        if not offset_validation.is_valid:
            logger.warning(f"Invalid offset parameter: {offset}")
            return format_error_response(CommonErrors.invalid_parameter(
                "offset", 
                offset, 
                offset_validation.error_message
            ))
        params['offset'] = offset
    
    if limit is not None:
        limit_validation = ParameterValidator.validate_limit_range(limit, max_limit=250)
        if not limit_validation.is_valid:
            logger.warning(f"Invalid limit parameter: {limit}")
            return format_error_response(CommonErrors.invalid_parameter(
                "limit", 
                limit, 
                limit_validation.error_message
            ))
        params['limit'] = limit
    
    if fromDateTime is not None:
        from_date_validation = ParameterValidator.validate_datetime_format(fromDateTime)
        if not from_date_validation.is_valid:
            logger.warning(f"Invalid fromDateTime parameter: {fromDateTime}")
            return format_error_response(CommonErrors.invalid_parameter(
                "fromDateTime", 
                fromDateTime, 
                from_date_validation.error_message
            ))
        params['fromDateTime'] = fromDateTime
    
    if toDateTime is not None:
        to_date_validation = ParameterValidator.validate_datetime_format(toDateTime)
        if not to_date_validation.is_valid:
            logger.warning(f"Invalid toDateTime parameter: {toDateTime}")
            return format_error_response(CommonErrors.invalid_parameter(
                "toDateTime", 
                toDateTime, 
                to_date_validation.error_message
            ))
        params['toDateTime'] = toDateTime
    
    try:
        data = await safe_committee_reports_request("/committee-report", ctx, params)
        
        if not data or 'reports' not in data:
            logger.warning("No committee reports data received from search")
            return format_error_response(CommonErrors.data_not_found("committee reports"))
        
        # Process and clean response - use reports data directly since base endpoint returns 'reports'
        reports_data = data['reports']
        if not reports_data:
            logger.info("No committee reports found in search")
            return format_error_response(CommonErrors.data_not_found("committee reports"))
        
        # Apply deduplication and sorting manually since clean_committee_reports_response expects 'committeeReports'
        from congress_api.core.response_utils import CommitteeReportsProcessor
        
        # Deduplicate and sort
        deduplicated_reports = CommitteeReportsProcessor.deduplicate_reports(reports_data)
        sorted_reports = sorted(deduplicated_reports, key=lambda x: x.get('updateDate', ''), reverse=True)
        limited_reports = sorted_reports[:limit]
        
        logger.info(f"Found {len(limited_reports)} committee reports matching search criteria")
        
        # Format results
        formatted_reports = []
        for report in limited_reports:
            formatted_reports.append(format_committee_report_item(report))
        
        result = f"# Committee Reports Search Results ({len(limited_reports)} found)\n\n"
        result += "\n\n---\n\n".join(formatted_reports)
        
        return result
        
    except Exception as e:
        logger.error(f"Error searching committee reports: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            "Failed to search committee reports",
            message=str(e)
        ))

# @require_paid_access
async def get_committee_report_content(
    ctx: Context,
    congress: int, 
    report_type: str, 
    report_number: int,
    chunk_number: int = 1,
    chunk_size: int = 8000
) -> str:
    """
    Get the actual text content of a specific committee report, with chunking support for large reports.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        report_type: Report type (e.g., 'hrpt' for House Report, 'srpt' for Senate Report)
        report_number: Report number
        chunk_number: Chunk number to retrieve (1-based, default: 1)
        chunk_size: Size of each chunk in characters (default: 8000)
    """
    logger.debug(f"Fetching content for committee report {congress}/{report_type}/{report_number}")
    
    # Validate congress parameter
    validation = ParameterValidator.validate_congress_number(congress)
    if not validation.is_valid:
        logger.warning(f"Invalid congress number: {congress}")
        return format_error_response(CommonErrors.invalid_congress_number(congress))
    
    # Validate report type
    report_type_validation = ParameterValidator.validate_report_type(report_type)
    if not report_type_validation.is_valid:
        logger.warning(f"Invalid report type: {report_type}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_type", 
            report_type, 
            report_type_validation.error_message
        ))
    report_type = report_type_validation.sanitized_value
    
    # Validate report number
    report_number_validation = ParameterValidator.validate_report_number(report_number)
    if not report_number_validation.is_valid:
        logger.warning(f"Invalid report number: {report_number}")
        return format_error_response(CommonErrors.invalid_parameter(
            "report_number", 
            report_number, 
            report_number_validation.error_message
        ))
    
    # Validate chunk_number parameter
    if not isinstance(chunk_number, int) or chunk_number < 1:
        error_response = CommonErrors.invalid_parameter(
            "chunk_number", 
            chunk_number, 
            "Chunk number must be a positive integer (1-based)"
        )
        return format_error_response(error_response)
    
    # Validate chunk_size parameter
    if not isinstance(chunk_size, int) or chunk_size < 1000 or chunk_size > 50000:
        error_response = CommonErrors.invalid_parameter(
            "chunk_size", 
            chunk_size, 
            "Chunk size must be between 1000 and 50000 characters"
        )
        return format_error_response(error_response)
    
    try:
        # First, get the text versions to find the content URL
        endpoint = f"/committee-report/{congress}/{report_type}/{report_number}/text"
        data = await safe_committee_reports_request(endpoint, ctx, {})
        
        if not data or 'text' not in data:
            logger.warning(f"No text versions data received for committee report {congress}/{report_type}/{report_number}")
            return format_error_response(CommonErrors.data_not_found(
                "committee report text versions", 
                {"congress": congress, "report_type": report_type, "report_number": report_number}
            ))
        
        text_versions = data['text']
        if not text_versions:
            logger.info(f"No text versions found for committee report {congress}/{report_type}/{report_number}")
            return format_error_response(CommonErrors.data_not_found(
                "committee report text versions", 
                {"congress": congress, "report_type": report_type, "report_number": report_number}
            ))
        
        # Get the formatted text URL (prefer HTML format)
        text_url = None
        selected_format = None
        
        # Look through all text versions for a formatted text URL
        for text_version in text_versions:
            formats = text_version.get("formats", [])
            for fmt in formats:
                if fmt.get("type") == "Formatted Text":
                    text_url = fmt.get("url")
                    selected_format = fmt
                    break
            if text_url:
                break
        
        if not text_url:
            # If no formatted text, try to get any available format
            for text_version in text_versions:
                formats = text_version.get("formats", [])
                if formats:
                    text_url = formats[0].get("url")
                    selected_format = formats[0]
                    break
        
        if not text_url:
            available_formats = []
            for text_version in text_versions:
                for fmt in text_version.get("formats", []):
                    available_formats.append(fmt.get("type", "Unknown"))
            
            error_response = CommonErrors.data_not_found("committee report content", {
                "congress": congress,
                "report_type": report_type,
                "report_number": report_number,
                "available_formats": available_formats
            })
            return format_error_response(error_response)
        
        # Fetch the actual committee report text content
        try:
            # Configure HTTP client with proper headers and timeout
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            timeout = httpx.Timeout(30.0)  # 30 second timeout
            
            async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
                logger.debug(f"Fetching content from URL: {text_url}")
                response = await client.get(text_url)
                
                logger.debug(f"HTTP response status: {response.status_code}")
                if response.status_code != 200:
                    error_response = CommonErrors.api_server_error("committee report content retrieval")
                    error_response.details = {
                        "http_status": response.status_code,
                        "url": text_url,
                        "response_text": response.text[:500] if response.text else "No response text"
                    }
                    return format_error_response(error_response)
                
                html_content = response.text
                
                # Extract text from HTML and clean it up
                # Remove script and style elements
                html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                
                # Remove HTML tags but preserve some structure
                clean_text = re.sub(r'<[^>]+>', '', html_content)
                
                # Clean up whitespace and formatting
                clean_text = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)  # Multiple newlines to double
                clean_text = re.sub(r'[ \t]+', ' ', clean_text)  # Multiple spaces to single
                clean_text = clean_text.strip()
                
                # Calculate chunking
                total_chars = len(clean_text)
                total_chunks = (total_chars + chunk_size - 1) // chunk_size  # Ceiling division
                
                if chunk_number < 1 or chunk_number > total_chunks:
                    error_response = CommonErrors.invalid_parameter(
                        "chunk_number", 
                        chunk_number, 
                        f"Invalid chunk number. Report has {total_chunks} chunks of {chunk_size} characters each"
                    )
                    return format_error_response(error_response)
                
                # Extract the requested chunk
                start_pos = (chunk_number - 1) * chunk_size
                end_pos = min(start_pos + chunk_size, total_chars)
                chunk_text = clean_text[start_pos:end_pos]
                
                # Add some overlap context if not the first chunk
                if chunk_number > 1 and start_pos > 200:
                    overlap_start = max(0, start_pos - 200)
                    overlap_text = clean_text[overlap_start:start_pos]
                    chunk_text = f"[...previous context: {overlap_text[-200:]}]\n\n{chunk_text}"
                
                result = [
                    f"# Committee Report {report_type.upper()} {report_number} - {congress}th Congress",
                    f"**Format:** {selected_format.get('type', 'Unknown')}",
                    f"**Chunk:** {chunk_number} of {total_chunks} (characters {start_pos+1:,}-{end_pos:,} of {total_chars:,})",
                    f"**Source:** {text_url}",
                    "",
                    "## Report Content",
                    "",
                    chunk_text
                ]
                
                if chunk_number < total_chunks:
                    result.extend([
                        "",
                        f"📄 **Note**: This is chunk {chunk_number} of {total_chunks}. Use `chunk_number={chunk_number + 1}` to get the next chunk."
                    ])
                
                return "\n".join(result)
                
        except httpx.TimeoutException:
            logger.error(f"Timeout while fetching committee report content from: {text_url}")
            error_response = CommonErrors.api_server_error("committee report content retrieval")
            error_response.details = {
                "error": "Request timeout",
                "url": text_url,
                "suggestion": "The content server may be temporarily slow. Please try again."
            }
            return format_error_response(error_response)
            
        except httpx.RequestError as e:
            logger.error(f"Request error while fetching committee report content: {e}")
            error_response = CommonErrors.api_server_error("committee report content retrieval")
            error_response.details = {
                "error": f"Network error: {str(e)}",
                "url": text_url,
                "suggestion": "Please check your internet connection and try again."
            }
            return format_error_response(error_response)
            
        except Exception as e:
            logger.error(f"Unexpected error while fetching committee report content: {e}")
            error_response = CommonErrors.api_server_error("committee report content retrieval")
            error_response.details = {
                "error": f"Unexpected error: {str(e)}",
                "url": text_url
            }
            return format_error_response(error_response)
        
    except Exception as e:
        logger.error(f"Error fetching committee report content: {str(e)}")
        return format_error_response(CommonErrors.api_server_error(
            "Failed to fetch committee report content",
            message=str(e)
        ))
