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
    orig_from, orig_seg, orig_intro = P.ET.fromstring, P.extract_segments, P.extract_intro_segments

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

    def wrap_intro(elem, header):
        emitted.add(id(elem))                       # the section elem is the unit source
        subdivided.append(elem)
        state["in_intro"] = True
        try:
            return orig_intro(elem, header)
        finally:
            state["in_intro"] = False

    P.ET.fromstring, P.extract_segments, P.extract_intro_segments = cap_fromstring, wrap_seg, wrap_intro
    try:
        parsed = P.parse_bill_xml(xml_bytes, pkg, version, None)
    finally:
        P.ET.fromstring, P.extract_segments, P.extract_intro_segments = orig_from, orig_seg, orig_intro

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
    return parsed, leaks, orphans


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
    parsed, leaks, orphans = audit(xml, "BILLS-synthetic", "syn")
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
    _parsed, leaks, orphans = audit(xml, "BILLS-synthetic", "syn")
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
    _parsed, leaks, orphans = audit(data, entry["package_id"], entry["version"])
    assert not leaks, f"{entry['package_id']}: {len(leaks)} unit-source element(s) inside quoted material"
    assert not orphans, f"{entry['package_id']}: {len(orphans)} orphaned child(ren) dropped by subdivision"
