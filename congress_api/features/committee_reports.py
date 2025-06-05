# congress_api/features/committee_reports.py
import logging
from typing import Dict, List, Any, Optional
from fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.api_wrapper import safe_committee_reports_request
from ..core.validators import ParameterValidator, ValidationResult
from ..core.exceptions import APIErrorResponse, ErrorType, format_error_response, CommonErrors
from ..core.response_utils import CommitteeReportsProcessor, clean_committee_reports_response

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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
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
