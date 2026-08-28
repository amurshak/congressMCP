"""Step 5 of the govinfo-search work order (spec section 6.5): the tool
description is load-bearing (D17's root harm was matching semantics the
caller was never told). Every mandatory item is pinned INDIVIDUALLY --
an enumeration whose members are not individually pinned is the
assumption the section-6.5 list exists to reject.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")


def _doc() -> str:
    """The docstring, whitespace-flattened: inspect.getdoc dedents and the
    source wraps at ~80 cols, so phrase pins match on the flattened text."""
    from congress_api.features.bills_tool import bills
    doc = inspect.getdoc(inspect.unwrap(bills))
    assert doc, "bills tool has no docstring"
    return " ".join(doc.split())


def test_item_1_names_the_corpus():
    doc = _doc()
    assert "full text of congressional bills" in doc
    assert "every version of every bill" in doc
    assert "GovInfo BILLS collection" in doc


def test_item_2_matching_semantics():
    # Pins the section-6.5 item-2 BLOCKQUOTE (Addendum 3 as bounced and
    # re-issued with mechanical acceptance): the three deliberate
    # properties are pinned by their own sentences, not paraphrases.
    doc = _doc()
    # AND narrowing, stated with its consequence.
    assert ("words are ANDed -- every term must appear in the SAME "
            "document, so each added word strictly shrinks the result "
            "set and can never grow it") in doc
    assert "Start with the distinctive minimum" in doc
    # The worked example WITH MAGNITUDES -- the clause that changes
    # behavior where the abstract statement measurably did not.
    assert ('"Radiation Exposure Compensation Act amendments '
            'downwinders" returns 1 bill') in doc
    assert ("dropping the two description words returns 26, including "
            "the enacted vehicle") in doc
    # The starvation clause: a small count is not a finding. The remedy is
    # BROADER, not narrower (maintainer correction, 2026-08-27): under AND
    # semantics a starved result came from too many words, so the fix is
    # dropping words -- the section-6.5 blockquote's "re-query narrower"
    # wording is the bug, flagged back to the spec session.
    assert "the usual cause of a starved result" in doc
    assert ("A small count means the terms rarely co-occur, NOT that "
            "few such bills exist -- re-query broader (drop words) "
            "before concluding anything") in doc
    assert "re-query narrower" not in doc
    # The cross-tool boundary line: search_bill_text ORs and rewards
    # synonyms; this path intersects and discards.
    assert ("unlike search_bill_text, which ORs its queries array and "
            "rewards adding alternate phrasings, an added synonym on "
            "this path intersects and discards") in doc
    # Retained clauses, alongside (their own bullet, sentence-case).
    assert "Do NOT quote bill names" in doc
    assert "quoted phrases measured to miss title text" in doc
    assert 'title:"..." / shorttitle:"..." for exact titles' in doc
    assert "OR / NOT available" in doc
    # "field operators pass through" is deliberately GONE -- Addendum 4
    # item 0 replaced the open-ended claim with the measured enumeration
    # (test_item_9_field_enumeration_each_field_pinned).


def test_item_3_version_discovery():
    doc = _doc()
    assert "matched_versions" in doc
    # match-scoped by construction, not the complete set
    assert "not the bill's complete version set" in doc
    # the affirmative discovery path: fielded no-text query
    assert 'keywords="congress:119 billtype:s docnumber:1071"' in doc
    # the pinned-version error disclosure stays
    assert "version_not_available" in doc


def test_item_4_count_semantics():
    doc = _doc()
    assert "total_version_matches" in doc
    assert "version packages" in doc.lower()
    assert "can exceed the number of distinct bills" in doc
    assert "results_count counts the bills actually returned" in doc


def test_item_5_pagination():
    doc = _doc()
    assert "next_page_token back verbatim" in doc
    assert "run short" in doc
    assert "reappear" in doc and "same identity" in doc


def test_item_6_fallback():
    doc = _doc()
    assert "recency_window_fallback" in doc
    assert "fallback_trigger" in doc
    assert "not the corpus" in doc.lower()


def test_item_7_blank_keywords_rejected():
    doc = _doc()
    assert "blank or whitespace-only keywords are rejected" in doc


def test_item_8_time_bounding():
    doc = _doc()
    assert "fromDateTime/toDateTime bound the VERSION'S PUBLICATION DATE" \
        in doc
    assert "inclusive both ends" in doc
    assert "either side may be given alone" in doc
    assert "datetimes truncated to the date" in doc
    assert "NOT congress.gov's update date" in doc
    assert "the same bounds filter updateDate over the window" in doc


def test_item_9_field_enumeration_each_field_pinned():
    # Addendum 4 item 0 (section 6.5 item 9): the docstring enumerates every
    # supported fielded operator WITH ITS MEASURED VALUE FORM. Each field is
    # pinned individually with its example -- an enumeration whose members
    # are not individually pinned is the assumption this list exists to
    # reject. Probe artifacts: runs/govinfo-search/ (2026-08-27 field run).
    doc = _doc()
    for pinned in (
        "congress:119",
        "billtype:hr (hr s hjres sjres hconres sconres hres sres)",
        "docnumber:4631",
        "billversion:enr (a version code)",
        "chamber:house / chamber:senate",
        "member:schumer (member last name)",
        "memberparty:r (single party letter)",
        "memberstate:mo (two-letter state code)",
        "committee:judiciary (a committee-name word)",
        "actiondate:2025-01-03 (YYYY-MM-DD)",
        "publishdate:2025-07-23",
        "isprivate:false",
        "isappropriation:false",
        'uscodecitation:"42 U.S.C. 2210"',
        'statutecitation:"133 Stat. 1198"',
        'plawcitation:"Public Law 101-426"',
        "the three citation fields take the quoted citation string",
        "field:range(a,b) works on date fields",
    ):
        assert pinned in doc, pinned
    # The old open-ended phrasing is GONE: "operator pass-through" without
    # the operator list was the D17 root harm again.
    assert "field operators pass through" not in doc


def test_item_9_unrecognized_field_line_matches_the_probe():
    # The preregistered silent-empty expectation was FALSIFIED: the probe
    # measured HTTP 500 (the section-2b malformed-request family), so per
    # the contract the "matches nothing" line is SKIPPED and the docstring
    # states the measured error behavior instead. Artifact:
    # runs/govinfo-search/ unrecognized_field_prereg.json.
    doc = _doc()
    assert "silently matches nothing" not in doc
    assert "A field name NOT on this list is a query error upstream" in doc
    assert "do not invent field names" in doc


def test_q11_snippets_bullet_with_quoted_governs():
    # Addendum 4 item 1: the snippet tri-state is stated structurally, and
    # the quoted-governs sentence is MANDATORY -- without it Q11 reintroduces
    # the F4/A1 failure shape (text the bill is removing presented as what
    # the bill says) on the tool consumers reach first.
    doc = _doc()
    assert 'snippet_status "localized" with a snippet object' in doc
    assert '"not_localized" with snippet null' in doc
    assert "BOTH fields absent means localization was not attempted" in doc
    assert "snippet_fetch: N (default 0, hard cap 5)" in doc
    assert "UNCACHED hits in rank order" in doc
    assert ("carries the matched unit's section_id and match_contexts") in doc
    # The quoted-governs sentence, pinned as a sentence.
    assert ('"quoted" governs: a snippet drawn from quoted material is '
            "language the bill is inserting or striking -- delimited in "
            "the snippet text -- NOT what current law says") in doc


def test_q12_diagnostics_bullet_order_caveat_and_small_can_be_correct():
    # Addendum 4 continuation (Q12, ruled 2026-08-27): the ladder's two
    # mandatory description lines are the order caveat and the
    # small-can-be-correct line -- without them the ladder reads as a
    # verdict against small results, which is exactly the misreading the
    # ruling forbids.
    doc = _doc()
    assert "diagnostics.term_ladder" in doc
    assert "2+ text terms and total_version_matches < 10" in doc
    assert "chopped from the right" in doc
    # The order caveat, pinned as its own sentences.
    assert ("right-chopping isolates trailing added words (the usual "
            "failure); when the rare term sits FIRST, every rung stays "
            "small down to the single-term rung -- which is the correct "
            "reading: the core term is rare") in doc
    # The small-can-be-correct line.
    assert ("A small count can be a CORRECT answer -- the ladder is "
            "evidence for judging a result, not a verdict against it") in doc
    # The terminal denominator rung and the constraints leg.
    assert "the ladder's denominator" in doc
    assert "diagnostics.leave_one_out" in doc
    assert ("the omission that restores hits names the dead "
            "constraint") in doc
    # Probe failure honesty and absence semantics.
    assert 'count null with status "probe_failed", never 0' in doc
    assert ("Absence of diagnostics means it did not fire, never that "
            "it ran and found nothing") in doc


def test_addendum5_uscodecitation_note_trap():
    # Addendum 5 (2026-08-27): GovInfo's citation index keys the code
    # section, not notes published under it, so the two citation fields
    # silently DISAGREE about a note-codified statute. Consumer-found;
    # figures re-probed and confirmed before pinning (standing rule) --
    # artifacts runs/govinfo-search/2026-08-27T173136Z/ (Congress-119
    # scope reconstructs the consumer's numbers exactly: 7 bills each
    # side, zero RECA on the uscodecitation side; unscoped confirms the
    # trap corpus-wide, 201 vs 63 version matches).
    doc = _doc()
    assert ("uscodecitation matches the CODE SECTION, not notes "
            "published under it") in doc
    assert "note-codified" in doc  # the ruled acceptance-grep phrase
    assert ('does NOT match uscodecitation:"42 U.S.C. 2210"') in doc
    # The measured contrast, with figures (the section-6.5 lesson: the
    # abstract warning alone does not change behavior).
    assert "7 bills, ZERO of them RECA" in doc
    assert ('plawcitation:"Public Law 101-426" returns the 7-bill RECA '
            "answer set") in doc
    # The remedy and the preference rule.
    assert ("for a note-codified Act use "
            'plawcitation:"Public Law NNN-NNN"') in doc
    assert "prefer plawcitation" in doc


def test_removed_parameters_are_disclaimed():
    # The signature break is part of what shapes input: the description
    # says search_bills does not take the removed window parameters --
    # and, post-Q10, no longer disclaims the restored date bounds.
    doc = _doc()
    assert "does NOT take offset/sort/format" in doc
    assert "date filters" not in doc
