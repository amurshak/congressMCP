*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 4. Tools

Everything after `*` is keyword-only. Required parameters precede it.

```python
search_bill_text(
    congress: int,
    bill_type: str,
    number: int,
    queries: list[str],
    *,
    version: str | None = None,
    max_hits: int = 10,
) -> dict

get_bill_section(
    congress: int,
    bill_type: str,
    number: int,
    section_id: str,
    *,
    version: str | None = None,
    max_bytes: int = 25_000,
) -> dict

get_bill_toc(
    congress: int,
    bill_type: str,
    number: int,
    *,
    version: str | None = None,
    depth: int = 2,
) -> dict
```

`get_bill_toc` is a **navigation aid, not the answer path.**

### Input validation — hard caps, reject before touching FTS

| Input | Cap | On violation |
|---|---|---|
| `len(queries)` | 8 | Error |
| Each query length | 200 chars | Error |
| Empty / whitespace / tokenless query (no alphanumeric after tokenization) | — | Error naming the offending query |
| `max_hits` | 1–50 | Clamp, note in response |
| `max_bytes` | 1_000–100_000 | Clamp, note in response |
| `depth` | 1–5 | Clamp, note in response |
| TOC nodes returned | 500 | Return shallower depth, say so |

All byte limits are **UTF-8 encoded bytes of the returned text field**, not of the serialized JSON payload. State this in docstrings.

---

---

## 9. Response schemas

Return typed models, not bare dicts. Concrete shapes:

```jsonc
// search_bill_text
{
  "package_id": "BILLS-119s1071enr",
  "version": "enr",
  "version_resolution": "fresh",        // fresh | cached | cached_offline
  "version_resolved_at": "2026-08-03T14:22:01Z",
  "version_resolution_note": null,
  "source_format": "bill_dtd",
  "last_modified": "2025-12-19T03:11:48Z",
  "govinfo_url": "https://www.govinfo.gov/app/details/BILLS-119s1071enr",
  "cache": { "index_hit": true, "version_hit": true },
  "timing": {
    "resolve_ms":  412.3,   // congress.gov version resolution
    "download_ms": 1112.4,  // GovInfo document download
    "parse_ms":    165.8,   // Bill DTD parse + chunk
    "index_ms":    38.0,    // FTS5 build
    "search_ms":   0.4,     // search_bill_text only; null on get_bill_section/toc
    "total_ms":    1729.0
  },
  "sections_indexed": 4127,             // top-level addressable units, incl. synthetic
  "chunks_indexed": 5310,               // units after subdivision
  "chunks_searched": 5310,
  "queries_used": ["icebreaker", "polar security cutter"],
  "hits": [
    {
      "section_id": "D:H/T:I/S:3501",
      "ancestor_path": [
        {"type": "D",  "enum": "H",  "header": "Coast Guard Authorization Act of 2025"},
        {"type": "T",  "enum": "I",  "header": "Authorizations"}
      ],
      "header": "Polar security cutter program",
      "snippet": "...is amended by striking \"icebreaker\" and inserting...",
      "match_contexts": ["operative", "quoted"],
      "matched_queries": ["icebreaker"],
      "is_amendatory": true,
      "amends": ["14 U.S.C. 5601"],
      "score": 0.0328,
      "node_kind": "structural",
      "byte_length": 4211,
      "subtree_byte_length": 4211
    }
  ]
}
```

### `byte_length` vs `subtree_byte_length`

Live: `S 4042, T:II/S:204` reports `byte_length: 73` — its own header — while its subtree runs ~60,700 bytes across 14 children. **The bill's largest section reads as its smallest**, and a consumer budgeting its next call reads that as "cheap, and probably empty." It will skip the section that matters.

Additive, not a redefinition. `byte_length` keeps its current meaning — callers already read it as own-text size, and §4's `max_bytes` is defined against the returned text field.

| Field | Meaning |
|---|---|
| `byte_length` | UTF-8 bytes of **this unit's own** `display_text` |
| `subtree_byte_length` | `byte_length` + the same for **every descendant**, recursively |

**Pin the containment semantics, or two implementers will compute this differently.** A subdivided parent's `display_text` is its **own header and intro only, exclusive of its children** — that is what the 73-byte reading shows the implementation already does, and it is the right choice: no duplicated text in storage, and it is what makes §5's "return the section's own header and intro text plus child descriptors" expressible. The consequence is that §5's "parent fits `max_bytes` → return whole section" row is served by **concatenating children at read time**, not by reading a parent field. Say so in the implementation.

Because the parent is exclusive, `subtree_byte_length = own + Σ descendants` involves no double counting. For a leaf, **emit it equal to `byte_length` rather than null** — a consumer sorting or thresholding on one field should not have to coalesce.

Present on **hits, TOC nodes, and section-response children**. The highest-value place is `get_bill_toc`: §4 calls it a navigation aid, and size-per-branch is most of what makes a navigation aid useful for deciding where to descend.

`max_bytes` continues to govern **returned text only** and is never compared against `subtree_byte_length`.

```jsonc
// get_bill_section  (envelope fields as above, plus)
{
  "section_id": "D:H/T:I/S:3501",
  "ancestor_path": [ /* ... */ ],
  "header": "Polar security cutter program",
  "text": "...",
  "is_amendatory": true,               // RULED 2026-08-20 (F32) — same per-unit computation as search hits
  "amends": [{"kind": "usc", "cite": "14 U.S.C. 5601"}],   // ditto; empty list when none
  "node_kind": "structural",
  "byte_length": 4211,
  "subtree_byte_length": 60700,
  "truncated": false,
  "children": [                          // present when truncated or subdivided
    {"section_id": "D:H/T:I/S:3501/SS:(a)", "header": "In general",
     "node_kind": "structural", "byte_length": 2104, "subtree_byte_length": 2104}
  ]
}
```

> **`is_amendatory` and `amends` on `BillSectionResponse` — RULED 2026-08-20 (F32, §18; measured in §17's cold A1 ×3).** These fields existed only on search hits, and the section-direct path — the rational one for any consumer already holding a `section_id`, and the one §17's single-step prompts take by construction — returned no amendatory disclosure at all: the frame survived only as raw statutory text, which the cross-vendor floor flattened in 2 of 2 section-direct runs ("Section 141 requires the Air Force to maintain…") while the one search-path run, fed `amends` on the hit, led its answer with the amend frame. Semantics are **identical to the hit fields** — same per-unit computation, same `kind` discriminator, same V13 false-positive governance and A5 verb gate; this is exposure of an existing value on a second path, not new inference machinery, and per the carry-don't-reconstruct rule it must read the same stored value the search path reads. Minimal width deliberately: no `match_contexts` analogue (there is no query on this path) and no new note field yet.
>
> **Preregistration for the re-run (record the outcome either way):** *expected* — with the fields present, floor section-direct A1 names 9062(j)/the amend frame, grounded in the measured behavior that this consumer leads with `amends` when it is delivered (`2026-08-20T161031Z`); *falsified if* ≥2 of 3 section-direct re-runs still present the inserted text as the bill's own requirement with the fields verified present in the trace — which would show a passive schema field does not propagate on this path and the next rung is an **active** note (the `struck_text_note` form), not more width.
>
> **Outcome (2026-08-20, §17 fifth adjudication): expected direction, not falsified — on-path n=1 (PASS), because path choice proved consumer-chosen; the ≥2/3 escalation did not fire (1/3 overall frame-drop with fields present) and minimal width stands.** F32 is verified live at the consumer boundary; the denominator lesson is recorded in §17.
>
> **Container semantics — implementer call ratified with the semantics pinned (2026-08-20).** Structural containers (`D:`/`T:`/`ST:`) report `is_amendatory: false`, `amends: []`: a container's own text is its heading, headings do not amend (V18: 35/35 non-amendatory), and this matches `byte_length`'s own-text-exclusive-of-children precedent. **The fields describe the unit's own stored value — for a true container that is always false/empty, and that is a true statement, not a missing one.**
>
> **The subdivided-section caveat is NOT ratified as stated — it reintroduces F32's shape as an active mislabel on one path.** The implementer's docstring scopes the fields to "the addressed unit's own text." But this section's own read contract serves a subdivided parent that fits `max_bytes` by **concatenating children at read time** — so a large amendatory section whose amendatory verb sits in a child unit would return the full amendatory text under `is_amendatory: false`. That is worse than the pre-F32 absence: a false assertion sitting beside the text it mislabels, on exactly the sections (the oversized ones) where a consumer most needs the frame. `S:141` dodges it only by being a leaf. **Check-dead-defensive first — the contract is conditional on V22 (§14 file `10-fixtures-verification.md`), which measures whether any subdivided parent in the corpus has an amendatory descendant.** *If V22 finds ≥1:* the fields on `get_bill_section` must describe **the returned `text`** — OR of `is_amendatory` / deduplicated union of `amends` over exactly the units whose text is included in the response (still carried stored values; the aggregation is mechanical, not new inference; a truncated or descriptor-only response includes no child text and keeps the own-unit values, which also preserves the container ruling above unchanged). *If V22 finds 0 with a non-zero denominator:* own-text semantics stand everywhere, the case is recorded dead-defensive, and the docstring note is the guard. The docstring's current wording is correct today and must change only if the aggregation contract activates.
>
> **V22 MEASURED 2026-08-20 — 391 of 602 subdivided parents are the mislabel shape (341 assembled under default `max_bytes`), and the adjacent container-path shapes are live too (185 chunk-only prefixes, 975 assembled containers). The aggregation contract ACTIVATES — F33 (§18).** The ruling, in its final form, is one sentence: **`is_amendatory` and `amends` describe the response's `text`.** Concretely:
>
> - **The participating set is exactly the units whose text is included in the response** — all-or-nothing per unit by this section's read contract (assembly happens only when the subtree fits; truncation returns descriptors, never partial children). `is_amendatory` is the OR over that set; `amends` is the union over that set, **deduplicated by (`kind`, `cite`) identity, in document order** — deterministic, so it is testable. No cap: the list is bounded naturally because assembly is bounded by `max_bytes`.
> - **This binds every assembling path, not the path V22 was aimed at** — subdivided parents, chunk-only prefixes, and assembled structural containers — per the correctness-rule-binds-every-path convention; V22 measured all three shapes live.
> - **The container ratification above is hereby narrowed to descriptor-only responses**, where it remains exactly right: no text returned beyond the heading → own-unit `false`/`[]` is a true statement about the returned text. The two rulings are now the same rule applied to two response shapes.
> - **Values are carried, never recomputed** — the aggregate reads the same stored per-unit values the search path reports, extending the F32 conformance property (section == live hit) to: assembled-response fields == OR/union of the per-unit values of the included units.
> - **Acceptance is set-based against V22's populations, not count-based:** the 341 default-assembled found parents report `is_amendatory: true`; the 261-subset reports non-empty `amends`; the 198 parent-false/no-descendant-true rows stay `false`/`[]`; the 13 overlap rows stay `true`. The V22 script holds the sets; re-run it against the fixed field values and diff.
> - **Deliberately not built:** per-child `is_amendatory`/`amends` on child *descriptors* (the >100KB descriptor-only rows). No measured failure exists on that path — a consumer drilling down receives the fields on the child fetch, so every piece of text it actually reads arrives labeled. Reopen only on evidence.
>
> **VERIFIED AND CLOSED 2026-08-20** — implementation `fe17fa5` (one aggregation helper, values carried from the stored unit fields, contract stated independently in the tests), verify pass `668b357`: the V22 instrument now diffs the shipped tool against this contract on every id it examined — 3,216 calls, **0 mismatches across all eight populations**, reproduced by this session (exit 0, figures identical). **Correction to the acceptance enumeration above, caught by the implementer stating the contract independently:** "the 261-subset reports non-empty `amends`" used a denominator doing other work — 261 counts every found parent whose descendants cite, but 32 of those are descriptor-only under default `max_bytes` and *correctly* keep `[]` per this very ruling; the assembled-and-cited population is **229, and 229/229 report non-empty**. The ruling was never in tension with itself — the acceptance sentence was; this is the set-vs-count discipline applied to the spec's own acceptance text.

```jsonc
// error envelope — every failure path
{
  "error": {
    "code": "version_not_available",     // stable machine-readable string
    // load-bearing codes incl. (see §3 for the resolution/fallback contract):
    //   bill_not_found       — congress.gov 404; definitive, GovInfo fallback NOT consulted
    //   congress_unavailable — 5xx / non-JSON 200 / network; recoverable → triggers GovInfo fallback
    //   govinfo_unavailable  — GovInfo fetch failed definitively (incl. redirect-chain exhaustion, F22)
    //   version_not_available — bill exists, WELL-FORMED requested version does not (lists available)
    //   version_not_found     — the version string is malformed, not a version code at all
    //                           (pre-network guard at the shared load path; F38 ruling 2026-08-25 —
    //                           deliberate split: malformed vs absent demand different remediations)
    //   internal_error       — a genuine server fault; NOT a masked upstream/decode failure (F21/F22)
    //   govinfo_key_rejected — a key WAS sent and GovInfo returned 401. A keyless server must NOT wear this code (F31): "existing key rejected" sends the operator hunting a stale key that does not exist. Missing key is its own code (api_key_missing-shaped) naming the variables to set
    "message": "S. 1071 exists but has no 'ih' version.",
    "detail": {"available_versions": ["is", "es", "enr"]},   // MUST NOT carry secrets — see below
    "remediation": "Retry with one of the listed versions, or omit version."
  }
}
```

### `matched_queries` — per-hit query attribution, and an input to the next call

For each hit, the subset of the caller's queries that produced it. **Load-bearing in multi-query calls, not decorative.**

Because §7 phrase-quotes every query, a two-word query is a **phrase, not an OR**. So an unexpected hit in a multi-query call is explained by *which sibling query matched it* — never by tokenizer behavior. `matched_queries` answers "why did this hit appear" directly, and a consumer should read it before drawing conclusions about retrieval.

It also closes the iteration loop §7 opens: §7 instructs the model to pass several phrasings at once, and `matched_queries` is how it learns **which phrasing to drop** on the next call. Say this in the tool description rather than leaving it for a careful reader to notice.

**Field decisions:** `ancestor_path` is an **array of typed nodes**, not a string. `amends` is a **list**. `score` is the RRF score. `govinfo_url` is the **public details page**, never the API URL (which would carry the key).

> **Error `detail` must not carry secret-bearing URLs — the F15 rule, generalized (F22, `cfd459e`).** `govinfo_url`'s no-key rule is one instance of a wider contract: **any URL that reaches a response `detail` or a log must be stripped to `scheme+host+path`**, because it can carry secrets in its query string that are not the api_key. F22 surfaced the new vector concretely — a GovInfo redirect can target a CDN/S3 URL whose query string holds a **signed access token**, and F22 puts the next-hop URL into the error envelope's `detail`, so it strips the query before including it. Treat this as the standing rule for the whole error surface, not a per-field fix: the api_key was the first secret-in-URL (F15, §11); signed redirect targets are the second; assume a third. Cross-reference §11's credential hygiene. `cache.index_hit` and
`cache.version_hit` are separate — version resolution can hit the network while the index is cached.

### `timing` — server-measured, on all three tools

> **Amendment A7 (2026-08-25, maintainer): `timing` is emitted only when `CONGRESSMCP_VERBOSE` is set in the server environment.** What the spec said: `timing` ships on every response (A2, and A6's split restored in PR 2). What changed: it is now env-gated, absent by default. Why: a real consumer session weighed the telemetry blocks and the maintainer adopted the narrow version of its finding — `timing` is the only block that is **purely performance and never load-bearing for correctness** (six null fields on every warm hit), while `cache`, `version_resolution*`, and the disclosure notes are diagnostic-on-failure and stay always-on, because a failure that may not reproduce is worth their tokens on first occurrence. The consumer itself retracted its broader verbose-flag proposal on exactly this reasoning; §4's always-on telemetry decision otherwise **stands un-reopened**. A2's rationale (self-instrumenting tool) is preserved behind the env var, which is where an SRE lives anyway.

> **Amendment A2 (intentional, PR 1).** Added because the calling model is often the only harness and cannot see call durations; it was inferring latency from gaps between `version_resolved_at` stamps, which also include its own token generation. Server-side timing makes the tool self-instrumenting.

Semantics, to be documented in the tool descriptions:

- **`total_ms` is server COMPUTE time — a lower bound on client-observed latency.** It is stamped before response serialization and MCP transport, neither of which is measured. State this explicitly so the number is not over-read as end-to-end latency.
- `resolve_ms` and `download_ms` are **split** rather than a single `fetch_ms`. In PR 1 they always run together, so the split looks redundant — it is not. Once PR 2 persists the index, a warm index with an expired version TTL produces a network call alongside `index_hit: true`, and a lumped `fetch_ms > 0` next to a cache hit reads like a bug. Null either field when that leg did not run.
- `search_ms` is null on `get_bill_section` and `get_bill_toc`.
- In PR 1, with `version_resolution: "fresh"` and `index_hit: false`, every leg runs on every call — there is no caching yet.

**Measured profile on real enrolled bills** (supersedes any assumption that parse dominates):

| Leg | Share of wall clock | Stability |
|---|---|---|
| fetch (resolve + download) | **73–92%** | **High variance — 1480–2818ms across calls seconds apart** |
| parse | 165–510ms | Stable per document; scales with size |
| index | 38–140ms | Stable per document; scales with size |
| search | <1ms | Stable |

Ranges widened by the V2 live run on the 9.36 MB NDAA `enr` (fetch 2.82s / parse 0.51s / index 0.14s / total 3.88s — fetch 73%). Fetch remains dominant and remains the only high-variance term on every document measured.

**Two conclusions for PR 2**, both of which the §10 design already satisfies:

1. The dominant win is skipping the re-**fetch**, not the re-parse. Caching buys variance elimination as much as raw latency — fetch is the only high-variance term.
2. This confirms that caching the **built index** rather than the raw XML is the correct shape. A warm hit opens the `.db` and skips fetch, parse, and index together, so §10's "do not retain raw XML" decision stands: the bytes are not what gets cached.

The `timing` block adds ~80 bytes per response and does not threaten the budget below.

### Budget

The "two calls, under ~10KB" figure is a **typical-flow target for the search step**, not a hard per-response cap. Search hits at `max_hits=10` land around 2–3KB. `get_bill_section` defaults to 25,000 bytes of text because real sections legitimately run that long and truncating all of them is worse than a larger payload; the hard ceiling is 100,000.

---

---

## Container nodes must be fetchable, or marked unfetchable

**Live defect, §17 Group C, 2026-08-06.** `get_bill_toc` returns container nodes — `D:C/T:XXXI`, `D:C/T:XXXI/ST:A`, `/ST:B`, `/ST:C` — and `get_bill_section` rejects them with `section_not_found`. **The TOC's id namespace is a superset of the section namespace and nothing marks the difference.** `node_kind` reports `structural` for a subtitle and for a leaf section alike, so a consumer drilling down the TOC cannot tell which ids it may fetch.

The `section_not_found` remediation compounds it: *"Use `search_bill_text` or `get_bill_toc`…"* — the id came from `get_bill_toc`.

**Fix: resolve containers by returning header plus `children` descriptors.** §5 already defines that response shape for a subdivided parent exceeding `max_bytes`; reusing it makes the TOC → section → child path work end-to-end and introduces nothing new. A container is simply a parent whose own text is a heading.

If containers are instead left unfetchable, they must be **marked** — a distinct `node_kind`, or a `fetchable` flag. Leaving them indistinguishable from leaf sections is the only option that should not survive, because it guarantees a failed call for any consumer that navigates the way the TOC invites.

## `get_bill_toc` depth disclosure — three degradations, three signals (F11, 2026-08-08)

One flag was answering two questions and hiding a third. The fix (`a52d54a`) keeps `toc_truncated`'s meaning and adds two fields, so a consumer never has to diff request against response to learn what happened:

- **`toc_truncated`** — more exists below the returned tree. Unchanged.
- **`depth_reduced`** (bool) + **`requested_depth`** — the node budget served a **shallower depth than requested** (`s1071` 5→3, `hr2471` 4/5→2). Distinct from `toc_truncated`: the two disagree on 3 of 5 `s1071` rows, and that disagreement is the information that did not exist before. `hres463` is clean on both.
- **`toc_note`** — the **third** degradation: even depth 1 can exceed the node cap, in which case the requested depth **is** served but the node list is **cut**. That is neither truncation-below nor depth reduction, and it was disclosed by nothing at all. Do **not** reuse the internal `node_capped` as `depth_reduced` — it reports a reduction that never happened (sabotage-checked: the substitution fails the depth-1 test). The reduction note is also not suppressed when hidden-section advice is present, because `hidden_note` phrases its remedy in terms of the depth *served* and alone reads as though the request was honored.

**Generalized contract — one disclosure condition, one field; never `or`-substitute two notes.** `get_bill_toc` is the model: the depth clamp gets `toc_note`, and `version_resolution_note` is left untouched for version disclosure. Every tool must follow it.

> **F17 (ultrareview `bug_003`, 2026-08-09) — `version_resolution_note` is clobbered by the input-clamp note in the other three tools.** `search_bill_text`, `get_bill_section`, and `_container_response` set `version_resolution_note = note or loaded.resolved.version_resolution_note`. Python's `or` is a fallback, not a merge: when a caller trips the `max_hits`/`max_bytes` clamp on a bill that **also** carries a version warning (an unrecognized GPO code alongside `enr`), the version disclosure is **silently dropped** and the caller sees only *"Value 999 was clamped to 50."* The `_envelope` comment even says each tool "merges in the input-clamp note" — the intent was merge, the code substitutes. **This is the A3/§3 disclosure — the mechanism that warns a model it may be reading a silently-older version, the worst failure class — defeated on an input as ordinary as "asked for more hits than allowed,"** and the callers who trip the clamp are the least-experienced ones who most need it. It is also an instance of the *active disclosures must propagate* principle (F6): the propagation is what breaks.
>
> **Fix — two steps, both ruled (2026-08-10):**
>
> 1. **Stop the loss (done).** Never `or`-substitute; the interim merge (`" ".join(filter(None, [note, version_resolution_note])) or None`) preserves the data. Ship it.
> 2. **Then split into a dedicated field — RULED, adopt it.** Move the input-parameter clamp advisory (`max_hits`/`max_bytes`) to its own **`request_note`** on `SearchBillTextResponse` and `BillSectionResponse` (and the container response), leaving `version_resolution_note` to carry **only** version disclosures. This is a design call the implementer routed to the spec owner, and the merge alone does not settle it — because the merge *breaks the field's presence signal*: after it, `version_resolution_note != null` fires on clamps too, so a model keying on presence gets a **false version-warning on every clamp** (F17 in reverse). The split restores the clean biconditional and separates a **safety** disclosure from a **benign** advisory, so the model need not parse the string to tell which — the same reason `node_kind` (§5) and the `amends` kind-discriminator (§6) exist, and the same orthogonality `toc_note`/`depth_reduced` already have (F11). **Not speculative width** (§6): F17 proved the two notices co-occur, so separating them is correctness. **Free now, permanent once a consumer depends on the shape** — do it while nothing has shipped. `request_note` is the implementer's name and generalizes to any input advisory; the name is the cheap, revisable part, the separation is the ruling.
>
> Add a test on the **both-notes-populated** path — today's tests pass only because each fixture populates exactly one note. Severity: normal — a live safety-disclosure loss, not a crash.

---

## Amendment A6 — `timing` ships one field, not two (2026-08-06)

**Spec said:** `timing` carries split `resolve_ms` / `download_ms`, each nulled when that leg did not run. **Implementation ships a single `fetch_ms`.**

**Accepted, and recorded rather than left silent.** Every PR 1 call is cold — resolve and download both always run — so the split conveys nothing today. It becomes informative only when PR 2 lets a warm index coexist with a network call, at which point `download_ms: null` against a populated `resolve_ms` is a real signal.

**A6 CLOSED 2026-08-22 — the trigger fired and the split shipped** (`070560c`, PR 2 step 5): `fetch_ms` is gone; `resolve_ms`/`download_ms`/`parse_ms`/`index_ms` each null when the leg did not run. Certified live by the spec session: a fresh-resolve-over-warm-index call shows exactly the predicted signal (`resolve_ms: 1084.5`, `download_ms: null`, `index_hit: true`), and a within-TTL hit nulls every leg at `total_ms: 1.7`.

**This is a reasoning-driven amendment, not a measurement-driven one**, which distinguishes it from A1–A5. It is recorded under the same convention because an undocumented divergence is the failure mode the convention exists to prevent — not because it carries the same evidential weight.

**Trigger to revisit, stated so it is not forgotten:** the first PR 2 change that makes `index_hit: true` possible. At that point split the field, or delete `timing` from §9 if the split still is not wanted.
