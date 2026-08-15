"""
Congressional Laws tool — enacted public and private laws via the /law endpoint.

The /law endpoints return the same shapes as /bill (a `bills` list for listings,
a `bill` object for details, each law carrying a `laws: [{number, type}]` field),
so this tool reuses BillsFormatter directly.

Operations:
- get_laws: list enacted laws for a congress, optionally by law type (pub/priv).
- get_law_details: detail for a specific law (congress + law type + law number).
"""
import logging
from typing import Optional

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError

from ...mcp_app import mcp
from ...core.api_wrapper import safe_congressional_request
from ...core.operation_routing import validate_operation_kwargs
from ...core.validators import ParameterValidator
from .bills.formatters import BillsFormatter

logger = logging.getLogger(__name__)


def _normalize_law_type(law_type: Optional[str]) -> Optional[str]:
    """Map friendly law-type aliases to the API's 'pub'/'priv'. None passes through."""
    if not law_type:
        return None
    lt = law_type.strip().lower()
    if lt in ("pub", "public"):
        return "pub"
    if lt in ("priv", "private"):
        return "priv"
    return None


async def get_laws(
    ctx: Context,
    congress: Optional[int] = None,
    law_type: Optional[str] = None,
    limit: int = 20,
    offset: Optional[int] = None,
) -> str:
    """List enacted laws for a congress (optionally filtered by pub/priv)."""
    if congress is None:
        return "A congress number is required (e.g. 119)."
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return congress_validation.error_message

    endpoint = f"/law/{congress}"
    if law_type is not None:
        normalized = _normalize_law_type(law_type)
        if not normalized:
            return f"Invalid law_type '{law_type}'. Use 'pub' (public) or 'priv' (private)."
        endpoint = f"/law/{congress}/{normalized}"

    params = {"limit": limit}
    if offset is not None:
        params["offset"] = offset

    data = await safe_congressional_request(endpoint, ctx, params, endpoint_type="bills")
    if isinstance(data, dict) and "error" in data:
        return str(data["error"])

    return BillsFormatter.format_bills_list(data, f"Laws — {congress}th Congress")


async def get_law_details(
    ctx: Context,
    congress: Optional[int] = None,
    law_type: Optional[str] = None,
    law_number: Optional[int] = None,
) -> str:
    """Get detail for a specific enacted law."""
    if congress is None or law_type is None or law_number is None:
        return "get_law_details requires congress, law_type ('pub'/'priv'), and law_number."
    congress_validation = ParameterValidator.validate_congress_number(congress)
    if not congress_validation.is_valid:
        return congress_validation.error_message

    normalized = _normalize_law_type(law_type)
    if not normalized:
        return f"Invalid law_type '{law_type}'. Use 'pub' (public) or 'priv' (private)."

    endpoint = f"/law/{congress}/{normalized}/{law_number}"
    data = await safe_congressional_request(endpoint, ctx, {}, endpoint_type="bills")
    if isinstance(data, dict) and "error" in data:
        return str(data["error"])

    bill = data.get("bill", {})
    if not bill:
        return f"No law found for {normalized} {law_number} in the {congress}th Congress."
    return BillsFormatter.format_bill_detail(bill)


async def route_laws_operation(ctx: Context, operation: str, **kwargs) -> str:
    """Route a laws operation to its impl.

    Standard bucket pattern (core/operation_routing.py): the guard rejects a
    parameter belonging to a sibling operation with a ToolError naming it,
    instead of the old cherry-picking route that silently dropped it.
    """
    if operation == "get_laws":
        validate_operation_kwargs(get_laws, kwargs, operation)
        return await get_laws(ctx, **kwargs)
    elif operation == "get_law_details":
        validate_operation_kwargs(get_law_details, kwargs, operation)
        return await get_law_details(ctx, **kwargs)
    else:
        raise ToolError(f"Unknown laws operation: {operation}")


@mcp.tool(
    "laws",
    title="Congressional Laws - Enacted public and private laws",
)
async def laws(
    ctx: Context,
    operation: str,
    congress: Optional[int] = None,
    law_type: Optional[str] = None,
    law_number: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> str:
    """
    Congressional Laws - enacted public and private laws (the /law endpoint).

    OPERATIONS:
    • get_laws: list enacted laws for a congress. Optional law_type ('pub' or
      'priv') narrows to public or private laws.
    • get_law_details: full detail for one law (needs congress, law_type, law_number).

    Args:
        operation: 'get_laws' or 'get_law_details'
        congress: Congress number (e.g., 119) — required
        law_type: 'pub' (public) or 'priv' (private); optional for get_laws,
                  required for get_law_details
        law_number: The law's sequential number (required for get_law_details)
        limit: Max results for get_laws (default 20)
        offset: Pagination offset for get_laws

    Examples:
        {"operation": "get_laws", "congress": 119}
        {"operation": "get_laws", "congress": 119, "law_type": "pub", "limit": 10}
        {"operation": "get_law_details", "congress": 119, "law_type": "pub", "law_number": 1}
    """
    try:
        # Forward only the parameters the caller actually set, like the other
        # bucket tools: the routing guard reads presence as intent, so an unset
        # None must not reach it.
        kwargs = {
            key: value
            for key, value in {
                "congress": congress,
                "law_type": law_type,
                "law_number": law_number,
                "limit": limit,
                "offset": offset,
            }.items()
            if value is not None
        }
        return await route_laws_operation(ctx, operation, **kwargs)
    except ToolError:
        raise
    except Exception as e:
        logger.error(f"Error in laws tool ({operation}): {e}")
        return f"Error executing laws operation '{operation}': {str(e)}"
