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

The same forwarding design produces a second, symmetric failure (issue
#71). Because the outer tool drops every unset parameter before routing,
an *omitted* parameter never reaches the handler at all — so a truly bare
call like `bills(operation="get_bill_details")`, which is exactly what a
caller reading a schema that marks every parameter optional would make,
used to die on `TypeError: get_bill_details() missing 3 required
positional arguments` inside the dispatch. The bucket's blanket
`except Exception` re-raised that as a ToolError carrying the raw Python
message: not the section-9 envelope, an uncaught-by-the-envelope crash
path. So this guard also checks the handler's required-parameter set up
front and raises CongressionalAPIError, which every bucket tool already
catches and renders as the section-9 envelope — a str envelope for the
str-returning tools, an envelope-carrying model for the structured ones.
"""
import inspect
from typing import Any, Callable, Dict

from mcp.server.mcpserver.exceptions import ToolError

from .exceptions import CommonErrors, CongressionalAPIError

_PLUMBING = ("ctx", "self")


def _required_parameters(sig: inspect.Signature) -> set:
    """Names the handler cannot be called without, minus router plumbing.

    Every dispatch site invokes its handler as `handler(ctx, **kwargs)`, so
    `ctx` is the only argument the router supplies itself; anything else
    without a default has to come from the caller's kwargs.
    """
    return {
        name
        for name, p in sig.parameters.items()
        if name not in _PLUMBING
        and p.default is inspect.Parameter.empty
        and p.kind not in (inspect.Parameter.VAR_KEYWORD,
                           inspect.Parameter.VAR_POSITIONAL)
    }


def validate_operation_kwargs(handler: Callable, kwargs: Dict[str, Any], operation: str) -> None:
    """Reject kwargs `handler` won't accept, and required ones it's missing.

    An unsupported parameter raises ToolError. A *missing required*
    parameter raises CongressionalAPIError, so the bucket tool's existing
    `except CongressionalAPIError` turns it into the section-9 envelope
    (issue #71) rather than a raw ToolError from the dispatch TypeError.

    The unsupported-parameter check is a no-op if `handler` declares a
    **kwargs catch-all; the missing-required check is not, since such a
    handler can still declare named parameters with no default. `kwargs`
    only ever contains parameters the caller actually set (the outer tool
    drops None/unset ones before routing), so anything rejected here was
    explicitly supplied by the caller for an operation that doesn't use it,
    and anything reported missing was genuinely never supplied.
    """
    sig = inspect.signature(handler)
    takes_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )

    if not takes_var_keyword:
        accepted = {name for name in sig.parameters if name != "ctx"}
        unexpected = set(kwargs) - accepted
        if unexpected:
            raise ToolError(
                f"Operation '{operation}' does not accept parameter(s): {', '.join(sorted(unexpected))}"
            )

    missing = _required_parameters(sig) - set(kwargs)
    if missing:
        raise CongressionalAPIError(
            CommonErrors.missing_parameter(sorted(missing), operation)
        )
