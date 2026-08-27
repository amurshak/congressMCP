"""The truly-bare bucket call: `bills(operation="get_bill_details")` (F71).

This is the call a caller reading the schema actually makes. A bucket tool
shares one schema across every operation, so every parameter is advertised
as optional even where an operation cannot run without it -- a model with
no other information supplies the operation and nothing else, and finds out
what is required from the response.

That path was the one nothing exercised. `test_invoke_all_operations_with_
defaults.py` synthesises a dummy value for every handler parameter lacking
a default (`_dummy_required_kwargs`), *specifically* to avoid this crash;
it proves the chain survives when a caller supplies some value, not that a
bare call is answered honestly. `test_bucket_operation_guard.py` covers the
mirror-image mistake -- a parameter the handler does not accept -- and
likewise pre-fills the required ones. So the omission case ran through
neither, and shipped raising

    ToolError: Error executing bills operation 'get_bill_details':
    get_bill_details() missing 3 required positional arguments: ...

because the outer tool drops unset parameters before routing, the handler
was then called without them, and the bucket's blanket `except Exception`
re-raised the resulting TypeError with the raw Python message. That is not
the section-9 envelope; it is a crash path the envelope never covered.

These tests call every bucket operation with `operation=` and nothing else,
and require the section-9 `missing_parameter` envelope naming every absent
parameter. The sweep reuses scripts/audit_tool_schemas.py's dispatch parser,
so a new operation branch on any route_<name>_operation is covered
automatically.
"""
import inspect
import json
import os
import sys
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("CONGRESS_API_KEY", "test-key-for-bare-call-sweep")

from scripts.audit_tool_schemas import (  # noqa: E402
    _find_route_function,
    _parse_bucket_dispatch,
)

from congress_api.core.client_handler import AppContext, SimpleCache  # noqa: E402
from congress_api.core.exceptions import CongressionalAPIError  # noqa: E402
from congress_api.core.operation_routing import validate_operation_kwargs  # noqa: E402
from congress_api.mcp_server import mcp, initialize_mcp_features  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

initialize_mcp_features()


# --------------------------------------------------------------------------- #
# The guard itself.
# --------------------------------------------------------------------------- #
async def _needs_a_and_b(ctx, a, b, c=None):
    return "ok"


async def _needs_nothing(ctx, a=None, b=None):
    return "ok"


async def _var_keyword_but_still_needs_a(ctx, a, **kwargs):
    return "ok"


def _envelope_of(exc: CongressionalAPIError) -> dict:
    from congress_api.core.exceptions import error_envelope

    return error_envelope(exc.error_response)["error"]


def test_missing_required_parameter_raises_a_typed_error_not_a_toolerror():
    """CongressionalAPIError is the type every bucket tool already catches and
    renders as the envelope; a ToolError here would bypass that entirely."""
    with pytest.raises(CongressionalAPIError) as exc:
        validate_operation_kwargs(_needs_a_and_b, {}, "get_thing")
    assert not isinstance(exc.value, ToolError)


def test_missing_parameter_envelope_names_the_operation_and_every_parameter():
    with pytest.raises(CongressionalAPIError) as exc:
        validate_operation_kwargs(_needs_a_and_b, {}, "get_thing")
    err = _envelope_of(exc.value)
    assert err["code"] == "missing_parameter"
    assert err["detail"]["operation"] == "get_thing"
    # Both, sorted -- not just the first one the caller would then re-omit.
    assert err["detail"]["missing_parameters"] == "a, b"
    assert "get_thing" in err["message"]
    assert err["remediation"]


def test_only_the_absent_parameters_are_reported():
    with pytest.raises(CongressionalAPIError) as exc:
        validate_operation_kwargs(_needs_a_and_b, {"a": 1}, "get_thing")
    assert _envelope_of(exc.value)["detail"]["missing_parameters"] == "b"


def test_a_satisfied_handler_passes():
    validate_operation_kwargs(_needs_a_and_b, {"a": 1, "b": 2}, "get_thing")


def test_optional_parameters_are_never_demanded():
    validate_operation_kwargs(_needs_nothing, {}, "get_thing")


def test_a_var_keyword_handler_still_has_its_named_requirements_checked():
    """The unsupported-parameter half of the guard short-circuits on **kwargs.
    The missing half must not: a **kwargs handler can still declare named
    parameters with no default, and omitting one crashes it just the same."""
    with pytest.raises(CongressionalAPIError) as exc:
        validate_operation_kwargs(_var_keyword_but_still_needs_a, {"z": 1}, "get_thing")
    assert _envelope_of(exc.value)["detail"]["missing_parameters"] == "a"


def test_an_unsupported_parameter_still_raises_the_original_toolerror():
    """The pre-existing half of the guard is unchanged, including its
    precedence: a call that is both wrong and incomplete reports the
    parameter the caller actually typed."""
    with pytest.raises(ToolError) as exc:
        validate_operation_kwargs(_needs_a_and_b, {"zzz": 1}, "get_thing")
    assert "get_thing" in str(exc.value) and "zzz" in str(exc.value)


# --------------------------------------------------------------------------- #
# Every bucket operation, called bare.
# --------------------------------------------------------------------------- #
class _FakeResponse:
    status_code = 200
    text = "{}"

    def raise_for_status(self):
        pass

    def json(self):
        return {}


class _FakeRequestContext:
    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


@dataclass
class _FakeContext:
    """Duck-types what the call chain touches: lifespan_context, and error()/
    info() as plain sync callables (client_handler.py calls them unawaited)."""

    request_context: _FakeRequestContext

    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


def _make_fake_ctx() -> _FakeContext:
    app_context = AppContext(
        api_key="test-key", client=httpx.AsyncClient(), cache=SimpleCache(60)
    )
    return _FakeContext(request_context=_FakeRequestContext(app_context))


def _required_of(handler) -> set:
    """The handler parameters a caller must supply: no default, not plumbing.

    Deliberately recomputed here from `inspect` rather than imported from
    congress_api.core.operation_routing -- a test that asks the code under
    test what it should have done cannot fail when that answer is wrong.
    """
    return {
        name
        for name, p in inspect.signature(handler).parameters.items()
        if name not in ("ctx", "self")
        and p.default is inspect.Parameter.empty
        and p.kind
        not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
    }


def _required_parameters_section(doc: str) -> str:
    """The bucket docstring's REQUIRED PARAMETERS block (issue #69).

    Bounded at both ends so a stray mention of the same word in the trailing
    `Args:`/`Key params:` summary -- which pre-dates #69 and is not
    per-operation -- cannot stand in for a real entry.
    """
    marker = "REQUIRED PARAMETERS"
    if marker not in doc:
        return ""
    start = doc.index(marker)
    ends = [doc.find(m, start) for m in ("Args:", "Key params:")]
    ends = [e for e in ends if e != -1]
    return doc[start : min(ends) if ends else len(doc)]


def _list_bucket_operations():
    """(tool_name, operation, tool_fn, required) per bucket dispatch branch."""
    ops = []
    for tool in mcp._tool_manager.list_tools():
        tool_fn = tool.fn
        module = inspect.getmodule(tool_fn)
        schema_sig = inspect.signature(tool_fn)
        route_fn = _find_route_function(module)
        if route_fn is None or "operation" not in schema_sig.parameters:
            continue
        for operation, call in _parse_bucket_dispatch(route_fn, module.__package__).items():
            handler_module = __import__(call.module_name, fromlist=[call.orig_name])
            handler = getattr(handler_module, call.orig_name)
            ops.append((tool.name, operation, tool_fn, _required_of(handler)))
    return ops


_BUCKET_OPS = _list_bucket_operations()
_OPS_WITH_REQUIRED = [o for o in _BUCKET_OPS if o[3]]


def _error_of(result) -> Optional[dict]:
    """The section-9 error dict, from either tool shape.

    Structured buckets return a model carrying a typed ErrorInfo; str
    buckets return the rendered JSON envelope. Returns None on success.
    """
    if hasattr(result, "success"):
        err = getattr(result, "error", None)
        if err is None:
            return None
        return {"code": err.code, "message": err.message, "detail": err.detail}
    if isinstance(result, str) and result.lstrip().startswith("{"):
        try:
            return json.loads(result).get("error")
        except ValueError:
            return None
    return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,operation,tool_fn,required",
    _OPS_WITH_REQUIRED,
    ids=[f"{t}::{o}" for t, o, _, _ in _OPS_WITH_REQUIRED],
)
async def test_bare_call_returns_the_missing_parameter_envelope(
    tool_name, operation, tool_fn, required
):
    """The issue #71 contract, per operation: pass `operation` and nothing
    else, and get a structured `missing_parameter` envelope naming every
    parameter the handler needs -- never a raised ToolError wrapping the
    dispatch's `missing N required positional arguments` TypeError."""
    ctx = _make_fake_ctx()
    with patch.object(httpx.AsyncClient, "get", return_value=_FakeResponse()):
        try:
            result = await tool_fn(ctx, operation=operation)
        except ToolError as e:  # pragma: no cover - the bug this test pins
            pytest.fail(
                f"{tool_name}::{operation} raised ToolError on a bare call "
                f"instead of returning the section-9 envelope: {e}"
            )

    err = _error_of(result)
    assert err is not None, (
        f"{tool_name}::{operation} needs {sorted(required)} but a bare call "
        f"reported no error at all: {str(result)[:200]}"
    )
    assert err["code"] == "missing_parameter", (
        f"{tool_name}::{operation} needs {sorted(required)}; a bare call "
        f"should say so with code 'missing_parameter', got "
        f"'{err['code']}': {err['message']}"
    )
    named = {p.strip() for p in (err["detail"] or {}).get("missing_parameters", "").split(",")}
    assert required <= named, (
        f"{tool_name}::{operation} omitted {sorted(required - named)} from "
        f"its missing_parameters detail -- a caller told only about some of "
        f"them re-submits and fails again."
    )
    assert (err["detail"] or {}).get("operation") == operation


@pytest.mark.parametrize(
    "tool_name,operation,tool_fn,required",
    _OPS_WITH_REQUIRED,
    ids=[f"{t}::{o}" for t, o, _, _ in _OPS_WITH_REQUIRED],
)
def test_every_demanded_parameter_is_documented_as_required(
    tool_name, operation, tool_fn, required
):
    """Issue #69 and #71 have to agree. The envelope tells a caller what was
    missing only *after* a failed call; the docstring's REQUIRED PARAMETERS
    section is the only channel that tells them before. A parameter the guard
    demands but the docstring never names means the first call is guaranteed
    to fail with no way to have known."""
    section = _required_parameters_section(tool_fn.__doc__ or "")
    assert section, (
        f"{tool_name} has operations with required parameters but its "
        f"docstring has no REQUIRED PARAMETERS section (issue #69)."
    )
    undocumented = sorted(p for p in required if p not in section)
    assert not undocumented, (
        f"{tool_name}::{operation} fails a bare call demanding "
        f"{undocumented}, but {tool_name}'s REQUIRED PARAMETERS section "
        f"never names {'them' if len(undocumented) > 1 else 'it'} -- a "
        f"caller reading the schema and the docstring cannot avoid the "
        f"failure (issues #69, #71)."
    )


def test_the_sweep_actually_found_operations():
    """Non-vacuity. If dispatch parsing regressed to zero, or every handler
    stopped declaring required parameters, both sweeps above would pass by
    never running -- which is exactly how this bug survived the two existing
    sweeps that pre-fill required parameters."""
    assert len(_BUCKET_OPS) >= 80, (
        f"expected ~82 bucket (tool, operation) pairs, found "
        f"{len(_BUCKET_OPS)} -- the dispatch parser may have regressed"
    )
    assert len(_OPS_WITH_REQUIRED) >= 50, (
        f"expected ~55 operations with required parameters, found "
        f"{len(_OPS_WITH_REQUIRED)} -- if handlers gained defaults, the bare "
        f"call is no longer being exercised anywhere"
    )
