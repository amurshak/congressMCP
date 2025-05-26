# congress_api/features/treaties.py
import logging
from typing import Dict, List, Any, Optional

from ..mcp_app import mcp
from ..core.client_handler import make_api_request

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
    
    # Check if the expected key is present
    if 'treaty' not in treaty_data:
        # Try to determine if this is a valid response in a different format
        if isinstance(treaty_data, dict) and len(treaty_data) > 0:
            # Log what keys we did receive
            logging.debug(f"Received keys in response: {list(treaty_data.keys())}")
            return f"Received treaty data, but in an unexpected format. Keys: {list(treaty_data.keys())}"
        return "No treaty data available."
    
    treaty = treaty_data['treaty']
    
    lines = [
        f"Congress Received: {treaty.get('congressReceived', 'N/A')}",
        f"Congress Considered: {treaty.get('congressConsidered', 'N/A')}",
        f"Treaty Number: {treaty.get('number', 'N/A')}"
    ]
    
    # Add suffix if available
    if 'suffix' in treaty and treaty['suffix']:
        lines.append(f"Suffix: {treaty.get('suffix', 'N/A')}")
    
    # Add topic if available
    if 'topic' in treaty:
        lines.append(f"Topic: {treaty.get('topic', 'N/A')}")
    
    # Add transmitted date if available
    if 'transmittedDate' in treaty:
        lines.append(f"Transmitted Date: {treaty.get('transmittedDate', 'N/A')}")
    
    # Add update date if available
    if 'updateDate' in treaty:
        lines.append(f"Update Date: {treaty.get('updateDate', 'N/A')}")
    
    # Add in force date if available
    if 'inForceDate' in treaty and treaty['inForceDate']:
        lines.append(f"In Force Date: {treaty.get('inForceDate', 'N/A')}")
    
    # Add titles if available
    if 'titles' in treaty and treaty['titles']:
        lines.append("\nTitles:")
        for title in treaty['titles']:
            lines.append(f"  - {title.get('titleType', 'Unknown')}: {title.get('title', 'N/A')}")
    
    # Add countries/parties if available
    if 'countriesParties' in treaty and treaty['countriesParties']:
        countries = [country.get('name', 'Unknown') for country in treaty['countriesParties']]
        lines.append(f"\nCountries/Parties: {', '.join(countries)}")
    
    # Add index terms if available
    if 'indexTerms' in treaty and treaty['indexTerms']:
        terms = [term.get('name', 'Unknown') for term in treaty['indexTerms']]
        lines.append(f"\nIndex Terms: {', '.join(terms)}")
    
    # Add related documents if available
    if 'relatedDocs' in treaty and treaty['relatedDocs']:
        lines.append("\nRelated Documents:")
        for doc in treaty['relatedDocs']:
            lines.append(f"  - {doc.get('citation', 'N/A')}: {doc.get('url', 'N/A')}")
    
    # Add actions info if available
    if 'actions' in treaty and treaty['actions']:
        actions = treaty['actions']
        lines.append(f"\nActions: {actions.get('count', 'N/A')}")
        if 'url' in actions:
            lines.append(f"Actions URL: {actions.get('url', 'N/A')}")
    
    # Add parts info if available
    if 'parts' in treaty and treaty['parts'] and isinstance(treaty['parts'], dict) and 'urls' in treaty['parts']:
        parts = treaty['parts']
        lines.append(f"\nParts: {parts.get('count', 'N/A')}")
        if 'urls' in parts:
            lines.append("Part URLs:")
            for url in parts['urls']:
                lines.append(f"  - {url}")
    
    # Add resolution text if available
    if 'resolutionText' in treaty and treaty['resolutionText']:
        lines.append("\nResolution Text:")
        lines.append(treaty['resolutionText'])
    
    return "\n".join(lines)

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
async def get_latest_treaties() -> str:
    """
    Get the most recent treaties.
    Returns the 10 most recently published treaties by default.
    """
    context = mcp.get_context()
    logger.debug("Getting latest treaties")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': 10
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint="/treaty",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaties: {data['error']}"
    
    # Format the response
    return format_treaties_list(data)

@mcp.resource("congress://treaties/{congress}")
async def get_treaties_by_congress(congress: int) -> str:
    """
    Get treaties for a specific Congress.
    
    Args:
        congress: The Congress number (e.g., 117).
    """
    context = mcp.get_context()
    logger.debug(f"Getting treaties for Congress: {congress}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': 20
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint=f"/treaty/{congress}",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaties for Congress {congress}: {data['error']}"
    
    # Format the response
    return format_treaties_list(data)

@mcp.resource("congress://treaties/{congress}/{treaty_number}")
async def get_treaty_detail(congress: int, treaty_number: int) -> str:
    """
    Get detailed information for a specific treaty.
    
    Args:
        congress: The Congress number (e.g., 117).
        treaty_number: The treaty number (e.g., 3).
    """
    context = mcp.get_context()
    logger.debug(f"Getting treaty details for Congress: {congress}, Treaty Number: {treaty_number}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json'
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint=f"/treaty/{congress}/{treaty_number}",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaty details for Congress {congress}, Treaty Number {treaty_number}: {data['error']}"
    
    # Format the response
    return format_treaty_detail(data)

@mcp.resource("congress://treaties/{congress}/{treaty_number}/{treaty_suffix}")
async def get_treaty_detail_with_suffix(congress: int, treaty_number: int, treaty_suffix: str) -> str:
    """
    Get detailed information for a specific partitioned treaty.
    
    Args:
        congress: The Congress number (e.g., 114).
        treaty_number: The treaty number (e.g., 13).
        treaty_suffix: The treaty suffix (e.g., 'A').
    """
    context = mcp.get_context()
    logger.debug(f"Getting treaty details for Congress: {congress}, Treaty Number: {treaty_number}, Suffix: {treaty_suffix}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json'
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint=f"/treaty/{congress}/{treaty_number}/{treaty_suffix}",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaty details for Congress {congress}, Treaty Number {treaty_number}, Suffix {treaty_suffix}: {data['error']}"
    
    # Format the response
    return format_treaty_detail(data)

# --- MCP Tools ---

@mcp.tool("get_treaty_actions")
async def get_treaty_actions(
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
    context = mcp.get_context()
    logger.debug(f"Getting treaty actions for Congress: {congress}, Treaty Number: {treaty_number}, Suffix: {treaty_suffix}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': 50
    }
    
    # Determine the endpoint based on whether a suffix is provided
    if treaty_suffix:
        endpoint = f"/treaty/{congress}/{treaty_number}/{treaty_suffix}/actions"
    else:
        endpoint = f"/treaty/{congress}/{treaty_number}/actions"
    
    # Make the API request
    data = await make_api_request(
        endpoint=endpoint,
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaty actions: {data['error']}"
    
    # Format the response
    return format_treaty_actions(data)

@mcp.tool("get_treaty_committees")
async def get_treaty_committees(
    congress: int,
    treaty_number: int
) -> str:
    """
    Get committees for a specific treaty.
    
    Args:
        congress: The Congress number (e.g., 116).
        treaty_number: The treaty number (e.g., 3).
    """
    context = mcp.get_context()
    logger.debug(f"Getting treaty committees for Congress: {congress}, Treaty Number: {treaty_number}")
    
    # Set up parameters for the API request
    params = {
        'format': 'json',
        'limit': 50
    }
    
    # Make the API request
    data = await make_api_request(
        endpoint=f"/treaty/{congress}/{treaty_number}/committees",
        params=params,
        ctx=context
    )
    
    # Check if there was an error in the response
    if isinstance(data, dict) and 'error' in data:
        return f"Error retrieving treaty committees: {data['error']}"
    
    # Format the response
    return format_treaty_committees(data)

@mcp.tool("search_treaties")
async def search_treaties(
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
    context = mcp.get_context()
    logger.debug(f"Searching for treaties with congress: {congress}, topic: {topic}, from_date: {from_date}, to_date: {to_date}, limit: {limit}")
    
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
        ctx=context
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
