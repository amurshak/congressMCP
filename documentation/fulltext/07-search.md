*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 7. Search

### FTS5 table — external content over `segments`

```sql
CREATE VIRTUAL TABLE seg_fts USING fts5(
  text,
  content='segments',
  content_rowid='id',
  tokenize='porter unicode61 remove_diacritics 2'
);
```

**Population — external content does NOT auto-populate.** `optimize` optimizes an existing index; it does not build one. Required sequence:

```sql
-- after all INSERTs into units and segments:
INSERT INTO seg_fts(seg_fts) VALUES('rebuild');
INSERT INTO seg_fts(seg_fts) VALUES('optimize');
```

Omitting `rebuild` yields an empty index that fails silently.

**Ranking:** `bm25(seg_fts)` — in SQLite **more negative ranks better**, so `ORDER BY bm25(seg_fts) ASC`. No column weighting in v1 (single column). Deterministic tie-break: `ORDER BY bm25(seg_fts) ASC, units.section_id ASC`.

**Integrity:** `INSERT INTO seg_fts(seg_fts) VALUES('integrity-check')` during adoption validation **[PR2]**.

**Feature detection:** the local Python SQLite build may lack FTS5. Detect at startup. The **server must still start**; the three bill-text tools return a targeted capability error naming FTS5 and the Python/SQLite build.

### Query escaping — most likely shipped bug in this change

Query strings come from a model and land in MATCH syntax where `"` `*` `-` `^` `NEAR` `OR` `AND` `NOT` are operators. Applied to **every** query with no exceptions:

```python
def fts_literal(q: str) -> str:
    return '"' + q.replace('"', '""') + '"'
```

This also fixes phrase semantics: `Radiation Exposure Compensation` bare is three ANDed terms; quoted it is a phrase. Single words become literal terms, multi-word become phrases, operator injection becomes impossible. **Never pass model-supplied text to MATCH unquoted.**

### Multi-query fusion — reciprocal rank fusion, k=60

BM25 scores are **not comparable across queries**; summing or maxing raw scores lets a rare term dominate.

1. **Normalize and dedupe** queries first (casefold, collapse whitespace, strip). A repeated query must not gain extra weight.
2. Run each query independently against `seg_fts`, aggregating matched segments to their `unit_id`.
3. Take `candidate_limit_per_query = min(200, max(50, max_hits * 5))` **units** per query. Taking only `max_hits` per query is insufficient — a unit ranked 11th for three queries may deserve a top fused rank and would never enter the candidate set.
4. Fuse with **1-based ranks**:

```
score(u) = Σ_q  1 / (60 + rank_q(u))
```

Units absent from a query contribute nothing. Sort descending, take `max_hits`. Tie-break on `section_id` ascending. Do not invent an alternative.

> **k=60 is challenged, 2026-08-06 — and the challenge is specific, not general.**
>
> **k=60 comes from Cormack et al. (2009), where the fused lists were different retrieval *systems* over one query.** Those votes are genuinely independent: different algorithms fail differently, so agreement is real evidence. **Here the lists are different query *rewrites* over one BM25 index.** Paraphrases share terms and produce correlated rankings, so consensus across them is largely the same evidence counted N times.
>
> **The quantitative form of the problem.** With `candidate_limit_per_query` at 50–200, a unit's rank spans 1..200, so contributions span `1/61 = 0.0164` down to `1/260 = 0.0038` — a **4× spread across the entire list**, while *each additional list a unit appears in* adds up to another `0.0164`. **A unit ranked 1st in one list scores less than a unit ranked ~150th in two.** At k=60 with short lists, RRF degenerates toward *counting how many lists contain the unit* — voting, not ranking. That is exactly the boilerplate failure: `The Secretary shall`, `Not later than 180 days`, definitions, and clerical amendments match every rewrite weakly and win on breadth.
>
> **§7 hands the weighting to the model without saying so.** §7 assigns query expansion to the calling model, so **the model decides how many rewrites each concept gets** — and under sum-of-reciprocals that is a vote count. E1's ceiling run issued 28 queries in 4 rounds; if six paraphrase one concept and one covers another, the first is weighted 6×. **Nobody chose that weighting and nothing discloses it.**
>
> **This is not an unexamined parameter — it is a recorded intent now being questioned.** V9 asserts as a *desired* property that *"a unit ranked outside `max_hits` for every individual query but highly ranked for several can still reach the fused top-N."* Sol's argument is that on congressional boilerplate the same behavior is a defect. Both can hold; which dominates in practice is **measurable, and should not be settled by retuning k on reasoning.** Note also that V9's dedup covers *identical* queries only — near-duplicates are the actual case and gain full weight.
>
> **No fusion failure has been observed.** Across every §17 trace the model found what it needed. This is theory-driven, which earns a measurement, not a change. **V20 below.**

**Apply the limit at the unit level, not the segment level.** A flat `LIMIT n` on matched *segments* truncates the candidate set before the per-query *unit* limit applies — a very common term produces many segments inside few units. Aggregate in SQL (`GROUP BY unit_id` with `MIN(bm25)`) and limit the grouped result. Live defect 5e was a `LIMIT 1000` on segments; same family as the candidate-depth issue above.

### Ranking philosophy

No embedding pipeline. The calling model already knows the NDAA says "Polar Security Cutter" — that semantic bridge comes free from the client. Optimize for cheap iterative multi-query. **The tool description must instruct the model to pass several phrasings and synonyms in one call.**

---

---

## Query semantics must be stated in the tool description

**Measured 2026-08-06 (§17 Groups B and E).** Queries match as **literal phrases with stemming** — not as bags of words, not semantically. `Space Force end strength` returns zero against a bill containing both *"End strengths for active forces"* and *"Space Force"*; `polar security cutter` and `Seventeenth Coast Guard District` both hit. Length is not the variable; **verbatim presence is.**

§7 assigns query expansion to the calling model, which only works if the model knows what a query does. Two consumers independently wrote *descriptions of topics* — the natural choice under a bag-of-words assumption — and burned ten and three queries respectively on zero hits before recovering by collapsing to single common words.

**Say it in the tool description:** queries match as literal phrases with stemming; supply phrases expected to appear verbatim; prefer several short exact phrases over one descriptive one.

**Additionally, make a zero-hit response diagnostic.** Return what the query tokenized to. Zero hits currently means *absent* or *not phrased as the document phrases it*, and nothing distinguishes them — the same ambiguity this spec has now ruled on five times elsewhere.

> **FIXED 2026-08-08 — `79fe05a` (F10).** `search_bill_text` returns `query_diagnostics` for every query that matched nothing: `terms` (FTS5 stems), `absent` (terms not in the index), and a `verdict` — **`phrasing`** (all terms present → rephrase) or **`absent_term`** (a term is missing → stop). Null when every query hit; diagnosed **per query**, not only on all-zero responses. **The tokeniser is FTS5 itself via a probe table sharing the `FTS_TOKENIZER` constant with the segment index — never a Python re-implementation**, which sabotage shows reports `icebreaker` absent from a bill that contains it. Measured: 1,677 zero-hit pairs split 50.1% `phrasing` / 49.9% `absent_term`, so the verdict discriminates. See §18 F10.

---

## Rewrite imbalance is the model's to control, so tell the model

**Measured 2026-08-06 (V20):** 1 to 8 queries per round across §17's 30 rounds — an **8× spread in vote weight, chosen by the calling model and disclosed nowhere.** Under sum-of-reciprocals each query is an independent vote, so six paraphrases of one concept weight it 6× against a concept given one.

**Stated in the tool description, not normalized away.** §7 assigns expansion to the calling model; the corresponding obligation is to say **how expansion is weighted** — each query is an independent vote, and N paraphrases of one concept weight it N×. Prefer distinct concepts over paraphrases of one.

Normalizing per concept would require **clustering**, which is an estimate, and would introduce an unmeasured behavior behind the model's back to correct a weighting the model chose deliberately. Description over machinery, same as F9.

**k is not involved.** The V20 sweep is nearly flat, so this is not fixable by retuning fusion and would persist unchanged at any k.
