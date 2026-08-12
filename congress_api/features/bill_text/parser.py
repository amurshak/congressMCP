"""Namespace-agnostic Bill DTD XML parsing and structural chunking."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field

from .client import BillTextError
from .models import AncestorNode


MAX_UNIT_BYTES = 8_000
STRUCTURE_TYPES = {
    "division": "D",
    "title": "T",
    "subtitle": "ST",
    "part": "PT",
    "section": "S",
    "subsection": "SS",
}
FALLBACK_CHAIN = ["subsection", "paragraph", "subparagraph", "clause"]
# Qualified-id codes for the subdivision chain (spec §5). `PARA`/`SUBP`/`CL` are
# real document enums; a byte-bounded cut is NOT an enumeration of anything and is
# addressed `CHUNK:{n}` instead, in a namespace that cannot be mistaken for a bill
# enum (citing "§204(a)(3)" from a byte cut labelled PARA:3 would be wrong).
SUBDIV_CODE = {
    "subsection": "SS",
    "paragraph": "PARA",
    "subparagraph": "SUBP",
    "clause": "CL",
}
# node_kind is derivable from the id's leaf prefix; it is surfaced anyway so a
# consumer (a model) never has to parse an id string to decide whether a citation
# is safe. `structural` came from the document and may be cited; `synthetic` is
# ours (stable, not a citation); `chunk` refers to nothing the bill enumerates.
_STRUCTURAL_PREFIXES = {"D", "T", "ST", "PT", "S", "SS", "PARA", "SUBP", "CL"}
_SYNTHETIC_PREFIXES = {"PRE", "RC", "U"}
BLOCK_NAMES = {
    "header",
    "enum",
    "text",
    "chapeau",
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "section",
    "division",
    "title",
    "subtitle",
    "part",
    "whereas",
    "resolving-clause",
}
SKIP_NAMES = {"toc", "page-break"}
# Committee-struck text (F4). The Bill DTD marks it with changed="deleted" (declared
# on the structure-attribute groups) plus reported-display-style="strikethrough";
# there is no <DELETED> element, which an earlier reading of the spec assumed.
#
# Struck text is IN the document but is not part of the bill as reported -- the
# dominant shape is the Senate committee substitute, "strike all after the enacting
# clause and insert the part printed in italic", which carries the whole original
# bill struck alongside its replacement. Emitting it produced two versions of the
# same bill side by side: on 119s4726rs, 16 of 33 sections were struck, 18 ids took a
# V8 `#n` collision suffix that hid what the collision MEANT, and get_bill_section("1")
# resolved uniquely -- no ambiguity error -- to the struck text, because struck text
# comes first in document order.
#
# Excluded rather than given a fourth context, mirroring A4's quoted-block carve-out:
# markup present in the document that is not enacted text. match_contexts stays
# three-valued. Struck material contributes NEITHER a unit NOR text, so a live unit's
# display_text can never contain struck language (a struck <quoted-block> inside a
# live section is dropped, not kept as a `quoted` segment).
#
# THE CARVE-OUT BINDS EVERY UNIT-EMITTING PATH. Enumerated, because a rule scoped to
# the path it was found on has failed four times in this feature (A4, A5, intro
# labelling, _subdivide):
#   1. structural discovery      -- _Chunker.walk returns before _emit_addressable
#   2. synthetic emission        -- same early return covers _emit_synthetic
#   3. structural subdivision    -- _subdivide skips struck children
#   4. byte fallback             -- byte_split_unit splits an already-emitted unit, so
#                                   it is bound transitively: no struck unit can reach
#                                   it. Pinned by test rather than left to inference.
#   5. text extraction           -- extract_segments / element_text skip struck subtrees
DELETED_MARK = "deleted"
# Inline/typographic elements whose text flows into the surrounding run rather
# than forming a block of its own. Emitting them as separate segments turns e.g.
# "Coast Guard cutter <italic>Mackinaw</italic> (WLBB-30)" into three fake blocks
# that read as headings to a naive consumer and wreck downstream chunking.
# `quote`/`quoted-block` are inline in position too, but they change segment
# context, so they stay on the block/recursion path and are handled separately.
INLINE_NAMES = {
    "italic",
    "bold",
    "i",
    "b",
    "sup",
    "sub",
    "superscript",
    "subscript",
    "term",
    "external-xref",
    "internal-xref",
    "fraction",
}
# The amendatory-verb clause, shared by is_amendatory and the amends verb-hug so
# the two can never drift (A5). is_amendatory's regex is a strict SUPERSET of the
# hug verb (it also counts by-striking/inserting/adding/redesignating), which is
# what lets the `amends != [] ⟹ is_amendatory` invariant hold by construction.
_AMEND_VERB = r"(?:is|are)\s+(?:further\s+|hereby\s+)?(?:amended|repealed)"
# The citation-to-verb "hug" (A5): only closing parens, commas, semicolons, and
# whitespace may sit between a citation and the amendatory verb -- zero prose.
# This is the SINGLE hug definition for every amends form; there are no per-form
# windows. General rule for any future form: NO citation form is self-gating. A
# form that "obviously names its target" has only resolved the cite; whether
# *this unit* amends it is independent, and only the verb hug establishes that.
_HUG = r"[)\s,;]*" + _AMEND_VERB + r"\b"
# A6 (DEFERRED, not rejected). The strict hug drops genuine amendments phrased with
# an interposed clause -- "Section X of title 10, United States Code, as amended by
# section Z, is further amended" or "... (article 6 of the UCMJ) is amended". V13
# measured 12-14 such losses on the NDAA (exhaustive on the distant-verb class),
# ~0 on hr1; the dropped units stay is_amendatory, so nothing is hidden. The loss
# is systematic, not random -- "as amended by" marks already-amended (high-traffic)
# provisions -- so a discovery consumer would feel it on exactly the hottest cites.
# DO NOT relax this hug without the A6 flip condition: the idiom at a material rate
# in a THIRD document AND a bounded implementation showing 0 added false positives
# on a >=30 hand sample that includes interposed-clause citations. Both, not either.
# THE TRAP: the interposed clause usually carries its OWN citation ("as amended by
# Public Law 118-31") that this bill does NOT amend. A naive relaxation makes the
# clause transparent for the outer cite AND pulls that inner cite into hugging range
# of the same verb -- manufacturing the exact false-positive class V13 just removed,
# in the freshly-approved public_law form. Any A6 must skip the clause for the OUTER
# citation only; citations inside the clause stay ineligible.
# The is_amendatory verb SUPERSET only -- never _AMEND_VERB, which gates `amends`
# (V13 measured that gate's per-form precision at 0/30; an unmeasured form here would
# reopen it for nothing). `to read as follows` added per V18: enumerated exhaustively,
# it newly flags exactly ONE unit in the 18-bill corpus (115hr1 S:13502, a genuine
# amendment -- "Paragraph (1) of section 743(d) is to read as follows:" -- that lacked
# any gated verb), 0 false positives. §6 directs consumers to is_amendatory, so a known
# false negative there contradicts how the field is sold.
AMENDATORY_RE = re.compile(
    r"\b" + _AMEND_VERB + r"\b|\bby striking\b|\bby inserting\b|\bby adding\b|"
    r"\bredesignat(?:e|ing|ed)\b|\bto read as follows\b",
    re.IGNORECASE,
)
# Three accepted citation forms for `amends`, resolving to a U.S. Code or Public
# Law target (never a named Act). ALL THREE share the single `_HUG` gate (A5): the
# amendatory verb must hug the citation, with only closers/commas/semicolons/
# whitespace between. Resolution differs per form; the gate does not.
#   - longhand USC:  "Section {sec} of title {title}, United States Code" + hug.
#     A5 corrected the original spec claim that longhand is "self-anchored" and
#     needs no verb: it resolves without context, but whether *this unit amends it*
#     is a separate property. Un-gated, it fired on definitional / "subject to" /
#     "notwithstanding" cross-references (NDAA: 411 of 695 matches non-amendments).
#   - shorthand USC: "{title} U.S.C. {sec}" + hug. Captures "...(7 U.S.C. 2012) is
#     amended" that longhand misses on reconciliation bills.
#   - public law:    "(Public Law {c}-{n})" / "{v} Stat. {p}" + hug (V15-approved).
AMENDS_RE = re.compile(
    r"Section\s+([0-9A-Za-z().-]+)\s+of\s+title\s+([0-9A-Za-z]+),\s+United States Code"
    + _HUG,
    re.IGNORECASE,
)
# Section suffixes are joined by ANY unicode dash, not just the ASCII hyphen. The
# source writes "42 U.S.C. 1395w-4" and "16 U.S.C. 3839aa-2" with U+2013, and the
# ASCII-only class made the hug fail on the dash -- so EVERY en-dash-suffixed section
# was dropped from `amends` even when perfectly hugged by an amendatory verb. Same
# defect the P.L. form already carried and had corrected (repro S:549E); the USC form
# was missed then. Found by V19 Population B, which flagged units as "short" that were
# short for this reason rather than for A5's accepted recall cost.
#
# Precision re-checked at V13's standard before widening the gate: 198 newly-captured
# cites corpus-wide, hand-coded sample n=30 (seed 13), 30/30 genuine amendment targets
# -- every one "Section X of [Act] (N U.S.C. Y-Z) is amended by ...". No ranges, no
# cross-references, no provenance cites.
_SECTION_DASH = "\\-\u2010-\u2015"
AMENDS_USC_RE = re.compile(
    r"\b(\d+)\s+U\.?\s?S\.?\s?C\.?\s+"                        # title N U.S.C.
    rf"(\d+[A-Za-z]*(?:[{_SECTION_DASH}]\d+[A-Za-z]*)?)"      # section: 823, 1395ww, 1395w-4
    r"(?:\([0-9A-Za-z]+\))*"                                  # optional designators, e.g. (a)(1)
    + _HUG,
    re.IGNORECASE,
)


def _normalize_section_dash(section: str) -> str:
    """Emit one canonical cite per target regardless of the dash the drafter typed.

    Without this, the same section cited with U+2013 in one clause and a hyphen in
    another yields two entries in `amends` for one target -- the de-duplication
    failure the P.L. form was fixed for, reproduced in the USC form.
    """
    return re.sub(f"[{_SECTION_DASH}]", "-", section)
AMENDS_PL_RE = re.compile(
    r"\b(?:Public\s+Law|Pub\.?\s*L\.?|P\.?\s*L\.?)\s*\.?\s*"
    # Congress-number joined by ANY unicode hyphen/dash. The bill mixes them: a
    # single "Public Law 118‑159" written with U+2011 (non-breaking hyphen) where
    # the rest uses U+2013 was missed, then mislabeled as a Statutes-at-Large page
    # via the Stat fallback (repro S:549E). Accept U+2010..U+2015 and hyphen-minus.
    r"(\d+)[-‐-―](\d+)"
    r"(?:[\s;(]*\d+\s+Stat\.\s*\d+\)?)?"         # optional same-instance "; 139 Stat. 656"
    + _HUG,
    re.IGNORECASE,
)
# Standalone Statutes-at-Large cite (emitted only where no P.L. form covers it in
# the same instance -- see the span check in Unit.amends). Prefer the P.L. form.
AMENDS_STAT_RE = re.compile(
    r"\b(\d+)\s+Stat\.\s+(\d+)"
    + _HUG,
    re.IGNORECASE,
)
# A citation reached via an "as [added|amended] by ..." clause is an intervening
# amender / provenance note, not the amendment target. Repro S:1106: the verb hugs
# the LAST cite in a chain -- "(Public Law 109-234), as added by ... (P.L. 110-417),
# as most recently amended by section 145(a) of the [NDAA] (P.L. 118-159), is
# amended" -- so the hug binds to the current-year intervener, not the target. Left
# unchecked this made the FY2025 NDAA look like the most-amended act in the corpus,
# a drafting-style artifact (exactly the V15 failure mode). Requires the "as"
# prefix so the operative verb "is/are amended by" is never mistaken for provenance.
PROVENANCE_RE = re.compile(
    r"\bas\s+(?:so\s+|most\s+recently\s+|further\s+|previously\s+|originally\s+|subsequently\s+)?"
    r"(?:added|amended|inserted|redesignated|transferred|enacted|revised)\s+by\b",
    re.IGNORECASE,
)


def _is_provenance_cite(text: str, start: int) -> bool:
    """True if the citation at `start` sits inside an "as ... amended/added by"
    clause within its sentence -- i.e. it is an intervening amender, not the
    target. Precision-first: a chain target that appears only *before* the clause
    is dropped rather than mis-attributed to the intervener (a known recall cost,
    same shape as A5's interposition losses -- the unit stays is_amendatory)."""
    window = text[max(0, start - 220):start]
    # Confine to the current sentence; the chain has no period within it, but a
    # prior sentence's "as amended by" must not bleed across.
    cut = max(window.rfind(". "), window.rfind("\n\n"))
    if cut != -1:
        window = window[cut + 1:]
    return bool(PROVENANCE_RE.search(window))


@dataclass
class Segment:
    context: str
    text: str
    # True when this segment CONTINUES the preceding inline run rather than starting a
    # new block (F12). An inline <quote> must still be its own segment -- §6 needs one
    # context per segment and the amendatory safety property depends on it -- but it
    # sits mid-sentence, so joining it with the BLOCK separator fractures the sentence:
    #     "...(commonly known as the" | "Indian Civil Rights Act of 1968" | ") is amended"
    # rendered as three blocks. The split is structurally required; the separator is not.
    inline: bool = False


@dataclass
class Unit:
    section_id: str
    ancestor_path: list[AncestorNode]
    header: str | None
    segments: list[Segment]
    child_ids: list[str] = field(default_factory=list)

    @property
    def display_text(self) -> str:
        # Same join as render_segments, minus the delimiters, so byte_length and the
        # segment-concatenation invariant stay coherent with what a caller reads.
        return join_segments(self.segments, render=False)

    @property
    def byte_length(self) -> int:
        return len(self.display_text.encode("utf-8"))

    @property
    def is_amendatory(self) -> bool:
        # Verb-only (V18). The prior quote branch -- "any quoted segment => amendatory"
        # -- fired on non-amendatory quotation: appropriations account headings, short
        # titles, defined terms, report titles, findings-quotes. A hand-coded sample
        # (n=35, seed=18) over the 18-bill corpus was 35/35 non-amendatory, and the
        # prediction that the branch caught ungated imperative amendments was falsified
        # (0/35; ~1% by targeted probe). A structural marker is not evidence of
        # amendment -- gate on the verb (A5's principle, applied to quotation).
        return any(AMENDATORY_RE.search(segment.text) for segment in self.segments if segment.context == "operative")

    @property
    def amends(self) -> list[dict[str, str]]:
        # Scan operative text only: a cite inside a quoted segment is part of the
        # language being *inserted*, not the target being amended (spec §6 --
        # exclude quoted material structurally, not by proximity). Returns objects
        # {kind, cite}: kind is "usc" or "public_law", never a named Act. Sorted by
        # (kind, cite), de-duplicated on the pair.
        #
        # A5 structural post-condition: `amends != [] ⟹ is_amendatory == true`.
        # Enforced here by construction so no citation form -- present or future --
        # can populate amends on a unit that amends nothing. (One direction only;
        # the converse is intentionally NOT guaranteed -- named Acts and the IRC
        # leave amendatory units empty by design.) All amends forms share the same
        # verb hug as is_amendatory's superset detector, so this guard never drops a
        # legitimately-matched cite; it only forecloses drift.
        if not self.is_amendatory:
            return []
        found: set[tuple[str, str]] = set()
        operative_text = "\n\n".join(
            segment.text for segment in self.segments if segment.context == "operative"
        )
        # Skip any cite reached via an "as ... amended/added by" clause: it is an
        # intervening amender in a citation chain, not the target (repro S:1106).
        for match in AMENDS_RE.finditer(operative_text):
            if _is_provenance_cite(operative_text, match.start()):
                continue
            found.add(("usc", f"{match.group(2)} U.S.C. {match.group(1)}"))
        for match in AMENDS_USC_RE.finditer(operative_text):
            if _is_provenance_cite(operative_text, match.start()):
                continue
            found.add(("usc", f"{match.group(1)} U.S.C. {_normalize_section_dash(match.group(2))}"))
        # Public Law targets, preferring the P.L. form. The P.L. pattern absorbs a
        # same-instance Statutes-at-Large cite; a standalone Stat cite is emitted
        # only where no P.L. match covers its span (so one enactment cited two ways
        # -- "P.L. 119-38; 139 Stat. 656" -- yields a single target).
        pl_spans: list[tuple[int, int]] = []
        for match in AMENDS_PL_RE.finditer(operative_text):
            if _is_provenance_cite(operative_text, match.start()):
                continue
            found.add(("public_law", f"P.L. {match.group(1)}-{match.group(2)}"))
            pl_spans.append((match.start(), match.end()))
        for match in AMENDS_STAT_RE.finditer(operative_text):
            if any(start <= match.start() < end for start, end in pl_spans):
                continue
            if _is_provenance_cite(operative_text, match.start()):
                continue
            found.add(("public_law", f"{match.group(1)} Stat. {match.group(2)}"))
        return [{"kind": kind, "cite": cite} for kind, cite in sorted(found)]


@dataclass
class ParsedBill:
    package_id: str
    version: str
    last_modified: str | None
    units: list[Unit]
    sections_indexed: int
    quotes_seen: set[str]
    # Sections dropped because a committee struck them (F4). Drives the caller-facing
    # note: an exclusion nobody is told about is the defect-#2 shape (content silently
    # lost), so this count is what turns a silent drop into an active disclosure.
    struck_sections_excluded: int = 0
    # section_id -> total bytes of the unit *and its descendant chunks*. A
    # subdivided section's own `byte_length` is just its intro (e.g. 73 B), which
    # reads as a tiny section when the real subtree is tens of KB; this exposes
    # the true size so a consumer is not misled (spec §5 resolution, decision 2).
    subtree_bytes: dict[str, int] = field(default_factory=dict)


def is_struck(elem: ET.Element) -> bool:
    """True if this element was struck by committee (F4).

    Attribute-based, namespace-agnostic on the value, and deliberately narrow: only
    the DTD's own changed="deleted". reported-display-style="strikethrough" is a
    RENDERING hint that accompanies it, not an independent signal -- treating a
    display style as evidence of the property would be the structural-marker mistake
    this feature has made repeatedly.
    """
    return elem.get("changed") == DELETED_MARK


def count_struck_sections(elem: ET.Element) -> int:
    """Sections inside a struck subtree, for the caller-facing disclosure count."""
    total = 1 if local_name(elem) == "section" else 0
    for child in elem.iter():
        if child is not elem and local_name(child) == "section":
            total += 1
    return total


def normalize_enum(value: str | None) -> str | None:
    """Strip TRAILING periods from a document enum at id-construction time (F2).

    An id component carries the enum's *identity*, not its typography. GovInfo
    writes a section enum as `1832.` because the heading reads "SEC. 1832." -- the
    period is a heading terminator and appears in no citation of that section. Left
    in, it leaked into the id: `get_bill_section("804")` answered "No section or
    chunk matched '804'" while three sections numbered 804 existed, and only `804.`
    resolved. Four independent sessions tripped on it, and the tool asserting a
    falsehood is worse than the miss.

    Trailing only. Internal periods stay, so decimal-style enums (`1.2`) survive.
    Contrast `PARA:(3)`: parentheses ARE how that enum is written and they
    disambiguate level, so they are kept.
    """
    if value is None:
        return None
    cleaned = value.strip().rstrip(".").strip()
    return cleaned or None


def node_kind_for(section_id: str) -> str:
    """Derive node_kind from the id's leaf component prefix (spec §5)."""
    prefix = section_id.split("/")[-1].split(":", 1)[0]
    if prefix == "CHUNK":
        return "chunk"
    if prefix in _SYNTHETIC_PREFIXES:
        return "synthetic"
    return "structural"


def compute_subtree_bytes(units: list[Unit]) -> dict[str, int]:
    """Map every section_id *prefix* -> own bytes of it plus all descendants.

    Keyed by prefix, not just by emitted unit id, so TOC container nodes that are
    never emitted as units (a `<division>`/`<title>`) also get a size-per-branch
    (spec §9: the highest-value place for this field is get_bill_toc). Because
    every unit's `byte_length` is own-text only -- a subdivided parent holds just
    its intro, its children are separate units -- summing own bytes across a
    prefix double-counts nothing, and `prefix_bytes[unit.section_id]` equals
    `own + Σ descendants` for an emitted unit (spec §9 containment semantics).
    """
    prefix_bytes: dict[str, int] = {}
    for unit in units:
        parts = unit.section_id.split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            prefix_bytes[prefix] = prefix_bytes.get(prefix, 0) + unit.byte_length
    return prefix_bytes


def parse_bill_xml(xml_bytes: bytes, package_id: str, version: str, last_modified: str | None = None) -> ParsedBill:
    # Billion-laughs guard (spec §11). Stdlib expat does not fetch external DTDs or
    # expand external entities by default, so XXE is low-risk, but internal general
    # entities (the billion-laughs vector) ARE expanded. Bill XML has no legitimate
    # internal entity declarations, so reject any document whose raw bytes carry
    # one before parsing -- costs nothing, needs no library.
    if b"<!ENTITY" in xml_bytes:
        raise BillTextError(
            "unsafe_document",
            "The document declares XML entities and was refused before parsing.",
            {"package_id": package_id},
            "This is not expected for GovInfo Bill DTD XML; report it if it recurs.",
        )
    root = ET.fromstring(xml_bytes)
    chunker = _Chunker(package_id, version, last_modified)
    chunker.walk(root, [])
    return ParsedBill(
        package_id=package_id,
        version=version,
        last_modified=last_modified,
        units=chunker.units,
        sections_indexed=chunker.sections_indexed,
        quotes_seen=chunker.quotes_seen,
        struck_sections_excluded=chunker.struck_sections_excluded,
        subtree_bytes=compute_subtree_bytes(chunker.units),
    )


class _Chunker:
    def __init__(self, package_id: str, version: str, last_modified: str | None):
        self.package_id = package_id
        self.version = version
        self.last_modified = last_modified
        self.units: list[Unit] = []
        self.sections_indexed = 0
        self.struck_sections_excluded = 0
        self.synthetic_counts: defaultdict[str, int] = defaultdict(int)
        self.sibling_counts: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self.quotes_seen: set[str] = set()

    def walk(self, elem: ET.Element, path: list[AncestorNode]) -> None:
        name = local_name(elem)
        if name in SKIP_NAMES:
            return
        if is_struck(elem):
            # Paths 1 and 2 of the carve-out: returning here forecloses both
            # _emit_addressable and _emit_synthetic for this element and everything
            # beneath it, so no struck subtree can produce an addressable unit.
            self.struck_sections_excluded += count_struck_sections(elem)
            return
        if name in {"quote", "quoted-block"}:
            # V14 carve-out (spec §5): never emit an addressable unit from inside
            # quoted material. A bill inserting a new <section> produces
            # <quoted-block><section><enum>…; a generic walk would make that a
            # phantom unit for text the bill is *inserting*, not enacting -- the
            # amendatory trap at unit level, where match_contexts cannot help
            # because the unit itself is spurious. The quoted text stays fully
            # searchable as `quoted` segments of the enclosing real unit (captured
            # by extract_segments), never as a unit of its own.
            return
        if name in STRUCTURE_TYPES:
            node = self._node_for(elem, STRUCTURE_TYPES[name], path)
            new_path = path + [node]
            if name == "section":
                self.sections_indexed += 1
                self._emit_addressable(elem, new_path, node)
                return
            for child in list(elem):
                self.walk(child, new_path)
            return
        if name == "preamble":
            # Simple resolutions carry their whereas clauses in a top-level
            # <preamble> that is a sibling of <resolution-body>, not inside it.
            # Emit each as a synthetic PRE unit so the substance is addressable.
            for child in list(elem):
                if local_name(child) == "whereas":
                    self._emit_synthetic(child, "PRE", path)
                elif local_name(child) == "resolving-clause":
                    self._emit_synthetic(child, "RC", path)
                else:
                    self.walk(child, path)
            return
        if name in {"resolution-body", "legis-body", "engrossed-amendment-body"}:
            before = len(self.units)
            for child in list(elem):
                if local_name(child) == "whereas":
                    self._emit_synthetic(child, "PRE", path)
                elif local_name(child) == "resolving-clause":
                    self._emit_synthetic(child, "RC", path)
                else:
                    self.walk(child, path)
            # U:1 is the last resort for a body with no addressable structure at all;
            # its span is the WHOLE body, so it must fire only when the recursion above
            # emitted nothing AND there is non-struck content left to capture. Two ways
            # the old single-clause guard was wrong:
            #  - It sniffed the body's DIRECT children for a STRUCTURE_TYPES tag, but
            #    sections can sit under a container that is not itself a STRUCTURE_TYPES
            #    key (chapter/subchapter/subpart, all real DTD levels per
            #    _QUOTED_BLOCK_LEVEL). There the recursion emitted S units yet the sniff
            #    saw no structural child, so U:1 fired anyway and duplicated every
            #    section verbatim under a spurious root. Ask what the walk produced.
            #  - When a reported substitute strikes the ENTIRE prior text, every body
            #    section is struck; the recursion emits nothing, but there is nothing to
            #    wrap either -- extract_segments drops the struck matter, so a U:1 built
            #    from it is an empty, contentless synthetic root that also inflates
            #    sections_indexed (observed on 119s4726rs). Suppress it.
            if len(self.units) == before and extract_segments(elem, None):
                self._emit_synthetic(elem, "U", path)
            return
        for child in list(elem):
            self.walk(child, path)

    def _node_for(self, elem: ET.Element, typ: str, path: list[AncestorNode]) -> AncestorNode:
        enum = normalize_enum(direct_text(elem, "enum")) or self._synthetic_enum(typ)
        base_enum = enum
        parent_key = "/".join(f"{node.type}:{node.enum}" for node in path)
        key = (parent_key, typ, base_enum)
        self.sibling_counts[key] += 1
        if self.sibling_counts[key] > 1:
            enum = f"{base_enum}#{self.sibling_counts[key]}"
        return AncestorNode(type=typ, enum=enum, header=direct_text(elem, "header"))

    def _synthetic_enum(self, typ: str) -> str:
        self.synthetic_counts[typ] += 1
        return str(self.synthetic_counts[typ])

    def _emit_synthetic(self, elem: ET.Element, typ: str, path: list[AncestorNode]) -> None:
        self.synthetic_counts[typ] += 1
        node = AncestorNode(type=typ, enum=str(self.synthetic_counts[typ]), header=direct_text(elem, "header"))
        self.sections_indexed += 1
        self._emit_addressable(elem, path + [node], node)

    def _emit_addressable(self, elem: ET.Element, path: list[AncestorNode], node: AncestorNode) -> None:
        section_id = "/".join(f"{item.type}:{item.enum}" for item in path)
        segments = extract_segments(elem, node.header)
        unit = Unit(section_id=section_id, ancestor_path=path[:-1], header=node.header, segments=segments)
        if unit.byte_length <= MAX_UNIT_BYTES:
            self.units.append(unit)
            return
        subdivided_tag, children = self._subdivide(elem, path)
        if children:
            parent = Unit(
                section_id=section_id,
                ancestor_path=path[:-1],
                header=node.header,
                segments=extract_own_segments(elem, node.header, subdivided_tag),
                child_ids=[child.section_id for child in children],
            )
            self.units.append(parent)
            self.units.extend(children)
        else:
            self.units.extend(byte_split_unit(unit))

    def _subdivide(self, elem: ET.Element, path: list[AncestorNode]) -> tuple[str | None, list[Unit]]:
        for child_name in FALLBACK_CHAIN:
            # Path 3 of the carve-out: a struck subsection/paragraph inside a live
            # section must not become a child unit either.
            child_elems = [
                child
                for child in list(elem)
                if local_name(child) == child_name and not is_struck(child)
            ]
            if not child_elems:
                continue
            units = []
            typ = SUBDIV_CODE[child_name]
            # Disambiguate colliding sibling enums exactly as _node_for does for the
            # structural path: bills contain genuine duplicate subdivision letters
            # (e.g. 116hr6395 s.1832 has two subsection "(e)"s), and without the #{n}
            # suffix the two units share an id -- _resolve_unit and get_bill_section's
            # child_by_id then dict-overwrite, making the first unreachable and dropping
            # its text from the assembled section. Local to one section's children.
            sibling_counts: dict[str, int] = {}
            for idx, child in enumerate(child_elems, start=1):
                base_enum = normalize_enum(direct_text(child, "enum")) or str(idx)
                sibling_counts[base_enum] = sibling_counts.get(base_enum, 0) + 1
                enum = base_enum if sibling_counts[base_enum] == 1 else f"{base_enum}#{sibling_counts[base_enum]}"
                node = AncestorNode(type=typ, enum=enum, header=direct_text(child, "header"))
                child_id = "/".join([*(f"{item.type}:{item.enum}" for item in path), f"{node.type}:{node.enum}"])
                child_unit = Unit(child_id, path, node.header, extract_segments(child, node.header))
                if child_unit.byte_length > MAX_UNIT_BYTES:
                    units.extend(byte_split_unit(child_unit))
                else:
                    units.append(child_unit)
            return child_name, units
        return None, []


def byte_split_unit(unit: Unit) -> list[Unit]:
    """Split an oversized unit into `CHUNK:{n}` cuts each within MAX_UNIT_BYTES,
    preserving each segment's `context`.

    A byte cut is arbitrary and enumerates nothing, so chunks are addressed
    `CHUNK:{n}`, never a document enum code. Critically, segments are *clipped* to
    each chunk's span with their `context` carried through unchanged: a chunk
    falling inside a <quoted-block> keeps a `quoted` segment, so match_contexts
    still flags inserted language at chunk level. Flattening a chunk's text to a
    single `operative` segment (the previous behaviour) silently broke V4 on
    exactly the largest amendatory sections -- the ones that get chunked (spec §5,
    §6; V14 second assertion). A segment straddling a cut yields one row on each
    side with the same context.
    """
    if unit.byte_length <= MAX_UNIT_BYTES:
        return [unit]
    # Flatten segments into (context, atom) pieces, each atom already within the
    # cap. A single paragraph with no blank-line breaks (e.g. a flattened table)
    # can itself exceed the cap, so _bound_atom word-packs / hard-cuts it.
    atoms: list[tuple[str, str]] = []
    for segment in unit.segments:
        for piece in _segment_atoms(segment.text):
            atoms.append((segment.context, piece))
    chunks: list[Unit] = []
    buf: list[tuple[str, str]] = []
    buf_bytes = 0
    idx = 1
    for context, atom in atoms:
        atom_bytes = len(atom.encode("utf-8"))
        sep = 2 if buf else 0  # segments join with "\n\n" in display_text
        if buf and buf_bytes + sep + atom_bytes > MAX_UNIT_BYTES:
            chunks.append(_chunk_unit(unit, idx, buf))
            idx += 1
            buf = [(context, atom)]
            buf_bytes = atom_bytes
        else:
            buf.append((context, atom))
            buf_bytes += sep + atom_bytes
    if buf:
        chunks.append(_chunk_unit(unit, idx, buf))
    return chunks or [unit]


def _segment_atoms(text: str) -> list[str]:
    atoms: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        stripped = paragraph.strip()
        if stripped:
            atoms.extend(_bound_atom(stripped))
    return atoms


def _bound_atom(paragraph: str) -> list[str]:
    """Break a single paragraph into pieces each within MAX_UNIT_BYTES.

    Prefers word boundaries; hard-splits on encoded bytes only for a pathological
    single token longer than the cap, so the size ceiling always holds.
    """
    if len(paragraph.encode("utf-8")) <= MAX_UNIT_BYTES:
        return [paragraph]
    pieces: list[str] = []
    buf = ""
    for word in paragraph.split(" "):
        candidate = (buf + " " + word) if buf else word
        if len(candidate.encode("utf-8")) > MAX_UNIT_BYTES and buf:
            pieces.append(buf)
            buf = word
        else:
            buf = candidate
        while len(buf.encode("utf-8")) > MAX_UNIT_BYTES:
            cut = buf.encode("utf-8")[:MAX_UNIT_BYTES].decode("utf-8", "ignore") or buf[:1]
            pieces.append(cut)
            buf = buf[len(cut):]
    if buf:
        pieces.append(buf)
    return pieces


def _chunk_unit(unit: Unit, idx: int, pieces: list[tuple[str, str]]) -> Unit:
    # Do not synthesize a `header` segment for a byte cut -- it has no header of
    # its own (spec §5). The parent header rides along only as the display/
    # breadcrumb `header` field; any real `header` *segment* of the parent is
    # clipped naturally into the first chunk that covers its span, never copied
    # into every chunk.
    segments = coalesce_segments([Segment(context, text) for context, text in pieces])
    return Unit(
        section_id=f"{unit.section_id}/CHUNK:{idx}",
        ancestor_path=unit.ancestor_path,
        header=unit.header,
        segments=segments,
    )


def extract_own_segments(elem: ET.Element, header: str | None, subdivided_tag: str | None) -> list[Segment]:
    """Segments of a subdivided section's OWN text: everything that did NOT become a
    child unit -- the intro matter before the first subdivision AND any flush/closing
    text after the last one. Only children with `subdivided_tag` (the tag _subdivide
    carved into child units) are skipped; skipping by tag also drops struck instances
    of it, which _subdivide already excluded.

    The previous behaviour stopped at the first FALLBACK_CHAIN child, so a section's
    trailing text -- the classic flush/hanging paragraph after the last subsection --
    was captured by neither the parent nor any child. It then existed in no unit: not
    in the FTS index, not returned by get_bill_section, with truncated=false and no
    disclosure. That is the "content silently absent" failure the struck-text note
    exists to prevent, occurring with no note at all, on exactly the oversized
    sections that take this subdivide path.
    """
    segments = []
    if header:
        segments.append(Segment("header", header))
    for child in list(elem):
        if local_name(child) == subdivided_tag:
            continue
        if local_name(child) in {"enum", "header"}:
            continue
        # Delegate to extract_segments rather than flattening to a hard-coded
        # `operative` segment: the matter preceding the first subdivision can carry a
        # <quote>/<quoted-block> (e.g. `by striking "the Secretary" in the matter
        # preceding paragraph (1)`), and that inserted text must keep `quoted`
        # context or a byte-subdivided section presents struck/inserted language as
        # enacted -- the V4 amendatory trap, at the intro of exactly the largest
        # amendatory sections. extract_segments assigns the same contexts the main
        # unit path does (spec §6).
        segments.extend(extract_segments(child, None))
    return segments or ([Segment("header", header)] if header else [])


def extract_segments(elem: ET.Element, unit_header: str | None, in_quote: bool = False) -> list[Segment]:
    segments: list[Segment] = []
    name = local_name(elem)
    if name in SKIP_NAMES or name == "toc":
        return segments
    # Path 5 of the carve-out: struck material contributes no TEXT either, so a live
    # unit's display_text never carries language the committee removed. This is what
    # covers a struck <quoted-block> inside a live section -- it is dropped, not kept
    # as a `quoted` segment (match_contexts stays three-valued).
    if is_struck(elem):
        return segments
    quote_now = in_quote or name in {"quote", "quoted-block"}
    if quote_now and name in {"quote", "quoted-block"}:
        # A quote element becomes one `quoted` segment; strip any source delimiters
        # so segments.text is clean and rendering wraps without doubling. The Bill
        # DTD puts the operative connective/terminator that FOLLOWS the inserted
        # material -- "; and", ";", "." -- in an <after-quoted-block> child (1:1 with
        # every quoted-block). That belongs OUTSIDE the quote, so exclude it from the
        # quoted text and emit it as a trailing operative segment; otherwise it reads
        # as '"(D) the Coast Guard. ; and"' with the connective swallowed (spec §6).
        out: list[Segment] = []
        # flatten_quoted, not element_text: preserves block boundaries between the
        # structural units of inserted material (F12, second direction).
        quoted_text = strip_quote_delimiters(flatten_quoted(elem))
        if quoted_text:
            out.append(Segment("quoted", quoted_text, inline=is_inline_quote(elem)))
        for child in list(elem):
            if local_name(child) == "after-quoted-block":
                connective = element_text(child)
                if connective:
                    # The connective follows the inserted material in the same
                    # sentence, so it continues the run rather than starting a block.
                    out.append(Segment("operative", connective, inline=True))
        return [segment for segment in out if segment.text]
    if name == "header" and unit_header and not in_quote:
        text = element_text(elem)
        return [Segment("header", text)] if text else []
    if len(list(elem)) == 0:
        text = element_text(elem)
        if text and name not in {"enum"}:
            return [Segment("operative", text)]
        return []
    context = "quoted" if quote_now else "operative"
    # `run` accumulates the current inline text flow (own text + inline children +
    # tails). It is flushed to a segment only at a real block boundary, so inline
    # elements never split a sentence into separate blocks.
    run = ""
    run_inline = False
    if elem.text and elem.text.strip() and name not in {"bill", "legis-body", "resolution-body"}:
        run = normalize_text(elem.text)
    for child in list(elem):
        child_name = local_name(child)
        if child_name in SKIP_NAMES or child_name == "toc":
            if child.tail and child.tail.strip():
                run = _join_inline(run, normalize_text(child.tail))
            continue
        if child_name == "footnote":
            if run:
                segments.append(Segment(context, run))
                run = ""
            text = element_text(child)
            if text:
                segments.append(Segment("operative", f"[footnote] {text}"))
            if child.tail and child.tail.strip():
                run = _join_inline(run, normalize_text(child.tail))
            continue
        if child_name in INLINE_NAMES:
            text = element_text(child)
            if text:
                run = _join_inline(run, text)
            if child.tail and child.tail.strip():
                run = _join_inline(run, normalize_text(child.tail))
            continue
        # Block child, or a context-changing quote/quoted-block: end the current
        # inline run, emit the child's own segments, then resume with its tail.
        if run:
            segments.append(Segment(context, run, inline=run_inline))
            run = ""
            run_inline = False
        segments.extend(extract_segments(child, unit_header, quote_now))
        if child.tail and child.tail.strip():
            run = _join_inline(run, normalize_text(child.tail))
            # Text following an INLINE quote continues that sentence, so the run it
            # starts must not be rendered as a new block (F12).
            run_inline = run_inline or (
                child_name in {"quote", "quoted-block"} and is_inline_quote(child)
            )
    if run:
        segments.append(Segment(context, run, inline=run_inline))
    if not segments and name not in {"bill", "legis-body", "resolution-body"}:
        text = element_text(elem)
        if text:
            segments.append(Segment(context, text))
    return coalesce_segments(segments)


def coalesce_segments(segments: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for segment in segments:
        # Tighten operative runs assembled by inline-join (element_text output is
        # already tight); preserves the "\n\n" join since _tighten_punct ignores
        # newlines. Idempotent, so re-coalescing at each recursion level is safe.
        segment.text = _tighten_punct(segment.text)
        if not segment.text:
            continue
        if out and out[-1].context == segment.context:
            out[-1].text = f"{out[-1].text}\n\n{segment.text}"
        else:
            out.append(segment)
    return out


# Quote delimiters live in the RENDERING of segments, never in storage (spec §6).
# V16: the source carries no delimiters in 99.9% of cases (the tag is the
# delimiter), but a 0.1% class does -- strip those at extraction so segments.text
# is always clean and rendering can wrap unconditionally without doubling.
_OPEN_QUOTE_CHARS = "\"“‘`"       # " “ ‘ `
_CLOSE_QUOTE_CHARS = "\"”’'"      # " ” ’ '
_QUOTE_OPEN = '"'
_QUOTE_CLOSE = '"'
# Leading punctuation that hugs the previous piece with no separator, so a
# terminator after a closing delimiter does not orphan (`" .` / `)"`); spec §6.
_ATTACH_PUNCT = ".,;:)]}%!?"


# Structural levels that are their own block INSIDE quoted material. Flattening a
# quoted-block with a plain space join ran sibling units together --
# "(2) Annual basis.-(A) In general.-..." -- losing every boundary in an inserted
# chapter, which is exactly the material a reader most needs structured.
# The mark rendered between a heading and its body inside quoted material. It is
# EDITORIAL -- inserted by this renderer, present in no source document -- and the
# glyph is chosen so a reader can TELL it is ours. Inside quoted material the reader
# is looking at language the bill is inserting, so a mark that also occurs in bill
# text is unattributable. Measured across the 20-package corpus, inside quoted
# segments only: em dash 10,177, en dash 1,408, colon 2,022 -- all genuine source
# punctuation, at the same order of magnitude as the 16,479 separators emitted here,
# so none of them can carry the signal. Middle dot occurs 0 times, as do "|", "»",
# and "▸". Newline is unavailable for a different reason: it already means block
# boundary in this renderer.
#
# This is a legibility choice, not a correctness one -- the SEPARATION is ruled, the
# character is revisable.
_HEADER_SEP = " · "
# Separator punctuation the SOURCE sometimes puts at the head of the body, which must
# be absorbed rather than doubled ("Quorum --- .A majority"). Only 1 instance inside
# quoted material across the 20-package corpus, and it is degenerate (a lone "."), but
# the same drafting shape is live in operative context, so the guard is not
# speculative -- it is the same convention observed at a neighbouring site.
_HEADER_SEP_ABSORB = ".—–-: "

_QUOTED_BLOCK_LEVEL = {
    "division", "title", "subtitle", "chapter", "subchapter", "part", "subpart",
    "section", "subsection", "paragraph", "subparagraph", "clause", "subclause",
    "item", "subitem",
}


def is_inline_quote(elem: ET.Element) -> bool:
    """Does this quoting element flow inline, or stand as its own block?

    Measured across the 20-package corpus rather than assumed: <quote> carries
    display-inline on 0 of 38,277 occurrences -- it is the inline quoting element by
    nature -- while <quoted-block> is block on 7,535 and explicitly inline on 208
    (display-inline="yes-display-inline"). So the document declares it, and the only
    inference is for <quote>, where the absence is total.
    """
    if local_name(elem) == "quote":
        return True
    return elem.get("display-inline") == "yes-display-inline"


def flatten_quoted(elem: ET.Element) -> str:
    """Flatten quoted material, preserving block boundaries between structural units.

    element_text joins every child with a single space, which is right for inline
    runs and wrong across sibling paragraphs. Whitespace only -- no token changes --
    so the FTS index and every search result are unaffected; this alters how quoted
    material READS, not what it matches.
    """
    out = ""

    def add(piece: str, block: bool = False, after_header: bool = False) -> None:
        nonlocal out
        if after_header:
            # The source carries no separator between a heading and its body -- GPO's
            # renderer inserts one. Without it a heading runs into its own text
            # ("(A) In general At least once each year..."), which reads as prose and
            # hides where the heading ends. Absorb any separator punctuation the
            # source already put at the head of the body so the two cannot double up.
            piece = piece.lstrip(_HEADER_SEP_ABSORB).lstrip()
        if not piece:
            return
        if not out:
            out = piece
        elif block:
            out += f"\n\n{piece}"
        elif after_header:
            out += f"{_HEADER_SEP}{piece}"
        elif piece[:1] in _ATTACH_PUNCT:
            out += piece
        else:
            out += f" {piece}"

    if elem.text and elem.text.strip():
        add(normalize_text(elem.text))
    # Detection is STRUCTURAL -- off the <header> element -- never a regex over the
    # flattened text. The designator slot takes four digits ("IHR (2005) Monitoring"),
    # so no text pattern separates a real enum+header from a parenthetical
    # abbreviation; a text-level rule fires on "(IT) Platform Planning" and
    # "(UN) General Assembly" alike. The markup already knows, so ask it.
    prev_was_header = False
    for child in list(elem):
        name = local_name(child)
        if name in SKIP_NAMES or name == "toc" or name == "after-quoted-block" or is_struck(child):
            if child.tail and child.tail.strip():
                add(normalize_text(child.tail))
            continue
        block = name in _QUOTED_BLOCK_LEVEL
        # A header followed by a BLOCK sibling already gets "\n\n", which separates it
        # at least as clearly; only the same-block run-on needs the mark.
        add(flatten_quoted(child), block=block, after_header=prev_was_header and not block)
        prev_was_header = name == "header"
        if child.tail and child.tail.strip():
            add(normalize_text(child.tail))
            prev_was_header = False
    return out


def strip_quote_delimiters(text: str) -> str:
    """Remove one leading + one trailing source quote mark (the wrapping pair)."""
    stripped = text.strip()
    if stripped[:1] in _OPEN_QUOTE_CHARS:
        stripped = stripped[1:]
    if stripped[-1:] in _CLOSE_QUOTE_CHARS:
        stripped = stripped[:-1]
    return stripped.strip()


def join_segments(segments: list[Segment], render: bool) -> str:
    """Join segments, distinguishing an INLINE continuation from a BLOCK boundary.

    §5's rule -- inline elements flow into the surrounding run, block elements
    separate with "\\n\\n" -- was applied in reverse for quotes: an inline <quote>
    got the block separator. One join function serves both display_text (render=False,
    clean) and render_segments (render=True, delimiters on quoted spans), so the two
    can never disagree about where a boundary falls.
    """
    out = ""
    for segment in segments:
        if not segment.text:
            continue
        piece = (
            f"{_QUOTE_OPEN}{segment.text}{_QUOTE_CLOSE}"
            if render and segment.context == "quoted"
            else segment.text
        )
        if not out:
            out = piece
        elif piece[:1] in _ATTACH_PUNCT:
            out += piece            # terminator hugs the preceding piece, no space
        elif segment.inline:
            out += f" {piece}"      # mid-sentence: continue the run
        else:
            out += f"\n\n{piece}"   # real block boundary
    return out.strip()


def render_segments(segments: list[Segment]) -> str:
    """Render segments in ordinal order, wrapping `quoted` spans in delimiters.

    This is the serialization-time rendering function (spec §6): `segments.text`
    stays canonical/clean and FTS indexes it unrendered, while display_text and
    snippets are produced here. Delimiters make the inserted string and the anchor
    string distinguishable from each other and from operative prose, which §8
    relies on when it declines server-side direction inference. Trailing
    punctuation hugs a closing delimiter rather than orphaning after it.
    """
    return join_segments(segments, render=True)


def direct_text(elem: ET.Element, child_name: str) -> str | None:
    for child in list(elem):
        if local_name(child) == child_name:
            text = element_text(child)
            return text or None
    return None


def element_text(elem: ET.Element, exclude: set[str] | None = None) -> str:
    if local_name(elem) in SKIP_NAMES or local_name(elem) == "toc" or is_struck(elem):
        return ""
    pieces: list[str] = []
    if elem.text:
        pieces.append(elem.text)
    for child in list(elem):
        child_name = local_name(child)
        if child_name in SKIP_NAMES or child_name == "toc" or is_struck(child) or (exclude and child_name in exclude):
            if child.tail:
                pieces.append(child.tail)
            continue
        pieces.append(element_text(child, exclude))
        if child.tail:
            pieces.append(child.tail)
    text = " ".join(piece for piece in pieces if piece)
    return normalize_text(text)


def _tighten_punct(text: str) -> str:
    # Remove spaces/tabs (never newlines -- they carry the segment join) that the
    # element_text / inline-join space-joining orphaned around brackets and
    # terminators: `( Public Law 118-31 ; )` -> `(Public Law 118-31;)`, `counselor
    # .` -> `counselor.`. Idempotent. Spec §6: punctuation belongs against its word.
    text = re.sub(r"([(\[])[ \t]+", r"\1", text)
    return re.sub(r"[ \t]+([.,;:)\]])", r"\1", text)


def normalize_text(text: str) -> str:
    return _tighten_punct(re.sub(r"\s+", " ", text).strip())


def _join_inline(run: str, text: str) -> str:
    """Join inline text onto the running flow with a single separating space.

    Matches element_text's single-space token joining; the boundary spaces that
    lived in the source text/tail are already stripped by normalize_text.
    """
    return f"{run} {text}" if run else text


def local_name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
