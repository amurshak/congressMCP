*(congressMCP bill-text spec — see `00-INDEX.md` for the file map. This file is the **user-facing** draft, not internal spec; it satisfies the §12 README deliverable and adds a usage guide. Placement is flexible — surface it at the repo's docs root / server README when PR 2 ships.)*

# congressMCP Bill Text Search — User Guide (DRAFT)

> **Draft, and written from the spec rather than the shipped source.** It describes the tools' *specified contract*; runtime numbers are the V-step measurements, cited inline. Items marked **(PR 2)** are not yet implemented. Verify against the shipped build before publishing.

## What this adds

Full-text search over the **actual text of congressional bills** — fetched from GovInfo, parsed, and indexed locally — rather than proxied API summaries. Three tools:

- **`search_bill_text`** — find language across a bill
- **`get_bill_section`** — fetch one addressable unit of a bill
- **`get_bill_toc`** — see a bill's structure

They are **self-sufficient**: give them `congress` + `bill_type` + `number` and they resolve the version, fetch the document, parse it, and index it on their own — no other tools required.

## Read this first: bills mostly *amend* existing law

This is the single most important thing to understand before trusting a result. A bill rarely states policy outright; it **amends** existing statute — inserting, striking, redesignating. So a search hit can land on text the bill is **removing**, or on text it is **inserting into** existing law, and neither is the same as "what the bill requires."

Every hit carries two signals. Use them:

- **`match_contexts`** — a subset of `{operative, quoted, header}`. **If `quoted` appears at all**, the matched language may sit inside a quotation construct (inserted or struck text) — *even when `operative` is also present*. Presence of `quoted` governs.
- **`is_amendatory`** — `true` when the unit amends existing law.

**Example.** *"Section 2304(a) of title 10, United States Code, is amended by striking 'icebreaker' and inserting 'polar security cutter'."* A hit on **icebreaker** is the word being **removed**; `match_contexts` includes `quoted`. Reported as "what the bill says," that is the opposite of the truth.

## Query semantics — literal phrases with stemming

Queries match as **literal phrases with stemming**. **Not** semantic, **not** bag-of-words.

- Supply short **exact phrases** you expect to appear verbatim (`"polar security cutter"`), not descriptions (`"icebreaker replacement program"`).
- Prefer several **distinct concepts** over paraphrases of one — each query is an independent vote, so N paraphrases weight that concept N×.
- Up to **8 queries** per call; `matched_queries` tells you which query produced each hit, so you know which phrasing to drop next.
- **Zero hits?** The response carries `query_diagnostics` per dead query: `terms` (the stems the tokenizer produced), `absent` (terms not in the index), and a `verdict` — **`phrasing`** (all terms present, so rephrase) or **`absent_term`** (a term is missing, so stop).

## `amends` is a convenience, not a completeness guarantee

`amends` lists U.S. Code and Public Law citations a unit amends. Read it as citations **found**, not citations **present** — a populated list is *not* proof it is the whole list, and nothing distinguishes three-of-three from three-of-four. It resolves **U.S. Code and Public Law only**, **never named Acts** (including the Internal Revenue Code by bare section number). To decide whether text is amendatory, rely on **`is_amendatory` + `match_contexts`**, not `amends`.

## The tools

```python
search_bill_text(congress, bill_type, number, queries, *, version=None, max_hits=10)
get_bill_section(congress, bill_type, number, section_id, *, version=None, max_bytes=25_000)
get_bill_toc(congress, bill_type, number, *, version=None, depth=2)
```

- **`search_bill_text`** — ranked hits, each with `match_contexts`, `is_amendatory`, `amends`, a `snippet` (drawn from a quoted segment when any match is quoted), `section_id`, `ancestor_path`, and `score`. `version=None` resolves to the latest authoritative version.
- **`get_bill_section`** — one unit's full text. An oversized unit returns a heading plus child descriptors instead of raw text. Accepts synthetic ids for preamble, resolving-clause, and undivided bodies (`PRE:`/`RC:`/`U:`). Bare vs trailing-period ids both resolve (`804` and `804.`); a genuinely ambiguous id returns `ambiguous_section_id` with the qualified matches.
- **`get_bill_toc`** — a **navigation aid**, not the answer path. Reports size per branch (`subtree_byte_length`) so you can decide where to descend.

## Disclosures the tools surface — watch for these fields

- **`version_resolution_note`** — which version was selected and why (e.g., an unrecognised GPO code, or a failed-passage version chosen for want of an alternative).
- **`struck_text_note`** — sections a committee struck were **excluded**; the note names the count and points at the prior version where the struck text is recoverable.
- **`query_diagnostics`** — see *Query semantics*.
- **`depth_reduced` / `requested_depth` / `toc_note`** — TOC degradation: depth served shallower than asked, and/or the node list cut. `toc_truncated` separately means more exists below.

## Operational

- **No new API key.** The bill-text tools use the **same congress.gov key** you already have — both `api.congress.gov` and `api.govinfo.gov` sit behind `api.data.gov`. (Users assume otherwise; they are wrong.)
- **Network egress:** `api.congress.gov` (metadata / version resolution) and `api.govinfo.gov` (bill content). Nothing else.
- **First-call latency:** **~3.9 s cold** on a large enrolled bill (NDAA measured: fetch 2.82 / parse 0.51 / index 0.14 / **total 3.88 s**). Set client timeouts accordingly. In PR 1 every call re-indexes (**~4.4 s**) — there is no cache yet.
- **Rate limits:** independent buckets — **36,000/hour** GovInfo, **20,000/hour** congress.gov — so indexing cannot starve the other tools.

### Not yet implemented — PR 2

- **Where data lives:** resolved cache path per platform — **(PR 2)**.
- **Disk:** 500 MB cap, how to change it, `congressmcp cache clear` — **(PR 2)**.
- **Offline behaviour:** explicitly cached versions queryable offline; `version=None` offline is best-effort and labelled `cached_offline` — **(PR 2)**.

---
