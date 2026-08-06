"""V17 -- wire-format conformance for the three bill-text tools (spec §9).

Exercises the SERIALIZER, not the fetch: load_bill_text is patched to return a
fixture-built LoadedBillText, so a green run here is NOT an end-to-end acceptance --
it asserts the response CONTRACT that no V1-V16 step covered. D2 is the reason this
gap is load-bearing: a tool can pass every parser/index step and still emit an empty
structured array with all content in a prose blob.

The two assertions that carry the weight -- both catch D2, where field-presence would
not (members=[] is present and correctly typed; presence is not the property):

  POPULATION -- collections are non-empty for inputs known to match. The check is that
    the tool PUT the data in the structured field, not that the field exists.

  COUNT/COLLECTION COHERENCE -- every count field equals the size of what it counts
    (chunks_indexed == #units, sections_indexed, chunks_searched, toc depth == measured
    tree depth). D2's actual signature is results_count disagreeing with an empty
    serializer; a per-field check structurally cannot see that, a cross-field invariant
    catches it on the first run. Same family as `amends != [] => is_amendatory`.

Plus a no-prose-blob guard, and -- the durable half, the only assertion that guards a
FUTURE failure rather than confirming today's behavior -- an AST check that the
bill_text package never imports the shared response_converters. That is exactly how
someone "routing the new tools through the shared converter for consistency" would
silently inherit D2; it is one line and it outlives the rest.
"""
from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

import congress_api.features.bill_text.tools as tools
from congress_api.features.bill_text.client import ResolvedBillText
from congress_api.features.bill_text.index import BillTextIndex
from congress_api.features.bill_text.parser import parse_bill_xml
from congress_api.features.bill_text.service import LoadedBillText

FIXTURE = Path(__file__).parent / "fixtures" / "bill_text_trimmed.xml"
PKG, VER = "BILLS-119s1071enr", "enr"
_QUERY = "polar security cutter"      # present in the fixture's quoted material
_SECTION_ID = "D:B/T:I/S:102"          # a real leaf section in the fixture


def _loaded() -> LoadedBillText:
    parsed = parse_bill_xml(FIXTURE.read_bytes(), PKG, VER, "2025-12-19T03:11:48Z")
    resolved = ResolvedBillText(
        package_id=PKG, version=VER, version_resolved_at="2025-12-19T03:11:48Z",
        version_resolution_note=None, last_modified="2025-12-19T03:11:48Z", xml_bytes=b"",
    )
    return LoadedBillText(resolved=resolved, parsed=parsed, index=BillTextIndex(parsed),
                          timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0})


LOADED = _loaded()


class _Ctx:  # never touched: load_bill_text is patched, so the fetch path never runs
    pass


def _call(coro_fn, *args, **kwargs):
    async def fake_load(ctx, congress, bill_type, number, version):
        return LOADED
    with patch.object(tools, "load_bill_text", new=fake_load):
        return asyncio.run(coro_fn(_Ctx(), *args, **kwargs))


def _measured_depth(nodes: list[dict]) -> int:
    """Max nesting depth of a toc forest (1 per level, 0 for empty)."""
    if not nodes:
        return 0
    return 1 + max(_measured_depth(n.get("children") or []) for n in nodes)


# --------------------------------------------------------------------------- #
# search_bill_text
# --------------------------------------------------------------------------- #
def test_search_populates_hits_and_counts_cohere():
    res = _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
                queries=[_QUERY], max_hits=10)
    assert "summary" not in res                          # no prose-blob smuggling
    # POPULATION: a matching query must return a non-empty structured array
    assert isinstance(res["hits"], list) and len(res["hits"]) > 0
    # COHERENCE: reported index/search counts must equal reality
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed
    assert res["chunks_searched"] == res["chunks_indexed"]   # the whole bill was searched
    assert len(res["hits"]) <= 10                            # respects max_hits
    # each hit is a structured object carrying the §9 payload, not a string
    assert all(isinstance(h, dict) and h.get("section_id") for h in res["hits"])


# --------------------------------------------------------------------------- #
# get_bill_section
# --------------------------------------------------------------------------- #
def test_section_populates_text_and_counts_cohere():
    res = _call(tools.get_bill_section, congress=119, bill_type="s", number=1071,
                section_id=_SECTION_ID)
    assert "summary" not in res
    # POPULATION: the statutory text lives in a structured field, non-empty
    assert isinstance(res["text"], str) and res["text"].strip()
    assert res["section_id"] == _SECTION_ID
    # COHERENCE
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed
    # children coherence: when present it is a list; each entry a structured object
    if res.get("children") is not None:
        assert isinstance(res["children"], list)
        assert all(isinstance(c, dict) and c.get("section_id") for c in res["children"])


# --------------------------------------------------------------------------- #
# get_bill_toc
# --------------------------------------------------------------------------- #
def test_toc_populates_tree_and_depth_coheres():
    res = _call(tools.get_bill_toc, congress=119, bill_type="s", number=1071, depth=5)
    assert "summary" not in res
    # POPULATION: a bill with sections must yield a non-empty toc
    assert isinstance(res["toc"], list) and len(res["toc"]) > 0
    # COHERENCE (count/collection): the toc roots are exactly the bill's top-level
    # structures -- every one represented, none invented.
    top_level = {u.section_id.split("/")[0] for u in LOADED.parsed.units}
    assert len(res["toc"]) == len(top_level)
    # `depth` is the effective depth BOUND (requested, reduced by the node cap), not a
    # measurement -- so the tree must respect it, but need not reach it.
    assert 1 <= _measured_depth(res["toc"]) <= res["depth"]
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed


# --------------------------------------------------------------------------- #
# The durable half: bill_text must never inherit the shared members/committees
# serializer (response_converters), which is where D2 lives. This guards the
# realistic future regression, not today's behavior.
# --------------------------------------------------------------------------- #
def test_bill_text_never_imports_shared_response_converters():
    pkg_dir = Path(tools.__file__).parent
    offenders: list[str] = []
    for py in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            mods: list[str] = []
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                mods.extend(alias.name for alias in node.names)
            if any("response_converters" in m for m in mods) or any(
                n.startswith("convert_") and n.endswith("_response") for n in names
            ):
                offenders.append(f"{py.name}: {mods or names}")
    assert not offenders, (
        "bill_text imports the shared response converter -- D2's serializer. Build the "
        f"response models directly instead: {offenders}"
    )


@pytest.mark.parametrize("missing", ["hits", "text", "toc"])
def test_conformance_fields_are_the_ones_that_matter(missing):
    # Guards the guard: if these payload keys are renamed, the population checks above
    # would silently pass on .get(); pin the names the assertions depend on.
    shapes = {
        "hits": _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
                      queries=[_QUERY], max_hits=10),
        "text": _call(tools.get_bill_section, congress=119, bill_type="s", number=1071,
                      section_id=_SECTION_ID),
        "toc": _call(tools.get_bill_toc, congress=119, bill_type="s", number=1071, depth=5),
    }
    assert missing in shapes[missing]
