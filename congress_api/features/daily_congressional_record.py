# congress_api/features/daily_congressional_record.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        
        # Add congress information if available in the issue
        if 'congress' in issue:
            lines[1] = f"Congress: {issue.get('congress', 'N/A')}"
        
        # Add full issue date if available
        if 'fullIssue' in issue:
            lines.append(f"Full Issue Date: {issue.get('fullIssue', 'N/A')}")
        
        # Add entire issue links
        if 'entireIssue' in issue:
            lines.append("\nEntire Issue:")
            for item in issue['entireIssue']:
                part = item.get('part', '')
                part_text = f" (Part {part})" if part else ""
                lines.append(f"  - {item.get('type', 'N/A')}{part_text}: {item.get('url', 'N/A')}")
        
        # Add sections
        if 'sections' in issue:
            lines.append("\nSections:")
            for section in issue['sections']:
                lines.append(f"  - {section.get('name', 'N/A')}")
                lines.append(f"    Pages: {section.get('startPage', 'N/A')} - {section.get('endPage', 'N/A')}")
                
                if 'text' in section:
                    lines.append("    Available formats:")
                    for text_item in section['text']:
                        part = text_item.get('part', '')
                        part_text = f" (Part {part})" if part else ""
                        lines.append(f"      - {text_item.get('type', 'N/A')}{part_text}: {text_item.get('url', 'N/A')}")
        
        # Add articles info
        if 'articles' in issue:
            articles = issue['articles']
            lines.append(f"\nArticles: {articles.get('count', 'N/A')}")
            lines.append(f"Articles URL: {articles.get('url', 'N/A')}")
    else:
        # Handle case where the response doesn't have an 'issue' key
        # This might be the case for older API versions or different response formats
        lines.append("\nNo detailed issue information available.")
        
        # Try to extract any available information from the response
        if 'request' in record_data:
            lines.append(f"\nAPI Request: {record_data.get('request', {}).get('url', 'N/A')}")
    
    return "\n".join(lines)
    
    return "\n".join(lines)

def format_daily_record_articles(articles_data: Dict[str, Any]) -> str:
    """Formats articles from a daily congressional record issue."""
    if not articles_data or 'articles' not in articles_data:
        return "No articles available."
    
    articles = articles_data['articles']
    if not articles:
        return "No articles found."
    
    lines = ["Daily Congressional Record Articles:"]
    
    for section in articles:
        section_name = section.get('name', 'Unnamed Section')
        lines.append(f"\n## {section_name}")
        
        section_articles = section.get('sectionArticles', [])
        for article in section_articles:
            title = article.get('title', 'Untitled')
            lines.append(f"\n- {title}")
            lines.append(f"  Pages: {article.get('startPage', 'N/A')} - {article.get('endPage', 'N/A')}")
            
            if 'text' in article:
                lines.append("  Available formats:")
                for text_item in article['text']:
                    part = text_item.get('part', '')
                    part_text = f" (Part {part})" if part else ""
                    lines.append(f"    - {text_item.get('type', 'N/A')}{part_text}: {text_item.get('url', 'N/A')}")
    
    return "\n".join(lines)

# --- MCP Resources ---

@mcp.resource("congress://daily-congressional-record/latest")
async def get_latest_daily_congressional_record() -> str:
    """
    Get the most recent daily congressional record issues.
    Returns the 10 most recently published issues by default.
    """
    ctx = mcp.get_context()
    params = {
        "limit": 10,
        "format": "json"
    }
    
    logger.debug("Fetching latest daily congressional record issues")
    data = await make_api_request("/daily-congressional-record", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving latest daily congressional record issues: {data['error']}")
        return f"Error retrieving latest daily congressional record issues: {data['error']}"
    
    if 'dailyCongressionalRecord' not in data:
        logger.warning("No dailyCongressionalRecord field in response")
        return "No daily congressional record issues found."
    
    issues = data['dailyCongressionalRecord']
    if not issues:
        logger.info("No daily congressional record issues found")
        return "No daily congressional record issues found."
    
    logger.info(f"Found {len(issues)} daily congressional record issues")
    lines = ["Latest Daily Congressional Record Issues:"]
    for issue in issues:
        lines.append("")
        lines.append(format_daily_record_item(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://daily-congressional-record/{volume_number}")
async def get_daily_congressional_record_by_volume(volume_number: str) -> str:
    """
    Get daily congressional record issues for a specific volume.
    
    Args:
        volume_number: The volume number (e.g., "166").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching daily congressional record issues for volume {volume_number}")
    data = await make_api_request(f"/daily-congressional-record/{volume_number}", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving daily congressional record issues for volume {volume_number}: {data['error']}")
        return f"Error retrieving daily congressional record issues for volume {volume_number}: {data['error']}"
    
    if 'dailyCongressionalRecord' not in data:
        logger.warning(f"No dailyCongressionalRecord field in response for volume {volume_number}")
        return f"No daily congressional record issues found for volume {volume_number}."
    
    issues = data['dailyCongressionalRecord']
    if not issues:
        logger.info(f"No daily congressional record issues found for volume {volume_number}")
        return f"No daily congressional record issues found for volume {volume_number}."
    
    logger.info(f"Found {len(issues)} daily congressional record issues for volume {volume_number}")
    lines = [f"Daily Congressional Record Issues for Volume {volume_number}:"]
    for issue in issues:
        lines.append("")
        lines.append(format_daily_record_item(issue))
    
    return "\n".join(lines)

@mcp.resource("congress://daily-congressional-record/{volume_number}/{issue_number}")
async def get_daily_congressional_record_issue(volume_number: str, issue_number: str) -> str:
    """
    Get detailed information for a specific daily congressional record issue.
    
    Args:
        volume_number: The volume number (e.g., "168").
        issue_number: The issue number (e.g., "153").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching daily congressional record issue for volume {volume_number}, issue {issue_number}")
    api_endpoint = f"/daily-congressional-record/{volume_number}/{issue_number}"
    logger.info(f"API Endpoint: {api_endpoint}")
    
    data = await make_api_request(api_endpoint, ctx, params=params)
    
    # Log the raw response for debugging
    logger.info(f"Raw API Response: {data}")
    
    if "error" in data:
        logger.error(f"Error retrieving daily congressional record issue for volume {volume_number}, issue {issue_number}: {data['error']}")
        return f"Error retrieving daily congressional record issue for volume {volume_number}, issue {issue_number}: {data['error']}"
    
    logger.info(f"Retrieved daily congressional record issue for volume {volume_number}, issue {issue_number}")
    return format_daily_record_detail(data)

@mcp.resource("congress://daily-congressional-record/{volume_number}/{issue_number}/articles")
async def get_daily_congressional_record_articles(volume_number: str, issue_number: str) -> str:
    """
    Get articles from a specific daily congressional record issue.
    
    Args:
        volume_number: The volume number (e.g., "167").
        issue_number: The issue number (e.g., "21").
    """
    ctx = mcp.get_context()
    params = {
        "format": "json"
    }
    
    logger.debug(f"Fetching articles for daily congressional record volume {volume_number}, issue {issue_number}")
    data = await make_api_request(f"/daily-congressional-record/{volume_number}/{issue_number}/articles", ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error retrieving articles for daily congressional record volume {volume_number}, issue {issue_number}: {data['error']}")
        return f"Error retrieving articles for daily congressional record volume {volume_number}, issue {issue_number}: {data['error']}"
    
    logger.info(f"Retrieved articles for daily congressional record volume {volume_number}, issue {issue_number}")
    return format_daily_record_articles(data)

# --- MCP Tools ---

@mcp.tool()
async def search_daily_congressional_record(
    volume_number: Optional[str] = None,
    issue_number: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for daily congressional record issues based on various criteria.
    
    Args:
        volume_number: Optional volume number to filter by (e.g., "169").
        issue_number: Optional issue number to filter by (e.g., "118").
        limit: Maximum number of results to return (default: 10).
    """
    ctx = mcp.get_context()
    params = {
        "format": "json",
        "limit": limit
    }
    
    endpoint = "/daily-congressional-record"
    
    # Build the endpoint based on provided parameters
    if volume_number:
        endpoint = f"{endpoint}/{volume_number}"
        if issue_number:
            endpoint = f"{endpoint}/{issue_number}"
    
    logger.debug(f"Searching daily congressional record with endpoint: {endpoint}")
    data = await make_api_request(endpoint, ctx, params=params)
    
    if "error" in data:
        logger.error(f"Error searching daily congressional record: {data['error']}")
        return f"Error searching daily congressional record: {data['error']}"
    
    # Handle different response formats based on the endpoint
    if issue_number and volume_number:
        # Detailed issue view
        logger.info(f"Retrieved daily congressional record volume {volume_number}, issue {issue_number}")
        return format_daily_record_detail(data)
    elif volume_number:
        # Volume view
        if 'dailyCongressionalRecord' not in data:
            logger.warning(f"No dailyCongressionalRecord field in response for volume {volume_number}")
            return f"No daily congressional record issues found for volume {volume_number}."
        
        issues = data['dailyCongressionalRecord']
        if not issues:
            logger.info(f"No daily congressional record issues found for volume {volume_number}")
            return f"No daily congressional record issues found for volume {volume_number}."
        
        logger.info(f"Found {len(issues)} daily congressional record issues for volume {volume_number}")
        lines = [f"Daily Congressional Record Issues for Volume {volume_number}:"]
    else:
        # Latest issues view
        if 'dailyCongressionalRecord' not in data:
            logger.warning("No dailyCongressionalRecord field in response")
            return "No daily congressional record issues found."
        
        issues = data['dailyCongressionalRecord']
        if not issues:
            logger.info("No daily congressional record issues found")
            return "No daily congressional record issues found."
        
        logger.info(f"Found {len(issues)} daily congressional record issues")
        lines = ["Search Results - Daily Congressional Record Issues:"]
    
    # Format the list of issues
    if 'dailyCongressionalRecord' in data:
        issues = data['dailyCongressionalRecord']
        for issue in issues:
            lines.append("")
            lines.append(format_daily_record_item(issue))
    
    return "\n".join(lines)
