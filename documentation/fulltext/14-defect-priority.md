*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

# 18. Prioritized defect list — from §17 and the GovInfo code audit

Everything the adversarial prompt suite and the accompanying source audit surfaced, ranked
by **harm if left unfixed**, not by fix cost. Fix cost and status are annotated separately
so the two are not confused.

**Provenance is marked** because it changes how much weight each item carries: `[E2E]` =
observed live in a §17 run; `[AUDIT]` = found by comparing the spec against GovInfo's
published documentation; `[E2E-]` = observed but with a caveat on the evidence.

**On merge gating.** §17's stated rule is that a **Group A** failure blocks merge. **Group A
passed in both cells**, so *by the stated rule nothing here blocks*. F1 and F2 should block
on ordinary correctness grounds regardless — they are not consumer-behavior findings, they
return wrong content. Do not let a clean Group A be read as a clean bill of health.

---

## P0 — returns the wrong document or asserts something false

### F1. `renr` loses to `enr`; agreed-to resolutions resolve to `ih` `[AUDIT]`

The precedence table covers **17 of GovInfo's 53 published version codes**. Two gaps are
correctness bugs, not coverage gaps:

- **`renr` (re-enrolled) gets precedence 0 and sorts last**, so `enr` wins and the resolver
  returns **superseded text as final**.
- **`ath` / `ats` are absent entirely**, and simple and concurrent resolutions never receive
  `enr` — so **every agreed-to resolution resolves to `ih`**.

Worst failure available: everything downstream is drawn from the wrong document and nothing
in the response says so. §3's invariant (*"if an `enr` version exists… enrolled is terminal
for every bill"*) is wrong on both counts.

**Fix:** complete the table against the published list, **and assign categories, not just
ranks** — administrative codes (`ash`, `sas`, `sc`, `oph`, `ops`), negative terminals
(`fph`, `fps`, `fah`, `lth`, `lts`, `iph`, `ips`, `pav`), and re-issues (`renr`, `reah`,
`res`) cannot be expressed on one linear scale. A failed-passage version is chronologically
last and must never be "latest."
**Status: FIXED 2026-08-06.** 53 codes, each with a category alongside its rank; `renr` 95
beats `enr`; `ath`/`ats` 80. **`NEGATIVE` sorts below even unknown codes** — an unknown code
might be a new authoritative stage, a failed-passage version is known not to be — and
selection of one for want of an alternative is disclosed in `version_resolution_note`. A
completeness test pins all 53 so a future GPO addition fails loudly rather than falling to
precedence 0. Original ranks preserved exactly.

### F2. Trailing period makes the tool assert a falsehood `[E2E]`

`get_bill_section("804")` returns *"No section or chunk matched '804'"* — **while three
sections numbered 804 exist**. `804.` returns the correct `ambiguous_section_id`. Four
independent incognito sessions tripped on this.

A citation is written `§1832`, never `§1832.`; the period is a heading terminator that
leaked into the id namespace.

**Fix:** strip **trailing** periods at id construction, never internal ones. Free today under
§10 (schema version in filename, discard and rebuild); permanent the day PR 2 ships.
**Status: FIXED 2026-08-06.** Stripped at id construction (trailing only, internal
preserved); the resolver **also accepts the period form on input**, which cannot collide
because ids no longer contain one. That second half matters — a model copying `SEC. 804.`
verbatim was the exact input that produced the false "no section matched". Live on the NDAA:
`804`, `804.`, `7223`, `7117` all resolve; zero period-bearing ids remain; ambiguity still
errors rather than guessing.

---

## P1 — silently incomplete or unexamined content

### F3. `amends` can be **partially** populated `[E2E]`

`S:7223.` returns `[2158, 2159(c), 2160]` while its own snippet also amends **§2161**.

A5's recall cost was accepted because a unit losing a cite still flies `is_amendatory: true`.
**That covers empty arrays, not short ones.** A populated array reads as *the* answer, and
nothing distinguishes three-of-three from three-of-four. **Partial population is worse than
empty.** Does not reopen the verb gate; reopens disclosure.
**Status: RULED 2026-08-06 — documentation, no schema change. IMPLEMENTED 2026-08-08 —
`833a570`.** V19 Population B: 9.5% after the en-dash resolution fix, and an upper bound at that.
The tool description no longer stops at "convenience"/what `amends` never resolves (which reads
as a caveat about *empty* arrays); it now states the partial case: **a populated list is not
evidence it is the whole list — nothing distinguishes three-of-three from three-of-four — so
treat it as citations *found*, not citations *present*.** Same edit closes F8.

### F4. No reported version has ever been parsed `[AUDIT]`

GovInfo marks deleted text with `<DELETED>` tags in bill text files. **Struck-in-committee
text is not `operative`, `quoted`, or `header`** — the segment model has no name for it. If
it parses as `operative`, the tool presents text a committee **removed** as text the bill
contains: the amendatory trap at a layer V4 does not cover.

Every fixture and all 18 extended-corpus packages are `enr`, `eh`, or `is`. Struck text
appears in **reported** versions (`rh`, `rs`). **An entire version class is unrepresented** —
which is exactly how the intro-labelling hazard stayed latent at 0-of-53.
**Status: measured and RULED 2026-08-06; implementation open.** The premise was right in
substance, wrong in specifics: no `<DELETED>` element — the DTD uses `changed="deleted"`
(219 instances, 80 packages, 162 on `<section>`) and inline `<deleted-phrase>` (**0 in the
wild**). Present in 38 of 80 reported packages, **zero in enrolled/engrossed/introduced**.

**Severity was worse than "unknown" — it was live.** On `119s4726rs`, 16 of 33 sections are
struck and the parser emits all 33, so **`get_bill_section("1")` resolves uniquely, with no
ambiguity error, to the struck text.** A consumer citing it cites what the bill as reported
does not say.

**IMPLEMENTED 2026-08-06.** `119s4726rs`: 33 → 17 sections, **18 collisions → 0**, and
`get_bill_section("1")` now returns the **substitute**. Five paths enumerated and each
**sabotage-verified individually** — which caught a real gap, since two text-extraction
guards covered each other on every tested shape. `struck_text_note` on all three tools,
naming the count and pointing at the prior version, null when nothing was struck.
`<deleted-phrase>` pinned at zero by corpus assertion, with a failure message naming what
the firing document is for.

**Ruling: exclude and disclose** — never emit a unit from a `changed="deleted"` subtree;
`match_contexts` stays three-valued. Full reasoning in §6, including why a fourth context,
opt-in retrieval, and refusing reported versions were each rejected. Three conditions:
carve-out binds **every** unit-emitting path, disclosure is **active** (the mechanism §17
showed consumers actually read), and `deleted-phrase` gets a corpus assertion pinning it at
zero rather than speculative handling.

### F16. The collision suffix silently masked the substitute pattern `[E2E]`

18 ids on `119s4726rs` carry V8's `#2` suffix because the struck original and the substitute
are two versions of the same section side by side; search ranks `S:9` and `S:9#2` adjacently
and nothing distinguishes them.

**V8 was built for genuine duplicate enums across divisions.** This is a different condition
wearing the same shape, and the handler could not tell them apart — **it succeeded, and in
succeeding it hid that anything had duplicated.** F4's carve-out should drop `#2` from this
cause to zero; confirm it does. Then decide whether a silently-applied disambiguation should
be silent: **a mechanism that quietly resolves an anomaly prevents anyone from learning the
anomaly occurred.**
**Status:** open, downstream of F4. **Cost:** small once F4 lands.

### F5. The TOC hands out ids `get_bill_section` rejects `[E2E]`

`D:C/T:XXXI/ST:B` appears verbatim in a TOC response and returns `section_not_found`.
`node_kind` reports `structural` for containers and leaf sections alike, so a consumer
walking the TOC cannot tell which ids are fetchable. The remediation then names
`get_bill_toc` — the tool that supplied the rejected id.

**Status: FIXED 2026-08-06.** Containers resolve through `get_bill_section`, reusing §5's
subdivided-parent shape — subtree assembled when it fits `max_bytes`, heading plus child
descriptors when it does not.

### F14. TOC ids were reconstructed instead of carried `[FIXED — found while closing F5]`

`_build_toc` rebuilt each id as `ancestor_path + leaf`, valid only while `ancestor_path`
covers every component but the last — **false for byte-split chunks.** It emitted
`D:D/T:XLVII/CHUNK:2` for a unit whose real id is `D:D/T:XLVII/S:4701/CHUNK:2`. **28 ids on
`s1071` referred to nothing**, were rejected by `get_bill_section`, and were absent from
`subtree_bytes` — so they also reported **size 0**. A related short-`ancestor_path`
assumption hid **5 byte-split sections**, including `S:4701`, a real citable section that
exists only as chunks.

Fixed: the id is authoritative; `ancestor_path` supplies headers only. Live across four
bills — NDAA, Consolidated Appropriations 2022, `hres463`, `sres27` — every TOC id and every
search-hit id resolves. **0 rejections.**

> **Blast radius, measured after the fix — and it falsifies half of what was written here
> first.** `compute_subtree_bytes` keys on **real** unit ids and sums over prefixes, so it
> never saw the fabricated ids. `D:D` reports 214,109 bytes and `D:D/T:XLVII` 12,738
> **before and after**, and the title ranking inside Division D is identical rank-for-rank.
> The five hidden sections' chunks carry real ids that prefix-match their ancestors, so
> their bytes were always counted.
>
> **Damage was confined to two things:** fabricated **leaf** nodes looking up an absent key
> and reporting 0 (105 at depth 5, 28 at depth 3), and the **5 byte-split sections those ids
> displaced out of the tree entirely.** `S:4701` and four siblings never appeared in the TOC.
>
> **So C1 consumed correct values and its conclusion stands.** The harm is **completeness of
> the tree, not correctness of the aggregates** — a consumer asking what is in Title XLVII
> would have received an incomplete list at accurate sizes.

#### The principle survives; this is not its instance

*§17 tests consumption, V-steps test production, and neither covers the other* is worth
keeping. **But only one direction of it has been demonstrated.**

- **Production correct, consumption fails — demonstrated.** F6: `match_contexts` was right in
  the response and the floor consumer ignored it. No V-step can see that.
- **Production wrong, consumption passes — still hypothetical.** F14 looked like the
  instance and is not, because its bogus leaves were **additive** rather than corrupting an
  aggregate. Demonstrating it needs a field whose **aggregate** is wrong while a consumer
  reads it happily. No such case has been found.

Recorded as an asymmetry rather than a symmetry, because claiming both halves are shown when
one is would be the same error this entry corrects.


## P2 — the safety margin depends on the reader

### F6. `match_contexts` is passive, and the floor drops it `[E2E]`

Both cells received `['operative','quoted','header']` on the same `§7215` hit. The ceiling
volunteered *"some of the matched language may be text being struck."* **The floor said
nothing.**

The floor's answer is not wrong — the margin is what vanished. **Active disclosures
propagate** (`version_resolution_note` was acted on; `amends` was used by both cells);
**passive fields depend on the reader**, and `match_contexts` is the passive field carrying
this project's load-bearing property.
**Status: RULED 2026-08-06 — per-hit note, on a different condition than specified.** V21 at
hit level: mixed 8.8%, **quoted-only 29.2%**, operative-only 57.9%, neither 4.2% (n=240). The
unit-population proxy had said 46.5% — **wrong by 5×.**

**The note fires on `operative` ∉ `match_contexts`** — quoted-only plus neither, 33.4% of
hits — not on mixing. A hit matching only in quoted material is one where the query matched
**nothing the bill enacts**, it is 3.3× more common than the mixed case, and it is the more
dangerous of the two because a mixed hit still contains an operative anchor. A1's `S:141.` hit
was exactly this shape and passed only because the ceiling model read the field.

### F7. A consumer that never calls the tool cannot be reached `[E2E]`

B1 at the floor made **zero calls** and produced a fabricated bill citation — *"Div. G,
Title II, § 204"* against a division whose titles are LXXI–LXXVII and sections 7001–7999.
The codified `§333(a)(2)` text was right from priors; **the bill-level location, the one
thing these tools uniquely supply, was invented** — and the answer read *more* authoritative
than the correct one.

No response-side change reaches this. **Fix:** the tool description must say that knowing
codified law does not establish where a provision sits **in this bill**.
**Status: FIXED** — `07f3889`.

### F8. The `amends` boundary is discoverable but not disclosed `[E2E]`

The ceiling derived the limitation from first principles — chapter-level amendments,
conforming machinery, non-USC targets — **without ever naming the field whose documented
caveat it was describing.** An independent scorer flagged the same omission. 22 amendatory
hits returned `amends: []` in one (biased) sample.
**Status: RULED 2026-08-06 — tool description, no schema change. IMPLEMENTED 2026-08-08 —
`833a570`, with F3.** V19 Population A: 512 lead-in cases, **8.1% of amendatory units** on the
stable denominator. Four-fifths of empty `amends` is empty **by design** — named Acts, IRC bare
sections, unresolvable targets — so disclosing one minority cause of a majority-deliberate
condition is not warranted. The description edit deliberately **omits** the chapter/title
lead-in cause for that reason: naming one minority cause of a majority-deliberate condition
would misdescribe the field. It carries the F3 partial-population caveat instead.

---

## P3 — cost, legibility, and ergonomics

### F9. Query semantics are undocumented `[E2E]`

Matching is **literal phrase with stemming** — not bag-of-words, not semantic.
`Space Force end strength` returns zero against a bill containing both *"End strengths for
active forces"* and *"Space Force."* §7 assigns expansion to the calling model, which cannot
expand well against semantics nobody stated. **Two independent sessions burned 13 queries**
before collapsing to single common words.
**Status: FIXED** — `07f3889`.

### F10. Zero-hit responses carry no diagnostic `[E2E]`

Zero means *absent* or *not phrased as the document phrases it*, indistinguishable. Return
the actual tokenisation. **Cost:** small.
**Status: FIXED 2026-08-08 — `79fe05a`.** `search_bill_text` returns `query_diagnostics` per
query that matched nothing — `terms` (the FTS5 stems), `absent` (terms not in the index), and a
`verdict`: **`phrasing`** (terms all present, so rephrase) vs **`absent_term`** (a term is
missing, so stop). Null when every query hit, so the field's *presence* means something died.
Diagnosed **per query, not only on all-zero responses** — a dead query inside a successful call
is equally unreadable and shares the code path.

**The tokeniser is FTS5 itself, through a probe table sharing one `FTS_TOKENIZER` constant with
the segment index — not a Python Porter reimplementation.** That shortcut is the trap: sabotage
confirms a reimplementation reports `icebreaker` absent from a bill that contains it — telling
the caller to abandon a word that is there, the worst failure this field can have. Three tests
pin it. Measured on 100 real V20 queries × 20 packages = **1,677 zero-hit pairs, 50.1%
`phrasing` / 49.9% `absent_term`** — the verdict discriminates rather than collapsing; all 841
`phrasing` verdicts checked against stems of separately-assembled rendered text, 0 mislabelled.

> **Method note (fifth instance this thread).** The first checker reported 7 mislabellings that
> were *its own* defect — it compared the stem `heavi` against raw text containing `heavy`. An
> instrument confusing stemmed and unstemmed text is precisely the confusion this diagnostic
> exists to expose: *a measurement of a property is subject to the same failure class as the
> property* (`00-INDEX`). Second one the implementer caught before it reached this document.

### F11. `toc_truncated` cannot signal depth clamping `[E2E]`

The node budget silently clamps requested depth (5→3 on `s1071`, 4/5→2 on `hr2471`), and
`toc_truncated` is `true` whenever more exists below — including when the depth **was**
honored. A consumer must diff request against response to notice; neither cell did. The
field is otherwise meaningful (`hres463` returned `false`).
**Fix:** a distinct field when the requested depth was reduced. **Cost:** small.

**Status: FIXED 2026-08-08 — `a52d54a`, 136 passed.** Added `depth_reduced` (bool) and
`requested_depth`; `toc_truncated`'s meaning left alone, so one flag no longer answers two
questions. The two fields disagree on 3 of 5 `s1071` rows, and that disagreement is the
information that did not exist before:

| bill | depth req | served | `depth_reduced` | `toc_truncated` |
|---|---|---|---|---|
| `s1071` | 1–3 | = | false | true |
| `s1071` | 4, 5 | 3 | true | true |
| `hr2471` | 3, 4, 5 | 2 | true | true |
| `hres463` | 2, 5 | = | false | false |

The 5→3 and 4/5→2 clamps reproduce exactly; `hres463` stays clean on both fields.

**A third degradation was hiding in the same flag.** `_toc_nodes` returned
`node_capped=True` even when depth 1 exceeds the cap — but that case **serves the requested
depth and cuts the node list**, so reusing `node_capped` as `depth_reduced` reports a
reduction that never happened, while the cut list itself was disclosed by nothing at all. Now
separated and stated in `toc_note`. **Both substitutions sabotage-checked:** reusing
`node_capped` fails the depth-1 test; restoring the note's `elif` fails the prose assertion.

The reduction note is also **no longer suppressed when hidden-section advice is present** —
they say different things, and `hidden_note` phrases its remedy in terms of the depth *served*,
so alone it reads as though the request had been honored. See §4.

### F12. Segment joining does not distinguish inline from block `[E2E]`

One cause — segment joining not distinguishing inline from block — in two directions: inline
`<quote>` spans separated by `\n\n` (the **block** separator), fracturing sentences; and
`<quoted-block>` sibling paragraphs joined with a single space by `element_text`, losing their
block boundaries. A consumer rebuilt the subparagraph hierarchy itself and warned the reader it
had done so. §5's rule is right and the implementation had it inverted for both.
**Status: FIXED** — `5a54833`. One join function for `display_text` and `render_segments`;
segments carry an `inline` flag, measured not assumed (`<quote>` inline on 0 of 38,277;
`<quoted-block>` block on 7,535, explicitly inline on 208). Replay impact — **27/30 rounds
exact, 1 differing only in chunk indices, 2 at section level (one section drops out of a
top-8), 0 known-correct targets lost** — not "whitespace-only." Rendering propagates into
ranking through chunk boundaries, now a PR 2 cache-key requirement (§10).

**Correction 2026-08-08 (retracts a reassignment first written here).** The `(2) Annual basis`
→ `(A) In general` sibling break **is** F12's second direction and shipped `\n\n` in `5a54833`
— an observation run confirms it, and both between-segment header boundaries already carry `\n\n`
(header → header 0 adjacencies via `coalesce_segments`; header → body 41,290/41,292). The
genuine remaining run-on is a **third** case: a header → body boundary **inside a flattened
`quoted` block** (`(A) In general At least once each year…`), living in `flatten_quoted`, not at
any segment join — so a join-level separator rule fires on zero of it. Tracked under §6's
relocated header-boundary ruling. **IMPLEMENTED 2026-08-08 (`3c90288`):** structural detection
off `<header>`, 16,479 occurrences / 3,221 units, glyph `·` (the pinned `—` collides with the
corpus's own em-dash usage inside quoted segments — 10,177×); replay via the fresh gate
27 exact / 2 chunk-only / 1 section-level, 0 lost. See §6.

### F13. Chunk `header` — CLOSED, both halves `[E2E]`

**Indexing half: §5 is honored.** 584 chunks across 93 documents — header as display field
574 (permitted), as indexed segment 150, **parent header duplicated 0**. The 21 multi-header
chunk groups are distinct descendant headings, which is legitimate.

**Provenance half: falsified — and the hypothesis was mine.** I proposed that
`CHUNK:3`'s `header: "Chapter 3"` was a heading drawn from inserted text, and called it *"the
quoted carve-out applied to the header field"* and a fifth path for F4's enumeration.
**Measured: 0 of 41,854 header segments and 0 of 15,085 header fields draw from quoted
material.** The `Chapter 3` case reproduces exactly, and its source is
`<header>Chapter 3</header>` with `quoted_ancestor=False` under
`<subsection><enum>(e)</enum>` — **the bill's own subsection heading, naming the chapter that
subsection amends.** Accurate, and permitted by §5 as a breadcrumb.

**Consequences:** F13 closes entirely rather than half. F12 and F13 do **not** merge, so F12
stands alone. And F4's enumeration has five paths, not six.

> **Second wrong call of mine in this project**, after reading the orphaned `" .` as a
> surviving source delimiter. Both were inferences from a single suggestive instance, both
> stated with more confidence than one instance supports, and both were overturned by a
> corpus measurement. The pattern in my own contributions is the same one the conventions
> warn about — recorded rather than quietly corrected.

> **The harness caught three of its own defects before any result reached this document**,
> via planted positives and negatives. The middle one matters most: the shortfall detector
> counted **every** citation and reported **14.1%** against a 10% threshold — measuring
> cross-references, which is **A5's false-positive class reintroduced as a measurement and
> aimed at the very field A5 had just cleaned of it.** It would have driven a schema change
> on a wrong number.
>
> **General rule, now in the conventions: a measurement of a property is subject to the same
> failure class as the implementation of that property.** Plant positives and negatives in
> the detector before trusting the figure.

---

## Not defects — recorded so they are not re-raised

- **~4.4 s per call, full re-index every time.** Caching is PR 2 and unimplemented. The
  **inert `cache` fields reporting `false`** are worth changing to `null` before then: this
  spec's own author read them as a measurement twice.
- **RRF `k=60`.** Challenged on sound theoretical grounds — correlated query rewrites are not
  independent voters — but **no fusion failure has been observed in any trace.** V20
  specified; do not retune before it reports.
- **`rfs` unrecognised.** The `version_resolution_note` fired live and a consumer acted on it.
  The ruling, implementation, and consumer response were all correct; the missing code is
  F1's problem, not a separate defect.

---

## F15. The API key is in INFO logs — and it is one credential, not two `[E2E, confirmed live]`

Full `api_key=…` appears in the congress.gov request URL at INFO level. Recorded in §11 as
pre-existing and out of scope. **Two facts make "out of scope" the wrong resting place:**

1. **§3 states GovInfo and congress.gov use the same key.** So the `X-Api-Key` header
   migration on the new GovInfo client — done, in PR 1 — is undermined by the client beside
   it. **PR 1's own dependency leaks the credential PR 1 uses.** The hardening is not
   partial; it is bypassed.
2. **Trace mode redaction is necessary but not sufficient.** §17 requires
   `CONGRESSMCP_TRACE_DIR` to redact the key at write time. If INFO logs carry it anyway, the
   artifact a user attaches to a bug report still contains a live credential — which is the
   exact scenario the redaction rule was written for.

**Not a request to fix the pre-existing client inside PR 1.** But it belongs on the register
at correctness-class severity for PR A, and **trace-mode redaction should cover log output as
well as trace output**, since they share the same disclosure path.

**Status: FIXED 2026-08-06**, as a `LogRecord` **factory** rather than a filter. The
reasoning is right and worth preserving: a logger filter sees only records made through that
logger, a handler filter only handlers attached at install time, and the property wanted is
*no log record carries the key* — which only a factory delivers across loggers and handlers
configured later. It also catches the real shape: **httpx puts the URL in `record.args`, not
`record.msg`**, so a naive `msg`-only redaction would have passed its test and leaked in
production. **Verified non-vacuously** — the fix was sabotaged and the test failed with the
key visible. Third application of the prove-the-detector-bites discipline, after the
quoted-leak predicate and the subdivision-coverage assertion.

> **Two things to change or confirm.**
>
> **1. Install it unconditionally, not only while `CONGRESSMCP_TRACE_DIR` is set.** The key
> reaches INFO logs regardless of trace mode, and the disclosure path — logs pasted into an
> issue — does not depend on trace mode either. **Gating means the protection is absent
> exactly when nobody is watching.** Redaction can only remove a credential from output;
> there is no scenario in which the key is wanted in a log line, so the gate adds a failure
> mode (protection contingent on an unrelated variable) for no benefit.
>
> **Both actioned, squashed into `1284500`.** Unconditional install **surfaced a live leak
> that four green tests had missed**: httpx logs `request.url` as an `httpx.URL`, not a
> `str`, so the `isinstance(value, str)` guard skipped exactly the argument carrying the
> key and `%s` restored it at emit time. Chaining was already correct and is now pinned — a
> bare factory ignoring `previous` fails a dedicated test while passing every redaction
> test. Live at INFO: `api_key=[REDACTED]`, zero occurrences, call succeeds.

#### What this cost the discipline, and what replaces it

**The earlier sabotage check could not have caught this.** Sabotaging a fix that does not
work still fails the test. Non-vacuity establishes that a test is sensitive to **the fix**;
it says nothing about whether the test exercises the **real input shape** — and a test and
the fix it guards are usually written from the same mental model, so perturbing one never
surfaces an assumption they share. Here both assumed `str`.

**What caught it:** installing unconditionally forced a realistic run, and the log was
**grepped** rather than trusted. The generalized rule is now in `00-INDEX.md`: any test whose
input the author constructs inherits the author's assumptions, and something in the chain
must exercise an input the author did not build. The trimmed-fixture rule, outside the parser.

**Residuals closed 2026-08-06.** Both were real. Error envelopes: `_unexpected` interpolated
the exception and `raise_for_status` embedded the URL — redaction moved to the single
`_error` construction point, covering every path rather than today's known ones. Tracebacks:
`exc_text` alone was insufficient because the server renders through **rich**, which formats
`exc_info` directly — the same test-environment-differs-from-production shape as the
`isinstance(str)` miss, on a different axis. **Stated limit:** a renderer showing locals can
still reach `exc.request.url`; all of this is downstream of the key being a query parameter,
so the surface shrinks and the durable fix remains the separate PR.

**Two more vacuous tests found by sabotage-then-watch-it-pass**, both now in the conventions:
an assertion that cannot fail for non-ASCII secrets (`ensure_ascii` escaping), and an
apparent guarantee that was an **ordering accident** — `logger.exception` mutating exception
args in place before `_error` ran, so the envelope stayed clean with the redaction deleted.

**Third coverage channel identified.** A leaked credential is invisible to both V-steps
(response content) and §17 (consumer behavior). Process side effects — logs, tracebacks,
files, emitted URLs — are a channel nothing tests. Recorded in §11, with two residuals to
confirm before F15 closes: **uncaught tracebacks bypass the logging system entirely**, and
any error path echoing a request URL would put the key in a response rather than a log,
which is strictly worse.

---

## Suggested order — revised 2026-08-06

**~~Next: answer F13's open indexing question~~ — done 2026-08-06: §5 is honored, the
display field is not indexed, parent-header duplication is 0/584. V21's definition is
updated accordingly (project `header` out; report the operative × quoted 2×2).**

**Next: the three corpus measurements — V19, V21, V20 — as one pass.** Since the original `S 4042` finding — five chunks each carrying the header
*"In general"* — it has never been established whether a chunk's inherited header is emitted
as an indexed `header` **segment** or only as a display field. §5 forbids the former.

It goes first because **V21 depends on it.** V21 reports the distribution across all four
`match_contexts` combinations; if headers are duplicated into chunks as segments, `header`
is inflated and the distribution it measures is not the distribution that exists. Answer it
before the scan, not after.

**Then the three corpus measurements together — V19, V21, V20.** One harness, one corpus
pass, and they share the hygiene requirements just recorded (non-zero denominator, identity
not string matching, members pinned individually). Running them now is also when the
`urllib`/403 lesson is cheapest to apply; in a month it is a paragraph nobody rereads.

V19 gates F3 and F8, V21 gates F6, V20 gates the RRF question. **Decisions are the
bottleneck, not implementation** — every one of these is fast to fix and slow to rule, so
measure first and the queue drains quickly afterward.

**Then F12 + F13 together**, as the spec requires — they share a cause (segment joining not
distinguishing inline from block). **F12 fixed `5a54833`; F13 closed separately.**

**Then F11 and F10**, whenever. Both are small, neither blocks anything.

**Already landed:** F9 (query semantics) and F7 (codified-law-is-not-bill-location) shipped
in `07f3889`.

---

## Post-review triage — ultrareview `review/bill-text-core → master`, 2026-08-09

Eight cloud-review findings on the **implementation** core. The spec owner cannot fix source;
this is triage — which touch the spec's contracts (recorded here) versus pure code defects
(routed to the implementation session). Severity as the reviewer graded it.

**Re-adjudicated 2026-08-10 after the review branch was rebuilt.** Final tally: **one
spec-relevant (F17, fixed both in code and contract), three real code nits (fixed), and four
refuted.** Three of the four refutations (`bug_002`, `bug_004`, `bug_008`) are **artifacts of
the review slicing**, not of the software — see the measurement note at the end of this
section. The lesson is on the review side, and it is the same one this directory keeps
relearning: *a reading is only as sound as the tree it was taken against.*

**Bill-text feature, spec-relevant:**

- **F17 — `bug_003` (normal): `version_resolution_note` clobbered by the input-clamp note.**
  `note or version_resolution_note` in `search_bill_text` / `get_bill_section` / `_container_response`
  silently drops the §3 version warning whenever a `max_hits`/`max_bytes` clamp also fires.
  **Recorded and contract-hardened in §4** (one condition, one field; never `or`-substitute — the
  `toc_note`/F11 pattern). This is the important one: a live safety-disclosure loss.
  **Schema ruling (2026-08-10, implementer-routed):** the interim merge stops the loss but leaves
  `version_resolution_note` carrying two kinds of notice, which breaks its presence-as-signal (it
  now fires on clamps too). **Adopt a dedicated `request_note`** for the input clamp, keeping
  `version_resolution_note` version-only — free now, and the reasoning is in §4.

**Bill-text feature, code-only (route to implementation session; no spec change):**

- `bug_006` (nit): `sqlite_supports_fts5()` opens/closes a SQLite connection on every tool call to
  check a compile-time property — `@functools.cache` it (`bill_text/index.py`).
  **FIXED in 950125d.**
- `bug_005` (nit): `python -m congress_api` discards `main()`'s return, so cache-CLI exit codes
  (§10) are lost under `-m` but propagated by the console script — `raise SystemExit(main())`.
  Real and confirmed: `-m` exited 0 on a refusal while the console script exited 1. **FIXED in
  950125d** (both paths return 1 on refusal; `cache info` still 0). This is the only fix here
  that touches a §10 contract observably — the CLI exit code is now consistent across both
  entry points.

**Out of the bill-text feature and out of this directory's authority (relay only):**

- `bug_002` (normal) — **REFUTED 2026-08-10.** *(The 2026-08-09 refutation reached the right
  conclusion for the wrong reason; corrected here.)* The finding claimed the default
  (non-`BILL_TEXT_ONLY`) server path is unstartable because 33 feature files import
  `mcp.server.fastmcp`. **False, and the "33" is a slicing artifact.** Measured `fastmcp`-import
  counts (`git grep -l 'mcp\.server\.fastmcp'`, `*.py`) across the trees:

  | tree | fastmcp imports | `mcp` pin |
  |---|---|---|
  | merge-base `c6428f6` (pre-migration) | **35** | `mcp>=1.26.0` |
  | `0ab182c` (MCP-2 migration) | **0** | `mcp>=2.0.0,<3` |
  | feature branch `950125d` (real) | **0** | `mcp>=2.0.0,<3` |
  | `review/bill-text-core` `7b09ae2` (slice) | **33** | `mcp>=2.0.0,<3` |

  The real branch has **zero** `fastmcp` imports — so my earlier "surviving in test files" reason
  was itself wrong; there are none, anywhere. The reviewer's 33 matches the **review slice**, whose
  overlay froze ~74 out-of-scope files at the pre-migration base. The reviewer read a stale tree and
  reported it accurately — about the slice, not the software. **No action; the default path starts.**
- `bug_004` (nit) — **REFUTED 2026-08-10, same cause.** "`pyproject.toml` still allows
  `mcp>=1.26`" was true only of the *original* slice's frozen `pyproject`; the real branch has
  pinned `mcp>=2.0.0,<3` since the migration (`0ab182c`), and the rebuilt slice now carries the
  correct pin too (table above). No action.
- `bug_008` (normal) — **REFUTED 2026-08-10 on its own premise** (implementer determination,
  relayed). The finding assumed `ctx.error()` is a coroutine in mcp 2.x; `Context.error` is **sync**
  in the installed `mcp` 2.0.0, so calling it without `await` is correct — no coroutine leak.
  Bill-text tools were unaffected regardless (own client). No action.
- `bug_007` (nit): `MCP_TRANSPORT` removed from code but still documented in `README.md:92`
  (repo root, not `documentation/fulltext/`). **FIXED in 950125d** (stale row removed). My
  `16-user-guide.md` never carried transport config, so there was no drift on my side.

**Measurement note — 3 of 8 findings were review-slicing artifacts.** The review branch is built
by overlaying only the in-scope paths onto the branch point, so every out-of-scope file (here ~74)
sits at pre-branch state. A reviewer reading whole files sees that stale content and reports it
faithfully — a true statement about the *slice*, a false one about the *shipped software*. The
rebuilt slices (`7b09ae2`, `d10eccd`) each carry a root `REVIEW-SCOPE.md` naming the staleness and
the in-scope paths, and slice 1 now folds in `pyproject.toml` / `requirements.txt` / `README.md` /
`.gitignore` to remove the most common trigger. That mitigates but does not eliminate the class: it
depends on the reviewer reading the marker. **The clean fix is to review a diff, not a worktree** —
then no out-of-scope file is present to be misread. This is the §16/§17 discipline turned on the
review process itself: *a finding is only as valid as the tree it was measured against; when reader
scope ≠ change scope, the reader will manufacture false positives from the gap.*
