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

All byte limits are **UTF-8 encoded bytes of the returned text field**, not of the
serialized JSON payload. State this in docstrings.

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

Live: `S 4042, T:II/S:204` reports `byte_length: 73` — its own header — while its subtree
runs ~60,700 bytes across 14 children. **The bill's largest section reads as its
smallest**, and a consumer budgeting its next call reads that as "cheap, and probably
empty." It will skip the section that matters.

Additive, not a redefinition. `byte_length` keeps its current meaning — callers already
read it as own-text size, and §4's `max_bytes` is defined against the returned text field.

| Field | Meaning |
|---|---|
| `byte_length` | UTF-8 bytes of **this unit's own** `display_text` |
| `subtree_byte_length` | `byte_length` + the same for **every descendant**, recursively |

**Pin the containment semantics, or two implementers will compute this differently.** A
subdivided parent's `display_text` is its **own header and intro only, exclusive of its
children** — that is what the 73-byte reading shows the implementation already does, and
it is the right choice: no duplicated text in storage, and it is what makes §5's "return
the section's own header and intro text plus child descriptors" expressible. The
consequence is that §5's "parent fits `max_bytes` → return whole section" row is served by
**concatenating children at read time**, not by reading a parent field. Say so in the
implementation.

Because the parent is exclusive, `subtree_byte_length = own + Σ descendants` involves no
double counting. For a leaf, **emit it equal to `byte_length` rather than null** — a
consumer sorting or thresholding on one field should not have to coalesce.

Present on **hits, TOC nodes, and section-response children**. The highest-value place is
`get_bill_toc`: §4 calls it a navigation aid, and size-per-branch is most of what makes a
navigation aid useful for deciding where to descend.

`max_bytes` continues to govern **returned text only** and is never compared against
`subtree_byte_length`.

```jsonc
// get_bill_section  (envelope fields as above, plus)
{
  "section_id": "D:H/T:I/S:3501",
  "ancestor_path": [ /* ... */ ],
  "header": "Polar security cutter program",
  "text": "...",
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

```jsonc
// error envelope — every failure path
{
  "error": {
    "code": "version_not_available",     // stable machine-readable string
    "message": "S. 1071 exists but has no 'ih' version.",
    "detail": {"available_versions": ["is", "es", "enr"]},
    "remediation": "Retry with one of the listed versions, or omit version."
  }
}
```

### `matched_queries` — per-hit query attribution, and an input to the next call

For each hit, the subset of the caller's queries that produced it. **Load-bearing in
multi-query calls, not decorative.**

Because §7 phrase-quotes every query, a two-word query is a **phrase, not an OR**. So an
unexpected hit in a multi-query call is explained by *which sibling query matched it* —
never by tokenizer behavior. `matched_queries` answers "why did this hit appear"
directly, and a consumer should read it before drawing conclusions about retrieval.

It also closes the iteration loop §7 opens: §7 instructs the model to pass several
phrasings at once, and `matched_queries` is how it learns **which phrasing to drop** on
the next call. Say this in the tool description rather than leaving it for a careful
reader to notice.

**Field decisions:** `ancestor_path` is an **array of typed nodes**, not a string.
`amends` is a **list**. `score` is the RRF score. `govinfo_url` is the **public details
page**, never the API URL (which would carry the key). `cache.index_hit` and
`cache.version_hit` are separate — version resolution can hit the network while the
index is cached.

### `timing` — server-measured, on all three tools

> **Amendment A2 (intentional, PR 1).** Added because the calling model is often the
> only harness and cannot see call durations; it was inferring latency from gaps between
> `version_resolved_at` stamps, which also include its own token generation. Server-side
> timing makes the tool self-instrumenting.

Semantics, to be documented in the tool descriptions:

- **`total_ms` is server COMPUTE time — a lower bound on client-observed latency.** It
  is stamped before response serialization and MCP transport, neither of which is
  measured. State this explicitly so the number is not over-read as end-to-end latency.
- `resolve_ms` and `download_ms` are **split** rather than a single `fetch_ms`. In PR 1
  they always run together, so the split looks redundant — it is not. Once PR 2
  persists the index, a warm index with an expired version TTL produces a network call
  alongside `index_hit: true`, and a lumped `fetch_ms > 0` next to a cache hit reads
  like a bug. Null either field when that leg did not run.
- `search_ms` is null on `get_bill_section` and `get_bill_toc`.
- In PR 1, with `version_resolution: "fresh"` and `index_hit: false`, every leg runs on
  every call — there is no caching yet.

**Measured profile on real enrolled bills** (supersedes any assumption that parse
dominates):

| Leg | Share of wall clock | Stability |
|---|---|---|
| fetch (resolve + download) | **73–92%** | **High variance — 1480–2818ms across calls seconds apart** |
| parse | 165–510ms | Stable per document; scales with size |
| index | 38–140ms | Stable per document; scales with size |
| search | <1ms | Stable |

Ranges widened by the V2 live run on the 9.36 MB NDAA `enr` (fetch 2.82s / parse 0.51s /
index 0.14s / total 3.88s — fetch 73%). Fetch remains dominant and remains the only
high-variance term on every document measured.

**Two conclusions for PR 2**, both of which the §10 design already satisfies:

1. The dominant win is skipping the re-**fetch**, not the re-parse. Caching buys
   variance elimination as much as raw latency — fetch is the only high-variance term.
2. This confirms that caching the **built index** rather than the raw XML is the correct
   shape. A warm hit opens the `.db` and skips fetch, parse, and index together, so
   §10's "do not retain raw XML" decision stands: the bytes are not what gets cached.

The `timing` block adds ~80 bytes per response and does not threaten the budget below.

### Budget

The "two calls, under ~10KB" figure is a **typical-flow target for the search step**,
not a hard per-response cap. Search hits at `max_hits=10` land around 2–3KB.
`get_bill_section` defaults to 25,000 bytes of text because real sections legitimately
run that long and truncating all of them is worse than a larger payload; the hard
ceiling is 100,000.

---

---

## Container nodes must be fetchable, or marked unfetchable

**Live defect, §17 Group C, 2026-08-06.** `get_bill_toc` returns container nodes —
`D:C/T:XXXI`, `D:C/T:XXXI/ST:A`, `/ST:B`, `/ST:C` — and `get_bill_section` rejects them with
`section_not_found`. **The TOC's id namespace is a superset of the section namespace and
nothing marks the difference.** `node_kind` reports `structural` for a subtitle and for a
leaf section alike, so a consumer drilling down the TOC cannot tell which ids it may fetch.

The `section_not_found` remediation compounds it: *"Use `search_bill_text` or
`get_bill_toc`…"* — the id came from `get_bill_toc`.

**Fix: resolve containers by returning header plus `children` descriptors.** §5 already
defines that response shape for a subdivided parent exceeding `max_bytes`; reusing it makes
the TOC → section → child path work end-to-end and introduces nothing new. A container is
simply a parent whose own text is a heading.

If containers are instead left unfetchable, they must be **marked** — a distinct
`node_kind`, or a `fetchable` flag. Leaving them indistinguishable from leaf sections is the
only option that should not survive, because it guarantees a failed call for any consumer
that navigates the way the TOC invites.

## `get_bill_toc` depth disclosure — three degradations, three signals (F11, 2026-08-08)

One flag was answering two questions and hiding a third. The fix (`a52d54a`) keeps
`toc_truncated`'s meaning and adds two fields, so a consumer never has to diff request against
response to learn what happened:

- **`toc_truncated`** — more exists below the returned tree. Unchanged.
- **`depth_reduced`** (bool) + **`requested_depth`** — the node budget served a **shallower
  depth than requested** (`s1071` 5→3, `hr2471` 4/5→2). Distinct from `toc_truncated`: the two
  disagree on 3 of 5 `s1071` rows, and that disagreement is the information that did not exist
  before. `hres463` is clean on both.
- **`toc_note`** — the **third** degradation: even depth 1 can exceed the node cap, in which
  case the requested depth **is** served but the node list is **cut**. That is neither
  truncation-below nor depth reduction, and it was disclosed by nothing at all. Do **not** reuse
  the internal `node_capped` as `depth_reduced` — it reports a reduction that never happened
  (sabotage-checked: the substitution fails the depth-1 test). The reduction note is also not
  suppressed when hidden-section advice is present, because `hidden_note` phrases its remedy in
  terms of the depth *served* and alone reads as though the request was honored.

---

## Amendment A6 — `timing` ships one field, not two (2026-08-06)

**Spec said:** `timing` carries split `resolve_ms` / `download_ms`, each nulled when that leg
did not run. **Implementation ships a single `fetch_ms`.**

**Accepted, and recorded rather than left silent.** Every PR 1 call is cold — resolve and
download both always run — so the split conveys nothing today. It becomes informative only
when PR 2 lets a warm index coexist with a network call, at which point `download_ms: null`
against a populated `resolve_ms` is a real signal.

**This is a reasoning-driven amendment, not a measurement-driven one**, which distinguishes
it from A1–A5. It is recorded under the same convention because an undocumented divergence is
the failure mode the convention exists to prevent — not because it carries the same evidential
weight.

**Trigger to revisit, stated so it is not forgotten:** the first PR 2 change that makes
`index_hit: true` possible. At that point split the field, or delete `timing` from §9 if the
split still is not wanted.
