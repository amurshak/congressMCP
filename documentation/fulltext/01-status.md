*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## Status — 2026-08-14 (current) — PR 1 in defect burndown

Branch `feature/bill-text-search-index`; spec tip `d75a548`, implementation tip `950125d`.
**The core feature is built and validated; PR 1 is not "done" — it is working down a defect
queue from two code-review rounds.** The dated log below (from 2026-08-03 onward) is the
decision history and stays as-is; this block is the authoritative *current* picture.

**Where the feature stands.** All acceptance V-steps are closed (V4/V5/V12–V16/V18/V20/V21;
V5 **PASS** `de3149e`; V20 **hold k=60**; V21 **F6 ruled**), the §17 adversarial suite ran at
ceiling and floor with **Group A clean in both cells**, Haiku added as a capability-floor cell,
and both PR-1 deliverables exist in draft: `15-completion-report.md` (§16 skeleton, still written
last) and `16-user-guide.md` (§12). Defects F1–F17 are addressed (most fixed and live-verified;
F17's `request_note` split shipped `8167124`). V11 (cache) and the obscure-bill cross-version diff
are **PR 2** by decision.

**The live queue is `14-defect-priority.md` §18 — read it there, not here.** Two reviews landed:
- **ultrareview (2026-08-09/10):** `bug_005/006/007` **fixed** (`950125d`); `bug_002/004/008`
  **refuted** (three were review-slicing artifacts — a reviewer reading a stale overlay tree).
- **code review (2026-08-14, 34 findings):** triaged to **F18–F27** plus routed nits. A fresh
  implementation session has the handoff.

**The real bar for "PR 1 done," in order:**

| # | Gate | State |
|---|---|---|
| 1 | **F20** — fallback version regex drops digit-suffixed codes (`client.py:310`) | **path asymmetry FIXED 2026-08-14** (shared letter-initial pattern; the anchor also blocks the real `5eh`-from-bill-12345 cross-bill collision). Residual (reissue ranking) **ruled in §3 but gated on existence** — **no real digit-suffixed BILLS package has been observed** (GovInfo documents none; the `pcs2` in play was a mocked test). Existence check DONE 2026-08-14: GovInfo returns **zero** for `ih2`/`pcs2`/`enr2` — no digit-suffixed code exists, so the ranking is dead-defensive (**do not build**) and "superseded print can win" was synthetic-only. **F20 disposed** — keep the fix, skip the ranking logic. |
| 2 | **F19 / F21 / F22** — oversize-unit no-split; JSON-guard fallback bypass; redirect-as-success | **F19 FIXED `e17ee04`** (§5 line-90 read contract refined). **F21 FIXED `5dd3c69`** (routed through `make_api_request`; #15 resolved; fallback-trigger contract §3, codes §9; **F28 RESOLVED dead-defensive** — 500-bill sample maxed at 5). **F22 FIXED `cfd459e`** (redirect exhaustion now raises `govinfo_unavailable`; surfaced a §9 contract — error `detail` must strip secret-bearing URL query strings, F15 generalized). **This whole row is now closed.** |
| 3 | **F23 / F24** — §17 harness scores an un-exercised run clean; guard routers ship untested | **F23 FIXED `27be6e4`** (fully ratified; Haiku amendment withdrawn). **F24 FIXED `880cb53`** (six dead SaaS-tier tests deleted; guard `raise` path now swept over all live branches — also addresses #18; #20 single-sourced; surfaced a silent-param-drop bug in the `laws` router, relayed). **Row 3 closed.** *Relayed:* 4 more `core.services` baselined collection errors, same greenwash, out of scope. |
| 4 | **§17 re-run** of affected cells (implementer-scripted CLI, §17) once F23/F24 are in | **DONE `2026-08-15T033553Z`** (build `9224726`, all fixes ancestors, tree clean, F23 guard clean). **Group A 16/16 PASS — merge gate met.** Fixes confirmed at consumer: F2 (D5, no false neg), F11 (C3), segment/`amends`/struck-text (Group A incl. Haiku), B1 CHUNK, version rh/eh (E3). Open (model-behavior, not tool defects): D4 disambiguation-caveat gap, `PRE:`/`S:` id leakage in weaker cells. **Group F still indicative-only** (spec-derived + not isolated) — verbatim gap OPEN. Full record §16/§E. |
| 5 | **F18 / F25 / F26** — quote-pair strip; `str(item)` version regex; whitespace-collapse desync | **F18 FIXED `449d38b`** (matched-pair-only; content-over-doubled-delimiter ruled in §6). **F25 FIXED `b464957`** (reads `formats[].url` by path). **F26 FIXED `995d3cf`** (one shared `collapse_ws`; source scan pinned so it can't drift). **Row 5 closed.** |
| 6 | **§16 completion report finalized** from `15-completion-report.md` | last, after 1–5 |

> **Implementation queue COMPLETE 2026-08-14.** All nine bill-text defects (F18–F26) are fixed and
> committed, one per fix. What remains for "PR 1 done" is **not implementation**: (4) the §17 re-run,
> (6) §16, and the three **maintainer requirements calls** below. The routed code-only nits
> (#12, #16, #18, #22–#34, #13) are housekeeping, non-blocking.

**No past evidence is invalidated** — every §17 run to date was executed in a proper venv
(maintainer-confirmed); F23/F24 are prospective guards, not re-adjudications.

**Requirements calls parked with the maintainer** (implementer must not decide): **#4** bills
`version` seam (unwired or delete?), **F27/#24** whether the server converges on one error shape,
**#17** pinned-version pre-validation round-trip. **Group F** (§17) still has zero verbatim rows.

**§10 gained two contracts on 2026-08-14:** the CLI exit-code contract (refusal → `1` on both
entry points; `info` → `0`) and a PR1→PR2 constraint that PR 2's cache module must own the layout
literals the PR-1 CLI already hardcodes. See `08-cache-storage.md`.

---

## Status — PR 1 landed, live validation run 2026-08-03 *(historical — superseded by the 2026-08-14 block above; kept as decision history)*

Branch `feature/bill-text-search-index`, commit `bb235ac`. Unit suite: 8 passed,
1 skipped. V-steps below run **live against real APIs**, not fixtures.

### Headline

**V4 passes on real data.** The segment model exists to make one specific failure
impossible, and that is now demonstrated rather than argued: quoted-only term `dietary`
→ `match_contexts=['quoted']`, snippet drawn from the quoted segment, and
`get_bill_section` returning "…is amended by striking subsection (u) and inserting the
following: (u) Thrifty food plan…". A reader can tell the bill inserts rather than
enacts.

### Results

| Step | Result | Finding |
|---|---|---|
| V1 uslmLink | ✅ | `enr` has `uslmLink`; **`is`/`es`/`eh` do not.** USLM is an enrolled-only enhancement, never a general path. Bill-DTD-for-all-versions is the only correct choice, not a compromise. |
| V2 measurements | ✅ | NDAA `enr`: sha `6f68c0a1…`, 9.36 MB XML, 1397 units, 1133 sections, 3.15 MB text. Cold: fetch 2.82s / parse 0.51s / index 0.14s / **total 3.88s**. |
| V3 needle | ✅ | NDAA `[icebreaker, polar security cutter]` → 2 hits in **Division G, Titles LXXI/LXXII** (Coast Guard), `ancestor_path` interpretable without a second call. RECA carrier = `enr` (5 hits); `eh` = 0 hits **with `sections_indexed`=334 > 0**. 119hr1 has only `eh` + `enr`. |
| V4 amendatory trap | ✅ | See headline. |
| V5 structural floor | ✅ **PASS 2026-08-08** (was ❌ on real data — kept as history) | Three assertions satisfied; synthetic ids resolve on input (`PRE:` 15/15 live on `hres463`, `RC:`/`U:` via constructed docs). The prior real-data failure — passed on trimmed fixtures, failed on a real resolution — is **why the corpus exists** (§13); kept, not deleted with the mark. See the V5 status block below. |
| V6 tokenizer | ✅ | porter collapses icebreaker/icebreaking/icebreakers → 1 hit each; amend/amended/amending → 50 each. |
| V7 / V9 / V10 | ✅ (unit) | Escaping, RRF dedupe, non-empty rebuild covered. |
| V12 quota | ✅ **isolated** | 3 GovInfo calls left the congress counter unchanged. **36,000 (GovInfo) vs 20,000 (congress)** — independent buckets. Indexing cannot starve congress.gov tools. |

**Merge list closed 2026-08-04.** Six commits on `feature/bill-text-search-index`:
`b370e8d` intro quoted-context fix + corpus infra, `586a40f` V17 wire-conformance guard,
`07cc78c` V5 synthetic resolution + circular TOC advice, `1755c12` **(V8 confirmed closed on
its assertions — §17 D5 shows bare `804.` returning `ambiguous_section_id` with three
qualified matches on `117hr2471enr`)** colliding
subdivision id disambiguation, `b801a4f` keyword-only params. **Five are enumerated
against a count of six, and the `X-Api-Key` freeze-now item appears in neither** —
reconcile before calling the list closed.

Three real defects were found and fixed during the closing pass, each in a shipping
statute and each with a regression guard: the intro mislabel (VAWA, WRDA), the circular
TOC advice, and the §1832 id collision.

**A3 closed at both tiers**, `2626523` (WARNING pinned) and `c729076` (`version_resolution_note`
extended to the partial-unknown case). Nine commits, `b370e8d` → `c729076`; 67 passed, 2
skipped.

**V18 reported and disposed** — quote branch dropped (35/35 non-amendatory), prediction
falsified, invariant measured clean across 19,234 units. `to read as follows` to be added
to `AMENDATORY_RE` only, after enumerating all 18 instances. See §6 and §14.

### Definition of done for PR 1 — in order

> **Superseded 2026-08-14.** This table tracked the *original* PR-1 close-out and its items are
> all done; the current bar for "PR 1 done" is the F18–F27 burndown table in the top block. Kept
> for the item-2 correction note below, which is a recorded process lesson.

§16 is written **last**, not next. It reports results; anything unfinished when it is
written either gets omitted or gets amended in afterwards, and both defeat the point.

| # | Item | State |
|---|---|---|
| 1 | V18 disposition implemented | **done** — `7d93691` |
| 2 | `X-Api-Key` on the new GovInfo client | **done** — landed with the freeze-now pair |
| 3 | Trace mode (`CONGRESSMCP_TRACE_DIR`) | **done** |
| 4 | Self-or-ancestor leak predicate (V14 hardening) | **done** |
| 5 | Trailing-content coverage assertion | **done** — `b370e8d`, 0/571, non-vacuity proven; three coverage questions in §14 |
| 6 | **§17 end-to-end prompt suite — Group A blocks merge regardless of V-step status** | **Group A clean in both cells.** Floor: A1/A2/A3′ pass, A4 marginal. Ceiling: all four pass, A4 outstanding. **The safety property is carried by the tool, not by the consumer's reasoning budget** — the best available result. Findings are navigation ergonomics; see §17 |
| 7 | Group F questions collected from prior research sessions | table empty |
| 8 | §16 completion report | last |

> **Correction on item 2, worth keeping rather than deleting.** It was recorded here as
> "flagged three times, never answered." It had in fact been reported — the same message
> that gave the commit table said *"both freeze-now items"* closed, which covers it. The
> table listed five commits against a stated six; the gap was read as evidence of an open
> item and the prose above it was not re-read. The claim then repeated across several turns.
>
> **This is A3 inverted.** A3 was the spec asserting a code behavior nobody re-read. This
> was the spec asserting an *open item* nobody re-read. Same failure, opposite direction:
> a confident claim about state, carried forward on repetition rather than on a source.
> An enumeration is only a guard if each row is re-checked against the record, not against
> the previous version of the enumeration.

**How §16 should be written.** Structured against this spec's own enumerations — every
V-step **by number**, every amendment **by number**, every §16 question **by name** — so a
gap renders as a blank rather than as an omission. Written as narrative prose it will read
complete whether or not it is. Invariants over impressions, applied to the report format.

**Interface defect confirmed across both cells:** a fully-qualified `section_id` cannot be
constructed from a citation, only retrieved, and `get_bill_toc` cannot supply one on a wide
bill (node budget clamps depth; `toc_truncated` is `true` even when the depth was honored,
so the clamp is undisclosed). Opus at high reasoning made the same three wrong guesses as
Sonnet at low. Reasoning buys nothing when the missing information is not inferable. **V19**
is specified for the related `amends` disclosure question. See §17.

**§17 Group B (ceiling): B1 and B2 pass, B3 invalid.** B1 is the strongest result in the
suite — the model fetched a `CHUNK:` unit carrying `node_kind: chunk` **and**
`match_contexts: ['quoted']`, then cited the enclosing `§ 7201(e)` as *enacting*
`14 U.S.C. § 333(a)(2)`. Rename, `node_kind`, and quoted-labelling all held on one response.
Three new items: strip trailing periods from ids (§5, ruled), `RC:` may be unreachable with
the resolving clause typed `S:1`, and zero-hit searches carry no diagnostic.

**§17 Group E (ceiling): all three pass.** E2 did the boolean itself from `matched_queries`
and volunteered a `match_contexts` caveat unprompted; E3 caught a defective prompt (H.R. 3838
has no enrolled version) and compared `eh` against `s1071enr` with every claim verified
against retrieved text. **New finding: queries match as literal phrases, and the tool
description does not say so** — see §7.

**§17 Group D (ceiling): all five pass, D4 marginal.** D5 **closes the V8 question** — bare
`804.` returns `ambiguous_section_id` listing three qualified matches, exactly as specified.
It also shows the trailing-period defect producing a **false** message: `804` reports "No
section or chunk matched" when three exist. That upgrades the §5 strip ruling from
ergonomics to correctness.

**Group A independently scored** (GPT-5.6 Sol, no tools, no project history): all four pass.
It docked A1 for the same weakness this spec had already recorded — the amendment frame
resting on a single verb while the substance renders as bare bullets — and independently
flagged that the A4 answer never names the `amends` field whose limitation it was
explaining, which supports V19. Scoring covers the **ceiling cell only**; the floor cell's
A4 remains marginal.

**Trace-grounded independent review adds three items:** (a) 22 amendatory hits with
`amends: []` in one biased sample — V19's direction confirmed, measurement still owed;
(b) **`S:7223.` returns a *partially* populated `amends`** (§§2158/2159(c)/2160, missing
2161), which breaks A5's acceptance reasoning — that argument covered empty arrays, not
short ones; (c) the partial-unknown version note **fired live on an unrecognized `rfs`
code** and the consumer acted on it — ruling validated, and `rfs` is missing from §3's
precedence table.

**Precedence-table audit against GovInfo's published list (2026-08-06): 17 of 53 codes
covered, and two gaps are correctness bugs.** `renr` (re-enrolled) sorts **last** and loses
to `enr`, so a re-enrolled bill returns superseded text as final. Simple and concurrent
resolutions have **no terminal code in the table at all** — `ath`/`ats` are absent, so an
agreed-to resolution resolves to `ih`. §3's stated invariant ("if `enr` exists, resolve to
it; enrolled is terminal for every bill") is wrong on both counts. **Check whether
`hres463` has an `ath` version** — §17's B2 answer was drawn from `ih` and flagged that very
uncertainty.

**Also new: no reported version (`rh`/`rs`) has ever been parsed.** Struck-in-committee text
is a fourth thing the segment model does not name, and the whole corpus is `enr`/`eh`/`is`.
See §3.

**RRF k=60 challenged (adversarial review, 2026-08-06).** k=60 comes from fusing independent
retrieval *systems*; here the lists are correlated query *rewrites* over one index. With
50–200-deep candidate lists the contribution spread is only ~4×, so **appearing in one more
list outweighs ranking first in one** — which is the congressional-boilerplate failure. §7
also hands the effective vote count to the calling model, since it decides how many rewrites
each concept gets. **V20 specified; do not retune k before it reports** — no fusion failure
has been observed in any §17 trace.

**§17 Group C (ceiling): all three pass.** New defect — **`get_bill_toc` returns container
ids (`D:C/T:XXXI/ST:B`) that `get_bill_section` rejects**, with nothing in `node_kind`
distinguishing container from leaf, and a remediation that points back at the tool which
supplied the id. See §4. C1 also shows a consumer combining `subtree_byte_length`, `CHUNK`,
and `match_contexts: ['quoted']` to conclude that Title XXXI is large because it *re-enacts
existing law*, not because it makes new policy — the segment model used as an analytical
instrument rather than a safety rail. C2's target had no children and did not test drill-down.

**§17 floor reruns (Sonnet 5 low): B1 FAILS.** Zero tool calls, and a **fabricated bill
citation** — "Div. G, Title II, § 204" against a division whose titles are LXXI–LXXVII and
sections 7001–7999. The codified `§ 333(a)(2)` text is right from priors; the bill-level
location, which is exactly what these tools supply, is invented. A tool-adoption failure that
no response-side change reaches.

**E2's pre-registered measurement answered: the context caveat does not survive at the
floor.** Both cells received `match_contexts: ['operative','quoted','header']` on the same
hit; only the ceiling surfaced it. **Active disclosures propagate (`version_resolution_note`,
`amends`); passive fields depend on the reader** — and `match_contexts` is the passive field
carrying the load-bearing property. **V21** specified to decide whether it needs an active
form.

**§17 adversarial suite complete.** Groups A–E run at the ceiling, A plus B1/D1/E2 at the
floor, Group A independently scored. **Group A passed in both cells — the safety property is
carried by the tool, not by the consumer's reasoning budget.** 13 findings ranked in
`14-defect-priority.md`; two are P0 correctness bugs (`renr`/`ath` precedence, trailing-period
false negative) that should block on ordinary grounds even though the stated Group-A gate is
clean.

**F1, F2, F5 fixed 2026-08-06** (53-code precedence table with categories, trailing-period
strip, container resolution), plus **F14** found while closing F5 — TOC ids reconstructed from
`ancestor_path + leaf`, 28 phantom ids on `s1071`, 5 byte-split sections hidden. **`hres463`
has no `ath` version**, so the §17 check closes: the `ih`-sourced answer was correctly
sourced, and the `ath`/`ats` defect stands on general grounds without this fixture
demonstrating it. **A6** records the `timing` single-field divergence. **F15 fixed** (`1284500`). Installing it unconditionally **surfaced a live leak four green
tests had missed** — httpx logs an `httpx.URL`, not a `str`, so the type guard skipped the
argument carrying the key. **Sabotage-checking could not have caught it**: sabotaging a
broken fix still fails the test. Non-vacuity proves test-fix coupling, not test-reality
coupling — see the generalized rule in `00-INDEX.md`. It also identifies a **third coverage
channel** — process side effects, invisible to both V-steps and §17 — recorded in §11 with
two residuals (uncaught tracebacks; error paths that echo request URLs).

**Failing-test baseline is repo-scope, not feature-scope.** The 16 known failures are
MCP 2.x migration fallout and dead code, pre-existing in the repository and unrelated to
bill text. Enumerated in `tests/KNOWN_FAILURES.md` and clamped by
`tests/check_known_failures.py`, which fails on growth **and** shrinkage. **Out of PR 1 and
PR 2 scope by decision** — tracked as D9 in `../tool-defect-register.md`, with two notes for
whoever picks it up.

**Correction:** F14 did **not** understate `subtree_byte_length`. `compute_subtree_bytes`
keys on real unit ids and sums over prefixes, so container totals were correct before and
after and **C1's conclusion stands**. The damage was fabricated leaf nodes reporting 0 and
5 sections hidden from the tree — completeness, not correctness. The consumption/production
principle survives but only one direction of it is demonstrated; see §18.

**F4 measured and ruled.** No `<DELETED>` element — the DTD uses `changed="deleted"` (219
instances, 162 on `<section>`, 38 of 80 reported packages; **zero outside reported
versions**) and inline `<deleted-phrase>` (0 in the wild). **The hazard was live, not
latent:** on `119s4726rs` the parser emits all 33 sections including 16 struck ones, so
`get_bill_section("1")` returns **struck text with no ambiguity error**. **Ruled and implemented: exclude and disclose**,
`match_contexts` stays three-valued — see §6. `119s4726rs`: 33 → 17 sections, 18 collisions
→ 0, `"1"` returns the substitute. **F16** (the `#2` suffix masking the substitute pattern)
resolves as a consequence.

**Three method findings from the F4 work, now conventions:** an enumeration whose members are
not individually pinned is the assumption it exists to reject; provenance is established by
identity, never by string match; and a scan that errors must not look like a scan that found
nothing — **assert a non-zero denominator**, which applies directly to V19, V20, and V21.

**Oldest open item closed 2026-08-06.** The chunk-header indexing question, open since the
original `S 4042` finding: **§5 is honored** — 584 chunks across 93 documents, header as
display field 574 (permitted), as indexed segment 150, **parent header duplicated 0**. The
21 multi-header chunk groups are distinct descendant headings, which is legitimate. V21's
definition updated as a result: **project `header` out and report the operative × quoted
2×2**, since header participation is size-correlated and would confound the mix.

**F13's provenance half stands** — `CHUNK:3` carrying `header: "Chapter 3"` from inserted
text — with a new cheap question attached: of the 150 chunks with indexed header segments,
how many of those headings sit inside a `<quoted-block>`?

**V20 and hit-level V21 complete (`1efdb56`, 127 passed), replay fidelity 30/30 verified to
bite.** **V20: hold k=60** — fusion demoted the correct unit in 7 of 17 observations by 1–4
ranks, **never lost one**, the k-sweep is nearly flat so k is not the lever, and the predicted
boilerplate failure occurred in 1 of 18 rounds. First measurement here to **refute** a concern
rather than confirm one. Rewrite imbalance survives (1–8 queries per round, 8× vote spread) and
goes in the **tool description**, not into normalization.

**V21: F6 ruled — per-hit note, but on `operative` ∉ `match_contexts`, not on mixing.** Hit
level: mixed **8.8%**, **quoted-only 29.2%**, neither 4.2% — against a unit-population proxy
of 46.5%, **wrong by 5×**. Quoted-only is 3.3× more common than mixed and more dangerous: the
query matched nothing the bill enacts. A1's `S:141.` hit was exactly that shape.

**F3 and F8 ruled — documentation, no schema change** (`dfafacb`, 128 passed). B re-measured
at 9.5% (subtraction would have said 9.1%; 109 units migrated between populations), then **6.9%** after a
third instrument fix. The mechanism recorded here as trailing-provenance was **wrong** — it
was **designator-splitting**, the detector keeping subsection designators the parser drops.
**B was never above the line.** The instability itself is the finding: 10.1% → 9.5% → 6.9%
across three genuine detector defects, against a 10-point threshold. **Pre-registration does
not protect the operationalization.** **A's criterion was
mine and it drifts**: its ratio rose with the numerator unchanged at 512 because unrelated
fixes shrank the denominator. On the stable denominator A is **8.1% of amendatory units**; the
ruling is robust to the choice, which is why it stands unrevised.

**F12 fixed** (`5a54833`, 132 passed). One join function for `display_text` and
`render_segments`; inline-ness measured rather than assumed. **It was not whitespace-only** —
rendering moves chunk boundaries, which moves bm25, which reordered 3 of 30 replayed rounds
(0 targets lost). **New PR 2 requirement:** the cache key must carry a **rendering** version,
not only a schema version, or a stale index serves differently-chunked content under a valid
key (§10). **F12 as shipped is the inline-quote + `<quoted-block>` separator pair**, and its
second direction — the `(2) Annual basis` → `(A) In general` sibling break — shipped `\n\n`. An
observation run (2026-08-08) confirms both between-segment header boundaries already carry `\n\n`.
The *remaining* run-on is a third case — header → body **inside flattened `quoted` blocks**
(`flatten_quoted`) — tracked under §6's relocated header-boundary ruling. **IMPLEMENTED
2026-08-08 (`3c90288`):** structural detection off `<header>`, 16,479 occurrences / 3,221 units,
glyph `·` (not `—`, which collides with the corpus's own em-dash usage inside quoted segments);
replay via the fresh gate 27 exact / 2 chunk-only / 1 section-level, 0 lost. See §6 and §18.

**Gate rewrite reviewed: right in direction, dropped a check that need not have been.** The
replay gate was doing two jobs — fidelity (replay reproduces shipped `search()`) and
regression (answers not lost). Fidelity is inherently version-pinned and does not survive a
code change; regression is durable. **Restore fidelity as `replay == live_search` computed
fresh on both sides**, which never goes stale and is not self-referential. Keep the rewritten
regression assertion and the impact classification as-is.

> **Follow-up 2026-08-08 (F12 report).** The implementer landed the gate rewrite and framed the
> choice as binary — keep the stale "reproduces the trace exactly" assertion (which forbids
> legitimate change and gets deleted the first time it is inconvenient) or drop it and report
> impact as measured. They took the latter, keeping "a known-correct target present in the trace
> must still be found" plus the impact classification. **Accepted as far as it goes** — but it
> omits the third option recorded above: fidelity as `replay == live_search` **computed fresh on
> both sides in the same run**, which is neither the stale pre-F12 trace nor a re-recorded trace
> (self-referential). It tests the replay *machinery* against live ground truth and never goes
> stale. **Still owed**; the regression + impact-classification gate is fine to ship meanwhile.
>
> **DONE 2026-08-08 — `f4b1a40`, and it turned out to be about the harness's own validity.** The
> fresh check compares `replay == live_search` at the shipped k, both computed fresh in one
> process: **30/30.** The sharper framing the implementation surfaced: `rank_map` + `fused_order`
> *reimplement* `search()`'s admission and RRF, and the k-sweep, the max-of-lists control, and
> every fusion diagnostic run on that copy — nothing had verified the copy agreed with `search()`,
> so a drifted copy would characterise a fusion that does not ship while printing a full table of
> plausible ranks. Sabotage: fusing at k=10 fails 1/30 (weak — V20's flat-k finding), **shrinking
> the candidate cap fails 3/30 (the structural drift that matters).** The failure report names the
> **first diverging rank**, not a fixed prefix — found while reading sabotage output, where two
> lines printed identically but diverged at rank 21 (40 results vs 20). *A gate whose failure looks
> like a false positive gets ignored* — the same set-vs-count lesson from V19, on the gate's own
> output. **This closes the fresh-fidelity item; nothing on it remains owed.**

**Header/text boundary ruled** — render it, neutrally, not as GPO's `.—`. V16 set the
precedent: a structural distinction the source makes must survive serialization, which is why
quote delimiters are rendered despite being absent from source at 0.0%.

**Outstanding:** the §17 end-to-end prompt suite (`12-e2e-prompts.md`) — **any Group A
failure blocks merge regardless of V-step status**; V11 (cache — PR 2), V18 (`is_amendatory` quote branch — new; see §14),
and §16's completion report, which is the actual bar for "PR 1 done." **D2 cleared** — the shared-converter
defect does not reach the bill-text tools, structurally or empirically; §9 is met on the
wire. **V14 filed** — both assertions pass on both fixtures by identity proof
and apples-to-apples conservation. **V13 complete** — shorthand/P.L. 0/30 each, quoted-leak 0, longhand
failed and produced A5; A5's recall cost measured and accepted.

**V14 fix landed.** The quoted-block phantom-unit defect — the third HIGH — is fixed. The
carve-out now binds the subdivision path as well as discovery (A4 extended, §5). V14's
remaining role is acceptance: the positive control, the does-not-delete-content assertion,
and the unit/section delta decomposition. Confirm which of those ran, since V14 was
written specifically because a fix can pass the phantom check while failing the rest.

**A5 landed 2026-08-04:** longhand USC citations are verb-gated like the other two forms.
"Longhand is self-anchoring" was empirically false — same family as A3 and A4. One hug
predicate, three resolvers; `is_amendatory` is a strict superset of the gate verb, and
`amends` returns `[]` up front when a unit is not amendatory, so the coherence invariant
holds **by construction** rather than by measurement. Incoherent units 126 → 0 (NDAA),
12 → 0 (hr1). Recall cost 12–14 NDAA units, accepted; bounded recovery deferred in §14b.

**Done 2026-08-04:** V15 (P.L. citation consistency — **PASS**, one denominator
outstanding; §6 decision approved), V16 (delimiter source fidelity — **never present**,
render unconditionally; §6 decision settled).

**V5 status — limbo resolved to one owed observation (2026-08-08).** It is marked ❌ above and
defect #2 is fixed and live-verified with hres463 → 16 units / 15 `PRE:` clauses, which is most
of what V5 asserts. V5 also requires two more things:

1. **`get_bill_toc` degrades sensibly at a non-existent depth — SATISFIED by the F11 work.**
   The F11 table (§18) shows `hres463` requesting depth 5 against a shallow tree and being
   *served* depth 5 with `toc_truncated: false` and `depth_reduced: false` — a deeper-than-exists
   request returning the full tree cleanly, with no error and no false truncation. That is the
   sensible degradation V5 wanted; cite that row.
2. **Synthetic `PRE:`/`RC:` ids resolve through `get_bill_section` — STILL OWED.** The defect-#2
   note covers only that the `PRE:` units are *produced*, not that they *resolve on input*. **The
   one observation that flips V5 to PASS:** `get_bill_section` on a `PRE:` id from `hres463`
   (and, if any exists, an `RC:` id) returns the whereas/resolving-clause text rather than
   `section_not_found`. Hand this to the implementer; it is the last thing between V5 and a
   pass/fail mark.

Do not mark V5 passed until item 2 is observed; do not leave it ❌ once it is.

> **Preregistration for item 2 (2026-08-08, before it runs).** *Expected:* `get_bill_section`
> on a `PRE:` id produced for `hres463` (and an `RC:` id if one exists) returns the corresponding
> whereas / resolving-clause text — synthetic ids are addressable on input, **V5 PASSES**, and
> §5's addressing model needs no change. *Falsifier:* the call returns `section_not_found` or any
> error, establishing that `PRE:`/`RC:` ids are **produced but not resolvable** — a new defect in
> the **F5/F14 family** (an id handed to a consumer that the resolver rejects), which reopens §5's
> addressing contract for synthetic units. Both outcomes are defensible; record the exact id
> tried and the returned text or error. **This is the shape V5 was written to catch** — a fix can
> produce the units (defect #2, verified) while leaving them unaddressable, and only an
> on-input resolution observes the second half.

> **Outcome 2026-08-08 — V5 PASS, the preregistered *expected* result not the falsifier
> (`de3149e`).** All 15 `PRE:` ids from `hres463` resolve on input to their whereas text, **0
> failures** (`sections_indexed: 16` = 15 `PRE:` + 1 `S:1`). Item 1 was re-observed live rather
> than cited: `hres463` at depth 5 → served 5, `depth_reduced: false`, `toc_truncated: false`,
> `toc_note: null`, 16 nodes, 10 search hits. §5's addressing model needs no change; the F5/F14
> family is **not** reopened.
>
> **The prereg's "`RC:` id if one exists" clause earned its place — none exists, anywhere.** All
> 20 packages mint `PRE:` only (n=15, all `hres463`), so a corpus-only pass rests on **one of
> three** synthetic shapes. The zero was confirmed real, not a classifier blind spot: the scan
> classifies through the same `_SYNTHETIC_PREFIXES = {PRE, RC, U}` the resolver uses, so `RC:`/`U:`
> would have been counted had they appeared — the *scan-that-errors-must-not-look-like-one-that-
> found-nothing* discipline (`00-INDEX`), applied to the classifier. Both uncovered branches were
> then reached with constructed documents and both resolve: `RC:` (`<resolving-clause>` →
> *"Resolved, That the House finds as follows."*) and `U:` (undivided body → *"An undivided body
> with no sections at all."*).
>
> **A real coverage gap closed on the way.** `RC:` already had an end-to-end test; `U:` had only
> `node_kind_for("U:1") == "synthetic"`, which exercises the **classifier, not the resolver.**
> Since no corpus package mints a `U:` id, neither the suite nor the corpus could have caught a
> resolver that emits the id and then rejects it — **the exact F5/F14 shape V5 exists to watch.**
> Now covered by a resolver test.

### Defect status (updated after fix round — 11 passed, 1 skipped)

**Fixed and live-verified:** #1 (NDAA `version=None` → `enr` ✓), #2 (hres463 → 16 units,
15 `PRE:` clauses ✓), #3 (0 units over 8 KB, was 330 KB max ✓). New fixture
`hres_preamble_trimmed.xml` captures the real whereas-under-`<preamble>` shape, plus
three regression tests for the shapes the original trimmed fixtures dodged.

**#4 — mitigated, one residual.** The stderr leak was a standalone harness, not the
server; `main.py:83` sets `httpx` → `WARNING` at import via `configure_logging()`, before
any request, which suppresses httpx's INFO-level URL logging for both clients.
`BillTextError.detail` carries only `status_code`, and `govinfo_url` is the public
details page. **Residual:** the key is still a query param, so the mitigation is "not
logged at this level" rather than "cannot be logged." Take the `X-Api-Key` header change
— a global log level is something any future contributor can flip to INFO while
debugging something unrelated, and the failure mode is silent key disclosure. Scope to
the new GovInfo client; the congress.gov client is a separate pre-existing issue.

**Open:** 5b keyword-only params (**do before merge** — positional order freezes into a
breaking change the moment anything depends on it), 5c `/search` fallback (**defer**;
instead make resolution failure say "pass an explicit `version=` to bypass"),
5a `quotes_seen`, 5d `<!ENTITY` guard, 5e unit-level RRF limit.

### A3 — CLOSED, synthetic and live. This block was wrong and is corrected.

**The shipped sort is `(precedence DESC, date DESC, code ASC)` — precedence-primary, as
§3 specified.** A missing date sorts last *within its own tier* and cannot promote
anything across tiers. Null-as-most-recent was the **prior** rule, removed; the docstring
says so explicitly.

> **Correction.** Earlier revisions of this block asserted that null-as-most-recent had
> shipped, and characterized A3 as "correct only while null dates appear on enrolled
> entries." **That fragility belongs to the rejected design, not the implemented one.**
> Precedence-primary makes the null irrelevant rather than special-cased, in either
> position. The claim was carried here unverified and repeated across sessions — the exact
> failure mode this spec exists to prevent, committed by the spec.

**Covering tests, in the tree and green since before the current session:**

| Test | Establishes | Landed |
|---|---|---|
| `test_order_versions_puts_dateless_enrolled_first` | `enr` with `date=""` beats dated earlier versions | `6df4b11` |
| `test_order_versions_precedence_primary_does_not_promote_null_dated_nonterminal` | `ih@null` loses to `eh@dated` — **the discriminating counterexample** | `eb0b1ed` |
| `test_order_versions_all_unknown_codes_fall_back_to_date_primary` | total-unknown degradation | — |

The second is the case that fails against null-as-most-recent, which is what makes it
worth having. **This was never unrun — it was unremarked**, sitting inside an aggregate
pass count without A3 named. That is the real process miss, and it is a different one from
"the test does not exist."

**Live closure (defect-1 repro, end-to-end).** `version=None` on S. 1071/119 resolves to
`enr`, not `eah`. The ordered list the resolver actually saw: `enr, eah, es, is` — all
known, lowercase, ISO dates. The congress.gov contract holds on field shape and code
casing, which is what made this worth credentials; the ordering logic itself was already
proved synthetically.

A fourth test, `test_order_versions_logs_unknown_codes_loudly`, pins the WARNING — an
unknown code loses to a known one regardless of date, sorts last, and logs. **That log is
the condition §3's entire tradeoff rests on**, so it earns a regression guard rather than a
one-time confirmation.

**Partial-unknown gap — characterized, and §3 amended in response.** A new GPO code marking
the newest stage sorts last, so an older version wins: loud in the server log, silent in
the response, since only the all-unknown case emitted a `version_resolution_note`. **That
surfaced the safer case and hid the more dangerous one** — all-unknown falls back to
date-primary and probably lands right, while some-unknown actively demotes the newest
version. §3 now requires the note whenever *any* unrecognized code appears and
`version=None`. Not a defect; a decision that had not been made.

| # | Sev | Defect | Root cause |
|---|---|---|---|
| 1 | **HIGH** | `version=None` on S.1071 resolves to `eah`, not `enr` — the icebreaker query reads the wrong document | congress.gov returns `date: null` for Enrolled Bill entries; date-primary sort buries them. **Spec error** — §3 assumed every version has a date. See amendment A3. |
| 2 | **HIGH** | hres463 indexes as `S:1` only; all 15 `<whereas>` clauses — the entire substance — silently lost. No `PRE:` id ever produced | Parser emits `PRE:` only for whereas that are *direct children* of `resolution-body`/`legis-body`. Real shape nests them under a top-level `<preamble>` that is a **sibling** of `<resolution-body>`. **Spec error** — §5 never specified where `<preamble>` lives. See amendment A4. |
| 3 | MED | 8/1397 NDAA units exceed 8 KB; one `PARA:2` is **330 KB**, zero `\n\n` | Byte fallback splits only on blank lines; a flattened table with no paragraph breaks emits whole. §5's chain has no terminal case. |
| 4 | MED | **API key visible in stderr** | Key passed as a query param; httpx logs full URLs at INFO. Violates §2/§11. Pre-existing for the congress client; new code inherited it. |
| 5a | LOW | `ParsedBill.quotes_seen` initialized, never populated — reports `[]` even when quoted segments exist | Dead diagnostic. Populate it; it is exactly the signal that would have surfaced defect 2 earlier. |
| 5b | LOW | Tool params are positional | §4 mandates `*` before `version`/`max_hits`/`max_bytes`/`depth`. |
| 5c | LOW | No GovInfo `/search` fallback when congress.gov is down | §3 secondary path unimplemented. With congress.gov the sole resolution path, this is a single point of failure. |
| 5d | LOW | `ET.fromstring`, no hardening | Stdlib expat does not fetch external DTDs or expand external entities by default, so XXE risk is low — but **billion-laughs is unguarded**. |
| 5e | LOW | RRF SQL caps at `LIMIT 1000` **segments** | The candidate set is *units*; a very common term truncates before the per-query unit limit applies. Same family as the RRF-depth issue in §7. |

### Third HIGH — quoted-block phantom units. FIXED.

**What it was.** A bill inserting a whole new section produces
`<quoted-block><section><enum>…`. A walk generic over `<section>` turns that into a
**phantom addressable unit for text the bill is inserting, not enacting** — the amendatory
trap at *unit* level, where `match_contexts` cannot help because the unit itself is
spurious. Fixing defect #2 generalized the walk and widened the exposure.

**How it was missed.** §5's A4 mandated the carve-out, but scoped it under *discovery* and
said nothing about the **subdivision** chain — where the defect actually lived. A4 has
been extended to bind every unit-emitting path.

**Status: fixed, revalidated, FILED.** V14 passes both assertions on both fixtures by the
strong method in each case. Absent the carve-out `s1071enr` would have emitted **6,461
phantom units including 282 phantom sections**, so the positive control is real. Phantom
suppression proved by **source-element identity** (1363 and 989 emitted elements, zero
with a quoted ancestor — no string comparison). Quoted-text conservation is
**1.00000 apples-to-apples**; the earlier surplus was tokenization. Re-emission across
subdivision boundaries ruled out on data, so §9's exclusive containment holds. Live V4
queries confirm per-unit context on real searches, 8/8 and 8/8.

### Intro-labeling mislabel — V4-class, confirmed, fix in progress

`extract_intro_segments` hard-coded `Segment("operative", …)` (parser.py:562) with no
per-child classification. A `<quote>` in the matter preceding the first subdivision of an
over-size section was emitted as **operative** — inserted text presented as enacted text.
Independent of the phantom-unit defect and the same correctness class.

**Latent at 0 of 53** subdivided sections across both fixtures: untriggered, not absent.
No existing check could have caught it — a mislabel produces zero quoted words in the
parent unit by construction, so the re-emission probe reads 0 under both the healthy and
the broken case.

**Fixed and validated on live documents.** Each intro child is delegated to
`extract_segments`. Suite 42 passed / 1 skipped. A widened scan — 18 packages, 571
subdivided sections — found the hazard was **live, not latent**: `117hr2471enr` `S:804`
(VAWA) and `116hr133enr` `S:401` (WRDA) each had a quoted span mislabeled operative in a
shipping statute. The identity harness was widened to three call-site categories and reads
1363/989 with 0 leaks, unchanged by the fix. See §14, including two spec-session
predictions about the harness that did not hold.

**The 1397-units-against-1133-sections figure is not evidence either way.** §9 defines
`sections_indexed` as top-level addressable units *including synthetic*, so the 264 delta
is equally consistent with `PRE:`/`RC:`/`U:` units and enumerated non-section blocks.
It motivated the question; it does not support it. V14's third assertion decomposes the
delta so this number stops being cited as a signal.

### V3 validates the ambiguity-resolution mechanism

`eh` returning 0 hits **with `sections_indexed`=334** is exactly the case that field was
added for. Without it, "this version doesn't carry RECA" and "the parser produced
nothing" are the same response. Keep it in every search payload.

### Corrections this run forced into the spec

- §3 stated congress.gov's ceiling as 5,000/hour. **Measured: 20,000.** Corrected.
- §3 hedged that GovInfo indexing might starve congress.gov quota. **Settled: separate
  buckets.** Hedging removed.
- The V1 open question ("does non-enrolled carry `uslmLink`") is **closed: no.**

---
