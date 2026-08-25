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
    # The starvation clause: a small count is not a finding.
    assert "the usual cause of a starved result" in doc
    assert ("A small count means the terms rarely co-occur, NOT that "
            "few such bills exist -- re-query narrower before "
            "concluding anything") in doc
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
    assert "field operators pass through" in doc


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


def test_removed_parameters_are_disclaimed():
    # The signature break is part of what shapes input: the description
    # says search_bills does not take the removed window parameters --
    # and, post-Q10, no longer disclaims the restored date bounds.
    doc = _doc()
    assert "does NOT take offset/sort/format" in doc
    assert "date filters" not in doc
