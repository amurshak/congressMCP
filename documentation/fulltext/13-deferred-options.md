*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 14b. Recorded design options — PR 2+, not this iteration

### Named-Act alias resolution — REJECTED on measurement, not on principle

**The idea.** Where a bill pairs a named Act with its public law once, key on the name and
resolve subsequent bare uses of that name to the same P.L. — recovering `amends` targets
the verb gate currently drops.

**Measured 2026-08-04 and withdrawn by its own proposer.** Two findings killed it:

1. **Zero recall in the corpus it was proposed for.** In Division G the Don Young Coast
   Guard Authorization Act name appears 15×: 10 with an explicit in-clause P.L., 5 bare.
   **All 5 bare cites are non-amendatory** — `procured pursuant to`, hiring deadlines,
   and U.S. Code note cites (`14 U.S.C. 504 note`, `16 U.S.C. 1390 note`). None sits in an
   amendatory-verb clause. Resolving them would manufacture false positives, not recover
   amendments. The earlier claim of 4 alias-recoverable cites at `S:7344` and
   `S:7231/SS:(b)` was wrong and is retracted.
2. **The ambiguity is live, not hypothetical.** Whole-package, the genuine recoverable
   population is **2 clauses**, and they split along the failure line: Atomic Energy
   Defense Act (41 mentions, 1 pairing — clean) versus Military Construction
   Authorization Act (50 mentions, **47 distinct P.L. pairings**, because it is enacted
   per fiscal year). See §6 for the full record; this is now the canonical evidence for
   the named-Act red line.

**Rejected, not deferred.** The upside is two clauses in one bill; the downside is
confident wrong resolution wherever an Act name is reused across enactments, which is
common in authorization lineages. Reopening requires a mechanism that distinguishes
reused names from unique ones per-document — not a larger corpus.

### Generic document-search core (committee reports and beyond) — DEFERRED at N=1

**The idea.** Extract the search infrastructure so a second document type — CRPT
(committee reports) is the motivating case — reuses it, with only the document-specific
layer changing.

**The seam is the document adapter, not the data source and not FTS5.**

- *Not the data source.* GovInfo serves CRPT through the same packages endpoint, same
  auth, same rate bucket. The fetch layer barely moves.
- *Not FTS5.* Escaping, BM25 config, RRF fusion and snippet extraction are ~200 lines
  over a stdlib module. Extracting only these leaves the expensive half duplicated — the
  walk that emits units, the quoted carve-out binding every emitting path, segment
  clipping across byte cuts, the addressing vocabulary. That is where the amendments and
  the HIGHs live.
- *The adapter surface,* if this is ever built: (a) element names for structural
  discovery, (b) the id component table, (c) segment classification rules, (d) extraction
  quirks. Everything downstream — subdivide, clip, index, query, fuse, snippet — is shared.

**Reference resolution: verified, not assumed (2026-08-04).** `get_bill_toc(congress=119,
bill_type="s", number=1801)` resolved the version, fetched `BILLS-119s1801rs`, and returned
a 27-section TOC **with no other tool registered**. The core takes `congress` +
`bill_type` + `number` and needs no discovery layer beside it. That upgrades this option:
a self-resolving core is a **standalone asset**, not a component requiring a companion
tool, and the adapter surface below stays as drawn.

**The reusable asset is the safety property, not the infrastructure.** "Never report
quoted material as the document's own voice" is not bill-specific. Committee reports
quote bill text, existing law, and testimony constantly, and a model summarizing one has
the identical failure mode. A generic core carrying the segment discipline gives document
type two a **tested** correctness property instead of a reimplemented one. This is the
argument the option should be judged on; infrastructure reuse is the weaker case.

**Why not now.**

1. **N=1.** An abstraction designed from one example fits the second badly, and the
   compromise is often worse than duplication. Extraction from two working
   implementations is far better informed — the deferral buys real information.
2. **Gating unknown:** does CRPT carry structural XML comparable to the Bill DTD? The
   GovInfo CRPT help page documents granule access as `.htm`, which *hints* at
   HTML/text rather than a structural schema — an inference from a URL pattern, not a
   measurement. **Verify against the packages API before any design work.** If CRPT is
   flat text, the unit-addressing model does not transfer at all and the shared surface
   collapses to chunk-and-index, which is not worth an interface.
3. **V14 is unfixed** and lives in exactly the code a refactor relocates. Extracting now
   makes a known defect generic, then fixes it twice.

**Sequencing if it is ever done:** after the V14 fix and PR 1 merge, **before PR 2**.
PR 2 bakes "one SQLite file per package" and the manifest schema into storage, and those
are the concepts a generic core would want to own.

**Positioning note.** GovInfo's own MCP server (public preview) offers two
discovery-oriented tools. Discovery is the easy half; the differentiating value here is
the search interface. That asymmetry is the reason search infrastructure is worth
treating as an asset at all.

#### If the option is declined and a second type is written by copy — the extraction bill

Deferral is a reasonable choice, and the cost of later extraction is **dominated by
discipline during the copy, not by the decision to copy.**

| Category | Extraction cost |
|---|---|
| Identical and stays identical (escaping, RRF, BM25 config) | trivial — diff and pick one |
| Same shape, different vocabulary (walk, addressing, subdivision) | mechanical, bounded, visible |
| **Semantics that quietly drifted in the copy** | **expensive — re-litigating design with two live consumers** |
| Two verification suites asserting the same properties in different words | routinely underestimated |

**The expensive row is the whole risk.** Copy-paste-modify duplicates the *design*, not
just the code, and the copy makes decisions that never received the scrutiny the first
set did. This project's entire defect history is undocumented assumptions surfacing as
HIGHs; two copies means two assumption sets, one of which was never argued.

**Two existing constraints make this much cheaper than it looks:**

- **§10 forbids cache migrations** — discard and rebuild. On-disk divergence between two
  implementations costs a rebuild, not a migration. The cache is disposable by design.
- **§15 forbids new dependencies** — everything is stdlib plus `sqlite3`, so there is no
  dependency graph to untangle.

**Cheap forcing function, if the copy route is taken:** declare a shared-module manifest
— files that must remain byte-identical across implementations, edited in both or
neither — and add a CI check that diffs them. Roughly an hour of work, and it keeps the
expensive row empty. Without it, drift is silent and the extraction may simply never
happen.

**The one thing that must not diverge** is quoted-segment detection. If the second
implementation reimplements it, V4's guarantee does not transfer and the new type needs
its own V4 from scratch.

### Bounded hug extension for interposed clauses — DEFERRED, not rejected

**What it would do.** Allow one interposed `(…)` parenthetical, or one
`, as {amended|added|redesignated} by …,` clause, between a citation and its amendatory
verb. Recovers the 12–14 NDAA units A5 knowingly drops.

**Why it is not being done now.** A5's strict adjacency rule was settled hours earlier
precisely to close a precision hole, the lost units still report `is_amendatory: true`,
and n is 12–14 on a single document with 0 on hr1. One bill's drafting idiom is not a
corpus finding. Relaxing a just-settled gate on a single-document signal is how the
longhand hole got there.

**The strongest argument for doing it anyway, recorded so it is not lost.** The loss is
**systematic, not random**. It fires on `as amended by` interpositions, which by
definition mark provisions that have been amended before — high-traffic, frequently
touched sections — and on UCMJ-article parentheticals, which concentrate the loss in one
subject area of the NDAA specifically. A 4–5% loss biased toward the most heavily amended
provisions is a different thing from a 4–5% loss spread evenly, and if `amends` is ever
used for discovery ("which bills amend 10 U.S.C. 3501") that bias hits the queries most
likely to be asked.

**The trap, if this is ever implemented.** The interposed clause frequently *contains its
own citation* — `Section X of title 10, United States Code, as amended by Public Law
118-31, is further amended` names a public law that this bill does **not** amend. A naive
relaxation makes the interposed clause transparent for the outer cite **and** brings the
inner cite into hugging range of the same verb, manufacturing exactly the class of false
positive V13 just removed, in the newly-approved `public_law` form. The clause must be
skipped **for the outer citation only**; citations inside it are ineligible. This
asymmetry is easy to state and easy to get wrong.

Note also the interaction with the named-Act rule: §6 resolves only the parenthetical in
`Section 3 of the Food and Nutrition Act of 2008 (7 U.S.C. 2012)`. A `(…)` interposition
allowance touches the same construction from the other side.

**What would flip this to A6.** The idiom appearing at material rate in a third document
beyond NDAA and hr1, **and** a bounded implementation showing 0 added false positives on
a ≥30 hand sample that specifically includes interposed-clause citations. Both, not
either.

### `cited_authorities` — unresolved citation tokens

An alternative to resolving IRC cites: emit them **unresolved** in a separate field,
e.g. `cited_authorities: ["45F(a)(1)"]` — literal captured section tokens with no U.S.
Code claim attached. This sidesteps §6 entirely (nothing is resolved to a named Act) and
fixes the bare-anchor coverage problem, since the operative clause carries the section
number even when it drops the Act name.

**Hard constraints, all three required if this is ever built:**

1. **Reuse the same amendatory-verb proximity gate as `amends`** — emit only when
   "Section X … is/are amended/repealed" fires. Without the gate it drowns in internal
   navigation: bills are wall-to-wall "subsection (b)", "paragraph (1)", bare
   self-references. That is the same naive-flood failure that shorthand-without-verb was
   rejected for.
2. **Never format values to look resolved.** `45F(a)(1)` is fine; anything shaped like
   `26 U.S.C. 45F` is not, however obvious the mapping seems in context.
3. **The field description the model sees must state that the tokens are unresolved
   literals scoped to the enclosing document and cannot be joined across bills or
   codes.** The model is precisely the consumer that will otherwise try.

**What it gives:** "this unit amends something numbered 45F." **What it does not give:**
a cross-act citation filter.

**Open shape question:** a separate field, or one `amends` list with a `resolved`
discriminator per entry? The latter unifies the concept but complicates the common case,
which is currently a flat `list[str]`. Decide when scoping, not now.

---

### Cross-version section content-fingerprint diff — DEFERRED (follow-on, not this feature)

**The idea (recovered from the 2026-08-09 maintainer probe, and scoped out by its own proposer).**
The version-difference finding in §17's Group F establishes that these tools surface **structural**
divergence between two versions for free (`get_bill_toc` comparison — title counts, missing
subtitles, one-sided headers) but leave **content/value** changes under an *identical header*
invisible (a rate moving 3.5% → 1%), because no query finds them unless you already suspect them.
The proposed closer: **align sections across versions on identity — `header` text plus
amended-citation set — rather than on `section_id`, then flag pairs that match on identity but
diverge on body.**

**Why it is a different feature, not a spec amendment.** The current tools are per-version
retrieval; this is a cross-version *comparison* that produces a candidate-change list. It does
**not** violate the settled *no amendment-direction inference* line — it reports "these two
sections are the same provision and the body changed," not which way. But it is new surface and
new machinery, and the proposer explicitly called it a follow-on. **Adopting it is a requirements
decision, not recorded here as adopted.**

**Design notes to keep if it is ever built:**

1. **Do not anchor on `amends` alone** — the tool contract already says `amends` is a convenience,
   not complete (F3/F8), so it will miss alignments. The signal is **`header` + `amends` +
   `byte_length` delta together**: match on header (and amends where present), then flag an
   identity-match with a body/byte divergence as a candidate worth a human read.
2. **It produces a candidate list, not a verdict.** The output is "these section pairs probably
   changed materially" — the consumer still reads them. That keeps it on the retrieval side of the
   retrieval-vs-analysis line the Group F finding drew.
3. **The value it adds is exactly the case priors cannot cover:** a content change under an
   unchanged header, which structural TOC comparison and query search both miss. Test it on an
   **obscure** bill (per the Group F methodological rule) — a famous bill's changes are already in
   the model's priors and would not exercise the feature.

**Status: deferred, unrejected.** No measurement against it; it addresses a real, characterized
gap. It waits on a requirements decision and on PR 2 (a cross-version diff wants the cache, or it
re-indexes both versions every call).

---
