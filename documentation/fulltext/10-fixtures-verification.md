*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 13. Fixtures

Pin these exactly. Record a SHA-256 of each source document alongside measurements.

| Fixture | Package ID | Why |
|---|---|---|
| **FY2026 NDAA** | `BILLS-119s1071enr` | The NDAA became law via S. 1071 (Pub. L. 119–60, signed 2025-12-18) after passing the Senate as S. 2296 and being introduced in the House as H.R. 3838 — **do not use those numbers for the enrolled text**. Enrolled → frozen forever. ~3,100 pages. Deep `<division>`/`<title>`/`<subtitle>` nesting. Its division structure includes a Coast Guard Authorization division, where Polar Security Cutter provisions live. |
| **119hr1** | resolve `enr` via §3 | Large budget reconciliation. **Heavily amendatory throughout** — quoted-vs-operative density is high everywhere. Contains a RECA expansion (the needle query). No defense content. |
| **119hres463** | resolve via §3 | Small simple resolution. **Structural floor** — `<resolution-body>`, likely no `<section>` elements. |

**On the NDAA:** confirm the enrolled S. 1071 division layout rather than assuming it from the S. 2296 text — vehicles get restructured in conference. If the Polar Security Cutter provisions are not in the enrolled text, search it for `icebreaker` and pin whichever division actually carries them; report what you find.

**Because `enr` is exactly where USLM exists and USLM is out of scope, force the Bill DTD path for this fixture.**

### Trimmed fixtures cannot validate parser assumptions — only regressions

**V5 passed on the committed trimmed fixtures and failed on a real resolution.** That is structural, not bad luck: trimmed fixtures are authored by whoever writes the parser, from the same mental model of the document. They encode the same assumptions the parser encodes, so they can catch a *regression* against an assumption already held but never a *wrong* assumption.

The natural response to a V5-class bug — add a trimmed fixture reproducing it — closes that instance and leaves the general hole open. **Any parser-assumption step (V5, V8, and the structural half of V3) must be run against at least one unmodified live document before it counts as passing.** Trimmed fixtures are for fast regression runs, not for establishing correctness the first time.

### Fixture storage

**Do not commit full NDAA or 119hr1 XML** — many megabytes in the repo's git history; a maintainer will object.

- **Committed:** hand-trimmed XML preserving the structural cases — nested division/title/subtitle, **both** quoting forms, one section large enough to trigger subdivision, one oversized leaf with no structural children (byte-fallback path), a `<toc>` block to confirm exclusion, duplicate enums across divisions, and hres463's `<resolution-body>` whole.
- **Gitignored, and separate from the production cache:** a developer fixture cache for the live acceptance runs. The production cache never retains XML; this one does. They must not share a directory.

### Extended scan corpus — keep it, as a manifest rather than as bytes

Distinct in kind from both the committed trimmed fixtures and the acceptance fixtures. Acceptance fixtures answer *does this document parse correctly*; the extended corpus answers *does this construction occur in the wild, and where*. The intro-labeling defect justified it in one pass: 0 triggers across 53 subdivided sections in the acceptance fixtures, 2 real triggers across 571 in eighteen packages.

**Keep the 18 packages. Commit the definition, not the content.**

- A manifest of `package_id` + version + `sha256`, plus a fetch script. Reproducible, credential-gated, zero repo weight, and consistent with §10 — the cache is disposable and the filesystem is authoritative.
- Bytes stay in the gitignored developer cache alongside the acceptance fixtures.
- Every parser-assumption scan records `package_id` + version + **N**, the way individual runs already carry the two-fixture stamp. A scan that finds nothing is a result: "0 of 571 across 18 packages" is what makes the trailing-content edge a bounded risk rather than an unknown one.

**Record why these eighteen**, so the corpus grows deliberately rather than by accident. The current set spans genuinely different drafting shops — tax (TCJA, IRA), emergency (CARES), appropriations (three), authorization (four NDAAs), infrastructure (IIJA) — and that variety is what surfaced VAWA and WRDA. Additions should widen drafting style, not just add volume. Chamber and vintage are the obvious uncovered axes.
- Live acceptance tests are **opt-in** (env flag or pytest marker), never part of the default unit-test run.

---

---

## 14. Verification

**V1 — DONE.** `uslmLink` present (with `xhtmlLink`, also new relative to GPO's published sample); both `<quote>` and `<quoted-block>` confirmed in real Bill DTD. See the status block. **Remaining sub-check:** fetch a **non-enrolled** package summary (e.g. 119hr1 `ih` or `es`) and report whether `uslmLink` is present there too.

**V2.** *(Partially answered — see the measured profile in §9; fetch is 85–92% of wall clock and the only high-variance term. Confirm across all three fixtures and record the `timing` block verbatim rather than re-deriving it.)* For all three fixtures record: SHA-256, raw XML bytes, unit count, largest single unit, extracted-text bytes, final on-disk index size, **and cold wall-clock broken out as fetch / parse / index / total.** The split matters — index time is tunable, fetch time is not. These numbers go in the README; the latency claim must be measured.

**V3 — needle in haystack.**
- **First determine which version of 119hr1 carries the RECA expansion.** It may have entered via the Senate rather than the House-passed text, in which case `ih` correctly returns zero hits — indistinguishable from a parse failure unless the version is pinned. Search each version; pin the carrier.
- Assert version-specifically: hits in the carrying version; zero hits **with `sections_indexed` > 0** in a non-carrying version. Both required.
- Repeat on `BILLS-119s1071enr` with `["icebreaker", "polar security cutter"]`. Report hit counts, whether `ancestor_path` makes hits interpretable without a second call, and the `match_contexts` distribution.

**V4 — the amendatory regression.** Use 119hr1.
- Find a term appearing **exclusively** inside quoted material. Freeze as a fixture.
- **This is a two-call flow.** `search_bill_text` returns a ~300-char snippet; run `get_bill_section` on the top hit before asserting.
- Assertions: every hit carries `"quoted"` in `match_contexts`; the snippet is drawn from a quoted segment; the `get_bill_section` text includes the surrounding operative verbs. From that payload, a reader must be able to tell the bill is **not** enacting that language.
- A payload permitting the opposite conclusion is a test failure regardless of ranking.

**V5 — structural floor.** *(no credentials needed)* 119hres463: parser produces usable chunks from `<resolution-body>`, search returns real results, synthetic `PRE:`/`RC:` ids resolve through `get_bill_section`, `get_bill_toc` degrades sensibly when the depth does not exist. **`sections_indexed` must be > 0** — synthetic units count. Zero chunks silently returned is a failure.

**PASS 2026-08-08 (`de3149e`).** All four assertions met: 16 usable units from `<resolution-body>`, 10 search hits, `PRE:` 15/15 resolve on input, and TOC non-existent-depth via the F11 `hres463` depth-5 row. `RC:`/`U:` are minted nowhere in the corpus, so both were reached with constructed documents and both resolve — which closed a real `U:` resolver-test gap (F5/F14 shape). Full outcome in `01-status.md`. **Passed on trimmed fixtures long before it passed on a real resolution** — that history is why the extended corpus exists (§13).

**V6 — tokenizer.** *(no credentials needed)* Confirm porter collapses `icebreaker` / `icebreaking` / `icebreakers` to one stem on the real fixtures. If not, say so; the query-expansion story depends on it.

**V7 — escaping.** *(no credentials needed)* Queries containing `"`, `*`, `-`, `^`, `OR`, `NEAR`, and punctuation-only input. None may crash or silently change meaning; punctuation-only must hit the tokenless-query validation error, not FTS.

**V8 — addressing.** *(no credentials needed)* Find or construct a bill with the same section enum in two divisions. Bare-enum lookup must error listing both qualified matches. Test parent-of-subdivided-section on both sides of `max_bytes`, and the byte-fallback `PARA:` path.

**V9 — RRF.** *(no credentials needed)* Confirm a unit ranked outside `max_hits` for every individual query but highly ranked for several can still reach the fused top-N. Confirm duplicate queries do not gain weight.

**V10 — FTS build.** *(no credentials needed — run this first)* Assert non-empty index after build. Deliberately omit `rebuild` in a test and confirm the failure is caught rather than silently returning zero hits.

**V11 — cache [PR2].** Cap at ~20MB, index several bills, confirm LRU fires, files unlinked, disk reclaimed, manifest consistent. Then exercise every recovery row: delete a package DB under the manifest; delete `manifest.db`; truncate it; drop an orphan DB; drop a *newer*-schema DB and confirm it is ignored, not deleted; bump the schema and confirm only older files are swept. Failure injection: kill mid-build and confirm the `.tmp` is cleaned and no partial DB is adopted; two processes building the same package simultaneously; manifest locked; malformed XML; FTS5 unavailable; over-large response.

**V11 — PASS 2026-08-22, 14/14 scenarios, every check green.** Instrument `tests/corpus/v11.py` (`5e2bb22`), offline against the 12 real enrolled corpus bills plus a keyed `--live` S.1071 pass; artifact `runs/v11/2026-08-22T035126Z/` (report.json: 14 scenarios, 0 failing checks, spec-session-read); **offline sweep independently reproduced by the spec session, 13/13.** Highlights: S1 LRU fired 5× over NDAA-scale bills with rows==files after every write; S3a SIGKILL mid-build left a `.tmp` that was never adopted and swept only past 1 h; S3b exactly-one-publisher; S3c a hit waited out `busy_timeout` (5.25 s) rather than failing; S4 live cold 4.3 s → warm 33 ms every-leg-null → pinned 56 ms. **The sweep found one real defect — F34 (§18): the publish race** — check-then-`os.replace` let both concurrent builders "win" (POSIX `os.replace` silently overwrites), fixed `61821b4` with an atomic `os.link` claim; the strict re-run's exactly-one-publisher check now holds. Two harness self-corrections recorded honestly by the implementer: a str-vs-Path marshalling bug, and a planted "newer-schema" file that was a v1 body under a v2 name — the binary trusting **meta over filename** and sweeping it is adoption rule 3 working, not a bug.

**V12 — key reuse and quota isolation.** Confirm the existing congress.gov key is accepted by `api.govinfo.gov`. With that one key, read `X-RateLimit-Limit` and `X-RateLimit-Remaining` from **both** hosts and determine whether GovInfo requests decrement the congress.gov budget. If shared, say so loudly — it changes whether indexing can starve the existing tools and would justify recommending a separate key.

**V13 — `amends` precision. RUN 2026-08-04 — PARTIAL: two forms pass, one fails.** *(no credentials needed if run against cached documents)*.

| Form | Gate | Measure | FP rate |
|---|---|---|---|
| shorthand USC | verb hug | 30 hand-verified, NDAA | **0/30** |
| public law | verb hug | 30 hand-verified, NDAA | **0/30** |
| Statutes-at-Large | verb hug + P.L. dedup | small n; standalone survivors genuine | ~0% |
| **longhand USC** | **none** | 695 NDAA / 32 hr1 matches | **59% / 88% non-amendment** |
| quoted-segment leak, any form | structural, operative-only | full corpus | **0 — as designed** |

**Outcome: A5.** The longhand form is now verb-gated; see §6. The quoted-segment structural guarantee holds at zero leaks, which is the result V4 depends on. The decision-4 P.L. addition is precision-safe.

**The decisive number is not a rate.** 126 NDAA units (21% of those populating `amends`) report targets while `is_amendatory` is false. Only an un-gated form can do that. A rate requires a judgement about what counts as a false positive; an incoherent unit is wrong on the document's own terms. §6 now carries this as a permanent invariant (`amends != [] ⟹ is_amendatory == true`) rather than a one-off finding.

**Recall cost measured 2026-08-04 and accepted — see §6.** 12–14 genuine NDAA units lost to interposed-clause drafting, upper bound near 50 given 30/388 sampling on the no-verb class; 0 on hr1; shared-verb construction 1 occurrence. Invariant confirmed live: incoherent units 126 → 0 (NDAA), 12 → 0 (hr1). The bounded-hug recovery is deferred in §14b with its precision trap documented.

**Why the measurement was required, for the record.** The 59% headline was the complement of the verb-hug rate, so it was produced by the gate under evaluation rather than independently of it. The gate's direction was never in doubt — `has the meaning given`, `Subject to`, `as defined in`, `notwithstanding` are unambiguous — but its cost was unknown, and "minor recall cost" is the same shape of claim as "longhand is self-anchoring." Both are now measured. Keep this pattern: a gate's headline number should not be computed by the gate.

**Regression assertions for A5:** definitional, `subject to`, and `notwithstanding` cites no longer populate `amends`; the four §6 examples specifically; and the structural invariant above asserted across the whole corpus, not a sample.

**V14 — quoted-block phantom units. FIXED AND REVALIDATED 2026-08-04 — PASS on both fixtures.** *(no credentials needed if run against cached documents)*.

| | `s1071enr` @ `enr` | `hr3838eh` @ `eh` |
|---|---|---|
| would-be phantom units suppressed | **6,461** (282 sections) | **2,528** (91 sections) |
| enums appearing only inside quoted material | 244 | 75 |
| emitted ids leaking such an enum | **0** | **0** |
| real `<section>` vs parser section-groups | 1133 = 1133 | 888 = 888 |
| source→unit quoted-word ratio | 1.0025 | 1.0102 |

**Both assertions pass.** The harness builds its **own parent map from raw XML** rather than reusing the parser traversal, so a carve-out leak surfaces as a divergence instead of being masked by the bug under test — this is the right shape for the positive control and it is satisfied: the corpus demonstrably contains the phantom-producing structures at scale. Exact corroboration on real-section counts on both fixtures.

**The magnitude is the finding.** Without the carve-out, `s1071enr` alone would emit 6,461 phantom addressable units, 282 of them phantom *sections* — inserted statutory text the bill quotes rather than enacts. That is the unit-level amendatory trap, and it is closed.

#### Both methodology points closed — V14 filed

**Q1, source-element identity — proof, not inference.** The parser was instrumented by patching `ET.fromstring` and wrapping the unit-level `extract_segments` / `extract_intro_segments` calls (the recursive self-call is distinguishable by a third positional argument), recording exactly which elements become units, **keyed by object identity in the parser's own tree**. Then: no element with a `<quote>`/`<quoted-block>` ancestor may be in that set.

| | emitted source elements | with a quoted ancestor |
|---|---|---|
| `s1071enr` @ `enr` | 1363 | **0** |
| `hr3838eh` @ `eh` | 989 | **0** |

No string comparison anywhere, so the id-collision weakness of the parent-map approach does not apply.

> **Coverage boundary, worth stating so a later reader does not over-read it.** This method proves the property for **element-derived units**. `CHUNK` units and synthetic (`PRE:`/`RC:`/`U:`) units are not element-derived and are outside its scope — they are covered instead by the conservation measure and the live V4 run below. The three checks together are complete; none is complete alone.

**Q2, the surplus — tokenization, not re-emission.** Two measurements:

1. **Apples-to-apples.** Counting the source side through `element_text` — the same flatten the emitter applies — gives **0.99998** (3 words in 176k) and **1.00000**. The earlier 1.0025/1.0102 was raw `itertext` versus normalized tokenization. Benign.
2. **Re-emission probe, decisive.** Parent/intro units number 35 and 18; source-quoted words appearing inside them: **0 and 0**. Re-emission across subdivision boundaries is ruled out on the data. **§9's exclusive containment holds and `subtree_byte_length` does not double-count.**

Pass criterion is now the band `1.00 ≤ r ≤ 1.02`, adopted; at 1.00000 the one-sided concern is moot.

**Live V4 end-to-end — the property aggregate conservation cannot establish.** Auto-selected quoted-only phrases queried through the FTS index: **8/8** on `hr3838eh`, **8/8 substantively** on `s1071enr`. The single non-`['quoted']` result is `['quoted','header']` on an inserted subsection title that also matches the enclosing section's own header — both contexts correct, not a mislabel. Every hit drew its snippet from the inserted span with the operative `Section X … is amended by striking/inserting` adjacent. Per-unit context is correct on real queries; no offsetting errors.

#### Intro-labeling defect — fixed and validated on live documents

`extract_intro_segments` hard-coded `operative` (parser.py:562). Fixed by delegating each intro child to `extract_segments`. Suite 42 passed / 1 skipped. Recorded in §6 with the standing rule it produced.

**The hazard was LIVE, not latent.** The two acceptance fixtures showed 0 of 53, but a widened scan — **N=18 packages, 571 subdivided sections** (TCJA, IRA, CARES, three appropriations, four NDAAs, IIJA) — found **2 real triggers**:

- `117hr2471enr` `S:804` (VAWA, tribal jurisdiction). Intro now parses as `[header, operative, quoted "Indian Civil Rights Act of 1968", operative]`. The old code flattened all four into one operative segment: **a quoted span mislabeled operative in a shipping statute.**
- `116hr133enr` `S:401` (WRDA, project authorizations) — same shape, quoted "Report to Congress on Future Water Resources Development".

Identity harness clean on both (0 leaks); the quoted intro phrase retrieves `match_contexts=['quoted']` end-to-end. **These are the validating live documents §13 requires**; the synthetic fixture guards the regression only. Measured rate: 2/571 sections, 2/18 packages.

#### Two spec-session predictions that did not hold — corrected

**1. "V14 will fail spuriously on the fix."** It cannot. The leak test is **ancestor**-based, intro children are direct children of the section, and Assertion 1 already establishes the section has no quoted ancestor — so no intro child can have one. Quoted descendants are never individually recorded: `quote`/`quoted-block` are flattened by `element_text` and return before recursing, and a `<text>`-wrapped quote is reached only through the three-argument recursive call the discriminator already excludes. Measured buggy and fixed, on both fixtures and the synthetic: leaked = 0 in every cell.

What the two-way discriminator actually did was **inflate the emitted set with non-unit-sources** (1366/990 buggy versus 1363/989 fixed) — corrupting the count's *meaning*, not the verdict. The widening was still right; the stated reason was wrong.

**2. "Expect the counts to move."** They do not. The parser fix changes context *within* a parent unit, not the set of elements that become unit sources. 1363/989 hold.

#### Harden the leak predicate: self-or-ancestor, not ancestor

The predicate is currently "has a `<quote>`/`<quoted-block>` **ancestor**," which by construction cannot flag a `<quote>` element that is itself recorded as a unit source. The analysis above argues that never happens — quotes are flattened and return before recursing. **Make the predicate `is-or-has-ancestor` so that argument becomes an assertion.** It should read 0 either way; the value is that a future change to the flatten path cannot silently open a class the test structurally cannot see. Same move as the subdivision-coverage assertion below.

#### Trailing/orphaned content — approved, as a test-time assertion

Structurally reachable and would be **dropped**: `extract_intro_segments` ends at the first `FALLBACK_CHAIN` child and `_subdivide` promotes only `FALLBACK_CHAIN` children to units, so a non-subdivision child in that region is neither. **0 of 571 observed.**

**Add the coverage assertion.** Every non-`enum`/`header` child of a subdivided section must land in either the intro or a child unit. Reasons it is worth the near-zero cost:

- Content **loss** is worse than mislabeling and is invisible to every existing check — a conservation ratio computed over the traversal that dropped the content will not show it. This is the same structural blindness that let the intro mislabel read as 0.
- It converts an observation into an invariant, which is exactly the lesson the intro defect taught: 0 meant two different things and nothing distinguished them.
- It is an assertion, not a behavioral change, so it cannot regress anything.

**Shipped in `b370e8d`, sharing the `audit()` harness with the identity-leak check.** Detector runs on the **raw XML tree**, independent of what the parser emitted, so it sees the structural orphan whether or not the parser dropped it. **0 orphans across 571 subdivided sections in 18 packages.** Two always-on unit tests keep the 0 honest — one plants a flush `<text>` after the last subsection and asserts the detector sees it, one asserts the ordinary shape is clean. A 0 therefore means *absent*, not *blind*, which is the property the intro mislabel lacked.

#### Three coverage questions on the detector

**1. Does it recurse? — the one that might matter.** §5 applies the subdivision chain **recursively**, so the intro/`_subdivide` seam exists at every level, not only section→subsection: a `<paragraph>` with flush text after its first `<subparagraph>` is the same construction one level down. The detector is described as running once per subdivided **section**, and 571 is a section-level count. If `extract_intro_segments` is invoked at each recursive level the deeper levels are covered for free; if subdivision below the first level takes a different path, **the 0 attests to the top level only**. Determine which, and say so — a bounded 0 is worth much less if its bound is unstated.

**2. `sub_type` is single-valued — triage note for the day it fires.** `sub_type` is the tag of the *first* `FALLBACK_CHAIN` child, and the loop exempts only that tag. A section mixing subdivision types after the first would flag the odd one out. Whether that is a true orphan or a detector artifact depends on whether `_subdivide` promotes **any** `FALLBACK_CHAIN` child or only same-type siblings. Record the answer **now**, while it is cheap: the failure mode is someone hitting a red test months from now, guessing "detector artifact," and dismissing a real content-loss finding.

**3. The plant tests trailing; the loop also covers interleaved.** `children[first_sub:]` catches a non-subdivision child *between* two subsections, but the non-vacuity plant only exercises the trailing position. Same test, different insertion point — worth adding so both branches of the detector are proven to bite rather than one.

**Test-time, over the extended corpus — not a production assertion.** A hard failure in production on an unusual bill would take the tool down for a content-loss edge. Staging: assert in tests now; **if it ever fires, that is the live instance that justifies the behavioral fix**, and the fix gets designed against a real document rather than speculatively.

**Method note worth keeping:** measuring conservation across *all* split paths rather than only byte-cuts was the right call. Large amendatory sections mostly split along subdivisions (only 14 and 10 units respectively fall through to `CHUNK`), so a byte-cut-only measure would have exercised almost none of the real behavior.

**V15 — Public Law citation consistency. RE-RUN UNBIASED 2026-08-04 — PASS, recorded at measured strength.** *(no credentials needed against cached documents)*.

Superseding frame: `BILLS-119s1071enr` @ `enr`, **every amendatory unit, no query selection**, with Division G broken out. The earlier 48-unit figure came from a query-selected frame and is superseded.

| Frame | clauses | sections | explicit | bare name | back-ref | sections ≥2 | mixed |
|---|---|---|---|---|---|---|---|
| whole package | 44 | 38 | 89% | 5% | 7% | **5** | **0** |
| Division G (Coast Guard) | 14 | 9 | **100%** | 0% | 0% | **4** | **0** |

**The ≥2 denominator this step demanded is 5.** Per the criterion set before the number was known, low single digits means the honest finding is **"zero mixing observed across five eligible sections,"** not "measured clean." §6's decision proceeds on that basis. The standard does not loosen because the result was favorable.

**Independent strengthening:** no section cites one target both by P.L. number and by bare name. Same-target consistency does not depend on the ≥2 denominator and is a tighter property than cross-target form-mixing.

**Back-reference exclusion — verified, closed.** All 3 clauses V15 actually excluded sit in single-Act sections (`S:2309`, `S:3113`, `S:6502`), so the antecedent is unambiguous and the exclusion is safe. The multi-antecedent case **is real** — `S:6801` names 5 Acts, `S:6804` names 3 — but the `such Act` uses there are non-amendatory cross-references and never entered the amendatory frame, so they do not touch the numbers.

**That the ambiguity exists at all is the argument for the current default.** Back-refs are excluded rather than resolved because a resolver would have to pick among five antecedents in `S:6801` with nothing in the text to disambiguate. Same reasoning as the named-Act red line: unpredictable resolution is worse than uniform absence.

**Corpus correction:** Division G of `s1071enr` is the Coast Guard body, measured directly and the cleanest frame in the fixture set — an earlier record wrongly called it unreachable and substituted a proxy. The alias-resolution premise built on that record is retracted and the option is rejected in §14b.

**V16 — quoted delimiter source fidelity. RUN 2026-08-04 — verdict: NEVER present.** *(no credentials needed)*.

5,176 quoting elements sampled across all three fixtures, far above the ≥50 floor.

| Doc | `<quote>` n | open | close | `<quoted-block>` n | open | close |
|---|---|---|---|---|---|---|
| NDAA `enr` | 2,827 | 0.0% | 0.0% | 680 | 0.1% | 0.0% |
| 119hr1 `enr` | 1,280 | 0.0% | 0.0% | 386 | 0.0% | 0.0% |
| S 4977 `is` | 2 | 0.0% | 0.0% | 1 | 0.0% | 0.0% |
| hres463 | 0 | — | — | 0 | — | — |

The tag is the delimiter; the character data carries no marks. **Decision recorded in §6: render unconditionally, strip defensively for the 0.1% class**, since this section's no-doubled-delimiters post-condition fails on it otherwise. The `S 3548` orphaned `" .` is not a source delimiter and its origin is still unexplained — see the loose end noted in §6.

---

**V17 — §9 conformance on the wire.** *(offline; fixture-backed, CI-friendly)*.

Every other step in this list measures the parser or the index. **None measures what a caller receives.** D2 in the tool-defect register is the demonstration that the gap is load-bearing: `convert_members_committees_response` hard-returns `members=[]`, `committees=[]`, `summary=<raw markdown>` because `_extract_json` returns `None` for impls that emit pre-formatted markdown — the array-population code never executes. A tool can pass every parse-level check and still be unusable to a programmatic consumer.

**Scope now: the three bill-text tools.** Extending it across the other 96 operations belongs to PR A, where it is worth far more — those tools have no Pydantic model enforcing shape at all.

#### The assertions that discriminate — and the one that does not

> **`members=[]` is present and correctly typed.** A schema-conformance check as first proposed — "every §9 field present and correctly typed" — **would have passed D2.** That phrasing is retained nowhere; it is recorded here only as the trap. Against Pydantic-modelled responses it is close to fully redundant, since validated `model_dump()` already guarantees shape. Presence is not the property. **Population is.**

1. **Non-empty payload on known-matching input.** Invoke each tool against a fixture and a query known to match; assert the structured collection is **non-empty** and that the substantive content is inside it. `hits`, `children`, and the TOC node list are the collections that matter.
2. **Count/collection coherence.** Any count field must equal the length of what it counts. D2's signature was precisely that `results_count` and the serializer disagreed — a per-field check cannot see that, a cross-field one catches it immediately. Same family as `amends != [] ⟹ is_amendatory` in §6: **coherence invariants catch serializer defects that field-level checks structurally cannot.**
3. **No prose fallback.** Assert no top-level `summary`-style blob carries content absent from the structured fields. This is what D2 actually is.
4. **Structural: `bill_text` imports no `response_converters`.** One AST-level assertion, and the most durable item here. It guards the realistic future failure — a well-meant consistency refactor routing the new tools through the shared converter and silently inheriting D2.

**Method note.** Patching `load_bill_text` to return a parsed fixture exercises the serialization path without network, which is the right trade for a CI guard. It is not a substitute for the live acceptance runs — it tests the serializer, not the fetch.

**Current state, measured live 2026-08-04:** `search_bill_text` returns a populated `hits` list with every §9 `SearchHit` field present; `get_bill_section` returns `text`, `children`, `node_kind`, `subtree_byte_length`, `truncated` as first-class fields; neither carries a top-level summary blob. §9 is met on the wire. V17 converts that observation into something that cannot regress.

**V18 — the `is_amendatory` quote branch. Gates the S:7111/S:7231 over-fire decision.** *(no credentials needed; extended corpus)*.

`is_amendatory` over-fires on units whose only amendatory signal is a quotation construct — defined terms and report titles rather than amendatory text.

**The proposed refinement — treat `<quoted-block>` as amendatory and inline `<quote>` as not — fails on evidence already in this document.** Inline `<quote>` carries genuine amendatory insertions constantly: `S 3548` reads *is amended by inserting "or section 2 of this Act" after "any violation of the Sherman Act"*, and both of those are inline quotes in a real strike/insert. A block-versus-inline rule would drop every short insertion in the corpus. The two forms differ in the *size* of what is quoted, not in whether an amendment is happening.

**The over-fire is A5's lesson in a different costume.** A5 established that a citation form naming its target is not thereby evidence that this unit amends it. The same holds here: **a quotation construct is a structural marker, not evidence of amendment.** Gate on the amendatory verb, which is already the shared `_AMEND_VERB` predicate, rather than on the presence of quoted material.

**Measure before removing the branch.** `is_amendatory` must remain a **strict superset** of the `amends` verb gate (§6's coherence invariant depends on it), so the question is what the quote-only branch contributes:

1. Across the extended corpus, count units where `is_amendatory` fires **only** via the quote branch, with no amendatory verb present.
2. Hand-sample ≥30 of them.
3. If they are predominantly defined terms and report titles — as `S:7111`/`S:7231` and the VAWA/WRDA intro cases suggest — **drop the branch**.
4. If a meaningful share are genuine amendments the verb list misses, the fix is **widening the verb list**, not retaining a structural proxy for it. Report which.

#### Pre-registered before the data — thresholds, a prediction, and an invariant check

**Threshold, set now.** *Predominantly* means **≥80% of the hand sample are defined terms, report titles, or other non-amendatory quotation**. Below that, the branch is catching real amendments and dropping it is a recall decision, not a precision fix. Fixed before the numbers exist, for the same reason V15's ≥2 denominator was: a threshold chosen after the result is not a threshold.

**Prediction, stated so it can be wrong.** The quote-only branch most likely exists because **imperative amendatory language carries no gated verb.** A5's hug matches `is|are [further|hereby] amended|repealed`, and constructions like *"Strike the following:"* or *"Insert after subsection (b) the following:"* match none of it while being unambiguously amendatory. If that is what the branch is catching, neither *drop* nor a generic widening is right — the fix is **adding the imperative forms specifically**, and the hand sample should be coded for this category rather than only for amendatory-versus-not.

If the prediction is wrong and the sample is overwhelmingly titles and defined terms, drop the branch and say the prediction failed.

**Invariant check before dropping anything.** §6 requires `amends != [] ⟹ is_amendatory`, which holds because `is_amendatory` is a strict superset of the `amends` verb gate. Dropping the quote branch **narrows** `is_amendatory` — confirm it does not narrow below the gate. It should not: both derive from the shared `_AMEND_VERB`, so removing a non-verb branch leaves the verb branch, which still contains the gate. Assert it rather than reason it; the invariant is load-bearing and this is the first change that shrinks its left side.

**A third option exists and I lean against it.** Keep the branch but add an `amendatory_basis` field distinguishing `verb` from `quote-only`, preserving recall while marking the weaker inference. §6 has consistently refused to push this kind of judgement onto the consumer, and a boolean plus a caveat field consumers will not read is worse than a boolean that means one thing. Recorded because if the sample comes back near 50/50, neither drop nor widen is clean and this becomes the least-bad answer.

#### V18 RESULT — 2026-08-04. Branch dropped. Prediction falsified.

Hand-coded n=35, seed 18, reproducible. **35/35 non-amendatory quotation.** 0 imperative-amendatory, 0 ambiguous.

| Category | n |
|---|---|
| Appropriations account / program headings | 19 |
| Defined terms (`the term`, `referred to as`) | 6 |
| Report, study, and statement titles | 4 |
| Short titles (`may be cited as`) | 3 |
| Fund / program names | 3 |
| Quoted text inside findings | 3 |

**Threshold (≥80%): cleared by 20 points.** Disposition is mechanical — **drop the quote branch; `is_amendatory` becomes verb-only.**

**Prediction: falsified, and recorded as such.** The branch was predicted to be catching ungated *imperative* amendments (`Strike the following:`). Zero in the sample; a whole-population probe puts the ungated-amendatory residual at ~1% (18/3153) and those are **declarative** (`is to read as follows`), not imperative. The branch existed because non-amendatory quotation constructs use `<quote>` — headings, titles, defined terms, findings. A wrong prediction that was cheap to test and changed what got coded is worth more than a vague one that could not fail.

**Invariant: measured, not reasoned.** Across 19,234 units / 3,387 with `amends != []`, **0 violations** under verb-only `is_amendatory`. 3,651 units flip True→False; **0 carry an `amends` target**. Structurally guaranteed — `amends` requires `_HUG ⊃ _AMEND_VERB` and `AMENDATORY_RE ⊃ _AMEND_VERB` — and now confirmed corpus-wide. **Pin it as a corpus test**: this is the first change that shrinks the invariant's left side.

**State the residual at the width the evidence supports.** 35/35 clean bounds the genuine rate at roughly **8% at 95% confidence** against a 3,651-unit flip population; the targeted population probe puts the specific ungated category at **~1%**. The probe is the tighter number but it can only find categories someone thought to search for. Record "≤8% by sampling, ~1% by targeted probe," not a flat 1% — the same discipline applied to A5's 30/388.

#### The ~1% residual — add `to read as follows`, with three constraints

**Add it.** §6 tells consumers to use `is_amendatory` **and** `match_contexts` to identify amendatory text, and positions `amends` — not `is_amendatory` — as the convenience that makes no completeness claim. A known false negative in the field the spec directs consumers to rely on is inconsistent with how that field is sold. `match_contexts` carrying those units means retrieval survives, but the flag would be knowingly wrong.

1. **`AMENDATORY_RE` only — never `_AMEND_VERB`.** The shared verb set gates `amends`, whose per-form precision V13 measured at 0/30. Adding an unmeasured form there reopens V13 for nothing. Widening the superset alone preserves both the invariant and the measured precision.
2. **Enumerate all 18 before adding.** n=18 is small enough to read exhaustively, so there is no reason to sample. If any are not genuine amendments, the addition needs narrowing first. Complete beats representative when complete is affordable.
3. **Re-assert the invariant after.** The addition widens the left side back out — the safe direction, but assert rather than reason, on the same grounds as the drop.

**This is A5's lesson applied correctly:** a targeted addition to a curated verb list, not a structural proxy retained because it sometimes catches something. Keeping the quote branch to reach this 1% is precisely the position 35/35 rules out.

#### Document what `is_amendatory` now guarantees

Verb-only means it will miss amendatory constructions using no recognized verb form. Say so in §6 and in the tool description. The field remains the dependable signal — it is now dependable in a stateable way, which is better than dependable by assumption.

Either outcome is a real answer. Retaining the branch because it sometimes helps, without knowing how often it hurts, is the position this spec has rejected three times.

**V19 — RE-MEASURE after the en-dash fix, 2026-08-06 (`dfafacb`). Both populations land on documentation.**

| | before | after |
|---|---|---|
| Population B | 359 / 3,556 = **10.1%** | 349 / 3,665 = **9.5%** — below |
| Population A | **18.6%** | **19.4%** — below, and closer |

**Re-measuring rather than subtracting was necessary, and by more than the arithmetic.** Subtraction predicted 9.1%. The denominator moved: **109 units that previously reported empty `amends` now populate one**, leaving A's population and entering B's — while `N_short` fell by only **10**, not 36.

#### B was never above the line, and the inflation was the instrument — corrected mechanism

| metric | figure | |
|---|---|---|
| **COUNT** (pre-registered wording), USC-bearing denominator | **207 / 2,985 = 6.9%** | below |
| COUNT, original denominator | 207 / 3,665 = 5.6% | below |
| SET (stricter, offered as diagnostic only) | 992 / 2,985 = 33.2% | — |

**The cause was designator-splitting, not trailing provenance.** The detector kept the source's en-dash and kept **subsection designators inside the capture**, while the parser normalizes the dash and drops designators:

```
33 U.S.C. 467f–2(a)  ⎫
33 U.S.C. 467f–2(b)  ⎬ detector: 3 targets      parser: 1 cite
33 U.S.C. 467f–2(c)  ⎭
```

**One section amended in three subsections — the most ordinary drafting shape there is — counted as a threefold shortfall.**

> **Correction, and the error was mine.** This document previously recorded trailing `as amended by` provenance as *the* mechanism for all 26 cases. That rested on **one example**, and the maintainer's standing instruction is to mark anything unverified as needing verification rather than writing it as settled. It was written as settled. **Third time in this project I have generalized a mechanism from a single suggestive instance** — after the orphaned `" .` and the `Chapter 3` header — and the third overturned by measurement.

#### Why a count comparison hid it, and the rule that follows

**`present > reported` never has to surface a pairing.** A cardinality comparison does not force the two sides to be aligned, so a systematic mismatch in *what counts as an element* is invisible by construction. A set comparison would have shown `467f–2(a)` against `467f–2` immediately.

> **When comparing two derived collections, compare sets and inspect the difference — not counts.** Counts hide element-definition mismatches. This is the **third instrument defect of the same family** in this harness (after the header detector comparing normalized text against raw `itertext()`): **the two sides of the comparison were produced by different pipelines.** Distinct from correlate-as-sufficient, and it needs the set-difference guard rather than planted positives — a plant tests a known shape, and this shape was not known.

**Read the 33.2% as an instrument diagnostic, not a field metric.** It fires on disagreement in **either** direction, so it counts the detector's misses as the field's. What it does say: **detector and parser disagree about element identity roughly five times more often than the field is short.** That supports trusting the count metric's *direction* and not its *precision*.

**Denominator change, flagged rather than found later:** B narrowed to units reporting ≥1 USC cite, since a public-law-only unit cannot be short in the USC domain. **Accepted** — it is the same correction as A's, a denominator that contains only units where the phenomenon is possible. Note it moved the figure **up** (6.9% vs 5.6%), against the convenient direction, which is what distinguishes a correction from a convenience.

#### The instability is the finding worth keeping

**10.1% → 9.5% → 6.9%, across three instrument corrections, each a genuine defect fix.**

**Pre-registration protects against choosing a threshold after the data. It does not protect against the operationalization moving underneath it** — and this one moved 3.2 points against a 10-point line. Had the true value sat near 10%, the ruling would have turned on instrument quality rather than on the phenomenon.

**The guard is two-part, and the plants alone were not enough:** planted positives and negatives catch **known** failure shapes; a **set-difference inspection** catches element-definition mismatches nobody thought to plant. Do both before the number is reported at all, not after a threshold comes close.

#### A's threshold drifts on work unrelated to A — my denominator was wrong

**A's ratio rose from 18.6% to 19.4% with its numerator unchanged at exactly 512.** Fixing a resolution bug that has nothing to do with lead-ins removed 109 non-lead-in empties and concentrated the remainder. **Every future resolution improvement pushes A toward 20% without the phenomenon A measures changing at all.**

**That is a defect in the criterion I specified, not in the measurement.** `N_empty_leadin / N_empty` has a shrinking denominator by construction. The question F8 asks — *is this blind spot systematic enough to disclose per-unit?* — has a stable denominator available:

> **`N_empty_leadin / N_amendatory` = 512 / 6,304 = 8.1%**, invariant under resolution fixes elsewhere, because neither term moves when a non-lead-in empty gets resolved.

**The ruling does not change and that is the point.** 8.1% of amendatory units, 19.4% of empties — **neither is a majority phenomenon on either metric**, so the decision is robust to the denominator choice. Recording the flaw without restating the threshold, because a criterion revised after seeing the data is worth nothing; **use the stable metric for any future re-measurement**, where A currently sits nowhere near a line rather than 0.6 points from one.

#### Precision re-checked before widening — correctly

Widening a gate measured at 0/30 false positives **reopens that measurement**, and it was closed proactively: 198 new cites, 30 sampled (seed 13), **30/30 genuine targets**, all `Section X of [Act] (N U.S.C. Y–Z) is amended by …`, no ranges, no cross-references. The corpus-wide `amends != [] ⟹ is_amendatory` invariant holds.

**Record it at its width:** 30/30 bounds the false-positive rate at roughly **10% at 95% confidence** against 198 new cites, so up to ~20 could be wrong. Same discipline as A5's 30/388. Not a concern; a number stated at the precision the sample supports.

---

**V19 — RESULT 2026-08-06.** `N_amendatory` 6,304.

| Population | figure | threshold | outcome |
|---|---|---|---|
| **A** — empty with chapter/title lead-in | 512 / 2,748 empty = **18.6%** | 20% | **below → documentation** |
| **B** — populated but short | 359 / 3,556 = **10.1%** | 10% | **contested — see below** |

**A: threshold honored, F8 is a tool-description fix.** 18.6% against a 20% line is close enough that the direction is real and the examples are exactly the predicted construction (`Part VI of subchapter B of chapter 1 is amended`). **What settles it beyond the threshold:** `N_empty` is **43.6% of all amendatory units**, and only 18.6% of that emptiness is the lead-in case. The other four-fifths is empty **by design** — named Acts, the IRC by bare section, unresolvable targets, all deliberate §6 exclusions. A schema change to disclose one minority cause of a majority-deliberate condition is not warranted; the documentation is.

**B: fix the resolution bug and re-measure before ruling.** 36 of the 359 are a regex defect, not A5's accepted recall cost: `AMENDS_USC_RE`'s section suffix is `(?:-\d+)?`, **ASCII hyphen only**, while the source writes `16 U.S.C. 3839aa–2` with an **en-dash** — so the hug cannot cross and every en-dash-suffixed section is dropped. The P.L. form was already fixed for unicode dashes; the USC form was missed.

**Why this is not goalpost-moving, stated because it resembles it.** Population B was defined as units containing *more resolvable citations than `amends` reports*. **An en-dash-suffixed section is resolvable** — the regex simply fails to. Those 36 belong in the fix pile, not the disclosure pile, and that is true independent of which side of 10% the remainder lands on. If the corrected figure were 10.5%, B would clear and get a signal.

**Do not subtract — re-measure.** 359 − 36 = 323 assumes the shortfalls are independent. A unit short by one en-dash cite may also be short by an interposed-clause cite, and fixing the regex changes which units are short, not only how many.

**F3's disposition therefore waits on the re-run.**

---

**V19 — `amends` completeness: two populations, one scan.** *(no credentials needed; offline over the extended corpus)*. Gates **F3** and **F8**.

Both questions are about the same field and answered by one pass, but they are **different defects with different remedies**, so report them separately and do not pool.

#### Population A — empty arrays that should not be empty (gates F8)

A unit is `is_amendatory: true` with `amends: []` because its target is named by a **chapter- or title-level lead-in** followed by bare section numbers — `Title 46, United States Code, is amended as follows` — which no citation form in §6 resolves.

Measure across the extended corpus:

- `N_amendatory` — total amendatory units *(the denominator; fail the scan if zero)*
- `N_empty` — of those, how many report `amends: []`
- `N_empty_leadin` — of those, how many carry a chapter- or title-level amendatory lead-in

**Pre-registered threshold:** if `N_empty_leadin / N_empty` is **≥ 20%**, the blind spot is systematic and belongs in the response, not only the documentation — a per-unit note naming the condition, in the `version_resolution_note` shape §17 showed consumers actually read. Below 20%, the tool description carries it and no schema change is warranted.

**Prior evidence, and why it is not the answer.** An independent trace review found **22** amendatory hits with `amends: []` including chapter 47 of title 46, subtitle I adding chapter 3, and chapter 73 with the §7306 rewrite. Those came from queries literally shaped like `title 46, United States Code, is amended` — **a lower bound on a sample biased toward the phenomenon.** It establishes direction, not size.

#### Population B — populated arrays that are short (gates F3)

`S:7223.` reports `[2158, 2159(c), 2160]` while its own operative text also amends **§2161**. This is the more dangerous case: an empty array is visibly incomplete, a populated one reads as the answer.

Measure:

- `N_populated` — units with a non-empty `amends`
- `N_short` — of those, how many contain **more resolvable citations under an amendatory lead-in** in their operative text than `amends` reports
- the **distribution of the shortfall** — one missing, two, more

**Pre-registered threshold:** if `N_short / N_populated` is **≥ 10%**, add a completeness signal to the response. Below 10%, §6's existing *convenience, not completeness* wording covers it.

**Be honest about what B is.** §6 already documents `amends` as making no completeness claim, so a short array is **within contract**. The argument for a signal is **legibility, not correctness**: nothing distinguishes three-of-three from three-of-four, and A5's recall cost was accepted on reasoning that assumed the incomplete case would be empty. That is a weaker case than F8's and the threshold is set higher to reflect it.

#### Method notes

**Report `n examined` with every figure and fail if it is zero** — per the corpus-scan hygiene below. The `urllib`/403 incident is why.

**String matching is correct here, and this is not an exception to the identity rule.** Detecting a lead-in phrase in operative text is a **textual** question. The identity rule governs **provenance** — which element produced a unit — and does not apply. Do not over-apply it and do not skip it where it does apply: scan `operative` segments only, per §6, and establish that scoping by segment identity rather than by text position.

**Both populations, one corpus pass, one report.** Pooling them into a single "amends incompleteness rate" would hide that one is a resolution gap and the other a disclosure gap, with different fixes.

#### The replay gate after F12 — split it, do not choose between the two things it was doing

F12 changed rendering, which moved chunk boundaries, which moved bm25, which reordered results: 27/30 rounds reproduce exactly, 1 differs in chunk indices, 2 at section level, **0 known-correct targets lost.** The gate as written — *reproduces the recorded `top_hits` exactly and in order* — failed on a legitimate change.

**The gate was serving two purposes and only one of them survives a code change:**

| purpose | needs | version-pinned? |
|---|---|---|
| **Fidelity** — the offline replay reproduces the shipped `search()`, so V20's ranks are not from a drifted harness | exact reproduction at a **fixed code state** | yes, inherently |
| **Regression** — behavior has not changed in a way that loses answers | a **durable** property | no |

**The rewrite converts the first into the second, and the first is what V20's numbers rest on.** After it, nothing establishes that the replay still exercises the shipped code path. If the harness itself drifts — a change to how it builds queries, applies `max_hits`, or assembles candidate lists — *"target still found"* can pass while the replay has stopped being a replay.

**Both are recoverable, and the dilemma dissolves once fidelity stops comparing against a file:**

- **Fidelity: `replay(query_set) == live_search(query_set)`, computed fresh, both sides now.** Never goes stale, never blocks a legitimate change, and isolates harness drift from behavior change. **This is the check whose absence would make V20's ranks meaningless.**
- **Regression: a known-correct target present in the recorded trace must still be found.** Durable, exactly as rewritten.
- **Impact: the exact/chunk/section classification reported, not asserted.** Also as rewritten.

**The "re-recording is self-referential" objection is right about the regression baseline and does not apply to fidelity.** Re-recording a *regression* baseline asserts new behavior matches new behavior — circular. Comparing replay to a **live call** asserts two code paths agree *today*, which is a real claim at every code state. **The rewrite was correct in direction and dropped a check that did not have to be dropped.**

---

**V20 — RESULT 2026-08-06. Hold k=60. The theory is directionally right and practically immaterial.**

Fidelity established first: **30/30 rounds reproduce their recorded `top_hits` exactly and in order** through the shipped `search()`, verified to bite by corrupting a recorded hit list. Without that every rank below is a plausible number from a drifted replay.

**The diagnostic answers yes — 7 of 17 target observations demoted, by +1 to +4 ranks.**

| | |
|---|---|
| targets ever **lost** from the result set | **0** — worst case rank 6 against `max_hits=15` |
| k-sweep | **nearly flat**; k=1 helps in exactly one case (S:804, 4 vs 6) |
| max-of-lists control | better in the harmed cases (S:804, 3 vs 6), on deltas of 1–3 |
| boilerplate promoted over its best single-query rank | **1 of 18 rounds** |

**Ruling: hold k=60**, and record why the argument failed rather than merely that it did.

**The 4×-spread argument predicted a k-sensitivity the data does not show.** If contribution spread across a list were the mechanism, k would be a strong lever; it is nearly inert here. **So the theory is right about direction and wrong about magnitude** — and since k is not the lever, retuning it would not fix even the seven observed demotions. The lever that does move them is max-of-lists, and switching fusion strategy over a 1–3 rank reorder that never lost a target is disproportionate.

**The predicted congressional-boilerplate failure is not occurring** — 1 of 18. That was the specific mechanism proposed, and it is refuted rather than merely unobserved.

> **My pre-registration was under-specified, and this is where it shows.** V20 asked a **binary** question — *does fusion ever demote the correct unit* — and the answer is a **magnitude**. No threshold was fixed in advance for what size of demotion warrants a change, so the governing rule had to be articulated after the data: **the harm that matters is loss from the result set, not reordering within it.** Zero losses.
>
> That rule is defensible and I would have set it in advance had I seen the shape of the question. Recording the gap because a pre-registration that quietly acquires its threshold afterward is worth less than one that admits it did.

> **First measurement in this project to refute a concern rather than confirm one.** V13 found the longhand leak, V18 found the quote branch, V19 found the en-dash bug. V20 tested a sound-sounding argument and found it immaterial. The discipline is only worth something if it can return "no," and this is the instance.

#### Rewrite imbalance survives, and it is not a k problem

**1 to 8 queries per round — an 8× spread in vote weight, chosen by the model, disclosed nowhere.** Independent of k, exactly as §7 predicted. Measured queries-per-round is separated from **estimated** concepts-per-round (token-overlap clustering), correctly — presenting a clustering judgement as a count would be the correlate error again.

**Ruling: fix it in the tool description, not by normalizing.** §7 assigns query expansion to the calling model, so **tell the model how expansion is weighted**: each query is an independent vote, and N paraphrases of one concept weight it N×. That puts the control where the decision is made. Normalizing per concept would require clustering — an **estimate** — and introduces a new unmeasured behavior behind the model's back to correct a weighting the model chose. Same shape as F9, and the cheapest fix available.

---

**V20 — does fusion ever hurt?** *(no credentials needed; offline over cached packages)*.

Settles the k=60 challenge in §7 by measurement rather than by retuning on argument.

**Use the §17 runs as ground truth — they cost nothing.** Group A, B, D, and E produced query sets with **known-correct target units**: `S:141.` (tanker inventory), `S:147.` (A-10), `S:7117.` (polar security cutter), `S:7215.` (Great Lakes icebreaking), `D:W/T:VIII/ST:A/S:804.` (tribal jurisdiction), `T:VII/ST:A/S:70104.` (child tax credit), and the `CHUNK:3` training passage. Replay each **verbatim query set** offline.

**The single diagnostic that decides it:**

> **Does the correct unit ever rank *worse* under fusion than under its own best single query?**

If no, fusion is not hurting and k stays at 60 regardless of the theory. If yes, the harm is concrete and quantified rather than argued. Report per case: best single-query rank, fused rank, and the delta.

**Sweep alongside it**, on the same query sets — `k ∈ {1, 5, 10, 60}` plus **max-of-lists** as a non-RRF control. Report the correct unit's rank under each. Smaller k sharpens rank-1 dominance; max-of-lists removes the consensus effect entirely and is the cleanest test of whether consensus is doing any useful work here.

**Also report the boilerplate case directly:** for each query set, how far up the fused list do units whose only matches are `The Secretary shall`, `Not later than 180 days`, definitions, or clerical amendments appear, versus their rank in the single best query.

**And measure the imbalance §7 hands to the model:** across the §17 query sets, how many rewrites did each distinct concept receive? If the spread is wide, the model has been weighting fusion without knowing it, and **that is a disclosure or normalization question independent of k.** Per-concept normalization is the obvious remedy and needs its own precision check before adoption.

**Do not change k before this reports.** No fusion failure has been observed in any §17 trace; the argument is sound but untested, and this spec has now four times declined to act on a sound-sounding argument without a number.

**V21 — HIT-LEVEL RESULT 2026-08-06. F6 ruled: emit a per-hit note — but not on the condition this step was written around.**

| | count | share |
|---|---|---|
| operative + quoted (**mixed**) | 21 | **8.8%** |
| operative only | 139 | 57.9% |
| **quoted only** | **70** | **29.2%** |
| neither | 10 | 4.2% |

n = 240 hits across 30 rounds (7 returned nothing).

**The unit-population proxy said 46.5%. The hit distribution is 8.8% — wrong by 5×**, and in the direction that mattered: near-midpoint ambiguity became a decisive minority. **That gap is the entire justification for V21's "realistic query set" wording**, and it is worth remembering the next time a proxy is offered as "the right denominator." It was the right denominator and the wrong distribution, and the wrong distribution is what the decision turned on.

#### The ruling, and the condition is not "mixed"

**`quoted only` at 29.2% is the finding, not the footnote.** A hit whose match_contexts is `['quoted']` alone is one where **the query matched nothing the bill enacts** — every matched word is inserted or struck text. That is the amendatory trap in its purest form, it is **3.3× more common than the mixed case**, and it is more dangerous: a mixed hit at least contains an operative match the consumer can anchor on.

**So the note fires on the absence of an operative match, not on the presence of mixing:**

> **Condition: `operative` ∉ `match_contexts`.** Covers `quoted only` (29.2%) and `neither` (4.2%) — **33.4% of hits.** Wording should say what is true and useful: *this hit's matched language does not appear in the bill's operative text.*

**Mixed (8.8%) gets nothing.** An operative match exists, so the consumer has real material to anchor on, and adding a signal there dilutes the one that matters.

**A1 is the reference case.** Its `S:141.` hit was `['quoted', 'header']` — **quoted-only** — and it passed **only because the ceiling model read the field.** The floor rerun showed what happens when it does not. This condition is exactly A1's shape, occurring in 29.2% of hits.

**Sample caveat, and what survives it.** 240 hits over §17's topic selection is modest and not unbiased. The precise 8.8/29.2 split is soft. **The direction is not** — a 5× proxy gap cannot be sampling noise, and "mixed is a decisive minority while quoted-only is substantial" is robust to it. Re-measure on a wider query set before quoting the percentages anywhere load-bearing.

---

**V21 — PARTIAL RESULT 2026-08-06. Unit population, not hit distribution.**

| | count | share |
|---|---|---|
| operative + quoted (**mixed**) | 9,310 | **46.5%** |
| operative only | 9,768 | 48.8% |
| quoted only | 339 | 1.7% |
| neither | 583 | 2.9% |
| `header` (orthogonal attribute) | 14,404 | 72.0% |

**This is the right denominator and the wrong distribution.** V21 asks about **hits over a realistic query set**; this is the unit population hits are drawn from. Hits are selected by relevance, and nothing establishes that mixed-context units are hit at their population rate — policy-content queries would favour operative text, amendment queries would favour mixed, and the bias could run either way.

**46.5% is too close to the midpoint to rule on a proxy.** The whole decision is minority-versus-majority, and a proxy that lands within four points of the line settles nothing. **Do not rule F6 on this.**

**What it does establish:** `header` at 72% confirms it is ubiquitous and orthogonal, validating the decision to project it out. And `quoted only` at 1.7% is low enough that quoted-only units are effectively a rarity.

**Convert with the §17 query sets** — extracted verbatim to `v20-query-sets.json` / `v20-query-sets.md`: 30 search calls, 115 queries, 7 zero-hit rounds, with the units fetched after each round. Same artifact unblocks V20.

---

**V21 — operative/quoted mixing in hits.** *(no credentials needed; offline over the extended corpus)*. Decides whether `match_contexts` needs an active disclosure. Gates **F6**.

**Why it exists.** §17's floor rerun showed a consumer receiving `match_contexts: ['operative', 'quoted', 'header']` and **not surfacing it**, where the ceiling on the identical response volunteered *"some of the matched language may be text being struck."* The signal is present and **passive**; only surplus reasoning reads it. Active disclosures do propagate here — `version_resolution_note` was acted on, `amends` was used by both cells.

#### Project `header` out of the measurement

**Report the operative × quoted 2×2, not the seven-subset distribution.** Earlier wording called for "all four combinations" and was underspecified; three contexts yield seven non-empty subsets, and `header` is orthogonal to the question.

| | quoted absent | quoted present |
|---|---|---|
| **operative absent** | — | quoted-only |
| **operative present** | operative-only | **both** |

**`header` participation is size-correlated and would confound it.** Measured 2026-08-06: nested descendant headings are indexed as `header` segments of their enclosing unit — legitimate, not duplication — so **a unit with many subordinate headings matches header-ish queries more readily.** Including `header` in the reported combinations would mix a fact about unit size into a measurement about context mixing. Report `header` frequency **separately**, as an attribute, not as a dimension of the mix.

**Decision rule, unchanged in substance:**

- **"Both" is most hits** → an active note is noise; the fix belongs in the tool description, which must state that a mixed-context hit may include struck or inserted language.
- **"Both" is a minority** → that minority is exactly where a consumer needs prompting, and the `version_resolution_note` pattern applies: emit a per-hit note naming the condition.

Report `n examined` and fail if zero, per the hygiene section below.

**Related, and cheaper:** B1's floor failure was **not calling the tool at all**. No response-side change reaches that consumer; F7 addressed it in the tool description (`07f3889`).

---

**V22 — subdivided amendatory parents.** *(no credentials needed; offline over the extended corpus)*. Decides whether F32's section-response fields need returned-text aggregation or own-unit values suffice. Gates the conditional contract in §4 (F32 container/subdivision ruling, 2026-08-20).

**Why it exists.** §4's read contract serves a subdivided parent within `max_bytes` by concatenating children at read time, while F32's new fields carry the parent unit's **own** stored value — so if any amendatory section is large enough to subdivide, its full amendatory text returns under `is_amendatory: false`, an active mislabel of the F32 failure shape. Whether that section exists in reality is a corpus fact, not a judgment call — check-dead-defensive before contracting for it (the F20-ranking / F28 / F23-Haiku lesson).

**Procedure.** Over every package in the extended corpus, enumerate units that have children (the subdivided parents — identity against the parser's own tree, never string matching). For each, read the stored per-unit `is_amendatory` of the parent and of every descendant. Count parents where the parent's own value is false and ≥1 descendant's is true; also record the parent-true/descendant-true overlap so the fix, if owed, can be sized. Report **`n found` / `n subdivided parents examined` / `n packages scanned`, and fail if either denominator is zero** — a corpus with no subdivided parents at all is a different result from one where none is amendatory, and both differ from a scan that errored.

**Preregistration.** *Expected:* ≥1 found — NDAA-scale sections exceed the subdivision threshold (S. 4042 `T:II/S:204` spans ~60,700 bytes across 14 children) and multi-subsection amendments to Title 10 are ordinary drafting. *Falsified if* 0 found with non-zero denominators, in which case the §4 aggregation contract is recorded **dead-defensive — do not build**, own-text semantics stand, and the docstring note is the guard. Record the outcome either way.

**V22 — MEASURED 2026-08-20. Preregistration CONFIRMED, and not marginally: the mislabel shape is the norm, not the edge.** Instrument: `tests/corpus/v22.py` (implementation commit `4cdc4f4`); identity from the parser's own tree (child-id closure, no dangling ids), stored values cross-checked against the index column the search path reads (391/391 agree); **reproduced by this session** (`python -m tests.corpus.v22`, ~12s offline, every figure identical to the implementation report). All hygiene gates passed, denominators non-zero.

| Figure | n |
|---|---|
| Found — parent own `is_amendatory` false, ≥1 descendant true | **391** |
| Subdivided parents examined | 602 |
| Packages scanned | 21 |
| Found ∧ subtree ≤ 25,000 B — assembled under default `max_bytes`, full amendatory text returned under `false` | **341** |
| Found ∧ subtree ≤ 100,000 B (assemblable at the clamp ceiling) | 388 |
| Found whose descendants carry ≥1 `amends` cite (aggregated `amends` would be non-empty) | 261 |
| Parent true ∧ ≥1 descendant true (overlap — own-unit semantics correct for a subdivided amender) | 13 |
| Parent true, no descendant true | 0 |
| Parent false, no descendant true | 198 |

**Reading: 65% of all subdivided parents are the mislabel shape**, because the drafting norm puts the amendatory verb in subsection (a) while the parent unit's own text is a header and often nothing else — the found rows are TCJA sections and omnibus "Amendments relating to…" sections with nearly every child amendatory. The 13 overlap rows are the entire population where own-unit semantics get a subdivided amender right.

**Adjacent shapes, reported separately (not the preregistered figure; both resolve via the container path, which the F32 ruling gave `false`/`[]`):** chunk-only prefixes (oversized `S:n`/`SS:(a)` emitted only as `CHUNK:k` units, no unit under the id itself) — 297 examined, **219 with an amendatory chunk, 185 assembled by default under `false`/`[]`**; structural containers — 2,317 examined, 1,712 with an amendatory descendant, **975 assembled by default**.

**Outcome: the §4 aggregation contract ACTIVATES, generalized to every assembling path (subdivided parents, chunk-only prefixes, assembled containers) — ruled in §4 as F33.** Own-unit values on an assembled response emit exactly the failure shape F32 exists to prevent, with a confident `false` attached. The A1 re-run traces are evidence for neither side here — `S:141` is a leaf.

**V22 verify pass — CLOSED 2026-08-20.** The instrument gained a second stage (`668b357`) that calls the shipped `get_bill_section` on every id it examined and diffs the response fields against the F33 contract, exiting non-zero on any mismatch — the set-based acceptance made executable. Against the F33 build (`fe17fa5`): 3,216 calls, **0 mismatches, all eight populations** (341/341, 229/229 assembled-and-cited, 50/50, 198/198, 13/13, 231/231, 1,512/1,512, 871/871), reproduced by the spec session with exit 0. The 229 (not 261) denominator is the correct one and is recorded as a correction in §4. F33 closed; the aggregation contract is live and continuously verifiable by re-running this scan.

### Corpus-scan hygiene — applies to V19, V20, V21, V22

**Assert a non-zero denominator.** A scan that errors and a scan that found nothing render identically today. An earlier resolution scan used bare `urllib`, swallowed exceptions, and reported 403s from a blocked User-Agent as *"no resolutions have 2+ versions."* The conclusion was not load-bearing, but the scan established nothing and was reported as though it had. **Every measurement below must report `n examined` alongside `n found`, and fail if `examined` is zero.**

**Do not identify provenance by string match.** Content recurs across versions — a committee substitute repeats the struck text's wording verbatim. Use identity instrumentation against the parser's own tree, the instrument that settled V14's Q1.

**Verify each member of an enumeration independently.** Overlapping guards cover each other on the shapes an author thinks to test; the enumeration can be complete while its verification is not.

---

*Deferred and rejected design options live in `13-deferred-options.md`.*
