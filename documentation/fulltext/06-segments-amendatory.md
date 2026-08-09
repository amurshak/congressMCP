*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 6. The segment model — how `match_contexts` survives flattening

**Do not flatten a chunk into a single `text` field.** If you do, a match can no longer
be attributed to operative text, quoted material, or a header, and the whole safety
mechanism in §7 collapses. This is the load-bearing structural decision of the change.

### Storage

```sql
CREATE TABLE units (          -- addressable chunks
  id INTEGER PRIMARY KEY,
  section_id TEXT NOT NULL UNIQUE,
  ancestor_path TEXT NOT NULL,      -- JSON array of {type, enum, header}
  header TEXT,
  display_text TEXT NOT NULL,       -- segments concatenated in ordinal order
  byte_length INTEGER NOT NULL,
  is_amendatory INTEGER NOT NULL,
  amends TEXT NOT NULL              -- JSON array, possibly empty
);

CREATE TABLE segments (
  id INTEGER PRIMARY KEY,
  unit_id INTEGER NOT NULL REFERENCES units(id),
  ordinal INTEGER NOT NULL,
  context TEXT NOT NULL CHECK (context IN ('operative','quoted','header')),
  text TEXT NOT NULL
);
```

`display_text` is what `get_bill_section` returns — segments in ordinal order, so it
reads naturally with the operative verbs surrounding the quoted material.

### Context assignment — exactly one per segment

- A segment inside `<quote>` **or** `<quoted-block>` → `quoted`.
- Otherwise, a segment that is the unit's own `<header>` → `header`.
- Otherwise → `operative`.

**Quoted-containment dominates.** A header nested inside quoted material is `quoted`,
not `header`. One context per segment, deterministic.

### Both quoting constructs count

Bill DTD has two: `<quoted-block>` for block-level insertions, inline `<quote>` for
word- and phrase-level strike-and-insert. **The icebreaker case is the inline form.** A
walker tracking only `<quoted-block>` classifies precisely the dangerous case as
`operative`. *Confirm the exact element names in step V1.*

### Quoted-span delimiters — rendering, not storage

Live: `S 3548` (166 bytes) renders as *"is amended by inserting or section 2 of this Act
after any violation of the Sherman Act ."* — the inserted string and the anchor string
are **indistinguishable from each other and from the operative prose.**

**This is not cosmetic; it is the precondition for §8's stated strategy.** §8 declines
direction inference on the grounds that returning the full unit lets operative verbs
travel with the quoted text so the model can read it. Strip the delimiters and the model
*cannot* read it: "inserting X after Y" is unrecoverable once X and Y have no boundaries.
Declining to infer direction server-side is only defensible while the client is given
material it can actually parse. Restoring the delimiters is what makes the non-goal in §8
a choice rather than an abdication.

**Rule: delimiters are a rendering function of `(text, context)`, applied at
serialization. They are never stored.**

- `segments.text` stays canonical and clean. It is the single source of truth.
- `display_text` and snippets are both **rendered** from segments in ordinal order,
  wrapping `quoted` spans in delimiters.
- The FTS-indexed text is `segments.text`, unrendered.

Rendering at serialization rather than storing a divergent `display_text` is the load-
bearing part. If display and indexed text were two stored strings, snippet offsets
computed against one would not map onto the other, and §8 requires snippets be drawn from
**quoted segments specifically** — offset drift there reintroduces exactly the failure V4
guards. One stored string, one pure rendering function, no drift.

`unicode61` strips punctuation, so leaving delimiters out of the index costs nothing in
recall; that is a happy consequence, not the reason.

> **V16 settled this — render unconditionally.** 5,176 quoting elements sampled across
> all three fixtures: opening and closing marks are absent from source character data at
> 0.0% in every cell but one (0.1% of 680 NDAA `<quoted-block>`). **The tag is the
> delimiter**; the text inside carries none. No normalization step is needed.
>
> **The 0.1% exception is not optional to handle.** This section's own post-condition —
> no `display_text` contains doubled delimiters — fails on that class if source marks are
> not stripped. Strip defensively at extraction; it is a few characters of code and it
> makes the rendering function total rather than correct-at-99.9%.
>
> **The `S 3548` orphaned `" .` was not a source delimiter** — those do not exist in the
> data — and the earlier reading of it in this spec was an inference from a single repro
> that measurement overturned. It is the separate spacing artifact named below.
>
> **Loose end, worth one query before closing:** if the corpus carries no quotation marks,
> that `"` character still came from somewhere. Confirm its origin — the 0.1% class, a
> report-side quoting convention, or a third path not yet sampled. "No source delimiters
> exist" and "an orphaned delimiter appeared in output" cannot both be true without a
> third explanation, and the unexplained one is the kind that turns out to be a different
> defect.

#### The header/text boundary must be rendered — F12's sibling, and the precedent is V16

`(A) In general At the written request…` — the source carries no `.—` between a heading and
its text; GPO's renderer inserts it. Declining to insert punctuation the source does not
contain is the cautious reading, **but V16 already settled the principle in the other
direction.** Quotation marks are absent from source character data at 0.0%; this spec renders
them anyway, because **a structural distinction the source makes must survive serialization.**
The source makes the header/text distinction structurally, via the `<header>` element.

**Losing it has a measured cost:** §17's B1 consumer **rebuilt the subparagraph hierarchy
itself** and warned its reader it had done so.

**Ruling: render the boundary, but do not imitate GPO.** The requirement is that the boundary
be *visible*, not that it match `.—`. A neutral separator is preferable precisely because
`.—` inside quoted material could be mistaken for source text — the doubling hazard V16
handled by stripping. This is F12's sibling and belongs with it, not as a new defect.

Also fix inline-quote spacing so terminators do not orphan (`"referred to as the Service
)"`, trailing `" .`). Punctuation adjacent to a closing delimiter belongs outside it,
without an inserted space.

> **FIXED `5a54833`.** Segments carry an `inline` flag and **one join function serves both
> `display_text` and `render_segments`**, so the two cannot disagree about where a boundary
> falls. Inline quotes no longer take the block separator; quoted material keeps its sibling
> paragraph boundaries. Which elements are inline is **measured, not assumed** — `<quote>`
> carries `display-inline` on **0 of 38,277** occurrences, `<quoted-block>` is block on 7,535
> and explicitly inline on 208, so the document declares it and the only inference is for
> `<quote>`, where the absence is total.
>
> **It was not free, and "whitespace only" was wrong.** Rendering changes `display_text`
> length → moves byte-split boundaries → changes chunk content → changes bm25 → **reorders
> results.** The V20 replay measured it: 27/30 rounds exact, 1 differing in chunk indices, 2
> at section level with one section dropping out of a top-8. **0 known-correct targets lost.**
>
> **General consequence worth carrying forward: any change to text rendering propagates into
> ranking through chunk boundaries.** F11 and F10 are response fields and touch no text, so
> they are safe. **PR 2 is not** — see below.

> **Live 2026-08-06 — this is one defect, and only the delimiter half shipped.** §17's
> Group A and B runs show **segment joining does not distinguish inline from block**, in
> both directions:
>
> - Inline `<quote>` spans are separated by `\n\n`, the **block** separator, fracturing
>   single sentences across paragraph breaks
>   (`(commonly known as the` ⏎⏎ `"Indian Civil Rights Act of 1968") is amended—`).
> - `header` segments join their text with **no** separator, producing
>   `(2) Annual basis.—(A) In general.—At least once each year…` as a run-on.
>
> A consumer reconstructed the subparagraph hierarchy itself and warned the reader it had
> done so. §5 states inline elements join without added whitespace and block elements
> separate with `\n\n`; the rule is right and the implementation has it inverted for these
> two cases. Fix them together — they share a cause.

**This stays inside §8.** Delimiters are rendering fidelity — reproducing a distinction
the source document makes. They assert nothing about which span is being struck and which
inserted. `match_contexts` remains the machine-readable signal; the delimiters are the
human- and model-readable one.

### What `quoted` claims — and what it does not

`quoted` asserts one thing: **the text sits inside a `<quote>` or `<quoted-block>`
construct in the source markup.** It is a structural fact, not a semantic judgement, and
in particular it is *not* a claim that the text is being inserted by the bill.

The distinction became concrete with the two live intro cases (§14): `117hr2471enr`
`S:804` quotes "Indian Civil Rights Act of 1968" as a *commonly-known-as* short title, and
`116hr133enr` `S:401` quotes a report title. The Bill DTD wraps both in `<quote>`, so both
are labeled `quoted` — correctly, and consistently with the main path — even though the
short title is part of the operative sentence identifying the amendment target rather than
inserted text.

**This is the right behavior and the reason should be on the record.** Classifying by
usage — short title versus inserted text — is semantic inference about what a quotation
construct *means*, which is the same thing §8 refuses when it declines direction
inference. The structural rule is mechanical, checkable, and identical across every path.
The alternative is a judgement call that fails silently.

**The consequence for consumers, and it is a real one:** a hit with
`match_contexts=['quoted']` means "this matched inside a quotation construct," so a
consumer must not read it as "the bill is inserting this." §8's answer applies unchanged —
the full unit is returned, the operative verbs travel with the quoted material, and the
model reads it. `quoted` narrows where to look; it does not decide what the bill does.

### Committee-struck text — excluded, not a fourth context (F4 ruling, 2026-08-06)

**Decision: never emit an addressable unit from a `changed="deleted"` subtree, and disclose
the exclusion actively.** `match_contexts` stays three-valued: `operative`, `quoted`,
`header`.

**Measured facts this rests on.** There is no `<DELETED>` element — the Bill DTD marks
deletion two ways, `changed="deleted"` on structural elements and inline `<deleted-phrase>`.
In the wild only the attribute occurs: **219 instances across 80 packages, 162 on
`<section>`; `deleted-phrase` measured 0.** 38 of 80 reported packages carry it; **zero in
any enrolled, engrossed, or introduced probe.** The dominant pattern is the Senate committee
substitute — *strike all after the enacting clause and insert the part printed in italic* —
and on `119s4726rs` **16 of 33 sections are struck while the parser emits all 33.**

#### Why not a fourth context

**`match_contexts` answers "where in the document did this come from," not "is this still
current."** `operative` / `quoted` / `header` are **provenance** categories. Struck text is a
**currency** category — it *was* this bill's text and the committee removed it. Adding
`deleted` puts a temporal distinction into a spatial field, which is this spec's most-repeated
error in reverse: **two questions collapsed onto one signal.**

**A committee substitute is a version boundary inside one package.** The struck sections are
the predecessor text; the substitute is the current text. §3 already owns that problem —
precedence, resolution, disclosure — and the struck text is **always recoverable as the prior
version**, because anything struck in a reported version was present in the version before
it. Nothing is lost by excluding it; a second retrieval path would duplicate machinery that
exists.

**And a fourth context would preserve the live defect.** Today `get_bill_section("1")`
resolves **uniquely, with no ambiguity error, to the struck text** — document order puts it
first. Labelling it `['deleted']` leaves that resolution intact and relies on the consumer
reading a passive field. **§17 measured what happens to passive fields at the floor: the
caveat was dropped.** A citation to struck text is a citation to something the bill as
reported does not say.

#### Why not opt-in retrieval, and why not refusing reported versions

**Opt-in (`include_struck=True`) adds a parameter for a capability that already exists.**
The use case — *what did the committee remove* — is served by fetching the prior version and
diffing, which these tools already do. And a parameter is weaker than a passive field for a
consumer that does not know it exists.

**Refusing `rh`/`rs` outright is too blunt and contradicts §3.** 42 of 80 reported packages
carry no struck markup at all, the precedence table now ranks reported versions at 20, and
reported text is what a chamber actually votes on. Refusal turns a legitimate question into a
hard error.

#### Three specifics that make the exclusion safe

**1. The carve-out binds every unit-emitting path** — discovery, structural subdivision, and
byte fallback. Stated as an enumeration because a rule scoped to its discovery path has now
failed four times in this codebase (A4, A5, `extract_intro_segments`, `client_handler`).

**2. Disclosure is active, not passive.** Emit a response-level note naming the **count**
excluded and stating that the struck text is retrievable as the prior version. §17 showed
`version_resolution_note` being read and acted on by a consumer while `match_contexts` was
ignored by the same class of consumer. **Use the mechanism that demonstrably propagates.**

**3. Assert `deleted-phrase` stays at zero.** Do not implement inline handling on
speculation — measured 0 across 80 packages. Add a corpus assertion that fires if it ever
appears, the same shape as the subdivision-coverage assertion. A zero that nothing watches
becomes a latent hazard; that is the intro-labelling lesson.

#### The `#2` suffix was masking this, and that is its own finding

18 ids on `119s4726rs` carry V8's collision suffix because the struck original and the
substitute are **two versions of the same section sitting side by side**, and search ranks
`S:9` and `S:9#2` adjacently with nothing distinguishing them.

**The collision handler silently succeeded, and in succeeding it hid the duplication.** V8
was built for genuine duplicate enums across divisions — a legitimate case where two distinct
provisions share a number. This is a different case wearing the same shape, and the mechanism
could not tell them apart.

After the carve-out, `#2` from this cause should fall to **zero**; confirm it does. Then
consider whether a silently-applied disambiguation suffix should be silent at all — **a
mechanism that quietly resolves an anomaly prevents anyone from learning the anomaly
occurred.**

### No segment-producing path may hard-code a context

**Every path that emits segments classifies per child.** `quoted` for `<quote>` and
`<quoted-block>`, `header` for the unit's own header, `operative` for everything else.
There is one classification rule and every path uses it.

> **Defect, found 2026-08-04, fixed.** `extract_intro_segments` hard-coded
> `Segment("operative", …)` with no per-child classification, unlike `extract_segments`
> which flips context on `quote`/`quoted-block`. Consequence: a `<quote>` in the matter
> preceding the first subdivision of an over-size section — `Section 5 is amended by
> striking "the Secretary" in the matter preceding paragraph (1)—` — was emitted as
> **operative**, presenting inserted text as enacted text. V4-class, and independent of
> the phantom-unit defect.
>
> **Latent, not absent, in the fixture set: 0 of 53 subdivided sections across both
> bills.** The trigger is ordinary drafting — a section large enough to subdivide, with
> real subdivision children, and a strike/insert quote before the first child. Rare
> enough to miss two large bills; common enough that it lands eventually.
>
> **Why nothing caught it.** The re-emission probe reads 0 quoted words in parent units
> under *both* "no re-emission" and "mislabeled to operative" — a mislabel produces zero
> quoted words in the parent by construction. Two different properties collapsed onto one
> number, and every existing check treated 0 as the expected answer.
>
> **Fix:** delegate each intro child to `extract_segments` rather than flattening it with
> `element_text`. Same logic as the main path, which is the point.

**This is the third instance of one recurring failure: a correctness rule scoped to the
path where it was discovered.** A4 scoped the quoted carve-out to *discovery* and missed
*subdivision*. A5 scoped the amendatory-verb gate to the *shorthand* citation form and
missed *longhand*. This scoped per-child classification to `extract_segments` and missed
`extract_intro_segments`. When a rule is stated, state the set of paths it binds, and
check that the set is exhaustive rather than the one path in front of you.

### Ancestor headers are NOT indexed into descendants

Only the unit's own header is a `header` segment. Repeating a title header into every
descendant floods results.

### `is_amendatory` — precise definition

True iff **either**:
- the unit contains ≥1 `quoted` segment, **or**
- any `operative` segment matches, case-insensitively:
  `\b(is|are) amended\b` | `\bby striking\b` | `\bby inserting\b` | `\bby adding\b` |
  `\bredesignat(e|ing|ed)\b` | `\bis repealed\b`

Otherwise false. No other heuristics.

> **V18, 2026-08-04 — the quote branch is gone; `is_amendatory` is verb-only.** It
> previously also fired on the presence of a quotation construct. Hand-coding found
> **35/35 such units non-amendatory** — appropriations account headings, defined terms,
> report titles, short titles, fund names, quoted findings — and dropping the branch flips
> 3,651 units True→False, **none carrying an `amends` target**, so §6's coherence invariant
> is preserved and was measured corpus-wide rather than argued.
>
> **A quotation construct is a structural marker, not evidence of amendment** — the same
> lesson A5 recorded for citation forms. Fourth instance of the recurring pattern: a
> correlate treated as sufficient.

**What `is_amendatory` guarantees, stated rather than assumed.** It is **verb-based**. It
will miss amendatory constructions that use no recognized verb form; the measured residual
is ~1% of amendatory units (`is to read as follows`, addressed by a targeted addition to
`AMENDATORY_RE` — never to the shared `_AMEND_VERB`, which gates `amends` and whose
per-form precision V13 measured at 0/30). Those units remain retrievable with
`match_contexts=['quoted']`, so the gap is flag completeness, not retrieval.

This belongs in the tool description too. §6 directs consumers to `is_amendatory` **and**
`match_contexts` as the reliable pair, with `amends` as the convenience — so
`is_amendatory` carries an expectation `amends` does not, and its boundary should be
stateable.

### `amends` — three accepted citation forms, all verb-gated

> **Amendment A1 (intentional, PR 1).** This section originally pinned `amends` to the
> longhand form alone. Measured against live enrolled text, that fires well on defense
> bills and is nearly blind to reconciliation bills, which amend named Acts cited in
> U.S. Code shorthand: **NDAA 328/807 amendatory units populated; 119hr1 only 14/293**,
> where longhand appears 39x but shorthand appears 373x. Since §13 selects hr1
> *precisely for* amendatory density, 14/293 defeated the fixture's purpose. Not silent
> drift — a spec-calibration miss the implementation corrected.

Populated from **either** form, both resolving to a U.S. Code target. Results are a
**list**, de-duplicated and sorted. Empty list when nothing matches.

> **Amendment A5 (V13, 2026-08-04). The longhand form is verb-gated too.** The spec held
> that longhand is "self-anchored (it names the target), so it needs no amendatory verb,"
> and gated only the shorthand. **Measured, that is backwards.** NDAA: 695 longhand
> matches, 411 firing on non-amendment cites; hr1: 32 matches, 88% non-amendment. Worse,
> 126 NDAA units (21% of the 599 populating `amends`) report targets while
> `is_amendatory` is false — they amend nothing and name targets anyway.
>
> **The error was conflating two different properties.** Longhand *is* self-anchoring in
> the sense the spec meant: it resolves to a U.S. Code provision without surrounding
> context. But `amends` needs two things — that the citation resolves, **and** that this
> unit amends it — and only the first is context-free. "Section 101(a)(16) of title 10,
> United States Code" is the standard way to cross-reference or define *any* U.S. Code
> provision; most occurrences are definitional, `subject to`, or `notwithstanding`.
>
> Generalize the lesson: **no citation form is self-gating.** Resolvability and
> amendatory relationship are independent, and a future form that "obviously names its
> target" gets a verb gate like the rest. Same family as A3 and A4 — a confident spec
> claim the measurement refuted.

**All three forms require an amendatory verb hug.** Resolution differs; the gate does not.

| Form | Pattern | Emits |
|---|---|---|
| longhand USC | `Section {sec} of title {title}, United States Code` | `{"kind": "usc", "cite": "{title} U.S.C. {sec}"}` |
| shorthand USC | `{title} U.S.C. {sec}` | same |
| public law | `(Public Law {c}-{n})` / `{v} Stat. {p}` | `{"kind": "public_law", "cite": "P.L. {c}-{n}"}` |

**The verb hug, stated once as a number — this closes the open window question.**
Between the end of the citation and the amendatory verb, permit **only** the characters
`)`, `,`, `;` and whitespace. Nothing else. The verb set is
`is|are [further|hereby] amended` and `is|are [further|hereby] repealed`.

This is an adjacency rule rather than a character window, and it is better than one:
exact, testable, and identical across all three forms. Do not implement per-form
variants — a single predicate, three resolvers.

**The verb detector used here must be the same one that sets `is_amendatory`**, or a
strict subset of it. Otherwise the invariant below holds by coincidence rather than by
construction, and coincidences drift.

**Structural post-condition — assert this permanently, not just as a regression test:**

```
amends != []  ⟹  is_amendatory == true
```

One direction only. The converse is explicitly **not** guaranteed: named Acts, the IRC by
bare section number, and unresolvable targets all leave an amendatory unit with
`amends: []`, by design.

This invariant is what should have caught the longhand leak, and it would have caught it
without hand-sampling 30 units. The 126 incoherent NDAA units are its violation, and
they are worth more than the percentage tables — a rate needs a judgement call about
what counts as a false positive, while an incoherent unit is unambiguously wrong on the
document's own terms. **Prefer invariants over rates wherever one is available.**

#### A5's recall cost — measured, accepted

Measured before merge rather than asserted, per this section's own demand. NDAA drops
411 longhand matches:

| Drop class | Count | Genuine amendments lost |
|---|---|---|
| no verb (definitional / `subject to` / `notwithstanding` / applicability) | 388 | 0 of 30 sampled |
| distant verb belonging to a neighboring kept cite | ~7 | 0 — all 23 classified |
| **interposed clause** (`, as amended by Z, is further amended`; `(article N of the UCMJ) is amended`) | ~12–14 | **yes — genuine, lost** |

Shared-verb construction (`Section A …, and section B …, are amended`): **1** occurrence
in NDAA, 0 in hr1. The spec suspected this might be common in appropriations drafting; it
is not.

**Invariant confirmed on live data:** incoherent units went 126 → 0 (NDAA) and 12 → 0
(hr1). Coverage fell as predicted, 599 → 391 units (NDAA) and 117 → 101 (hr1).

**State the loss at the precision the sampling supports.** The distant-verb class was
enumerated exhaustively (23/23), so "0 lost" there is solid. The no-verb class was
sampled 30 of 388 at 0 genuine — which bounds the rate at roughly **10% at 95%
confidence**, i.e. up to ~37 further units, not zero. The honest figure is **12–14
confirmed lost, upper bound near 50**, rather than a flat ~4–5%. The decision does not
change; the number goes in the record at its real width. If someone later wants to
narrow it, the cheap move is enlarging that 30 — not re-arguing the gate.

**Accepted as designed cost, because the contract holds.** Every lost unit still reports
`is_amendatory: true`, so no consumer is blinded — `amends` misses a resolved cite, which
is precisely the "convenience, not completeness" contract this field carries. §6 does not
treat coverage as a KPI, and this is the shape of loss it was written to accept.

> **The acceptance argument has a gap, found live 2026-08-06 (§17, independent trace
> review). Partial extraction was never considered.**
>
> `D:G/…/S:7223.` returns `amends` listing **§§ 2158, 2159(c), 2160** while its own snippet
> also says title 14 is amended **"in section 2161."** The unit is `is_amendatory: true`
> **and** carries a non-empty `amends` that is silently short by one.
>
> A5 was accepted on the reasoning that a unit losing a cite still flies the amendatory
> flag, so the consumer knows to read further. **That holds when a unit loses *all* its
> targets and `amends` comes back empty — an obviously incomplete answer.** It does not hold
> when three of four targets are present: a populated array reads as *the* answer, and
> nothing distinguishes "these are the targets" from "these are three of the targets."
>
> **Partial population is worse than empty**, for the same reason this spec has ruled six
> times over: two conditions collapsed onto one signal, with the more dangerous one
> unsurfaced.
>
> **This does not reopen A5** — the verb gate is right and the precision numbers stand. It
> reopens the *disclosure* question, and it should be measured alongside V19 rather than
> ruled on from one instance: **how often does a unit's operative text contain more
> resolvable citations under an amendatory lead-in than `amends` reports?** That count, not
> the empty-array count, is what decides whether a completeness signal is warranted.

**The known-boundary test must pin the property that makes the loss acceptable.**
`test_a5_known_recall_cost_interposed_clause_drops_longhand_cite` should also assert the
dropped unit reports `is_amendatory: true`. Without that assertion, a future change to
amendatory detection could silently remove the fallback that justifies A5's recall cost,
and the test would still pass while the tradeoff underneath it had evaporated.

**Named-Act titles are never resolved.** In "Section 3 of the Food and Nutrition Act of
2008 (7 U.S.C. 2012)", only the parenthetical is used. This red line does not move.

**Observed after A1:** hr1 14 → 114 units, NDAA 328 → 502. The thrifty-food-plan section
now returns the four Food and Nutrition Act cites where it previously returned `[]`.
**These counts predate A5** and will fall when the longhand gate lands — expect NDAA to
shed roughly 411 spurious targets and 126 incoherent units. A drop here is the change
working, not a regression.

### `amends` optimizes precision at the cost of recall — by design

**Coverage is not a KPI.** The figures above are recall-side counts recorded to show the
shorthand form was worth adding; they are **not** a target to push higher. Rising
coverage should prompt suspicion, not satisfaction. **V13's false-positive rate is the
only metric that governs this field.**

**Precision was unmeasured until V13, and the concern was justified — but pointed at the
wrong form.** The 328 → 502 jump was too coarse to reveal leakage, and the leak turned
out to be in the form the spec never worried about. Shorthand and P.L. measured 0/30
false positives each; longhand measured badly enough to require A5.

### Not covered — named Acts, including the IRC by bare section number

**Named Acts are never resolved.** This includes the Internal Revenue Code cited by bare
section number. Such units still report `is_amendatory: true` with `amends: []`.

The IRC *could* in principle be mapped — IRC section numbers align 1:1 with Title 26
(IRC §45F = 26 U.S.C. 45F). **The reason not to is statability, not difficulty.**

The anchor "of the Internal Revenue Code of 1986" is present on some clauses and absent
on others **within a single section**. Measured on 119hr1: 42 anchored occurrences
bill-wide, yet the operative clause of `S:70401` (employer child-care credit) reads bare
— "Section 45F(a)(1) is amended by striking 25 percent". Same section, both forms.

An IRC mapping would therefore make `amends` populate or not **based on per-clause
drafting style.** That matters more here than it would elsewhere because **the consumer
is a model.** A field populated inconsistently for the same kind of provision teaches a
false inference — that empty `amends` means "not amending the U.S. Code," when it
actually means "the drafter omitted the Act name in this clause." Silent inconsistency
in a field a model reasons over is worse than uniform absence. An *unpredictable* rule
is the failure; an *incomplete* one is not.

The invariant "`amends` resolves U.S. Code citations, never named Acts" is one sentence a
consumer can reason about. IRC→26 destroys it.

**The slope has substance.** The next request is SSA→Title 42, where the numbers do
**not** align (SSA §1902 = 42 U.S.C. 1396a). It cannot be satisfied the same way, so the
precedent should not be set.

#### Measured: the same name resolves to different public laws in one document

The red line was argued from reasoning until 2026-08-04, when V15's unbiased pass found
the collision live in `BILLS-119s1071enr`:

| Named Act | Mentions | Distinct P.L. pairings in-document |
|---|---|---|
| Atomic Energy Defense Act (`S:3117`) | 41 | **1** — clean, unambiguous |
| Military Construction Authorization Act (`S:2309`) | 50 | **47** |

The Military Construction Authorization Act is enacted **per fiscal year**, so the same
title names dozens of different enactments *inside a single bill*. Any name→P.L. keying
resolves it to whichever pairing was seen first, silently and wrongly, for 46 of 47 uses.

**This is the strongest evidence the named-Act exclusion has.** It is no longer a slope
argument about a hypothetical future request — it is a document in the fixture set where
name-based resolution produces confident wrong answers at scale. Cite this case, not the
SSA hypothetical, when the question is reopened.

Note that the clean case exists too (Atomic Energy Defense Act: 41 mentions, 1 pairing,
40 bare uses recoverable). **A rule that works for one Act and fails for the next is
exactly the unpredictability this section refuses.** One clean instance is not a
counterargument; it is the trap.

**Consumers should use `is_amendatory` and `match_contexts` to identify amendatory text.
`amends` is a convenience, not a completeness guarantee.** State this in the tool
description, not only the README.

### Public Law / Statutes-at-Large targets — APPROVED with one open denominator (V15)

**Invariant, amended:** `amends` resolves **U.S. Code and Public Law citations, never
named Acts.** Still one sentence a consumer can reason about, which was the test.

**V15 result.** NDAA `enr` + 119hr1 `enr`, 48 P.L.-amending units: ~88% carry an explicit
`P.L.`/`Stat.` cite, 5–13% named-Act only, 0–7% back-reference only, and **zero sections
mix an explicit cite with a short form among their own clauses.** That last figure is the
IRC signature — `S:70401` carrying both forms inside one section is what refused the IRC —
and its absence is the reason this clears where the IRC did not.

**Approved on that basis**, gated on the **same amendatory-verb hug** the shorthand U.S.
Code form uses, and scanning `operative` segments only, exactly as §6 already requires for
both existing forms.

#### The denominator, supplied — record the finding at its actual strength

V15's unbiased re-run (2026-08-04, `BILLS-119s1071enr` @ `enr`, every amendatory unit, no
query selection) supplies the number this section demanded:

| Frame | P.L.-target clauses | sections | explicit | bare name | back-ref | sections ≥2 clauses | of those, mixed |
|---|---|---|---|---|---|---|---|
| whole package | 44 | 38 | 89% | 5% | 7% | **5** | **0** |
| Division G (Coast Guard) | 14 | 9 | **100%** | 0% | 0% | **4** | **0** |

**Five sections is low single digits, which is the case this spec said in advance would
make the finding "not yet contradicted" rather than "clears."** That standard holds now
that the answer came back favorable. The IRC signature is absent, and the observation
window in which it could have appeared is small. Proceed — but if this decision is
challenged later, the honest statement is *"zero mixing observed across five eligible
sections,"* not *"measured clean."*

**An independent signal does strengthen it.** No section cites a single target both by
P.L. number and by bare name — same-target consistency, which is a tighter property than
form-mixing across different targets and does not depend on the ≥2 denominator. Division
G, the body this project cares most about, is 100% explicit with zero bare cites.

**One assumption underneath the table is unmeasured.** Back-references were excluded from
the recoverable population on the grounds that "such Act" resolves from the section's own
antecedent. In a section naming two different Acts, that antecedent is ambiguous. The
exclusion justifies dropping 7% of clauses, so it is worth confirming rather than
assuming — count sections where a back-reference follows more than one distinct named Act.

#### Corpus notes to keep on the record

- **The motivating repro is unaccounted for.** Item 4 was raised on
  `S 4977 → P.L. 119-38; 139 Stat. 656`. V15 finds S 4977 in the 119th is the REDACT Act —
  antitrust, `is` only, **zero P.L. amendments**. The measurement corpus is therefore not
  the document that raised the issue, and that document has not been identified. The
  finding stands on NDAA + hr1 regardless, but an unexplained repro is a loose thread:
  either the original report mis-identified the bill, or there is a vehicle neither of us
  has looked at.
- **Coast Guard lineage is covered directly**, via Division G of `s1071enr` — the body an
  earlier record wrongly called unreachable. It is the cleanest frame in the corpus.
- **Classification is regex-heuristic** and the percentages carry noise, as reported. The
  two decisive signals are ordinal rather than precise, so they survive it. The
  denominator above does not depend on precision either.

#### Precision — validated

V13 ran 2026-08-04: P.L. targets measured **0/30** false positives on a hand sample,
matching the shorthand U.S. Code form. The verb hug is carrying its weight here despite
public law cites appearing routinely as effective-date anchors and `notwithstanding`
references. See `10-fixtures-verification.md`.

#### Shape: objects with a `kind` discriminator — my call, not the implementer's

`amends` becomes `list[dict]`:

```jsonc
"amends": [
  {"kind": "usc",         "cite": "14 U.S.C. 5601"},
  {"kind": "public_law",  "cite": "P.L. 119-38"}
]
```

Sorted by `(kind, cite)`, de-duplicated on the pair. Empty list when nothing matches, as
before.

**Why not a separate `amends_public_law` field.** It keeps the common case flat, and it
recreates the exact defect that opened item 4: a consumer reading only `amends` sees a
P.L.-amending unit as amending nothing. Two fields make "empty `amends`" ambiguous again —
"amends nothing" or "amends something recorded elsewhere" — and §6's whole argument
against the IRC is that a field a model reasons over must not be silently ambiguous.

**Why not a flat list of mixed strings.** `["14 U.S.C. 5601", "P.L. 119-38"]` forces the
consumer to parse string syntax to know what kind of target it holds. That is the same
objection that produced `node_kind` in §5, and it should be answered the same way in both
places or neither.

**Why breaking the shape is free today.** Nothing has merged; §4's keyword-only change is
also still pending for the same reason. The cost of this change is zero now and permanent
the day a consumer depends on `list[str]` — same reasoning as the `CHUNK:` id rename.

**Deliberately not included:** decomposed `title`/`section` fields on `usc` entries. No
consumer need has been demonstrated for them, and speculative structure is how a schema
gets wide. Add them when something asks.

**`cited_authorities` (§14b) stays a separate field if it is ever built.** Its hard
constraint 2 — never format an unresolved token to look resolved — is harder to hold
inside a list whose other entries are resolved cites. The discriminator gives it a home
later if that judgement changes; it is not an invitation.

#### P.L. and Statutes-at-Large name the same enactment twice

`P.L. 119-38; 139 Stat. 656` is one target cited two ways. **Prefer the P.L. form.** Emit
a `Stat.` cite only where no P.L. form accompanies it in the same citation instance, and
never both. `kind` is `public_law` for either form; the distinction is in the `cite`
string.

---

---

## 8. The amendatory trap — the correctness issue that matters most

> *Section 2304(a) of title 10, United States Code, is amended by striking
> "icebreaker" and inserting "polar security cutter".*

A hit on "icebreaker" here lands in text the bill is **removing**. Reported as "what the
bill says," that is the exact opposite of the truth.

### Section-level flags saturate

`is_amendatory` at unit level is true for most units of a reconciliation bill. A flag
true nearly everywhere carries no information. **The discriminating signal is where each
match landed** — which the segment model preserves.

### `match_contexts` is a set

```
match_contexts: list[str]    # subset of {"operative", "quoted", "header"}
```

**Union across all matching segments and all queries.** Because whole units are
returned, one unit routinely matches in both operative and quoted segments; a scalar
would force the walker to pick, and any such rule is sometimes wrong.

**Rule the model must apply, stated in the tool description:** if `"quoted"` appears
**at all**, the hit may include language the bill is removing — even when `"operative"`
is also present. Presence of `"quoted"` governs.

### Snippet selection

**If any matching segment has context `quoted`, the snippet must be drawn from a quoted
segment**, even when a different segment ranked higher. The caution must be visible in
the snippet, not merely in a flag. Include the immediately preceding operative text in
the snippet window where available.

### Explicit non-goal: direction inference

Strike-and-insert yields two structurally identical quoted spans distinguishable only by
surrounding verb order — before `striking ... in each place it appears`, multi-clause
amendments, redesignations, and amendments-to-amendments. Return the full unit so
operative verbs travel with the quoted text, populate `match_contexts`, let the model
read it. A confidently-wrong direction is worse than no answer.

---
