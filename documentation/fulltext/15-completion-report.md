*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

# 16. Completion report — PR 1 — DRAFT SKELETON (2026-08-09)

> **This is the skeleton, not the report.** It is laid out against the spec's own
> enumerations — every V-step by number, every amendment by number, every §16 question by
> name, every defect by F-number — so a gap renders as a blank `[ ]`, never as prose that reads
> complete. Fill each cell **from the record and cite the source**; do not narrate. Per the §16
> rule, the report is written **last**; while any blocker at the end remains open this stays a
> skeleton. Every descriptive claim about runtime behaviour is stamped with the commit or
> measurement it rests on (`00-INDEX`), and the spec author cannot read the source — so numbers
> come from V-steps and reported artifacts, never from familiarity.

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

- **Original runs (pre-fix).** Group A passed in both cells; 13 findings ranked in §18; B1 at
  the floor made zero calls (F7). The safety property is carried by the tool, not the consumer's
  reasoning budget.
- **Re-run — `[ PENDING ]`.** Harness specified (§17, the re-run subsection); Haiku capability
  cell added; preregistration recorded (fixed defects should not reproduce, Group A holds both
  cells). **Not yet executed.** This is a blocker below, not a blank to leave.

## F. Measured profile

- Cold **3.88 s** on a large enrolled bill (V2); **~4.4 s/call**, full re-index every call — no
  cache in PR 1. Client-timeout implication belongs in the README (§12).
- Rate limits independent — indexing cannot starve congress.gov tools (V12).

## G. Stated limitations and boundaries

- `amends` resolves U.S. Code and Public Law only, **never named Acts** (incl. IRC by bare
  section); convenience, not completeness; populated = citations *found*, not *present*.
- `is_amendatory` is verb-only; ~1% amendatory residual uses no recognised verb, retrievable via
  `match_contexts=['quoted']`.
- Committee-struck text excluded and disclosed via `struck_text_note`; recoverable as the prior
  version.
- Header→body operative run-on (`Quorum.A majority`) — 2-instance residual on `join_segments`,
  outside the flatten-site separator ruling.
- Caching, offline, disk cap — **PR 2**; `cache` fields currently inert.

## H. Process notes

- Two HIGH defects were spec errors, faithfully implemented (§3 assumed every version has a
  date → A3; §5 never said where `<preamble>` sits → A4). The credential-free V5/V7/V9/V10 were
  skipped though flagged first, and V5-against-a-real-resolution was the check that would have
  caught the largest bug.
- The header-separator glyph moved `—`→`·` when measurement showed `—` collides with the
  corpus's own em-dash use inside quoted segments — the pinned criterion applied to new evidence,
  not overridden.

---

## Blockers before this skeleton becomes the report (gates, not blanks)

- [ ] **§17 re-run executed and diffed against its preregistration** (§E)
- [ ] **F16** dispositioned — confirm F4's carve-out drops `#2` to zero, then the silent-suffix
  question
- [ ] Cosmetic residuals closed or explicitly deferred: `quotes_seen` populated, `cache`
  `false`→`null`, `S 3548`'s orphaned `" .` origin
- [ ] A final pass confirming no open ruling remains, and every `[ ]` above is filled or
  deliberately marked out-of-scope

---
