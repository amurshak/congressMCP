import os
from pathlib import Path

import pytest

from congress_api.features.bill_text.index import BillTextIndex, fts_literal, has_token, normalized_query
from congress_api.features.bill_text.client import TextVersion, order_versions, _xml_url_from_summary
from congress_api.features.bill_text.models import AncestorNode
from congress_api.features.bill_text.parser import (
    MAX_UNIT_BYTES,
    Segment,
    Unit,
    byte_split_unit,
    parse_bill_xml,
)
from congress_api.features.bill_text.tools import _resolve_unit, _toc_nodes


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
    assert first.unit.amends == ["14 U.S.C. 5601"]


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


def test_rrf_dedupes_duplicate_queries():
    parsed = parse_fixture("bill_text_trimmed.xml")
    index = BillTextIndex(parsed)
    single = index.search(["icebreaker"], 10)[0].score
    duplicate = index.search(["icebreaker", "icebreaker"], 10)[0].score
    assert duplicate == single


def test_toc_depth_and_node_cap_shape():
    parsed = parse_fixture("bill_text_trimmed.xml")
    toc, truncated, depth = _toc_nodes(parsed.units, 2)
    assert depth == 2
    assert not truncated
    assert toc[0].section_id == "D:A"


def test_oversized_leaf_byte_fallback_uses_para_ids():
    unit = Unit(
        section_id="D:A/T:I/S:999",
        ancestor_path=[AncestorNode(type="D", enum="A", header="Division")],
        header="Large leaf",
        segments=[Segment("operative", "\n\n".join(["needle " * 600, "haystack " * 600]))],
    )
    chunks = byte_split_unit(unit)
    assert [chunk.section_id for chunk in chunks] == ["D:A/T:I/S:999/PARA:1", "D:A/T:I/S:999/PARA:2"]
    assert all(chunk.byte_length <= 8_000 for chunk in chunks)


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
    assert [c.section_id for c in chunks] == [f"D:A/T:I/S:1/SS:(a)/PARA:{i}" for i in range(1, len(chunks) + 1)]


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
    assert unit.amends == ["14 U.S.C. 5601", "7 U.S.C. 2012", "7 U.S.C. 2028"]
    assert "42 U.S.C. 1396" not in unit.amends  # bare cross-reference, not amended


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

    toc = await tools_mod.get_bill_toc(None, 119, "s", 1071, depth=2)
    assert "error" not in toc and toc["toc"]

    search = await tools_mod.search_bill_text(None, 119, "s", 1071, ["icebreaker"], max_hits=999)
    assert "error" not in search and search["hits"]
    assert "clamped to 50" in search["version_resolution_note"]  # clamp note still merges
    assert search["timing"]["search_ms"] is not None and search["timing"]["total_ms"] >= 0
    assert toc["timing"]["search_ms"] is None  # no search phase for toc

    section = await tools_mod.get_bill_section(None, 119, "s", 1071, search["hits"][0]["section_id"])
    assert "error" not in section and section["text"]


@pytest.mark.asyncio
async def test_tool_wrapper_catches_and_logs_unexpected_errors(monkeypatch, caplog):
    import logging

    import congress_api.features.bill_text.tools as tools_mod

    async def boom(ctx, congress, bill_type, number, version):
        raise RuntimeError("simulated downstream failure")

    monkeypatch.setattr(tools_mod, "load_bill_text", boom)
    with caplog.at_level(logging.ERROR):
        result = await tools_mod.get_bill_toc(None, 119, "s", 1071)
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


@pytest.mark.skipif(not os.getenv("CONGRESSMCP_LIVE_ACCEPTANCE"), reason="live GovInfo/Congress.gov acceptance is opt-in")
def test_live_acceptance_placeholder():
    pytest.skip("Run V1-V12 manually with CONGRESSMCP_LIVE_ACCEPTANCE and record findings in the README/PR.")
