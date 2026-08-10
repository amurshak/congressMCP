"""Typed response models for bill text tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AncestorNode(BaseModel):
    type: str
    enum: str
    header: str | None = None


class AmendsTarget(BaseModel):
    # `amends` resolves U.S. Code and Public Law citations, never named Acts. The
    # kind discriminator means a consumer never parses `cite` syntax to know what
    # kind of target it holds (same reasoning as node_kind in §5).
    kind: Literal["usc", "public_law"]
    cite: str


class CacheStatus(BaseModel):
    index_hit: bool = False
    version_hit: bool = False


class Timing(BaseModel):
    """Server-measured wall-clock per phase, in milliseconds. fetch_ms covers
    congress.gov version resolution plus the GovInfo document download; while
    version_resolution is "fresh" and index_hit is false these run on every call
    (persistence is PR 2). search_ms is present only for search_bill_text."""

    fetch_ms: float
    parse_ms: float
    index_ms: float
    search_ms: float | None = None
    total_ms: float


class ErrorPayload(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None
    remediation: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


class BillTextEnvelope(BaseModel):
    package_id: str
    version: str
    version_resolution: Literal["fresh", "cached", "cached_offline"] = "fresh"
    version_resolved_at: str
    # VERSION ISSUES ONLY. Non-null means the served text is not simply the version the
    # caller asked for: the latest listed version was unavailable and the server fell
    # back, or the resolved code is NEGATIVE/ADMINISTRATIVE -- failed passage, laid on
    # the table, a sponsor annotation -- rather than authoritative bill text.
    #
    # The invariant is `version_resolution_note != null <=> a version issue`, and it is
    # load-bearing: a consumer can key on the field's PRESENCE without parsing it.
    # Input-clamp advisories used to be merged in here, which broke that in both
    # directions -- first by clobbering the version note (F17), then, once merged, by
    # firing a false version warning on every over-large max_hits. Request-level
    # advisories go in `request_note` instead.
    version_resolution_note: str | None = None
    source_format: Literal["bill_dtd"] = "bill_dtd"
    last_modified: str | None = None
    govinfo_url: str
    cache: CacheStatus = Field(default_factory=CacheStatus)
    sections_indexed: int
    chunks_indexed: int
    # Active disclosure that committee-struck text was excluded (F4). A response-level
    # NOTE rather than a per-hit field on purpose: §17 measured version_resolution_note
    # being read and acted on by a consumer that ignored match_contexts on the same
    # response, so the note is the mechanism that demonstrably propagates. Null when
    # the document carries no struck text, which is every enrolled/engrossed/introduced
    # version measured.
    struck_text_note: str | None = None
    timing: Timing | None = None


class SearchHit(BaseModel):
    section_id: str
    node_kind: Literal["structural", "synthetic", "chunk"]
    ancestor_path: list[AncestorNode]
    header: str | None
    snippet: str
    match_contexts: list[Literal["operative", "quoted", "header"]]
    matched_queries: list[str]
    is_amendatory: bool
    amends: list[AmendsTarget]
    score: float
    byte_length: int
    # Total bytes of this unit plus its descendant chunks; equals byte_length for
    # a leaf, but exposes the real size of a subdivided section whose own
    # byte_length is only its intro text.
    subtree_byte_length: int


class QueryDiagnostic(BaseModel):
    """Why one query matched nothing (F10).

    A zero-hit response is otherwise unreadable: "this bill does not discuss the
    subject" and "the bill discusses it in other words" are the same empty list, and
    the caller cannot tell whether rephrasing would help. `terms` also exposes the
    stemming, which is where a phrase quietly stops meaning what was typed
    ("Force" indexes as "forc", "striking" as "strike").
    """

    query: str
    # The query as the index tokenized it -- produced by FTS5 itself, not a
    # reimplementation, so it is the tokenisation the search actually ran.
    terms: list[str]
    # Terms that appear nowhere in this bill. Non-empty means no rephrasing helps.
    absent_terms: list[str]
    # "absent_term": at least one term is missing from the bill entirely.
    # "phrasing": every term is present, but not as this contiguous phrase -- the
    # query is answerable, just not in these words. Matching is literal phrase with
    # stemming, so word order and adjacency are load-bearing.
    verdict: Literal["absent_term", "phrasing"]


class SearchBillTextResponse(BillTextEnvelope):
    # Benign advisory about how THIS REQUEST's arguments were adjusted -- a clamped
    # max_hits or max_bytes. Separated from version_resolution_note so a caller can tell
    # a safety disclosure from a parameter footnote WITHOUT parsing strings, the same
    # discriminator pattern as node_kind and the amends {kind, cite} objects. Null when
    # every argument was used as given.
    request_note: str | None = None
    chunks_searched: int
    queries_used: list[str]
    # Present only for queries that matched nothing; null when every query hit.
    query_diagnostics: list[QueryDiagnostic] | None = None
    hits: list[SearchHit]


class SectionChild(BaseModel):
    section_id: str
    node_kind: Literal["structural", "synthetic", "chunk"]
    header: str | None
    byte_length: int
    subtree_byte_length: int


class BillSectionResponse(BillTextEnvelope):
    # Benign advisory about how THIS REQUEST's arguments were adjusted -- a clamped
    # max_hits or max_bytes. Separated from version_resolution_note so a caller can tell
    # a safety disclosure from a parameter footnote WITHOUT parsing strings, the same
    # discriminator pattern as node_kind and the amends {kind, cite} objects. Null when
    # every argument was used as given.
    request_note: str | None = None

    section_id: str
    node_kind: Literal["structural", "synthetic", "chunk"]
    ancestor_path: list[AncestorNode]
    header: str | None
    text: str
    byte_length: int
    subtree_byte_length: int
    truncated: bool
    children: list[SectionChild] | None = None


class TocNode(BaseModel):
    section_id: str
    node_kind: Literal["structural", "synthetic", "chunk"]
    type: str
    enum: str
    header: str | None
    byte_length: int
    subtree_byte_length: int
    children: list["TocNode"] = Field(default_factory=list)


class BillTocResponse(BillTextEnvelope):
    # The depth this call ATTEMPTED, after clamping the argument to 1-5 (the clamp
    # itself is disclosed separately in toc_note). Reported so a caller can see the
    # depth actually served without holding onto its own request to diff against.
    requested_depth: int
    # The depth actually served.
    depth: int
    # True when the 500-node cap forced a shallower tree than requested_depth (F11).
    # Distinct from toc_truncated on purpose: toc_truncated answers "does more exist
    # below what I got?", which is true whenever sections nest deeper -- INCLUDING
    # when the requested depth was honored in full. It therefore cannot signal that
    # the depth argument was overridden, and a caller reading only toc_truncated
    # cannot tell a complete depth-3 tree with deeper sections from a depth-5 request
    # silently served at 3. Observed on s1071 (5 -> 3) and hr2471 (4/5 -> 2).
    depth_reduced: bool = False
    toc_truncated: bool = False
    toc_note: str | None = None
    toc: list[TocNode]
