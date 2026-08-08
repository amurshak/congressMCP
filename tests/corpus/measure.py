#!/usr/bin/env python
"""V19 / V21 measurement harness over the extended corpus. Offline; no credentials.

    BILL_TEXT_CORPUS_CACHE=... python -m tests.corpus.measure

Reports V19 (amends completeness -- two populations, reported separately) and V21
(match_contexts distribution). Each measurement prints n examined alongside n found.

CORPUS-SCAN HYGIENE, enforced here rather than trusted:

  NON-ZERO DENOMINATOR. A scan that errored and a scan that found nothing render
  identically. An earlier resolution scan used bare urllib, swallowed exceptions, and
  reported 403s from a blocked User-Agent as "no resolutions have 2+ versions" -- it
  established nothing and was reported as though it had. Every denominator here is
  asserted non-zero and the run exits non-zero if any is empty.

  PROVENANCE BY IDENTITY, NEVER BY STRING. Content recurs across versions; a committee
  substitute repeats the struck text verbatim. Segment scoping is done by walking the
  parser's own Segment objects, not by locating text positions in a flattened string.
  V19's LEAD-IN detection is a genuine exception and not a violation: "does this text
  contain a chapter-level amendatory lead-in" is a textual question about content, not
  a provenance question about which element produced a unit. The identity rule governs
  the latter. Applied here: the lead-in regex runs ONLY over operative segments,
  selected by segment.context, so the scoping is by identity and the matching is by
  text -- each where it belongs.

  ENUMERATION MEMBERS VERIFIED INDEPENDENTLY. Overlapping guards cover each other on
  the shapes an author thinks to test, so an enumeration can be complete while its
  verification is not. See tests/test_bill_text_measure.py, which plants a positive
  for every population counted here and asserts each detector fires alone.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from congress_api.features.bill_text.parser import parse_bill_xml  # noqa: E402

MANIFEST = json.loads((HERE / "manifest.json").read_text())


def cache_dir() -> Path:
    default = HERE.parent.parent / MANIFEST["cache_default"]
    return Path(os.getenv(MANIFEST["cache_env"], str(default)))


# --------------------------------------------------------------------------- #
# V19 detectors
# --------------------------------------------------------------------------- #
# A chapter- or title-level amendatory lead-in: the target is named by a container
# ("Title 46, United States Code, is amended as follows", "Chapter 47 of title 46 ...
# is amended"), after which the unit's own text addresses bare section numbers. No
# §6 citation form resolves this, so `amends` comes back empty on a unit that plainly
# amends something -- Population A.
# The container must be the SUBJECT of the amendment, not an object inside a
# section-level citation. Anchoring at a clause boundary is what separates
#     "Chapter 47 of title 46 ... is amended"        <- lead-in, unresolvable
# from
#     "Section 2304(a) of title 10 ... is amended"   <- ordinary, fully resolvable
# The unanchored form matched "title 10" inside the second, which would have counted
# the single most common amendatory shape in the corpus as a blind spot and pushed
# Population A toward its threshold on a measurement artifact. Caught by a planted
# negative, not by reading the regex.
LEADIN_RE = re.compile(
    r"(?:^|[.;:\n—–]|\)\s)\s*"
    r"(?:title|chapter|subtitle|subchapter|part)\s+"
    r"(?:[0-9]+[A-Za-z]*|[IVXLC]+)\b"
    r"(?:\s+of\s+[^,.;]{0,60}?)?"
    r"[^.;]{0,120}?\b(?:is|are)\s+(?:further\s+|hereby\s+)?amended",
    re.IGNORECASE,
)

# A citation that a HUMAN would resolve to a U.S. Code target, used for Population B.
# Deliberately NOT the regex that populates `amends`: measuring the field's shortfall
# with the field's own detector is circular and reports zero by construction. This is
# looser on purpose -- it accepts a bare section reference that sits under an
# amendatory lead-in, which is exactly the class §6 declines to resolve.
BARE_SECTION_RE = re.compile(r"\bsections?\s+(\d+[A-Za-z]*(?:\([0-9A-Za-z]+\))*)", re.IGNORECASE)
# Section suffixes are joined by ANY unicode dash in the source, not just the ASCII
# hyphen -- "16 U.S.C. 3839aa-2" is written with U+2013. The parser's P.L. form was
# already corrected for this (repro S:549E); its USC form was not, which is a separate
# finding this scan quantifies rather than a property of the scan.
_DASH = "\\-\u2010-\u2015"
USC_ANY_RE = re.compile(
    rf"\b(\d+)\s+U\.?\s?S\.?\s?C\.?\s+(\d+[A-Za-z]*(?:[{_DASH}]\d+[A-Za-z]*)?(?:\([0-9A-Za-z]+\))*)",
    re.IGNORECASE,
)
# The same citation restricted to the en-dash-suffixed shape the parser's hug cannot
# cross, used to separate "short because of a fixable resolution bug" from "short
# because of A5's accepted recall cost". The two have different remedies.
USC_NONASCII_DASH_RE = re.compile(
    rf"\b(\d+)\s+U\.?\s?S\.?\s?C\.?\s+(\d+[A-Za-z]*[\u2010-\u2015]\d+[A-Za-z]*(?:\([0-9A-Za-z]+\))*)",
    re.IGNORECASE,
)
LONGHAND_ANY_RE = re.compile(
    r"section\s+([0-9A-Za-z().-]+)\s+of\s+title\s+(\d+[A-Za-z]*),\s+United States Code",
    re.IGNORECASE,
)


def operative_text(unit) -> str:
    """Operative segments only, joined. Scoping by segment.context -- identity of the
    segment the parser produced -- never by position in a flattened string (§6)."""
    return "\n\n".join(s.text for s in unit.segments if s.context == "operative")


def has_leadin(text: str) -> bool:
    return bool(LEADIN_RE.search(text))


# An amendatory verb reached from a citation across an interposed clause. This is a
# RELAXED hug, not an absent gate: the strict §6 hug permits only ")", ",", ";" and
# whitespace between citation and verb, and A5's accepted recall cost is exactly the
# citations that lose to an interposed clause ("..., as amended by Public Law 118-31,
# is further amended"). Relaxing the hug measures that cost; removing it measures
# something else entirely.
RELAXED_VERB_RE = re.compile(
    r"\b(?:(?:is|are)\s+(?:further\s+|hereby\s+)?amended|by\s+striking|by\s+inserting|by\s+adding)\b",
    re.IGNORECASE,
)


def _amendatory_within_clause(text: str, start: int) -> bool:
    """True if an amendatory verb follows this citation within the same sentence."""
    window = text[start:start + 240]
    cut = window.find(". ")
    if cut != -1:
        window = window[:cut]
    return bool(RELAXED_VERB_RE.search(window))


def amendment_targets(text: str) -> set[str]:
    """Citations a reader would judge to be AMENDMENT TARGETS of this unit.

    NOT "every citation present". The first version of this counted every U.S. Code
    citation in operative text and reported 14.1% of populated arrays as short --
    against a threshold of 10%. It was measuring cross-references: a definitions
    section naming three statutes, an appropriations section naming seven programs.
    That is precisely the false-positive class A5 removed from `amends` itself (411
    of 695 NDAA longhand matches were non-amendments), reintroduced as a measurement
    and pointed at the field that had just been cleaned of it.

    Gate on the verb, as everything else in this feature does -- but with the hug
    RELAXED across an interposed clause, so what this counts is the population the
    strict hug knowingly drops. Provenance cites ("as amended by ...") are excluded
    for the same reason the parser excludes them: an intervening amender is not the
    target.

    Bare section numbers count only under a chapter/title lead-in, the construction
    §6 resolves no form for, and only within the clause following it.
    """
    from congress_api.features.bill_text.parser import _is_provenance_cite

    found: set[str] = set()
    for match in USC_ANY_RE.finditer(text):
        if _amendatory_within_clause(text, match.end()) and not _is_provenance_cite(text, match.start()):
            found.add(f"{match.group(1)} U.S.C. {match.group(2)}")
    for match in LONGHAND_ANY_RE.finditer(text):
        if _amendatory_within_clause(text, match.end()) and not _is_provenance_cite(text, match.start()):
            found.add(f"{match.group(2)} U.S.C. {match.group(1)}")
    for lead in LEADIN_RE.finditer(text):
        clause = text[lead.end():lead.end() + 400]
        for bare in BARE_SECTION_RE.finditer(clause):
            if _amendatory_within_clause(clause, bare.end()):
                found.add(f"bare:{bare.group(1)}")
    return found


# --------------------------------------------------------------------------- #
def measure(packages):
    v19a = Counter()
    v19b = Counter()
    shortfall = Counter()
    v21 = Counter()
    examined = Counter()
    examples = {"A": [], "B": []}

    for pkg, path in packages:
        parsed = parse_bill_xml(path.read_bytes(), pkg, "x", None)
        examined["packages"] += 1
        for unit in parsed.units:
            examined["units"] += 1
            op = operative_text(unit)

            # ---- V19 ------------------------------------------------------- #
            if unit.is_amendatory:
                v19a["N_amendatory"] += 1
                amends = unit.amends
                if not amends:
                    v19a["N_empty"] += 1
                    if has_leadin(op):
                        v19a["N_empty_leadin"] += 1
                        if len(examples["A"]) < 5:
                            examples["A"].append((pkg, unit.section_id, op[:150]))
                else:
                    v19b["N_populated"] += 1
                    reported = len(amends)
                    present = len(amendment_targets(op))
                    if present > reported:
                        v19b["N_short"] += 1
                        shortfall[min(present - reported, 3)] += 1
                        # Separate the fixable resolution bug from A5's accepted
                        # recall cost: they are the same symptom with different cures.
                        if any(
                            _amendatory_within_clause(op, m.end())
                            for m in USC_NONASCII_DASH_RE.finditer(op)
                        ):
                            v19b["N_short_endash"] += 1
                        if len(examples["B"]) < 5:
                            examples["B"].append(
                                (pkg, unit.section_id, reported, present, op[:150])
                            )

            # ---- V21 ------------------------------------------------------- #
            # operative x quoted 2x2, with HEADER PROJECTED OUT and reported
            # separately as an attribute. Three contexts yield seven non-empty
            # subsets, not four, and header participation is size-correlated --
            # nested descendant headings are indexed as header segments of their
            # enclosing unit, so a big unit carries header for reasons that have
            # nothing to do with context mixing. Folding it into the combination
            # space would mix a fact about unit size into a measurement about
            # mixing. The decision F6 turns on is "does this hit mix operative and
            # quoted", which header never affects.
            ctx = {s.context for s in unit.segments}
            v21[(("operative" in ctx), ("quoted" in ctx))] += 1
            if "header" in ctx:
                examined["units_with_header"] += 1

    return v19a, v19b, shortfall, v21, examined, examples


def measure_quoted_headers(packages):
    """Do indexed header segments ever come from inside quoted material?

    If they do, a heading the bill is INSERTING is indexed as the enclosing unit's
    header, so a heading-phrase search returns `header` context for text the bill
    does not enact -- the A4 carve-out reasoning applied to the header field rather
    than to unit emission.

    Identity-instrumented against the parser's own tree: a heading's text can recur
    between quoted and operative material, so a string match cannot establish which
    subtree it came from. Same instrument that settled V14.
    """
    import xml.etree.ElementTree as ET

    from congress_api.features.bill_text.parser import element_text, local_name

    seg_from_quoted = 0
    field_from_quoted = 0
    total_header_segments = 0
    total_header_fields = 0
    examples = []
    for pkg, path in packages:
        raw = path.read_bytes()
        root = ET.fromstring(raw)
        parent = {c: p for p in root.iter() for c in p}

        def quoted_ancestor(elem) -> bool:
            cur = elem
            while cur is not None:
                if local_name(cur) in {"quote", "quoted-block"}:
                    return True
                cur = parent.get(cur)
            return False

        # Header text that exists ONLY inside quoted subtrees in this document.
        # Compare like with like: extract header text with the PARSER's own
        # element_text, which normalizes whitespace and tightens punctuation. A raw
        # itertext() join does neither, so an operative header carrying internal
        # newlines failed to match its own emitted segment, dropped out of the
        # exclusion set, and made a quoted twin look like the only source -- 2 false
        # positives that read exactly like the defect being looked for.
        quoted_headers, operative_headers = set(), set()
        for elem in root.iter():
            if local_name(elem) != "header":
                continue
            text = element_text(elem)
            if not text:
                continue
            (quoted_headers if quoted_ancestor(elem) else operative_headers).add(text)
        quoted_only = quoted_headers - operative_headers

        parsed = parse_bill_xml(raw, pkg, "x", None)
        for unit in parsed.units:
            for seg in unit.segments:
                if seg.context == "header":
                    total_header_segments += 1
                    if seg.text in quoted_only:
                        seg_from_quoted += 1
                        if len(examples) < 5:
                            examples.append(("segment", pkg, unit.section_id, seg.text[:60]))
            if unit.header:
                total_header_fields += 1
                if unit.header in quoted_only:
                    field_from_quoted += 1
                    if len(examples) < 5:
                        examples.append(("field", pkg, unit.section_id, unit.header[:60]))
    return (
        seg_from_quoted,
        total_header_segments,
        field_from_quoted,
        total_header_fields,
        examples,
    )


def require(label: str, n: int) -> None:
    """A denominator of zero means the scan established nothing. Say so and fail."""
    if n == 0:
        print(f"\nFAIL: {label} is zero -- this scan measured nothing.")
        sys.exit(1)


def pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}%" if den else "n/a"


def main() -> int:
    cache = cache_dir()
    packages = [
        (e["package_id"], cache / f"{e['package_id']}.xml")
        for e in MANIFEST["packages"]
        if (cache / f"{e['package_id']}.xml").exists()
    ]
    print(f"corpus cache: {cache}")
    print(f"packages examined: {len(packages)} of {len(MANIFEST['packages'])} in manifest")
    require("packages examined", len(packages))

    v19a, v19b, shortfall, v21, examined, examples = measure(packages)
    require("units examined", examined["units"])

    print(f"units examined: {examined['units']:,}\n")

    print("=" * 78)
    print("V19 POPULATION A -- empty arrays that should not be empty (gates F8)")
    print("=" * 78)
    require("N_amendatory", v19a["N_amendatory"])
    print(f"  N_amendatory    {v19a['N_amendatory']:>7,}   (denominator)")
    print(f"  N_empty         {v19a['N_empty']:>7,}   {pct(v19a['N_empty'], v19a['N_amendatory'])} of amendatory")
    print(f"  N_empty_leadin  {v19a['N_empty_leadin']:>7,}   {pct(v19a['N_empty_leadin'], v19a['N_empty'])} of empty")
    ratio_a = v19a["N_empty_leadin"] / v19a["N_empty"] if v19a["N_empty"] else 0
    print(f"\n  PRE-REGISTERED THRESHOLD: >= 20% -> per-unit response note; below -> tool description")
    print(f"  RESULT: {pct(v19a['N_empty_leadin'], v19a['N_empty'])} -> "
          f"{'RESPONSE NOTE warranted' if ratio_a >= 0.20 else 'tool description only'}")
    for pkg, sid, txt in examples["A"]:
        print(f"     e.g. {pkg} {sid}: {txt[:100]!r}")

    print()
    print("=" * 78)
    print("V19 POPULATION B -- populated arrays that are short (gates F3)")
    print("=" * 78)
    require("N_populated", v19b["N_populated"])
    print(f"  N_populated     {v19b['N_populated']:>7,}   (denominator)")
    print(f"  N_short         {v19b['N_short']:>7,}   {pct(v19b['N_short'], v19b['N_populated'])} of populated")
    if shortfall:
        print("  shortfall distribution:")
        for k in sorted(shortfall):
            label = f"{k} missing" if k < 3 else "3+ missing"
            print(f"     {label:<12} {shortfall[k]:>6,}")
    print(f"  ...of which involve an en-dash-suffixed USC section the hug cannot cross:")
    print(f"     N_short_endash {v19b['N_short_endash']:>6,}   "
          f"{pct(v19b['N_short_endash'], v19b['N_short'])} of short  <- a FIXABLE regex gap,")
    print(f"     not A5's accepted recall cost. Different cause, different remedy.")
    ratio_b = v19b["N_short"] / v19b["N_populated"] if v19b["N_populated"] else 0
    print(f"\n  PRE-REGISTERED THRESHOLD: >= 10% -> completeness signal; below -> existing wording")
    print(f"  RESULT: {pct(v19b['N_short'], v19b['N_populated'])} -> "
          f"{'COMPLETENESS SIGNAL warranted' if ratio_b >= 0.10 else 'existing wording covers it'}")
    for pkg, sid, rep, pres, txt in examples["B"]:
        print(f"     e.g. {pkg} {sid}: reports {rep}, text carries {pres}: {txt[:90]!r}")
    print("\n  NOT POOLED with Population A: A is a resolution gap, B a disclosure gap.")

    print()
    print("=" * 78)
    print("V21 -- operative x quoted (header projected out, reported as an attribute)")
    print("=" * 78)
    total = sum(v21.values())
    require("units with contexts", total)
    labels = {
        (True, True): "operative + quoted  (MIXED)",
        (True, False): "operative only",
        (False, True): "quoted only",
        (False, False): "neither",
    }
    for key in ((True, True), (True, False), (False, True), (False, False)):
        n = v21.get(key, 0)
        print(f"  {labels[key]:<30} {n:>7,}   {pct(n, total)}")
    mixed = v21.get((True, True), 0)
    print(f"\n  header attribute (orthogonal): {examined['units_with_header']:,} units "
          f"({pct(examined['units_with_header'], total)}) carry a header segment")
    print(f"\n  PRE-REGISTERED: most hits mixed -> tool description; a minority -> per-hit note")
    print(f"  RESULT: {pct(mixed, total)} mixed -> "
          f"{'MINORITY: per-hit note applies' if mixed / total < 0.5 else 'MAJORITY: tool description'}")

    print()
    print("=" * 78)
    print("Header provenance -- are indexed headers ever drawn from quoted material?")
    print("=" * 78)
    seg_q, seg_n, fld_q, fld_n, hex_ = measure_quoted_headers(packages)
    require("header segments examined", seg_n)
    require("header fields examined", fld_n)
    print(f"  header SEGMENTS examined {seg_n:>7,}   from quoted-only text: {seg_q:,}  {pct(seg_q, seg_n)}")
    print(f"  header FIELDS   examined {fld_n:>7,}   from quoted-only text: {fld_q:,}  {pct(fld_q, fld_n)}")
    for kind, pkg, sid, text in hex_:
        print(f"     {kind:<8} {pkg} {sid}: {text!r}")
    if seg_q or fld_q:
        print("\n  NONZERO: a heading the bill is INSERTING is presented as a unit's own")
        print("  header -- the A4 carve-out reasoning applied to the header field.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
