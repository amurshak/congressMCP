"""Shared guard for bucket-tool operation routing.

The bucket tools (bills, amendments, treaties_and_summaries,
committee_intelligence, voting_and_nominations, research_and_professional,
records_and_hearings) each expose one @mcp.tool covering many `operation`
values, backed by a route_<name>_operation() that dispatches to a specific
handler per operation and forwards it the *entire* flat kwargs dict the
outer tool collected -- every parameter that is relevant to *any* operation
in the bucket, not just the one being called.

Individual handlers only accept the subset of those parameters that apply to
them, so forwarding the full dict blindly means any caller who sets a
parameter that happens to belong to a sibling operation gets an unhandled
`TypeError: <handler>() got an unexpected keyword argument`, surfaced
through the tool's generic exception handler as an opaque failure — instead
of a message that says what's actually wrong.

Call this immediately before invoking the resolved handler in every
route_<name>_operation if/elif branch. It doesn't change what's accepted —
handlers still reject parameters they don't declare — it just turns that
rejection into a clear, honest ToolError naming the operation and the bad
parameter(s), instead of a raw TypeError or a swallowed generic error.
"""
import inspect
from typing import Any, Callable, Dict

from mcp.server.mcpserver.exceptions import ToolError


def validate_operation_kwargs(handler: Callable, kwargs: Dict[str, Any], operation: str) -> None:
    """Raise ToolError if `kwargs` contains a key `handler` doesn't accept.

    No-op if `handler` declares a **kwargs catch-all. `kwargs` only ever
    contains parameters the caller actually set (the outer tool already
    drops None/unset ones before routing), so anything rejected here was
    explicitly supplied by the caller for an operation that doesn't use it.
    """
    sig = inspect.signature(handler)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return

    accepted = {name for name in sig.parameters if name != "ctx"}
    unexpected = set(kwargs) - accepted
    if unexpected:
        raise ToolError(
            f"Operation '{operation}' does not accept parameter(s): {', '.join(sorted(unexpected))}"
        )
