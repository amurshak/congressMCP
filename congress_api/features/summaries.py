# summaries.py
from typing import Dict, Any, Optional, List
import json
import logging
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request

# Reliability Framework Imports
from ..core.api_wrapper import safe_summaries_request
from ..core.validators import ParameterValidator
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import SummariesProcessor, clean_summaries_response
from ..core.auth.auth import require_paid_access

# Configure logging
logger = logging.getLogger(__name__)

# Formatting helpers
def format_summary(summary: Dict[str, Any]) -> str:
    """Format a summary into a readable format."""
    result = []
    
    # Basic information about the bill
    bill = summary.get("bill", {})
    bill_type = bill.get("type", "Unknown")
    bill_number = bill.get("number", "Unknown")
    congress = bill.get("congress", "Unknown")
    title = bill.get("title", "Untitled")
    
    result.append(f"# {title}")
    result.append(f"**Bill:** {bill_type.upper()} {bill_number} ({congress}th Congress)")
    
    # Action information
    action_date = summary.get("actionDate", "Unknown date")
    action_desc = summary.get("actionDesc", "Unknown action")
    result.append(f"**Action:** {action_desc} on {action_date}")
    
    # Chamber information
    current_chamber = summary.get("currentChamber", "Unknown")
    result.append(f"**Current Chamber:** {current_chamber}")
    
    # Summary text
    if "text" in summary:
        result.append("\n## Summary")
        result.append(summary["text"])
    
    # Update information
    update_date = summary.get("updateDate", "Unknown")
    result.append(f"\n**Last Updated:** {update_date}")
    
    return "\n".join(result)

def format_summaries_list(summaries: List[Dict[str, Any]], title: str) -> str:
    """Format a list of summaries into a readable format."""
    if not summaries:
        return "No summaries found."
    
    result = [f"# {title}\n"]
    result.append(f"**Found {len(summaries)} summaries**\n")
    
    for i, summary in enumerate(summaries, 1):
        result.append(f"## {i}. Summary")
        
        # Basic information about the bill
        bill = summary.get("bill", {})
        bill_type = bill.get("type", "Unknown")
        bill_number = bill.get("number", "Unknown")
        congress = bill.get("congress", "Unknown")
        title = bill.get("title", "Untitled")
        
        result.append(f"**Bill:** {bill_type.upper()} {bill_number} ({congress}th Congress)")
        result.append(f"**Title:** {title}")
        
        # Action information
        action_date = summary.get("actionDate", "Unknown date")
        action_desc = summary.get("actionDesc", "Unknown action")
        result.append(f"**Action:** {action_desc} on {action_date}")
        
        # Update information
        update_date = summary.get("updateDate", "Unknown")
        result.append(f"**Last Updated:** {update_date}")
        
        # Add URL to view full summary
        bill_url = bill.get("url", "")
        if bill_url:
            result.append(f"\n[View Bill Details]({bill_url})")
        
        result.append("")  # Add spacing between summaries
    
    return "\n".join(result)

# Resources
@mcp.resource("congress://summaries/latest")
async def get_latest_summaries(ctx: Context) -> str:
    """
    Get the most recent bill summaries.
    
    Returns a list of the 10 most recently updated summaries across all
    Congresses, sorted by update date in descending order.
    """
    logger.info("Accessing latest summaries resource")
    try:
        # Use defensive API wrapper
        data = await safe_summaries_request("/summaries", ctx, {"limit": 10, "sort": "updateDate+desc"})
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")  
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return format_error_response(
                CommonErrors.api_server_error("/summaries", data["error"])
            )
        
        # Process response with deduplication and cleaning
        summaries = clean_summaries_response(data, limit=10)
        
        if not summaries:
            return "No recent summaries found."
        
        logger.info(f"Returning {len(summaries)} latest summaries")
        return format_summaries_list(summaries, "Latest Bill Summaries")
        
    except Exception as e:
        logger.error(f"Error accessing latest summaries: {str(e)}")
        return format_error_response(
            CommonErrors.api_server_error("/summaries", str(e))
        )

@mcp.resource("congress://summaries/{congress}")
async def get_summaries_by_congress(ctx: Context, congress: str) -> str:
    """
    Get summaries from a specific Congress.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        
    Returns a list of the 10 most recently updated summaries from the
    specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing summaries for Congress {congress}")
    
    try:
        # Validate congress parameter
        congress_int = int(congress)
        validation = ParameterValidator.validate_congress_number(congress_int)
        if not validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("congress", congress, validation.error_message, validation.suggestions)
            )
        
        # Use defensive API wrapper
        data = await safe_summaries_request(f"/summaries/{congress}", ctx, {"limit": 10, "sort": "updateDate+desc"})
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return format_error_response(
                CommonErrors.api_server_error(f"/summaries/{congress}", data["error"])
            )
        
        # Process response with deduplication and cleaning
        summaries = clean_summaries_response(data, limit=10)
        
        if not summaries:
            return f"No summaries found for the {congress}th Congress."
        
        logger.info(f"Returning {len(summaries)} summaries for Congress {congress}")
        return format_summaries_list(summaries, f"Bill Summaries - {congress}th Congress")
        
    except ValueError:
        return format_error_response(
            CommonErrors.invalid_parameter("congress", congress, "Congress must be a valid number", ["117", "118", "119"])
        )
    except Exception as e:
        logger.error(f"Error accessing summaries for Congress {congress}: {str(e)}")
        return format_error_response(
            CommonErrors.api_server_error(f"/summaries/{congress}", str(e))
        )

@mcp.resource("congress://summaries/{congress}/{bill_type}")
async def get_summaries_by_type(ctx: Context, congress: str, bill_type: str) -> str:
    """
    Get summaries from a specific Congress and bill type.
    
    Args:
        congress: The number of the Congress (e.g., "117")
        bill_type: The type of bill (e.g., "hr", "s")
        
    Returns a list of the 10 most recently updated summaries of the specified
    bill type from the specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing summaries for Congress {congress}, bill type {bill_type}")
    
    try:
        # Validate congress parameter
        congress_int = int(congress)
        validation = ParameterValidator.validate_congress_number(congress_int)
        if not validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("congress", congress, validation.error_message, validation.suggestions)
            )
        
        # Validate bill type
        bill_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("bill_type", bill_type, bill_validation.error_message, bill_validation.suggestions)
            )
        
        # Use defensive API wrapper
        data = await safe_summaries_request(f"/summaries/{congress}/{bill_type}", ctx, {"limit": 10, "sort": "updateDate+desc"})
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return format_error_response(
                CommonErrors.api_server_error(f"/summaries/{congress}/{bill_type}", data["error"])
            )
        
        # Process response with deduplication and cleaning
        summaries = clean_summaries_response(data, limit=10)
        
        if not summaries:
            return f"No {bill_type.upper()} summaries found for the {congress}th Congress."
        
        logger.info(f"Returning {len(summaries)} {bill_type.upper()} summaries for Congress {congress}")
        return format_summaries_list(summaries, f"{bill_type.upper()} Bill Summaries - {congress}th Congress")
        
    except ValueError:
        return format_error_response(
            CommonErrors.invalid_parameter("congress", congress, "Congress must be a valid number", ["117", "118", "119"])
        )
    except Exception as e:
        logger.error(f"Error accessing summaries for Congress {congress}, bill type {bill_type}: {str(e)}")
        return format_error_response(
            CommonErrors.api_server_error(f"/summaries/{congress}/{bill_type}", str(e))
        )

@mcp.resource("congress://summaries/help")
async def get_summaries_help(ctx: Context) -> str:
    """
    Get usage guide and examples for the summaries API.
    
    Returns comprehensive information about how to use summaries endpoints,
    including examples, parameter formats, and best practices.
    """
    return """# 📋 **Bill Summaries API - Usage Guide**

## **Available Resources**

### **📊 Latest Summaries**
- **Resource**: `congress://summaries/latest`
- **Description**: Get the 10 most recent bill summaries across all Congresses
- **Use Case**: Stay updated on recent legislative activity

### **🏛️ Congress-Specific Summaries**  
- **Resource**: `congress://summaries/{congress}`
- **Description**: Get summaries from a specific Congress (e.g., 118th Congress)
- **Example**: `congress://summaries/118`
- **Use Case**: Research legislative activity in a particular Congress

### **📝 Bill Type Summaries**
- **Resource**: `congress://summaries/{congress}/{bill_type}`
- **Description**: Get summaries for specific bill types in a Congress
- **Example**: `congress://summaries/118/hr` (House bills in 118th Congress)
- **Use Case**: Focus on specific types of legislation

## **Available Tools**

### **🔍 Search Summaries**
- **Tool**: `search_summaries`
- **Parameters**: keywords, congress (optional), bill_type (optional), limit, sort, from_date, to_date
- **Example**: Search for "climate change" summaries in 118th Congress
- **Use Case**: Find summaries by topic or keyword

### **📄 Specific Bill Summaries**
- **Tool**: `get_bill_summaries`  
- **Parameters**: congress, bill_type, bill_number
- **Example**: Get summaries for HR 1 in 118th Congress
- **Use Case**: Get all summaries for a specific bill

## **Valid Bill Types**
- **hr** - House Bill
- **s** - Senate Bill  
- **hjres** - House Joint Resolution
- **sjres** - Senate Joint Resolution
- **hconres** - House Concurrent Resolution
- **sconres** - Senate Concurrent Resolution
- **hres** - House Resolution
- **sres** - Senate Resolution

## **Congress Number Ranges**
- **Valid Range**: 1-119 (1st Congress to current)
- **Current Congress**: 119th (2025-2027)
- **Recent Congresses**: 118th (2023-2025), 117th (2021-2023), 116th (2019-2021)

## **Date Format**
- **Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- **Example**: `2024-01-01T00:00:00Z`

## **Limits**
- **Search Results**: 1-250 (default: 10)
- **API Rate Limits**: Managed automatically with retry logic

## **Examples**

### **Find Climate Legislation**
```
Tool: search_summaries
Keywords: "climate change"
Congress: 118
Bill Type: hr
Limit: 20
```

### **Get Infrastructure Bill Summaries**
```
Tool: get_bill_summaries
Congress: 117
Bill Type: hr
Bill Number: 3684
```

### **Latest Senate Resolutions**
```
Resource: congress://summaries/118/sres
```

## **Tips for Best Results**
- Use specific keywords for better search results
- Combine congress and bill_type filters to narrow results
- Check multiple Congresses for comprehensive research
- Use date ranges to focus on specific time periods
"""

@mcp.resource("congress://summaries/api-info")
async def get_summaries_api_info(ctx: Context) -> str:
    """
    Get technical information about the summaries API including limits and capabilities.
    
    Returns information about API endpoints, rate limits, response formats,
    and technical specifications for developers.
    """
    return """# 🔧 **Summaries API - Technical Information**

## **API Endpoints**

### **Base Endpoint**
- **URL**: `/summaries`
- **Method**: GET
- **Authentication**: Managed automatically

### **Endpoint Variations**
- `/summaries` - All summaries with pagination
- `/summaries/{congress}` - Congress-specific summaries  
- `/summaries/{congress}/{bill_type}` - Bill type specific summaries

## **Rate Limits & Performance**

### **Request Limits**
- **Timeout**: 10 seconds per request
- **Retries**: 2 automatic retries on failure
- **Retry Delay**: 1 second between retries
- **Max Results**: 250 per request

### **Response Processing**
- **Deduplication**: Automatic removal of duplicate summaries
- **Sorting**: By update date (newest first)
- **Filtering**: Client-side keyword filtering for search

## **Response Format**

### **Successful Response Structure**
```json
{
  "summaries": [
    {
      "congress": 118,
      "bill": {
        "type": "hr",
        "number": 1234,
        "title": "Bill Title"
      },
      "summaryText": "Summary content...",
      "actionDate": "2024-01-15",
      "updateDate": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "count": 25,
    "next": "next_page_url"
  }
}
```

### **Error Response Structure**
```json
{
  "error": "Error message",
  "details": "Detailed error information",
  "suggestions": ["Helpful suggestion 1", "Helpful suggestion 2"]
}
```

## **Parameter Validation**

### **Congress Numbers**
- **Range**: 1-119
- **Type**: Integer
- **Validation**: Automatic range checking

### **Bill Types**
- **Valid Values**: hr, s, hjres, sjres, hconres, sconres, hres, sres
- **Case**: Insensitive (automatically converted to lowercase)
- **Validation**: Automatic format checking

### **Bill Numbers**
- **Range**: 1-99999
- **Type**: Positive integer
- **Validation**: Automatic range and type checking

### **Dates**
- **Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- **Timezone**: UTC (Z suffix required)
- **Validation**: Automatic format verification

## **Error Handling**

### **Common Error Types**
- **Invalid Parameters**: User-friendly messages with suggestions
- **API Timeouts**: Automatic retry with exponential backoff
- **Server Errors**: Graceful degradation with helpful error messages
- **Rate Limiting**: Automatic handling with retry logic

### **Defensive Programming**
- **Timeout Protection**: Prevents hanging requests
- **Input Sanitization**: Automatic parameter cleaning
- **Response Validation**: Ensures data integrity
- **Comprehensive Logging**: Enhanced debugging capabilities

## **Data Quality Features**

### **Deduplication Logic**
- **Key Fields**: Congress + Bill Type + Bill Number + Action Date
- **Algorithm**: Hash-based duplicate detection
- **Result**: Clean, unique summaries only

### **Sorting & Filtering**
- **Default Sort**: Update date (newest first)
- **Search Filtering**: Title, text, and action description
- **Case Insensitive**: All text searches ignore case
- **Partial Matching**: Supports substring matching

## **Integration Notes**

### **MCP Architecture**
- **Resources**: Static/hierarchical data (no parameters)
- **Tools**: Dynamic operations (require parameters)
- **Consistency**: Follows Congressional MCP patterns

### **Reliability Framework**
- **Defensive API Wrapper**: Timeout and retry protection
- **Parameter Validation**: Comprehensive input checking
- **Error Standardization**: Consistent error response format
- **Response Processing**: Automatic cleaning and deduplication
"""

# Tools
# @require_paid_access
async def search_summaries(
    ctx: Context,
    keywords: str, 
    congress: Optional[int] = None, 
    bill_type: Optional[str] = None,
    limit: int = 10,
    sort: str = "updateDate+desc",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """
    Search for bill summaries based on keywords.
    
    Args:
        keywords: Keywords to search for in bill summaries
        congress: Optional Congress number (e.g., 117 for 117th Congress)
        bill_type: Optional bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        limit: Maximum number of results to return (default: 10)
        sort: Sort order (default: "updateDate+desc")
        from_date: Optional start date for filtering (format: YYYY-MM-DDT00:00:00Z)
        to_date: Optional end date for filtering (format: YYYY-MM-DDT00:00:00Z)
    """
    logger.info(f"Searching for summaries with keywords: {keywords}")
    
    try:
        # Parameter validation
        if not keywords or not keywords.strip():
            return format_error_response(
                CommonErrors.invalid_parameter("keywords", keywords, "Keywords cannot be empty", ["climate change", "healthcare", "defense"])
            )
        
        # Validate limit
        limit_validation = ParameterValidator.validate_limit_range(limit, 250)
        if not limit_validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("limit", str(limit), limit_validation.error_message, limit_validation.suggestions)
            )
        
        # Validate congress if provided
        if congress is not None:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                return format_error_response(
                    CommonErrors.invalid_parameter("congress", str(congress), congress_validation.error_message, congress_validation.suggestions)
                )
        
        # Validate bill type if provided
        if bill_type is not None:
            bill_validation = ParameterValidator.validate_bill_type(bill_type)
            if not bill_validation.is_valid:
                return format_error_response(
                    CommonErrors.invalid_parameter("bill_type", bill_type, bill_validation.error_message, bill_validation.suggestions)
                )
        
        # Validate date formats if provided
        if from_date is not None:
            date_validation = ParameterValidator.validate_date_format(from_date)
            if not date_validation.is_valid:
                return format_error_response(
                    CommonErrors.invalid_parameter("from_date", from_date, date_validation.error_message, date_validation.suggestions)
                )
        
        if to_date is not None:
            date_validation = ParameterValidator.validate_date_format(to_date)
            if not date_validation.is_valid:
                return format_error_response(
                    CommonErrors.invalid_parameter("to_date", to_date, date_validation.error_message, date_validation.suggestions)
                )
        
        # Build API request parameters
        params = {
            # Increase the limit to get more results for filtering
            "limit": min(100, limit * 5),  # Get more results but cap at 100
            "sort": sort
        }
        
        # Add optional date filters if provided
        if from_date:
            params["fromDateTime"] = from_date
        if to_date:
            params["toDateTime"] = to_date
        
        # Build endpoint
        endpoint = "/summaries"
        if congress is not None:
            endpoint = f"/summaries/{congress}"
            if bill_type is not None:
                endpoint = f"/summaries/{congress}/{bill_type}"
        
        # Use defensive API wrapper
        data = await safe_summaries_request(endpoint, ctx, params)
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return format_error_response(
                CommonErrors.api_server_error(endpoint, data["error"])
            )
        
        # Process response with deduplication and cleaning
        summaries = clean_summaries_response(data, limit=100)  # Get more for filtering
        
        if not summaries:
            return f"No summaries found for the specified criteria."
        
        # Client-side filtering based on keywords using processor
        filtered_summaries = SummariesProcessor.filter_by_keywords(summaries, keywords)
        
        # Limit the results to the requested number
        filtered_summaries = filtered_summaries[:limit]
        
        if not filtered_summaries:
            return f"No summaries found matching '{keywords}'."
        
        logger.info(f"Found {len(filtered_summaries)} summaries matching '{keywords}'")
        return format_summaries_list(filtered_summaries, f"Bill Summaries Matching '{keywords}'")
        
    except Exception as e:
        logger.error(f"Error searching summaries with keywords '{keywords}': {str(e)}")
        return format_error_response(
            CommonErrors.api_server_error("/summaries", str(e))
        )


# @require_paid_access
async def get_bill_summaries(
    ctx: Context,
    congress: int,
    bill_type: str,
    bill_number: int
) -> str:
    """
    Get summaries for a specific bill.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        bill_type: Bill type (e.g., 'hr' for House Bill, 's' for Senate Bill)
        bill_number: Bill number
    """
    logger.info(f"Getting summaries for {bill_type.upper()} {bill_number} in Congress {congress}")
    
    try:
        # Parameter validation
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("congress", str(congress), congress_validation.error_message, congress_validation.suggestions)
            )
        
        bill_validation = ParameterValidator.validate_bill_type(bill_type)
        if not bill_validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("bill_type", bill_type, bill_validation.error_message, bill_validation.suggestions)
            )
        
        number_validation = ParameterValidator.validate_bill_number(bill_number)
        if not number_validation.is_valid:
            return format_error_response(
                CommonErrors.invalid_parameter("bill_number", str(bill_number), number_validation.error_message, number_validation.suggestions)
            )
        
        # Use the existing bill summaries endpoint with defensive wrapper
        endpoint = f"/bill/{congress}/{bill_type}/{bill_number}/summaries"
        data = await safe_summaries_request(endpoint, ctx, {})
        
        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return format_error_response(
                CommonErrors.api_server_error(endpoint, data["error"])
            )
        
        # Handle different data structures for summaries
        summaries_data = data.get("summaries", {})
        
        # Extract summary items based on the data structure
        if isinstance(summaries_data, list):
            summaries = summaries_data
        elif isinstance(summaries_data, dict) and "item" in summaries_data:
            items = summaries_data["item"]
            if isinstance(items, list):
                summaries = items
            else:
                # If there's only one item, wrap it in a list
                summaries = [items]
        else:
            # If we can't determine the structure, just use an empty list
            logger.warning(f"Unexpected summaries structure: {type(summaries_data)}")
            summaries = []
        
        if not summaries:
            return f"No summaries found for {bill_type.upper()} {bill_number} in the {congress}th Congress."
        
        # Deduplicate summaries
        summaries = SummariesProcessor.deduplicate_summaries(summaries)
        
        result = [f"# Summaries for {bill_type.upper()} {bill_number} - {congress}th Congress"]
        result.append(f"**Found {len(summaries)} summaries**\n")
        
        for i, summary in enumerate(summaries, 1):
            result.append(f"## {i}. Summary Version")
            
            # Get version code and date
            version_code = summary.get("versionCode", "Unknown")
            version_date = summary.get("updateDate", "Unknown date")
            
            result.append(f"**Version:** {version_code}")
            result.append(f"**Date:** {version_date}")
            
            # Get summary text
            if "text" in summary:
                result.append("\n### Content")
                result.append(summary["text"])
            
            result.append("")  # Add spacing between summaries
        
        logger.info(f"Returning {len(summaries)} summaries for {bill_type.upper()} {bill_number}")
        return "\n".join(result)
        
    except Exception as e:
        logger.error(f"Error getting summaries for {bill_type.upper()} {bill_number} in Congress {congress}: {str(e)}")
        return format_error_response(
            CommonErrors.api_server_error(f"/bill/{congress}/{bill_type}/{bill_number}/summaries", str(e))
        )
