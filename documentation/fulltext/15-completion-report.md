*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

# 16. Completion report — PR 1

> **Status 2026-08-16: complete.** Four items remain open and are named under *Gates* at the end — one owed confirmation (F16), three maintainer requirements calls, and Group F's sourcing gap. **None blocks merge under §17's stated rule** (a Group A failure blocks; Group A passed 16/16 in all four cells). It is laid out against the spec's own enumerations — every V-step by number, every amendment by number, every §16 question by name, every defect by F-number — so a gap renders as a blank `[ ]`, never as prose that reads complete. Every descriptive claim about runtime behaviour is stamped with the commit or measurement it rests on (`00-INDEX`); the spec author cannot read the source, so numbers come from V-steps and reported artifacts, never from familiarity. Figures attributed to the implementation session are marked *(reported)* where they were not independently re-derived here.

---

## PR description — copy from the block below

*(Everything between the rules is written to be pasted into the pull request. The rest of this document is the evidence behind it.)*

---

### Full-text search and retrieval for congressional bills

**What this adds.** Three tools — `search_bill_text`, `get_bill_section`, `get_bill_toc` — that search and read **the actual text of a bill**, with its structure intact (division → title → subtitle → section → subsection), resolving the right version automatically.

**What it buys you that you didn't have.** The existing ~93 tools return metadata *about* bills — sponsors, actions, committee history, summaries, and a link to the text. To answer *"what does this bill actually say about X,"* someone had to open the document; the FY2026 NDAA is 9.36 MB of XML. These tools answer that question directly, in **3.88 s cold** on that same bill.

The part that matters most is not search — it is **not being confidently wrong**. Bills are mostly *amendments to other law*: the text is full of quoted blocks the bill is inserting into, or striking from, the U.S. Code. A plain full-text search over a bill happily returns a hit sitting inside one of those blocks, and reporting it as "what the bill requires" is a wrong answer with **no tell** — it reads exactly like a right one. This is not a rare corner: measured at hit level, **29.2% of matches are quoted-only** (V21) — nearly a third of what a naive search returns is text the bill does not enact.

So every match carries `match_contexts` (`operative` / `quoted` / `header`) and every unit carries `is_amendatory` and `amends`, which is how a consumer tells

> *"the bill requires an inventory of not less than 478 aircraft"* (wrong)

from

> *"the bill amends 10 U.S.C. § 9062(j) to require 478 aircraft in FY2027"* (right).

That distinction is the feature. The same machinery also excludes **committee-struck text** in reported versions — text a committee *removed*, which a naive parse would return as current — and discloses the exclusion rather than hiding it.

**Why the diff is this big.** It is a complete subsystem plus its verification apparatus. The product code is a small fraction:

| Part | Files | Added | Share |
|---|---|---|---|
| **Bill-text feature code** | 8 | 3,467 | 20% |
| Tests + E2E harness | 27 | 7,057 | 42% |
| Spec + decision record | 21 | 5,268 | 31% |
| Shared-layer adoption in existing tools | 44 | 1,170 (−321) | 7% |
| **Total** (111 commits) | **100** | **16,962** (−1,862) | |

The 42% is the point, not overhead: bill XML is adversarial (nested quoted blocks, 330 KB single paragraphs, resolutions with no sections, typos enacted *into* the Code), so the feature is pinned by fixtures, a 20-package corpus, and a four-cell end-to-end suite that tests the **consumer** — whether a model reading these responses draws the right conclusion — not just the code.

**How to review it.** Reading `documentation/fulltext/06-segments-amendatory.md` first is worth ten minutes: the segment model is the load-bearing decision and everything else follows from it. Then, in order of attention:

1. `parser.py` (1,115) — XML → addressable units + segments. The riskiest file; the amendatory/struck-text/chunking logic lives here.
2. `tools.py` (875) — the three tool surfaces and response shapes (spec §4/§9).
3. `client.py` (620) — fetch and version resolution (spec §3); 53 GPO version codes ranked by authority, not date.
4. `index.py` (306) — FTS5 (porter) + RRF fusion, `k=60`.
5. `trace.py` (310) — out-of-band instrumentation used by the E2E suite; off unless `CONGRESSMCP_TRACE_DIR` is set.

`models.py`/`service.py`/`__init__.py` are small. Tests, `runs/`, and the spec files can be skimmed unless a specific claim is in question.

**What's verified.** 21 acceptance steps (V1–V21) run live against real APIs, not fixtures; bill-text suite **166 passed / 1 skipped** *(reported)*. The end-to-end suite ran across four cells — attention floor (Sonnet, crowded context), reasoning ceiling (Opus, fresh), capability floor (Haiku), and an isolated cell where only these three tools are registered so every claim is attributable — **70 prompt runs**, most recent `runs/2026-08-15T033553Z`. The gating group (the amendatory-trap prompts) passed **16/16 across all four cells**, including at the capability floor.

**What's deliberately deferred to PR 2.** Persistent caching, offline mode, and the disk cap. Today every call re-fetches, re-parses, and re-indexes (**~4.4 s**), so client timeouts should allow for it. The `cache` fields in responses are present but inert.

**Blast radius on existing behaviour.** The new tools are additive. The shared-layer changes are mostly mechanical adoption of a parameter guard across 7 routers, with **one visible change**: the `laws` tools previously accepted an inapplicable parameter and silently ignored it; they now reject it with a clear error. That is the documented contract, but it is a behaviour change on a public tool. The `mcp` dependency is pinned `>=2.0.0,<3`.

**One more thing, offered as useful rather than as criticism.** Driving the new tools end-to-end meant driving the existing surface alongside them, so this work doubled as an unplanned audit of it. Anything found is written up in **`documentation/tool-defect-register.md`** — a standing register, kept separate from this feature and **not a prerequisite for this PR**. It is worth a look because it also records what is *working* and worth protecting with regression tests (the validation error envelopes are unusually complete), and because it keeps the findings that turned out to be **wrong**: of eight items raised by one automated review, three were artifacts of the review tool reading a stale worktree, and they are recorded as refuted with the measurement that killed them, so nobody re-raises them next cycle. Nothing in that register is a regression from this PR.

---

*(End of PR description.)*

---

## A. V-step results (V1–V21)

Sourced from `01-status.md`, where each step's full finding and its live-run evidence are recorded.

| Step | Result | Finding / citation |
|---|---|---|
| V1 uslmLink | ✅ | `enr` has `uslmLink`; `is`/`es`/`eh` do not — USLM enrolled-only (settled) |
| V2 measurements | ✅ | NDAA `enr`: 9.36 MB XML, 1397 units, 1133 sections, 3.15 MB text; cold fetch 2.82 / parse 0.51 / index 0.14 / **total 3.88 s** |
| V3 needle | ✅ | icebreaker → Division G (Coast Guard); `eh` 0 hits with `sections_indexed` > 0 |
| V4 amendatory trap | ✅ | `dietary` quoted-only → `match_contexts=['quoted']`, snippet from quoted segment |
| V5 structural floor | ✅ | **PASS 2026-08-08** (`de3149e`; was ❌ real data). `PRE:` 15/15 resolve on input; `RC:`/`U:` reached via constructed docs. History kept (§13) |
| V6 tokenizer | ✅ | `porter unicode61 remove_diacritics 2`; icebreaker/-ing/-s → one stem |
| V7 escaping | ✅ | unit-covered; FTS5 quote-escaping holds — §17 E2 confirmed live at all three cells (no operator error on a quoted phrase) |
| V8 id collision | ✅ | bare `804.` → `ambiguous_section_id`, three qualified matches (`117hr2471enr`) |
| V9 RRF dedupe | ✅ | unit-covered (`01-status.md`: V7/V9/V10 ✅ unit) |
| V10 non-empty rebuild | ✅ | unit-covered (`01-status.md`: V7/V9/V10 ✅ unit) |
| V11 cache | **[ ] PR 2** | not implemented; cache fields inert |
| V12 quota | ✅ | 36,000 GovInfo / 20,000 congress.gov, independent buckets |
| V13 `amends` false-positive | ✅ | shorthand/P.L. 0/30 each; longhand failed → A5 |
| V14 phantom units | ✅ | source-element identity proof; 0 quoted-ancestor emitted |
| V15 P.L. consistency | ✅ | PASS; 0 sections mix explicit + short form; named-Act exclusion holds |
| V16 delimiters | ✅ | absent from source at 0.0%; render unconditionally |
| V17 wire conformance | ✅ | guard landed `586a40f`; D2 cleared — the shared-converter defect does not reach these tools, §9 met on the wire |
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

- **119hr1 RECA-expansion version** — **`enr`** carries it (V3: 5 hits; `eh` returns 0 hits *with* `sections_indexed`=334, which is the ambiguity-resolution case that field exists for). Independently corroborated in the §17 re-run: the ceiling cell located the enacted expansion at HR 1 §100203/§100205 (P.L. 119-21).
- **`uslmLink` exists / any non-enrolled package carries it** — `enr` yes, `is`/`es`/`eh` no (V1); standing consequence for the Bill-DTD-for-all-versions decision if it ever changes upstream
- **Tokenizer behaviour, concretely** — `porter unicode61 remove_diacritics 2` (V6)
- **Self-sufficiency** — the three tools resolve, fetch, and navigate from `congress`+`bill_type`+`number` alone; `CONGRESSMCP_BILL_TEXT_ONLY` makes it enforceable. A design choice the spec never stated
- **Design choices the spec did not cover** — enumerated rather than gestured at, and now complete: A5's verb gate on all three citation forms; the intro-labelling fix (per-child classification); V17's scoping; struck-text **exclude-and-disclose** (F4); the header-separator glyph **`·`**, chosen on evidence after `—` was measured to collide with the corpus's own em-dash use; **RRF k=60 held** after V20 refuted the concern; the `amends` object-with-`kind` shape; **one disclosure condition, one field** (F17's `request_note` split); **matched-pair-only** delimiter stripping with content preferred over display neatness (F18); the error taxonomy's recoverability split — `congress_unavailable` triggers the GovInfo fallback, `bill_not_found` is definitive and does not (F21); **no secret-bearing URL in an error `detail`** (F22); the CLI exit-code contract (refusal → `1` on both entry points, §10); and **decomposition over enumeration** for version codes — a reissue inherits its base's rank rather than earning a table row (§3, specified but unbuilt, see D)

## D. Defect disposition (F1–F28)

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

**F17–F28 — the two post-review rounds (2026-08-09 ultrareview, 2026-08-14 code review).** All nine implementation items are fixed, one commit each; two more were measured to be unreachable and deliberately **not** built.

| F | Disposition | Commit / evidence |
|---|---|---|
| F17 clamp note clobbered `version_resolution_note` | FIXED + schema ruling | `35d676f` merge, then `8167124` — dedicated `request_note`; one condition, one field |
| F18 quote delimiters stripped unpaired | FIXED | `449d38b` — matched-pair only; a trailing apostrophe survives into `segments.text`; 0/18 corpus change (latent) |
| F19 subdivided parent not byte-bounded | FIXED | `e17ee04` — parent's own segments now split; `subtree_bytes` conserved; 0/18 inventory change (latent) |
| F20 fallback dropped digit-suffixed version codes | FIXED (path); ranking **NOT BUILT** | `fd4ac5a` — one shared letter-initial pattern on both enumeration paths, which also blocks a real cross-bill packageId collision. The reissue-ranking follow-on is **dead-defensive**: GovInfo returns **zero** for `ih2`/`pcs2`/`enr2`, so no such code exists (§3) |
| F21 unguarded `response.json()` skipped the GovInfo fallback | FIXED | `5dd3c69` — routed through `make_api_request`; resolves #15 (request-counting + cache restored). Fallback-trigger contract now stated in §3, codes in §9 |
| F22 redirect exhaustion returned a closed 3xx as success | FIXED | `cfd459e` — raises `govinfo_unavailable`; generalized §9 rule: **no secret-bearing URL in an error `detail`** (signed CDN targets, the F15 lesson on a new surface) |
| F23 harness scored an un-exercised run as clean | FIXED | `27be6e4` — interpreter pinned to `sys.executable`, startup import probe, non-aborting per-cell zero-trace check. A Haiku carve-out was considered and **withdrawn** (that cell measures disclosure-*reading*, and Haiku did adopt the tools) |
| F24 six bucket tests un-collectable behind a green baseline | FIXED | `880cb53` — the six were verified dead (removed SaaS-tier architecture) and deleted; the guard's `raise` path is now swept over **every live router branch** (84 cases, ≥40 non-vacuity floor), which also closes #18's missing coverage enforcement; baseline single-sourced (#20) |
| F25 version code read from the dict repr | FIXED | `b464957` — reads `formats[].url` by path. The demonstration: a `note` reading *"supersedes …ih"* resolved the item **to `ih`**, the version it supersedes |
| F26 whitespace-collapse re-implemented at four sites | FIXED | `995d3cf` — one shared `parser.collapse_ws`; the test **pins the source scan**, so a re-implementation fails CI even if it matches that day |
| F27 two error systems on one server | **DECISION NEEDED** | §9's envelope is deliberate, so this is cross-server *consistency*, not drift — a maintainer call, not an implementer's |
| F28 version enumeration capped at 20 | **NOT A DEFECT** (measured) | 500-bill sample (250 each, 118th/119th) maxed at **5** versions — 4× margin; dead-defensive, no change |

**Two entries are worth reading as results in their own right.** F20's ranking machinery and F28's pagination guard were both fully specified and then **not built**, because the measurement said the case cannot occur. Recording *"we checked, it does not exist, do not build it"* is the cheapest thing in this document to lose and the most expensive to rediscover.

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
- **Consumer-side cost, from the §17 re-run** (`2026-08-15T033553Z`): a deep read-through is expensive without a cache — A4 at the ceiling ran **42 `get_bill_section` calls / ~703 KB of tool responses** to enumerate Division G. That is the behaviour PR 2's cache economics decide; it is recorded here as the pre-cache baseline PR 2 has to improve on, not as a defect.
- Corpus scale for the latent-defect checks: **18–20 packages**, 19,234 units; three of the nine fixes (F18, F19, F26) changed **zero** bytes on real data — latent, and caught before they were live.

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
- **The verification apparatus caught its own defects, twice.** The A4 fabrication detector was validated with planted good/bad citations *before* its verdict was trusted — and an earlier version of it counted every citation and reported 14.1% against a 10% threshold, measuring cross-references: the exact false-positive class it was built to check, reintroduced as the measurement. Generalized rule, now a convention: *a measurement of a property is subject to the same failure class as the implementation of that property.* Separately, F23 found that the E2E harness could score a run that exercised nothing as clean.
- **The spec's own author was wrong on the record five times this cycle** — a mocked test fixture cited as an observation (F20), defensive machinery for two cases the data ruled out (F20 ranking, F28), a withdrawn carve-out (F23/Haiku), and a fabrication finding retracted once the instrument's scope was applied to it (§17 F3). Each is recorded in place with the correction rather than quietly edited out. The pattern is worth stating plainly for whoever reads these rulings next: the **verifications** held; the **defect-flags** were where the errors clustered.
- **Review scope is part of review validity.** Three of eight findings in one automated review were artifacts of the review branch presenting stale out-of-scope files — true about the slice, false about the software. Recorded in `../tool-defect-register.md`; the durable fix is to review a diff, not a worktree.

---

## Gates — what is closed, and what is honestly still open

- [x] **§17 re-run executed** — `2026-08-15T033553Z`, build `9224726` (all fixes ancestors), complete four-cell run. **Group A 16/16 PASS (merge gate met)**; fixes confirmed at consumer (F2/D5, F11/C3, segment-`amends`/Group A incl. Haiku, B1-CHUNK, version/E3). Open: Group F verbatim+isolation gap (indicative only); consumer-side D4 caveat gap and `PRE:`/`S:` id leakage (model behavior, not tool defects). See §E. *(F3/ceiling "fabrication" retracted — untraced-sibling, unverifiable.)*
- [ ] **F16** dispositioned — **one measurement, not a defect**: confirm F4's struck-text carve-out drops the `#2` collision suffix to zero on `119s4726rs`, then decide the residual question (*should a silently-applied disambiguation be silent?* — a mechanism that quietly resolves an anomaly prevents anyone from learning the anomaly occurred). Does not block merge on the stated §17 rule; it is an owed confirmation of a fix already shipped.
- [x] **Cosmetic residuals dispositioned.** `quotes_seen` — **resolved by measurement**: it is dead state (initialized, never mutated, never read), so *removal* is correct rather than population; routed as nit #30. `cache` `false`→`null` — **open, PR 2**, and worth doing before then: this spec's own author twice read the inert `false` as a measurement. `S 3548`'s orphaned `" .` — **explained**: not a source delimiter (V16 measured those at 0.0%), a spacing artifact, superseded by the F12/F18 delimiter work.
- [x] **Every `[ ]` above is filled or deliberately marked out-of-scope**, and the two items that remain open are named rather than folded into prose.
- [ ] **Three maintainer requirements calls** — not implementer decisions, not merge blockers, but they should be answered rather than drift: **F27** (does the server converge on one error shape?), **#4** (`bills_tool`'s `version` param — unwired seam to finish, or vestigial to delete? tracked as D12), **#17** (does the pinned-version pre-validation round-trip earn its better error message?).
- [ ] **Group F's verbatim-sourcing gap.** The six questions used were derived by someone who had read this spec, and were not run in the isolated cell — the manifest self-flags them as indicative only. Replace with verbatim questions from naive sources **and** run them in isolation before any Group F finding is recorded as a measurement. This is the one §17 gap the re-run did not close.

---
