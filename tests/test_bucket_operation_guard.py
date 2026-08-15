"""The validate_operation_kwargs guard, exercised where it actually lives (F24).

Six bucket test files used to claim this territory. They imported the standalone
`fastmcp` package and the deleted tier system (`congress_api.core.auth.auth`,
`FREE_OPERATIONS`/`PAID_OPERATIONS`), targeting bucket modules that were renamed
or replaced -- so they never collected, sat baselined as known collection
errors, and the guard's raise path shipped with zero coverage wearing a green
baseline. That is the greenwash F24 names: an errored check recorded as handled
reads as coverage that does not exist. These tests collect, and they drive the
guard through every live router branch rather than a deleted architecture.

The sweep reuses scripts/audit_tool_schemas.py's dispatch parser, so a new
operation branch added to any route_<name>_operation is swept automatically --
including the case where the author forgot to paste the guard call in, which
surfaces here as the handler's raw TypeError instead of the guard's ToolError.
"""
import inspect
import os
import sys
import typing
from typing import Any, Dict
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("CONGRESS_API_KEY", "test-key-for-guard-sweep")

from scripts.audit_tool_schemas import (  # noqa: E402
    _find_route_function,
    _parse_bucket_dispatch,
)

from congress_api.core.operation_routing import validate_operation_kwargs  # noqa: E402
from congress_api.mcp_server import mcp, initialize_mcp_features  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

initialize_mcp_features()


# --------------------------------------------------------------------------- #
# The guard itself.
# --------------------------------------------------------------------------- #
async def _takes_a_and_b(ctx, a=None, b=None):
    return "ok"


async def _takes_anything(ctx, **kwargs):
    return "ok"


def test_guard_raises_naming_the_operation_and_every_bad_parameter():
    with pytest.raises(ToolError) as exc:
        validate_operation_kwargs(_takes_a_and_b, {"a": 1, "x": 2, "y": 3}, "get_thing")
    message = str(exc.value)
    assert "get_thing" in message
    assert "x, y" in message  # sorted, both named -- not just the first


def test_guard_accepts_kwargs_the_handler_declares():
    validate_operation_kwargs(_takes_a_and_b, {"a": 1, "b": 2}, "get_thing")


def test_guard_is_a_noop_for_a_var_keyword_handler():
    validate_operation_kwargs(_takes_anything, {"anything": 1}, "get_thing")


def test_guard_never_counts_ctx_against_the_caller():
    # ctx is plumbing the router supplies, not a caller parameter.
    validate_operation_kwargs(_takes_a_and_b, {"a": 1}, "get_thing")


# --------------------------------------------------------------------------- #
# The raise path through every live router branch.
# --------------------------------------------------------------------------- #
class _FakeResponse:
    status_code = 200
    text = "{}"

    def raise_for_status(self):
        pass

    def json(self):
        return {}


def _dummy_value(annotation: Any) -> Any:
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        non_none = [a for a in typing.get_args(annotation) if a is not type(None)]
        annotation = non_none[0] if non_none else str
    if annotation is bool:
        return True
    if annotation is int:
        return 1
    if annotation is float:
        return 1.0
    return "TEST"


def _dummy_required_kwargs(handler) -> Dict[str, Any]:
    sig = inspect.signature(handler)
    kwargs = {}
    for name, p in sig.parameters.items():
        if name in ("ctx", "self"):
            continue
        if p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
            continue
        if p.default is inspect.Parameter.empty:
            kwargs[name] = _dummy_value(p.annotation)
    return kwargs


def _list_guarded_operations():
    """(tool, operation, route_fn, call_kwargs, extraneous) per bucket branch.

    `extraneous` is a parameter the OUTER tool's schema exposes but the
    operation's handler does not accept -- i.e. a sibling operation's
    parameter, the exact caller mistake the guard exists to catch. Operations
    whose handler accepts every schema parameter (or takes **kwargs) have no
    such input and are skipped: the guard is unreachable through the tool for
    them, which is a property of the schema, not a coverage gap.
    """
    ops = []
    for tool in mcp._tool_manager.list_tools():
        tool_fn = tool.fn
        module = inspect.getmodule(tool_fn)
        schema_sig = inspect.signature(tool_fn)
        route_fn = _find_route_function(module)
        if route_fn is None or "operation" not in schema_sig.parameters:
            continue
        schema_params = {
            name for name in schema_sig.parameters if name not in ("ctx", "operation")
        }
        dispatch = _parse_bucket_dispatch(route_fn, module.__package__)
        for operation, call in dispatch.items():
            handler_module = __import__(call.module_name, fromlist=[call.orig_name])
            handler = getattr(handler_module, call.orig_name)
            sig = inspect.signature(handler)
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                continue
            accepted = {name for name in sig.parameters if name != "ctx"}
            candidates = sorted(schema_params - accepted)
            if not candidates:
                continue
            kwargs = _dummy_required_kwargs(handler)
            extraneous = candidates[0]
            kwargs[extraneous] = _dummy_value(schema_sig.parameters[extraneous].annotation)
            kwargs["operation"] = operation
            ops.append((tool.name, operation, route_fn, kwargs, extraneous))
    return ops


_GUARDED = _list_guarded_operations()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,operation,route_fn,kwargs,extraneous",
    _GUARDED,
    ids=[f"{t}::{o}" for t, o, _, _, _ in _GUARDED],
)
async def test_sibling_parameter_raises_a_toolerror_naming_it(
    tool_name, operation, route_fn, kwargs, extraneous
):
    """A parameter belonging to a sibling operation must surface as the guard's
    ToolError naming the operation and the parameter -- never the handler's raw
    `TypeError: unexpected keyword argument`, which is what a branch missing
    its validate_operation_kwargs call produces here."""
    with patch.object(httpx.AsyncClient, "get", return_value=_FakeResponse()):
        with pytest.raises(ToolError) as exc:
            await route_fn(None, **kwargs)
    message = str(exc.value)
    assert operation in message and extraneous in message


def test_the_sweep_actually_found_branches():
    """Non-vacuity: if dispatch parsing regressed to zero, every test above
    would pass by never existing."""
    assert len(_GUARDED) >= 40, (
        f"expected dozens of guarded (tool, operation) branches, found "
        f"{len(_GUARDED)} -- the dispatch parser or the schema/handler "
        "signatures may have regressed"
    )
