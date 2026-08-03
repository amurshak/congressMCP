#!/usr/bin/env python3
"""Audit every registered MCP tool for schema/implementation drift.

Background
----------
This server exposes MCP tools in two shapes:

  - "bucket" tools (bills, laws, amendments, treaties_and_summaries,
    committee_intelligence, voting_and_nominations, research_and_professional,
    records_and_hearings): one @mcp.tool covers many `operation` values. The
    tool function builds a single kwargs dict from its own (non-None)
    parameters and forwards it, unfiltered, to whichever handler
    `route_<name>_operation()` selects for that operation. Every parameter in
    the tool's schema is therefore live ammunition for every operation, not
    just the ones that use it.

  - "flat" tools (congress_api/features/members_committees_tools.py): one
    @mcp.tool == one operation, delegating directly to an impl function with
    an explicit, hand-written set of keyword arguments.

In both shapes, the exposed schema is generated from the @mcp.tool wrapper's
own signature (FastMCP does this automatically, so wrapper signature and
schema are identical by construction -- there is no drift to find there).
The drift this script looks for is between what the wrapper forwards and
what the downstream handler actually accepts and uses:

  - EXTRA:   forwarded param the handler's signature doesn't declare (and the
             handler has no **kwargs catch-all) -> guaranteed TypeError the
             moment a caller supplies that param. If the wrapper's own
             default for that param is not None, it is forwarded on *every*
             call, including ones that omit it -- this is flagged separately
             as "always triggers" since it makes the operation permanently
             uncallable rather than conditionally broken.
  - MISSING: handler accepts a parameter the schema never exposes at all --
             that capability is silently unreachable through the tool, no
             error, just a feature nobody can turn on.
  - UNUSED:  the parameter is both forwarded and accepted, but the handler's
             body never references it -- accepted, no effect, no error.
  - DROPPED: (flat tools only) the wrapper's own schema declares a parameter
             it never actually forwards to its delegate call. Reachable in
             principle but the wrapper throws it away before it can do
             anything.

Usage
-----
    python scripts/audit_tool_schemas.py           # human-readable report
    python scripts/audit_tool_schemas.py --check    # same, exits 1 if any
                                                     # EXTRA/DROPPED finding
                                                     # is not in the allowlist

Known, deliberately-unfixed exception
--------------------------------------
bills/get_bill_content's `version` (EXTRA) and `chunk_number`/`chunk_size`
(UNUSED) are excluded from the failing set via ALLOWLIST below. Content
chunking isn't implemented yet -- get_bill_content currently delegates to
get_bill_text_versions and ignores all three params. Accepting `version` and
silently ignoring it would be worse than the current hard rejection, so it's
left alone pending the real chunking implementation. See the comment on
get_bill_content in congress_api/features/buckets/bills/api.py.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

IGNORED_PARAMS = {"ctx", "self"}

# (tool_name, operation, param_name) triples that are known, deliberate
# exceptions -- not bugs to fix, just not yet implemented. Keep this list
# small and each entry commented with why.
ALLOWLIST: Set[Tuple[str, str, str]] = {
    # version: get_bill_content doesn't do real content-chunking yet; it
    # delegates to get_bill_text_versions and has no use for a specific
    # version. Accepting the param and ignoring it would be worse than
    # rejecting it outright. See congress_api/features/buckets/bills/api.py.
    ("bills", "get_bill_content", "version"),          # EXTRA
    ("bills", "get_bill_content", "chunk_number"),      # UNUSED
    ("bills", "get_bill_content", "chunk_size"),        # UNUSED

    # most_recent: get_committee_nominations keeps the same signature as its
    # sibling committee tools (get_committee_bills/reports/communications),
    # but the Senate nominations endpoint is already newest-first, so there's
    # no "jump to the end" flip to perform. Documented in the function's own
    # docstring. See congress_api/features/committees.py.
    ("get_committee_nominations", "get_committee_nominations", "most_recent"),  # UNUSED
}


@dataclass
class OperationAudit:
    tool_name: str
    operation: str
    handler_qualname: str
    extra: Set[str] = field(default_factory=set)
    extra_always: Set[str] = field(default_factory=set)
    missing_from_schema: Set[str] = field(default_factory=set)
    dropped_by_wrapper: Set[str] = field(default_factory=set)
    unused_in_body: Set[str] = field(default_factory=set)
    error: Optional[str] = None

    @property
    def clean(self) -> bool:
        """No findings of any kind, including informational-only ones."""
        return not (
            self.extra or self.missing_from_schema
            or self.dropped_by_wrapper or self.unused_in_body or self.error
        )

    @property
    def blocking(self) -> bool:
        """Findings that should fail CI.

        Plain `extra` (a bucket operation rejecting a sibling operation's
        parameter) is EXCLUDED here: it's an inherent, structural property of
        the shared-schema bucket design, not a bug -- and it's already made
        safe at runtime by validate_operation_kwargs, which turns it into a
        clear ToolError instead of a raw TypeError. `extra_always` is NOT
        excluded: a param the wrapper forwards on every call (even when the
        caller never set it) makes the operation permanently broken, which is
        exactly bug #1's failure mode (get_member_sponsored_legislation
        rejected `limit` even when omitted, because the old wrapper always
        forwarded its own hardcoded default).
        """
        return bool(
            self.extra_always or self.missing_from_schema
            or self.dropped_by_wrapper or self.unused_in_body or self.error
        )

    def filtered(self) -> "OperationAudit":
        """Copy with allowlisted (tool, operation, param) triples removed."""
        def drop(names: Set[str]) -> Set[str]:
            return {
                n for n in names
                if (self.tool_name, self.operation, n) not in ALLOWLIST
            }
        return OperationAudit(
            tool_name=self.tool_name,
            operation=self.operation,
            handler_qualname=self.handler_qualname,
            extra=drop(self.extra),
            extra_always=drop(self.extra_always),
            missing_from_schema=drop(self.missing_from_schema),
            dropped_by_wrapper=drop(self.dropped_by_wrapper),
            unused_in_body=drop(self.unused_in_body),
            error=self.error,
        )


# --------------------------------------------------------------------------
# Signature helpers
# --------------------------------------------------------------------------

def _param_names(sig: inspect.Signature, exclude=IGNORED_PARAMS) -> Set[str]:
    return {
        name for name, p in sig.parameters.items()
        if name not in exclude
        and p.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)
    }


def _has_var_keyword(sig: inspect.Signature) -> bool:
    return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())


def _non_none_default_params(sig: inspect.Signature, exclude=IGNORED_PARAMS) -> Set[str]:
    """Params with a concrete (non-None) default -- forwarded on every call,
    even when the caller never sets them."""
    out = set()
    for name, p in sig.parameters.items():
        if name in exclude:
            continue
        if p.default is not inspect.Parameter.empty and p.default is not None:
            out.add(name)
    return out


def _body_referenced_names(fn: Callable) -> Set[str]:
    """Names referenced (Load context) anywhere in fn's body -- not its
    signature or decorators."""
    src = textwrap.dedent(inspect.getsource(fn))
    tree = ast.parse(src)
    fn_node = tree.body[0]
    names: Set[str] = set()
    for stmt in fn_node.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
            # f-strings / .format(**locals())-style dynamic access would be
            # invisible to this check; none of this codebase's handlers do
            # that (verified by hand when this script was written).
    return names


# --------------------------------------------------------------------------
# AST-based dispatch resolution
# --------------------------------------------------------------------------

@dataclass
class DelegateCall:
    module_name: str  # resolved absolute module the handler lives in
    orig_name: str     # the handler's name in that module
    kwarg_names: Set[str]
    has_star_kwargs: bool


def _collect_local_imports(stmts: List[ast.stmt]) -> Dict[str, Tuple[Optional[str], int, str]]:
    """name -> (module, level, orig_name) for every ImportFrom found anywhere
    within the given statement list (arbitrary nesting)."""
    imports: Dict[str, Tuple[Optional[str], int, str]] = {}
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    imports[local_name] = (node.module, node.level, alias.name)
    return imports


def _find_delegate_call(
    stmts: List[ast.stmt],
    imports: Dict[str, Tuple[Optional[str], int, str]],
    container_package: str,
    container_module=None,
    skip_names: Set[str] = frozenset(),
) -> Optional[DelegateCall]:
    """Find the delegate handler call in `stmts`. The callee is resolved either
    via a local import collected into `imports`, or -- if `container_module`
    is given -- as a same-module function (laws.py's route function calls
    get_laws/get_law_details directly, with no import at all, since they live
    in the same file)."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name in skip_names:
                    continue
                kwarg_names = {kw.arg for kw in node.keywords if kw.arg is not None}
                has_star_kwargs = any(kw.arg is None for kw in node.keywords)

                if name in imports:
                    module, level, orig_name = imports[name]
                    rel_name = "." * level + (module or "")
                    resolved_module = importlib.import_module(rel_name, package=container_package)
                    return DelegateCall(
                        module_name=resolved_module.__name__,
                        orig_name=orig_name,
                        kwarg_names=kwarg_names,
                        has_star_kwargs=has_star_kwargs,
                    )

                if container_module is not None:
                    candidate = getattr(container_module, name, None)
                    if inspect.iscoroutinefunction(candidate):
                        return DelegateCall(
                            module_name=container_module.__name__,
                            orig_name=name,
                            kwarg_names=kwarg_names,
                            has_star_kwargs=has_star_kwargs,
                        )
    return None


def _extract_operation_literal(test: ast.expr) -> Optional[str]:
    if (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name) and test.left.id == "operation"
        and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and isinstance(test.comparators[0].value, str)
    ):
        return test.comparators[0].value
    return None


def _parse_bucket_dispatch(route_fn: Callable, container_package: str) -> Dict[str, DelegateCall]:
    """Walk a route_<name>_operation if/elif chain, returning operation ->
    DelegateCall for each `if operation == "x": ... <handler>(...)` branch."""
    src = textwrap.dedent(inspect.getsource(route_fn))
    tree = ast.parse(src)
    fn_node = tree.body[0]
    result: Dict[str, DelegateCall] = {}
    container_module = inspect.getmodule(route_fn)

    def walk_chain(if_node: ast.If) -> None:
        op_value = _extract_operation_literal(if_node.test)
        if op_value is not None:
            imports = _collect_local_imports(if_node.body)
            call = _find_delegate_call(
                if_node.body, imports, container_package,
                container_module=container_module, skip_names={route_fn.__name__},
            )
            if call is not None:
                result[op_value] = call
        for stmt in if_node.orelse:
            if isinstance(stmt, ast.If):
                walk_chain(stmt)

    for stmt in fn_node.body:
        if isinstance(stmt, ast.If):
            walk_chain(stmt)

    return result


def _parse_flat_delegate(tool_fn: Callable, container_package: str) -> Optional[DelegateCall]:
    src = textwrap.dedent(inspect.getsource(tool_fn))
    tree = ast.parse(src)
    fn_node = tree.body[0]
    imports = _collect_local_imports(fn_node.body)
    container_module = inspect.getmodule(tool_fn)
    return _find_delegate_call(
        fn_node.body, imports, container_package,
        container_module=container_module, skip_names={tool_fn.__name__},
    )


def _find_route_function(module) -> Optional[Callable]:
    for name, obj in vars(module).items():
        if name.startswith("route_") and name.endswith("_operation") and inspect.isfunction(obj):
            return obj
    return None


# --------------------------------------------------------------------------
# Core comparison
# --------------------------------------------------------------------------

def _audit_operation(
    tool_name: str,
    operation: str,
    schema_params: Set[str],
    always_forwarded: Set[str],
    forwarded_params: Set[str],
    handler: Callable,
) -> OperationAudit:
    audit = OperationAudit(
        tool_name=tool_name,
        operation=operation,
        handler_qualname=f"{handler.__module__}.{handler.__qualname__}",
    )
    handler_sig = inspect.signature(handler)
    handler_params = _param_names(handler_sig)
    handler_has_kwargs = _has_var_keyword(handler_sig)
    always_forwarded = always_forwarded & forwarded_params

    if not handler_has_kwargs:
        audit.extra = forwarded_params - handler_params
        audit.extra_always = audit.extra & always_forwarded

    audit.missing_from_schema = handler_params - schema_params
    # Only meaningful if the handler would actually have accepted it -- a
    # bucket route function that deliberately narrows kwargs per operation
    # (e.g. laws.py) "drops" plenty of schema params its handler never
    # declared anyway, which is correct scoping, not a bug.
    audit.dropped_by_wrapper = (schema_params - forwarded_params) & handler_params

    reachable = forwarded_params & handler_params
    if reachable:
        body_names = _body_referenced_names(handler)
        audit.unused_in_body = {p for p in reachable if p not in body_names}

    return audit


def run_audit() -> List[OperationAudit]:
    from congress_api.mcp_server import mcp, initialize_mcp_features

    initialize_mcp_features()
    tools = mcp._tool_manager.list_tools()

    results: List[OperationAudit] = []
    for tool in tools:
        tool_fn = tool.fn
        module = inspect.getmodule(tool_fn)
        schema_sig = inspect.signature(tool_fn)
        route_fn = _find_route_function(module)

        if route_fn is not None and "operation" in schema_sig.parameters:
            # Bucket tool: schema forwards its full (non-None) param set to
            # every operation via **kwargs, so forwarded == schema for all of
            # them by construction.
            dispatch = _parse_bucket_dispatch(route_fn, module.__package__)
            schema_params = _param_names(schema_sig) - {"operation"}
            always_forwarded = _non_none_default_params(schema_sig) - {"operation"}
            if not dispatch:
                results.append(OperationAudit(
                    tool_name=tool.name, operation="*", handler_qualname="?",
                    error=f"could not parse any operations out of {route_fn.__qualname__}",
                ))
                continue
            for operation, call in dispatch.items():
                forwarded = set(call.kwarg_names)
                if call.has_star_kwargs:
                    forwarded |= schema_params
                try:
                    handler_module = importlib.import_module(call.module_name)
                    handler = getattr(handler_module, call.orig_name)
                except Exception as e:  # pragma: no cover - defensive
                    results.append(OperationAudit(
                        tool_name=tool.name, operation=operation, handler_qualname=call.orig_name,
                        error=f"could not resolve handler: {e}",
                    ))
                    continue
                results.append(_audit_operation(tool.name, operation, schema_params, always_forwarded, forwarded, handler))
        else:
            # Flat tool: the tool function IS the operation.
            call = _parse_flat_delegate(tool_fn, module.__package__)
            if call is None:
                results.append(OperationAudit(
                    tool_name=tool.name, operation=tool.name, handler_qualname="?",
                    error="could not find a delegate call in the tool body",
                ))
                continue
            forwarded = set(call.kwarg_names)
            schema_params = _param_names(schema_sig)
            always_forwarded = _non_none_default_params(schema_sig)
            if call.has_star_kwargs:
                forwarded |= schema_params
            try:
                handler_module = importlib.import_module(call.module_name)
                handler = getattr(handler_module, call.orig_name)
            except Exception as e:  # pragma: no cover - defensive
                results.append(OperationAudit(
                    tool_name=tool.name, operation=tool.name, handler_qualname=call.orig_name,
                    error=f"could not resolve handler: {e}",
                ))
                continue
            results.append(_audit_operation(tool.name, tool.name, schema_params, always_forwarded, forwarded, handler))

    return results


# --------------------------------------------------------------------------
# Reporting / CLI
# --------------------------------------------------------------------------

def format_report(results: List[OperationAudit], *, apply_allowlist: bool) -> Tuple[str, bool]:
    """Returns (report_text, has_blocking_findings). Prints every finding,
    including informational-only ones (see OperationAudit.blocking), but only
    informational/plain EXTRA findings don't affect the returned bool."""
    lines = []
    any_findings = False
    any_blocking = False
    for a in sorted(results, key=lambda r: (r.tool_name, r.operation)):
        view = a.filtered() if apply_allowlist else a
        if view.clean:
            continue
        any_findings = True
        any_blocking = any_blocking or view.blocking
        tag = "" if view.blocking else "  (informational only)"
        lines.append(f"\n{a.tool_name} :: {a.operation}  ({a.handler_qualname}){tag}")
        if view.error:
            lines.append(f"  ERROR: {view.error}")
        if view.extra:
            marker = " [ALWAYS TRIGGERS]" if view.extra_always else ""
            always_note = f" (always: {sorted(view.extra_always)})" if view.extra_always else ""
            lines.append(f"  EXTRA (handler rejects){marker}: {sorted(view.extra)}{always_note}")
        if view.missing_from_schema:
            lines.append(f"  MISSING FROM SCHEMA (handler supports, schema hides): {sorted(view.missing_from_schema)}")
        if view.dropped_by_wrapper:
            lines.append(f"  DROPPED BY WRAPPER (schema has it, never forwarded): {sorted(view.dropped_by_wrapper)}")
        if view.unused_in_body:
            lines.append(f"  UNUSED IN BODY (accepted, no effect): {sorted(view.unused_in_body)}")

    header = f"Audited {len(results)} (tool, operation) pairs."
    if not any_findings:
        header += " No drift found." if apply_allowlist else " No drift found (including allowlisted)."
    elif not any_blocking:
        header += " No CI-blocking drift found (informational-only findings below)."
    return header + "".join(lines), any_blocking


def main() -> int:
    check_mode = "--check" in sys.argv
    results = run_audit()
    report, has_blocking = format_report(results, apply_allowlist=True)
    print(report)
    if check_mode:
        return 1 if has_blocking else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
