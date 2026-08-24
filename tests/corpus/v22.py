#!/usr/bin/env python
"""V22 -- subdivided amendatory parents. Offline over the extended corpus.

    BILL_TEXT_CORPUS_CACHE=... python -m tests.corpus.v22

Decides whether F32's section-response fields need returned-text aggregation or
own-unit values suffice (spec §10 V22; gates the §4 F32 container/subdivision
contract). get_bill_section serves a subdivided parent within max_bytes by
concatenating its children at read time, while is_amendatory / amends carry the
parent unit's OWN stored value -- so a parent whose own intro is not amendatory but
whose children are returns its full amendatory text under `is_amendatory: false`.
Whether that section exists is a corpus fact. This script counts it.

THE MEASUREMENT (the preregistered one). Over every cached package, enumerate the
subdivided parents -- units with child_ids, identity against the parser's own tree,
never string matching -- and for each read the stored per-unit is_amendatory of the
parent and of every descendant (recursive closure over child_ids). Count parents
where the parent's own value is false and >=1 descendant's is true. Also record the
parent-true/descendant-true overlap so a fix, if owed, can be sized.

TWO ADJACENT SHAPES, reported separately and labelled so, because the same §4 ruling
gave containers `false / []` and they are served by the same assemble-at-read path:

  * chunk-only prefixes -- a section (or subdivision) over MAX_UNIT_BYTES with NO
    further structural subdivision is emitted ONLY as `.../CHUNK:k` units; no unit
    exists under the prefix itself (`.../S:n` or `.../S:n/SS:(a)`), so addressing it
    by that id resolves through the CONTAINER path and reports false / [] regardless
    of what its chunks say;
  * structural containers (division / title / subtitle / ...) -- never units; they
    report false / [] by ruling, and when their subtree fits max_bytes the assembled
    text is returned under that value.

For each the script reports how many have >=1 amendatory descendant AND would be
assembled under the DEFAULT max_bytes (25,000) -- the configuration in which the
mislabel is active rather than latent (above max_bytes the response is the heading
plus child descriptors, and the amendatory text is not in it).

STORED-VALUE CROSS-CHECK. "Stored per-unit value" is literal: for every found parent
the script re-reads is_amendatory from the BillTextIndex sqlite row -- the column the
search path reports from -- and fails if it disagrees with the Unit property. That is
the carry-don't-reconstruct identity F32 depends on, checked rather than assumed.

VERIFY (F33 acceptance, set-based). After measuring, the script calls the SHIPPED
get_bill_section for every subdivided parent and every non-unit prefix it examined
(load_bill_text patched to the cached, parsed package -- no network) and diffs the
response's is_amendatory / amends against the F33 contract stated independently:
assembled response -> OR / (kind, cite)-union in document order over exactly the
units whose text was included; descriptor-only response -> the addressed unit's own
values (false / [] for a container heading). It then reports the V22 populations by
name -- found∧assembled must read true, found∧assembled∧cited must carry non-empty
amends, both-false rows must stay false / [], overlap rows must stay true -- and
FAILS on any mismatch. This is the acceptance the F33 ruling set: the sets, not the
counts.

HYGIENE (spec §10). Reports n found / n examined / n packages for every figure and
FAILS (exit 1) if a denominator is zero, a manifest package is missing from the
cache, a cached file's sha256 disagrees with the manifest, or the parser's tree is
inconsistent (a child_id that resolves to no unit). A scan that errored must never
render like a scan that found nothing. The preregistered outcome is printed in the
spec's own terms; recording it is the spec session's job, not this script's.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

import asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

import congress_api.features.bill_text.tools as tools  # noqa: E402
from congress_api.features.bill_text.client import ResolvedBillText  # noqa: E402
from congress_api.features.bill_text.index import BillTextIndex  # noqa: E402
from congress_api.features.bill_text.parser import (  # noqa: E402
    ParsedBill,
    Unit,
    parse_bill_xml,
)
from congress_api.features.bill_text.service import LoadedBillText  # noqa: E402

MANIFEST = json.loads((HERE / "manifest.json").read_text())

# get_bill_section's default max_bytes and its clamp ceiling (tools.py). Below the
# default the whole subtree is assembled into `text`; the ceiling is the largest a
# caller can ask for at all.
DEFAULT_MAX_BYTES = 25_000
MAX_MAX_BYTES = 100_000

CHUNK_RE = re.compile(r"^CHUNK:\d+$")


def cache_dir() -> Path:
    default = HERE.parent.parent / MANIFEST["cache_default"]
    return Path(os.getenv(MANIFEST["cache_env"], str(default)))


# --------------------------------------------------------------------------- #
# tree helpers -- identity against the parser's own structures
# --------------------------------------------------------------------------- #

def descendants_of(parent: Unit, by_id: dict[str, Unit]) -> list[Unit]:
    """Recursive closure over child_ids. Raises KeyError on a dangling child_id --
    that is a tree-integrity failure the caller turns into a FAIL, never a skip."""
    out: list[Unit] = []
    stack = list(parent.child_ids)
    while stack:
        cid = stack.pop(0)
        child = by_id[cid]  # KeyError on purpose
        out.append(child)
        stack = list(child.child_ids) + stack
    return out


def merged_amends(units: list[Unit]) -> list[dict[str, str]]:
    """Union of the units' amends, de-duplicated, in the parser's (kind, cite) order."""
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for u in units:
        for a in u.amends:
            seen.setdefault((a["kind"], a["cite"]), a)
    return [seen[k] for k in sorted(seen)]


def _loaded_for(parsed: ParsedBill, raw: bytes, index: BillTextIndex) -> LoadedBillText:
    resolved = ResolvedBillText(
        package_id=parsed.package_id, version=parsed.version, version_resolved_at="",
        version_resolution_note=None, last_modified=None, xml_bytes=raw,
    )
    return LoadedBillText(resolved=resolved, parsed=parsed, index=index,
                          timing={"resolve_ms": 0.0, "download_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0})


class _Ctx:
    pass


def _shipped_section(loaded: LoadedBillText, section_id: str, max_bytes: int) -> dict:
    """Call the SHIPPED get_bill_section with the fetch patched out."""
    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded
    with patch.object(tools, "load_bill_text", new=fake_load):
        return asyncio.run(tools.get_bill_section(
            _Ctx(), congress=0, bill_type="x", number=0, section_id=section_id, max_bytes=max_bytes,
        ))


def expected_disclosure(units: list[Unit]) -> tuple[bool, list[dict[str, str]]]:
    """The F33 contract, independent of the implementation."""
    return any(u.is_amendatory for u in units), merged_amends_docorder(units)


def merged_amends_docorder(units: list[Unit]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for u in units:
        for a in u.amends:
            k = (a["kind"], a["cite"])
            if k not in seen:
                seen.add(k)
                out.append(a)
    return out


@dataclass
class FoundParent:
    package: str
    section_id: str
    header: str | None
    subtree_bytes: int
    n_desc: int
    n_desc_amendatory: int
    desc_amends: list[dict[str, str]]

    @property
    def fits_default(self) -> bool:
        return self.subtree_bytes <= DEFAULT_MAX_BYTES

    @property
    def fits_max(self) -> bool:
        return self.subtree_bytes <= MAX_MAX_BYTES


@dataclass
class PrefixShape:
    """A non-unit id prefix: either a chunk-only prefix or a structural container."""
    package: str
    prefix: str
    kind: str                      # "chunk_only_prefix" | "structural_container"
    subtree_bytes: int
    n_desc: int
    n_desc_amendatory: int
    desc_amends: list[dict[str, str]] = field(default_factory=list)

    @property
    def fits_default(self) -> bool:
        return self.subtree_bytes <= DEFAULT_MAX_BYTES


def non_unit_prefixes(parsed: ParsedBill, by_id: dict[str, Unit]) -> list[PrefixShape]:
    """Every id prefix that is NOT an emitted unit, classified by what sits directly
    beneath it. Prefixes come from subtree_bytes, the parser's own prefix map."""
    units = parsed.units
    shapes: list[PrefixShape] = []
    for prefix, size in parsed.subtree_bytes.items():
        if prefix in by_id:
            continue
        depth = len(prefix.split("/"))
        desc = [u for u in units if u.section_id.startswith(prefix + "/")]
        if not desc:
            continue  # cannot happen: subtree_bytes is built from units
        next_components = {u.section_id.split("/")[depth] for u in desc}
        kind = "chunk_only_prefix" if all(CHUNK_RE.match(c) for c in next_components) \
            else "structural_container"
        amend = [u for u in desc if u.is_amendatory]
        shapes.append(PrefixShape(
            package=parsed.package_id, prefix=prefix, kind=kind, subtree_bytes=size,
            n_desc=len(desc), n_desc_amendatory=len(amend), desc_amends=merged_amends(amend),
        ))
    return shapes


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main() -> int:
    cache = cache_dir()
    entries = MANIFEST["packages"]
    print(f"cache      : {cache}")
    print(f"manifest   : {len(entries)} packages")

    missing = [e["package_id"] for e in entries if not (cache / f"{e['package_id']}.xml").exists()]
    if missing:
        print(f"FAIL: {len(missing)} manifest package(s) absent from the cache: {missing}")
        print("      run `python -m tests.corpus.fetch_corpus` first; a partial corpus is "
              "a different instrument from the one V22 was written for.")
        return 1

    # ---- per-package scan --------------------------------------------------- #
    packages_scanned = 0
    parents_examined = 0
    found: list[FoundParent] = []
    overlap: list[tuple[str, str]] = []          # parent-true AND >=1 descendant-true
    parent_only: list[tuple[str, str]] = []      # parent-true, no descendant-true
    neither = 0
    shapes: list[PrefixShape] = []
    per_package: list[tuple[str, int, int, int]] = []  # pkg, n_parents, n_found, n_overlap
    store_mismatch: list[str] = []
    tree_errors: list[str] = []
    # for the verify pass: pkg -> (parsed, raw, index-or-None, parents, by_id)
    handles: dict[str, tuple] = {}

    for e in entries:
        pkg = e["package_id"]
        raw = (cache / f"{pkg}.xml").read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != e["sha256"]:
            print(f"FAIL: {pkg}: cached sha256 {digest[:16]}… != manifest {e['sha256'][:16]}… "
                  "-- the cache is not the manifest corpus.")
            return 1
        parsed = parse_bill_xml(raw, pkg, e["version"], None)
        by_id = {u.section_id: u for u in parsed.units}
        if len(by_id) != len(parsed.units):
            tree_errors.append(f"{pkg}: duplicate section_id among units")
        packages_scanned += 1

        parents = [u for u in parsed.units if u.child_ids]
        pkg_found = pkg_overlap = 0
        # Stored-value cross-check needs the index; build it once per package and
        # only consult it for the rows that carry a finding.
        index: BillTextIndex | None = None

        for parent in parents:
            try:
                desc = descendants_of(parent, by_id)
            except KeyError as exc:
                tree_errors.append(f"{pkg}: {parent.section_id} has dangling child_id {exc}")
                continue
            parents_examined += 1
            desc_amend = [d for d in desc if d.is_amendatory]
            if not parent.is_amendatory and desc_amend:
                pkg_found += 1
                row = FoundParent(
                    package=pkg, section_id=parent.section_id, header=parent.header,
                    subtree_bytes=parsed.subtree_bytes.get(parent.section_id, parent.byte_length),
                    n_desc=len(desc), n_desc_amendatory=len(desc_amend),
                    desc_amends=merged_amends(desc_amend),
                )
                found.append(row)
                # cross-check: the sqlite column the search path reports from
                if index is None:
                    index = BillTextIndex(parsed)
                stored = {
                    r["section_id"]: bool(r["is_amendatory"])
                    for r in index.conn.execute(
                        "SELECT section_id, is_amendatory FROM units WHERE section_id IN (%s)"
                        % ",".join("?" * (1 + len(desc))),
                        [parent.section_id, *(d.section_id for d in desc)],
                    ).fetchall()
                }
                if stored.get(parent.section_id) is not False:
                    store_mismatch.append(f"{pkg} {parent.section_id}: stored parent value "
                                          f"{stored.get(parent.section_id)!r}, property False")
                for d in desc_amend:
                    if stored.get(d.section_id) is not True:
                        store_mismatch.append(f"{pkg} {d.section_id}: stored {stored.get(d.section_id)!r}, "
                                              "property True")
            elif parent.is_amendatory and desc_amend:
                pkg_overlap += 1
                overlap.append((pkg, parent.section_id))
            elif parent.is_amendatory:
                parent_only.append((pkg, parent.section_id))
            else:
                neither += 1
        per_package.append((pkg, len(parents), pkg_found, pkg_overlap))
        shapes.extend(non_unit_prefixes(parsed, by_id))
        handles[pkg] = (parsed, raw, index, parents, by_id)

    # ---- hygiene gates ------------------------------------------------------ #
    if tree_errors:
        print(f"FAIL: parser tree inconsistent in {len(tree_errors)} place(s):")
        for t in tree_errors[:10]:
            print(f"   {t}")
        return 1
    if packages_scanned == 0:
        print("FAIL: zero packages scanned.")
        return 1
    if parents_examined == 0:
        print(f"FAIL: zero subdivided parents across {packages_scanned} packages -- the corpus "
              "has nothing for V22 to examine. That is a different result from 'none "
              "amendatory' and must not be read as it.")
        return 1
    if store_mismatch:
        print(f"FAIL: Unit property and stored index value disagree on {len(store_mismatch)} "
              "row(s) -- the carry-don't-reconstruct identity does not hold:")
        for m in store_mismatch[:10]:
            print(f"   {m}")
        return 1

    # ---- report: the preregistered measurement ------------------------------ #
    print()
    print("=" * 78)
    print("V22 -- subdivided parents whose OWN is_amendatory is false while >=1 descendant is true")
    print("=" * 78)
    print(f"  n found                      : {len(found)}")
    print(f"  n subdivided parents examined: {parents_examined}")
    print(f"  n packages scanned           : {packages_scanned}")
    print(f"  (stored-value cross-check    : {len(found)} found rows agree with the index column)")
    print()
    print("  breakdown of all subdivided parents:")
    print(f"     parent false, >=1 descendant true  (FOUND)   : {len(found)}")
    print(f"     parent true,  >=1 descendant true  (overlap) : {len(overlap)}")
    print(f"     parent true,  no descendant true             : {len(parent_only)}")
    print(f"     parent false, no descendant true             : {neither}")
    fits_default = [f for f in found if f.fits_default]
    fits_max = [f for f in found if f.fits_max]
    print()
    print("  sizing of the FOUND set against get_bill_section's read contract:")
    print(f"     subtree <= {DEFAULT_MAX_BYTES:,} B (assembled under DEFAULT max_bytes -> "
          f"amendatory text returned under false): {len(fits_default)}")
    print(f"     subtree <= {MAX_MAX_BYTES:,} B (assemblable at the clamp ceiling)          : {len(fits_max)}")
    print(f"     subtree >  {MAX_MAX_BYTES:,} B (heading + child descriptors only)           : {len(found) - len(fits_max)}")
    with_cites = [f for f in found if f.desc_amends]
    print(f"     found parents whose descendants carry >=1 amends cite (an aggregated `amends` "
          f"would be non-empty): {len(with_cites)}")
    if found:
        print()
        print(f"  {'package':<22}{'parent':<36}{'bytes':>8}{'fit':>5}{'desc':>6}{'amnd':>6}{'cites':>6}  header")
        for f in sorted(found, key=lambda r: (r.package, r.section_id))[:60]:
            print(f"  {f.package:<22}{f.section_id[:35]:<36}{f.subtree_bytes:>8,}"
                  f"{'y' if f.fits_default else 'n':>5}{f.n_desc:>6}{f.n_desc_amendatory:>6}"
                  f"{len(f.desc_amends):>6}  {str(f.header)[:28]}")
        if len(found) > 60:
            print(f"  ... {len(found) - 60} more not listed (counted above)")
    print()
    print("  per package (parents / found / overlap):")
    for pkg, n_par, n_f, n_o in per_package:
        print(f"     {pkg:<24} {n_par:>5} / {n_f:>4} / {n_o:>4}")

    # ---- report: adjacent shapes served by the container path ---------------- #
    print()
    print("=" * 78)
    print("ADJACENT (not the preregistered figure): non-unit prefixes served by the container")
    print("path, which reports false / [] by the F32 ruling")
    print("=" * 78)
    for kind, label in (("chunk_only_prefix", "chunk-only prefixes (section/subdivision with no own unit; byte-split only)"),
                        ("structural_container", "structural containers (division/title/subtitle/...)")):
        rows = [s for s in shapes if s.kind == kind]
        amend = [s for s in rows if s.n_desc_amendatory]
        active = [s for s in amend if s.fits_default]
        print(f"  {label}")
        print(f"     n examined                                   : {len(rows)}")
        print(f"     with >=1 amendatory descendant               : {len(amend)}")
        print(f"     ...AND subtree <= {DEFAULT_MAX_BYTES:,} B (assembled by default): {len(active)}")
        if kind == "chunk_only_prefix" and active:
            print(f"     {'package':<22}{'prefix':<36}{'bytes':>8}{'desc':>6}{'amnd':>6}{'cites':>6}")
            for s in sorted(active, key=lambda r: (r.package, r.prefix))[:30]:
                print(f"     {s.package:<22}{s.prefix[:35]:<36}{s.subtree_bytes:>8,}{s.n_desc:>6}"
                      f"{s.n_desc_amendatory:>6}{len(s.desc_amends):>6}")
            if len(active) > 30:
                print(f"     ... {len(active) - 30} more not listed (counted above)")
        print()

    # ---- VERIFY: the shipped tool against the F33 contract, set by set --------- #
    print("=" * 78)
    print(f"VERIFY -- shipped get_bill_section (default max_bytes={DEFAULT_MAX_BYTES:,}) vs the F33")
    print("contract, over every subdivided parent and non-unit prefix examined above")
    print("=" * 78)
    mismatches: list[str] = []
    found_ids = {(f.package, f.section_id) for f in found}
    overlap_ids = set(overlap)
    # named populations -> (n checked, n correct)
    pops: dict[str, list[int]] = {
        "found, assembled under default  -> is_amendatory true": [0, 0],
        "found, assembled, descendants cite -> amends non-empty": [0, 0],
        "found, descriptor-only           -> own values (false, [])": [0, 0],
        "both-false parents                -> false / []": [0, 0],
        "overlap parents (parent true)     -> true": [0, 0],
        "chunk-only prefixes, assembled    -> aggregate": [0, 0],
        "structural containers, assembled  -> aggregate": [0, 0],
        "non-unit prefixes, descriptor-only -> false / []": [0, 0],
    }
    n_calls = 0
    for pkg, (parsed, raw, index, parents, by_id) in handles.items():
        if index is None:
            index = BillTextIndex(parsed)
        loaded = _loaded_for(parsed, raw, index)
        for parent in parents:
            children = [by_id[c] for c in parent.child_ids]
            size = parsed.subtree_bytes.get(parent.section_id, parent.byte_length)
            assembled = size <= DEFAULT_MAX_BYTES
            exp = expected_disclosure([parent, *children]) if assembled else (parent.is_amendatory, parent.amends)
            res = _shipped_section(loaded, parent.section_id, DEFAULT_MAX_BYTES)
            n_calls += 1
            got = (res.get("is_amendatory"), res.get("amends"))
            ok = "error" not in res and got == exp
            key = (pkg, parent.section_id)
            if key in found_ids:
                if assembled:
                    pops["found, assembled under default  -> is_amendatory true"][0] += 1
                    pops["found, assembled under default  -> is_amendatory true"][1] += int(ok and got[0] is True)
                    if any(c.amends for c in children):
                        pops["found, assembled, descendants cite -> amends non-empty"][0] += 1
                        pops["found, assembled, descendants cite -> amends non-empty"][1] += int(ok and bool(got[1]))
                else:
                    pops["found, descriptor-only           -> own values (false, [])"][0] += 1
                    pops["found, descriptor-only           -> own values (false, [])"][1] += int(ok and got == (False, []))
            elif key in overlap_ids:
                pops["overlap parents (parent true)     -> true"][0] += 1
                pops["overlap parents (parent true)     -> true"][1] += int(ok and got[0] is True)
            elif not parent.is_amendatory and not any(c.is_amendatory for c in children):
                pops["both-false parents                -> false / []"][0] += 1
                pops["both-false parents                -> false / []"][1] += int(ok and got == (False, []))
            if not ok:
                mismatches.append(f"{pkg} {parent.section_id}: expected {exp}, got {got}"
                                  + (f" ERROR {res['error']['code']}" if "error" in res else ""))
        for shape in (x for x in shapes if x.package == pkg):
            desc = [u for u in parsed.units if u.section_id.startswith(shape.prefix + "/")]
            assembled = shape.subtree_bytes <= DEFAULT_MAX_BYTES
            exp = expected_disclosure(desc) if assembled else (False, [])
            res = _shipped_section(loaded, shape.prefix, DEFAULT_MAX_BYTES)
            n_calls += 1
            got = (res.get("is_amendatory"), res.get("amends"))
            ok = "error" not in res and got == exp
            if assembled:
                label = ("chunk-only prefixes, assembled    -> aggregate" if shape.kind == "chunk_only_prefix"
                         else "structural containers, assembled  -> aggregate")
            else:
                label = "non-unit prefixes, descriptor-only -> false / []"
            pops[label][0] += 1
            pops[label][1] += int(ok)
            if not ok:
                mismatches.append(f"{pkg} {shape.prefix} ({shape.kind}): expected {exp}, got {got}"
                                  + (f" ERROR {res['error']['code']}" if "error" in res else ""))
    print(f"  shipped-tool calls made: {n_calls}")
    for label, (n, okc) in pops.items():
        flag = "" if okc == n else "   <-- MISMATCH"
        print(f"  {label:<60} {okc:>5} / {n:<5}{flag}")
    if mismatches:
        print(f"\n  FAIL: {len(mismatches)} response(s) disagree with the F33 contract:")
        for m in mismatches[:15]:
            print(f"     {m}")
        verify_ok = False
    else:
        print("\n  VERIFY PASS: every response matches the F33 contract on every examined id.")
        verify_ok = True
    print()

    # ---- preregistered outcome, in the spec's own terms ---------------------- #
    print("=" * 78)
    if found:
        print(f"V22 OUTCOME: EXPECTED -- {len(found)} found "
              f"({len(fits_default)} assembled under default max_bytes) over "
              f"{parents_examined} parents / {packages_scanned} packages.")
        print("  The §4 aggregation question is LIVE: own-unit values mislabel real sections.")
    else:
        print(f"V22 OUTCOME: FALSIFIED -- 0 found over {parents_examined} parents / "
              f"{packages_scanned} packages (non-zero denominators).")
        print("  Per preregistration: aggregation contract is dead-defensive, own-text "
              "semantics stand, the docstring note is the guard.")
    print("  (Recording the outcome is the spec session's job. This script does not write "
          "under documentation/.)")
    return 0 if verify_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
