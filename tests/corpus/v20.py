#!/usr/bin/env python
"""V20 -- does fusion ever hurt? Offline replay of the §17 query sets.

    V20_QUERY_SETS=/path/v20-query-sets.json BILL_TEXT_CORPUS_CACHE=... \
        python -m tests.corpus.v20

Settles the k=60 challenge by measurement rather than by retuning on argument. No
fusion failure has been observed in any §17 trace; the argument against k=60 is sound
but untested, and this spec has four times declined to act on a sound-sounding
argument without a number.

THE SINGLE DIAGNOSTIC: does the correct unit ever rank WORSE under fusion than under
its own best single query? If no, k stays at 60 regardless of the theory. If yes, the
harm is concrete and quantified.

Replays each query set VERBATIM -- same queries in the same order, same max_hits,
because max_hits sets the per-query candidate cap (limit = min(200, max(50,
max_hits*5))) and therefore changes which units are admitted at all. Zero-hit rounds
are included: a concept that consumed a round and returned nothing still competed for
the model's attention budget, so excluding it would understate the imbalance.

Fusion is REPLICATED from BillTextIndex.search rather than re-derived, so a sweep over
k measures the shipped ranking and not a second implementation that happens to agree.

IDS: the §17 traces predate F2, so their target ids carry trailing periods
("D:A/T:I/ST:D/S:141."). Normalized on load -- comparing a pre-F2 id against a post-F2
index would report every target as missing, which renders identically to "fusion lost
the target" and is exactly the kind of silent zero the hygiene rules exist to stop.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from congress_api.features.bill_text.index import (  # noqa: E402
    BillTextIndex,
    fts_literal,
    normalized_query,
)
from congress_api.features.bill_text.parser import parse_bill_xml  # noqa: E402

MANIFEST = json.loads((HERE / "manifest.json").read_text())

# The nine units §17 established as correct, keyed by the round that sought them.
KNOWN_TARGETS = {
    "S:141": "A1 tanker inventory",
    "S:147": "A2 A-10 minimum inventory",
    "D:W/T:VIII/ST:A/S:804": "A3 tribal jurisdiction",
    "D:G/T:LXXII/ST:A/S:7201/SS:(e)/CHUNK:3": "B1 training on workings of Congress",
    "D:G/T:LXXI/ST:B/S:7117": "E1/E2 polar security cutter",
    "D:G/T:LXXII/ST:B/S:7215": "E1/E2 Great Lakes icebreaking",
    "T:VII/ST:A/S:70104": "D4 child tax credit",
    "D:A/T:XVIII/ST:D/S:1832": "B3/D5 modular open system approach",
    "D:C/T:XXXI/ST:B/S:3111": "C1 atomic energy defense codification",
}

# Boilerplate, defined explicitly so the figure is interpretable. A unit counts as
# boilerplate when its heading is stock machinery or its text is dominated by the
# stock phrases §7 names -- these are the units RRF's list-counting behaviour would
# float if consensus were doing harm.
BOILERPLATE_HEADER_RE = re.compile(
    r"^\s*(definitions?|clerical amendment|technical amendment|conforming amendment"
    r"|technical and conforming amendment|effective date|authorization of appropriations|rule of construction)",
    re.IGNORECASE,
)
BOILERPLATE_TEXT_RE = re.compile(
    r"\bthe Secretary shall\b|\bnot later than \d+ days\b|\bin this (section|subtitle|title|Act)[,:]",
    re.IGNORECASE,
)


def cache_dir() -> Path:
    default = HERE.parent.parent / MANIFEST["cache_default"]
    return Path(os.getenv(MANIFEST["cache_env"], str(default)))


def norm_id(section_id: str) -> str:
    """Apply F2's trailing-period rule to a pre-F2 id from the traces."""
    return "/".join(
        (lambda t, s, e: f"{t}:{e.rstrip('.')}" if s else t.rstrip("."))(*c.partition(":"))
        for c in section_id.split("/")
    )


def rank_map(index: BillTextIndex, queries: list[str], max_hits: int):
    """Per-query 1-based unit ranks, replicating BillTextIndex.search's admission.

    Returns (unit_rank, contexts, by_id). unit_rank[unit_id][query] = rank.
    """
    limit = min(200, max(50, max_hits * 5))
    unit_rank: dict[int, dict[str, int]] = defaultdict(dict)
    contexts: dict[int, set[str]] = defaultdict(set)
    for query in queries:
        rows = index.conn.execute(
            """
            SELECT units.id AS unit_id, segments.context
            FROM seg_fts
            JOIN segments ON segments.id = seg_fts.rowid
            JOIN units ON units.id = segments.unit_id
            WHERE seg_fts MATCH ?
            ORDER BY bm25(seg_fts) ASC, units.section_id ASC
            """,
            (fts_literal(query),),
        ).fetchall()
        ranked = 0
        for row in rows:
            unit_id = int(row["unit_id"])
            existing = unit_rank.get(unit_id)
            if existing is None or query not in existing:
                if ranked < limit:
                    ranked += 1
                    unit_rank[unit_id][query] = ranked
                elif existing is None:
                    continue
            contexts[unit_id].add(row["context"])
    by_id = {i: u for i, u in enumerate(index.parsed.units, start=1)}
    return unit_rank, contexts, by_id


def fused_order(unit_rank, by_id, k: int) -> list[int]:
    scored = [
        (-sum(1 / (k + r) for r in ranks.values()), by_id[uid].section_id, uid)
        for uid, ranks in unit_rank.items()
    ]
    return [uid for _, _, uid in sorted(scored)]


def max_of_lists_order(unit_rank, by_id) -> list[int]:
    """Non-RRF control: rank by BEST single-query rank, no consensus effect at all."""
    scored = [(min(ranks.values()), by_id[uid].section_id, uid) for uid, ranks in unit_rank.items()]
    return [uid for _, _, uid in sorted(scored)]


def position(order: list[int], unit_id: int) -> int | None:
    try:
        return order.index(unit_id) + 1
    except ValueError:
        return None


def main() -> int:
    qs_path = Path(os.getenv("V20_QUERY_SETS", str(Path.home() / "Downloads" / "v20-query-sets.json")))
    if not qs_path.exists():
        print(f"FAIL: query sets not found at {qs_path}")
        return 1
    rounds = json.loads(qs_path.read_text())
    cache = cache_dir()

    print(f"query sets : {qs_path}")
    print(f"rounds     : {len(rounds)}  queries: {sum(len(r['queries']) for r in rounds)}"
          f"  zero-hit rounds: {sum(1 for r in rounds if r['n_hits'] == 0)}")
    if not rounds:
        print("FAIL: zero rounds -- nothing measured.")
        return 1

    indexes: dict[str, BillTextIndex] = {}
    missing = set()
    for r in rounds:
        pkg = r["package_id"]
        if pkg in indexes or pkg in missing:
            continue
        path = cache / f"{pkg}.xml"
        if not path.exists():
            missing.add(pkg)
            continue
        indexes[pkg] = BillTextIndex(parse_bill_xml(path.read_bytes(), pkg, "x", None))
    if missing:
        print(f"FAIL: packages absent from the cache: {sorted(missing)}")
        return 1
    print(f"packages   : {len(indexes)} indexed\n")

    # ---- FIDELITY GATE ----------------------------------------------------- #
    # Every rank below is meaningless if the replay does not reproduce the runs it
    # claims to replay. The traces recorded top_hits, so that is checkable ground
    # truth rather than an assumption: replay each round through the SHIPPED
    # search() and require the returned order to match, exactly and in order.
    # A drifted replay would still produce a full table of plausible ranks.
    mismatches = []
    for r in rounds:
        hits = indexes[r["package_id"]].search(
            [normalized_query(q) for q in r["queries"]], r["max_hits"]
        )
        mine = [h.unit.section_id for h in hits][:10]
        theirs = [norm_id(s) for s in r["top_hits"]]
        if mine != theirs:
            mismatches.append((r["package_id"], r["queries"], theirs, mine))
    if mismatches:
        print(f"FAIL: replay does not reproduce {len(mismatches)} of {len(rounds)} recorded rounds.")
        for pkg, q, theirs, mine in mismatches[:3]:
            print(f"   {pkg} {q[:2]}\n      trace: {theirs[:5]}\n      mine : {mine[:5]}")
        return 1
    print(f"fidelity   : {len(rounds)}/{len(rounds)} rounds reproduce their recorded top_hits "
          "exactly and in order\n")

    ks = [1, 5, 10, 60]
    diagnostic_rows = []
    boilerplate_rows = []
    v21_hits = Counter()
    examined = Counter()

    for r in rounds:
        queries = [normalized_query(q) for q in r["queries"]]
        index = indexes[r["package_id"]]
        unit_rank, contexts, by_id = rank_map(index, queries, r["max_hits"])
        examined["rounds"] += 1
        if not unit_rank:
            examined["zero_hit_rounds"] += 1
            continue

        orders = {k: fused_order(unit_rank, by_id, k) for k in ks}
        orders["max"] = max_of_lists_order(unit_rank, by_id)

        # ---- V21 at HIT level: contexts of the units actually returned ---------- #
        for uid in orders[60][: r["max_hits"]]:
            ctx = contexts[uid]
            v21_hits[(("operative" in ctx), ("quoted" in ctx))] += 1
            examined["hits"] += 1

        # ---- the single diagnostic --------------------------------------------- #
        for uid, ranks in unit_rank.items():
            sid = by_id[uid].section_id
            if sid not in KNOWN_TARGETS:
                continue
            best_single = min(ranks.values())
            best_query = min(ranks, key=lambda q: ranks[q])
            fused = position(orders[60], uid)
            diagnostic_rows.append({
                "package": r["package_id"], "target": sid, "label": KNOWN_TARGETS[sid],
                "n_queries": len(queries), "best_single": best_single,
                "best_query": best_query, "fused60": fused,
                "delta": (fused - best_single) if fused else None,
                "sweep": {str(k): position(orders[k], uid) for k in ks},
                "max_of_lists": position(orders["max"], uid),
                "in_max_hits": bool(fused and fused <= r["max_hits"]),
            })
            examined["target_observations"] += 1

        # ---- boilerplate ------------------------------------------------------- #
        best_bp = None
        for pos, uid in enumerate(orders[60], start=1):
            unit = by_id[uid]
            if unit.section_id in KNOWN_TARGETS:
                continue
            if BOILERPLATE_HEADER_RE.match(unit.header or "") or BOILERPLATE_TEXT_RE.search(unit.display_text):
                best_bp = (pos, uid, unit.section_id, unit.header)
                break
        if best_bp:
            pos, uid, sid, hdr = best_bp
            boilerplate_rows.append({
                "package": r["package_id"], "section_id": sid, "header": hdr,
                "fused_rank": pos, "best_single_rank": min(unit_rank[uid].values()),
                "n_queries": len(queries),
            })

    # ------------------------------------------------------------------ report -- #
    print("=" * 78)
    print("V20 DIAGNOSTIC -- does the correct unit rank WORSE under fusion than under")
    print("                  its own best single query?")
    print("=" * 78)
    if not diagnostic_rows:
        print("FAIL: no known-correct target was observed in any replayed round.")
        return 1
    print(f"  target observations: {len(diagnostic_rows)} (n examined = {examined['rounds']} rounds)")
    print()
    print(f"  {'target':<40}{'q':>3}{'best1':>7}{'fused':>7}{'delta':>7}  {'sweep k=1/5/10/60':<20}{'max':>5}")
    harmed = []
    for row in sorted(diagnostic_rows, key=lambda d: (d["target"], d["n_queries"])):
        sweep = "/".join(str(row["sweep"][str(k)]) for k in ks)
        flag = ""
        if row["delta"] is not None and row["delta"] > 0:
            harmed.append(row)
            flag = "  <-- WORSE"
        print(f"  {row['target'][:39]:<40}{row['n_queries']:>3}{row['best_single']:>7}"
              f"{str(row['fused60']):>7}{str(row['delta']):>7}  {sweep:<20}{str(row['max_of_lists']):>5}{flag}")
    print()
    if harmed:
        print(f"  RESULT: fusion demoted the correct unit in {len(harmed)} of {len(diagnostic_rows)} observations.")
        for row in harmed:
            print(f"     {row['target']}: best single query {row['best_query']!r} rank "
                  f"{row['best_single']} -> fused {row['fused60']} (delta +{row['delta']})")
    else:
        print(f"  RESULT: fusion NEVER demoted the correct unit (0 of {len(diagnostic_rows)}).")
        print("  k stays at 60 regardless of the theory -- that was the pre-registered rule.")

    print()
    print("=" * 78)
    print("BOILERPLATE -- how far up the fused list does stock machinery reach?")
    print("=" * 78)
    print(f"  rounds with a boilerplate unit in the fused list: {len(boilerplate_rows)}")
    if boilerplate_rows:
        worst = sorted(boilerplate_rows, key=lambda d: d["fused_rank"])[:6]
        print(f"  {'section_id':<34}{'q':>3}{'fused':>7}{'best1':>7}  header")
        for row in worst:
            print(f"  {row['section_id'][:33]:<34}{row['n_queries']:>3}{row['fused_rank']:>7}"
                  f"{row['best_single_rank']:>7}  {str(row['header'])[:30]}")
        promoted = [r for r in boilerplate_rows if r["fused_rank"] < r["best_single_rank"]]
        print(f"\n  boilerplate PROMOTED by fusion (fused rank better than its best single): "
              f"{len(promoted)}/{len(boilerplate_rows)}")

    print()
    print("=" * 78)
    print("REWRITE IMBALANCE -- how many rewrites did each concept receive?")
    print("=" * 78)
    per_round = Counter(len(r["queries"]) for r in rounds)
    print("  queries per round (each query is one vote in the fused sum):")
    for n in sorted(per_round):
        print(f"     {n} quer{'y' if n == 1 else 'ies'}: {per_round[n]:>3} round(s)")
    print(f"  spread: {min(per_round)} to {max(per_round)} -- a {max(per_round) // max(min(per_round), 1)}x "
          "difference in how heavily a round's concept is weighted, chosen by the model,")
    print("  disclosed nowhere.")
    # Concept clustering within a round, by shared content token. An estimate, and
    # labelled as one -- the alternative is a judgement call presented as a count.
    stop = {"of", "the", "for", "and", "in", "on", "to", "a", "united", "states", "code", "is", "amended"}
    clusters = []
    for r in rounds:
        toks = [set(re.findall(r"[a-z0-9-]+", q.lower())) - stop for q in r["queries"]]
        groups: list[set[str]] = []
        for t in toks:
            for g in groups:
                if g & t:
                    g |= t
                    break
            else:
                groups.append(set(t))
        clusters.append((len(r["queries"]), len(groups)))
    print(f"\n  estimated concepts per round (token-overlap clustering, an ESTIMATE):")
    ratio = Counter(f"{q} queries -> {c} concept(s)" for q, c in clusters)
    for label, n in sorted(ratio.items(), key=lambda x: -x[1])[:8]:
        print(f"     {label:<34} {n:>3} round(s)")

    print()
    print("=" * 78)
    print("V21 AT HIT LEVEL -- contexts of units actually RETURNED by the §17 queries")
    print("=" * 78)
    total = sum(v21_hits.values())
    if not total:
        print("FAIL: zero hits across all replayed rounds.")
        return 1
    labels = {
        (True, True): "operative + quoted  (MIXED)",
        (True, False): "operative only",
        (False, True): "quoted only",
        (False, False): "neither",
    }
    for key in ((True, True), (True, False), (False, True), (False, False)):
        n = v21_hits.get(key, 0)
        print(f"  {labels[key]:<30} {n:>6,}   {100 * n / total:.1f}%")
    mixed = v21_hits.get((True, True), 0)
    print(f"\n  n hits examined: {total:,} across {examined['rounds']} rounds "
          f"({examined['zero_hit_rounds']} returned nothing)")
    print(f"  MIXED: {100 * mixed / total:.1f}% -- "
          f"{'minority: per-hit note applies' if mixed / total < 0.5 else 'majority: tool description'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
