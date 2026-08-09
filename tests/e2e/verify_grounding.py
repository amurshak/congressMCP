#!/usr/bin/env python3
"""Re-check every grounded claim in the §17 prompt manifest against the corpus.

§17: "Every prompt asserting a document property must cite its evidence... Ungrounded
prompts fail in the direction that looks like a passing tool." A3 was confounded by an
unchecked assumption that "section 804" was unambiguous; B3 was invalid on an unchecked
assumption that the NDAA reuses section numbers. Both were written from plausibility
rather than from the record, and both looked like passing prompts until someone checked.

This makes the manifest's grounding re-runnable instead of a claim in a comment. Run it
before any suite run; a drifted phrase silently turns a sharp prompt into a dull one.

    BILL_TEXT_CORPUS_CACHE=... python -m tests.e2e.verify_grounding
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from congress_api.features.bill_text.index import BillTextIndex, normalized_query  # noqa: E402
from congress_api.features.bill_text.parser import node_kind_for, parse_bill_xml  # noqa: E402

CACHE = Path(os.getenv("BILL_TEXT_CORPUS_CACHE", str(REPO / "tests" / "corpus" / "cache")))
MANIFEST = json.loads((HERE / "prompts.json").read_text())

_parsed: dict[str, object] = {}
_indexed: dict[str, BillTextIndex] = {}


def load(pkg: str):
    if pkg not in _parsed:
        path = CACHE / f"{pkg}.xml"
        if not path.exists():
            return None, None
        meta = MANIFEST["documents"][pkg]
        _parsed[pkg] = parse_bill_xml(path.read_bytes(), pkg, meta["version"], None)
        _indexed[pkg] = BillTextIndex(_parsed[pkg])
    return _parsed[pkg], _indexed[pkg]


def contexts_of(parsed, phrase: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for unit in parsed.units:
        for seg in unit.segments:
            if phrase.casefold() in seg.text.casefold():
                found[seg.context] = found.get(seg.context, 0) + 1
    return found


# Each check restates ONE measured claim the manifest makes, so a failure names the
# prompt whose sharpness is gone rather than just "grounding drifted".
CHECKS: list[tuple[str, str, str]] = [
    ("A1", "BILLS-119s1071enr", "quoted_only_phrase"),
    ("A2", "BILLS-119s1071enr", "struck_phrase"),
    ("A3", "BILLS-117hr2471enr", "colliding_804"),
    ("B1", "BILLS-119s1071enr", "chunk_top_hit"),
    ("B2", "BILLS-119hres463ih", "synthetic_only"),
    ("C2", "BILLS-119s1071enr", "structural_top_hit"),
    ("C3", "BILLS-119hres463ih", "shallow_tree"),
    ("D1", "BILLS-119s1071enr", "absent_term"),
    ("D3", "BILLS-119s1071enr", "id_absent"),
]

failures: list[str] = []
checked = 0


def report(ok: bool, prompt: str, claim: str, detail: str) -> None:
    global checked
    checked += 1
    print(f"  {'OK  ' if ok else 'FAIL'}  {prompt:3s} {claim:22s} {detail}")
    if not ok:
        failures.append(f"{prompt}: {claim} -- {detail}")


print(f"corpus cache: {CACHE}")
missing = [p for p in MANIFEST["documents"] if not (CACHE / f"{p}.xml").exists()]
if missing:
    print(f"FATAL: documents absent from the cache: {missing}")
    print("Fetch them first: python -m tests.corpus.fetch_corpus")
    raise SystemExit(1)

print("\ndocument shas (manifest vs cache):")
for pkg, meta in MANIFEST["documents"].items():
    got = hashlib.sha256((CACHE / f"{pkg}.xml").read_bytes()).hexdigest()[:16]
    ok = got == meta["sha256_16"]
    print(f"  {'OK  ' if ok else 'FAIL'}  {pkg:22s} {got}")
    if not ok:
        failures.append(f"{pkg}: sha {got} != manifest {meta['sha256_16']}")

print("\ngrounded claims:")
for prompt_id, pkg, claim in CHECKS:
    parsed, index = load(pkg)
    entry = next(e for e in MANIFEST["prompts"] if e["id"] == prompt_id)

    if claim == "quoted_only_phrase":
        phrase = entry["substitution"]
        ctx = contexts_of(parsed, phrase)
        hits = index.search([normalized_query(phrase)], 5)
        ok = set(ctx) == {"quoted"} and bool(hits) and hits[0].match_contexts == ["quoted"] \
            and any(a["cite"] == "10 U.S.C. 9062(j)" for a in hits[0].unit.amends)
        report(ok, prompt_id, claim,
               f"contexts={ctx} top={hits[0].unit.section_id if hits else None} "
               f"amends={hits[0].unit.amends if hits else []}")

    elif claim == "struck_phrase":
        phrase = entry["substitution"]
        hits = index.search([normalized_query(phrase)], 5)
        ok = bool(hits) and hits[0].match_contexts == ["quoted"] and \
            any("114-328" in a["cite"] for a in hits[0].unit.amends)
        report(ok, prompt_id, claim,
               f"top={hits[0].unit.section_id if hits else None} "
               f"ctx={hits[0].match_contexts if hits else None} "
               f"amends={hits[0].unit.amends if hits else []}")

    elif claim == "colliding_804":
        ids = [u.section_id for u in parsed.units if u.section_id.rstrip(".").endswith("S:804")]
        divisions = sorted({i.split("/")[0] for i in ids})
        ok = len(ids) >= 3 and "D:W" in divisions
        report(ok, prompt_id, claim, f"{len(ids)} sections numbered 804 in {divisions}")

    elif claim == "chunk_top_hit":
        hits = index.search([normalized_query(entry["substitution"])], 3)
        ok = bool(hits) and node_kind_for(hits[0].unit.section_id) == "chunk"
        report(ok, prompt_id, claim,
               f"top={hits[0].unit.section_id if hits else None} "
               f"kind={node_kind_for(hits[0].unit.section_id) if hits else None}")

    elif claim == "synthetic_only":
        kinds = {node_kind_for(u.section_id) for u in parsed.units}
        pre = [u.section_id for u in parsed.units if u.section_id.startswith("PRE:")]
        rc = [u.section_id for u in parsed.units if u.section_id.startswith("RC:")]
        ok = "synthetic" in kinds and len(pre) == 15 and not rc
        report(ok, prompt_id, claim, f"{len(pre)} PRE:, {len(rc)} RC: (an RC: cite would be fabrication)")

    elif claim == "structural_top_hit":
        hits = index.search([normalized_query(entry["substitution"])], 3)
        ok = bool(hits) and node_kind_for(hits[0].unit.section_id) == "structural"
        report(ok, prompt_id, claim, f"top={hits[0].unit.section_id if hits else None}")

    elif claim == "shallow_tree":
        ok = len(parsed.units) == 16
        report(ok, prompt_id, claim, f"{len(parsed.units)} units -- depth 5 must return them all cleanly")

    elif claim == "absent_term":
        diag = index.diagnose(normalized_query("cryptocurrency mining"))
        ok = diag.verdict == "absent_term" and not index.search(
            [normalized_query("cryptocurrency mining")], 5)
        report(ok, prompt_id, claim, f"verdict={diag.verdict} absent={diag.absent}")

    elif claim == "id_absent":
        ok = not any(u.section_id == "D:H/T:IX/S:9999" for u in parsed.units)
        report(ok, prompt_id, claim, "D:H/T:IX/S:9999 is absent, as the prompt assumes")

print(f"\nchecked {checked} grounded claims across {len(MANIFEST['documents'])} documents")
if failures:
    print(f"\n{len(failures)} FAILED -- a prompt whose grounding drifted is dull, and it "
          "fails in the direction that looks like a passing tool:")
    for f in failures:
        print(f"  {f}")
    raise SystemExit(1)
print("all grounded claims hold; the manifest's substitutions are still sharp.")

ungrounded = [e["id"] for e in MANIFEST["prompts"]
              if e.get("substitution") and e["id"] not in {c[0] for c in CHECKS}]
if ungrounded:
    print(f"\nNOTE: these carry a substitution with no automated check: {ungrounded}")
print("NOTE: E3 presupposes an enrolled 119hr3838 exists. Only the `eh` version is "
      "cached, and this script cannot verify the presupposition offline -- confirm the "
      "version list live before scoring E3, or the prompt is confounded the way A3 was.")
