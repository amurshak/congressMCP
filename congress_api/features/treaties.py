# congress_api/features/treaties.py
import logging
from typing import Dict, List, Any, Optional
from mcp.server.fastmcp import Context
from ..mcp_app import mcp
from ..core.client_handler import make_api_request
from ..core.api_wrapper import safe_treaties_request
from ..core.validators import ParameterValidator
from ..core.exceptions import CommonErrors, format_error_response
from ..core.response_utils import TreatiesProcessor, clean_treaties_response
from ..core.auth.auth import require_paid_access

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# --- Formatting Helpers ---

def format_treaty_item(item: Dict[str, Any]) -> str:
    """Formats a single treaty item for display in a list."""
    lines = [
        f"Congress Received: {item.get('congressReceived', 'N/A')}",
        f"Congress Considered: {item.get('congressConsidered', 'N/A')}",
        f"Treaty Number: {item.get('number', 'N/A')}"
    ]
    
    # Add suffix if available
    if 'suffix' in item and item['suffix']:
        lines.append(f"Suffix: {item.get('suffix', 'N/A')}")
    
    # Add topic if available
    if 'topic' in item:
        lines.append(f"Topic: {item.get('topic', 'N/A')}")
    
    # Add transmitted date if available
    if 'transmittedDate' in item:
        lines.append(f"Transmitted Date: {item.get('transmittedDate', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in item:
        lines.append(f"Update Date: {item.get('updateDate', 'N/A')}")
    
    # Add URL if available
    if 'url' in item:
        lines.append(f"URL: {item.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_treaty_detail(treaty_data: Dict[str, Any]) -> str:
    """Formats detailed information for a treaty."""
    if not treaty_data:
        return "No treaty data available."
    
    # Basic information
    result = []
    result.append(f"Congress Received: {treaty_data.get('congressReceived', 'N/A')}")
    result.append(f"Congress Considered: {treaty_data.get('congressConsidered', 'None')}")
    result.append(f"Treaty Number: {treaty_data.get('number', 'N/A')}")
    
    suffix = treaty_data.get('suffix', '')
    if suffix:
        result.append(f"Treaty Suffix: {suffix}")
    
    result.append(f"Topic: {treaty_data.get('topic', 'N/A')}")
    
    transmitted_date = treaty_data.get('transmittedDate')
    if transmitted_date:
        result.append(f"Transmitted Date: {transmitted_date}")
    
    in_force_date = treaty_data.get('inForceDate')
    if in_force_date:
        result.append(f"In Force Date: {in_force_date}")
    
    result.append(f"Update Date: {treaty_data.get('updateDate', 'N/A')}")
    
    # Titles
    titles = treaty_data.get('titles', [])
    if titles:
        result.append("\nTitles:")
        for title in titles:
            title_type = title.get('titleType', 'Unknown')
            title_text = title.get('title', 'No title')
            result.append(f"  - {title_type}: {title_text}")
    
    # Index terms
    index_terms = treaty_data.get('indexTerms', [])
    if index_terms:
        terms = [term.get('name', '') for term in index_terms if term.get('name')]
        if terms:
            result.append(f"\nIndex Terms: {', '.join(terms)}")
    
    # Resolution text availability
    resolution_text = treaty_data.get('resolutionText')
    if resolution_text and resolution_text.strip():
        result.append(f"\nResolution Text: Available ({len(resolution_text)} characters)")
        result.append("Use get_treaty_text tool to view full resolution text")
    else:
        result.append("\nResolution Text: Not available (treaty may still be under review)")
    
    # Related documents
    related_docs = treaty_data.get('relatedDocs', [])
    if related_docs:
        result.append(f"\nRelated Documents: {len(related_docs)} documents available")
        for i, doc in enumerate(related_docs[:3], 1):  # Show first 3
            doc_title = doc.get('title', f'Document {i}')
            result.append(f"  - {doc_title}")
        if len(related_docs) > 3:
            result.append(f"  ... and {len(related_docs) - 3} more")
    else:
        result.append("\nRelated Documents: None")
    
    # Treaty parts
    parts = treaty_data.get('parts', {})
    if parts and isinstance(parts, dict) and parts:
        result.append(f"\nTreaty Parts: Available")
        # Show part structure if available
        if 'count' in parts:
            result.append(f"  - Part count: {parts['count']}")
    else:
        result.append("\nTreaty Parts: None")
    
    # Actions and committees (existing)
    actions = treaty_data.get('actions', {})
    if actions and actions.get('count'):
        result.append(f"\nActions: {actions['count']}")
        if actions.get('url'):
            result.append(f"Actions URL: {actions['url']}")
    
    return '\n'.join(result)

def format_treaty_actions(actions_data: Dict[str, Any]) -> str:
    """Formats actions for a treaty."""
    if not actions_data or 'actions' not in actions_data or not actions_data['actions']:
        return "No actions available for this treaty."
    
    actions = actions_data['actions']
    lines = ["Treaty Actions:"]
    
    for action in actions:
        lines.append("")
        lines.append(f"Date: {action.get('actionDate', 'N/A')}")
        lines.append(f"Type: {action.get('type', 'N/A')}")
        lines.append(f"Text: {action.get('text', 'N/A')}")
        
        # Add committee if available
        if action.get('committee'):
            lines.append(f"Committee: {action.get('committee', 'N/A')}")
        
        # Add action code if available
        if 'actionCode' in action:
            lines.append(f"Action Code: {action.get('actionCode', 'N/A')}")
    
    return "\n".join(lines)

def format_treaty_committees(committees_data: Dict[str, Any]) -> str:
    """Formats committees for a treaty."""
    if not committees_data or 'treatyCommittees' not in committees_data or not committees_data['treatyCommittees']:
        return "No committees available for this treaty."
    
    committees = committees_data['treatyCommittees']
    lines = ["Treaty Committees:"]
    
    for committee in committees:
        lines.append("")
        lines.append(f"Name: {committee.get('name', 'N/A')}")
        lines.append(f"Chamber: {committee.get('chamber', 'N/A')}")
        lines.append(f"Type: {committee.get('type', 'N/A')}")
        lines.append(f"System Code: {committee.get('systemCode', 'N/A')}")
        
        # Add activities if available
        if 'activities' in committee and committee['activities']:
            lines.append("Activities:")
            for activity in committee['activities']:
                lines.append(f"  - {activity.get('name', 'N/A')} ({activity.get('date', 'N/A')})")
        
        # Add URL if available
        if 'url' in committee:
            lines.append(f"URL: {committee.get('url', 'N/A')}")
    
    return "\n".join(lines)

def format_treaties_list(data: Dict[str, Any]) -> str:
    """Formats a list of treaties."""
    if not data or 'treaties' not in data or not data['treaties']:
        return "No treaties available."
    
    treaties = data['treaties']
    formatted_treaties = []
    
    for treaty in treaties:
        formatted_treaties.append(format_treaty_item(treaty))
    
    return "\n\n".join(formatted_treaties)

# --- MCP Resources ---

@mcp.resource("congress://treaties/latest")
# @require_paid_access
async def get_latest_treaties(ctx: Context) -> str:
    """
    Get the most recent treaties.
    Returns the 10 most recently published treaties by default.
    """
    logger.debug("Getting latest treaties")
    
    try:
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': 10
        }
        
        # Make the defensive API request
        data = await safe_treaties_request(
            endpoint="/treaty",
            ctx=ctx,
            params=params
        )
        
        # Process and clean the response
        if isinstance(data, dict) and 'treaties' in data:
            treaties = clean_treaties_response(data, limit=10)
            if treaties:
                logger.debug(f"Successfully retrieved {len(treaties)} latest treaties")
                return format_treaties_list({'treaties': treaties})
            else:
                logger.warning("No treaties found in latest treaties response")
                return "No recent treaties found."
        else:
            logger.warning(f"Unexpected response format for latest treaties: {type(data)}")
            return "No treaties data available in the expected format."
            
    except Exception as e:
        logger.error(f"Error getting latest treaties: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint="/treaty",
            message=f"Failed to retrieve latest treaties: {str(e)}"
        )
        return format_error_response(error_response)

@mcp.resource("congress://treaties/{congress}")
# @require_paid_access
async def get_treaties_by_congress(ctx: Context, congress: int) -> str:
    """
    Get treaties for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    logger.debug(f"Getting treaties for Congress: {congress}")
    
    try:
        # Validate congress parameter
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            error_response = CommonErrors.invalid_parameter(
                parameter="congress",
                value=congress,
                message=congress_validation.error_message,
                suggestions=congress_validation.suggestions
            )
            return format_error_response(error_response)
        
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': 20
        }
        
        # Make the defensive API request
        data = await safe_treaties_request(
            endpoint=f"/treaty/{congress}",
            ctx=ctx,
            params=params
        )
        
        # Process and clean the response
        if isinstance(data, dict) and 'treaties' in data:
            treaties = clean_treaties_response(data, limit=20)
            if treaties:
                logger.debug(f"Successfully retrieved {len(treaties)} treaties for Congress {congress}")
                return format_treaties_list({'treaties': treaties})
            else:
                logger.warning(f"No treaties found for Congress {congress}")
                return f"No treaties found for Congress {congress}."
        else:
            logger.warning(f"Unexpected response format for Congress {congress} treaties: {type(data)}")
            return f"No treaties data available for Congress {congress} in the expected format."
            
    except Exception as e:
        logger.error(f"Error getting treaties for Congress {congress}: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint=f"/treaty/{congress}",
            message=f"Failed to retrieve treaties for Congress {congress}: {str(e)}"
        )
        return format_error_response(error_response)

@mcp.resource("congress://treaties/{congress}/{treaty_number}")
# @require_paid_access
async def get_treaty_detail(ctx: Context, congress: int, treaty_number: int) -> str:
    """Get detailed information about a specific treaty"""
    try:
        # Validate parameters
        ParameterValidator.validate_congress_number(congress)
        ParameterValidator.validate_treaty_number(treaty_number)
        
        # Make API request
        endpoint = f"/treaty/{congress}/{treaty_number}"
        params = {'format': 'json'}
        response = await safe_treaties_request(endpoint, ctx, params)
        
        if not response or 'treaty' not in response:
            error_response = CommonErrors.not_found(
                resource_type="treaty",
                identifier=f"{congress}/{treaty_number}",
                suggestions=[
                    "Verify the congress number and treaty number are correct",
                    f"Try searching for treaties in Congress {congress} first",
                    "Check if the treaty exists using the search_treaties tool"
                ]
            )
            return format_error_response(error_response)
        
        # Extract treaty data and format
        treaty_data = response['treaty']
        return format_treaty_detail(treaty_data)
        
    except Exception as e:
        logger.error(f"Error getting treaty detail for {congress}/{treaty_number}: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint=f"/treaty/{congress}/{treaty_number}",
            message=f"Failed to retrieve treaty details: {str(e)}"
        )
        return format_error_response(error_response)

@mcp.resource("congress://treaties/{congress}/{treaty_number}/{treaty_suffix}")
# @require_paid_access
async def get_treaty_detail_with_suffix(ctx: Context, congress: int, treaty_number: int, treaty_suffix: str) -> str:
    """Get detailed information about a specific partitioned treaty with suffix"""
    try:
        # Validate parameters
        ParameterValidator.validate_congress_number(congress)
        ParameterValidator.validate_treaty_number(treaty_number)
        treaty_suffix = ParameterValidator.validate_treaty_suffix(treaty_suffix)
        
        # Make API request
        endpoint = f"/treaty/{congress}/{treaty_number}/{treaty_suffix}"
        params = {'format': 'json'}
        response = await safe_treaties_request(endpoint, ctx, params)
        
        if not response or 'treaty' not in response:
            error_response = CommonErrors.not_found(
                resource_type="treaty",
                identifier=f"{congress}/{treaty_number}/{treaty_suffix}",
                suggestions=[
                    "Verify the congress number, treaty number, and suffix are correct",
                    f"Try checking if Treaty {congress}-{treaty_number} exists without suffix first",
                    "Verify the suffix format (single uppercase letter like 'A', 'B')"
                ]
            )
            return format_error_response(error_response)
        
        # Extract treaty data and format
        treaty_data = response['treaty']
        return format_treaty_detail(treaty_data)
        
    except Exception as e:
        logger.error(f"Error getting treaty detail for {congress}/{treaty_number}/{treaty_suffix}: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint=f"/treaty/{congress}/{treaty_number}/{treaty_suffix}",
            message=f"Failed to retrieve treaty details: {str(e)}"
        )
        return format_error_response(error_response)

# --- MCP Tools ---

# @require_paid_access
async def get_treaty_actions(
    ctx: Context,
    congress: int,
    treaty_number: int,
    treaty_suffix: Optional[str] = None
) -> str:
    """
    Get actions for a specific treaty.
    
    Args:
        congress: The Congress number (e.g., 117).
        treaty_number: The treaty number (e.g., 3).
        treaty_suffix: Optional treaty suffix for partitioned treaties (e.g., 'A').
    """
    logger.debug(f"Getting treaty actions for Congress: {congress}, Treaty Number: {treaty_number}, Suffix: {treaty_suffix}")
    
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            error_response = CommonErrors.invalid_parameter(
                parameter="congress",
                value=congress,
                message=congress_validation.error_message,
                suggestions=congress_validation.suggestions
            )
            return format_error_response(error_response)
        
        treaty_validation = ParameterValidator.validate_treaty_number(treaty_number)
        if not treaty_validation.is_valid:
            error_response = CommonErrors.invalid_parameter(
                parameter="treaty_number",
                value=treaty_number,
                message=treaty_validation.error_message,
                suggestions=treaty_validation.suggestions
            )
            return format_error_response(error_response)
        
        # Validate treaty suffix if provided
        clean_suffix = None
        if treaty_suffix:
            suffix_validation = ParameterValidator.validate_treaty_suffix(treaty_suffix)
            if not suffix_validation.is_valid:
                error_response = CommonErrors.invalid_parameter(
                    parameter="treaty_suffix",
                    value=treaty_suffix,
                    message=suffix_validation.error_message,
                    suggestions=suffix_validation.suggestions
                )
                return format_error_response(error_response)
            clean_suffix = suffix_validation.sanitized_value
        
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': 50
        }
        
        # Determine the endpoint based on whether a suffix is provided
        if clean_suffix:
            endpoint = f"/treaty/{congress}/{treaty_number}/{clean_suffix}/actions"
        else:
            endpoint = f"/treaty/{congress}/{treaty_number}/actions"
        
        # Make the defensive API request
        data = await safe_treaties_request(
            endpoint=endpoint,
            ctx=ctx,
            params=params
        )
        
        # Process the response
        if isinstance(data, dict):
            logger.debug(f"Successfully retrieved treaty actions for Congress {congress}, Treaty {treaty_number}")
            return format_treaty_actions(data)
        else:
            logger.warning(f"Unexpected response format for treaty actions: {type(data)}")
            return f"No treaty actions data available for Congress {congress}, Treaty {treaty_number}."
            
    except Exception as e:
        logger.error(f"Error getting treaty actions for Congress {congress}, Treaty {treaty_number}: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint=endpoint,
            message=f"Failed to retrieve treaty actions: {str(e)}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def get_treaty_committees(
    ctx: Context,
    congress: int,
    treaty_number: int
) -> str:
    """
    Get committees for a specific treaty.
    
    Args:
        congress: The Congress number (e.g., 116).
        treaty_number: The treaty number (e.g., 3).
    """

    logger.debug(f"Getting treaty committees for Congress: {congress}, Treaty Number: {treaty_number}")
    
    try:
        # Validate parameters
        congress_validation = ParameterValidator.validate_congress_number(congress)
        if not congress_validation.is_valid:
            error_response = CommonErrors.invalid_parameter(
                parameter="congress",
                value=congress,
                message=congress_validation.error_message,
                suggestions=congress_validation.suggestions
            )
            return format_error_response(error_response)
        
        treaty_validation = ParameterValidator.validate_treaty_number(treaty_number)
        if not treaty_validation.is_valid:
            error_response = CommonErrors.invalid_parameter(
                parameter="treaty_number",
                value=treaty_number,
                message=treaty_validation.error_message,
                suggestions=treaty_validation.suggestions
            )
            return format_error_response(error_response)
        
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': 50
        }
        
        # Make the API request
        data = await make_api_request(
            endpoint=f"/treaty/{congress}/{treaty_number}/committees",
            params=params,
            ctx=ctx
        )
        
        # Check if there was an error in the response
        if isinstance(data, dict) and 'error' in data:
            return f"Error retrieving treaty committees: {data['error']}"
        
        # Format the response
        return format_treaty_committees(data)
    
    except Exception as e:
        logger.error(f"Error getting treaty committees for Congress {congress}, Treaty {treaty_number}: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint=f"/treaty/{congress}/{treaty_number}/committees",
            message=f"Failed to retrieve treaty committees: {str(e)}"
        )
        return format_error_response(error_response)

# @require_paid_access
async def get_treaty_text(
    ctx: Context,
    congress: int,
    treaty_number: int,
    treaty_suffix: str = None
) -> str:
    """
    Get the full text/resolution for a specific treaty.
    
    Args:
        congress: Congress number (e.g., 117 for 117th Congress)
        treaty_number: Treaty number (e.g., 1, 3, 15)
        treaty_suffix: Optional treaty suffix for partitioned treaties (e.g., 'A', 'B')
    
    Returns:
        Full treaty resolution text, related documents, and parts information
    """
    try:
        # Validate parameters
        ParameterValidator.validate_congress_number(congress)
        ParameterValidator.validate_treaty_number(treaty_number)
        
        if treaty_suffix:
            treaty_suffix = ParameterValidator.validate_treaty_suffix(treaty_suffix)
        
        # Build endpoint and parameters
        if treaty_suffix:
            endpoint = f"/treaty/{congress}/{treaty_number}/{treaty_suffix}"
        else:
            endpoint = f"/treaty/{congress}/{treaty_number}"
        
        params = {'format': 'json'}
        
        # Make API request
        response = await safe_treaties_request(endpoint, ctx, params)
        
        if not response or 'treaty' not in response:
            return CommonErrors.not_found(
                resource_type="treaty text",
                identifier=f"{congress}/{treaty_number}" + (f"/{treaty_suffix}" if treaty_suffix else ""),
                suggestions=[
                    "Verify the congress number and treaty number are correct",
                    "Check if the treaty has been processed and has available text",
                    "Some treaties may not have text available if still under review"
                ]
            )
        
        treaty_data = response['treaty']
        
        # Format treaty text response
        result = []
        
        # Basic treaty info
        treaty_id = f"Treaty {congress}-{treaty_number}"
        if treaty_suffix:
            treaty_id += f"-{treaty_suffix}"
        
        result.append(f"# {treaty_id}")
        result.append("=" * (len(treaty_id) + 2))
        
        # Title
        titles = treaty_data.get('titles', [])
        if titles:
            formal_title = next((t['title'] for t in titles if 'formal' in t.get('titleType', '').lower()), None)
            short_title = next((t['title'] for t in titles if 'short' in t.get('titleType', '').lower()), None)
            
            if formal_title:
                result.append(f"\n**Formal Title:** {formal_title}")
            if short_title and short_title != formal_title:
                result.append(f"**Short Title:** {short_title}")
        
        # Basic details
        result.append(f"\n**Congress:** {treaty_data.get('congressReceived', 'N/A')}")
        result.append(f"**Topic:** {treaty_data.get('topic', 'N/A')}")
        
        transmitted_date = treaty_data.get('transmittedDate')
        if transmitted_date:
            result.append(f"**Transmitted:** {transmitted_date}")
        
        # Resolution text (main content)
        resolution_text = treaty_data.get('resolutionText')
        if resolution_text and resolution_text.strip():
            result.append("\n## Resolution Text")
            result.append("-" * 15)
            
            # Clean up HTML tags for better readability
            import re
            clean_text = re.sub(r'<br\s*/?>', '\n', resolution_text)
            clean_text = re.sub(r'<p[^>]*>', '\n', clean_text)
            clean_text = re.sub(r'</p>', '', clean_text)
            clean_text = re.sub(r'<[^>]+>', '', clean_text)  # Remove remaining HTML tags
            clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)  # Clean up extra whitespace
            
            result.append(clean_text.strip())
        else:
            result.append("\n## Resolution Text")
            result.append("-" * 15)
            result.append("**No resolution text available.**")
            result.append("\nThis treaty may still be under committee review or awaiting Senate action.")
            result.append("Resolution text typically becomes available after Senate consideration.")
        
        # Related documents
        related_docs = treaty_data.get('relatedDocs', [])
        if related_docs:
            result.append("\n## Related Documents")
            result.append("-" * 18)
            for i, doc in enumerate(related_docs, 1):
                doc_title = doc.get('title', f'Document {i}')
                doc_url = doc.get('url', 'No URL available')
                result.append(f"{i}. **{doc_title}**")
                if doc_url != 'No URL available':
                    result.append(f"   URL: {doc_url}")
        
        # Treaty parts
        parts = treaty_data.get('parts', {})
        if parts and isinstance(parts, dict) and parts:
            result.append("\n## Treaty Parts")
            result.append("-" * 13)
            
            if 'count' in parts:
                result.append(f"**Part Count:** {parts['count']}")
            
            # If parts have detailed structure, show it
            for key, value in parts.items():
                if key != 'count' and value:
                    result.append(f"**{key.title()}:** {value}")
        
        # Index terms
        index_terms = treaty_data.get('indexTerms', [])
        if index_terms:
            terms = [term.get('name', '') for term in index_terms if term.get('name')]
            if terms:
                result.append("\n## Index Terms")
                result.append("-" * 12)
                result.append(', '.join(terms))
        
        # Additional info
        result.append(f"\n## Additional Information")
        result.append("-" * 22)
        result.append(f"**Last Updated:** {treaty_data.get('updateDate', 'N/A')}")
        
        actions = treaty_data.get('actions', {})
        if actions and actions.get('count'):
            result.append(f"**Actions Available:** {actions['count']} (use get_treaty_actions tool)")
        
        if treaty_data.get('inForceDate'):
            result.append(f"**In Force Date:** {treaty_data['inForceDate']}")
        
        return '\n'.join(result)
        
    except Exception as e:
        logger.error(f"Error getting treaty text for {congress}/{treaty_number}: {str(e)}")
        return CommonErrors.api_server_error(
            endpoint=f"/treaty/{congress}/{treaty_number}",
            message=f"Failed to retrieve treaty text: {str(e)}"
        )

# @require_paid_access
async def search_treaties(
    ctx: Context,
    congress: Optional[int] = None,
    topic: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 10
) -> str:
    """
    Search for treaties based on various criteria.
    
    Args:
        congress: Optional Congress number (e.g., 117).
        topic: Optional topic to filter by (e.g., "Maritime Boundaries").
        from_date: Optional start date for filtering by update date (format: YYYY-MM-DDT00:00:00Z).
        to_date: Optional end date for filtering by update date (format: YYYY-MM-DDT00:00:00Z).
        limit: Maximum number of results to return (default: 10).
    """

    logger.debug(f"Searching for treaties with congress: {congress}, topic: {topic}, from_date: {from_date}, to_date: {to_date}, limit: {limit}")
    
    try:
        # Validate parameters
        if congress:
            congress_validation = ParameterValidator.validate_congress_number(congress)
            if not congress_validation.is_valid:
                error_response = CommonErrors.invalid_parameter(
                    parameter="congress",
                    value=congress,
                    message=congress_validation.error_message,
                    suggestions=congress_validation.suggestions
                )
                return format_error_response(error_response)
        
        # Set up parameters for the API request
        params = {
            'format': 'json',
            'limit': limit
        }
        
        # Add optional parameters if provided
        if from_date:
            params['fromDateTime'] = from_date
        
        if to_date:
            params['toDateTime'] = to_date
        
        # Determine the endpoint based on whether a congress is provided
        endpoint = "/treaty"
        if congress:
            endpoint = f"/treaty/{congress}"
        
        # Make the API request
        data = await make_api_request(
            endpoint=endpoint,
            params=params,
            ctx=ctx
        )
        
        # Check if there was an error in the response
        if isinstance(data, dict) and 'error' in data:
            return f"Error searching for treaties: {data['error']}"
        
        # If topic is provided, filter the results client-side
        if topic and 'treaties' in data and data['treaties']:
            filtered_treaties = []
            topic_words = [word.lower() for word in topic.split()]
            
            for treaty in data['treaties']:
                # Get the topic and title fields for searching
                treaty_topic = treaty.get('topic', '').lower()
                
                # Get titles if available
                treaty_titles = []
                if 'titles' in treaty and treaty['titles']:
                    for title_obj in treaty['titles']:
                        if 'title' in title_obj:
                            treaty_titles.append(title_obj['title'].lower())
                
                # Check if any word in the search topic matches the treaty topic
                match_found = False
                
                # Check in topic field
                for word in topic_words:
                    if word in treaty_topic:
                        match_found = True
                        break
                
                # If no match in topic, check in titles
                if not match_found and treaty_titles:
                    for title in treaty_titles:
                        for word in topic_words:
                            if word in title:
                                match_found = True
                                break
                        if match_found:
                            break
                
                if match_found:
                    filtered_treaties.append(treaty)
            
            # Replace the original treaties with the filtered ones
            if filtered_treaties:
                data['treaties'] = filtered_treaties
            else:
                return f"No treaties found matching topic: {topic}"
        
        # Format the response
        return format_treaties_list(data)
    
    except Exception as e:
        logger.error(f"Error searching for treaties: {str(e)}")
        error_response = CommonErrors.api_server_error(
            endpoint="/treaty",
            message=f"Failed to search treaties: {str(e)}"
        )
        return format_error_response(error_response)


# --- Helper Resources ---

@mcp.resource("congress://treaties/help")
# @require_paid_access
async def get_treaties_help(ctx: Context) -> str:
    """
    Get comprehensive help and usage guide for the Treaties API.
    """
    return """# Congressional Treaties API - Usage Guide

## 📋 Available Resources

### Latest Treaties
- **Resource**: `congress://treaties/latest`
- **Description**: Get the 10 most recent treaties
- **Example**: Access directly through MCP client

### Treaties by Congress
- **Resource**: `congress://treaties/{congress}`
- **Description**: Get all treaties for a specific Congress
- **Parameters**:
  - `congress`: Congress number (e.g., 117, 118)
- **Example**: `congress://treaties/117`

### Treaty Details
- **Resource**: `congress://treaties/{congress}/{treaty_number}`
- **Description**: Get detailed information for a specific treaty
- **Parameters**:
  - `congress`: Congress number (e.g., 117)
  - `treaty_number`: Treaty number (e.g., 3)
- **Example**: `congress://treaties/117/3`

### Partitioned Treaty Details
- **Resource**: `congress://treaties/{congress}/{treaty_number}/{treaty_suffix}`
- **Description**: Get details for partitioned treaties with suffixes
- **Parameters**:
  - `congress`: Congress number (e.g., 114)
  - `treaty_number`: Treaty number (e.g., 13)
  - `treaty_suffix`: Treaty suffix (e.g., 'A', 'B')
- **Example**: `congress://treaties/114/13/A`

## 🔧 Available Tools

### Get Treaty Actions
- **Tool**: `get_treaty_actions`
- **Description**: Get actions for a specific treaty
- **Parameters**:
  - `congress`: Congress number (required)
  - `treaty_number`: Treaty number (required)
  - `treaty_suffix`: Treaty suffix (optional)
- **Example**: Get actions for Treaty 3 of the 117th Congress

### Get Treaty Committees
- **Tool**: `get_treaty_committees`
- **Description**: Get committees for a specific treaty
- **Parameters**:
  - `congress`: Congress number (required)
  - `treaty_number`: Treaty number (required)
- **Example**: Get committees for Treaty 3 of the 117th Congress

### Get Treaty Text
- **Tool**: `get_treaty_text`
- **Description**: Get the full text/resolution for a specific treaty
- **Parameters**:
  - `congress`: Congress number (required)
  - `treaty_number`: Treaty number (required)
  - `treaty_suffix`: Treaty suffix (optional)
- **Example**: Get full text for Treaty 3 of the 117th Congress

### Search Treaties
- **Tool**: `search_treaties`
- **Description**: Search for treaties based on various criteria
- **Parameters**:
  - `congress`: Congress number (optional)
  - `topic`: Topic to filter by (optional)
  - `from_date`: Start date for filtering by update date (optional, format: YYYY-MM-DDT00:00:00Z)
  - `to_date`: End date for filtering by update date (optional, format: YYYY-MM-DDT00:00:00Z)
  - `limit`: Maximum results (default: 10)
- **Example**: Search for treaties about "Maritime Boundaries"

## 📊 Parameter Formats

### Congress Numbers
- **Valid Range**: 93-119 (current)
- **Format**: Integer
- **Examples**: 117, 118, 119

### Treaty Numbers
- **Format**: Positive integer
- **Examples**: 1, 3, 15

### Treaty Suffixes
- **Format**: Single uppercase letter
- **Examples**: 'A', 'B', 'C'
- **Use Case**: For partitioned treaties

### Date Formats
- **Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- **Examples**: 
  - `2023-01-01T00:00:00Z`
  - `2023-12-31T23:59:59Z`

## 💡 Best Practices

### Efficient Searching
1. **Use Congress Filter**: Specify congress number to narrow results
2. **Topic Keywords**: Use specific terms for better matches
3. **Date Ranges**: Limit searches to relevant time periods
4. **Reasonable Limits**: Use appropriate limit values (10-50 for most cases)

### Error Handling
- All functions include comprehensive parameter validation
- Detailed error messages with suggestions for corrections
- Automatic retry logic for temporary API issues

### Data Quality
- Automatic deduplication of treaty results
- Consistent sorting by update date (newest first)
- Clean, formatted output for easy reading

## 🎯 Common Use Cases

### Recent Treaty Activity
```
Resource: congress://treaties/latest
```

### Treaties by Congress
```
Resource: congress://treaties/118
```

### Specific Treaty Details
```
Resource: congress://treaties/117/3
```

### Search by Topic
```
Tool: search_treaties
Parameters: {"topic": "Maritime Boundaries", "limit": 20}
```

### Treaty Actions and History
```
Tool: get_treaty_actions
Parameters: {"congress": 117, "treaty_number": 3}
```

### Treaty Full Text
```
Tool: get_treaty_text
Parameters: {"congress": 117, "treaty_number": 3}
```

## 📞 Support

For additional help or to report issues:
- Check parameter formats and valid ranges
- Review error messages for specific guidance
- Use the `congress://treaties/api-info` resource for technical details
"""

@mcp.resource("congress://treaties/api-info")
# @require_paid_access
async def get_treaties_api_info(ctx: Context) -> str:
    """
    Get technical API information for the Treaties API.
    """
    return """# Congressional Treaties API - Technical Information

## 🔌 API Endpoints

### Base Endpoint
- **URL**: `https://api.congress.gov/v3/treaty`
- **Authentication**: API key required
- **Format**: JSON

### Available Endpoints
1. **List Treaties**: `/treaty`
2. **Treaties by Congress**: `/treaty/{congress}`
3. **Treaty Details**: `/treaty/{congress}/{treaty_number}`
4. **Partitioned Treaty**: `/treaty/{congress}/{treaty_number}/{suffix}`
5. **Treaty Actions**: `/treaty/{congress}/{treaty_number}/actions`
6. **Treaty Committees**: `/treaty/{congress}/{treaty_number}/committees`

## ⚡ Performance & Limits

### Rate Limits
- **Requests per hour**: 5,000
- **Concurrent requests**: 10
- **Timeout**: 30 seconds per request

### Response Limits
- **Default limit**: 10 items
- **Maximum limit**: 250 items
- **Pagination**: Supported via offset parameter

### Caching
- **Resource cache**: 5 minutes
- **Tool cache**: 2 minutes
- **Error cache**: 30 seconds

## 📋 Response Format

### Treaty Object Structure
```json
{
  "congress": 117,
  "number": "3",
  "suffix": null,
  "topic": "Maritime Boundaries",
  "updateDate": "2023-01-15T10:30:00Z",
  "transmittedDate": "2023-01-01T00:00:00Z",
  "inForceDate": null,
  "resolutionText": "<p>Senate resolution text...</p>",
  "relatedDocs": [
    {
      "title": "Treaty Document 117-3",
      "url": "https://www.congress.gov/treaty-document/117th-congress/senate/3"
    }
  ],
  "parts": {
    "count": 2,
    "urls": ["..."]
  },
  "titles": [
    {
      "title": "Treaty Title",
      "titleType": "Official Title"
    }
  ],
  "indexTerms": [
    {
      "name": "Maritime Boundaries"
    }
  ],
  "actions": {...},
  "committees": {...}
}
```

### Standard Response Wrapper
```json
{
  "treaties": [...],
  "pagination": {
    "count": 10,
    "next": "...",
    "prev": "..."
  }
}
```

## 🛡️ Parameter Validation

### Congress Number
- **Type**: Integer
- **Range**: 93-119
- **Validation**: Must be valid Congress number
- **Error**: Returns suggestion for nearest valid Congress

### Treaty Number
- **Type**: Positive Integer
- **Range**: 1-999
- **Validation**: Must be positive
- **Error**: Returns format requirements

### Treaty Suffix
- **Type**: String
- **Format**: Single uppercase letter (A-Z)
- **Length**: Exactly 1 character
- **Validation**: Automatically converted to uppercase
- **Error**: Returns format requirements

### Date Parameters
- **Format**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
- **Timezone**: UTC required
- **Validation**: Must be valid date format
- **Error**: Returns format example

### Limit Parameter
- **Type**: Integer
- **Range**: 1-250
- **Default**: 10
- **Validation**: Automatically clamped to valid range

## 🔄 Data Processing

### Treaty Text Processing
- **Resolution Text**: Automatically cleaned of HTML tags for readability
- **Text Availability**: Indicated in treaty details with character count
- **Format Conversion**: HTML content converted to clean markdown format
- **Content Validation**: Checks for actual content vs empty/null values

### Document Handling
- **Related Documents**: Extracted and formatted with titles and URLs
- **Treaty Parts**: Structured part information when available
- **Index Terms**: Organized keyword extraction for easy reference
- **Content Status**: Clear indication of what content is available

## 🚨 Error Handling

### Common Error Types
1. **Invalid Parameter**: Validation failed
2. **API Server Error**: Upstream API issues
3. **Timeout Error**: Request exceeded time limit
4. **Rate Limit**: Too many requests

### Error Response Format
```json
{
  "error": {
    "type": "InvalidParameter",
    "message": "Congress number must be between 93 and 119",
    "parameter": "congress",
    "value": 200,
    "suggestions": ["Try 118 or 119 for recent treaties"]
  }
}
```

### Retry Logic
- **Automatic retries**: 3 attempts
- **Backoff strategy**: Exponential (1s, 2s, 4s)
- **Retry conditions**: Timeout, server errors
- **No retry**: Invalid parameters, authentication

## 🔧 Integration Notes

### MCP Client Integration
- All tools and resources follow MCP standards
- Consistent parameter naming across functions
- Standardized error responses
- Self-documenting API with built-in help

### Data Consistency
- All responses use consistent field names
- Standardized date formats (ISO 8601)
- Uniform error handling across all endpoints
- Predictable response structures

### Performance Optimization
- Efficient parameter validation
- Smart caching strategies
- Minimal API calls through deduplication
- Optimized response processing

## 📈 Monitoring & Logging

### Request Logging
- All API calls logged with parameters
- Response times and status codes tracked
- Error rates monitored
- Usage patterns analyzed

### Health Checks
- API endpoint availability
- Response time monitoring
- Error rate thresholds
- Automatic alerting

## 🔐 Security

### API Key Management
- Secure storage of credentials
- Automatic key rotation support
- Rate limit compliance
- Request signing validation

### Data Privacy
- No sensitive data caching
- Secure parameter handling
- Audit trail maintenance
- Compliance with data policies
"""
