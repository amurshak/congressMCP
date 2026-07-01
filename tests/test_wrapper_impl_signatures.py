"""
Static wrapper -> impl signature conformance.

The live audit harness probes impls directly, so it is structurally BLIND to
wrapper/impl signature mismatches (the #28 / search_committees class: a tool
wrapper forwarding a kwarg the impl doesn't accept, or omitting a required one).
This test closes that gap with zero network: for each delegating wrapper in
members_committees_tools, it extracts the kwargs the wrapper forwards to its impl
(via AST) and asserts (a) every forwarded kwarg is accepted by the impl, and
(b) every required impl param is forwarded.
"""
import ast
import importlib
import inspect
import textwrap

import congress_api.features.members_committees_tools as mct

# wrapper tool name -> (impl module under congress_api.features, impl func name)
DELEGATIONS = {
    "search_members": ("members", "search_members"),
    "get_member_details": ("members", "get_member_details"),
    "get_member_sponsored_legislation": ("members", "get_member_sponsored_legislation"),
    "get_member_cosponsored_legislation": ("members", "get_member_cosponsored_legislation"),
    "get_members_by_congress": ("members", "get_members_by_congress"),
    "get_members_by_state": ("members", "get_members_by_state"),
    "get_members_by_district": ("members", "get_members_by_district"),
    "get_members_by_congress_state_district": ("members", "get_members_by_congress_state_district"),
    "search_committees": ("committees", "search_committees"),
    "get_committee_bills": ("committees", "get_committee_bills"),
    "get_committee_reports": ("committees", "get_committee_reports"),
    "get_committee_communications": ("committees", "get_committee_communications"),
    "get_committee_nominations": ("committees", "get_committee_nominations"),
}


def _forwarded_kwargs(wrapper_fn):
    """Return the set of keyword names the wrapper forwards in its impl call.

    Finds the awaited call whose first positional arg is `ctx` (the impl
    delegation) and collects its keyword argument names.
    """
    src = textwrap.dedent(inspect.getsource(wrapper_fn))
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id == "ctx":
            return {kw.arg for kw in node.keywords if kw.arg is not None}
    return set()


def _impl(mod, fn):
    module = importlib.import_module(f"congress_api.features.{mod}")
    return getattr(module, fn)


def test_wrappers_forward_only_accepted_kwargs():
    """No wrapper may forward a kwarg the impl doesn't accept (the #28 class)."""
    failures = []
    for tool, (mod, fn) in DELEGATIONS.items():
        impl_params = set(inspect.signature(_impl(mod, fn)).parameters)
        forwarded = _forwarded_kwargs(getattr(mct, tool))
        extra = forwarded - impl_params
        if extra:
            failures.append(f"{tool} -> {mod}.{fn} forwards unaccepted kwargs: {sorted(extra)}")
    assert not failures, "\n".join(failures)


def test_wrappers_supply_all_required_impl_params():
    """Every required impl param (no default) must be forwarded by the wrapper."""
    failures = []
    for tool, (mod, fn) in DELEGATIONS.items():
        sig = inspect.signature(_impl(mod, fn))
        required = {
            name for name, p in sig.parameters.items()
            if name != "ctx"
            and p.default is inspect.Parameter.empty
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
        }
        forwarded = _forwarded_kwargs(getattr(mct, tool))
        missing = required - forwarded
        if missing:
            failures.append(f"{tool} -> {mod}.{fn} missing required params: {sorted(missing)}")
    assert not failures, "\n".join(failures)
