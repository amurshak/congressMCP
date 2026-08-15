*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

# 16. Completion report — PR 1 — DRAFT SKELETON (2026-08-09)

> **This is the skeleton, not the report.** It is laid out against the spec's own enumerations — every V-step by number, every amendment by number, every §16 question by name, every defect by F-number — so a gap renders as a blank `[ ]`, never as prose that reads complete. Fill each cell **from the record and cite the source**; do not narrate. Per the §16 rule, the report is written **last**; while any blocker at the end remains open this stays a skeleton. Every descriptive claim about runtime behaviour is stamped with the commit or measurement it rests on (`00-INDEX`), and the spec author cannot read the source — so numbers come from V-steps and reported artifacts, never from familiarity.

---

## A. V-step results (V1–V21)

Fill `result` and `finding` from `01-status.md`; this table is largely complete on the record.

| Step | Result | Finding / citation |
|---|---|---|
| V1 uslmLink | ✅ | `enr` has `uslmLink`; `is`/`es`/`eh` do not — USLM enrolled-only (settled) |
| V2 measurements | ✅ | NDAA `enr`: 9.36 MB XML, 1397 units, 1133 sections, 3.15 MB text; cold fetch 2.82 / parse 0.51 / index 0.14 / **total 3.88 s** |
| V3 needle | ✅ | icebreaker → Division G (Coast Guard); `eh` 0 hits with `sections_indexed` > 0 |
| V4 amendatory trap | ✅ | `dietary` quoted-only → `match_contexts=['quoted']`, snippet from quoted segment |
| V5 structural floor | ✅ | **PASS 2026-08-08** (`de3149e`; was ❌ real data). `PRE:` 15/15 resolve on input; `RC:`/`U:` reached via constructed docs. History kept (§13) |
| V6 tokenizer | ✅ | `porter unicode61 remove_diacritics 2`; icebreaker/-ing/-s → one stem |
| V7 escaping | ✅ | [cite from 01-status] |
| V8 id collision | ✅ | bare `804.` → `ambiguous_section_id`, three qualified matches (`117hr2471enr`) |
| V9 RRF dedupe | ✅ | [cite] |
| V10 non-empty rebuild | ✅ | [cite] |
| V11 cache | **[ ] PR 2** | not implemented; cache fields inert |
| V12 quota | ✅ | 36,000 GovInfo / 20,000 congress.gov, independent buckets |
| V13 `amends` false-positive | ✅ | shorthand/P.L. 0/30 each; longhand failed → A5 |
| V14 phantom units | ✅ | source-element identity proof; 0 quoted-ancestor emitted |
| V15 P.L. consistency | ✅ | PASS; 0 sections mix explicit + short form; named-Act exclusion holds |
| V16 delimiters | ✅ | absent from source at 0.0%; render unconditionally |
| V17 wire conformance | ✅ | [cite] |
| V18 `is_amendatory` quote branch | ✅ | dropped; 35/35 such units non-amendatory; verb-only |
| V19 `amends` lead-in | ✅ ruled | Pop A 8.1% (stable denom); Pop B 6.9% — documentation, no schema change |
| V20 RRF k=60 | ✅ | **hold k=60**; the concern was refuted, not confirmed; k-sweep flat |
| V21 `match_contexts` mix | ✅ ruled | hit-level quoted-only 29.2%; per-hit note on `operative` ∉ `match_contexts` |

## B. Amendments (A1–A6)

| # | Spec said | Measured | Changed | Why measurement beat the spec |
|---|---|---|---|---|
| A1 | `amends` longhand-only | hr1 14/293 vs shorthand 373× | two-form | reconciliation bills cite USC shorthand |
| A2 | infer latency from stamps | model is the only harness | `timing` block | self-instrumenting |
| A3 | null-as-most-recent | precedence-primary shipped | `(prec, date, code)` | null irrelevant, not special-cased |
| A4 | quoted carve-out at discovery | phantom units via subdivision | binds every unit-emitting path | scoped-to-discovery missed subdivision |
| A5 | longhand self-anchoring | 411 non-amendment fires | verb-gate all three forms | resolvability ≠ amendatory |
| A6 | split `resolve_ms`/`download_ms` | every PR-1 call cold | ships one `fetch_ms` | split conveys nothing until PR 2 |

## C. §16 questions, by name

- **119hr1 RECA-expansion version** — `[ ]`
- **`uslmLink` exists / any non-enrolled package carries it** — `enr` yes, `is`/`es`/`eh` no (V1); standing consequence for the Bill-DTD-for-all-versions decision if it ever changes upstream
- **Tokenizer behaviour, concretely** — `porter unicode61 remove_diacritics 2` (V6)
- **Self-sufficiency** — the three tools resolve, fetch, and navigate from `congress`+`bill_type`+`number` alone; `CONGRESSMCP_BILL_TEXT_ONLY` makes it enforceable. A design choice the spec never stated
- **Design choices the spec did not cover** — the open-ended one; enumerate rather than gesture: A5, the intro-labelling fix, V17 scoping, struck-text exclude-and-disclose (F4), the header-separator glyph `·` chosen on evidence, RRF k=60 held after V20, `amends` object-with-`kind` shape. `[ ]` complete the list before this section is final

## D. Defect disposition (F1–F16)

| F | Disposition | Commit |
|---|---|---|
| F1 renr/ath precedence | FIXED | 53-code table, categories |
| F2 trailing-period false negative | FIXED | strip trailing, accept period-form input |
| F3 partial `amends` | RULED + IMPLEMENTED | `833a570` (description) |
| F4 struck reported-version text | RULED + IMPLEMENTED | exclude-and-disclose; `119s4726rs` 33→17 |
| F5 TOC hands out unfetchable ids | FIXED | container resolution |
| F6 passive `match_contexts` | RULED | V21 per-hit note |
| F7 codified-law ≠ bill location | FIXED | `07f3889` |
| F8 `amends` boundary undisclosed | RULED + IMPLEMENTED | `833a570` |
| F9 query semantics undocumented | FIXED | `07f3889` |
| F10 zero-hit no diagnostic | FIXED | `79fe05a` — `query_diagnostics` |
| F11 depth-clamp signal | FIXED | `a52d54a` — `depth_reduced`/`requested_depth`/`toc_note` |
| F12 inline/block join | FIXED | `5a54833` |
| F13 chunk header provenance | CLOSED | measured 0/41,854 from quoted |
| F14 reconstructed TOC ids | FIXED | id carried, not rebuilt |
| F15 API key in INFO logs | FIXED | `1284500` — LogRecord factory |
| F16 `#2` suffix masking substitute | disposition `[ ]` | downstream of F4 — confirm `#2`→0 |

## E. §17 — consumer-layer results

### COMPLETE RE-RUN — `2026-08-15T033553Z`, build `9224726`. The authoritative post-fix measurement.

**Integrity — solid.** Build `9224726` is on-branch and **all nine fixes (F18–F26) are confirmed git-ancestors**; `working_tree_clean: true`; `zero_trace_cell_failures: []` (the F23 guard ran and found no all-zero cell). Four cells exactly per §17 design: floor (Sonnet-5, crowded, full surface), ceiling (Opus-5, fresh, full surface), capability (Haiku, Group A only, single-step), isolation (Sonnet-5, `bill_text_only=true`, A–E — the fully-attributable cell). 70 results. Haiku **adopted the tools** (6 traces / 4 prompts), so the withdrawn F23 Haiku-amendment stays moot. The two per-prompt zero-call cases (F3 floor + ceiling) sit in cells with live siblings → consumer findings, not harness faults — the ratified F23 behavior, working.

**Results by group** (scored against pinned criteria; the four invariants applied to every answer):

- **Group A — 16/16 PASS across all four cells. The merge gate is met.** A1 (478-aircraft amendatory trap) passes everywhere and the **ceiling frame now survives past the first sentence** ("conforms paragraph (2) by striking the old 'below 466' trigger") — the first-run weakness, fixed. A2 (struck "96 A-10" text) and A3 (§804 VAWA) show struck-text/`amends` handling reaching the consumer, **Haiku included**. A4: no cell claims false completeness; ceiling is exemplary (reads text not index, enumerates four completeness caveats). **Isolation A4 verified grounded** — 42 `get_bill_section` reads, every distinctive cite present in the trace; the prior-run A4 fabrication concern does not reproduce on the fully-attributable cell.
- **Group B — PASS (B2/isolation marginal).** The **B1 `CHUNK`-as-enumeration defect is fixed in all three cells** (each cites the enclosing `§3111(a)` / "to be codified at 10 U.S.C. § 6141", none invents an enum or leaks `CHUNK:`). B2/isolation marginal: says "PRE:1 notes…" framed as "whereas clauses" — one word short of the pinned fail "*Section* PRE:1 states…".
- **Group C — all PASS.** C3 shows `depth_reduced: false` / `toc_truncated: false` — **the F11 depth disclosure reaching the consumer**. C1/C2 answer from aggregated subtree sizes without full fetches.
- **Group D — 12 PASS, 3 MARGINAL, 0 FAIL.** **D5 confirms the F2 trailing-period / `ambiguous_section_id` fix reached the consumer** — verified: 0 false "no section matched" negatives, all three cells surface the three "section 804"s (Div. W/X/E) via `get_bill_toc` + 4 section fetches. The old false negative is gone. D4 marginal in all three cells: each resolves "H.R. 1" to the 119th and names it but **none volunteers that the bare reference was ambiguous** — a consumer response-shape gap, not a tool defect (grounding note: no tool-side default).
- **Group E — all 9 PASS.** E3 fetches and names both `rh` and `eh`, reporting a real difference — the version-resolution path. **E2's pre-registered behavior recurs exactly**: ceiling surfaces the `housing`→`hous` stemming caveat, floor drops it — "the context caveat does not survive at the floor," the passive-disclosure prediction, confirmed. No FTS5 operator error in any cell.
- **Group F — INDICATIVE ONLY, and this run cannot close its gap.** The manifest self-flags (`group_f_caveat`) that the six questions were **spec-derived, not verbatim from naive sources, and below the count minimum** — they inherit the adversarial bias the rule exists to exclude. On the four invariants: F1/floor marginal (a confident false-negative on enacted law — grounded only in pending S.243, missing the enacted HR 1 §100203 the ceiling found); the rest pass. **F3/ceiling is UNRESOLVABLE, not a fabrication** — see the correction below. **The Group-F-verbatim gap remains open**; replace with naive-source questions AND run them in isolation before any F finding counts.

**Fixes confirmed reaching the consumer:** F2 (D5, all cells, no false negative) · F11 (C3 depth flags) · the segment/`amends`/struck-text model (Group A, all cells incl. Haiku) · B1 `CHUNK`-as-enum (fixed all cells) · version resolution `rh`/`eh` (E3). This is what the re-run was for: the burndown changed consumer behavior, not just the tests.

**Consumer/model findings (not tool defects — no implementation fix applies):** D4 disambiguation-caveat gap (all cells, no tool-side default to disambiguate a bare bill number across Congresses); synthetic-id leakage (`PRE:`/`S:`) into user-facing answers in the weaker/isolated cells on whereas/resolution prompts (B2, C3) while the ceiling stays clean — the "passive fields depend on the reader" pattern; E2's floor caveat-drop (pre-registered).

> **Correction — F3/ceiling is NOT a confirmed fabrication (my analysis error, 2026-08-15).** F3/ceiling answered "I searched for an FY2026 NDAA to check, but the keyword search returned nothing responsive" with an **empty bill-text trace**. I first recorded this as fabricated tool activity. **Retracted:** F3/ceiling ran `bill_text_only=false` (the full ~96-tool surface), and the trace instruments only the three bill-text tools — so an empty bill-text trace is consistent with a real call to an **untraced congress.gov sibling**. This is the trace-scope-integrity limit already stated in this section (a claim can come from an untraced sibling), which I failed to apply to my own read until the maintainer caught it. **Group F was not run in isolation** (isolation = A–E), so there is no fully-attributable F3 to settle it. Disposition: **unverifiable on this instrument; re-run F3 in isolation if it matters.** No confirmed fabrication appears anywhere in the run.
>
> **Isolation re-run of F3 (maintainer, 2026-08-15) — F3 is clean; the ceiling claim stays an unadjudicable outlier.** Run in the `bill_text_only=true` cell (trace scope == tool surface, so zero calls now *means* zero calls): **zero tool calls, and a sane answer** — *"Which bill are you referring to? … I'll need the specific bill … to pull the exact text."* This is the **correct** response: the bill-text tools require a bill identifier (congress/type/number) and F3 names none, so recognizing that and asking — rather than inventing a bill to search — is right, not a gap. Floor did the same. So F3 is invariant-clean in the attributable cell and is **not a defect**. The ceiling's "I searched for an FY2026 NDAA" is now an outlier against three clean references (floor, isolation, and the expected behavior), but the isolation run cannot reach back to adjudicate a *different* model on the *full* surface — it remains unverifiable, neither confirmed-fabrication nor confirmed-honest, and is left there. *(This was the fifth confident negative finding of mine this cycle to fail scrutiny — F20, F28, the F23 Haiku amendment, the Haiku id-echo, and this; my integrity/grounding **verifications** held, my **defect-flags** did not. Weight accordingly.)*

- **Original runs (pre-fix).** Group A passed in both cells; 13 findings ranked in §18; B1 at the floor made zero calls (F7). **Caveat established 2026-08-09:** these ran on Claude Desktop with web access, and some claims were grounded in web artifacts rather than in these tools — so the prior findings are **not fully attributable** to the tools, and some passes may have been web-propped. Treat them as a cross-reference, not a clean baseline.
- **Re-run — first run executed `2026-08-09T062714Z`, build `9e119f9`; PARTIAL.** Floor (`claude-sonnet-5`) + ceiling (`claude-opus-5`), Groups A–F, 48 results, 0 harness failures, all `cold_cwd` temp, built-ins off. **Valid cold run, but NOT fully attributable:** both cells ran the full ~96-op congress surface with only the three bill-text tools instrumented, so a claim can come from an untraced sibling tool. Per-claim salvage confirmed for A1/A2/A3 (pinned claims present in the bill-text trace); A4 (fabrication check) cannot be audited until the trace is complete. **Owed: the isolation cell (`bill_text_only=true`)** — the only fully-attributable configuration (§17 surface correction) — before recording "the tool carried the property" or any fabrication verdict. Group F is DERIVED, not verbatim (manifest `group_f_caveat`), so it is weak evidence. Preregistration asymmetry stands: a prior pass the re-run fails is a trace-inspection trigger, not an automatic regression.
- **Isolation cell executed `2026-08-09T154646Z`, build `2ec66c5`; Group A, fully attributable.** `bill_text_only=1`, `claude-sonnet-5`, fresh; A1–A4. **Instrument certified:** every trace call is one of the three tools (get_bill_section 37 / get_bill_toc 5 / search_bill_text 4), all `cold_cwd` temp, 0 harness failures — trace scope == tool surface. **A1/A2/A3 tool-attributable** (load-bearing claims in the trace). **A4:** the model bypassed the `amends` field (which the tools populated richly — 95 distinct targets in-trace) and did a 31-section read-through, then claimed the list is *"complete for Division G"* — which touches the pinned FAIL condition ("presents the list as complete") on a path the criterion did not anticipate (its own read-through, not `amends`).
  - **A4 fabrication audit — DONE, PASSES (2026-08-09).** Detector validated first (6 planted-good cites resolve via structured `amends`; 5 planted-bad come back unsupported — it bites). On the real answer: **93 distinct (title, section) cites parsed, 0 with no support anywhere in the trace** — 25 via structured `amends`, 68 via phrase-level "section N of title T … is amended" co-occurrence. The two citations the **prior** run fabricated — `14 U.S.C. 502` and `46 U.S.C. 4701` — are both **genuinely trace-grounded here** (rec 11: *"chapter 5 of title 14 … is amended— in section 502"*; rec 20: *"Chapter 47 of title 46 … is amended— in section 4701"*), as are the collision-zone `46 U.S.C. 7315/7116`. **No fabrications found** — a real improvement over the prior run, attributable to the fix round, on a fully-attributable instrument. *Residuals:* ~62 of the 68 co-occurrence-supported cites were not individually eyeballed (the 6 highest-risk were, all genuine); the audit checks target existence, not correct subsection/action.
  - **Capability floor (Haiku, `2026-08-09T172014Z`): PASSES the criterion — errs safe.** `claude-haiku-4-5`, single-step variant, **2 calls** (can't afford the ceiling's 31), so it relied on the tool and answered: *"No, this likely isn't all of them"* — citing the F3/F8 convenience caveat **by name** and independently catching the `max_hits=50` truncation. This confirms the hypothesis: A4's intended over-trust test fires at the capability floor, and the disclosure holds at the **weakest tier** (the strongest form of the result — no reasoning required). *Caveats:* the cell ran `bill_text_only=false` (full surface, **not** fully attributable), so the *criterion* PASS is solid (content-based) but the section list's accuracy is uncertified; and the single-step prompt pre-directed the search. n=1.
  - **Disposition DEFERRED to PR2 (decision 2026-08-09).** The "did more work than I wanted" concern — the 31-call read-through and the completeness over-claim — is **cost-contingent**: it only matters if the calls are expensive. PR1 has no cache (~4.4 s/call; A4 ceiling ran 408 s), so over-work is costly *now*; **PR2 caching sets the real per-call cost, and if cached calls are cheap the read-through is fine — arguably the right behavior (verify rather than trust an incomplete `amends`).** So the A4-criterion rework / re-scope-to-floor question waits until PR2 measures that cost. **What does not defer:** the fabrication audit passed on a fully-attributable instrument, and the F3/F8 tool-description property held — the model understood `amends` might be incomplete, which is *why* it verified. **A4 removed as a merge blocker; it is a PR2 open question.**

## F. Measured profile

- Cold **3.88 s** on a large enrolled bill (V2); **~4.4 s/call**, full re-index every call — no cache in PR 1. Client-timeout implication belongs in the README (§12).
- Rate limits independent — indexing cannot starve congress.gov tools (V12).

## G. Stated limitations and boundaries

- `amends` resolves U.S. Code and Public Law only, **never named Acts** (incl. IRC by bare section); convenience, not completeness; populated = citations *found*, not *present*.
- `is_amendatory` is verb-only; ~1% amendatory residual uses no recognised verb, retrievable via `match_contexts=['quoted']`.
- Committee-struck text excluded and disclosed via `struck_text_note`; recoverable as the prior version.
- Header→body operative run-on (`Quorum.A majority`) — 2-instance residual on `join_segments`, outside the flatten-site separator ruling.
- Caching, offline, disk cap — **PR 2**; `cache` fields currently inert.
- **Retrieval, not analysis.** The tools return per-version text and `amends`; *version-difference* and *"what changed and why it matters"* are the consumer's to compute, drawn from priors — so a convincing answer on a famous bill (119hr1) can be prior-driven, not tool-driven. No version-diff capability, by design (§17 Group F; settled: no amendment-direction inference).

## H. Process notes

- Two HIGH defects were spec errors, faithfully implemented (§3 assumed every version has a date → A3; §5 never said where `<preamble>` sits → A4). The credential-free V5/V7/V9/V10 were skipped though flagged first, and V5-against-a-real-resolution was the check that would have caught the largest bug.
- The header-separator glyph moved `—`→`·` when measurement showed `—` collides with the corpus's own em-dash use inside quoted segments — the pinned criterion applied to new evidence, not overridden.

---

## Blockers before this skeleton becomes the report (gates, not blanks)

- [x] **§17 re-run executed** — `2026-08-15T033553Z`, build `9224726` (all fixes ancestors), complete four-cell run. **Group A 16/16 PASS (merge gate met)**; fixes confirmed at consumer (F2/D5, F11/C3, segment-`amends`/Group A incl. Haiku, B1-CHUNK, version/E3). Open: Group F verbatim+isolation gap (indicative only); consumer-side D4 caveat gap and `PRE:`/`S:` id leakage (model behavior, not tool defects). See §E. *(F3/ceiling "fabrication" retracted — untraced-sibling, unverifiable.)*
- [ ] **F16** dispositioned — confirm F4's carve-out drops `#2` to zero, then the silent-suffix question
- [ ] Cosmetic residuals closed or explicitly deferred: `quotes_seen` populated, `cache` `false`→`null`, `S 3548`'s orphaned `" .` origin
- [ ] A final pass confirming no open ruling remains, and every `[ ]` above is filled or deliberately marked out-of-scope

---
