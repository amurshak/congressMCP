"""Extended-corpus invariants for the bill-text parser (spec §10 third fixture class).

Two invariants, asserted test-time only (never in production -- taking the tool down
over a parser edge is a bad trade):

  V14 IDENTITY: no element that becomes a unit's source is (or sits under) a <quote>/
    <quoted-block>. Instrumented by object identity in the parser's own tree, so the
    check cannot be fooled by id-string collisions. The predicate is `is-OR-has` a
    quoted ancestor -- deliberately wider than the ancestor-only form: a <quote>
    recorded as a source *itself* is flattened-and-returned today so it never happens,
    but making the predicate cover it means a future change to the flatten path cannot
    silently open a class the test can't see.

  SUBDIVISION COVERAGE: every non-enum/header child of a subdivided section lands in
    either the intro (before the first subdivision child) or a child unit (a
    FALLBACK_CHAIN element). Anything else -- a flush <text> continuation, a stray
    element after the last subdivision -- is neither, and is dropped. Content loss is
    invisible to a conservation ratio computed over the traversal that dropped it, so
    it needs its own assertion. 0/571 across the extended corpus at time of writing;
    if this ever fires, that firing IS the live document that justifies a behavioral
    fix -- designed against a real construction instead of an imagined one.

The corpus is committed as tests/corpus/manifest.json (package_id + version + sha256);
bytes live in the gitignored cache (populate with tests/corpus/fetch_corpus.py). When
the cache is absent -- e.g. CI without credentials -- the corpus tests skip; the
always-on tests below still prove the two detectors are not vacuous.
"""
from __future__ import annotations

import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import congress_api.features.bill_text.parser as P

QUOTE_TAGS = {"quote", "quoted-block"}
_SENT = object()
_CORPUS_DIR = Path(__file__).parent / "corpus"
_MANIFEST = json.loads((_CORPUS_DIR / "manifest.json").read_text())


def _cache_dir() -> Path:
    default = _CORPUS_DIR.parent.parent / _MANIFEST["cache_default"]
    return Path(os.getenv(_MANIFEST["cache_env"], str(default)))


def audit(xml_bytes: bytes, pkg: str, version: str):
    """Parse `xml_bytes`, returning (parsed, identity_leaks, orphaned_children).

    Instruments the emitter by object identity, distinguishing the three call sites of
    extract_segments (unit-level / recursive / intro-delegated) with a re-entrancy-free
    flag so intro children -- folded into the parent unit, not unit sources -- are not
    recorded.
    """
    emitted: set[int] = set()
    subdivided: list[ET.Element] = []
    captured: dict[str, ET.Element] = {}
    state = {"in_intro": False}
    orig_from, orig_seg, orig_intro = P.ET.fromstring, P.extract_segments, P.extract_own_segments

    def cap_fromstring(data, *a, **k):
        r = orig_from(data, *a, **k)
        captured["root"] = r
        return r

    def wrap_seg(elem, unit_header, in_quote=_SENT):
        if in_quote is _SENT:                       # unit-level OR intro-delegated
            if not state["in_intro"]:
                emitted.add(id(elem))               # genuine unit source
            return orig_seg(elem, unit_header, False)
        return orig_seg(elem, unit_header, in_quote)   # recursion

    def wrap_intro(elem, header, subdivided_tag=None):
        emitted.add(id(elem))                       # the section elem is the unit source
        subdivided.append(elem)
        state["in_intro"] = True
        try:
            return orig_intro(elem, header, subdivided_tag)
        finally:
            state["in_intro"] = False

    P.ET.fromstring, P.extract_segments, P.extract_own_segments = cap_fromstring, wrap_seg, wrap_intro
    try:
        parsed = P.parse_bill_xml(xml_bytes, pkg, version, None)
    finally:
        P.ET.fromstring, P.extract_segments, P.extract_own_segments = orig_from, orig_seg, orig_intro

    root = captured["root"]
    parent = {c: par for par in root.iter() for c in par}

    def is_or_has_quoted(elem) -> bool:             # hardened predicate: self OR ancestor
        cur = elem
        while cur is not None:
            if P.local_name(cur) in QUOTE_TAGS:
                return True
            cur = parent.get(cur)
        return False

    leaks = [e for e in root.iter() if id(e) in emitted and is_or_has_quoted(e)]

    def is_or_has_struck(elem) -> bool:              # same hardened self-OR-ancestor shape
        cur = elem
        while cur is not None:
            if cur.get("changed") == P.DELETED_MARK:
                return True
            cur = parent.get(cur)
        return False

    # F4: identity, never text matching. A struck subtree and the substitute that
    # replaced it share wording by construction -- the short title is identical in
    # both -- so "this string also appears under a struck element" is not evidence of
    # provenance. It flagged the LIVE section on 119s4726rs for exactly that reason.
    struck_leaks = [e for e in root.iter() if id(e) in emitted and is_or_has_struck(e)]

    orphans = []
    for elem in subdivided:
        kids = list(elem)
        first_sub = next((i for i, c in enumerate(kids) if P.local_name(c) in P.FALLBACK_CHAIN), None)
        if first_sub is None:
            continue
        sub_type = P.local_name(kids[first_sub])
        for c in kids[first_sub:]:
            nm = P.local_name(c)
            if nm in {"enum", "header", sub_type}:
                continue
            if P.element_text(c).strip():
                orphans.append((elem, nm))
    return parsed, leaks, orphans, struck_leaks


# --------------------------------------------------------------------------- #
# Always-on: prove the two detectors are not vacuous, without needing the corpus.
# --------------------------------------------------------------------------- #
def _big(n_bytes: int) -> bytes:
    return ("word " * (n_bytes // 5)).strip().encode()


def test_identity_detector_flags_a_planted_quoted_source():
    # Sanity: if a quoted element WERE recorded as a unit source, the hardened predicate
    # must catch it. We can't make the parser do that, so assert the predicate directly.
    root = ET.fromstring(b"<section><quoted-block><text>x</text></quoted-block></section>")
    parent = {c: p for p in root.iter() for c in p}

    def is_or_has_quoted(elem):
        cur = elem
        while cur is not None:
            if P.local_name(cur) in QUOTE_TAGS:
                return True
            cur = parent.get(cur)
        return False

    qb = next(e for e in root.iter() if P.local_name(e) == "quoted-block")
    inner = next(e for e in root.iter() if P.local_name(e) == "text")
    assert is_or_has_quoted(qb)      # the quote itself (ancestor-only form would miss this)
    assert is_or_has_quoted(inner)   # something under it


def test_struck_detector_flags_a_planted_struck_source():
    # Same non-vacuity guarantee the quoted detector gets: if a struck element WERE
    # recorded as a unit source, the self-OR-ancestor predicate must catch it -- both
    # the marked element itself and anything beneath it.
    root = ET.fromstring(
        b'<legis-body><section changed="deleted"><subsection><text>x</text></subsection></section></legis-body>'
    )
    parent = {c: p for p in root.iter() for c in p}

    def is_or_has_struck(elem):
        cur = elem
        while cur is not None:
            if cur.get("changed") == P.DELETED_MARK:
                return True
            cur = parent.get(cur)
        return False

    section = next(e for e in root.iter() if P.local_name(e) == "section")
    inner = next(e for e in root.iter() if P.local_name(e) == "text")
    assert is_or_has_struck(section)   # the marked element itself
    assert is_or_has_struck(inner)     # something under it
    # ...and an unmarked sibling tree is not flagged, so the predicate discriminates.
    clean = ET.fromstring(b"<legis-body><section><text>y</text></section></legis-body>")
    clean_parent = {c: p for p in clean.iter() for c in p}
    cur = next(e for e in clean.iter() if P.local_name(e) == "text")
    seen = False
    while cur is not None:
        seen = seen or cur.get("changed") == P.DELETED_MARK
        cur = clean_parent.get(cur)
    assert not seen


def test_coverage_detector_flags_trailing_orphaned_content():
    # A subdivided section with a flush <text> AFTER the last subsection: that content
    # is neither intro nor a child unit. The detector must see it (proving 0/571 on the
    # corpus is a real absence, not a blind spot).
    xml = (
        b"<bill><legis-body><section><enum>7</enum><header>H</header>"
        b"<text>intro chapeau</text>"
        b"<subsection><enum>(a)</enum><text>" + _big(6000) + b"</text></subsection>"
        b"<subsection><enum>(b)</enum><text>" + _big(6000) + b"</text></subsection>"
        b"<text>flush continuation applying to both subsections</text>"
        b"</section></legis-body></bill>"
    )
    parsed, leaks, orphans, _struck = audit(xml, "BILLS-synthetic", "syn")
    assert not leaks
    assert any(nm == "text" for _elem, nm in orphans)  # the trailing flush text is caught


def test_coverage_clean_on_ordinary_subdivided_section():
    xml = (
        b"<bill><legis-body><section><enum>7</enum><header>H</header>"
        b"<text>intro chapeau</text>"
        b"<subsection><enum>(a)</enum><text>" + _big(6000) + b"</text></subsection>"
        b"<subsection><enum>(b)</enum><text>" + _big(6000) + b"</text></subsection>"
        b"</section></legis-body></bill>"
    )
    _parsed, leaks, orphans, _struck = audit(xml, "BILLS-synthetic", "syn")
    assert not leaks and not orphans


# --------------------------------------------------------------------------- #
# Corpus-conditional: the invariants over real documents (skips without the cache).
# --------------------------------------------------------------------------- #
def _available():
    cache = _cache_dir()
    for entry in _MANIFEST["packages"]:
        path = cache / f"{entry['package_id']}.xml"
        if path.exists():
            yield entry, path


_AVAILABLE = list(_available())


@pytest.mark.skipif(not _AVAILABLE, reason="extended corpus not fetched (see tests/corpus/fetch_corpus.py)")
@pytest.mark.parametrize("entry,path", _AVAILABLE, ids=[e["package_id"] for e, _ in _AVAILABLE])
def test_corpus_invariants(entry, path):
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"], f"{entry['package_id']} hash mismatch vs manifest"
    parsed, leaks, orphans, struck_leaks = audit(data, entry["package_id"], entry["version"])
    assert not leaks, f"{entry['package_id']}: {len(leaks)} unit-source element(s) inside quoted material"
    assert not orphans, f"{entry['package_id']}: {len(orphans)} orphaned child(ren) dropped by subdivision"
    # V8: every section_id must be unique -- a collision makes one unit unreachable
    # (dict-overwrite in _resolve_unit / child_by_id) and drops its text from the
    # assembled section. 116hr6395 s.1832 ships two subsection "(e)"s; without #-suffix
    # disambiguation this fires.
    ids = [u.section_id for u in parsed.units]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"{entry['package_id']}: duplicate section_ids {dupes}"
    # V18: is_amendatory is verb-only (the quote branch was dropped -- the first change
    # to shrink the left side of `amends != [] => is_amendatory`). Assert corpus-wide
    # that no amends target was stranded by the narrowing.
    stranded = [u.section_id for u in parsed.units if u.amends and not u.is_amendatory]
    assert not stranded, f"{entry['package_id']}: amends target with is_amendatory False: {stranded}"
    # F4: no emitted unit may draw its source from a committee-struck subtree.
    # Identity-instrumented in the parser's own tree, self-OR-ancestor, matching the
    # V14 predicate -- text matching cannot work here because a substitute repeats the
    # struck version's wording.
    assert not struck_leaks, (
        f"{entry['package_id']}: {len(struck_leaks)} unit-source element(s) inside "
        "committee-struck material"
    )


@pytest.mark.skipif(
    not any(e["version"] in {"rh", "rs"} for e, _ in _AVAILABLE),
    reason="no reported (rh/rs) package in the fetched corpus",
)
def test_f4_struck_detector_fires_on_a_real_document_with_the_carve_out_disabled(monkeypatch):
    """Non-vacuity against a REAL document, not a constructed one.

    The predicate test above is authored from the same mental model as the fix, so it
    cannot show that the detector meets the construction as GovInfo actually publishes
    it. Disabling the carve-out must make the detector fire on a real reported bill --
    if it stays silent, either the corpus has no struck material or the instrumentation
    misses it, and a green run would mean nothing.
    """
    reported = [(e, p) for e, p in _AVAILABLE if e["version"] in {"rh", "rs"}]
    fired = False
    for entry, path in reported:
        data = path.read_bytes()
        if b'changed="deleted"' not in data:
            continue                                    # nothing to detect in this one
        monkeypatch.setattr(P, "is_struck", lambda elem: False)
        _parsed, _leaks, _orphans, struck_leaks = audit(data, entry["package_id"], entry["version"])
        monkeypatch.undo()
        assert struck_leaks, (
            f"{entry['package_id']} contains changed=\"deleted\" but the detector found no "
            "unit source under it with the carve-out disabled -- the detector is blind."
        )
        fired = True
    if not fired:
        pytest.skip("no fetched reported package carries changed=\"deleted\"")


@pytest.mark.skipif(not _AVAILABLE, reason="extended corpus not fetched (see tests/corpus/fetch_corpus.py)")
def test_f4_deleted_phrase_remains_absent_from_the_corpus():
    """A WATCHED ZERO, not a speculative implementation (F4 condition 3).

    The Bill DTD declares <deleted-phrase> ("words or phrases which have been
    stricken") alongside the changed="deleted" attribute. Measured across 80 sampled
    reported packages: changed="deleted" 219 times, <deleted-phrase> ZERO. Only the
    attribute form is handled, because building for the inline form on speculation
    means shipping untested code against an imagined construction.

    An unwatched zero goes latent -- that is the intro-labelling lesson, where a
    condition read 0 under both the healthy and the broken case and nobody noticed.
    This assertion is what makes the zero mean *absent* rather than *unexamined*: if
    it ever fires, that firing IS the live document to design the handling against.
    Struck PHRASES would otherwise be emitted as ordinary operative text.

    WATCHING THE NON-EMPTY SHAPE, refined on evidence. The first corpus expansion
    fired this assertion, which is the mechanism working -- and the document it
    pointed at settled the design: BILLS-115hr1625enr carries exactly one
    <deleted-phrase>, and it is EMPTY (`<deleted-phrase
    reported-display-style="strikethrough"></deleted-phrase>` inside an
    appropriations text block). An empty element contributes no segments and cannot
    leak struck language; verified against the parser, which emits nothing for it.
    A NON-EMPTY one still would -- measured, its text comes out `operative` with no
    marker -- and still measures zero. So the watch narrows to the shape that can
    actually fail. An assertion that fires on an inert element trains its reader to
    ignore it, which is how a watched zero stops being watched.
    """
    offenders = []
    empty_seen = 0
    for entry, path in _AVAILABLE:
        data = path.read_bytes()
        if b"<deleted-phrase" not in data:
            continue
        root = ET.fromstring(data)
        for elem in root.iter():
            if P.local_name(elem) != "deleted-phrase":
                continue
            if "".join(elem.itertext()).strip():
                offenders.append(entry["package_id"])
            else:
                empty_seen += 1
    assert not offenders, (
        "A NON-EMPTY <deleted-phrase> now occurs in: " + ", ".join(sorted(set(offenders)))
        + ". F4 handled only changed=\"deleted\" because the inline form measured 0 "
        "non-empty occurrences. Design the handling against these documents -- struck "
        "phrases are currently emitted as ordinary operative text, inline, unmarked."
    )
    # Pin the empty form too, so a change in its frequency is visible rather than
    # silently absorbed: 1 across the 20-package corpus at time of writing.
    assert empty_seen <= 5, f"empty <deleted-phrase> count jumped to {empty_seen}; re-examine"
