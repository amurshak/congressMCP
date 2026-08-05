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
    version_resolution_note: str | None = None
    source_format: Literal["bill_dtd"] = "bill_dtd"
    last_modified: str | None = None
    govinfo_url: str
    cache: CacheStatus = Field(default_factory=CacheStatus)
    sections_indexed: int
    chunks_indexed: int
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


class SearchBillTextResponse(BillTextEnvelope):
    chunks_searched: int
    queries_used: list[str]
    hits: list[SearchHit]


class SectionChild(BaseModel):
    section_id: str
    node_kind: Literal["structural", "synthetic", "chunk"]
    header: str | None
    byte_length: int
    subtree_byte_length: int


class BillSectionResponse(BillTextEnvelope):
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
    depth: int
    toc_truncated: bool = False
    toc_note: str | None = None
    toc: list[TocNode]
