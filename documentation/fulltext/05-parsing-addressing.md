*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 5. Section addressing

Two failure modes: **collision** (two divisions can each contain "Sec. 101") and **subdivision** (search hits may point at chunks, `get_bill_section` takes sections).

### Qualified form

Slash-joined `{type}:{enum}` components, outermost ancestor first.

| Code | Meaning | Kind |
|---|---|---|
| `D` | division | structural |
| `T` | title | structural |
| `ST` | subtitle | structural |
| `PT` | part | structural |
| `S` | section | structural |
| `SS` | subsection | structural |
| `PARA` | **`<paragraph>`** — a real enum from the document | structural |
| `SUBP` | `<subparagraph>` | structural |
| `CL` | `<clause>` | structural |
| `PRE` | preamble / whereas | synthetic |
| `RC` | resolving clause | synthetic |
| `U` | unnumbered addressable block | synthetic |
| `CHUNK` | **byte-bounded cut — not an enumeration of anything** | chunk |

```
"D:H/T:I/S:3501"                 a section
"D:H/T:I/S:3501/SS:(a)"          a real subsection
"D:H/T:I/S:3501/SS:(a)/PARA:(3)" a real paragraph
"D:H/T:I/S:3501/SS:(a)/CHUNK:3"  the third byte cut of an unsplittable subsection
"PRE:1"                          preamble of a resolution
"RC:2"                           second resolving clause
```

Search hits always return the fully-qualified form. Chunks are addressable.

> **The `PARA` collision was a spec defect, corrected here.** The subdivision chain in this section names four structural levels (`<subsection>`, `<paragraph>`, `<subparagraph>`, `<clause>`) and the original component list assigned a code to one of them, while reusing `PARA` for the byte fallback. Live: `S 4042, T:II/S:204` returned `SS:(a)/PARA:1…5` at 132/7999/7997/7997/3889 bytes, where `PARA:3` opens mid-sentence continuing `PARA:2`. A consumer citing "§204(a)(3)" from `PARA:3` is **wrong**, and the id is what told it that. Byte cuts now live in a namespace that cannot be mistaken for a bill enum.
>
> Note the near-miss that made this dangerous: real enums carry their delimiters (`PARA:(3)`) and byte cuts do not (`CHUNK:3`), so the two *were* distinguishable — by a parenthesis. That is not a distinction to hang correctness on.

> **Trailing periods are stripped at id construction (2026-08-06).** A section enum in the source is `1832.`, period included, and that period leaked into the id: `1832` returned `section_not_found` while `1832.` resolved. Three independent consumers tripped on it across two §17 groups. **An id component carries the enum's identity, not its typography** — the period is a heading terminator (`SEC. 1832.`) and appears in no citation. Strip **trailing** periods only; leave internal ones so decimal-style enums survive. Contrast `PARA:(3)`: parentheses *are* how that enum is written and they disambiguate level, so they stay.

**Id changes are free before PR 2 ships.** §10 versions the schema in the filename and forbids migrations — discard and rebuild. Bump the schema version and no persisted id is carried forward, so "this changes persisted ids" is not an objection to making the change now. It becomes one the day PR 2 ships.

### `node_kind` — on every hit, TOC node, and section response

```
node_kind: "structural" | "synthetic" | "chunk"
```

Per the Kind column above. **This is derivable from the id prefix and is stated anyway** — the point is not to add information but to remove the need for a consumer to parse an id string to decide whether a citation is safe to make. §6's reasoning about the IRC applies directly: the consumer is a model, and a model that must infer citability from string syntax will sometimes infer it wrong. One field, no parsing.

`structural` means the enum came from the document and may be cited. `synthetic` means this document has no enum for it and the id is ours — stable for the package, but not a citation. `chunk` means **the boundaries are arbitrary and the id refers to nothing the bill enumerates**; it may be fetched and must never be cited.

### Resolution behavior

| Input | Behavior |
|---|---|
| Fully-qualified section id | Return that section |
| Chunk id | Return that chunk |
| Parent of subdivided section, fits `max_bytes` | Return whole section |
| Parent of subdivided section, exceeds `max_bytes` | Return the section's own header and intro text, plus child chunk descriptors (id, header, bytes). `truncated: true`. **Never silently return only the first chunk.** |
| Bare enum, unique match | Resolve — accepted convenience |
| Bare enum, multiple matches | Error listing every qualified match. **Never guess.** |

> **F19 refinement (2026-08-14, `e17ee04`) — a subdivided parent's own intro can itself be chunked, and that must not change the row above.** When a parent's own header+intro alone exceeds `MAX_UNIT_BYTES` (the **index-time** unit cap, 8 KB — distinct from the read-time `max_bytes`), the intro is split into the parent's **own** `CHUNK` children (`S:1/CHUNK:1…`), ordered **ahead of** the structural children so reading order is preserved. Those own-text chunks *are* "the section's own intro text": `get_bill_section` **assembles them inline up to `max_bytes`**, exactly as when the intro was one blob — only the **structural** children (subsections) are returned as descriptors. **Inline assembly here is required, not optional** — returning the own-intro chunks as descriptors would force a re-fetch of the section's own prose and could surface only the first chunk, the precise failure the row above forbids. This closes the model gap that allowed F19: **every** unit-emitting path, the subdivided parent included, is now bound by `MAX_UNIT_BYTES`. Latent when fixed — 0 of 18 corpus bills had an oversize parent intro; `subtree_byte_length` conservation and inline reading order both verified preserved.

### Locate structural units by element name, not by expected parent path

> **Amendment A4 (spec error, found live).** §5 said "preamble / whereas clauses → `PRE:{n}`" without specifying where `<preamble>` sits. The implementation looked for `<whereas>` as a **direct child** of `resolution-body`/`legis-body`. The real GovInfo shape nests 15 `<whereas>` under a top-level `<preamble>` that is a **sibling** of `<resolution-body>`. Live result: hres463 indexed as `S:1` alone and the entire substance of a sense-of-the-House resolution was silently lost — exactly the "zero chunks silently returned" failure V5 was written to catch.

**Rule:** discover structural unit types by **local element name anywhere in the document tree**, namespace-agnostic. Do not key on expected parent paths. Bill DTD nesting varies by document type more than this spec anticipated, and a parent-path assumption is a guess about a schema that has not been fully enumerated.

**Mandatory carve-out — implement at the same time, not after:**

> **Never emit an addressable unit from inside a `<quoted-block>` or `<quote>` subtree.** A bill inserting a whole new section produces `<quoted-block><section><enum>…`. Under a generic walk that becomes a phantom unit for text the bill is *inserting*, not enacting — the amendatory trap at unit level, where `match_contexts` cannot help because the unit itself is spurious. Generic discovery without this carve-out is more dangerous than the parent-path assumption it replaces.

> **A4 extended — scope correction, third spec error of this kind.** The carve-out above sat under a heading about *discovery* and was silent on the **subdivision** chain. Live testing reproduces phantom units in **chunked quoted-block subtrees**: a section large enough to subdivide, whose `<subsection>`/`<paragraph>` children live inside the quoted block, is descended into by a subdivider that is generic over those element names. The discovery walk can be perfectly carved out and phantoms still appear.
>
> **The rule binds every path that emits an addressable unit** — discovery, structural subdivision, and byte fallback alike. State it once, apply it everywhere.
>
> Same family as A3 and A4 proper: the implementation was faithful to a spec that under-specified. Recorded here rather than in the defect table because the scope gap is the cause and the phantom units are the symptom.

Quoted material remains fully searchable as `quoted` **segments** of its enclosing real unit. It is never a unit of its own.

**A unit that cannot be subdivided without entering quoted material falls through to the byte fallback.** Do not descend to get a smaller unit; do not emit the parent oversized. `CHUNK:{n}` with clipped segments is the correct outcome, which is why segment clipping above is a prerequisite for this carve-out rather than a separate improvement.

### Synthetic units for sectionless documents

Simple resolutions use `<resolution-body>`, not `<legis-body>`, and often contain **no `<section>` elements**. A chunker written only against bill structure emits zero chunks and reports "no results" for a document it failed to parse — worse than a crash.

- Preamble / whereas clauses → `PRE:{n}`, document order, 1-based.
- Resolving clauses → `RC:{n}`.
- Any addressable block with no enum → `U:{n}`.
- Duplicate enum at the same level → append `#2`, `#3` in document order.

Synthetic ids must be **deterministic and stable for a given package**.

### Subdivision fallback chain

Chunks over the 8KB threshold subdivide by, in order: `<subsection>` → `<paragraph>` → `<subparagraph>` → `<clause>` → **byte-bounded split** producing `CHUNK:{n}` when no finer structural node exists. Apply recursively.

**The byte fallback must terminate in a hard cut that cannot exceed the cap:** blank line (`\n\n`) → sentence boundary → whitespace → **hard character cut**. Splitting on blank lines alone is not a bound. Live: an NDAA byte-fallback chunk reached **330 KB with zero `\n\n`** — a flattened table where every structural splitter missed. Assert post-condition: no emitted chunk exceeds the threshold.

**The quoted carve-out applies to this chain, not only to discovery.** See the amended carve-out below; the subdivision walk is a unit-emitting path and is bound by it.

**Byte-fallback chunks inherit clipped segments, with contexts preserved.** A byte cut splits a unit's text, and the resulting chunks are units in their own right (§6: the `units` table *is* the chunk table), so each needs its own `segments` rows. Derive them by **clipping the parent's segments to the chunk's span and carrying `context` through unchanged.** A segment straddling a cut yields one row on each side, same `context`.

This is not a detail. Without it, a chunk falling entirely inside a `<quoted-block>` has no quoted segment, reports `match_contexts: ["operative"]`, and presents inserted text as what the bill says — **V4's guarantee failing at chunk level, on the largest amendatory sections, which are exactly the ones that get chunked.** Assert: for every unit, the concatenation of its segments equals its `display_text`, and no chunk of a parent containing quoted segments reports zero quoted segments while covering a quoted span.

**Do not copy a parent's header down into its chunks as a `header` segment.** §6 already forbids indexing ancestor headers into descendants; a byte cut has no header of its own. Live, all five chunks of `S 4042, T:II/S:204/SS:(a)` carried "In general". If that string is a `header` **segment** it is indexed five times and floods results — verify which it is. Carrying the parent header as a **display/breadcrumb field** is fine and useful; indexing it is a defect.

### Text extraction rules

- Match elements by **local name**, namespace-agnostic.
- Inline elements (`<external-xref>`, `<term>`) join **without** added whitespace; block elements separate with `\n\n`. **`<quote>` is not a plain inline join** — see "Quoted-span delimiters" in §6. The original blanket rule here is what stripped the delimiters live.
- Normalize runs of whitespace to single spaces within a block.
- **Drop** `<page-break>` and pagination/running-header artifacts.
- **Skip `<toc>` subtrees entirely.** The NDAA's table of contents repeats every section header verbatim; indexed, it returns plausible hits with valid `ancestor_path` ranked against real ones and corrupts hit counts.
- Footnotes: append at the end of their containing unit, prefixed `[footnote]`.
- Missing enum → synthetic `U:{n}` as above.

---
