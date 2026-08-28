# congressMCP bill-text spec — index

Implementation spec for a coding agent. Split into per-concern files because the single document exceeded what tooling would load without truncation. **These files are authoritative.** Concatenating them in filename order reproduces the whole spec.

Decisions are settled unless a section says "verify," "HELD," or "outstanding." Where a contract is defined here, follow it exactly rather than improvising.

## Read this first, then the file you need

| File | Contents | Read it when |
|---|---|---|
| `01-status.md` | Current status, defect table, V-step results, priority queue | **Always. Start here.** |
| `02-scope-context.md` | §0 scope, §1 deployment, §2 API key, §15 constraints, §16 completion report | Before starting anything |
| `03-data-sources.md` | §3 GovInfo vs congress.gov, version resolution, rate limits | Touching either upstream |
| `04-tools-responses.md` | §4 tool signatures and input caps, §9 response schemas | Changing any contract |
| `05-parsing-addressing.md` | §5 section ids, structural discovery, subdivision, text extraction | Parser or chunker work |
| `06-segments-amendatory.md` | §6 segment model, `is_amendatory`, `amends`, §8 the amendatory trap | **The load-bearing file** |
| `07-search.md` | §7 FTS5, escaping, RRF fusion | Search behavior |
| `08-cache-storage.md` | §10 cache layout, eviction, recovery — **[PR2]** | PR 2 only |
| `09-safety.md` | §11 XML hardening, secrets, download bounds | Network or parse entry points |
| `10-fixtures-verification.md` | §13 fixtures, §14 V1–V18, extended scan corpus | Writing or running any V-step |
| `11-readme-deliverable.md` | §12 user-facing README requirements | PR 2 |
| `12-e2e-prompts.md` | §17 end-to-end prompt suite — tests the *consumer*, not the code | Before merge |
| `13-deferred-options.md` | §14b deferred and rejected design options, with the evidence | Before reopening a settled call |
| `14-defect-priority.md` | §18 prioritized defect list from §17 and the source audit | **Deciding what to fix next** |
| `15-completion-report.md` | §16 completion report — **DRAFT SKELETON**, structured against the enumerations | Before merge; fill last |
| `16-user-guide.md` | **User-facing** draft — §12 README deliverable plus a usage guide | Publishing docs; PR 2 |

Cross-references in the text use section numbers (§5, §6). The table above maps them.

**Adjacent artifact:** `../tool-defect-register.md` tracks defects in the *pre-existing* tools, found during end-to-end testing of this feature. Not part of this spec, but D2 there carries an open question about whether these tools share a serializer that drops structured fields — which would mean §9 is unmet on the wire regardless of what V1–V16 report.

## Conventions — these bind

**Amendments, not drift.** When implementation diverges from spec intentionally, record it inline as an amendment: what the spec said, what was measured, what changed, why the measurement beat the spec. Four exist — A1 (`amends` two-form), A2 (`timing` block), A3 (version resolution), A4 (structural discovery, since extended in scope), A5 (longhand USC verb gate), A6 (`timing` ships one field), A7 (`timing` env-gated behind `CONGRESSMCP_VERBOSE`, otherwise absent), A8 (F36 parenthetical-trailer extraction; `usc_note` third kind). **Number the next one A9.**

**Verification steps are V1–V22**, defined in `10-fixtures-verification.md`. Refer to them by number. Several are credential-free and that is noted per step.

**Non-vacuity proves test-fix coupling, not test-reality coupling.** Removing a fix and confirming the test fails shows the test is sensitive to *the fix*. It cannot show the test exercises the *real input shape*, because **a test and the fix it guards are usually authored from the same mental model** — perturbing one does not surface an assumption they share.

F15 is the case study: the redaction handled `str`, the test passed a `str`, all four tests were green, and production leaked because httpx logs an `httpx.URL` object. Sabotaging the fix would still have failed the test, so the discipline could not have caught it. What did catch it was **grepping real process output**, and an unrelated decision (install unconditionally) that forced a realistic run.

**This is the trimmed-fixture rule generalized beyond the parser:** *any* test whose input **or environment** the author constructs inherits the author's assumptions. Something in the chain must exercise a condition the author did not build.

Both halves have now bitten in one fix. **Input:** the redaction handled `str`, production passed `httpx.URL`. **Environment:** `exc_text` redaction passed a stdlib test, and the server renders through **rich**, which formats `exc_info` directly and ignores `exc_text`. Same shape, different axis.

**An enumeration whose members are not *individually* pinned is the same assumption the enumeration exists to reject.** Listing the paths a rule binds is necessary and not sufficient. F4's five-path carve-out had two text-extraction guards that **covered each other on every shape tested**, so removing either left the suite green — the enumeration was complete and its verification was not. Finding the shape where each alone is load-bearing is the work. **Second instance of overlapping defenses masking each other**, after F15's `logger.exception` ordering accident; treat it as a standing property of how fixes get written here, not a coincidence.

**For provenance questions, use identity — never string matching.** A corpus detector built on text flagged the *live* section of `119s4726rs`, because a substitute repeats the struck version's wording and the short title is identical in both. **A string is not evidence of provenance.** V14 had already established the alternative — identity instrumentation against the parser's own tree — and the string approach was reached for anyway. This is correlate-as-sufficient appearing on the **test** side; the guard is the same instrument that settled V14's Q1.

**A threshold on a ratio drifts when its denominator is doing other work.** V19's Population A was specified as `N_empty_leadin / N_empty` and rose from 18.6% to 19.4% **with its numerator unchanged**, because an unrelated resolution fix removed 109 non-lead-in empties. Every future improvement pushes it toward the line without the measured phenomenon changing. **Choose a denominator that only moves when the thing being measured moves** — here `N_empty_leadin / N_amendatory`, stable at 8.1%. Check this when setting a threshold, not after a ruling comes within 0.6 points of flipping for reasons unrelated to it.

**Compare sets and inspect the difference — never counts.** A cardinality comparison (`present > reported`) never forces the two sides to be aligned, so a mismatch in **what counts as an element** is invisible by construction. V19's detector kept subsection designators while the parser drops them, so `467f–2(a)/(b)/(c)` read as a **threefold shortfall** on one section amended in three subsections — the most ordinary drafting shape there is. A set comparison surfaces it on the first row.

This is its own family: **the two sides were produced by different pipelines.** Planted positives do not catch it, because a plant tests a shape you already suspect. Third instance in one harness.

**Pre-registration does not protect the operationalization.** It stops a threshold being chosen after the data; it does nothing about the instrument moving underneath it. V19's Population B read 10.1% → 9.5% → 6.9% across three genuine detector fixes, **against a 10-point threshold** — near a line, the ruling would have turned on instrument quality rather than on the phenomenon. **Stabilize the instrument before the number counts:** plants for known failure shapes, set-difference inspection for unknown ones, then report.

**A measurement of a property is subject to the same failure class as the implementation of that property.** V19's shortfall detector counted every citation and reported 14.1% against a 10% threshold — **A5's false-positive class, reintroduced as a measurement and aimed at the field A5 had just cleaned of it.** It would have driven a schema change on a wrong number. The lead-in detector matched `title 10` inside a cross-reference; the header detector compared normalized text against raw `itertext()` and produced false positives shaped exactly like the defect being hunted. **Plant positives and negatives in the detector before trusting its figure** — the harness caught all three that way.

**An instrument below the wire proves nothing about the wire.** F36's acceptance drained every measured set — and the fix still shipped a P0 (F40): the new `usc_note` kind was rejected by the response models, which discard the *entire* response when one metadata entry fails validation. Invisible to every closure artifact, because the set-diff, precision, coherence, and residual instruments all read the parser/DB layer and no acceptance cell called a tool. **A schema-changing fix's acceptance must exercise the schema on the wire: at least one live call per new enum value or field, through every response model that carries it, on both entry points.** The enrolled fixtures had been sha-verified and never once served — verification *of* a fixture is not verification *through* it.

**A scan that errors must not look like a scan that found nothing.** An earlier resolution scan used bare `urllib` and swallowed exceptions; the 403s from a blocked default User-Agent read as *"no resolutions have 2+ versions."* **Assert a non-zero denominator on every corpus measurement** — *0 of 80 examined* and *0 of 0 examined* are different results and currently render identically. This costs one assertion and protects V19, V20, and V21, all of which are corpus scans.

**Two techniques that do reach it, both proven in the same fix:**

- **Test each defense in isolation.** Overlapping mitigations mask each other. `_unexpected` appeared to guarantee a clean envelope, but `logger.exception` mutated the exception's args **in place first** — so the envelope stayed clean with `_error`'s redaction deleted. An ordering accident reads exactly like a guarantee. Reorder the log after the return and it leaks.
- **Assert preconditions about reality, not just outcomes about code.** A precondition assertion failed and revealed that httpx **percent-encodes** the key in the URL, which literal substring redaction sails past. Real keys are alphanumeric so it is a no-op today, but a redaction that silently depends on the shape of the secret is not a redaction.

And watch for assertions that **cannot fail** for a whole input class: `secret not in json.dumps(x)` is vacuously true for any non-ASCII secret, because `ensure_ascii` defaults to `True` and escapes it. That test passed against a fully unredacted envelope.

**Trimmed fixtures cannot validate parser assumptions — only regressions.** They are authored from the same mental model as the parser, so they encode the same assumptions. Any parser-assumption step (V5, V8, V14, and the structural half of V3) must clear **one unmodified live document** before it counts as passed. This is why the largest defect so far shipped with a green test suite.

**Prefer measurement over assertion.** Anything stated from familiarity rather than measurement is marked as needing verification. Three HIGH defects trace to confident spec claims that were wrong — §3 assumed every version carries a date, §5 never said where `<preamble>` sits, §5's quoted carve-out never said it binds the subdivision path, and §6 called the longhand citation form self-anchoring when it is the leakiest of the three.

**Separate what the code *must* do from what the code *does*.** A prescriptive claim stays true until someone decides otherwise. A **descriptive** claim about runtime behavior goes stale silently, because everyone downstream treats it as settled and nobody re-reads the code. A3 is the case study: this spec asserted for months that null-as-most-recent had shipped, when the tree held precedence-primary — the claim was inherited, confident, and wrong, and it was repeated across sessions before anyone opened `order_versions`. Where a file records what the implementation currently does, **stamp it with a date and the symbol read**, and treat the code as the authority when the two disagree.

**Never reconstruct a value you already hold.** A third pattern, distinct from the two below and needing a different guard. `_build_toc` rebuilt section ids as `ancestor_path + leaf` when the id was already in hand — correct for every unit except byte-split chunks, so 28 ids on one bill referred to nothing and reported size 0. The guard is not measurement and not path enumeration; it is a code-review rule: **if the authoritative value is available, carry it.** A derived reconstruction is right until the derivation's assumption breaks, and it breaks silently.

**A structural marker is not evidence of a semantic property.** Distinct from the scoping rule below, and it needs its own guard. A5: a citation form naming its target was treated as evidence the unit amends it — false, 59% of longhand matches. V18: a quotation construct was treated as evidence of amendatory text — false, 35/35 were headings, defined terms, and titles. Both times the real signal was the **verb**. The check is not "which paths does this bind" but **"does the marker occur without the property, and how often"** — a measurement, not an enumeration. Ask it of any field derived from document structure rather than from language.

**A correctness rule binds every path, not the path it was found on.** Four defects have now had this exact shape, and the fourth shows it is not a parser phenomenon: A4 scoped the quoted carve-out to discovery and missed subdivision; A5 scoped the amendatory-verb gate to shorthand citations and missed longhand; the intro-labeling defect scoped per-child segment classification to `extract_segments` and missed `extract_intro_segments`. **And in security code: `client_handler.py` carefully redacts params for its debug log, then five lines later leaks the same credential through an exception path** — the author guarded the channel they were thinking about. When stating a rule, enumerate the paths it binds and check the enumeration is exhaustive. Later instances keep arriving on one specific seam — F32 (amendatory disclosure implemented on the search path, absent from the section path) and F38 (version validation caught by `search_bill_text`, escaping as `internal_error` on `get_bill_section`/`get_bill_toc`) both split exactly along the three-tool surface — so the concrete check for this codebase: a rule implemented in one tool's handler gets checked against the other two by name.

**Coverage is not a KPI.** For `amends` specifically, rising coverage should prompt suspicion rather than satisfaction; V13's false-positive rate is the only metric that governs that field.

## Settled — do not reopen

- GovInfo packages API for content; congress.gov for existence and version metadata.
- Bill DTD XML for all versions. USLM is enrolled-only (`is`/`es`/`eh` lack `uslmLink`) and permanently out of scope.
- Segment model (operative / quoted / header) rather than flattened text — this is what makes the amendatory safety property possible.
- No embeddings; the calling model does query expansion.
- No amendment-direction inference.
- `amends` resolves **U.S. Code and Public Law citations, never named Acts** — including the IRC by bare section number. Precision over recall.
- One SQLite file per package plus a derived manifest; the filesystem is authoritative.
- Cache maintenance via CLI, not MCP tools.
- No new dependencies.
- Rate-limit buckets are independent (36,000 GovInfo / 20,000 congress.gov, same key).
