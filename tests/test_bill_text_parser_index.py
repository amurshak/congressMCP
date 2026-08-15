import os
from pathlib import Path

import pytest

from congress_api.features.bill_text.index import BillTextIndex, fts_literal, has_token, normalized_query
from congress_api.features.bill_text.client import (
    ADMINISTRATIVE,
    NEGATIVE,
    REISSUE,
    TEXT_STAGE,
    VERSION_CODES,
    BillTextError,
    TextVersion,
    order_versions,
    version_category,
    _category_note,
    _xml_url_from_summary,
)
from congress_api.features.bill_text.models import AncestorNode
from congress_api.features.bill_text.parser import (
    MAX_UNIT_BYTES,
    SUBDIV_CODE,
    Segment,
    Unit,
    byte_split_unit,
    node_kind_for,
    parse_bill_xml,
    render_segments,
)
from congress_api.features.bill_text.tools import (
    _hidden_section_count,
    _hidden_section_note,
    _max_section_depth,
    _resolve_unit,
    _toc_nodes,
)


FIXTURES = Path(__file__).parent / "fixtures"


def parse_fixture(name):
    return parse_bill_xml((FIXTURES / name).read_bytes(), "BILLS-119s1071enr", "enr", "2025-12-19T03:11:48Z")


def test_parser_skips_toc_and_preserves_quoted_contexts():
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)

    toc_hits = index.search([normalized_query("table of contents")], 10)
    assert toc_hits == []

    hits = index.search([normalized_query("icebreaker")], 10)
    assert hits
    first = hits[0]
    assert "quoted" in first.match_contexts
    assert "is amended by striking" in first.snippet
    assert first.unit.is_amendatory
    assert first.unit.amends == [{"kind": "usc", "cite": "14 U.S.C. 5601"}]


def test_resolution_body_gets_synthetic_units():
    parsed = parse_fixture("hres_trimmed.xml")
    assert parsed.sections_indexed > 0
    ids = [unit.section_id for unit in parsed.units]
    assert "PRE:1" in ids
    assert "RC:1" in ids
    assert _resolve_unit(parsed.units, "PRE:1").section_id == "PRE:1"


def test_bare_duplicate_section_id_errors_with_matches():
    parsed = parse_fixture("bill_text_trimmed.xml")
    result = _resolve_unit(parsed.units, "101")
    assert result["error"]["code"] == "ambiguous_section_id"
    assert "D:A/T:I/S:101" in result["error"]["detail"]["matches"]
    assert "D:B/T:I/S:101" in result["error"]["detail"]["matches"]


def test_query_escaping_and_token_validation():
    assert fts_literal('icebreaker" OR "x') == '"icebreaker"" OR ""x"'
    assert has_token("NEAR")
    assert not has_token("*** --- ^^^")


def test_govinfo_xml_link_accepts_api_endpoint_shape():
    assert _xml_url_from_summary({"download": {"xmlLink": "https://api.govinfo.gov/packages/BILLS-x/xml"}}).endswith("/xml")


def test_govinfo_summary_never_returns_metadata_links_as_bill_text():
    # MODS/PREMIS are package metadata, not Bill DTD text. When no xmlLink exists the
    # extractor must return None (so bill_dtd_unavailable fires), never a metadata .xml
    # -- which parse_bill_xml would silently turn into an empty "successful" bill.
    assert _xml_url_from_summary({"download": {
        "modsLink": "https://api.govinfo.gov/packages/BILLS-x/mods.xml",
        "premisLink": "https://api.govinfo.gov/packages/BILLS-x/premis.xml",
        "pdfLink": "https://api.govinfo.gov/packages/BILLS-x/pdf",
    }}) is None
    # xmlLink still wins even when metadata links are also present.
    assert _xml_url_from_summary({"download": {
        "xmlLink": "https://api.govinfo.gov/packages/BILLS-x/xml",
        "modsLink": "https://api.govinfo.gov/packages/BILLS-x/mods.xml",
    }}).endswith("/xml")
    assert _xml_url_from_summary({"download": {}}) is None


def test_rrf_dedupes_duplicate_queries():
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)
    single = index.search(["icebreaker"], 10)[0].score
    duplicate = index.search(["icebreaker", "icebreaker"], 10)[0].score
    assert duplicate == single


def test_toc_depth_and_node_cap_shape():
    parsed = parse_fixture("bill_text_trimmed.xml")
    toc, truncated, depth, _ = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert depth == 2
    assert not truncated  # node cap is a separate concern from depth-limiting
    assert toc[0].section_id == "D:A"
    # Size-per-branch: a division node aggregates the bytes of everything under it,
    # so it is never smaller than any single descendant section (spec §9).
    assert toc[0].subtree_byte_length >= max((c.byte_length for c in toc[0].children), default=0)


def test_toc_flags_sections_hidden_below_returned_depth():
    # Regression (S. 1411): sections nested under a subtitle sit one level below a
    # default depth-2 TOC. They must not vanish silently -- toc_truncated=false
    # with children:[] reads as "this subtitle is empty" and a consumer stops.
    xml = (
        b"<bill><legis-body>"
        b"<title><enum>I</enum><header>First</header>"
        b"<subtitle><enum>A</enum><header>Sub A</header>"
        b"<section><enum>101</enum><header>Sec 101</header><text>alpha</text></section>"
        b"<section><enum>102</enum><header>Sec 102</header><text>beta</text></section>"
        b"</subtitle></title>"
        b"<title><enum>II</enum><header>Second</header>"
        b"<section><enum>201</enum><header>Sec 201</header><text>gamma</text></section>"
        b"</title></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    # The two sections under T:I/ST:A sit at depth 3; T:II/S:201 sits at depth 2.
    assert _max_section_depth(parsed.units) == 3
    _, node_capped, actual, _ = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert not node_capped  # nothing was cut by the node cap
    assert _hidden_section_count(parsed.units, actual) == 2  # the two ST:A sections
    # Requesting the required depth reveals everything; nothing hidden.
    assert _hidden_section_count(parsed.units, 3) == 0


def test_hidden_section_count_sees_byte_split_sections_below_depth():
    # Regression: a section that exceeds MAX_UNIT_BYTES with no subdivision is emitted
    # ONLY as `.../S:101/CHUNK:n` units. Keying "is this a section?" off the emitted
    # leaf (CHUNK) hid it from the completeness check, so a depth-2 TOC returned
    # children:[] with toc_truncated=false -- asserting a completeness that wasn't
    # there. Classify from the id (strip the byte-cut CHUNK), and dedupe so the three
    # chunks of one section count as one hidden section, not three.
    big = ("lorem ipsum dolor sit amet " * 400).encode()
    xml = (
        b"<bill><legis-body>"
        b"<title><enum>I</enum><header>First</header>"
        b"<subtitle><enum>A</enum><header>Sub A</header>"
        b"<section><enum>101</enum><header>Big Sec</header><text>" + big + b"</text></section>"
        b"</subtitle></title></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    # Only CHUNK units exist for S:101; there is no plain `.../S:101` unit.
    ids = [u.section_id for u in parsed.units]
    assert ids and all(i.endswith(("/CHUNK:1", "/CHUNK:2", "/CHUNK:3")) for i in ids)
    assert _max_section_depth(parsed.units) == 3  # the section sits at depth 3, not 1
    _, node_capped, actual, _ = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert not node_capped
    assert _hidden_section_count(parsed.units, actual) == 1  # one section, deduped
    assert _hidden_section_count(parsed.units, 3) == 0  # revealed at its own depth
    assert _hidden_section_note(parsed.units, actual, 2, parsed.subtree_bytes) is not None


def test_subdivided_parent_own_segments_are_byte_bounded():
    # F19 (spec §18; §5 post-condition "no emitted chunk exceeds the threshold"):
    # EVERY unit is subject to MAX_UNIT_BYTES, including a subdivided parent's own
    # intro/trailing segments. Before the fix, a section whose matter before the
    # first subsection exceeded the cap shipped whole -- the one path exempt from
    # the bound that chunking exists to enforce.
    big_intro = ("intro matter before any subsection " * 300).encode()  # ~10.5 KB
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>1</enum><header>Sec 1</header>"
        b"<text>" + big_intro + b"</text>"
        b"<subsection><enum>a</enum><header>ss a</header><text>alpha</text></subsection>"
        b"<subsection><enum>b</enum><header>ss b</header><text>beta</text></subsection>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119hr1ih", "ih", None)
    by_id = {u.section_id: u for u in parsed.units}
    oversize = {u.section_id: u.byte_length for u in parsed.units if u.byte_length > MAX_UNIT_BYTES}
    assert oversize == {}
    # The parent survives as a container: header only, with its body in CHUNK
    # children listed BEFORE the structural children (assembly order unchanged).
    parent = by_id["S:1"]
    chunk_ids = [cid for cid in parent.child_ids if "/CHUNK:" in cid]
    assert chunk_ids == [f"S:1/CHUNK:{i}" for i in range(1, len(chunk_ids) + 1)]
    assert len(chunk_ids) >= 2  # 10.5 KB of intro cannot fit one 8 KB chunk
    assert parent.child_ids == chunk_ids + ["S:1/SS:a", "S:1/SS:b"]
    assert all(cid in by_id for cid in parent.child_ids)
    # No content lost: every word of the intro is retrievable from the chunks.
    chunk_text = " ".join(by_id[cid].display_text for cid in chunk_ids)
    assert chunk_text.split().count("matter") == 300
    # Subtree accounting stays exact: own + sum of descendants.
    descendants = sum(by_id[cid].byte_length for cid in parent.child_ids)
    assert parsed.subtree_bytes["S:1"] == parent.byte_length + descendants


def test_hidden_section_count_excludes_subsection_byte_chunks():
    # The dual of the above: a byte chunk of a SUBSECTION (`.../S:101/SS:a/CHUNK:n`)
    # is sub-section navigation noise and must NOT be advertised as a hidden section.
    # Only the real S:101 (emitted as a subdivided parent) counts.
    big = ("lorem ipsum dolor sit amet " * 400).encode()
    xml = (
        b"<bill><legis-body>"
        b"<title><enum>I</enum><header>First</header>"
        b"<subtitle><enum>A</enum><header>Sub A</header>"
        b"<section><enum>101</enum><header>Sec 101</header>"
        b"<subsection><enum>a</enum><header>ss a</header><text>" + big + b"</text></subsection>"
        b"<subsection><enum>b</enum><header>ss b</header><text>small</text></subsection>"
        b"</section></subtitle></title></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    assert "T:I/ST:A/S:101" in ids  # the subdivided parent is a real section
    assert any(i.startswith("T:I/ST:A/S:101/SS:a/CHUNK:") for i in ids)  # noise present
    assert _max_section_depth(parsed.units) == 3  # S:101 at depth 3; SS/CHUNK excluded
    _, _, actual, _ = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert _hidden_section_count(parsed.units, actual) == 1  # just S:101, not its chunks


def test_oversized_leaf_byte_fallback_uses_chunk_ids():
    # A byte cut enumerates nothing, so it is addressed CHUNK:{n}, never PARA:{n}
    # (which is reserved for a real <paragraph> enum) -- spec §5, decision 1.
    unit = Unit(
        section_id="D:A/T:I/S:999",
        ancestor_path=[AncestorNode(type="D", enum="A", header="Division")],
        header="Large leaf",
        segments=[Segment("operative", "\n\n".join(["needle " * 600, "haystack " * 600]))],
    )
    chunks = byte_split_unit(unit)
    assert [chunk.section_id for chunk in chunks] == ["D:A/T:I/S:999/CHUNK:1", "D:A/T:I/S:999/CHUNK:2"]
    assert all(chunk.byte_length <= 8_000 for chunk in chunks)


def test_trailing_text_after_last_subdivision_is_captured():
    # Regression: an oversized section subdivided into subsections also carries flush
    # text after the last subsection (the classic hanging paragraph). The old parent
    # captured only the intro (it stopped at the first subdivision), so the trailing
    # text existed in no unit -- absent from the index and get_bill_section, with no
    # disclosure. It must now live in the parent's own segments.
    big = ("lorem ipsum dolor sit amet " * 400).encode()
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>101</enum><header>Sec 101</header>"
        b"<text>INTRO MATTER HERE</text>"
        b"<subsection><enum>a</enum><header>ss a</header><text>" + big + b"</text></subsection>"
        b"<subsection><enum>b</enum><header>ss b</header><text>" + big + b"</text></subsection>"
        b"<text>TRAILING CLOSING TEXT THAT MATTERS</text>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119hr1ih", "ih", None)
    parent = _resolve_unit(parsed.units, "S:101")
    own = " ".join(seg.text for seg in parent.segments)
    assert "INTRO MATTER HERE" in own
    assert "TRAILING CLOSING TEXT THAT MATTERS" in own
    # And it is searchable, not merely stored.
    index = BillTextIndex(parsed)
    hits = index.search([normalized_query("trailing closing text that matters")], 5)
    assert hits and hits[0].unit.section_id == "S:101"


def test_trailing_text_capture_does_not_resurrect_struck_matter():
    # The dual guard: a STRUCK trailing element must stay excluded -- capturing the
    # section's own text must not become a hole in the struck-text carve-out.
    big = ("lorem ipsum dolor sit amet " * 400).encode()
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>101</enum><header>Sec 101</header>"
        b"<subsection><enum>a</enum><header>ss a</header><text>" + big + b"</text></subsection>"
        b'<text changed="deleted">STRUCK TRAILING MUST NOT APPEAR</text>'
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119hr1ih", "ih", None)
    alltext = " ".join(seg.text for u in parsed.units for seg in u.segments)
    assert "STRUCK TRAILING MUST NOT APPEAR" not in alltext


def test_sections_under_non_structural_container_are_not_duplicated_as_whole_body_unit():
    # Regression: <chapter>/<subchapter>/<subpart> are real DTD levels but not
    # STRUCTURE_TYPES keys. The old whole-body U:1 guard sniffed only the body's direct
    # children for a structural tag; with sections nested under a chapter it saw none,
    # fired U:1 over the entire body, and duplicated every section verbatim under a
    # spurious citable root (also inflating sections_indexed).
    xml = (
        b"<bill><legis-body>"
        b"<chapter><enum>1</enum><header>Chap</header>"
        b"<section><enum>101</enum><header>S1</header><text>alpha content</text></section>"
        b"<section><enum>102</enum><header>S2</header><text>beta content</text></section>"
        b"</chapter></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119hr2ih", "ih", None)
    ids = [u.section_id for u in parsed.units]
    assert ids == ["S:101", "S:102"]  # no spurious U:1
    assert parsed.sections_indexed == 2  # not 3


def test_whole_body_unit_still_emitted_for_unstructured_body_but_not_when_all_struck():
    # The positive case survives: a body of loose text with no addressable structure is
    # captured as U:1 so nothing is lost.
    loose = parse_bill_xml(
        b"<bill><legis-body><text>loose body text, no sections</text></legis-body></bill>",
        "BILLS-119hr3ih", "ih", None,
    )
    assert [u.section_id for u in loose.units] == ["U:1"]
    # But an all-struck body (a reported substitute striking the entire prior text) has
    # nothing to capture -- U:1 would be empty -- so it must not be emitted at all.
    struck = parse_bill_xml(
        b'<bill><legis-body><section changed="deleted"><enum>1</enum><text>gone</text></section></legis-body></bill>',
        "BILLS-119hr4ih", "ih", None,
    )
    assert all(u.section_id != "U:1" for u in struck.units)


def test_preamble_whereas_become_addressable_pre_units():
    # Real GovInfo simple resolutions nest <whereas> inside a top-level
    # <preamble> that is a sibling of <resolution-body>. Those clauses are the
    # substance of the resolution and must not be silently dropped.
    parsed = parse_fixture("hres_preamble_trimmed.xml")
    ids = [unit.section_id for unit in parsed.units]
    assert ["PRE:1", "PRE:2", "PRE:3"] == [i for i in ids if i.startswith("PRE:")]
    assert "S:1" in ids
    assert parsed.sections_indexed >= 4  # 3 whereas + 1 section
    assert _resolve_unit(parsed.units, "PRE:2").section_id == "PRE:2"
    index = BillTextIndex(parsed)
    hits = index.search([normalized_query("coastal infrastructure")], 10)
    assert hits and hits[0].unit.section_id == "PRE:2"


def test_order_versions_puts_dateless_enrolled_first():
    # Congress.gov returns date=None for the enrolled entry; a date-primary sort
    # must not bury it behind dated earlier versions.
    versions = [
        TextVersion(code="enr", date="", type_label="Enrolled Bill"),
        TextVersion(code="eah", date="2025-12-10T05:00:00Z", type_label="Engrossed Amendment House"),
        TextVersion(code="es", date="2025-08-01T04:00:00Z", type_label="Engrossed in Senate"),
        TextVersion(code="is", date="2025-03-14T04:00:00Z", type_label="Introduced in Senate"),
    ]
    assert order_versions(versions)[0].code == "enr"
    # Among dated versions the later date still wins.
    dated = [v for v in versions if v.code != "enr"]
    assert order_versions(dated)[0].code == "eah"


def test_order_versions_precedence_primary_does_not_promote_null_dated_nonterminal():
    # A3 residual (credential-free counterexample): with NO enrolled version, a
    # dateless non-terminal entry must NOT float to the top. The prior
    # null-as-most-recent rule inverted the bug -- it resolved version=None to the
    # introduced text. Precedence-primary makes an undated introduced (ih=10) lose
    # to a dated engrossed (eh=40); date never participates in tier selection.
    versions = [
        TextVersion(code="ih", date="", type_label="Introduced in House"),
        TextVersion(code="eh", date="2025-06-01T04:00:00Z", type_label="Engrossed in House"),
    ]
    assert order_versions(versions)[0].code == "eh"


def test_order_versions_logs_unknown_codes_loudly(caplog):
    # A3 rests on this: §3 accepted precedence-primary because a new/unknown GPO code
    # fails LOUD, not silent. Such a code sorts last (so if it marks the newest stage an
    # older version wins) BUT a WARNING is logged -- that log is the whole tradeoff's
    # condition. Pin it so a refactor can't silence it. Confirmed live: version=None on
    # S.1071/119 resolves to `enr` (BILLS-119s1071enr), the defect-1 repro, end-to-end.
    import logging

    with caplog.at_level(logging.WARNING, logger="congress_api.features.bill_text.client"):
        ordered = order_versions(
            [
                TextVersion(code="xz", date="2099-01-01", type_label="Future GPO code"),
                TextVersion(code="enr", date="", type_label="Enrolled"),
            ]
        )
    assert ordered[0].code == "enr"   # known beats unknown regardless of the unknown's date
    assert ordered[-1].code == "xz"   # unknown sorts last
    assert any(
        "Unknown bill text version code" in r.message and "xz" in r.message
        for r in caplog.records
        if r.levelno == logging.WARNING
    )


def test_order_versions_all_unknown_codes_fall_back_to_date_primary():
    # Every code unknown -> precedence 0 for all -> the date tie-break governs,
    # i.e. date-primary among them (later date first).
    versions = [
        TextVersion(code="zz1", date="2025-01-01", type_label="?"),
        TextVersion(code="zz2", date="2025-09-09", type_label="?"),
    ]
    assert order_versions(versions)[0].code == "zz2"


def test_f1_reenrolled_supersedes_enrolled():
    # F1 correctness bug 1: `renr` was absent from the 17-code table, so it took
    # precedence 0 and sorted LAST -- `enr` won and the tool returned superseded
    # text as the bill's final text. A re-issue must outrank what it re-issues.
    versions = [
        TextVersion(code="enr", date="", type_label="Enrolled Bill"),
        TextVersion(code="renr", date="", type_label="Re-enrolled Bill"),
    ]
    assert order_versions(versions)[0].code == "renr"
    # Same shape one tier down: re-engrossed amendments supersede the engrossed ones.
    assert order_versions(
        [
            TextVersion(code="eah", date="2025-06-01", type_label="Engrossed Amendment House"),
            TextVersion(code="reah", date="", type_label="Re-engrossed Amendment House"),
        ]
    )[0].code == "reah"


def test_f1_agreed_to_resolution_does_not_resolve_to_introduced():
    # F1 correctness bug 2: simple and concurrent resolutions never receive `enr`,
    # and `ath`/`ats` were absent from the table entirely -- so EVERY agreed-to
    # resolution resolved to `ih`, the introduced text, silently. Agreed-to is the
    # terminal authoritative text for a resolution.
    versions = [
        TextVersion(code="ih", date="2025-06-01", type_label="Introduced in House"),
        TextVersion(code="ath", date="", type_label="Agreed to House"),
    ]
    assert order_versions(versions)[0].code == "ath"
    assert order_versions(
        [
            TextVersion(code="is", date="2025-06-01", type_label="Introduced in Senate"),
            TextVersion(code="ats", date="", type_label="Agreed to Senate"),
        ]
    )[0].code == "ats"


def test_f1_negative_terminal_versions_never_win():
    # "Latest" means most authoritative text, not most recent artifact. Failed
    # passage / laid on table / indefinitely postponed / vitiated are chronologically
    # LAST and not authoritative, so a rank-only-by-chronology table picks exactly
    # the wrong one. Every negative code must lose to any real text stage.
    for negative in ("fph", "fps", "fah", "lth", "lts", "iph", "ips", "pav"):
        versions = [
            TextVersion(code=negative, date="2025-12-31", type_label="negative"),
            TextVersion(code="ih", date="2025-01-01", type_label="Introduced in House"),
        ]
        assert order_versions(versions)[0].code == "ih", negative
        assert version_category(negative) == NEGATIVE
    # ... and lose to an UNKNOWN code too: a code GPO adds later may be a new
    # authoritative stage, whereas these are known not to be.
    assert order_versions(
        [
            TextVersion(code="fph", date="2025-12-31", type_label="Failed Passage House"),
            TextVersion(code="xz", date="2025-01-01", type_label="Future GPO code"),
        ]
    )[0].code == "xz"


def test_f1_administrative_versions_do_not_displace_the_stage_they_annotate():
    # Sponsor changes and print orders are chronologically later but textually
    # identical to the stage they annotate, so they must never displace it -- and
    # must not displace a LATER stage either.
    for admin in ("ash", "sas", "sc", "as", "oph", "ops", "pwah", "rhuc"):
        assert version_category(admin) == ADMINISTRATIVE
        versions = [
            TextVersion(code=admin, date="2025-12-31", type_label="administrative"),
            TextVersion(code="rh", date="2025-01-01", type_label="Reported in House"),
        ]
        assert order_versions(versions)[0].code == "rh", admin


def test_f1_second_chamber_receipt_sits_after_engrossment_not_with_introduced():
    # rfh/rfs (and the rdh/rds/hdh/hds siblings) carry the ORIGINATING chamber's
    # passed text; ranking them with ih/is would bury a passed bill under its own
    # introduced version.
    for received in ("rfh", "rfs", "rdh", "rds", "hdh", "hds"):
        assert order_versions(
            [
                TextVersion(code=received, date="", type_label="received"),
                TextVersion(code="is", date="2025-12-31", type_label="Introduced in Senate"),
            ]
        )[0].code == received


def test_f1_precedence_table_covers_every_published_govinfo_code():
    # The table was 17 of GovInfo's 53 published codes, and BOTH correctness bugs
    # F1 names were absences rather than misplacements. Pin the full published list
    # (govinfo.gov/help/bills) so a future code addition is a visible test failure
    # rather than a silent precedence-0 fallthrough.
    published = {
        "as", "ash", "ath", "ats", "cdh", "cds", "cph", "cps", "eah", "eas",
        "eh", "eph", "enr", "es", "fah", "fph", "fps", "hdh", "hds", "ih",
        "iph", "ips", "is", "lth", "lts", "oph", "ops", "pap", "pav", "pch",
        "pcs", "pp", "pwah", "rah", "ras", "rch", "rcs", "rdh", "rds", "reah",
        "renr", "res", "rfh", "rfs", "rh", "rhuc", "rih", "ris", "rs", "rth",
        "rts", "sas", "sc",
    }
    assert len(published) == 53
    assert published - set(VERSION_CODES) == set(), "published codes missing from the table"
    assert set(VERSION_CODES) - published == set(), "table carries codes GovInfo does not publish"
    # Every code carries a category, not just a rank -- the categorisation is what
    # keeps a later editor from "correcting" a rank back toward chronological order.
    assert all(
        category in {TEXT_STAGE, REISSUE, ADMINISTRATIVE, NEGATIVE}
        for _, category in VERSION_CODES.values()
    )


def test_f1_non_text_stage_selection_is_disclosed_to_the_caller():
    # Rank keeps these from displacing real text but says nothing when one is
    # selected anyway because it is all the bill has. Silence there presents a
    # failed-passage artifact as the latest text -- wrong answer, success envelope.
    assert "negative or terminated action" in (_category_note("fph") or "")
    assert "administrative version" in (_category_note("ash") or "")
    assert _category_note("enr") is None
    assert _category_note("renr") is None


def test_byte_split_enforces_cap_on_unbroken_paragraph():
    # A single paragraph with no blank-line breaks must still be split under cap.
    giant = "word " * 5000  # ~25 KB, no "\n\n"
    unit = Unit(
        section_id="D:A/T:I/S:1/SS:(a)",
        ancestor_path=[AncestorNode(type="D", enum="A", header="Division")],
        header="In general",
        segments=[Segment("operative", giant)],
    )
    chunks = byte_split_unit(unit)
    assert len(chunks) > 1
    assert all(chunk.byte_length <= MAX_UNIT_BYTES for chunk in chunks)
    assert [c.section_id for c in chunks] == [f"D:A/T:I/S:1/SS:(a)/CHUNK:{i}" for i in range(1, len(chunks) + 1)]


def test_amends_extracts_longhand_and_amendatory_shorthand_usc():
    # Longhand and shorthand-with-amendatory-verb are captured; a bare
    # cross-reference citation (no amendatory verb) is excluded, and named-Act
    # titles are never resolved.
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Amends multiple forms",
        segments=[
            Segment(
                "operative",
                "Section 5601 of title 14, United States Code, is amended. "
                "Section 3 of the Food and Nutrition Act of 2008 (7 U.S.C. 2012) is amended by striking subsection (u). "
                "Section 2028(a)(2)(A)(ii) of that Act (7 U.S.C. 2028) is amended. "
                "The Secretary shall consult 42 U.S.C. 1396 for guidance.",
            )
        ],
    )
    assert unit.amends == [
        {"kind": "usc", "cite": "14 U.S.C. 5601"},
        {"kind": "usc", "cite": "7 U.S.C. 2012"},
        {"kind": "usc", "cite": "7 U.S.C. 2028"},
    ]
    cites = {a["cite"] for a in unit.amends}
    assert "42 U.S.C. 1396" not in cites  # bare cross-reference, not amended


def test_amends_binds_verb_to_hugging_citation_not_a_distant_one():
    # Regression (S. 3346): an incidental cite (5 U.S.C. 553, APA rulemaking)
    # separated from the verb by prose must NOT bind to a distant "is amended",
    # and the real target (21 U.S.C. 823, which hugs the verb) must not be
    # swallowed inside an over-wide match. The old loose window returned
    # ["5 U.S.C. 553"] and dropped 823 entirely.
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Controlled substance rulemaking",
        segments=[
            Segment(
                "operative",
                "The Attorney General shall, in accordance with the rulemaking "
                "procedures under 5 U.S.C. 553, ensure that Section 303 of the "
                "Controlled Substances Act (21 U.S.C. 823) is amended by adding "
                "at the end the following new subsection.",
            )
        ],
    )
    assert unit.amends == [{"kind": "usc", "cite": "21 U.S.C. 823"}]


def test_amends_ignores_citations_in_quoted_insertions():
    # A cite inside quoted (inserted) language is not an amendment target; §6
    # requires excluding quoted segments structurally. Scanning display_text
    # (all contexts) would have wrongly reported the inserted title-26 cite.
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Insertion",
        segments=[
            Segment(
                "operative",
                "Section 5601 of title 14, United States Code, is amended by "
                "inserting at the end the following:",
            ),
            Segment("quoted", "Section 9999 of title 26, United States Code, shall govern."),
        ],
    )
    assert unit.amends == [{"kind": "usc", "cite": "14 U.S.C. 5601"}]
    assert "26 U.S.C. 9999" not in {a["cite"] for a in unit.amends}


def test_amends_extracts_public_law_targets_with_verb_hug_and_prefers_pl_over_stat():
    # V15-approved: P.L. targets, gated on the same amendatory-verb hug as the USC
    # shorthand. A same-instance Stat cite is absorbed (one target), a cross-
    # reference with no verb hug is excluded, and results carry the kind object.
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="PL amendments",
        segments=[
            Segment(
                "operative",
                "Section 5 of Public Law 119-38 (139 Stat. 656) is amended by striking subsection (b). "
                "Section 3 of Public Law 118-31 is repealed. "
                "Nothing in Public Law 117-263 shall be construed to limit this authority.",
            )
        ],
    )
    pairs = {(a["kind"], a["cite"]) for a in unit.amends}
    assert ("public_law", "P.L. 119-38") in pairs
    assert ("public_law", "P.L. 118-31") in pairs
    assert ("public_law", "P.L. 117-263") not in pairs  # cross-ref, no amendatory verb hug
    # The Statutes-at-Large cite in the same instance is not double-emitted.
    assert not any(a["cite"].endswith("Stat. 656") for a in unit.amends)


def test_amends_excludes_intervening_amender_in_citation_chain():
    # Repro S:1106: the verb hugs the LAST cite in an "as added by / as most
    # recently amended by" chain -- an intervening amender, not the target. It must
    # not be reported (precision-first), or the current-year NDAA looks like the
    # most-amended act in the corpus (a drafting-style artifact, the V15 failure).
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Chain",
        segments=[
            Segment(
                "operative",
                "Section 2405(a) of the Act (Public Law 109-234; 120 Stat. 490), as added "
                "by section 2 of Public Law 110-417, as most recently amended by section "
                "145(a) of the National Defense Authorization Act for Fiscal Year 2025 "
                "(Public Law 118-159; 138 Stat. 2000), is amended by striking the second sentence.",
            )
        ],
    )
    cites = {a["cite"] for a in unit.amends}
    assert "P.L. 118-159" not in cites   # "most recently amended by" intervener
    assert "P.L. 110-417" not in cites   # "as added by" intervener
    # A direct amendment in the same style is still captured (no provenance clause).
    direct = Unit("S:2", [], None, [Segment("operative",
        "Section 5 of Public Law 119-38 is amended by striking subsection (b).")])
    assert {a["cite"] for a in direct.amends} == {"P.L. 119-38"}


def test_amends_public_law_handles_unicode_hyphens_and_absorbs_stat():
    # Repro S:549E: a "Public Law 118‑159" written with U+2011 was missed, then the
    # Stat fallback mislabeled the page (138 Stat. 1894) as a public_law target.
    # Every unicode hyphen now resolves to the P.L., which absorbs the Stat.
    for dash in ("-", "‐", "‑", "–", "—"):
        unit = Unit("S:1", [], None, [Segment("operative",
            f"Section 2 of Public Law 118{dash}159 (138 Stat. 1894) is amended by striking.")])
        assert unit.amends == [{"kind": "public_law", "cite": "P.L. 118-159"}], repr(dash)


def test_amends_mixed_usc_and_public_law_sorted_by_kind_then_cite():
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Mixed",
        segments=[
            Segment(
                "operative",
                "Section 5601 of title 14, United States Code, is amended. "
                "Section 2 of Public Law 119-38 is amended by striking the second sentence.",
            )
        ],
    )
    # Sorted by (kind, cite): public_law precedes usc.
    assert unit.amends == [
        {"kind": "public_law", "cite": "P.L. 119-38"},
        {"kind": "usc", "cite": "14 U.S.C. 5601"},
    ]


def test_a5_longhand_cross_references_without_verb_hug_are_not_amends():
    # A5 (V13): longhand is NOT self-gating. Definitional / "subject to" /
    # "notwithstanding" cross-references with no amendatory verb hugging the cite
    # must not populate amends, and a non-amendatory unit reports amends == []
    # (the amends != [] ⟹ is_amendatory invariant).
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Definitions",
        segments=[
            Segment(
                "operative",
                "In this section, the term congressional defense committees has the "
                "meaning given that term in section 101(a)(16) of title 10, United "
                "States Code. Subject to section 3501 of title 10, United States Code, "
                "the Secretary shall act notwithstanding section 403 of title 37, "
                "United States Code.",
            )
        ],
    )
    assert not unit.is_amendatory
    assert unit.amends == []


def test_a5_longhand_with_verb_hug_still_resolves():
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Real amendment",
        segments=[Segment("operative", "Section 2391(b)(1) of title 10, United States Code, is amended—")],
    )
    assert unit.is_amendatory
    assert unit.amends == [{"kind": "usc", "cite": "10 U.S.C. 2391(b)(1)"}]


def test_a5_amends_nonempty_implies_is_amendatory_invariant():
    # The guard holds by construction even if a cite pattern would otherwise match:
    # a unit that is not amendatory returns [] regardless of cite text present.
    unit = Unit(
        section_id="S:1",
        ancestor_path=[],
        header="Cross-ref only",
        segments=[Segment("operative", "as provided in 7 U.S.C. 2012 and Public Law 119-38.")],
    )
    assert not unit.is_amendatory
    assert unit.amends == []


def test_a5_known_recall_cost_interposed_clause_drops_longhand_cite():
    # Documented A5 recall cost (V13): an interposed clause between the cite and the
    # verb -- "as amended by section Z," or a "(article N of the UCMJ)" parenthetical
    # -- defeats the strict adjacency hug, so the cite is not resolved into amends.
    # Measured on the NDAA: 12-14 confirmed losses (the distant-verb class was
    # enumerated exhaustively at 0 further; the no-verb class was sampled 30/388 at
    # 0, so the upper bound is ~50, not a flat rate), ~0 on hr1. A6 (recovery) is
    # DEFERRED, not rejected -- see the trap by _HUG in parser.py.
    #
    # The is_amendatory assertion below is LOAD-BEARING, not incidental: that
    # fallback is the entire reason this loss is acceptable (the unit is still
    # discoverable as amendatory; amends is a convenience, not completeness). Do not
    # remove it -- a future change to amendatory detection could quietly remove the
    # justification while amends == [] still passes.
    for op in (
        "Section 149 of title 10, United States Code, as amended by section 905 of this Act, is further amended—",
        "Section 806 of title 10, United States Code (article 6 of the Uniform Code of Military Justice) is amended—",
    ):
        unit = Unit("S:1", [], None, [Segment("operative", op)])
        assert unit.is_amendatory       # LOAD-BEARING: the justification for the loss
        assert unit.amends == []        # the interposed clause drops the cite


def test_a5_is_amendatory_verb_set_is_superset_of_the_gate():
    # is_amendatory must fire on every verb the gate accepts (are repealed, is
    # further/hereby amended), or the invariant would hold only by coincidence.
    for verb in ("is amended", "are amended", "is further amended", "is hereby amended",
                 "is repealed", "are repealed"):
        u = Unit("S:1", [], None, [Segment("operative", f"Section 2 of Public Law 119-38 {verb}.")])
        assert u.is_amendatory, verb
        assert u.amends == [{"kind": "public_law", "cite": "P.L. 119-38"}], verb


def test_v18_is_amendatory_is_verb_only_quote_alone_does_not_fire():
    # V18: the quote branch is dropped. A quoted segment with no amendatory verb -- an
    # appropriations account heading, a short title, a defined term -- is NOT amendatory.
    # (Sample n=35 was 35/35 non-amendatory; a structural marker isn't evidence of one.)
    unit = Unit("S:1", [], "Short title", [
        Segment("operative", "This Act may be cited as the"),
        Segment("quoted", "Consolidated Appropriations Act, 2021"),
    ])
    assert not unit.is_amendatory
    assert unit.amends == []


def test_v18_is_amendatory_catches_ungated_to_read_as_follows():
    # V18: the one ungated amendatory form the corpus enumeration surfaced (115hr1
    # S:13502) -- a genuine amendment with no gated verb. Added to AMENDATORY_RE (the
    # is_amendatory superset), never to the amends gate. Operative-only here to prove
    # the phrase drives it, not a lingering quote branch.
    unit = Unit("S:1", [], "Modify", [
        Segment("operative", "Paragraph (1) of section 743(d) is to read as follows:"),
    ])
    assert unit.is_amendatory


def test_render_segments_wraps_quoted_and_hugs_trailing_punctuation():
    from congress_api.features.bill_text.parser import render_segments

    rendered = render_segments(
        [
            Segment("operative", "is amended by striking"),
            Segment("quoted", "icebreaker"),
            Segment("operative", ". The vessel is redesignated."),
        ]
    )
    assert '"icebreaker"' in rendered           # quoted span is delimited
    assert '"icebreaker".' in rendered          # trailing terminator hugs the delimiter
    assert '"icebreaker" .' not in rendered      # no orphaned terminator


def test_source_quote_marks_stripped_so_no_doubled_delimiters():
    # V16 0.1% class: when the source DOES carry quotation marks in character data,
    # strip them at extraction so segments.text is clean and rendering does not
    # double them (spec §6 post-condition).
    xml = (
        "<bill><legis-body><section><enum>1</enum><header>H</header>"
        "<text>is amended by inserting <quote>“new text”</quote> at the end.</text>"
        "</section></legis-body></bill>"
    ).encode()
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    unit = next(u for u in parsed.units if u.section_id.endswith("S:1"))
    quoted = [s for s in unit.segments if s.context == "quoted"]
    assert quoted and quoted[0].text == "new text"  # curly source delimiters stripped
    from congress_api.features.bill_text.parser import render_segments

    rendered = render_segments(unit.segments)
    assert '"new text"' in rendered
    assert '""' not in rendered and '"“' not in rendered  # no doubled delimiters


def test_inline_elements_flow_into_one_operative_block():
    # Inline/typographic elements (italic vessel names, external-xrefs) must flow
    # into the surrounding text rather than split it into separate blocks. Before
    # the fix "Coast Guard cutter <italic>Mackinaw</italic> (WLBB-30)" parsed to
    # three "\n\n"-joined segments, so Mackinaw read as a heading and wrecked
    # downstream chunking.
    xml = (
        b"<bill><legis-body><section><enum>1</enum><header>Vessels</header>"
        b"<text>The Coast Guard cutter <italic>Mackinaw</italic> (WLBB-30) shall "
        b"be maintained under <external-xref>section 5601</external-xref> of the Act.</text>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    unit = next(u for u in parsed.units if u.section_id.endswith("S:1"))
    operative = [seg.text for seg in unit.segments if seg.context == "operative"]
    assert len(operative) == 1
    assert "Coast Guard cutter Mackinaw (WLBB-30)" in operative[0]
    assert "section 5601 of the Act" in operative[0]
    assert "\n\nMackinaw\n\n" not in unit.display_text


def test_node_kind_derives_from_leaf_id_prefix():
    # node_kind removes the need for a consumer to parse an id string to decide
    # whether a citation is safe (spec §5). structural = from the document;
    # synthetic = ours, stable but not a citation; chunk = enumerates nothing.
    assert node_kind_for("D:H/T:I/S:3501") == "structural"
    assert node_kind_for("D:H/T:I/S:3501/SS:(a)/PARA:(3)") == "structural"
    assert node_kind_for("D:H/T:I/S:3501/SS:(a)/CHUNK:3") == "chunk"
    assert node_kind_for("PRE:1") == "synthetic"
    assert node_kind_for("RC:2") == "synthetic"
    assert node_kind_for("U:1") == "synthetic"


def test_byte_fallback_preserves_quoted_context_in_chunks():
    # V14 second assertion: a byte cut of an amendatory section must not flatten
    # quoted (inserted) language into operative text. A chunk covering a quoted
    # span must still report a `quoted` segment, or match_contexts lies at chunk
    # level -- V4 failing on exactly the largest amendatory sections.
    unit = Unit(
        section_id="D:A/T:I/S:5",
        ancestor_path=[AncestorNode(type="D", enum="A", header="Div")],
        header="Amendment",
        segments=[
            Segment("operative", "is amended by inserting the following: " + "op " * 2000),
            Segment("quoted", "polar security cutter " * 2000),
            Segment("operative", "after the first place it appears " + "tail " * 2000),
        ],
    )
    chunks = byte_split_unit(unit)
    assert len(chunks) > 1
    assert all(c.byte_length <= MAX_UNIT_BYTES for c in chunks)
    assert all(c.section_id.startswith("D:A/T:I/S:5/CHUNK:") for c in chunks)
    # The quoted material survives as quoted segments; no chunk containing the
    # inserted phrase mislabels it operative-only.
    assert any(seg.context == "quoted" for c in chunks for seg in c.segments)
    for c in chunks:
        if "polar security cutter" in c.display_text:
            assert any(seg.context == "quoted" for seg in c.segments)


def _section_xml(enum, header, child_tag, child_enums, filler_bytes=5000):
    filler = ("word " * (filler_bytes // 5)).strip()
    children = b"".join(
        (
            f"<{child_tag}><enum>{ce}</enum><text>{filler}</text></{child_tag}>"
        ).encode()
        for ce in child_enums
    )
    return f"<section><enum>{enum}</enum><header>{header}</header>".encode() + children + b"</section>"


def test_subdivision_emits_spec_prefix_codes_not_element_names():
    # The subdivision chain uses the qualified codes SS/PARA/SUBP/CL, not the raw
    # element names (PARAGRAPH/SUBPARAGRAPH/CLAUSE) the old mapping produced.
    assert SUBDIV_CODE == {"subsection": "SS", "paragraph": "PARA", "subparagraph": "SUBP", "clause": "CL"}
    xml = (
        b"<bill><legis-body>"
        + _section_xml("1", "Subsections", "subsection", ["(a)", "(b)"])
        + _section_xml("2", "Paragraphs", "paragraph", ["(1)", "(2)"])
        + b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    assert "S:1/SS:(a)" in ids and "S:1/SS:(b)" in ids
    assert "S:2/PARA:(1)" in ids and "S:2/PARA:(2)" in ids


def test_no_addressable_unit_emitted_from_inside_quoted_block():
    # V14 regression fixture: a bill inserting a whole new <section> nests it in a
    # <quoted-block>. That inner section must NOT become a phantom addressable
    # unit; its text stays searchable only as a `quoted` segment of the enclosing
    # real section. Asserts both directions (spec §5, V14 first + second).
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>5</enum><header>Amendment</header>"
        b"<text>Section 2304 of title 10, United States Code, is amended to read as follows:</text>"
        b"<quoted-block>"
        b"<section><enum>2304</enum><header>Phantom</header>"
        b"<text>polar security cutter procurement authority</text></section>"
        b"</quoted-block>"
        # inline <quote> form too -- word/phrase-level strike-and-insert
        b"<text>and by striking <quote>icebreaker</quote> each place it appears.</text>"
        b"</section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    # (1) zero units emitted from inside the quoted subtree -- the inner enum 2304
    # never surfaces as an addressable id.
    assert all("2304" not in sid for sid in ids)
    section_units = [u for u in parsed.units if u.section_id.split("/")[-1].startswith("S:")]
    assert [u.section_id for u in section_units] == ["S:5"]
    # (2) the quoted text is fully retrievable as a `quoted` segment of S:5, and
    # both quoting forms are captured.
    s5 = next(u for u in parsed.units if u.section_id == "S:5")
    quoted = " ".join(seg.text for seg in s5.segments if seg.context == "quoted")
    assert "polar security cutter procurement authority" in quoted
    assert "icebreaker" in quoted
    index = BillTextIndex(parsed)
    hits = index.search([normalized_query("polar security cutter")], 10)
    assert hits and hits[0].unit.section_id == "S:5"
    assert hits[0].match_contexts == ["quoted"]


def test_strip_quote_delimiters_strips_only_a_matched_wrapping_pair():
    # F18 (spec §18 / §6 V16): the defensive strip exists ONLY for the 0.1%
    # class of source-embedded wrapping delimiters. Leading and trailing marks
    # must be stripped together as a matched pair or not at all -- an unpaired
    # mark is content, and deleting it makes segments.text (the one stored
    # source of truth) lossy.
    from congress_api.features.bill_text.parser import strip_quote_delimiters

    # The 0.1% class: a genuine wrapping pair is stripped, inner marks kept.
    assert strip_quote_delimiters("“The term ‘covered entity’ has meaning.”") == \
        "The term ‘covered entity’ has meaning."
    assert strip_quote_delimiters('"State means each State."') == "State means each State."
    # Unpaired trailing mark: a plural possessive is content and must survive.
    assert strip_quote_delimiters("amounts available under the Secretaries'") == \
        "amounts available under the Secretaries'"
    # Unpaired leading mark survives too.
    assert strip_quote_delimiters('"State means each of the several States') == \
        '"State means each of the several States'
    # Mismatched styles are not a pair; both marks are content.
    assert strip_quote_delimiters("“mixed wrapping'") == "“mixed wrapping'"
    # A lone mark is content, not a pair.
    assert strip_quote_delimiters('"') == '"'


def test_quoted_block_content_apostrophe_survives_into_segments():
    # F18 end-to-end: a quoted block whose text END is a possessive apostrophe
    # (no wrapping marks in source -- the 99.9% case) must reach segments.text
    # intact, or the FTS-indexed source of truth is silently lossy.
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>7</enum><header>Amendment</header>"
        b"<text>Section 4 is amended to read as follows:</text>"
        b"<quoted-block>"
        b"<section><enum>4</enum><header>Duties</header>"
        b"<text>The funds shall remain available at the Secretaries&#8217;</text></section>"
        b"</quoted-block>"
        b"</section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    s7 = next(u for u in parsed.units if u.section_id == "S:7")
    quoted = " ".join(seg.text for seg in s7.segments if seg.context == "quoted")
    assert "Secretaries’" in quoted  # the apostrophe is content, not a delimiter


def test_subdivided_section_intro_preserves_quoted_context():
    # V14-class: when an over-size section is subdivided, its intro (the matter before
    # the first subdivision) is emitted by extract_intro_segments. A <quote> there --
    # e.g. `striking "X" in the matter preceding paragraph (1)` -- must keep `quoted`
    # context, not be flattened to operative, or inserted language on the largest
    # amendatory sections reads as enacted (the amendatory trap at the intro). The
    # previous hard-coded operative label was latent on the two acceptance fixtures
    # but LIVE in the wider corpus: a scan of 18 packages / 571 subdivided sections
    # surfaced two real cases the old code mislabeled -- 117hr2471enr S:804 (VAWA,
    # `Section 204 of Public Law 90-284 ... <quote>Indian Civil Rights Act of 1968`)
    # and 116hr133enr S:401. This asserts the property directly (quote nested in a
    # <text>, as in those documents, not a bare child).
    filler = ("word " * 1200).strip()  # ~6000B each -> whole section forces subdivision
    phrase = "polar security cutter distinctive intro phrase"
    xml = (
        b"<bill><legis-body><section><enum>5</enum><header>Amendatory</header>"
        b"<text>Section 9062 of title 10, United States Code, is amended by striking "
        b"<quote>" + phrase.encode() + b"</quote> in the matter preceding paragraph (1).</text>"
        b"<subsection><enum>(a)</enum><text>" + filler.encode() + b"</text></subsection>"
        b"<subsection><enum>(b)</enum><text>" + filler.encode() + b"</text></subsection>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    parent = next(u for u in parsed.units if u.section_id == "S:5")
    # the section did subdivide (so the intro path was exercised, not the whole-unit path)
    assert parent.child_ids == ["S:5/SS:(a)", "S:5/SS:(b)"]
    # the inserted phrase survives as a quoted segment of the intro, not operative
    assert any(seg.context == "quoted" and phrase in seg.text for seg in parent.segments)
    assert not any(seg.context == "operative" and phrase in seg.text for seg in parent.segments)
    # and it is retrievable end-to-end with the correct context
    index = BillTextIndex(parsed)
    hits = index.search([normalized_query(phrase)], 5)
    assert hits and hits[0].unit.section_id == "S:5"
    assert hits[0].match_contexts == ["quoted"]


def test_after_quoted_block_connective_renders_outside_the_quote():
    # Bill DTD puts the trailing connective ("; and", ".") in an <after-quoted-block>
    # child of every quoted-block. It must be operative and render OUTSIDE the quote,
    # not swallowed as '"(D) the Coast Guard. ; and"' (repro; spec §6).
    xml = (
        b"<bill><legis-body><section><enum>1</enum><header>H</header>"
        b"<text>is amended by adding at the end the following:</text>"
        b"<quoted-block><paragraph><enum>(D)</enum><text>the Coast Guard.</text></paragraph>"
        b"<after-quoted-block>; and</after-quoted-block></quoted-block>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    unit = next(u for u in parsed.units if u.section_id.endswith("S:1"))
    quoted = " ".join(s.text for s in unit.segments if s.context == "quoted")
    assert "the Coast Guard" in quoted
    assert "; and" not in quoted  # connective is not swallowed into the quoted text
    assert any(s.context == "operative" and "; and" in s.text for s in unit.segments)
    from congress_api.features.bill_text.parser import render_segments

    rendered = render_segments(unit.segments)
    assert '; and"' not in rendered        # connective is not inside the closing delimiter
    assert 'the Coast Guard."' in rendered  # the quote closes before the connective


def test_subtree_byte_length_reflects_descendant_chunks():
    # A subdivided section's own byte_length is only its intro; subtree_byte_length
    # exposes the real size so a consumer is not misled (decision 2; repro S 204,
    # 73 B own vs ~60,700 B subtree).
    xml = (
        b"<bill><legis-body>"
        + _section_xml("1", "Big", "subsection", ["(a)", "(b)"])
        + b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    parent = next(u for u in parsed.units if u.section_id == "S:1")
    assert parent.child_ids  # it was subdivided
    subtree = parsed.subtree_bytes
    # Parent's own bytes are far smaller than the whole subtree.
    assert subtree["S:1"] > parent.byte_length
    assert subtree["S:1"] == parent.byte_length + sum(subtree[cid] for cid in parent.child_ids)
    # A leaf's subtree equals its own byte_length.
    leaf = next(u for u in parsed.units if u.section_id == "S:1/SS:(a)")
    assert subtree[leaf.section_id] == leaf.byte_length


def test_entity_declaration_is_refused_before_parsing():
    # Billion-laughs guard (spec §11): any raw <!ENTITY is rejected before the
    # parser runs. Real GovInfo Bill DTD XML never carries internal entities.
    xml = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE bill [ <!ENTITY lol "lololololol"> ]>'
        b"<bill><legis-body><section><enum>1</enum><text>&lol;</text></section>"
        b"</legis-body></bill>"
    )
    with pytest.raises(BillTextError) as exc:
        parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    assert exc.value.code == "unsafe_document"


def test_search_aggregates_matching_segments_to_one_unit_hit():
    # Unit-level candidate aggregation (spec §7 / 5e): a term matching several
    # segments of one unit yields a single hit, with match_contexts unioned across
    # the matching segments rather than one row per segment.
    xml = (
        b"<bill><legis-body><section><enum>1</enum><header>Icebreakers</header>"
        b"<text>The icebreaker program is amended by striking <quote>icebreaker</quote> "
        b"and inserting the following.</text></section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    index = BillTextIndex(parsed)
    hits = index.search([normalized_query("icebreaker")], 10)
    assert len(hits) == 1
    assert {"operative", "quoted"} <= set(hits[0].match_contexts)


@pytest.mark.asyncio
async def test_tool_wrappers_build_responses_without_network(monkeypatch):
    # Exercises the tools.py envelope + response-model construction for all three
    # tools (the layer above the parser/index). Guards against duplicate-keyword
    # envelope regressions such as version_resolution_note being passed twice.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_fixture("bill_text_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr",
            version="enr",
            version_resolved_at="2026-08-03T00:00:00Z",
            version_resolution_note=None,
            last_modified="2025-12-19T03:11:48Z",
            xml_bytes=b"",
        ),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    toc = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=2)
    assert "error" not in toc and toc["toc"]
    # Fixture sections sit at depth 3, so a depth-2 TOC must disclose the hidden
    # level rather than assert completeness.
    assert toc["toc_truncated"] is True
    assert "depth=3" in toc["toc_note"]
    # ...but depth 2 was served in full, so this is "more exists below", not an
    # override. The distinction F11 adds (see the dedicated tests below).
    assert toc["depth_reduced"] is False
    assert toc["requested_depth"] == 2 and toc["depth"] == 2

    search = await tools_mod.search_bill_text(None, congress=119, bill_type="s", number=1071, queries=["icebreaker"], max_hits=999)
    assert "error" not in search and search["hits"]
    # The clamp advisory lands in request_note, NOT version_resolution_note. This
    # assertion previously read `in search["version_resolution_note"]`, which is the
    # contract F17 broke: it passed whether or not the version note survived beside it,
    # because this fixture resolves cleanly and has no version note to lose.
    assert "clamped to 50" in search["request_note"]
    assert search["version_resolution_note"] is None
    assert search["timing"]["search_ms"] is not None and search["timing"]["total_ms"] >= 0
    assert toc["timing"]["search_ms"] is None  # no search phase for toc

    section = await tools_mod.get_bill_section(None, congress=119, bill_type="s", number=1071, section_id=search["hits"][0]["section_id"])
    assert "error" not in section and section["text"]


@pytest.mark.asyncio
async def test_f5_toc_container_ids_resolve_through_get_bill_section(monkeypatch):
    # F5: `D:C/T:XXXI/ST:B` appeared VERBATIM in a get_bill_toc response and then
    # returned section_not_found -- and the remediation named get_bill_toc, the tool
    # that had just handed out the id. Every container id the TOC emits must resolve,
    # so TOC -> section -> child works end to end for a consumer navigating the way
    # the TOC invites.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_fixture("bill_text_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr",
            version="enr",
            version_resolved_at="2026-08-03T00:00:00Z",
            version_resolution_note=None,
            last_modified=None,
            xml_bytes=b"",
        ),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    toc = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=5)
    ids = []
    stack = list(toc["toc"])
    while stack:
        node = stack.pop()
        ids.append(node["section_id"])
        stack.extend(node["children"])
    assert ids, "fixture produced no TOC nodes"

    containers = [sid for sid in ids if not any(u.section_id == sid for u in parsed.units)]
    assert containers, "fixture has no container nodes -- this test would prove nothing"

    for sid in ids:
        section = await tools_mod.get_bill_section(
            None, congress=119, bill_type="s", number=1071, section_id=sid
        )
        assert "error" not in section, f"TOC handed out {sid!r} and get_bill_section rejected it: {section}"
        assert section["section_id"] == sid

    # A container serves the §5 subdivided-parent shape: heading text plus child
    # descriptors, and each descriptor is itself fetchable (the next navigation hop).
    container = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071, section_id=containers[0]
    )
    assert container["children"]
    assert container["subtree_byte_length"] > 0
    for child in container["children"]:
        hop = await tools_mod.get_bill_section(
            None, congress=119, bill_type="s", number=1071, section_id=child["section_id"]
        )
        assert "error" not in hop


@pytest.mark.asyncio
async def test_f5_oversized_container_returns_descriptors_not_the_first_child(monkeypatch):
    # §5: never silently return only the first chunk. A container too large for
    # max_bytes returns its heading plus descriptors with truncated=true.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    # max_bytes clamps at a 1,000 floor, so the container's subtree has to clear that
    # for truncation to be reachable at all.
    body = ("word " * 400).strip().encode()   # ~2KB per section
    xml = (
        b"<bill><legis-body><division><enum>C</enum><header>Big division</header>"
        b"<title><enum>XXXI</enum><header>A title</header>"
        b"<section><enum>3101</enum><header>One</header><text>" + body + b"</text></section>"
        b"<section><enum>3102</enum><header>Two</header><text>" + body + b"</text></section>"
        b"</title></division></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    loaded = LoadedBillText(
        resolved=ResolvedBillText("BILLS-119s1071enr", "enr", "2026-08-03T00:00:00Z", None, None, b""),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    small = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071, section_id="D:C/T:XXXI", max_bytes=1_000
    )
    assert "error" not in small
    assert small["truncated"] is True
    assert [child["section_id"] for child in small["children"]] == ["D:C/T:XXXI/S:3101", "D:C/T:XXXI/S:3102"]
    # Heading only -- NOT the first child's text silently standing in for the whole.
    assert body.decode() not in small["text"]
    assert small["subtree_byte_length"] > len(small["text"].encode("utf-8"))

    # The same container comfortably within max_bytes assembles the whole subtree,
    # matching §5's "parent fits max_bytes -> return whole section" row.
    whole = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071, section_id="D:C/T:XXXI", max_bytes=100_000
    )
    assert whole["truncated"] is False
    assert whole["text"].count("word") > 700     # both sections present


@pytest.mark.asyncio
async def test_f5_byte_split_section_resolves_and_reassembles_from_its_chunks(monkeypatch):
    # A section too large to subdivide structurally is REPLACED by its CHUNK units,
    # so the section id itself is not a unit -- yet it is a real, citable section and
    # the TOC lists it (5 such on s1071, all rejected before this fix). It must
    # resolve and reassemble at read time; the chunks stay fetchable but non-citable.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    # No structural children to subdivide on -> byte fallback.
    body = ("word " * 4000).strip().encode()   # ~20KB, one <text>, no subsections
    xml = (
        b"<bill><legis-body><division><enum>D</enum><header>Div D</header>"
        b"<title><enum>XLVII</enum><header>Title XLVII</header>"
        b"<section><enum>4701</enum><header>Big section</header><text>" + body + b"</text></section>"
        b"</title></division></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    assert "D:D/T:XLVII/S:4701" not in ids            # replaced by its chunks
    assert any(sid.startswith("D:D/T:XLVII/S:4701/CHUNK:") for sid in ids)

    loaded = LoadedBillText(
        resolved=ResolvedBillText("BILLS-119s1071enr", "enr", "2026-08-03T00:00:00Z", None, None, b""),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    section = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071, section_id="D:D/T:XLVII/S:4701", max_bytes=100_000
    )
    assert "error" not in section
    assert section["node_kind"] == "structural"       # a real section, citable
    assert section["header"] == "Big section"
    assert section["text"].count("word") > 3900       # reassembled from every chunk
    assert all(child["node_kind"] == "chunk" for child in section["children"])


def test_f5_toc_ids_come_from_the_unit_id_not_ancestor_path_plus_leaf():
    # Found live while verifying F5 on s1071: 28 TOC nodes carried ids like
    # `D:D/T:XLVII/CHUNK:2` for units whose real id is `D:D/T:XLVII/S:4701/CHUNK:2`.
    # byte_split_unit carries the PARENT's ancestor_path onto a chunk while appending
    # /CHUNK:{n} to the parent's id, so the section component is in neither -- and
    # rebuilding the id as ancestor_path+leaf dropped it. The fabricated ids referred
    # to nothing: rejected by get_bill_section, and absent from subtree_bytes so they
    # reported size 0 as well.
    chunk = Unit(
        section_id="D:D/T:XLVII/S:4701/CHUNK:2",
        ancestor_path=[
            AncestorNode(type="D", enum="D", header="Division D"),
            AncestorNode(type="T", enum="XLVII", header="Title XLVII"),
        ],
        header="Section header",
        segments=[Segment("operative", "body text")],
    )
    nodes = _toc_nodes([chunk], 5, {})[0]
    ids = []
    stack = list(nodes)
    while stack:
        node = stack.pop()
        ids.append(node.section_id)
        stack.extend(node.children)
    assert "D:D/T:XLVII/S:4701/CHUNK:2" in ids
    assert "D:D/T:XLVII/S:4701" in ids
    assert "D:D/T:XLVII/CHUNK:2" not in ids   # the fabricated id
    # Every id the TOC emits must be a prefix of a real unit id, or a real unit id.
    real = {chunk.section_id}
    assert all(any(r == sid or r.startswith(f"{sid}/") for r in real) for sid in ids)


def test_f5_ambiguous_bare_enum_is_not_swallowed_by_container_resolution():
    # The container fallback must fire only on section_not_found. An ambiguous bare
    # enum is a real answer under §5 ("never guess") and must survive.
    filler = b"<text>body</text>"
    xml = (
        b"<bill><legis-body>"
        b"<division><enum>A</enum><section><enum>101</enum>" + filler + b"</section></division>"
        b"<division><enum>B</enum><section><enum>101</enum>" + filler + b"</section></division>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    result = _resolve_unit(parsed.units, "101")
    assert isinstance(result, dict) and result["error"]["code"] == "ambiguous_section_id"


@pytest.mark.asyncio
async def test_get_bill_section_concatenates_subdivided_section_when_it_fits(monkeypatch):
    # Spec §5/§9: "parent fits max_bytes -> return whole section" is served by
    # concatenating children at read time (the parent unit stores only its intro).
    # A tiny max_bytes instead returns the header+intro plus child descriptors.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    xml = b"<bill><legis-body>" + _section_xml("1", "Big", "subsection", ["(a)", "(b)"]) + b"</legis-body></bill>"
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    loaded = LoadedBillText(
        resolved=ResolvedBillText("BILLS-119s1071enr", "enr", "2026-08-04T00:00:00Z", None, None, b""),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    parent = next(u for u in parsed.units if u.section_id == "S:1")
    assert parent.child_ids and parent.byte_length < 200  # intro only

    # Whole section fits the 25 KB default -> assembled at read time, not truncated.
    whole = await tools_mod.get_bill_section(None, congress=119, bill_type="s", number=1071, section_id="S:1")
    assert whole["truncated"] is False
    # byte_length is the unit's own clean size (intro), not the payload (spec §9);
    # the real content shows up in subtree_byte_length and in text.
    assert whole["byte_length"] == parent.byte_length
    assert whole["subtree_byte_length"] == parsed.subtree_bytes["S:1"]
    assert whole["subtree_byte_length"] >= whole["byte_length"]  # invariant restored
    assert len(whole["text"]) >= 8000  # both subsections concatenated into the payload

    # A tiny max_bytes forces the header+intro + child-descriptor path.
    partial = await tools_mod.get_bill_section(None, congress=119, bill_type="s", number=1071, section_id="S:1", max_bytes=1000)
    assert partial["truncated"] is True
    assert [c["section_id"] for c in partial["children"]] == ["S:1/SS:(a)", "S:1/SS:(b)"]
    assert partial["byte_length"] <= 1000


@pytest.mark.asyncio
async def test_tool_wrapper_catches_and_logs_unexpected_errors(monkeypatch, caplog):
    import logging

    import congress_api.features.bill_text.tools as tools_mod

    async def boom(ctx, congress, bill_type, number, version):
        raise RuntimeError("simulated downstream failure")

    monkeypatch.setattr(tools_mod, "load_bill_text", boom)
    with caplog.at_level(logging.ERROR):
        result = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071)
    assert result["error"]["code"] == "internal_error"
    assert "RuntimeError" in result["error"]["message"]
    # Full traceback is logged (to stderr -> the MCP server log), not swallowed.
    assert any(rec.exc_info for rec in caplog.records)


@pytest.mark.asyncio
async def test_resolve_versions_falls_back_only_when_congress_unavailable(monkeypatch):
    import congress_api.features.bill_text.client as client_mod
    from congress_api.features.bill_text.client import BillTextError, _resolve_versions

    called = {"search": 0}

    async def fake_search(congress, bill_type, number):
        called["search"] += 1
        return [TextVersion(code="enr", date="2025-07-09", type_label="enr")]

    monkeypatch.setattr(client_mod, "govinfo_search_versions", fake_search)

    # congress.gov unreachable -> fall back to GovInfo search
    async def unavailable(ctx, c, t, n):
        raise BillTextError("congress_unavailable", "down")

    monkeypatch.setattr(client_mod, "congress_text_versions", unavailable)
    versions = await _resolve_versions(None, 119, "hr", 1)
    assert [v.code for v in versions] == ["enr"] and called["search"] == 1

    # a 404 is definitive: no fallback, error propagates
    async def not_found(ctx, c, t, n):
        raise BillTextError("bill_not_found", "nope")

    monkeypatch.setattr(client_mod, "congress_text_versions", not_found)
    with pytest.raises(BillTextError) as exc:
        await _resolve_versions(None, 119, "hr", 999999)
    assert exc.value.code == "bill_not_found" and called["search"] == 1  # unchanged


@pytest.mark.asyncio
async def test_redirect_exhaustion_is_an_explicit_error_not_a_success(monkeypatch):
    # F22 (spec §18): a redirect chain that never terminates must surface as an
    # explicit error. Before the fix, _follow_with_key exhausted max_redirects and
    # returned the last 3xx -- already aclose()d -- which callers read as a <400
    # success and then crashed on the closed body.
    import httpx

    import congress_api.features.bill_text.client as client_mod
    from congress_api.features.bill_text.client import (
        BillTextError,
        _follow_with_key,
        fetch_govinfo_package,
    )

    def endless_redirect(request):
        return httpx.Response(302, headers={"location": str(request.url)})

    real_async_client = httpx.AsyncClient

    def redirecting_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(endless_redirect)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", redirecting_client)

    # Caller level: the explicit error, never a "success" wearing a 3xx.
    with pytest.raises(BillTextError) as exc:
        await fetch_govinfo_package("BILLS-119hr1234ih")
    assert exc.value.code == "govinfo_unavailable"
    assert "redirect" in exc.value.message.lower()

    # A bounded chain still resolves: two hops then a document.
    hops = {"n": 0}

    def two_hops_then_ok(request):
        if hops["n"] < 2:
            hops["n"] += 1
            return httpx.Response(302, headers={"location": str(request.url)})
        return httpx.Response(200, json={"ok": True})

    async with real_async_client(transport=httpx.MockTransport(two_hops_then_ok)) as bounded:
        response = await _follow_with_key(bounded, "GET", "https://api.govinfo.gov/x", "key")
    assert response.status_code == 200 and hops["n"] == 2


@pytest.mark.asyncio
async def test_malformed_congress_body_routes_to_govinfo_fallback(monkeypatch):
    # F21 (spec §18): congress.gov answering HTTP 200 with an HTML body must not
    # escape as a JSONDecodeError that jumps over the GovInfo fallback and
    # surfaces as internal_error. Root cause #15: congress_text_versions bypassed
    # make_api_request and so missed its JSON-decode guard.
    import httpx

    import congress_api.core.client_handler as handler_mod
    import congress_api.features.bill_text.client as client_mod
    from congress_api.features.bill_text.client import (
        BillTextError,
        _resolve_versions,
        congress_text_versions,
    )

    class FakeHttpClient:
        def __init__(self, response):
            self._response = response

        async def get(self, endpoint, params=None):
            return self._response

    class FakeAppContext:
        def __init__(self, response):
            self.client = FakeHttpClient(response)
            self.api_key = "test-key"
            self.request_count = 0
            self.cache = None

    def serve(response):
        app_ctx = FakeAppContext(response)
        monkeypatch.setattr(handler_mod, "get_app_context", lambda: app_ctx)
        # Pre-fix path read the app context through client.py's own import; patch
        # both so the test exercises whichever wiring is live.
        monkeypatch.setattr(client_mod, "get_app_context", lambda: app_ctx, raising=False)

    request = httpx.Request("GET", "https://api.congress.gov/v3/bill/119/hr/1234/text")
    serve(httpx.Response(200, text="<html>Service temporarily unavailable</html>", request=request))

    # The decode failure surfaces as the recoverable taxonomy code, not a raw
    # JSONDecodeError and not bill_not_found...
    with pytest.raises(BillTextError) as exc:
        await congress_text_versions(None, 119, "hr", 1234)
    assert exc.value.code == "congress_unavailable"

    # ...so _resolve_versions reaches the GovInfo fallback and recovers.
    async def fake_search(congress, bill_type, number):
        return [TextVersion(code="ih", date="2025-01-03", type_label="ih")]

    monkeypatch.setattr(client_mod, "govinfo_search_versions", fake_search)
    versions = await _resolve_versions(None, 119, "hr", 1234)
    assert [v.code for v in versions] == ["ih"]

    # A 404 stays definitive: bill_not_found, fallback never consulted (spec §3).
    serve(httpx.Response(404, text="", request=request))
    consulted = {"n": 0}

    async def counting_search(congress, bill_type, number):
        consulted["n"] += 1
        return []

    monkeypatch.setattr(client_mod, "govinfo_search_versions", counting_search)
    with pytest.raises(BillTextError) as exc:
        await _resolve_versions(None, 119, "hr", 999999)
    assert exc.value.code == "bill_not_found" and consulted["n"] == 0


@pytest.mark.asyncio
async def test_govinfo_fallback_accepts_digit_suffixed_version_codes(monkeypatch):
    # F20 (spec §18): the fallback's packageId regex must accept the same code
    # alphabet as the primary path, or digit-suffixed reissues (pcs2, rh2, eas2)
    # are silently dropped -- a superseded print wins, or a real bill resolves
    # to bill_not_found.
    import congress_api.features.bill_text.client as client_mod
    from congress_api.features.bill_text.client import govinfo_search_versions

    import httpx

    payload = {
        "results": [
            {"packageId": "BILLS-119hr1234pcs2", "dateIssued": "2025-06-02"},
            {"packageId": "BILLS-119hr1234pcs", "dateIssued": "2025-05-01"},
            {"packageId": "BILLS-119hr1234ih", "dateIssued": "2025-01-03"},
            # A different, longer-numbered bill: its remainder after the
            # bill-1234 prefix is "5eh", which must not parse as a version code.
            {"packageId": "BILLS-119hr12345eh", "dateIssued": "2025-04-01"},
        ]
    }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            return httpx.Response(200, json=payload, request=httpx.Request("POST", url))

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", FakeAsyncClient)

    versions = await govinfo_search_versions(119, "hr", 1234)
    by_code = {v.code: v for v in versions}
    assert set(by_code) == {"pcs2", "pcs", "ih"}  # pcs2 kept, bill 12345 excluded
    assert by_code["pcs2"].date == "2025-06-02"

    # A bill whose ONLY package is digit-suffixed must resolve, not 404.
    payload = {"results": [{"packageId": "BILLS-119hr1234pcs2", "dateIssued": "2025-06-02"}]}
    versions = await govinfo_search_versions(119, "hr", 1234)
    assert [v.code for v in versions] == ["pcs2"]


def test_primary_and_fallback_use_identical_version_code_alphabet():
    # F20 acceptance: the two enumeration paths recognize the same code shapes.
    from congress_api.features.bill_text.client import _version_code_from_item

    item = {"formats": [{"url": "https://www.govinfo.gov/content/pkg/BILLS-119hr1234pcs2/xml/BILLS-119hr1234pcs2.xml"}]}
    assert _version_code_from_item(119, "hr", 1234, item) == "pcs2"


def test_version_code_read_from_formats_url_not_the_dict_repr():
    # F25 (spec §18 / §3 read-by-structure): the version code is a structural
    # property of formats[].url, never a substring of str(item). A code-shaped
    # string in ANY other field must not win over (or substitute for) the URL.
    from congress_api.features.bill_text.client import _version_code_from_item

    # A non-URL field mentions a different package id; the URL carries the truth.
    item = {
        "note": "supersedes BILLS-119hr1234ih",
        "formats": [
            {"type": "PDF", "url": "https://www.govinfo.gov/content/pkg/BILLS-119hr1234rh/pdf/BILLS-119hr1234rh.pdf"},
            {"type": "Formatted XML", "url": "https://www.govinfo.gov/content/pkg/BILLS-119hr1234rh/xml/BILLS-119hr1234rh.xml"},
        ],
    }
    assert _version_code_from_item(119, "hr", 1234, item) == "rh"

    # No formats at all: no code, regardless of what other fields mention.
    assert _version_code_from_item(
        119, "hr", 1234, {"type": "See BILLS-119hr1234eh elsewhere"}
    ) is None

    # Malformed shapes degrade to None, not a repr scan.
    assert _version_code_from_item(119, "hr", 1234, {"formats": "BILLS-119hr1234eh"}) is None
    assert _version_code_from_item(119, "hr", 1234, {"formats": [{"url": 42}, "junk"]}) is None


@pytest.mark.asyncio
async def test_resolve_notes_partial_unknown_code_to_the_caller(monkeypatch):
    # §3 ruling: an unrecognized code sorts last, so if it marks a newer stage a
    # genuinely older version wins -- a wrong answer inside a success envelope. The
    # all-unknown case already noted date-primary; the partial case was silent to the
    # caller (loud only in the operator log). The note now names the unknown code
    # whenever version=None and ANY code is unrecognized -- and stays silent otherwise.
    import congress_api.features.bill_text.client as client_mod

    async def fake_fetch(package_id):
        return ("2025-01-01T00:00:00Z", b"<bill><legis-body/></bill>")

    monkeypatch.setattr(client_mod, "fetch_govinfo_package", fake_fetch)

    async def with_unknown(ctx, c, t, n):
        return [
            TextVersion(code="enr", date="2025-01-01", type_label="Enrolled"),
            TextVersion(code="zq", date="2099-01-01", type_label="Future GPO code"),
        ]

    monkeypatch.setattr(client_mod, "congress_text_versions", with_unknown)
    resolved = await client_mod.resolve_and_fetch_bill_text(None, 119, "s", 1071, None)
    assert resolved.version == "enr"                              # known beats unknown
    assert resolved.version_resolution_note is not None
    assert "zq" in resolved.version_resolution_note              # names the unknown code
    assert "enr" in resolved.version_resolution_note            # relative to the chosen version

    # all codes known -> no note (no uncertainty to disclose)
    async def all_known(ctx, c, t, n):
        return [TextVersion(code="enr", date="2025-01-01", type_label="Enrolled"),
                TextVersion(code="is", date="2024-01-01", type_label="Introduced")]

    monkeypatch.setattr(client_mod, "congress_text_versions", all_known)
    r2 = await client_mod.resolve_and_fetch_bill_text(None, 119, "s", 1071, None)
    assert r2.version == "enr" and r2.version_resolution_note is None

    # caller named a version -> resolution made no choice -> the note would be noise
    monkeypatch.setattr(client_mod, "congress_text_versions", with_unknown)
    r3 = await client_mod.resolve_and_fetch_bill_text(None, 119, "s", 1071, "enr")
    assert r3.version == "enr" and r3.version_resolution_note is None


@pytest.mark.skipif(not os.getenv("CONGRESSMCP_LIVE_ACCEPTANCE"), reason="live GovInfo/Congress.gov acceptance is opt-in")
def test_live_acceptance_placeholder():
    pytest.skip("Run V1-V12 manually with CONGRESSMCP_LIVE_ACCEPTANCE and record findings in the README/PR.")


# --------------------------------------------------------------------------- #
# V5 -- synthetic-unit resolution and toc depth-degradation disclosure.
# --------------------------------------------------------------------------- #
def _deep_bill_xml(divs: int, titles: int, secs: int) -> bytes:
    # divs*titles*secs sections at depth 3; divs + divs*titles container nodes above.
    body = []
    for d in range(divs):
        titles_xml = []
        for t in range(titles):
            secs_xml = "".join(
                f"<section><enum>{s}</enum><header>Sec {d}.{t}.{s}</header><text>x</text></section>"
                for s in range(secs)
            )
            titles_xml.append(f"<title><enum>{t}</enum><header>Title {t}</header>{secs_xml}</title>")
        body.append(f"<division><enum>{d}</enum><header>Div {d}</header>{''.join(titles_xml)}</division>")
    return ("<bill><legis-body>" + "".join(body) + "</legis-body></bill>").encode()


def test_subdivide_disambiguates_colliding_subsection_enums():
    # V8: 116hr6395 s.1832 really ships two subsection "(e)"s (different content). Without
    # disambiguation they share an id; _resolve_unit and get_bill_section's child_by_id
    # dict-overwrite, so the first is unreachable and its text is dropped from the
    # assembled section. The subdivision path must #-suffix collisions like _node_for.
    filler = ("word " * 1000).strip().encode()  # ~5KB each -> section subdivides
    xml = (
        b"<bill><legis-body><section><enum>1832.</enum><header>Dup</header>"
        b"<subsection><enum>(e)</enum><header>first e</header><text>" + filler + b"</text></subsection>"
        b"<subsection><enum>(e)</enum><header>second e</header><text>" + filler + b"</text></subsection>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"
    # The source enum is "1832." and F2 strips the trailing heading terminator, so the
    # id is S:1832 -- the # suffix still disambiguates the two real "(e)" subsections.
    assert "S:1832/SS:(e)" in ids and "S:1832/SS:(e)#2" in ids
    first = _resolve_unit(parsed.units, "S:1832/SS:(e)")
    second = _resolve_unit(parsed.units, "S:1832/SS:(e)#2")
    assert not isinstance(first, dict) and not isinstance(second, dict)
    assert first.header == "first e" and second.header == "second e"   # both reachable, distinct
    parent = next(u for u in parsed.units if u.section_id == "S:1832")
    assert parent.child_ids.count("S:1832/SS:(e)") == 1                  # not duplicated
    assert "S:1832/SS:(e)#2" in parent.child_ids                         # both assembled


def test_f12_inline_quote_does_not_fracture_its_sentence():
    # F12, first direction. An inline <quote> must stay its own SEGMENT -- §6 needs one
    # context per segment and the amendatory property depends on it -- but it sits
    # mid-sentence, so joining it with the BLOCK separator split one sentence into
    # three blocks. The split is structurally required; the separator was not.
    xml = (
        b"<bill><legis-body><section><enum>804</enum><header>Tribal jurisdiction</header>"
        b"<text>Section 204 of Public Law 90-284 (25 U.S.C. 1304) (commonly known as the "
        b"<quote>Indian Civil Rights Act of 1968</quote>) is amended-</text>"
        b"</section></legis-body></bill>"
    )
    unit = parse_bill_xml(xml, "X", "enr", None).units[0]
    rendered = render_segments(unit.segments)
    assert '(commonly known as the "Indian Civil Rights Act of 1968") is amended' in rendered
    assert "the\n\n\"Indian" not in rendered      # the fracture this fixes
    # The segment structure is UNCHANGED -- three segments, contexts intact -- because
    # collapsing them would destroy what match_contexts reports.
    assert [s.context for s in unit.segments] == ["header", "operative", "quoted", "operative"]
    assert unit.segments[2].inline and unit.segments[3].inline


def test_f12_block_quoted_block_still_separates():
    # The inverse must not regress: a block-level <quoted-block> is a block, and only
    # an explicit display-inline="yes-display-inline" makes one inline. Measured:
    # <quote> carries display-inline on 0 of 38,277 occurrences, <quoted-block> is
    # block on 7,535 and explicitly inline on 208.
    block = (
        b"<bill><legis-body><section><enum>1</enum><header>H</header>"
        b"<text>is amended by adding at the end the following:</text>"
        b"<quoted-block display-inline=\"no-display-inline\"><text>New material.</text></quoted-block>"
        b"</section></legis-body></bill>"
    )
    unit = parse_bill_xml(block, "X", "enr", None).units[0]
    assert "\n\n\"New material.\"" in render_segments(unit.segments)
    assert not any(s.inline for s in unit.segments if s.context == "quoted")

    inline = block.replace(b'no-display-inline', b'yes-display-inline')
    unit2 = parse_bill_xml(inline, "X", "enr", None).units[0]
    assert any(s.inline for s in unit2.segments if s.context == "quoted")


def test_f12_quoted_material_keeps_its_block_structure():
    # F12, second direction. Flattening quoted material with a plain space join ran
    # sibling units together -- "(2) Annual basis.-(A) In general.-..." -- losing every
    # boundary in an inserted chapter, which is the material a reader most needs
    # structured. Whitespace only, so no token changes and search is unaffected.
    xml = (
        b"<bill><legis-body><section><enum>1</enum><header>H</header>"
        b"<text>is amended to read as follows:</text>"
        b"<quoted-block><section><enum>333.</enum><header>Training courses</header>"
        b"<paragraph><enum>(2)</enum><header>Annual basis</header><text>Once each year.</text></paragraph>"
        b"<paragraph><enum>(3)</enum><header>Covered recipients</header><text>Flag officers.</text></paragraph>"
        b"</section></quoted-block></section></legis-body></bill>"
    )
    unit = parse_bill_xml(xml, "X", "enr", None).units[0]
    quoted = next(s.text for s in unit.segments if s.context == "quoted")
    assert "Once each year.\n\n(3) Covered recipients" in quoted   # siblings separated
    assert "Once each year. (3)" not in quoted                     # the run-together
    # Enum and header still ride WITH their own text -- they are one block, not three.
    # The heading is marked off from its body rather than run into it (the separate
    # flatten_quoted header rule); what F12 asserts here is that this stays ONE block,
    # with no "\n\n" between the heading and the text it heads.
    assert "(2) Annual basis · Once each year." in quoted
    assert "Annual basis\n\nOnce each year" not in quoted


def _quoted_of(xml: bytes) -> str:
    unit = parse_bill_xml(xml, "X", "enr", None).units[0]
    return next(s.text for s in unit.segments if s.context == "quoted")


def test_header_separator_is_detected_structurally_not_by_text_pattern():
    # THE CONSTRAINT THAT DECIDES THE IMPLEMENTATION. A regex over flattened text
    # cannot tell a real enum+header from a parenthetical abbreviation: the designator
    # slot takes four digits, so "IHR (2005) Monitoring and Evaluation" and
    # "(UN) General Assembly Resolution" match the same shape as "(2) Annual basis".
    # Detection must key off the <header> ELEMENT. Both cases below are prose with NO
    # header markup, so a structural rule leaves them untouched and a text rule
    # corrupts them.
    for body in (
        b"<text>the IHR (2005) Monitoring and Evaluation Framework applies.</text>",
        b"<text>United Nations (UN) General Assembly Resolution 2758 is noted.</text>",
        b"<text>recommendations from the (IT) Platform Planning workstream.</text>",
    ):
        quoted = _quoted_of(
            b"<bill><legis-body><section><enum>1</enum><header>H</header>"
            b"<text>is amended to read as follows:</text><quoted-block><section>"
            b"<enum>9.</enum><header>T</header><paragraph><enum>(1)</enum>"
            + body
            + b"</paragraph></section></quoted-block></section></legis-body></bill>"
        )
        assert "·" not in quoted.split("\n\n")[-1], quoted


def test_header_separator_absorbs_punctuation_the_source_already_supplies():
    # GPO's ".---" is sometimes split across the markup, with the period sitting at the
    # head of the body text node (observed live as "Quorum.A majority..."). Inserting a
    # separator without absorbing it yields "Quorum - .A majority". Only one degenerate
    # instance sits inside quoted material corpus-wide, but the drafting shape is live
    # in operative context, so the guard is not speculative.
    quoted = _quoted_of(
        b"<bill><legis-body><section><enum>1</enum><header>H</header>"
        b"<text>is amended to read as follows:</text><quoted-block><section>"
        b"<enum>9.</enum><header>T</header>"
        b"<subparagraph><enum>(D)</enum><header>Quorum</header>"
        b"<text>.A majority of the members shall constitute a quorum.</text>"
        b"</subparagraph></section></quoted-block></section></legis-body></bill>"
    )
    assert "Quorum · A majority" in quoted, quoted
    assert "· ." not in quoted and "·  " not in quoted


def test_header_separator_is_not_added_where_a_block_break_already_separates():
    # A header followed by a block-level sibling already gets "\n\n", which separates
    # at least as clearly. Adding the mark there would double the signal and leave a
    # dangling dash at the end of a line.
    quoted = _quoted_of(
        b"<bill><legis-body><section><enum>1</enum><header>H</header>"
        b"<text>is amended to read as follows:</text><quoted-block><section>"
        b"<enum>9.</enum><header>Heading with no body</header>"
        b"<paragraph><enum>(1)</enum><text>Body of the paragraph.</text></paragraph>"
        b"</section></quoted-block></section></legis-body></bill>"
    )
    assert "Heading with no body\n\n(1) Body" in quoted, quoted
    assert "·" not in quoted


def test_amends_usc_section_suffix_accepts_any_unicode_dash():
    # The source writes "42 U.S.C. 1395w-4" and "16 U.S.C. 3839aa-2" with U+2013. The
    # ASCII-only suffix class made the verb hug fail ON THE DASH, so every en-dash
    # suffixed section was dropped from `amends` even when perfectly hugged -- the
    # same defect the P.L. form had already been corrected for (repro S:549E).
    # Surfaced by V19 Population B: units flagged short for a fixable regex gap rather
    # than for A5's accepted recall cost.
    for dash in ("-", "‐", "‑", "–", "—"):
        unit = Unit(
            section_id="S:1",
            ancestor_path=[],
            header=None,
            segments=[
                Segment(
                    "operative",
                    "Section 1848(t)(1) of the Social Security Act "
                    f"(42 U.S.C. 1395w{dash}4(t)(1)) is amended by striking the second sentence.",
                )
            ],
        )
        # Normalized to a single canonical cite: the same target written with different
        # dashes must not yield two entries, which is why the P.L. form normalizes too.
        assert unit.amends == [{"kind": "usc", "cite": "42 U.S.C. 1395w-4"}], dash

    # The A5 gate is untouched: without the verb hug it still resolves nothing.
    ungated = Unit(
        section_id="S:2",
        ancestor_path=[],
        header=None,
        segments=[Segment("operative", "Nothing in this section affects 42 U.S.C. 1395w–4.")],
    )
    assert ungated.amends == []


def test_f4_struck_sections_are_excluded_and_disclosed():
    # The dominant real shape (measured: 162 of 219 changed="deleted" occurrences sit
    # on <section>): a Senate committee substitute -- "strike all after the enacting
    # clause and insert the part printed in italic" -- carries the WHOLE original bill
    # struck alongside its replacement. Emitting both put two versions of the same bill
    # side by side, and because struck text comes first in document order, a bare
    # citation resolved uniquely -- with no ambiguity error -- to the struck version.
    xml = (
        b"<bill><legis-body>"
        b'<section changed="deleted" reported-display-style="strikethrough"><enum>1</enum>'
        b"<header>Short title</header><text>Original struck text about icebreakers.</text></section>"
        b'<section changed="added"><enum>1</enum><header>Short title</header>'
        b"<text>Substitute text about cutters.</text></section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s4726rs", "rs", None)
    ids = [u.section_id for u in parsed.units]
    assert ids == ["S:1"]                          # one section, not two
    assert not any("#" in i for i in ids)          # no V8 collision suffix masking the duplication
    assert parsed.sections_indexed == 1
    assert parsed.struck_sections_excluded == 1
    unit = _resolve_unit(parsed.units, "1")
    assert "Substitute text about cutters." in unit.display_text
    assert "icebreakers" not in unit.display_text   # struck text is gone, not merely flagged
    # Struck text must not be searchable either -- it is not in the bill as reported.
    assert BillTextIndex(parsed).search([normalized_query("icebreakers")], 5) == []


def test_f4_carve_out_binds_every_unit_emitting_path():
    # A rule scoped to the path it was found on has failed four times in this feature
    # (A4, A5, intro labelling, _subdivide), so each enumerated path is pinned
    # SEPARATELY rather than trusting one entry point to cover the rest.
    # Each subsection must exceed MAX_UNIT_BYTES on its own: once the struck one is
    # excluded its bytes are gone, so sizing the filler against the COMBINED total
    # would leave the section under the threshold and it would never subdivide -- the
    # test would then pass for the wrong reason.
    filler = ("word " * 2000).strip().encode()   # ~10KB each, > MAX_UNIT_BYTES alone
    assert len(filler) > MAX_UNIT_BYTES

    # Path 3: struck subsection inside a LIVE section must not become a child unit.
    xml = (
        b"<bill><legis-body><section><enum>5</enum><header>Live</header>"
        b'<subsection changed="deleted"><enum>(a)</enum><text>struck subsection ' + filler + b"</text></subsection>"
        b"<subsection><enum>(b)</enum><text>live subsection " + filler + b"</text></subsection>"
        b"</section></legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "X", "rs", None)
    ids = [u.section_id for u in parsed.units]
    # The live subsection is oversized, so it byte-splits -- which exercises paths 3
    # and 4 in one shot: the live branch reaches the byte fallback and the struck
    # branch produces nothing at all, not even a chunk.
    assert any(i.startswith("S:5/SS:(b)") for i in ids)
    assert not any(i.startswith("S:5/SS:(a)") for i in ids)
    assert not any("struck subsection" in u.display_text for u in parsed.units)

    # Path 4: byte fallback is bound TRANSITIVELY -- no struck unit reaches it, so no
    # CHUNK id may ever descend from struck material. Stated in the enumeration as an
    # inference, pinned here as a fact.
    xml_chunk = (
        b"<bill><legis-body>"
        b'<section changed="deleted"><enum>9</enum><header>Struck big</header><text>struck ' + filler + b"</text></section>"
        b"</legis-body></bill>"
    )
    parsed_chunk = parse_bill_xml(xml_chunk, "X", "rs", None)
    assert parsed_chunk.units == []
    assert parsed_chunk.struck_sections_excluded == 1

    # Path 5: struck material contributes no TEXT to a live unit either -- a struck
    # <quoted-block> inside a live section is dropped, not kept as a `quoted` segment.
    # This is what lets match_contexts stay three-valued.
    xml_quote = (
        b"<bill><legis-body><section><enum>7</enum><header>Live</header>"
        b'<text>is amended by inserting <quoted-block changed="deleted"><text>struck insertion</text></quoted-block>'
        b" and <quoted-block><text>live insertion</text></quoted-block>.</text>"
        b"</section></legis-body></bill>"
    )
    parsed_quote = parse_bill_xml(xml_quote, "X", "rs", None)
    unit = parsed_quote.units[0]
    assert "live insertion" in unit.display_text
    assert "struck insertion" not in unit.display_text
    assert set(s.context for s in unit.segments) <= {"operative", "quoted", "header"}


def test_f4_text_extraction_paths_are_pinned_independently():
    # The two text-extraction guards are mutually redundant on the shapes above -- each
    # covers the other, so removing either left the whole suite green. An enumeration
    # whose members are not INDIVIDUALLY pinned is the same "one entry point covers the
    # rest" assumption the enumeration exists to reject, so each gets the shape where
    # it alone is load-bearing.

    # extract_segments alone: a SMALL struck subsection in a section that never
    # subdivides, so _subdivide never runs and element_text is never asked for it.
    xml = (
        b"<bill><legis-body><section><enum>3</enum><header>Live</header>"
        b'<subsection changed="deleted"><enum>(a)</enum><text>struck small subsection</text></subsection>'
        b"<subsection><enum>(b)</enum><text>live small subsection</text></subsection>"
        b"</section></legis-body></bill>"
    )
    unit = parse_bill_xml(xml, "X", "rs", None).units[0]
    assert "live small subsection" in unit.display_text
    assert "struck small subsection" not in unit.display_text

    # element_text alone: a struck child inside a <header>, which direct_text extracts
    # without ever passing through extract_segments.
    xml2 = (
        b"<bill><legis-body><section><enum>4</enum>"
        b'<header>Live title <quote changed="deleted">struck words</quote> tail</header>'
        b"<text>body</text></section></legis-body></bill>"
    )
    unit2 = parse_bill_xml(xml2, "X", "rs", None).units[0]
    assert unit2.header == "Live title tail"
    assert "struck words" not in (unit2.header or "")
    assert "struck words" not in unit2.display_text


def test_f4_struck_marker_is_the_attribute_not_the_display_style():
    # reported-display-style="strikethrough" is a RENDERING hint that accompanies the
    # change marker, not independent evidence of it. Gating on the display style would
    # be the structural-marker mistake this feature has made repeatedly -- so an
    # element styled strikethrough WITHOUT changed="deleted" is kept.
    xml = (
        b"<bill><legis-body>"
        b'<section reported-display-style="strikethrough"><enum>1</enum><header>Styled only</header>'
        b"<text>kept because nothing marks it deleted</text></section>"
        b'<section changed="not-changed"><enum>2</enum><header>Explicitly unchanged</header>'
        b"<text>kept</text></section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "X", "rs", None)
    assert [u.section_id for u in parsed.units] == ["S:1", "S:2"]
    assert parsed.struck_sections_excluded == 0


def test_f4_no_note_when_the_document_carries_no_struck_text():
    # Measured 0 across every enrolled, engrossed, and introduced probe, so the note
    # must stay null there -- a disclosure that fires on documents with nothing to
    # disclose trains the reader to ignore it.
    parsed = parse_fixture("bill_text_trimmed.xml")
    assert parsed.struck_sections_excluded == 0


def test_f2_trailing_period_is_stripped_from_ids_and_accepted_on_input():
    # F2: the tool ASSERTED A FALSEHOOD -- get_bill_section("804") returned "No section
    # or chunk matched '804'" while three sections numbered 804 existed, because the
    # source enum "804." put the heading terminator in the id. Four sessions tripped on
    # it. An id component carries the enum's identity, not its typography.
    xml = (
        b"<bill><legis-body>"
        b"<section><enum>804.</enum><header>Alpha</header><text>alpha text</text></section>"
        b"<section><enum>1.2.</enum><header>Decimal</header><text>decimal text</text></section>"
        b"<section><enum>90</enum><header>Bare</header><text>bare text</text></section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    ids = [u.section_id for u in parsed.units]
    assert "S:804" in ids
    assert "S:1.2" in ids          # INTERNAL periods survive: decimal-style enums are real
    assert "S:90" in ids
    assert not any(sid.endswith(".") for sid in ids)
    # Both spellings resolve: the bare enum a citation uses, and the "SEC. 804."
    # typography a model copies out of the statutory text.
    for requested in ("804", "804.", "S:804", "S:804."):
        unit = _resolve_unit(parsed.units, requested)
        assert not isinstance(unit, dict), f"{requested!r} failed to resolve: {unit}"
        assert unit.header == "Alpha"


def test_f2_ambiguous_bare_enum_still_errors_rather_than_guessing():
    # The period fix must not turn a genuine collision into a silent pick: three
    # sections numbered 804 in different divisions is the real NDAA shape, and §5
    # requires listing every qualified match rather than guessing one.
    filler = b"<text>body</text>"
    xml = (
        b"<bill><legis-body>"
        b"<division><enum>A</enum><section><enum>804.</enum><header>One</header>" + filler + b"</section></division>"
        b"<division><enum>B</enum><section><enum>804.</enum><header>Two</header>" + filler + b"</section></division>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, "BILLS-119s1071enr", "enr", None)
    for requested in ("804", "804."):
        result = _resolve_unit(parsed.units, requested)
        assert isinstance(result, dict)
        assert result["error"]["code"] == "ambiguous_section_id"
        assert sorted(result["error"]["detail"]["matches"]) == ["D:A/S:804", "D:B/S:804"]


def test_synthetic_pre_rc_units_resolve_and_navigate():
    # V5 gap 1: preamble/resolving-clause units carry synthetic ids (PRE:/RC:). They must
    # be resolvable by get_bill_section's addresser and appear in the toc, or a whereas
    # clause a search surfaces cannot be retrieved.
    parsed = parse_fixture("hres_trimmed.xml")  # PRE:1, PRE:2, RC:1
    ids = [u.section_id for u in parsed.units]
    assert "PRE:1" in ids and "RC:1" in ids
    for sid in ("PRE:1", "RC:1"):
        unit = _resolve_unit(parsed.units, sid)
        assert not isinstance(unit, dict), f"{sid} failed to resolve: {unit}"
        assert unit.section_id == sid
        assert node_kind_for(sid) == "synthetic"
    root_ids = [n.section_id for n in _toc_nodes(parsed.units, 5, parsed.subtree_bytes)[0]]
    assert "PRE:1" in root_ids and "RC:1" in root_ids


def test_get_bill_section_retrieves_synthetic_unit_end_to_end():
    # V5 gap 1, through the tool: resolving RC:1 must return its text with node_kind synthetic.
    import asyncio
    from unittest.mock import patch

    import congress_api.features.bill_text.tools as tools
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.index import BillTextIndex
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_fixture("hres_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText("BILLS-119hres463ih", "ih", "t", None, None, b""),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, *a, **k):
        return loaded

    with patch.object(tools, "load_bill_text", new=fake_load):
        res = asyncio.run(tools.get_bill_section(
            object(), congress=119, bill_type="hres", number=463, section_id="RC:1"))
    assert res.get("section_id") == "RC:1"
    assert res.get("node_kind") == "synthetic"
    assert res.get("text", "").strip()


def test_undivided_body_unit_resolves_on_input_like_the_other_synthetic_shapes():
    # V5 completes the ENUMERATION, not one member of it. _SYNTHETIC_PREFIXES has three
    # shapes minted at three different call sites; PRE: and RC: are covered above and
    # observed live, but U: was only ever asserted as a STRING classification
    # (node_kind_for("U:1") == "synthetic") -- never resolved through the tool. No corpus
    # package produces a U: id (0 of 20), so nothing else can catch a resolver that
    # emits the id and then rejects it, which is exactly the F5/F14 shape V5 watches for.
    import asyncio
    from unittest.mock import patch

    import congress_api.features.bill_text.tools as tools
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.index import BillTextIndex
    from congress_api.features.bill_text.service import LoadedBillText

    # A body with no whereas, no resolving clause, and no structural children: the
    # only construction that reaches the U: branch.
    parsed = parse_bill_xml(
        b"<bill><legis-body><text>An undivided body with no sections at all.</text>"
        b"</legis-body></bill>",
        "BILLS-119hres463ih", "ih", None,
    )
    assert [u.section_id for u in parsed.units] == ["U:1"]
    loaded = LoadedBillText(
        resolved=ResolvedBillText("BILLS-119hres463ih", "ih", "t", None, None, b""),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, *a, **k):
        return loaded

    with patch.object(tools, "load_bill_text", new=fake_load):
        res = asyncio.run(tools.get_bill_section(
            object(), congress=119, bill_type="hres", number=463, section_id="U:1"))
    assert "error" not in res, res
    assert res.get("section_id") == "U:1"
    assert res.get("node_kind") == "synthetic"
    assert "undivided body" in res.get("text", "")


@pytest.mark.asyncio
async def test_clamp_note_does_not_clobber_the_version_resolution_note(monkeypatch):
    # F17. The sites wrote `note or loaded.resolved.version_resolution_note`, which is
    # not a merge: the first truthy note wins. The clamp note is always the trivial one
    # ("Value 999 was clamped to 50"); version_resolution_note is the substantive one --
    # it says the served text fell back to another version, or resolved to a
    # failed-passage code that is not authoritative bill text. So an out-of-range
    # argument silently destroyed a safety disclosure, and only for callers who passed
    # one, who are least likely to notice.
    #
    # The pre-existing wrapper test could not catch this: its fixture resolves with
    # version_resolution_note=None, so `or` and a real merge are indistinguishable
    # there. BOTH notes have to be present for the collision to exist at all.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    version_note = (
        "Resolved to 'fps', which records a negative or terminated action rather than "
        "authoritative bill text; no authoritative version was listed."
    )
    parsed = parse_fixture("bill_text_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr", version="fps",
            version_resolved_at="2026-08-10T00:00:00Z",
            version_resolution_note=version_note, last_modified=None, xml_bytes=b"",
        ),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    # search_bill_text: max_hits out of range. Both notices survive, in SEPARATE fields.
    search = await tools_mod.search_bill_text(
        None, congress=119, bill_type="s", number=1071,
        queries=["icebreaker"], max_hits=999)
    assert "error" not in search
    assert "negative or terminated" in search["version_resolution_note"]
    assert "clamped to 50" in search["request_note"]
    # ...and neither field carries the other's content.
    assert "clamped" not in search["version_resolution_note"]
    assert "negative or terminated" not in search["request_note"]

    # get_bill_section: max_bytes out of range, same collision.
    section = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071,
        section_id=search["hits"][0]["section_id"], max_bytes=10)
    assert "error" not in section
    assert "negative or terminated" in section["version_resolution_note"]
    assert "clamped to 1000" in section["request_note"]

    # With no clamp, the version note stands alone and request_note is null.
    clean = await tools_mod.search_bill_text(
        None, congress=119, bill_type="s", number=1071, queries=["icebreaker"])
    assert clean["version_resolution_note"] == version_note
    assert clean["request_note"] is None


@pytest.mark.asyncio
async def test_version_resolution_note_is_null_when_only_the_request_was_clamped(monkeypatch):
    # THE INVARIANT THE FIELD SPLIT EXISTS FOR: version_resolution_note != null <=> a
    # version issue. Merging the clamp advisory in fixed F17's data loss but broke the
    # invariant the other way -- every over-large max_hits produced a non-null
    # version_resolution_note, so a consumer keying on the field's PRESENCE (which is
    # the point of a note field: no string parsing) got a false version warning on a
    # perfectly ordinary request. That is the F17 collision inverted, and it is why the
    # dedicated field is worth a schema change rather than living with the merge.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_fixture("bill_text_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr", version="enr",
            version_resolved_at="2026-08-10T00:00:00Z",
            version_resolution_note=None,          # a clean resolution
            last_modified=None, xml_bytes=b"",
        ),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    search = await tools_mod.search_bill_text(
        None, congress=119, bill_type="s", number=1071,
        queries=["icebreaker"], max_hits=999)
    assert search["version_resolution_note"] is None, (
        "a clamped argument is not a version issue and must not raise the version flag"
    )
    assert "clamped to 50" in search["request_note"]

    section = await tools_mod.get_bill_section(
        None, congress=119, bill_type="s", number=1071,
        section_id=search["hits"][0]["section_id"], max_bytes=10)
    assert section["version_resolution_note"] is None
    assert "clamped to 1000" in section["request_note"]


def test_merge_notes_drops_empties_without_inventing_separators():
    from congress_api.features.bill_text.tools import _merge_notes

    assert _merge_notes(None, None) is None
    assert _merge_notes("", "   ") is None
    assert _merge_notes("only one", None) == "only one"
    assert _merge_notes(None, "only one") == "only one"
    assert _merge_notes("first.", "second.") == "first. second."


def test_zero_hit_diagnostic_separates_absent_from_merely_phrased_otherwise():
    # F10, the whole point. Both queries return zero hits and are indistinguishable in
    # the response without this. One is answerable by rephrasing; the other is not, and
    # a caller told only "hits: []" will report "the bill does not address it" for both.
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)

    # Every word IS in the bill -- just never adjacent in this order. This is F9's
    # canonical burned-queries example.
    phrasing = index.diagnose(normalized_query("icebreaker polar security"))
    assert index.search([normalized_query("icebreaker polar security")], 10) == []
    assert phrasing.absent == []
    assert phrasing.verdict == "phrasing"

    # A word that is simply not in this document. No rephrasing recovers it.
    absent = index.diagnose(normalized_query("cryptocurrency"))
    assert absent.verdict == "absent_term"
    assert absent.absent == absent.terms != []


def test_zero_hit_diagnostic_reports_the_tokenisation_the_index_actually_used():
    # The instrument must not be a second tokeniser. Porter stemming is what makes a
    # phrase stop meaning what the caller typed, so the reported terms have to be the
    # STEMS the search ran on -- if these came back as the raw words, the diagnostic
    # would explain a search that never happened.
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)
    diagnosis = index.diagnose(normalized_query("Amended by striking forces"))
    assert diagnosis.terms == ["amend", "by", "strike", "forc"], diagnosis.terms


def test_zero_hit_diagnostic_absence_test_runs_against_the_search_index():
    # The absence claim is the load-bearing one -- it tells a caller to stop trying.
    # A term present in the bill must never be reported absent, so plant both: a stem
    # that IS in the index and one that cannot be.
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)
    present = index.diagnose(normalized_query("icebreaker"))
    assert present.terms == ["icebreak"] and present.absent == []
    missing = index.diagnose(normalized_query("icebreaker zzqqxx"))
    assert missing.absent == ["zzqqxx"]      # only the planted word
    assert "icebreak" in missing.terms       # the real one still reported, not absent


@pytest.mark.asyncio
async def test_search_response_diagnoses_only_the_queries_that_died(monkeypatch):
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_fixture("bill_text_trimmed.xml")
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr", version="enr",
            version_resolved_at="2026-08-08T00:00:00Z", version_resolution_note=None,
            last_modified=None, xml_bytes=b"",
        ),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    # One live query, one dead. The dead one must be diagnosed even though the call
    # succeeded -- a hit elsewhere does not explain the query that found nothing.
    mixed = await tools_mod.search_bill_text(
        None, congress=119, bill_type="s", number=1071,
        queries=["icebreaker", "cryptocurrency mining"])
    assert mixed["hits"]
    diags = mixed["query_diagnostics"]
    assert [d["query"] for d in diags] == ["cryptocurrency mining"]
    assert diags[0]["verdict"] == "absent_term"

    # All queries productive -> the field stays null rather than reporting an empty
    # list, so its presence alone means "something found nothing".
    clean = await tools_mod.search_bill_text(
        None, congress=119, bill_type="s", number=1071, queries=["icebreaker"])
    assert clean["hits"] and clean["query_diagnostics"] is None


def test_query_matches_ignores_ranking_and_the_max_hits_cap():
    # A query whose only matches are outranked out of the top max_hits window still
    # "matched" -- query_matches must say so, independent of the ranked result list.
    secs = b"".join(
        b"<section><enum>%d</enum><header>Approps</header><text>appropriations fiscal year</text></section>" % i
        for i in range(1, 9)
    )
    secs += b"<section><enum>9</enum><header>Ships</header><text>the polar icebreaker program</text></section>"
    parsed = parse_bill_xml(b"<bill><legis-body>" + secs + b"</legis-body></bill>", "BILLS-119hr1ih", "ih", None)
    index = BillTextIndex(parsed)
    assert index.query_matches(normalized_query("icebreaker")) is True   # matched S:9
    assert index.query_matches(normalized_query("submarine")) is False   # truly absent
    assert index.query_matches("   ") is False                           # no token
    # It is truncated out of a max_hits=1 ranked window, proving the two disagree.
    ranked = index.search([normalized_query("appropriations"), normalized_query("icebreaker")], 1)
    assert "S:9" not in [h.unit.section_id for h in ranked]


@pytest.mark.asyncio
async def test_matched_query_outranked_by_max_hits_is_not_diagnosed(monkeypatch):
    # Regression: query_diagnostics was derived from the truncated result list, so a
    # query whose only hits fell outside the max_hits window was reported as zero-hit
    # and told (falsely) 'terms present but not phrased this way' -- a query that DID
    # match a section. Diagnose off query_matches, not off `ranked`.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    secs = b"".join(
        b"<section><enum>%d</enum><header>Approps</header><text>appropriations fiscal year</text></section>" % i
        for i in range(1, 9)
    )
    secs += b"<section><enum>9</enum><header>Ships</header><text>the polar icebreaker program</text></section>"
    parsed = parse_bill_xml(b"<bill><legis-body>" + secs + b"</legis-body></bill>", "BILLS-119hr1ih", "ih", None)
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119hr1ih", version="ih",
            version_resolved_at="2026-08-08T00:00:00Z", version_resolution_note=None,
            last_modified=None, xml_bytes=b"",
        ),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    # max_hits=1: icebreaker's only hit (S:9) is outranked out of the window, but it
    # matched -- so no diagnostic may be emitted for it.
    resp = await tools_mod.search_bill_text(
        None, congress=119, bill_type="hr", number=1,
        queries=["appropriations", "icebreaker"], max_hits=1)
    assert len(resp["hits"]) == 1
    assert resp["query_diagnostics"] is None

    # A genuinely absent query is still diagnosed in the same call.
    resp2 = await tools_mod.search_bill_text(
        None, congress=119, bill_type="hr", number=1,
        queries=["icebreaker", "submarine"], max_hits=1)
    assert [d["query"] for d in resp2["query_diagnostics"]] == ["submarine"]
    assert resp2["query_diagnostics"][0]["verdict"] == "absent_term"


def test_toc_depth_reduced_is_false_when_the_depth_was_honored():
    # F11, the case toc_truncated cannot express. The tree is complete to the depth
    # asked for; sections merely nest deeper. toc_truncated is TRUE here and always
    # has been -- so a caller reading it alone cannot distinguish this from a request
    # that was silently overridden. depth_reduced must separate them.
    parsed = parse_bill_xml(_deep_bill_xml(2, 2, 2), "BILLS-119s1071enr", "enr", None)
    toc, capped, actual, list_truncated = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert actual == 2 and not capped and not list_truncated
    assert _hidden_section_note(parsed.units, actual, 2, parsed.subtree_bytes) is not None


def test_toc_depth_reduced_fires_only_on_an_actual_reduction():
    # The planted positive: 2*10*30 = 600 sections exceed the cap at depth 3, so a
    # depth-5 request is served at depth 2. requested_depth must survive into the
    # response -- reporting only the served depth is what forced a consumer to diff
    # its own request to notice, and neither cell did.
    parsed = parse_bill_xml(_deep_bill_xml(2, 10, 30), "BILLS-119s1071enr", "enr", None)
    _, capped, actual, list_truncated = _toc_nodes(parsed.units, 5, parsed.subtree_bytes)
    assert capped is True and actual < 5 and not list_truncated


def test_toc_node_cap_at_depth_one_is_a_cut_list_not_a_depth_reduction():
    # THE GUARD AGAINST THE OBVIOUS IMPLEMENTATION. Reusing the old `node_capped` flag
    # as depth_reduced reports a reduction that did not happen: when even depth 1
    # exceeds the cap, the requested depth IS served and the node LIST is cut instead.
    # The two degradations are different losses and need different signals -- and the
    # cut list was previously disclosed by nothing at all.
    parsed = parse_bill_xml(_deep_bill_xml(600, 1, 1), "BILLS-119s1071enr", "enr", None)
    _, capped, actual, list_truncated = _toc_nodes(parsed.units, 1, parsed.subtree_bytes)
    assert actual == 1                 # the requested depth was honored...
    assert capped is False             # ...so this is NOT a depth reduction
    assert list_truncated is True      # ...it is a truncated list


@pytest.mark.asyncio
async def test_toc_response_separates_depth_reduction_from_more_below(monkeypatch):
    # End to end through the response model: the two fields must disagree on a bill
    # where the depth was reduced, which is the whole point of splitting them.
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import ResolvedBillText
    from congress_api.features.bill_text.service import LoadedBillText

    parsed = parse_bill_xml(_deep_bill_xml(2, 10, 30), "BILLS-119s1071enr", "enr", None)
    loaded = LoadedBillText(
        resolved=ResolvedBillText(
            package_id="BILLS-119s1071enr",
            version="enr",
            version_resolved_at="2026-08-03T00:00:00Z",
            version_resolution_note=None,
            last_modified=None,
            xml_bytes=b"",
        ),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)

    reduced = await tools_mod.get_bill_toc(
        None, congress=119, bill_type="s", number=1071, depth=5)
    assert "error" not in reduced
    assert reduced["depth_reduced"] is True
    assert reduced["requested_depth"] == 5
    assert reduced["depth"] < 5
    # The reduction must be stated in words too, alongside the hidden-section advice
    # rather than suppressed by it -- the note is the only channel a text-only reader has.
    assert "reduced to" in reduced["toc_note"]
    assert "search_bill_text" in reduced["toc_note"]

    # Same bill, a depth the cap can serve: more still exists below, but nothing was
    # overridden. toc_truncated stays true; depth_reduced must go false.
    honored = await tools_mod.get_bill_toc(
        None, congress=119, bill_type="s", number=1071, depth=1)
    assert honored["depth_reduced"] is False
    assert honored["requested_depth"] == 1 and honored["depth"] == 1
    assert honored["toc_truncated"] is True
    assert "reduced to" not in (honored["toc_note"] or "")


def test_toc_hidden_advice_promises_depth_only_when_servable():
    # V5 gap 2: when the depth ARGUMENT is what hides sections and the full tree still
    # fits under the node cap, advise the reachable depth.
    parsed = parse_bill_xml(_deep_bill_xml(2, 2, 2), "BILLS-119s1071enr", "enr", None)  # tiny, 8 sections
    toc, capped, actual, _ = _toc_nodes(parsed.units, 2, parsed.subtree_bytes)
    assert not capped and actual == 2
    note = _hidden_section_note(parsed.units, actual, 2, parsed.subtree_bytes)
    assert note and "call with depth=3" in note  # depth 3 is servable, so promise it


def test_toc_hidden_advice_does_not_recommend_a_depth_the_node_cap_blocks():
    # V5 gap 2, the actual defect: when the 500-NODE CAP (not the depth arg) hides the
    # sections, advising "call with depth=N" is circular -- that call re-caps to the same
    # tree. 2*10*30 = 600 sections exceed 500 at depth 3, forcing degradation to depth 2.
    parsed = parse_bill_xml(_deep_bill_xml(2, 10, 30), "BILLS-119s1071enr", "enr", None)
    toc, capped, actual, _ = _toc_nodes(parsed.units, 5, parsed.subtree_bytes)
    assert capped and actual < 3  # the cap forced a depth shallower than the sections
    note = _hidden_section_note(parsed.units, actual, 5, parsed.subtree_bytes)
    assert note is not None
    required = _max_section_depth(parsed.units)
    assert f"call with depth={required}" not in note   # would be circular
    assert "search_bill_text" in note and "deepest listable depth" in note
