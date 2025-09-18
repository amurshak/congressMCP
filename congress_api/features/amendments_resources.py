# amendments_resources.py - MCP resource functions for amendments
from typing import Dict, Any
import json
import logging
from fastmcp import Context
from ..mcp_app import mcp
from ..core.api_wrapper import DefensiveAPIWrapper

# Configure logging
logger = logging.getLogger(__name__)

# Formatting helpers
def format_amendment_summary(amendment: Dict[str, Any]) -> str:
    """Format an amendment into a readable summary."""
    result = []
    result.append(f"Amendment: {amendment.get('number', 'Unknown')}")
    result.append(f"Type: {amendment.get('type', 'Unknown')}")
    result.append(f"Congress: {amendment.get('congress', 'Unknown')}")

    if "purpose" in amendment:
        result.append(f"Purpose: {amendment.get('purpose', 'Not specified')}")

    if "latestAction" in amendment:
        action = amendment["latestAction"]
        result.append(f"Latest Action: {action.get('text', 'Unknown')} ({action.get('actionDate', 'Unknown date')})")

    result.append(f"URL: {amendment.get('url', 'No URL available')}")
    return "\n".join(result)

# Resources
@mcp.resource("congress://amendments/latest")
async def get_latest_amendments(ctx: Context) -> str:
    """
    Get the most recent amendments introduced in Congress.

    Returns a list of the 10 most recently updated amendments across all
    Congresses, sorted by update date in descending order.
    """
    logger.info("Accessing latest amendments resource")
    try:
        data = await DefensiveAPIWrapper.safe_api_request("/amendment", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received: {data.keys() if isinstance(data, dict) else 'not a dict'}")

        if "error" in data:
            logger.error(f"Error in API response: {data['error']}")
            return json.dumps({"error": data["error"]})

        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} amendments")

        if not amendments:
            return "No amendments found."

        result = ["# Latest Amendments in Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))

        return "\n\n".join(result)
    except Exception as e:
        logger.error(f"Exception in get_latest_amendments: {str(e)}")
        return f"Error retrieving latest amendments: {str(e)}"

@mcp.resource("congress://amendments/{congress}")
async def get_amendments_by_congress(ctx: Context, congress: str) -> str:
    """
    Get amendments from a specific Congress.

    Args:
        congress_num: The number of the Congress (e.g., "117")

    Returns a list of the 10 most recently updated amendments from the
    specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing amendments for Congress {congress}")
    try:
        data = await DefensiveAPIWrapper.safe_api_request(f"/amendment/{congress}", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received for Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")

        if "error" in data:
            logger.error(f"Error in API response for Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})

        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} amendments for Congress {congress}")

        if not amendments:
            return f"No amendments found for the {congress}th Congress."

        result = [f"# Amendments in the {congress}th Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))

        return "\n\n".join(result)
    except Exception as e:
        logger.error(f"Exception in get_amendments_by_congress for Congress {congress}: {str(e)}")
        return f"Error retrieving amendments for the {congress}th Congress: {str(e)}"

@mcp.resource("congress://amendments/{congress}/{amendment_type}")
async def get_amendments_by_type(ctx: Context,congress: str, amendment_type: str) -> str:
    """
    Get amendments from a specific Congress and amendment type.

    Args:
        congress: The number of the Congress (e.g., "117")
        amendment_type: The type of amendment (e.g., "samdt", "hamdt")

    Returns a list of the 10 most recently updated amendments of the specified
    type from the specified Congress, sorted by update date in descending order.
    """
    logger.info(f"Accessing {amendment_type} amendments for Congress {congress}")

    try:
        data = await DefensiveAPIWrapper.safe_api_request(f"/amendment/{congress}/{amendment_type}", ctx, {"limit": 10, "sort": "updateDate+desc"}, timeout_override=10.0)
        logger.info(f"API response received for {amendment_type} amendments in Congress {congress}: {data.keys() if isinstance(data, dict) else 'not a dict'}")

        if "error" in data:
            logger.error(f"Error in API response for {amendment_type} amendments in Congress {congress}: {data['error']}")
            return json.dumps({"error": data["error"]})

        amendments = data.get("amendments", [])
        logger.info(f"Found {len(amendments)} {amendment_type} amendments for Congress {congress}")

        if not amendments:
            return f"No {amendment_type.upper()} amendments found for the {congress}th Congress."

        result = [f"# {amendment_type.upper()} Amendments in the {congress}th Congress\n"]
        for amendment in amendments:
            result.append("---\n")
            result.append(format_amendment_summary(amendment))

        return "\n\n".join(result)

    except Exception as e:
        logger.error(f"Exception in get_amendments_by_type for {amendment_type} amendments in Congress {congress}: {str(e)}")
        return f"Error retrieving {amendment_type.upper()} amendments for the {congress}th Congress: {str(e)}"