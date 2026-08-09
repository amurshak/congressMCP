"""MCP tools for searching and retrieving bill text sections."""

from __future__ import annotations

import functools
import logging
import re
import time
from typing import Any

from mcp.server.mcpserver import Context

from ...mcp_app import mcp
from . import trace
from .client import BillTextError, govinfo_details_url
from .index import fts_literal, has_token, normalized_query, sqlite_supports_fts5
from .models import (
    AncestorNode,
    BillSectionResponse,
    BillTocResponse,
    CacheStatus,
    ErrorEnvelope,
    ErrorPayload,
    QueryDiagnostic,
    SearchBillTextResponse,
    SearchHit,
    SectionChild,
    Timing,
    TocNode,
)
from .parser import Unit, node_kind_for, render_segments
from .service import LoadedBillText, load_bill_text


logger = logging.getLogger(__name__)


def _debug_logged(fn):
    """DEBUG-ONLY out-of-band tracing (see trace.py). When CONGRESSMCP_TRACE_DIR is set,
    each invocation + the exact returned response is appended as a JSONL record, with the
    API key redacted at write time. Off (and zero-cost past one env check) otherwise.
    functools.wraps preserves __wrapped__, so the MCP schema (built via inspect.signature)
    sees the real keyword-only signature unchanged."""

    @functools.wraps(fn)
    async def wrapper(ctx, *args, **kwargs):
        if not trace.enabled():
            return await fn(ctx, *args, **kwargs)
        trace.clear_source()  # don't let a prior call's provenance leak if load fails
        started = time.perf_counter()
        result = await fn(ctx, *args, **kwargs)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        trace.write(fn.__name__, kwargs, result, duration_ms)
        return result

    return wrapper


def _error(code: str, message: str, detail: dict[str, Any] | None = None, remediation: str | None = None) -> dict[str, Any]:
    # Redact at the single construction point for EVERY error path, present and
    # future, rather than at the paths known to interpolate an exception today.
    # An error envelope is a worse disclosure channel than a log: it reaches the
    # CALLER, not just the operator. The live case is httpx's raise_for_status,
    # whose message embeds the full request URL -- and the congress.gov client
    # carries the key as a query parameter (§11, pre-existing), so
    # `f"...: {exc}"` puts a live credential in a field the caller receives.
    if detail is not None:
        detail = {
            key: trace.redact(value) if isinstance(value, str) else value
            for key, value in detail.items()
        }
    return ErrorEnvelope(
        error=ErrorPayload(
            code=code,
            message=trace.redact(message),
            detail=detail,
            remediation=trace.redact(remediation) if remediation else remediation,
        )
    ).model_dump()


def _unexpected(tool: str, exc: Exception) -> dict[str, Any]:
    # The MCP SDK turns an uncaught tool exception into a terse client string and
    # logs no traceback. Log it to stderr (captured in the MCP server log) so the
    # failure is debuggable, and hand the model a structured error instead.
    logger.exception("Unexpected error in %s", tool)
    return _error(
        "internal_error",
        f"{tool} failed unexpectedly: {type(exc).__name__}: {exc}",
        None,
        "Server-side bug; see the traceback in the MCP server log (mcp-server-<name>.log).",
    )


def _capability_error() -> dict[str, Any] | None:
    if sqlite_supports_fts5():
        return None
    import sqlite3
    import sys

    return _error(
        "fts5_unavailable",
        "Bill text search requires SQLite FTS5, but this Python SQLite build does not provide it.",
        {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version},
        "Use a Python build linked against SQLite with FTS5 enabled.",
    )


def _timing(loaded: LoadedBillText, started: float, search_ms: float | None = None) -> Timing:
    return Timing(
        **loaded.timing,
        search_ms=search_ms,
        total_ms=round((time.perf_counter() - started) * 1000, 1),
    )


def _envelope(loaded: LoadedBillText) -> dict[str, Any]:
    return {
        "package_id": loaded.resolved.package_id,
        "version": loaded.resolved.version,
        "version_resolution": "fresh",
        "version_resolved_at": loaded.resolved.version_resolved_at,
        # version_resolution_note is intentionally omitted here: each tool passes
        # it explicitly so it can merge in the input-clamp note.
        "source_format": "bill_dtd",
        "last_modified": loaded.resolved.last_modified,
        "govinfo_url": govinfo_details_url(loaded.resolved.package_id),
        "cache": CacheStatus(index_hit=False, version_hit=False).model_dump(),
        "sections_indexed": loaded.parsed.sections_indexed,
        "chunks_indexed": len(loaded.parsed.units),
        "struck_text_note": _struck_text_note(loaded),
    }


def _struck_text_note(loaded: LoadedBillText) -> str | None:
    """Disclose committee-struck text that was excluded from the index (F4).

    Names the count and where the text can still be read. An exclusion the caller is
    not told about is the defect-#2 shape -- substance silently absent -- and the
    caller cannot infer it, because a reported bill with its original struck looks
    exactly like a reported bill that changed nothing.
    """
    excluded = loaded.parsed.struck_sections_excluded
    if not excluded:
        return None
    return (
        f"{excluded} section(s) struck by committee in this reported version were "
        "excluded: they appear in the document with strikethrough markup but are not "
        "part of the bill as reported, so they are neither searchable nor citable "
        "here. The text as it stood before the committee acted is available by "
        "requesting the prior version (e.g. version='is' or 'ih')."
    )


def _normalize_queries(queries: list[str]) -> tuple[list[str], dict[str, str], list[str]]:
    notes: list[str] = []
    if len(queries) > 8:
        raise ValueError("len(queries) must be 8 or fewer.")
    seen = set()
    normalized = []
    display = {}
    for query in queries:
        if len(query) > 200:
            raise ValueError(f"Query exceeds 200 characters: {query[:40]}")
        norm = normalized_query(query)
        if not norm or not has_token(norm):
            raise ValueError(f"Query has no alphanumeric tokens after tokenization: {query!r}")
        if norm not in seen:
            seen.add(norm)
            normalized.append(norm)
            display[norm] = re.sub(r"\s+", " ", query).strip()
    if not normalized:
        raise ValueError("At least one non-empty query is required.")
    return normalized, display, notes


def _query_diagnostic(index, normalized: str, shown: str) -> QueryDiagnostic:
    # `shown` is the caller's own phrasing, not the normalized form: a diagnostic the
    # caller cannot match back to what they typed is one more thing to decode.
    diagnosis = index.diagnose(normalized)
    return QueryDiagnostic(
        query=shown,
        terms=diagnosis.terms,
        absent_terms=diagnosis.absent,
        verdict=diagnosis.verdict,
    )


def _clamp(value: int, low: int, high: int) -> tuple[int, str | None]:
    clamped = min(high, max(low, value))
    if clamped == value:
        return clamped, None
    return clamped, f"Value {value} was clamped to {clamped}; allowed range is {low}-{high}."


@mcp.tool(
    "search_bill_text",
    title="Search a bill's full statutory text by section (GovInfo)",
)
@_debug_logged
async def search_bill_text(
    ctx: Context,
    *,
    congress: int,
    bill_type: str,
    number: int,
    queries: list[str],
    version: str | None = None,
    max_hits: int = 10,
) -> dict[str, Any]:
    """
    Full-text search of a bill's statutory text (bill text / legislative text), parsed from
    GovInfo Bill DTD XML with segment-level FTS5, returning matching sections with the
    U.S. Code and Public Law citations they amend.

    Use this to answer "what does bill X say about Y" without reading the whole bill.

    Queries match as LITERAL PHRASES WITH STEMMING -- not bag-of-words, and not semantically.
    A query hits only where the bill contains that phrase verbatim, so a description of a topic
    finds nothing: "Space Force end strength" returns zero against a bill containing both "End
    strengths for active forces" and "Space Force". Prefer several short phrases you expect to
    appear verbatim, plus synonyms, in one call, e.g. ["icebreaker", "polar security cutter"];
    matched_queries reports which phrasing produced each hit, so you can drop the dead ones next call.

    A query that matches nothing gets an entry in query_diagnostics saying why, so zero hits is
    readable rather than ambiguous. verdict "phrasing" means every term IS in the bill but not as
    this contiguous phrase -- rephrase, do not conclude the bill is silent. verdict "absent_term"
    means absent_terms appear nowhere in the bill, so no rephrasing of them will help. terms shows
    the stemmed tokens actually searched ("Force" -> "forc"), which is where a phrase stops
    meaning what you typed.

    Knowing a provision as codified law does NOT establish where it sits in THIS bill. Division,
    title, and section numbers are properties of this document, and these tools are the only
    source for them -- answering a bill-location question from prior knowledge produces a
    confident, correctly-quoted, wrongly-cited answer. Call the tool instead.

    If "quoted" appears in match_contexts, the hit may include language the bill is removing,
    even when "operative" also appears; presence of "quoted" governs. Each amends entry is
    {kind: "usc"|"public_law", cite}; amends is a convenience (never named Acts, incl. the IRC by
    bare section number) -- use is_amendatory and match_contexts to identify amendatory text.
    max_hits is clamped to 1-50.
    """
    capability_error = _capability_error()
    if capability_error:
        return capability_error
    try:
        started = time.perf_counter()
        max_hits, note = _clamp(max_hits, 1, 50)
        normalized, display, _ = _normalize_queries(queries)
        loaded = await load_bill_text(ctx, congress, bill_type, number, version)
        search_start = time.perf_counter()
        ranked = loaded.index.search(normalized, max_hits)
        search_ms = round((time.perf_counter() - search_start) * 1000, 1)
        # F10: diagnose every query that matched nothing -- which covers the all-zero
        # response and the individually-dead query in an otherwise successful call,
        # since both leave the caller unable to tell "absent" from "worded otherwise".
        productive = {item for hit in ranked for item in hit.matched_queries}
        diagnostics = [
            _query_diagnostic(loaded.index, item, display[item])
            for item in normalized
            if item not in productive
        ]
        response = SearchBillTextResponse(
            **_envelope(loaded),
            version_resolution_note=note or loaded.resolved.version_resolution_note,
            timing=_timing(loaded, started, search_ms=search_ms),
            chunks_searched=len(loaded.parsed.units),
            queries_used=[display[item] for item in normalized],
            query_diagnostics=diagnostics or None,
            hits=[
                SearchHit(
                    section_id=hit.unit.section_id,
                    node_kind=node_kind_for(hit.unit.section_id),
                    ancestor_path=hit.unit.ancestor_path,
                    header=hit.unit.header,
                    snippet=hit.snippet,
                    match_contexts=hit.match_contexts,
                    matched_queries=[display[item] for item in hit.matched_queries],
                    is_amendatory=hit.unit.is_amendatory,
                    amends=hit.unit.amends,
                    score=round(hit.score, 6),
                    byte_length=hit.unit.byte_length,
                    subtree_byte_length=loaded.parsed.subtree_bytes.get(
                        hit.unit.section_id, hit.unit.byte_length
                    ),
                )
                for hit in ranked
            ],
        )
        return response.model_dump()
    except BillTextError as exc:
        return _error(exc.code, exc.message, exc.detail, exc.remediation)
    except ValueError as exc:
        return _error("invalid_request", str(exc), None, "Adjust the input and retry.")
    except Exception as exc:
        return _unexpected("search_bill_text", exc)


@mcp.tool(
    "get_bill_section",
    title="Retrieve the full statutory text of a bill section (GovInfo)",
)
@_debug_logged
async def get_bill_section(
    ctx: Context,
    *,
    congress: int,
    bill_type: str,
    number: int,
    section_id: str,
    version: str | None = None,
    max_bytes: int = 25_000,
) -> dict[str, Any]:
    """
    Retrieve the full statutory text of a single bill section -- or an addressable sub-section
    chunk -- parsed from the bill's GovInfo Bill DTD XML.

    Call this after search_bill_text or get_bill_toc to read a specific section by its section_id
    (e.g. "D:H/T:I/S:3501"). Fully-qualified section ids and chunk ids resolve directly; a bare
    section number (e.g. "101") resolves only when it is unique across the bill. Every id
    get_bill_toc returns resolves here, including structural containers such as a division,
    title, or subtitle ("D:C/T:XXXI/ST:B"), which return their heading plus child descriptors
    when the subtree exceeds max_bytes. The returned text
    carries operative and quoted (amendatory) language in reading order; when the section is
    subdivided, child chunk descriptors are included. Text is capped at max_bytes, measured as
    UTF-8 encoded bytes of the returned text field, clamped to 1,000-100,000.
    """
    capability_error = _capability_error()
    if capability_error:
        return capability_error
    try:
        started = time.perf_counter()
        max_bytes, note = _clamp(max_bytes, 1_000, 100_000)
        loaded = await load_bill_text(ctx, congress, bill_type, number, version)
        unit_or_error = _resolve_unit(loaded.parsed.units, section_id)
        if isinstance(unit_or_error, dict):
            # F5: before reporting section_not_found, try resolving the id as a
            # structural container. Only section_not_found falls through --
            # ambiguous_section_id is a real answer (§5 forbids guessing) and must
            # not be swallowed here.
            if unit_or_error["error"]["code"] != "section_not_found":
                return unit_or_error
            container = _resolve_container(
                loaded.parsed.units, _normalize_requested_id(section_id.strip())
            )
            if container is None:
                return unit_or_error
            return _container_response(loaded, container, started, note, max_bytes)
        unit = unit_or_error
        # Preserve document order via child_ids (a subdivided parent lists its
        # leaves in order); the units list is also in that order, but keying makes
        # it explicit.
        child_by_id = {child.section_id: child for child in loaded.parsed.units}
        children = [child_by_id[cid] for cid in unit.child_ids if cid in child_by_id]
        subtree = loaded.parsed.subtree_bytes
        subtree_len = subtree.get(unit.section_id, unit.byte_length)
        # Render at serialization: quoted spans are wrapped in delimiters here, not
        # in storage (spec §6). byte machinery (byte_length / subtree / byte_split)
        # stays on the clean display_text; only the returned `text` is rendered.
        own_rendered = render_segments(unit.segments)
        if children and subtree_len <= max_bytes:
            # Subdivided but the whole section fits: assemble it at read time. The
            # parent unit stores only its own header+intro (its byte_length is that
            # intro, e.g. 73 B), so §5's "parent fits max_bytes -> return whole
            # section" is served by concatenating the children here rather than
            # reading a single parent field (spec §9).
            full = "\n\n".join(
                part
                for part in (own_rendered, *(render_segments(c.segments) for c in children))
                if part
            )
            text = _limit_utf8(full, max_bytes)
            truncated = len(full.encode("utf-8")) > max_bytes
        elif children:
            # Subdivided and too large to inline: own header + intro plus child
            # descriptors so the caller can fetch a specific chunk. Never silently
            # return only the first chunk (spec §5).
            text = _limit_utf8(own_rendered, max_bytes)
            truncated = True
        else:
            # Leaf: its own text, truncated only if that alone exceeds max_bytes.
            text = _limit_utf8(own_rendered, max_bytes)
            truncated = len(own_rendered.encode("utf-8")) > max_bytes
        child_payload = (
            [
                SectionChild(
                    section_id=child.section_id,
                    node_kind=node_kind_for(child.section_id),
                    header=child.header,
                    byte_length=child.byte_length,
                    subtree_byte_length=subtree.get(child.section_id, child.byte_length),
                )
                for child in children
            ]
            if children
            else None
        )
        return BillSectionResponse(
            **_envelope(loaded),
            version_resolution_note=note or loaded.resolved.version_resolution_note,
            timing=_timing(loaded, started),
            section_id=unit.section_id,
            node_kind=node_kind_for(unit.section_id),
            ancestor_path=unit.ancestor_path,
            header=unit.header,
            text=text,
            # byte_length is the unit's OWN clean text size (spec §9), NOT the
            # rendered/concatenated payload: rendering adds ~2 bytes per quoted span
            # and concatenation inflates it, which made section disagree with search
            # on the same node and made subtree_byte_length read *smaller* than
            # byte_length on quoted leaves. Reporting the clean own size restores
            # `subtree_byte_length >= byte_length` and cross-tool agreement; the
            # returned `text` is still rendered and bounded by max_bytes.
            byte_length=unit.byte_length,
            subtree_byte_length=subtree_len,
            truncated=truncated,
            children=child_payload,
        ).model_dump()
    except BillTextError as exc:
        return _error(exc.code, exc.message, exc.detail, exc.remediation)
    except Exception as exc:
        return _unexpected("get_bill_section", exc)


@mcp.tool(
    "get_bill_toc",
    title="Bill statutory-text table of contents for section navigation (GovInfo)",
)
@_debug_logged
async def get_bill_toc(
    ctx: Context,
    *,
    congress: int,
    bill_type: str,
    number: int,
    version: str | None = None,
    depth: int = 2,
) -> dict[str, Any]:
    """
    Get a shallow table of contents -- divisions, titles, subtitles, and sections -- for a bill's
    statutory text from GovInfo, as a navigation aid for discovering the section_id values to pass
    to get_bill_section or search_bill_text.

    This is a navigation aid, not the answer path: it returns structure and headers, never the
    statutory text itself. depth is clamped to 1-5 (default 2) and total nodes are capped at 500.

    Two different things can be incomplete, and they are reported separately. depth_reduced is
    true when the node cap served a shallower tree than you asked for -- compare depth against
    requested_depth to see by how much. toc_truncated is true when more exists below what you
    got, which includes the case where your depth was honored in full; toc_note then gives the
    depth needed to reveal the rest, or says so when no depth can.
    """
    capability_error = _capability_error()
    if capability_error:
        return capability_error
    try:
        started = time.perf_counter()
        depth, note = _clamp(depth, 1, 5)
        loaded = await load_bill_text(ctx, congress, bill_type, number, version)
        toc, node_capped, actual_depth, list_truncated = _toc_nodes(
            loaded.parsed.units, depth, loaded.parsed.subtree_bytes
        )
        # A node showing children:[] at the depth boundary is indistinguishable
        # from a genuinely empty one, so a consumer reads "this subtitle has no
        # sections" and stops. Detect sections that nest below the returned depth
        # and disclose them rather than letting toc_truncated=false assert
        # completeness that isn't there.
        hidden_note = _hidden_section_note(
            loaded.parsed.units, actual_depth, depth, loaded.parsed.subtree_bytes
        )
        notes: list[str] = []
        if note:
            notes.append(note)
        if node_capped:
            # Always stated, even alongside hidden_note (F11). hidden_note explains
            # what is MISSING from the tree; it never says the depth argument was
            # overridden, and its remedy is phrased in terms of the depth actually
            # served -- so on its own it reads as if the request had been honored.
            notes.append(
                f"Requested depth {depth} was reduced to {actual_depth} by the 500-node cap."
            )
        if list_truncated:
            # Distinct from a depth reduction and previously undisclosed: the tree is
            # at the requested depth but nodes were dropped off the end of the list.
            notes.append(
                "The node list was cut at the 500-node cap, so some top-level nodes are "
                "missing entirely; use search_bill_text to reach them."
            )
        if hidden_note:
            notes.append(hidden_note)
        return BillTocResponse(
            **_envelope(loaded),
            version_resolution_note=loaded.resolved.version_resolution_note,
            timing=_timing(loaded, started),
            requested_depth=depth,
            depth=actual_depth,
            depth_reduced=node_capped,
            toc_truncated=node_capped or list_truncated or hidden_note is not None,
            toc_note=" ".join(notes) or None,
            toc=toc,
        ).model_dump()
    except BillTextError as exc:
        return _error(exc.code, exc.message, exc.detail, exc.remediation)
    except Exception as exc:
        return _unexpected("get_bill_toc", exc)


def _container_response(
    loaded: LoadedBillText, container: _Container, started: float, note: str | None, max_bytes: int
) -> dict[str, Any]:
    """Serve a container exactly as §5 serves a subdivided parent: assemble the whole
    subtree when it fits in max_bytes, otherwise return its heading plus child
    descriptors with truncated=true. Never silently return only the first child."""
    subtree = loaded.parsed.subtree_bytes
    subtree_len = subtree.get(container.section_id, 0)
    children = _container_children(container, loaded.parsed.units, subtree)
    if subtree_len <= max_bytes:
        full = "\n\n".join(
            part
            for part in (
                container.header or "",
                *(render_segments(unit.segments) for unit in container.descendants),
            )
            if part
        )
        text = _limit_utf8(full, max_bytes)
        truncated = len(full.encode("utf-8")) > max_bytes
    else:
        text = _limit_utf8(container.header or "", max_bytes)
        truncated = True
    return BillSectionResponse(
        **_envelope(loaded),
        version_resolution_note=note or loaded.resolved.version_resolution_note,
        timing=_timing(loaded, started),
        section_id=container.section_id,
        node_kind=node_kind_for(container.section_id),
        ancestor_path=container.ancestor_path,
        header=container.header,
        text=text,
        # 0 for the same reason as in _container_children: a container's heading is
        # not an indexed unit, so counting it would break the containment identity
        # and disagree with the same node in get_bill_toc.
        byte_length=0,
        subtree_byte_length=subtree_len,
        truncated=truncated,
        children=children,
    ).model_dump()


class _Container:
    """A TOC node that is a structural container (`D:C/T:XXXI/ST:B`) rather than an
    emitted unit: a parent whose own text is a heading.

    F5: the TOC's id namespace is a SUPERSET of the section namespace, and nothing
    marked the difference -- `node_kind` reported `structural` for a subtitle and a
    leaf section alike -- so an id copied verbatim out of a TOC response returned
    section_not_found, and the remediation then named get_bill_toc, the tool that had
    just supplied the id. §4 resolves containers instead of marking them, reusing the
    header-plus-`children`-descriptors shape §5 already defines for a subdivided
    parent, so TOC -> section -> child works end to end and nothing new is introduced.
    """

    def __init__(self, section_id: str, ancestor_path, node, descendants: list[Unit]):
        self.section_id = section_id
        self.ancestor_path = ancestor_path
        self.header = node.header
        self.descendants = descendants


def _resolve_container(units: list[Unit], requested: str) -> _Container | None:
    """Build a container view for `requested` if any unit sits beneath it."""
    prefix = f"{requested}/"
    descendants = [unit for unit in units if unit.section_id.startswith(prefix)]
    if not descendants:
        return None
    depth = len(requested.split("/"))
    anchor = descendants[0]
    if len(anchor.ancestor_path) >= depth:
        # Normal case: the container's own node sits at index depth-1 of a
        # descendant's ancestor_path, and everything above it is its ancestry.
        node = anchor.ancestor_path[depth - 1]
    else:
        # The container lies BELOW where ancestor_path reaches. This is the
        # byte-split section: byte_split_unit replaces the section unit with its
        # CHUNK units, which carry the section's ancestor_path (stopping at the
        # title) and its header. So `D:D/T:XLVII/S:4701` names a real, citable
        # section that is not itself a unit -- 5 such sections on s1071, every one
        # rejected until now even though the TOC lists them. Rebuild the node from
        # the id component and take the header from the chunks, which inherit it.
        typ, _, enum = requested.split("/")[-1].partition(":")
        node = AncestorNode(type=typ, enum=enum, header=anchor.header)
    return _Container(requested, anchor.ancestor_path[: depth - 1], node, descendants)


def _container_children(container: _Container, units: list[Unit], subtree: dict[str, int]) -> list[SectionChild]:
    """Immediate children of a container, in document order: emitted units where the
    next level down is a real unit, nested containers otherwise."""
    by_id = {unit.section_id: unit for unit in units}
    depth = len(container.section_id.split("/"))
    seen: list[str] = []
    for unit in container.descendants:
        child_id = "/".join(unit.section_id.split("/")[: depth + 1])
        if child_id not in seen:
            seen.append(child_id)
    children = []
    for child_id in seen:
        child = by_id.get(child_id)
        if child is not None:
            children.append(
                SectionChild(
                    section_id=child_id,
                    node_kind=node_kind_for(child_id),
                    header=child.header,
                    byte_length=child.byte_length,
                    subtree_byte_length=subtree.get(child_id, child.byte_length),
                )
            )
            continue
        nested = _resolve_container(units, child_id)
        children.append(
            SectionChild(
                section_id=child_id,
                node_kind=node_kind_for(child_id),
                header=nested.header if nested else None,
                # A container's own heading is display only -- it is not an indexed
                # unit, so it contributes nothing to the subtree sum. Reporting 0
                # keeps `subtree == own + Σ descendants` exact and keeps this field
                # in agreement with the same node as rendered by get_bill_toc.
                byte_length=0,
                subtree_byte_length=subtree.get(child_id, 0),
            )
        )
    return children


def _normalize_requested_id(requested: str) -> str:
    """Apply F2's trailing-period rule to an id the CALLER supplied.

    Ids no longer carry trailing periods (see parser.normalize_enum), so accepting
    the period form on input cannot collide with anything -- and a model copying
    "SEC. 804." out of the statutory text is the exact input that produced the
    false "no section matched" assertion. Strip per component so a qualified id
    (`D:H/T:I/S:3501.`) normalizes as readily as a bare enum.
    """
    parts = []
    for component in requested.split("/"):
        typ, sep, enum = component.partition(":")
        cleaned = (enum if sep else typ).strip().rstrip(".").strip()
        if not cleaned:
            parts.append(component)
        elif sep:
            parts.append(f"{typ.strip()}:{cleaned}")
        else:
            parts.append(cleaned)
    return "/".join(parts)


def _resolve_unit(units: list[Unit], requested: str) -> Unit | dict[str, Any]:
    requested = _normalize_requested_id(requested.strip())
    by_id = {unit.section_id: unit for unit in units}
    if requested in by_id:
        return by_id[requested]
    bare = requested.removeprefix("S:")
    matches = [unit for unit in units if unit.section_id.split("/")[-1] == f"S:{bare}" or unit.section_id.split("/")[-1] == bare]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        return _error(
            "ambiguous_section_id",
            f"Bare section id {requested!r} matched multiple sections.",
            {"matches": [unit.section_id for unit in matches]},
            "Retry with one of the qualified section_id values.",
        )
    return _error("section_not_found", f"No section or chunk matched {requested!r}.", None, "Use search_bill_text or get_bill_toc to find a valid section_id.")


def _limit_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


def _toc_nodes(
    units: list[Unit], depth: int, subtree_bytes: dict[str, int]
) -> tuple[list[TocNode], bool, int, bool]:
    """Build the deepest tree the 500-node cap allows, at or below `depth`.

    Returns (nodes, node_capped, actual_depth, list_truncated). The cap degrades in two
    distinguishable ways and F11 turns on telling them apart: it can serve a SHALLOWER
    tree than asked (actual_depth < depth), or -- when even depth 1 exceeds the cap --
    serve the requested depth with the node list CUT (list_truncated). The old single
    `node_capped` flag was true for both, so a caller could not tell "your depth was
    overridden" from "top-level nodes were dropped", and the second case reported a
    depth reduction that had not happened.
    """
    for actual_depth in range(depth, 0, -1):
        nodes = _build_toc(units, actual_depth, subtree_bytes)
        count = _count_toc(nodes)
        if count <= 500:
            return nodes, depth != actual_depth, actual_depth, False
    return _build_toc(units, 1, subtree_bytes)[:500], depth != 1, 1, True


def _build_toc(units: list[Unit], depth: int, subtree_bytes: dict[str, int]) -> list[TocNode]:
    """Build the TOC tree from each unit's ACTUAL section_id components.

    The id must never be reconstructed as `ancestor_path + leaf`. That holds only
    while ancestor_path covers every component but the last, and it does not for a
    byte-split chunk: `byte_split_unit` carries the PARENT's ancestor_path onto the
    chunk while appending `/CHUNK:{n}` to the parent's id, so the section component
    sits in neither. Reconstruction silently dropped it and emitted
    `D:D/T:XLVII/CHUNK:2` for a unit whose real id is `D:D/T:XLVII/S:4701/CHUNK:2`
    -- 28 such ids on s1071, every one of them referring to nothing, rejected by
    get_bill_section and missing from subtree_bytes (so they also reported size 0).
    Same failure as F5 -- the TOC handing out ids it invented -- via a second cause.
    The id is authoritative; ancestor_path supplies headers only.
    """
    roots: list[TocNode] = []
    node_map: dict[str, TocNode] = {}
    for unit in units:
        components = unit.section_id.split("/")
        parent = None
        for idx, component in enumerate(components[:depth]):
            sid = "/".join(components[: idx + 1])
            if sid not in node_map:
                typ, _, enum = component.partition(":")
                # Headers come from ancestor_path where it reaches; past its end the
                # remaining components belong to this unit (its own node, and any
                # chunk of it, which carries the parent header as a breadcrumb).
                header = (
                    unit.ancestor_path[idx].header
                    if idx < len(unit.ancestor_path)
                    else unit.header
                )
                toc_node = TocNode(
                    section_id=sid,
                    node_kind=node_kind_for(sid),
                    type=typ,
                    enum=enum,
                    header=header,
                    byte_length=unit.byte_length if idx == len(components) - 1 else 0,
                    # Size-per-branch: sum of own bytes at-or-under this prefix,
                    # so a consumer sees which division/title is worth descending
                    # into (spec §9 -- highest-value place for the field).
                    subtree_byte_length=subtree_bytes.get(sid, 0),
                )
                node_map[sid] = toc_node
                if parent is None:
                    roots.append(toc_node)
                else:
                    parent.children.append(toc_node)
            parent = node_map[sid]
    return roots


def _count_toc(nodes: list[TocNode]) -> int:
    total = 0
    stack = list(nodes)
    while stack:
        node = stack.pop()
        total += 1
        stack.extend(node.children)
    return total


# Section-level unit types (real addressable sections) as opposed to the
# sub-section chunk types (SS/PARA/SUBPARAGRAPH/CLAUSE) produced by subdivision.
# Only the former should drive "sections hidden below this depth"; advertising
# a deeper depth just to expose byte-split chunks would be navigation noise.
_SECTION_TYPES = {"S", "PRE", "RC", "U"}


def _section_unit_depth(unit: Unit) -> int:
    return len(unit.ancestor_path) + 1


def _is_section_level(unit: Unit) -> bool:
    typ = unit.section_id.split("/")[-1].split(":", 1)[0]
    return typ in _SECTION_TYPES


def _max_section_depth(units: list[Unit]) -> int:
    depths = [_section_unit_depth(unit) for unit in units if _is_section_level(unit)]
    return max(depths) if depths else 1


def _hidden_section_count(units: list[Unit], shown_depth: int) -> int:
    return sum(1 for unit in units if _is_section_level(unit) and _section_unit_depth(unit) > shown_depth)


def _hidden_section_note(
    units: list[Unit], actual_depth: int, requested_depth: int, subtree_bytes: dict[str, int]
) -> str | None:
    """Disclose sections that nest below the returned depth, with advice that is
    actually actionable.

    The trap: advising "call with depth={max_section_depth}" is wrong when the 500-node
    cap -- not the depth argument -- is what hid the sections. That deeper call rebuilds
    the same over-cap tree and degrades right back to this depth (the request the caller
    just made). So promise a depth only when the cap can serve it; otherwise the honest
    remedy is search_bill_text or narrowing to a subtree.
    """
    hidden = _hidden_section_count(units, actual_depth)
    if not hidden:
        return None
    required = _max_section_depth(units)
    # servable = the deepest depth the node cap actually permits (== actual_depth when
    # the caller already asked for the ceiling, else re-derived at the ceiling).
    servable = actual_depth if requested_depth >= 5 else _toc_nodes(units, 5, subtree_bytes)[2]
    if required <= servable:
        return (
            f"{hidden} section(s) nest below the returned depth {actual_depth} and are "
            f"collapsed into their parent nodes; call with depth={required} to see them, "
            f"or use search_bill_text."
        )
    return (
        f"{hidden} section(s) nest below the returned depth {actual_depth}; the full tree "
        f"cannot be listed to depth {required} (deepest listable depth is {servable}). Use "
        f"search_bill_text to find specific sections, or call get_bill_section on a division "
        f"or title to navigate its subtree."
    )
