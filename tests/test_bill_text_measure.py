"""Non-vacuity guards for the V19/V21 measurement harness (tests/corpus/measure.py).

A measurement is worth exactly what its detectors are worth. Every population counted
by the harness gets a PLANTED POSITIVE here and is asserted to fire on its own, and a
planted negative asserted not to fire -- because "0 found" and "detector blind" render
identically in a report, which is the failure the corpus-scan hygiene rules exist to
prevent.

Enumeration members are verified INDEPENDENTLY: the V19 populations overlap in the
units they draw from, so a single fixture that trips several detectors at once would
let one cover another. Each test below isolates one.

These run without the corpus, so the detectors stay honest in CI where the cache is
absent and the corpus-conditional tests skip.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.corpus.measure import (  # noqa: E402
    has_leadin,
    operative_text,
    amendment_targets,
)
from congress_api.features.bill_text.parser import Segment, Unit  # noqa: E402


def _unit(*segments: tuple[str, str]) -> Unit:
    return Unit(
        section_id="S:1",
        ancestor_path=[],
        header=None,
        segments=[Segment(context, text) for context, text in segments],
    )


# --------------------------------------------------------------------------- #
# Scoping: operative segments only, selected by segment identity (§6).
# --------------------------------------------------------------------------- #
def test_operative_text_excludes_quoted_and_header_segments():
    # The scoping must be by segment.context -- the identity of what the parser
    # produced -- not by locating text in a flattened string. A citation inside
    # quoted material is part of language being INSERTED, not a target being amended,
    # so counting it would inflate both V19 populations.
    unit = _unit(
        ("header", "Amendments to title 46"),
        ("operative", "Title 46, United States Code, is amended."),
        ("quoted", "Section 9999 of title 10, United States Code, is amended"),
    )
    text = operative_text(unit)
    assert "Title 46, United States Code, is amended." in text
    assert "9999" not in text          # quoted citation excluded
    assert "Amendments to title" not in text   # header excluded


# --------------------------------------------------------------------------- #
# V19 Population A: the chapter/title lead-in detector.
# --------------------------------------------------------------------------- #
def test_leadin_detector_fires_on_the_documented_constructions():
    # These are the constructions §6 resolves no citation form for, and the ones the
    # independent trace review saw returning amends: [].
    for text in (
        "Title 46, United States Code, is amended as follows:",
        "Chapter 47 of title 46, United States Code, is amended by adding at the end",
        "Subtitle I of title 46, United States Code, is amended by inserting",
        "Chapter 73 is amended to read as follows:",
        "Subchapter II of chapter 5 of title 5, United States Code, is further amended",
    ):
        assert has_leadin(text), f"lead-in detector missed: {text!r}"


def test_leadin_detector_does_not_fire_on_ordinary_amendatory_text():
    # A planted negative: a section-level amendment with a resolvable citation is NOT
    # a lead-in case, and counting it would inflate Population A toward its threshold.
    for text in (
        "Section 2304(a) of title 10, United States Code, is amended by striking \"icebreaker\".",
        "Section 5601 of title 14, United States Code, is amended.",
        "The Secretary shall submit a report not later than 180 days after enactment.",
    ):
        assert not has_leadin(text), f"lead-in detector false-positived: {text!r}"


# --------------------------------------------------------------------------- #
# V19 Population B: the shortfall detector.
# --------------------------------------------------------------------------- #
def test_shortfall_detector_is_not_the_field_it_measures():
    # THE CIRCULARITY GUARD. Measuring `amends`'s shortfall with the regex that
    # populates `amends` reports zero by construction. The detector must see targets
    # the field does not -- here, bare section numbers under a lead-in, which is
    # precisely the class §6 declines to resolve.
    text = (
        "Title 46, United States Code, is amended as follows: Section 2161 is amended "
        "by striking the second sentence, and section 2158 is amended by inserting."
    )
    found = amendment_targets(text)
    assert any(c.startswith("bare:") for c in found), "detector cannot see what amends misses"
    assert "bare:2161" in found and "bare:2158" in found


def test_shortfall_detector_ignores_bare_sections_without_a_leadin():
    # A planted negative for the inflation risk: without an amendatory lead-in a bare
    # "section 5" is an internal cross-reference, and counting it would make ordinary
    # drafting look like a shortfall.
    text = "Nothing in section 5 shall be construed to limit the authority under section 12."
    assert not any(c.startswith("bare:") for c in amendment_targets(text))


def test_shortfall_detector_requires_an_amendatory_verb_not_merely_a_citation():
    # THE INFLATION GUARD, and the one that mattered most. The first version counted
    # every U.S. Code citation in operative text and reported 14.1% short against a
    # 10% threshold -- measuring cross-references, which is the exact false-positive
    # class A5 removed from `amends`. A definitions or appropriations section naming
    # statutes amends none of them.
    cross_reference = (
        "In this section: The term Coastal Plain has the meaning given in section 1002 "
        "of the Alaska National Interest Lands Conservation Act (16 U.S.C. 3143), and "
        "nothing in this section affects 30 U.S.C. 181 or 42 U.S.C. 6501."
    )
    assert amendment_targets(cross_reference) == set()

    # ...while a real target in the same shape is still counted.
    real = "Section 1240B of the Food Security Act of 1985 (16 U.S.C. 3839aa) is amended by striking."
    assert "16 U.S.C. 3839aa" in amendment_targets(real)


def test_shortfall_detector_sees_unicode_dash_suffixed_sections():
    # "16 U.S.C. 3839aa-2" is written with an EN-DASH in the source. The parser's own
    # hug cannot cross it, which is a separate resolution defect this scan quantifies;
    # the scan's detector must not inherit the same blindness or it cannot see it.
    text = "Section 1240B of the Food Security Act of 1985 (16 U.S.C. 3839aa\u20132) is amended by striking."
    found = amendment_targets(text)
    assert any("3839aa" in c for c in found), found


def test_shortfall_detector_counts_resolvable_forms_it_should():
    # Both explicit forms must be seen, or B under-counts and reports a false clean.
    text = (
        "Section 2304 of title 10, United States Code, is amended, and "
        "7 U.S.C. 2012 is amended by striking."
    )
    found = amendment_targets(text)
    assert "10 U.S.C. 2304" in found
    assert "7 U.S.C. 2012" in found


# --------------------------------------------------------------------------- #
# V21: the context-combination population.
# --------------------------------------------------------------------------- #
def test_context_combinations_are_distinguishable():
    # V21 reports a DISTRIBUTION across combinations, so the harness must be able to
    # tell each apart -- a collapse to one bucket would render as a clean result.
    mixed = _unit(("operative", "a"), ("quoted", "b"))
    operative_only = _unit(("operative", "a"))
    quoted_only = _unit(("quoted", "b"))
    all_three = _unit(("operative", "a"), ("quoted", "b"), ("header", "c"))
    combos = {
        tuple(sorted({s.context for s in u.segments}))
        for u in (mixed, operative_only, quoted_only, all_three)
    }
    assert len(combos) == 4, f"combinations collapsed: {combos}"
    assert ("operative", "quoted") in combos
