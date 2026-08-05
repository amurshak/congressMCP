"""MCP tools for searching and retrieving bill text sections."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from mcp.server.mcpserver import Context

from ...mcp_app import mcp
from .client import BillTextError, govinfo_details_url
from .index import fts_literal, has_token, normalized_query, sqlite_supports_fts5
from .models import (
    BillSectionResponse,
    BillTocResponse,
    CacheStatus,
    ErrorEnvelope,
    ErrorPayload,
    SearchBillTextResponse,
    SearchHit,
    SectionChild,
    Timing,
    TocNode,
)
from .parser import Unit, node_kind_for, render_segments
from .service import LoadedBillText, load_bill_text


logger = logging.getLogger(__name__)


def _error(code: str, message: str, detail: dict[str, Any] | None = None, remediation: str | None = None) -> dict[str, Any]:
    return ErrorEnvelope(error=ErrorPayload(code=code, message=message, detail=detail, remediation=remediation)).model_dump()


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
    }


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


def _clamp(value: int, low: int, high: int) -> tuple[int, str | None]:
    clamped = min(high, max(low, value))
    if clamped == value:
        return clamped, None
    return clamped, f"Value {value} was clamped to {clamped}; allowed range is {low}-{high}."


@mcp.tool(
    "search_bill_text",
    title="Search a bill's full statutory text by section (GovInfo)",
)
async def search_bill_text(
    ctx: Context,
    congress: int,
    bill_type: str,
    number: int,
    queries: list[str],
    *,
    version: str | None = None,
    max_hits: int = 10,
) -> dict[str, Any]:
    """
    Full-text search of a bill's statutory text (bill text / legislative text), parsed from
    GovInfo Bill DTD XML with segment-level FTS5, returning matching sections with the
    U.S. Code and Public Law citations they amend.

    Use this to answer "what does bill X say about Y" without reading the whole bill.
    Pass several phrasings and synonyms in one call, e.g. ["icebreaker", "polar security cutter"];
    matched_queries reports which phrasing produced each hit, so you can drop the dead ones next call.
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
        response = SearchBillTextResponse(
            **_envelope(loaded),
            version_resolution_note=note or loaded.resolved.version_resolution_note,
            timing=_timing(loaded, started, search_ms=search_ms),
            chunks_searched=len(loaded.parsed.units),
            queries_used=[display[item] for item in normalized],
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
async def get_bill_section(
    ctx: Context,
    congress: int,
    bill_type: str,
    number: int,
    section_id: str,
    *,
    version: str | None = None,
    max_bytes: int = 25_000,
) -> dict[str, Any]:
    """
    Retrieve the full statutory text of a single bill section -- or an addressable sub-section
    chunk -- parsed from the bill's GovInfo Bill DTD XML.

    Call this after search_bill_text or get_bill_toc to read a specific section by its section_id
    (e.g. "D:H/T:I/S:3501"). Fully-qualified section ids and chunk ids resolve directly; a bare
    section number (e.g. "101") resolves only when it is unique across the bill. The returned text
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
            return unit_or_error
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
async def get_bill_toc(
    ctx: Context,
    congress: int,
    bill_type: str,
    number: int,
    *,
    version: str | None = None,
    depth: int = 2,
) -> dict[str, Any]:
    """
    Get a shallow table of contents -- divisions, titles, subtitles, and sections -- for a bill's
    statutory text from GovInfo, as a navigation aid for discovering the section_id values to pass
    to get_bill_section or search_bill_text.

    This is a navigation aid, not the answer path: it returns structure and headers, never the
    statutory text itself. depth is clamped to 1-5 (default 2) and total nodes are capped at 500.
    toc_truncated is true when the node cap forced a shallower tree OR sections nest below the
    returned depth (toc_note then gives the depth needed to reveal them).
    """
    capability_error = _capability_error()
    if capability_error:
        return capability_error
    try:
        started = time.perf_counter()
        depth, note = _clamp(depth, 1, 5)
        loaded = await load_bill_text(ctx, congress, bill_type, number, version)
        toc, node_capped, actual_depth = _toc_nodes(loaded.parsed.units, depth, loaded.parsed.subtree_bytes)
        # A node showing children:[] at the depth boundary is indistinguishable
        # from a genuinely empty one, so a consumer reads "this subtitle has no
        # sections" and stops. Detect sections that nest below the returned depth
        # and disclose them rather than letting toc_truncated=false assert
        # completeness that isn't there.
        hidden = _hidden_section_count(loaded.parsed.units, actual_depth)
        notes: list[str] = []
        if note:
            notes.append(note)
        if node_capped:
            notes.append(f"TOC node cap of 500 reached; returned depth {actual_depth}.")
        if hidden:
            required = _max_section_depth(loaded.parsed.units)
            notes.append(
                f"{hidden} section(s) nest below the returned depth {actual_depth} and are "
                f"collapsed into their parent nodes; call with depth={required} to see them, "
                f"or use search_bill_text."
            )
        return BillTocResponse(
            **_envelope(loaded),
            version_resolution_note=loaded.resolved.version_resolution_note,
            timing=_timing(loaded, started),
            depth=actual_depth,
            toc_truncated=node_capped or bool(hidden),
            toc_note=" ".join(notes) or None,
            toc=toc,
        ).model_dump()
    except BillTextError as exc:
        return _error(exc.code, exc.message, exc.detail, exc.remediation)
    except Exception as exc:
        return _unexpected("get_bill_toc", exc)


def _resolve_unit(units: list[Unit], requested: str) -> Unit | dict[str, Any]:
    requested = requested.strip()
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


def _toc_nodes(units: list[Unit], depth: int, subtree_bytes: dict[str, int]) -> tuple[list[TocNode], bool, int]:
    for actual_depth in range(depth, 0, -1):
        nodes = _build_toc(units, actual_depth, subtree_bytes)
        count = _count_toc(nodes)
        if count <= 500:
            return nodes, depth != actual_depth, actual_depth
    return _build_toc(units, 1, subtree_bytes)[:500], True, 1


def _build_toc(units: list[Unit], depth: int, subtree_bytes: dict[str, int]) -> list[TocNode]:
    roots: list[TocNode] = []
    node_map: dict[str, TocNode] = {}
    for unit in units:
        path = [*unit.ancestor_path]
        last = unit.section_id.split("/")[-1]
        typ, enum = last.split(":", 1)
        path.append(type("Node", (), {"type": typ, "enum": enum, "header": unit.header})())
        parent = None
        for idx, node in enumerate(path[:depth]):
            sid = "/".join(f"{item.type}:{item.enum}" for item in path[: idx + 1])
            if sid not in node_map:
                toc_node = TocNode(
                    section_id=sid,
                    node_kind=node_kind_for(sid),
                    type=node.type,
                    enum=node.enum,
                    header=node.header,
                    byte_length=unit.byte_length if idx == len(path) - 1 else 0,
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
