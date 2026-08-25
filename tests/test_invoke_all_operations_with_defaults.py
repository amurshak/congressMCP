"""Invoke every registered MCP tool operation with its schema defaults.

This is the runtime companion to scripts/audit_tool_schemas.py. The audit
script catches schema/signature drift statically; this test catches what
static analysis can't: whether the full call chain (tool wrapper -> routing
-> handler -> API request) actually runs to completion for every operation,
with realistic-shaped (but network-mocked) plumbing.

It would have caught both known bugs described in the schema-drift audit:
- get_member_sponsored_legislation: TypeError on `limit`, raised even when
  the caller omits it (the old wrapper always forwarded its own hardcoded
  default) -- masked in production by the tool's blanket except-and-return-
  an-error-object handling, which is exactly why this test checks `.success`
  on structured responses instead of only "did it raise".

The network is mocked at the httpx.AsyncClient.get level -- the one place
every request path funnels through regardless of which of the many
`safe_*_request`/`make_api_request` local import aliases a given handler
uses -- so every operation gets a uniformly empty-but-valid JSON response
without needing per-operation response fixtures.

Issue #69 follow-up: for bucket tools, one schema is shared across every
operation, so every parameter is marked optional even when a specific
operation genuinely requires it. When schema defaults trip a parameter-
shaped validation error (invalid_parameter and the handful of dedicated
invalid_*_type/congress_too_old_for_text codes), this test also asserts
that the required parameter is actually named in the tool's own docstring
-- the only channel available to tell a caller before it tries. Coverage
caveat: several bills-bucket detail operations (get_bill_titles,
get_bill_subjects, get_bill_text, etc.) return a bare prose string on
error rather than the section-9 envelope, so this check -- like the
crash check above it -- only reaches them via the JSON-string branch,
and not at all when the error is prose. Only get_bill_details and
get_bill_actions in that family are actually envelope-shaped today.
"""
import inspect
import os
import sys
import typing
from dataclasses import dataclass
from typing import Any, Dict
from unittest.mock import patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.audit_tool_schemas import (  # noqa: E402
    ALLOWLIST,
    _find_route_function,
    _param_names,
    _parse_bucket_dispatch,
    _parse_flat_delegate,
)

os.environ.setdefault("CONGRESS_API_KEY", "test-key-for-invocation-smoke-test")

from congress_api.mcp_server import mcp, initialize_mcp_features  # noqa: E402
from congress_api.core.client_handler import AppContext, SimpleCache  # noqa: E402

initialize_mcp_features()


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
    """Duck-types just what the call chain actually touches: lifespan_context
    (for the shared httpx client/api key/cache) and a no-op error() -- real
    client_handler.py calls ctx.error(...) without awaiting it, so this must
    be a plain sync callable, not a coroutine function."""
    request_context: _FakeRequestContext

    def error(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


def _make_fake_ctx() -> _FakeContext:
    app_context = AppContext(api_key="test-key", client=httpx.AsyncClient(), cache=SimpleCache(60))
    return _FakeContext(request_context=_FakeRequestContext(app_context))


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
    """One dummy value per handler param that has no default (excluding ctx)."""
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


def _list_operations():
    """(tool_name, operation_label, tool_fn, call_kwargs) for every
    registered (tool, operation) pair, skipping ALLOWLISTed exceptions."""
    ops = []
    for tool in mcp._tool_manager.list_tools():
        tool_fn = tool.fn
        module = inspect.getmodule(tool_fn)
        schema_sig = inspect.signature(tool_fn)
        route_fn = _find_route_function(module)

        if route_fn is not None and "operation" in schema_sig.parameters:
            dispatch = _parse_bucket_dispatch(route_fn, module.__package__)
            for operation, call in dispatch.items():
                if (tool.name, operation, "*") in ALLOWLIST:
                    continue
                handler_module = __import__(call.module_name, fromlist=[call.orig_name])
                handler = getattr(handler_module, call.orig_name)
                kwargs = _dummy_required_kwargs(handler)
                kwargs["operation"] = operation
                ops.append((tool.name, operation, tool_fn, kwargs))
        else:
            call = _parse_flat_delegate(tool_fn, module.__package__)
            if call is None:
                continue
            # Flat tools are a direct 1:1 mapping onto their delegate, so
            # what the *caller* must supply is governed by the outer tool's
            # own signature, not the delegate's -- the delegate may default
            # something the outer wrapper still requires (or vice versa).
            kwargs = _dummy_required_kwargs(tool_fn)
            ops.append((tool.name, tool.name, tool_fn, kwargs))
    return ops


_OPERATIONS = _list_operations()

# Issue #69: a handful of error codes name the offending parameter in the
# code itself rather than via the generic invalid_parameter -> detail.parameter
# channel: invalid_bill_type/invalid_amendment_type/invalid_communication_type
# come from dedicated CommonErrors.* helpers (congress_api/core/exceptions.py);
# congress_too_old_for_text is a domain-specific inline check in
# congress_api/features/buckets/amendments/api.py with no such helper. Map
# each straight to the parameter a bucket docstring must name.
_CODE_TO_PARAM = {
    "invalid_bill_type": "bill_type",
    "invalid_amendment_type": "amendment_type",
    "invalid_communication_type": "communication_type",
    "congress_too_old_for_text": "congress",
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,operation,tool_fn,kwargs",
    _OPERATIONS,
    ids=[f"{t}::{o}" for t, o, _, _ in _OPERATIONS],
)
async def test_operation_invocable_with_schema_defaults(tool_name, operation, tool_fn, kwargs):
    """Every operation must run its full call chain without raising, and never
    produce an internal_error -- with an always-empty-but-valid mocked network
    layer, internal_error (or an untyped failure) can only come from a code
    bug (a signature mismatch, a crash in the handler body), not business
    logic. Honest domain errors ARE allowed now that the section-9 envelope
    surfaces them: empty mocked data legitimately yields data_not_found, and
    schema defaults legitimately violate some operations' parameter rules
    (invalid_parameter). Before the envelope work those cases hid behind
    success=True markdown, which is what the old assertion checked."""
    import json as _json
    ctx = _make_fake_ctx()
    with patch.object(httpx.AsyncClient, "get", return_value=_FakeResponse()):
        result = await tool_fn(ctx, **kwargs)

    code = None
    detail = None
    if hasattr(result, "success"):
        if result.success is False:
            err = getattr(result, "error", None)
            assert err is not None, (
                f"{tool_name}::{operation} failed without a typed error: "
                f"{getattr(result, 'summary', result)}"
            )
            # With an always-healthy mocked network, none of these codes are
            # legitimate: internal_error is a crash by definition, and
            # server_error/general_* only arise from handler-local generic
            # excepts swallowing a crash (the network cannot have failed).
            assert err.code not in ("internal_error", "server_error",
                                    "general_error", "general_api_failure"), (
                f"{tool_name}::{operation} crashed: {err.message}"
            )
            code = err.code
            detail = err.detail
    elif isinstance(result, str) and result.lstrip().startswith("{"):
        try:
            payload = _json.loads(result).get("error") or {}
        except ValueError:
            payload = {}
        assert payload.get("code") not in ("internal_error", "server_error",
                                           "general_error", "general_api_failure"), (
            f"{tool_name}::{operation} crashed: {payload.get('message')}"
        )
        code = payload.get("code")
        detail = payload.get("detail")

    # Issue #69: a bucket's shared schema marks every parameter optional,
    # so when schema defaults trip a parameter-shaped validation error, the
    # only place a caller could have learned that parameter was required is
    # the tool's own docstring. Assert it's actually named there.
    missing_param = _CODE_TO_PARAM.get(code)
    if missing_param is None and code == "invalid_parameter" and detail:
        missing_param = detail.get("parameter")
    if missing_param is not None:
        doc = tool_fn.__doc__ or ""
        # Bucket docstrings carry a "REQUIRED PARAMETERS" section listing
        # exactly which operations need which params (issue #69). Anchor the
        # check there when it exists so a stray mention of the parameter name
        # elsewhere in the docstring (e.g. a generic Args: line) can't paper
        # over a missing entry for THIS operation; fall back to the whole
        # docstring for flat tools, which have no such section.
        marker = "REQUIRED PARAMETERS"
        required_section = doc[doc.index(marker):] if marker in doc else doc
        if code == "congress_too_old_for_text":
            assert missing_param in required_section, (
                f"{tool_name}::{operation} rejected schema defaults because "
                f"the dummy congress value is out of the supported range, "
                f"but the {tool_name} tool's docstring never names "
                f"'{missing_param}' as required in the first place -- a "
                f"caller has no way to learn it needs a real congress value "
                f"at all (issue #69)."
            )
        else:
            assert missing_param in required_section, (
                f"{tool_name}::{operation} rejected schema defaults with an "
                f"invalid '{missing_param}', but the {tool_name} tool's "
                f"docstring never names '{missing_param}' as required -- a "
                f"caller reading the schema has no way to learn that "
                f"beforehand (issue #69)."
            )


def test_operations_were_discovered():
    """Sanity check on the parametrization itself: if dispatch parsing
    silently found zero operations for every tool, the test above would
    trivially "pass" with nothing actually exercised."""
    assert len(_OPERATIONS) >= 90, (
        f"expected ~96 (tool, operation) pairs, found {len(_OPERATIONS)} -- "
        "audit_tool_schemas' dispatch parsing may have regressed"
    )
