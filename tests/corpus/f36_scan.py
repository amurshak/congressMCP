#!/usr/bin/env python
"""F36 measurement (preregistered, 14-defect-priority.md, 2026-08-22). Offline.

    python -m tests.corpus.f36_scan --extra path/to/BILLS-119hr10115ih.xml
    BILL_TEXT_CORPUS_CACHE=... python -m tests.corpus.f36_scan --out runs/f36/<ts>

MEASUREMENT ONLY -- the fix is post-PR-2 and lands with F35. This scan counts
the class F36 names: amendatory units whose verb-hugged SUBJECT carries a
parenthetical Public Law N-M / N U.S.C. M note citation and whose `amends`
carries no entry for it. The live miss is

    Section 5A of the Radiation Exposure Compensation Act
    (Public Law 101–426; 42 U.S.C. 2210 note) is amended—

where the P.L. form's hug fails on the "; 42 U.S.C. 2210 note" trailer inside
the parenthetical, and the USC form's hug fails on the word "note" -- so both
forms miss and `amends: []`. En-dash AND hyphen P.L. forms are both matched
(the live miss is 101–426, en-dash) and reported separately.

WHAT IS COUNTED, AND HOW.
  * Candidate INSTANCE: a parenthetical "( ... )" in a unit's OPERATIVE text
    (scoped by segment.context -- identity, never position) whose body contains
    a P.L. cite and/or a "N U.S.C. M note" cite, and that is the amendatory
    subject -- i.e. the parser's own verb hug (_HUG: only closers, commas,
    semicolons, whitespace) binds the closing paren to "is/are [further|hereby]
    amended|repealed". That is the STRICT tier: the exact text the fix must
    catch. A RELAXED tier is reported beside it: the same parenthetical with an
    interposed clause before the verb within the sentence ("..., as added by
    section 110204 of Public Law 118-xx, is amended") -- the A6 class, counted
    separately because A6's own flip condition governs it, not F36.
  * Provenance exclusion: a parenthetical reached via "as [added|amended] by"
    is an intervening amender, not the target, and is not a candidate (the
    parser's own _is_provenance_cite decides).
  * MISS: the instance's P.L. cite (as "P.L. C-N", any dash normalized) and/or
    its USC-note cite (as "T U.S.C. S") is absent from the unit's `amends`.
    NO-ENTRY = none of the instance's cites is in `amends` (F36 proper: "yielding
    no amends entry"); PARTIAL = the P.L. was captured but the USC-note was not
    (the parenthetical "(43 U.S.C. 1331 note; Public Law 109–432)" shape) --
    reported beside, not counted as F36.
  * UNIT-level count (the preregistered metric): amendatory units with >= 1
    strict-tier NO-ENTRY instance.
  * PRECISION SAMPLE: a seeded random sample (n=20, seed 36) of strict no-entry
    instances with +/-140 chars of context is written into the report for hand
    coding -- V13's discipline; a detector's count is not evidence until its
    precision is.
  * Planted negative, live: the same parenthetical in a non-amendatory position
    ("a claim submitted under the ... Act (Public Law 101–426; ...)." -- hr10115
    S:12) must NOT be a candidate; the scan reports how many parentheticals were
    seen but not hugged, per document, so the gate's selectivity is visible.

CORPUS-SCAN HYGIENE (tests/corpus/measure.py): every denominator printed beside
every count; corpus-wide denominators asserted non-zero and the run exits
non-zero if any is empty. A document with zero amendatory units is reported as
"n=0 amendatory" -- never as "0 found".

Artifacts: <out>/report.md and <out>/report.json (default runs/f36/<utc-ts>).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from congress_api.features.bill_text import parser as parser_mod  # noqa: E402
from congress_api.features.bill_text.parser import parse_bill_xml  # noqa: E402

MANIFEST = json.loads((HERE / "manifest.json").read_text())

# Any unicode hyphen/dash between the Congress number and the law number.
_PL_DASH = "\\-\u2010-\u2015"
PL_IN_PAREN_RE = re.compile(
    r"(?:Public\s+Law|Pub\.?\s*L\.?|P\.?\s*L\.?)\s*\.?\s*"
    rf"(?P<congress>\d+)(?P<dash>[{_PL_DASH}])(?P<law>\d+)",
    re.IGNORECASE,
)
USC_NOTE_RE = re.compile(
    r"\b(?P<title>\d+)\s+U\.?\s?S\.?\s?C\.?\s+"
    rf"(?P<section>\d+[A-Za-z]*(?:[{parser_mod._SECTION_DASH}]\d+[A-Za-z]*)?)"
    r"(?:\([0-9A-Za-z]+\))*\s+note\b",
    re.IGNORECASE,
)
# A balanced, non-nested parenthetical. Nested parens inside the body (rare in
# this position) would split it; the hr10115 shape has none.
PAREN_RE = re.compile(r"\(([^()]*)\)")
# The parser's own hug, applied to the text that follows the closing paren.
STRICT_HUG_RE = re.compile(r"^" + parser_mod._HUG, re.IGNORECASE)
# The relaxed tier (A6 class): an amendatory verb later in the same sentence.
RELAXED_VERB_RE = re.compile(r"\b" + parser_mod._AMEND_VERB + r"\b", re.IGNORECASE)


def cache_dir() -> Path:
    default = REPO / MANIFEST["cache_default"]
    return Path(os.getenv(MANIFEST["cache_env"], str(default)))


def operative_text(unit) -> str:
    return "\n\n".join(s.text for s in unit.segments if s.context == "operative")


def _tier(after: str) -> str | None:
    """strict | relaxed | None for the text following a parenthetical's ')'."""
    if STRICT_HUG_RE.match(after):
        return "strict"
    window = after[:240]
    cut = window.find(". ")
    if cut != -1:
        window = window[:cut]
    if RELAXED_VERB_RE.search(window):
        return "relaxed"
    return None


def instances(text: str) -> list[dict]:
    """Every parenthetical PL / USC-note cite in `text`, classified."""
    found: list[dict] = []
    for m in PAREN_RE.finditer(text):
        body = m.group(1)
        pl = PL_IN_PAREN_RE.search(body)
        usc = USC_NOTE_RE.search(body)
        if not pl and not usc:
            continue
        provenance = parser_mod._is_provenance_cite(text, m.start())
        tier = None if provenance else _tier(text[m.end():])
        found.append({
            "text": "(" + body + ")",
            "context": text[max(0, m.start() - 140):m.end() + 140].replace("\n", " "),
            "pl": (f"P.L. {pl.group('congress')}-{pl.group('law')}" if pl else None),
            "pl_dash": (("en-dash" if pl.group("dash") == "\u2013" else
                         "hyphen" if pl.group("dash") == "-" else
                         f"U+{ord(pl.group('dash')):04X}") if pl else None),
            "usc_note": (f"{usc.group('title')} U.S.C. "
                         f"{parser_mod._normalize_section_dash(usc.group('section'))}"
                         if usc else None),
            "provenance": provenance,
            "tier": tier,
        })
    return found


def scan_unit(unit) -> dict | None:
    """Per-unit record, or None when the unit has no parenthetical cite at all."""
    text = operative_text(unit)
    inst = instances(text)
    if not inst:
        return None
    amends = {a["cite"] for a in unit.amends}
    for i in inst:
        cites = [c for c in (i["pl"], i["usc_note"]) if c]
        i["in_amends"] = [c for c in cites if c in amends]
        i["missing"] = [c for c in cites if c not in amends]
        i["shape"] = ("pl+usc_note" if i["pl"] and i["usc_note"]
                      else "pl" if i["pl"] else "usc_note")
        i["no_entry"] = bool(i["missing"]) and not i["in_amends"]
        i["partial"] = bool(i["missing"]) and bool(i["in_amends"])
    return {
        "section_id": unit.section_id,
        "is_amendatory": unit.is_amendatory,
        "amends": sorted(amends),
        "instances": inst,
    }


def scan_document(package_id: str, data: bytes, version: str) -> dict:
    parsed = parse_bill_xml(data, package_id, version, None)
    units = parsed.units
    amendatory = [u for u in units if u.is_amendatory]
    records = [r for r in (scan_unit(u) for u in units) if r]

    def count(pred) -> int:
        return sum(1 for r in records for i in r["instances"] if pred(r, i))

    strict_miss_units = sorted({
        r["section_id"] for r in records if r["is_amendatory"]
        and any(i["tier"] == "strict" and i["no_entry"] for i in r["instances"])
    })
    relaxed_miss_units = sorted({
        r["section_id"] for r in records if r["is_amendatory"]
        and r["section_id"] not in strict_miss_units
        and any(i["tier"] == "relaxed" and i["no_entry"] for i in r["instances"])
    })
    shapes: dict[str, int] = {}
    for r in records:
        for i in r["instances"]:
            if i["tier"] == "strict" and i["no_entry"]:
                shapes[i["shape"]] = shapes.get(i["shape"], 0) + 1
    return {
        "package_id": package_id,
        "sha256": hashlib.sha256(data).hexdigest(),
        "units": len(units),
        "amendatory_units": len(amendatory),
        "units_with_paren_cite": len(records),
        "instances_total": count(lambda r, i: True),
        "instances_not_hugged": count(lambda r, i: i["tier"] is None and not i["provenance"]),
        "instances_provenance": count(lambda r, i: i["provenance"]),
        "instances_strict": count(lambda r, i: i["tier"] == "strict"),
        "instances_strict_missing": count(lambda r, i: i["tier"] == "strict" and i["missing"]),
        "instances_strict_no_entry": count(lambda r, i: i["tier"] == "strict" and i["no_entry"]),
        "instances_strict_partial": count(lambda r, i: i["tier"] == "strict" and i["partial"]),
        "instances_relaxed": count(lambda r, i: i["tier"] == "relaxed"),
        "instances_relaxed_missing": count(lambda r, i: i["tier"] == "relaxed" and i["missing"]),
        "instances_relaxed_no_entry": count(lambda r, i: i["tier"] == "relaxed" and i["no_entry"]),
        "strict_no_entry_shapes": dict(sorted(shapes.items())),
        "pl_dash_forms_strict_missing": _dash_forms(records, "strict"),
        "pl_dash_forms_relaxed_missing": _dash_forms(records, "relaxed"),
        "f36_units_strict": strict_miss_units,
        "f36_units_relaxed_only": relaxed_miss_units,
        "records": records,
    }


def _dash_forms(records: list[dict], tier: str) -> dict[str, int]:
    forms: dict[str, int] = {}
    for r in records:
        for i in r["instances"]:
            if i["tier"] == tier and i["no_entry"] and i["pl_dash"]:
                forms[i["pl_dash"]] = forms.get(i["pl_dash"], 0) + 1
    return dict(sorted(forms.items()))


def render_markdown(report: dict) -> str:
    lines = [
        "# F36 measurement -- parenthetical P.L. / U.S.C.-note cites on the amendatory subject",
        "",
        f"Generated {report['generated_utc']}; build {report['build_sha'][:12]}. "
        "Measurement only (fix lands post-PR-2 with F35).",
        "",
        "Strict = the parser's own verb hug binds the parenthetical's `)` to the verb "
        "(the text F36's fix must catch). Relaxed = interposed clause before the verb "
        "(A6 class, reported beside, not counted as F36). Missing = the instance's "
        "cite(s) absent from the unit's `amends`.",
        "",
        "| document | units | amendatory | w/ paren cite | instances | not hugged | "
        "provenance | strict | strict no-entry | strict partial | relaxed | "
        "relaxed no-entry | F36 units (strict) | A6-only units |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for d in report["documents"]:
        lines.append(
            f"| {d['package_id']} | {d['units']} | {d['amendatory_units']} | "
            f"{d['units_with_paren_cite']} | {d['instances_total']} | "
            f"{d['instances_not_hugged']} | {d['instances_provenance']} | "
            f"{d['instances_strict']} | {d['instances_strict_no_entry']} | "
            f"{d['instances_strict_partial']} | "
            f"{d['instances_relaxed']} | {d['instances_relaxed_no_entry']} | "
            f"{', '.join(d['f36_units_strict']) or '-'} | "
            f"{', '.join(d['f36_units_relaxed_only']) or '-'} |"
        )
    t = report["totals"]
    lines += [
        "",
        f"**Totals** -- documents {t['documents']}; units {t['units']}; amendatory units "
        f"{t['amendatory_units']}; parenthetical-cite instances {t['instances_total']} "
        f"(not hugged {t['instances_not_hugged']}, provenance {t['instances_provenance']}); "
        f"strict-hugged {t['instances_strict']} of which NO ENTRY in `amends` "
        f"{t['instances_strict_no_entry']} (shapes {json.dumps(t['strict_no_entry_shapes'])}) "
        f"and PARTIAL (P.L. captured, USC-note not) {t['instances_strict_partial']}; "
        f"relaxed {t['instances_relaxed']} of which no entry {t['instances_relaxed_no_entry']}.",
        "",
        f"**F36 unit count (preregistered metric, strict tier, no-entry): "
        f"{t['f36_units_strict']}** (of {t['amendatory_units']} amendatory units); A6-only "
        f"units {t['f36_units_relaxed_only']}. P.L. dash forms among strict no-entry: "
        f"{json.dumps(t['pl_dash_forms_strict_missing'])}; among relaxed no-entry: "
        f"{json.dumps(t['pl_dash_forms_relaxed_missing'])}.",
        "",
        f"## Precision sample -- {len(report['precision_sample'])} strict no-entry instances, "
        f"seed {report['precision_seed']}, for hand coding",
        "",
        "| # | document | unit | parenthetical | context |",
        "|---:|---|---|---|---|",
        *[f"| {n} | {x['package_id']} | {x['section_id']} | `{x['text'][:70]}` | "
          f"…{x['context'].replace('|', '\\|')}… |"
          for n, x in enumerate(report["precision_sample"], start=1)],
        "",
        "## Instances on the F36 bill and every strict/relaxed NO-ENTRY instance elsewhere",
        "",
        "| document | unit | tier | parenthetical | P.L. (dash) | USC note | in amends | missing |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for d in report["documents"]:
        show_all = d["package_id"] == report.get("focus_package")
        for r in d["records"]:
            for i in r["instances"]:
                if not show_all and not (i["tier"] and i["no_entry"]):
                    continue
                lines.append(
                    f"| {d['package_id']} | {r['section_id']} | "
                    f"{('provenance' if i['provenance'] else i['tier'] or 'not hugged')} | "
                    f"`{i['text'][:90]}` | {i['pl'] or '-'} ({i['pl_dash'] or '-'}) | "
                    f"{i['usc_note'] or '-'} | {', '.join(i['in_amends']) or '-'} | "
                    f"{', '.join(i['missing']) or '-'} |"
                )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extra", action="append", default=[],
                    help="extra XML file(s) to scan beside the corpus, e.g. "
                         "BILLS-119hr10115ih.xml (package id taken from the filename)")
    ap.add_argument("--focus", default="BILLS-119hr10115ih",
                    help="package whose every instance is listed (default the F36 bill)")
    ap.add_argument("--out", default=None, help="artifact dir (default runs/f36/<utc-ts>)")
    args = ap.parse_args(argv)

    sources: list[tuple[str, Path, str]] = []
    cdir = cache_dir()
    for entry in MANIFEST["packages"]:
        path = cdir / f"{entry['package_id']}.xml"
        if path.exists():
            sources.append((entry["package_id"], path, entry["version"]))
    for raw in args.extra:
        path = Path(raw)
        pid = path.name.removesuffix(".xml")
        sources.append((pid, path, pid[-2:]))
    if not sources:
        print("FATAL: nothing to scan (empty corpus cache and no --extra)")
        return 1

    docs = [scan_document(pid, path.read_bytes(), ver) for pid, path, ver in sources]
    keys = ("units", "amendatory_units", "units_with_paren_cite", "instances_total",
            "instances_not_hugged", "instances_provenance", "instances_strict",
            "instances_strict_missing", "instances_strict_no_entry",
            "instances_strict_partial", "instances_relaxed", "instances_relaxed_missing",
            "instances_relaxed_no_entry")
    totals = {k: sum(d[k] for d in docs) for k in keys}
    totals["documents"] = len(docs)
    totals["f36_units_strict"] = sum(len(d["f36_units_strict"]) for d in docs)
    totals["f36_units_relaxed_only"] = sum(len(d["f36_units_relaxed_only"]) for d in docs)
    shapes: dict[str, int] = {}
    for d in docs:
        for k, v in d["strict_no_entry_shapes"].items():
            shapes[k] = shapes.get(k, 0) + v
    totals["strict_no_entry_shapes"] = dict(sorted(shapes.items()))
    pool = [{"package_id": d["package_id"], "section_id": r["section_id"],
             "text": i["text"], "context": i["context"]}
            for d in docs for r in d["records"] for i in r["instances"]
            if i["tier"] == "strict" and i["no_entry"]]
    seed = 36
    sample = random.Random(seed).sample(pool, min(20, len(pool)))
    for tier in ("strict", "relaxed"):
        forms: dict[str, int] = {}
        for d in docs:
            for k, v in d[f"pl_dash_forms_{tier}_missing"].items():
                forms[k] = forms.get(k, 0) + v
        totals[f"pl_dash_forms_{tier}_missing"] = dict(sorted(forms.items()))

    import subprocess  # noqa: PLC0415
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                         text=True).stdout.strip() or "UNKNOWN"
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "build_sha": sha,
        "focus_package": args.focus,
        "corpus_cache": str(cdir),
        "extra": [str(Path(x)) for x in args.extra],
        "totals": totals,
        "precision_seed": seed,
        "precision_sample": sample,
        "documents": docs,
    }

    out = Path(args.out or (REPO / "runs" / "f36" /
                            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")))
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    md = render_markdown(report)
    (out / "report.md").write_text(md)
    print(md)
    print(f"artifacts: {out}")

    # Non-zero denominators, asserted: an errored scan must not read as an empty one.
    empty = [k for k in ("documents", "units", "amendatory_units", "instances_total")
             if not totals[k]]
    if empty:
        print(f"FATAL: empty denominator(s) {empty} -- the scan established nothing")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
