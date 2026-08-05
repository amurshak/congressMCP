"""Namespace-agnostic Bill DTD XML parsing and structural chunking."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field

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
AMENDATORY_RE = re.compile(
    r"\b(is|are) amended\b|\bby striking\b|\bby inserting\b|\bby adding\b|"
    r"\bredesignat(e|ing|ed)\b|\bis repealed\b",
    re.IGNORECASE,
)
# Two accepted citation forms for `amends`, both resolving to a U.S. Code target
# (never a named-Act title -- that generalization stays out of scope):
#   1. Longhand: "Section {sec} of title {title}, United States Code". Self-
#      anchored (it names the target), so it needs no amendatory verb.
#   2. Shorthand "{title} U.S.C. {sec}", accepted only when the amendatory verb
#      "is/are [further/hereby] amended|repealed" *hugs* the citation -- nothing
#      but closing parens, commas, and whitespace may sit between the section
#      number and the verb. That hug is the whole gate: reconciliation bills
#      amend named Acts cited as "...(7 U.S.C. 2012) is amended", which the
#      longhand form never captures, while an incidental cross-reference like
#      "under 5 U.S.C. 553, ensure that ... is amended" is rejected because prose
#      (not just closers/whitespace) separates it from the verb. An earlier
#      loose window (`[0-9A-Za-z().,\s]*?`) let a stray cite bridge across a whole
#      sentence to a distant verb, both mis-attributing the target and swallowing
#      the real one inside the over-wide match.
AMENDS_RE = re.compile(
    r"Section\s+([0-9A-Za-z().-]+)\s+of\s+title\s+([0-9A-Za-z]+),\s+United States Code",
    re.IGNORECASE,
)
AMENDS_USC_RE = re.compile(
    r"\b(\d+)\s+U\.?\s?S\.?\s?C\.?\s+"          # title N U.S.C.
    r"(\d+[A-Za-z]*(?:-\d+)?)"                   # section: 823, 1395ww, 1395w-4
    r"(?:\([0-9A-Za-z]+\))*"                     # optional subsection designators, e.g. (a)(1)
    r"[)\s,]*"                                   # only closers/commas/space may hug the verb
    r"(?:is|are)\s+(?:further\s+|hereby\s+)?(?:amended|repealed)\b",
    re.IGNORECASE,
)


@dataclass
class Segment:
    context: str
    text: str


@dataclass
class Unit:
    section_id: str
    ancestor_path: list[AncestorNode]
    header: str | None
    segments: list[Segment]
    child_ids: list[str] = field(default_factory=list)

    @property
    def display_text(self) -> str:
        return "\n\n".join(segment.text for segment in self.segments if segment.text).strip()

    @property
    def byte_length(self) -> int:
        return len(self.display_text.encode("utf-8"))

    @property
    def is_amendatory(self) -> bool:
        if any(segment.context == "quoted" for segment in self.segments):
            return True
        return any(AMENDATORY_RE.search(segment.text) for segment in self.segments if segment.context == "operative")

    @property
    def amends(self) -> list[str]:
        # Scan operative text only: a U.S. Code cite inside a quoted segment is
        # part of the language being *inserted*, not the target being amended
        # (spec §6 -- exclude quoted material structurally, not by proximity).
        found = set()
        operative_text = "\n\n".join(
            segment.text for segment in self.segments if segment.context == "operative"
        )
        for match in AMENDS_RE.finditer(operative_text):
            found.add(f"{match.group(2)} U.S.C. {match.group(1)}")
        for match in AMENDS_USC_RE.finditer(operative_text):
            found.add(f"{match.group(1)} U.S.C. {match.group(2)}")
        return sorted(found)


@dataclass
class ParsedBill:
    package_id: str
    version: str
    last_modified: str | None
    units: list[Unit]
    sections_indexed: int
    quotes_seen: set[str]


def parse_bill_xml(xml_bytes: bytes, package_id: str, version: str, last_modified: str | None = None) -> ParsedBill:
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
    )


class _Chunker:
    def __init__(self, package_id: str, version: str, last_modified: str | None):
        self.package_id = package_id
        self.version = version
        self.last_modified = last_modified
        self.units: list[Unit] = []
        self.sections_indexed = 0
        self.synthetic_counts: defaultdict[str, int] = defaultdict(int)
        self.sibling_counts: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self.quotes_seen: set[str] = set()

    def walk(self, elem: ET.Element, path: list[AncestorNode]) -> None:
        name = local_name(elem)
        if name in SKIP_NAMES:
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
            emitted = False
            for child in list(elem):
                if local_name(child) == "whereas":
                    emitted = True
                    self._emit_synthetic(child, "PRE", path)
                elif local_name(child) == "resolving-clause":
                    emitted = True
                    self._emit_synthetic(child, "RC", path)
                else:
                    self.walk(child, path)
            if not emitted and not any(local_name(child) in STRUCTURE_TYPES for child in list(elem)):
                self._emit_synthetic(elem, "U", path)
            return
        for child in list(elem):
            self.walk(child, path)

    def _node_for(self, elem: ET.Element, typ: str, path: list[AncestorNode]) -> AncestorNode:
        enum = direct_text(elem, "enum") or self._synthetic_enum(typ)
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
        children = self._subdivide(elem, path)
        if children:
            parent = Unit(
                section_id=section_id,
                ancestor_path=path[:-1],
                header=node.header,
                segments=extract_intro_segments(elem, node.header),
                child_ids=[child.section_id for child in children],
            )
            self.units.append(parent)
            self.units.extend(children)
        else:
            self.units.extend(byte_split_unit(unit))

    def _subdivide(self, elem: ET.Element, path: list[AncestorNode]) -> list[Unit]:
        for child_name in FALLBACK_CHAIN:
            child_elems = [child for child in list(elem) if local_name(child) == child_name]
            if not child_elems:
                continue
            units = []
            typ = "SS" if child_name == "subsection" else child_name.upper().replace("-", "")
            for idx, child in enumerate(child_elems, start=1):
                enum = direct_text(child, "enum") or str(idx)
                node = AncestorNode(type=typ, enum=enum, header=direct_text(child, "header"))
                child_id = "/".join([*(f"{item.type}:{item.enum}" for item in path), f"{node.type}:{node.enum}"])
                child_unit = Unit(child_id, path, node.header, extract_segments(child, node.header))
                if child_unit.byte_length > MAX_UNIT_BYTES:
                    units.extend(byte_split_unit(child_unit))
                else:
                    units.append(child_unit)
            return units
        return []


def byte_split_unit(unit: Unit) -> list[Unit]:
    text = unit.display_text
    if len(text.encode("utf-8")) <= MAX_UNIT_BYTES:
        return [unit]
    # Split on blank lines first, then guarantee every atom is within the cap:
    # a single paragraph with no blank-line breaks (e.g. a flattened table) can
    # itself exceed the cap, and splitting only on "\n\n" would emit it whole.
    atoms: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        if paragraph.strip():
            atoms.extend(_bound_atom(paragraph.strip()))
    chunks = []
    buf = ""
    idx = 1
    for atom in atoms:
        candidate = (buf + "\n\n" + atom) if buf else atom
        if len(candidate.encode("utf-8")) > MAX_UNIT_BYTES and buf:
            chunks.append(_para_unit(unit, idx, buf))
            idx += 1
            buf = atom
        else:
            buf = candidate
    if buf:
        chunks.append(_para_unit(unit, idx, buf))
    return chunks or [unit]


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


def _para_unit(unit: Unit, idx: int, text: str) -> Unit:
    return Unit(
        section_id=f"{unit.section_id}/PARA:{idx}",
        ancestor_path=unit.ancestor_path,
        header=unit.header,
        segments=[Segment("operative", text)],
    )


def extract_intro_segments(elem: ET.Element, header: str | None) -> list[Segment]:
    segments = []
    if header:
        segments.append(Segment("header", header))
    for child in list(elem):
        if local_name(child) in FALLBACK_CHAIN:
            break
        if local_name(child) in {"enum", "header"}:
            continue
        text = element_text(child)
        if text:
            segments.append(Segment("operative", text))
    return segments or ([Segment("header", header)] if header else [])


def extract_segments(elem: ET.Element, unit_header: str | None, in_quote: bool = False) -> list[Segment]:
    segments: list[Segment] = []
    name = local_name(elem)
    if name in SKIP_NAMES or name == "toc":
        return segments
    quote_now = in_quote or name in {"quote", "quoted-block"}
    if quote_now and name in {"quote", "quoted-block"}:
        segments.append(Segment("quoted", element_text(elem)))
        return [segment for segment in segments if segment.text]
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
            segments.append(Segment(context, run))
            run = ""
        segments.extend(extract_segments(child, unit_header, quote_now))
        if child.tail and child.tail.strip():
            run = _join_inline(run, normalize_text(child.tail))
    if run:
        segments.append(Segment(context, run))
    if not segments and name not in {"bill", "legis-body", "resolution-body"}:
        text = element_text(elem)
        if text:
            segments.append(Segment(context, text))
    return coalesce_segments(segments)


def coalesce_segments(segments: list[Segment]) -> list[Segment]:
    out: list[Segment] = []
    for segment in segments:
        if not segment.text:
            continue
        if out and out[-1].context == segment.context:
            out[-1].text = f"{out[-1].text}\n\n{segment.text}"
        else:
            out.append(segment)
    return out


def direct_text(elem: ET.Element, child_name: str) -> str | None:
    for child in list(elem):
        if local_name(child) == child_name:
            text = element_text(child)
            return text or None
    return None


def element_text(elem: ET.Element) -> str:
    if local_name(elem) in SKIP_NAMES or local_name(elem) == "toc":
        return ""
    pieces: list[str] = []
    if elem.text:
        pieces.append(elem.text)
    for child in list(elem):
        if local_name(child) in SKIP_NAMES or local_name(child) == "toc":
            if child.tail:
                pieces.append(child.tail)
            continue
        pieces.append(element_text(child))
        if child.tail:
            pieces.append(child.tail)
    text = " ".join(piece for piece in pieces if piece)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _join_inline(run: str, text: str) -> str:
    """Join inline text onto the running flow with a single separating space.

    Matches element_text's single-space token joining; the boundary spaces that
    lived in the source text/tail are already stripped by normalize_text.
    """
    return f"{run} {text}" if run else text


def local_name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1] if "}" in elem.tag else elem.tag
