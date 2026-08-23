# congressMCP — pre-existing tool defect register

**The running register of defects in the pre-existing congressMCP tools** — everything outside the three bill-text tools. Separate artifact from `fulltext/`: that directory specifies the new tools and holds their `F`-numbered defects; **this one is the standing home for the surface they landed on**, and stays open after PR 1 ships.

## How this register runs

**Scope.** A finding belongs here if it lives outside `congress_api/features/bill_text/` — the other ~93 tools, the shared request/converter/validation layers, the test baseline, and packaging. Bill-text defects are `F`-numbered in `fulltext/14-defect-priority.md` and stay there. When one finding touches both (a shared layer under the new feature), it gets an entry **here** and a cross-reference there, not two competing records.

**Provenance is recorded, because it sets how much weight an entry carries.** `[E2E]` observed live in a §17 consumer run; `[AUDIT]` found reading source or published docs; `[REVIEW]` reported by a code review and **not yet independently confirmed**; `[SWEEP]` surfaced by an automated test sweep. A `[REVIEW]` entry is a claim until someone reproduces it — three findings in the 2026-08-09 review turned out to be artifacts of the review's own stale worktree, so this distinction is not ceremonial.

**Negative results stay.** Refuted findings are kept with the evidence that killed them (bottom section) rather than deleted, so the same false positive does not get re-raised each review cycle.

**Status vocabulary.** `OPEN` · `FIXED <commit>` · `REFUTED <date + why>` · `DECISION NEEDED` (a maintainer product/requirements call, never an implementer's) · `OUT OF SCOPE <where it went>`.

---

## Triage axes

**Silent wrongness before visible failure.** A tool that returns a *wrong* answer with a success envelope is the same harm class as reporting struck text as operative — the model has no way to detect it. A tool that errors is annoying and self-announcing. Sort by this, not by tool popularity.

**Shared-layer before isolated.** A defect underneath the bill-text feature is not a "pre-existing tool bug"; it is a bug the new feature's verification ran on top of.

---

## Register

| ID | Sev | Failure mode | Shared layer? | PR |
|---|---|---|---|---|
| D1 | HIGH | **Silent wrong answer** — valid empty result | no | **FIXED upstream `abb7550`** (audited live; residual: full-name spelling errors *visibly*) |
| D2 | HIGH | **Silent** — contract unmet, counter disagrees with serializer | **likely — check** | A |
| D3 | HIGH | Garbage presented as data | feed converter | B |
| D4 | HIGH | **Silent truncation** | feed | B |
| D5 | HIGH | **Silent data loss** | feed | **PARTIAL** — drop class fixed upstream `ed9aa4b`; dup not reproduced; walk-twice test worth pinning |
| D6 | MED | Enables confabulation | no | D |
| D7 | MED | Visible garbage + ambiguous absence | converter family | **PARTIAL** — absence half fixed by `b04d327` typed errors; HTML half open (A) |
| D8 | — | Working, protect with regression tests | — | — |
| D9 | hygiene | Known-failing test baseline, clamped not fixed | repo-wide | out of scope |
| D10 | HIGH | **Silent data loss** — `_extract_json` discards real content behind a success envelope | converter family (4 buckets) | OPEN |
| D11 | MED | **Silent wrong answer** — `laws` router dropped sibling params via `kwargs.get` | router | **FIXED** `880cb53` |
| D12 | MED | Advertised-but-unroutable params → every documented use `ToolError`s | 3 tools | OPEN (one needs a decision) |
| D13 | MED | Credential in INFO logs — congress.gov client, same key as GovInfo | **yes — under bill-text** | **FIXED** `1284500` |
| D14 | MED | Guard hand-pasted at 81 sites, nothing enforced coverage | 7 routers | **coverage FIXED** `880cb53`; decorator open |
| D15 | LOW | `from_date_time` / `fromDateTime` mixed permanently on the public surface | public MCP surface | OPEN |
| D16 | LOW | Allowlist skip that never fires — documented exclusion is dead code | test quality | OPEN |
| D17 | HIGH | **Noise presented as results** — `search_bills` OR-splits + substring-matches; `Act` carries every named-Act query | no — client-side filter | OPEN (after PR 2) |
| D18 | HIGH | **Silent wrong answer** — `search_bills` scans a 250-bill recency window; bills unreachable by exact title; `offset`/`limit` incoherent | no | OPEN (after PR 2; **must land with or before any D17 matcher fix**) |
| D19 | LOW | `client_handler.py` calls async (deprecated) `ctx.error` un-awaited ×4 — client notification never happens | no | OPEN (reopened from `bug_008`'s failed refutation) |

---

### D1 — `search_members` state filter is dead in every code path

Validation accepts only a 2-char code; the post-fetch filter compares against the API's full state name. `state="NJ"` → 0 results. `state="New Jersey"` → `INVALID_PARAMETER`. Reproduced with `state="CA", chamber="Senate"` → 0.

**Severity is higher than "dead."** Dead would error. This returns **success with an empty set**, so a model asking who represents New Jersey is told *nobody does*, with no signal that a filter silently ate the result. That is a wrong answer, not a failure.

**Fix:** code→name normalization before comparison, or filter API-side. Prefer API-side if the endpoint supports it — it removes the dual representation rather than translating between them.

**Regression test:** assert non-empty for a known state in both chambers, and assert the two spellings agree rather than merely that one works.

**FIXED upstream `abb7550` (#50/#51) — audited live 2026-08-21.** `state="NJ"` → 20 members; the entry's own `state="CA", chamber="senate"` repro → 11; mechanism is API-side routing (`/member/congress/{c}/{state}`) plus full-pagination before client-side filters — the entry's preferred fix. **Residual, downgraded:** `state="New Jersey"` still errors, but *visibly* (`INVALID_PARAMETER`, names the 2-char requirement) — the silent-wrong-answer severity this entry was ranked on is dead; the two-spellings regression test remains unmet as a nicety, not a defect.

---

### D2 — top-level `members` / `committees` arrays never populated

Every response carries an empty structured array while all real content sits in a `summary` markdown blob. `results_count` reports correctly, so **the counter and the serializer disagree** — which means the data exists at serialization time and is being dropped on the way out. Programmatic consumers must regex markdown.

**Locus (found 2026-08-04):** `response_converters.py:82`, `convert_members_committees_response`. The members/committees impls return pre-formatted markdown, so `_extract_json` returns `None` and control reaches the branch at line 96 that hard-returns `members=[]`, `committees=[]`, `summary=<raw>`. The array-population code at lines 108–141 runs only for JSON input, which never arrives. The function's own comment concedes the empty branch is the normal path for every one of these tools. `results_count` comes from a separate regex over the markdown (`_extract_result_count`), which is exactly why the counter reports nonzero against empty arrays.

**Does not block PR 1 — cleared on two independent lines.** *Structural:* the bill-text tools import no `convert_*_response`; they build their own Pydantic models (`SearchBillTextResponse`, `BillSectionResponse`, `BillTocResponse`), populate structured fields inline, and return `model_dump()` directly — no markdown round-trip. *Empirical:* live against GovInfo, `search_bill_text` returns a populated `hits` list with every §9 `SearchHit` field present, `get_bill_section` returns `text`/`children`/`node_kind`/ `subtree_byte_length`/`truncated` as first-class fields, and neither carries a top-level summary blob.

**Fix:** populate the structured array; keep the markdown summary as a convenience field, not the payload. Add the missing verification step (see below).

---

### D3 — amendment records destroy the sponsored-legislation feed

~60% of 350 records rendered as `UNKNOWN Unknown (Congress N) / No title available`. Offset 300 was 47/50 unusable. The converter reads bill-shaped keys (`type`, `number`, `title`) against amendment objects, which carry `amendmentNumber` and `purpose`/`description`.

**Two changes, kept separate:** (a) detect `/amendment/` in the URL and map the correct fields; (b) add a `type` filter so callers can request bills only. (a) is the defect; (b) is ergonomics and should not be the fix for (a).

**Pattern worth auditing beyond this bug.** This is the third instance of "every record carries field X" being false — A3 was null `date` on version records, and amendments are again where date fields go missing. Grep the converters for unguarded field access on optional keys; there is likely a fourth.

---

### D4 — feed is not partitioned by congress

Sorting appears to be `updateDate desc`, so recently-touched old measures float into the middle of the stream: 43 consecutive 114th-Congress amendments between offsets ~81–142; S 1081/114, S 3742/116, S 4732/117 appearing individually near offset 277, surrounded on both sides by 119th bills.

**Silent truncation.** A consumer that stops paginating at the first off-target congress reports a partial answer as complete. The result set is unbounded in time — you cannot know you are done without walking everything.

**Fix:** `congress` param on both member-legislation tools.

---

### D5 — page boundaries are non-deterministic

0→50 duplicated `samdt/5404` and **dropped** `samdt/5408`. 100→150 duplicated `S 3806`. 50→100 and 150→200 clean. Inconsistent overlap rules out off-by-one and points to an unstable sort on tied `updateDate` values.

The duplicate is harmless and detectable. **The drop is invisible data loss.**

**Fix:** stable secondary sort key (bill type, then number) plus client-side dedupe in any exhaustive walk.

---

### D4 + D5 together — the actual headline

Neither is as bad alone as the pair is jointly. **D4 means an exhaustive walk is the only correct strategy. D5 means an exhaustive walk still loses records.** Together they make "list all legislation sponsored by member X" unanswerable with confidence — the one question these tools exist to answer.

Fix them in the same PR and verify them together: walk a member's full feed twice with different page sizes and assert identical sets. Neither fix alone makes that test pass.

---

### D6 — no summary, introduced date, policy area, or latest action

Member tools return number/type/congress/title only, forcing N+1 calls for any "summarize each" request.

**The risk is not the extra calls — it is what a less cautious agent does instead.** Producing the test document required inferring from titles. That works for `Zero Food Waste Act` and fails completely for acronym titles: `REDACT`, `GAAME`, `SECURES`, `FOCUS`, `NOTICE`, `PROSPECT`, `RAISE`. 24 entries were marked † rather than guessed. An agent without that discipline confabulates, and the output looks identical.

Same value system as `amends` precision: a field shape that invites inference is worse than one that returns nothing.

**Fix:** an `include` param for summary/date/policy-area/latest-action rather than unconditional inflation of every response.

---

### D7 — `get_bill_summaries` returns raw HTML; absence is ambiguous

S 751 came back with `<p>`, `<strong>`, `&nbsp;` unconverted. Same converter family as D2.

**Second half, separate defect:** S 4977 (introduced ~July 2026) returned the bare string `No summaries found`, which cannot distinguish **"CRS has not written one yet"** from **"the lookup failed."** Those warrant different consumer behavior — one is worth retrying, the other is not. Same ambiguity-of-absence problem §6 worked through for empty `amends`, and it deserves the same answer: make the two cases distinguishable in the response rather than in a human's interpretation of a string.

---

### D9 — known-failing test baseline, repo-scope. Clamped, not fixed.

> **Clamp ergonomics FIXED `46f648f` (2026-08-23, prompted by F37's undiagnosable CI log):** on a regression the clamp now re-runs exactly the regressed node ids with `--tb=long -rA` and prints the output verbatim under a REGRESSION DETAIL banner; shrink-only and matching paths unchanged. The baseline itself (2 failures + 4 collection errors) remains clamped-not-fixed, as recorded below.

> **Update 2026-08-15 — this entry's own prediction fired, and half of it is now actioned.** D9 warned that the file held **two populations with different lifecycles** and that the dead ones needed *deleting*, not waiting on the migration. That is exactly what happened. Six baselined **collection errors** were bill-text-adjacent (they imported the standalone `fastmcp` package) and were **verified dead and deleted** in `880cb53` — they tested the removed SaaS-tier architecture (`core.auth.auth`, `check_operation_access`, `FREE`/`PAID_OPERATIONS`, and 5 of 6 target modules renamed), so no import fix could have made them collect. Collection errors **10 → 4**. The baseline is also **single-sourced** now: the Python copy of the set is gone, `KNOWN_FAILURES.md`'s fenced blocks are the one machine-read record, the checker **refuses an empty parse** instead of reporting everything as a regression, and a new test rejects baselined entries whose files no longer exist.
>
> **Still open: the 4 `core.services` entries** — the population D9 named. Same greenwash shape, out of the bill-text work's scope. **Give them the treatment the six got — verify dead, then delete or repair — rather than assuming.** The six turned out dead by inspection, not by assumption, and that distinction is the whole point.

Pre-existing in the **repo**, not in the bill-text feature. Mostly **MCP 2.x migration** fallout plus dead code. Outside PR 1 and PR 2 scope by decision, recorded here so the decision is deliberate rather than forgotten.

**Clamped, correctly.** `tests/KNOWN_FAILURES.md` enumerates all 16 with causes; `tests/check_known_failures.py` fails on **growth or shrinkage**, both verified by simulation. Failing only on growth would let a silently-fixed entry leave the list stale until it is fiction — a bigger version of the problem the clamp solves.

**Two things to note before someone hits them cold:**

**1. The ratchet will fire loudly during the MCP 2.x migration, and that is correct.** Most of these resolve at once when the migration lands, so the shrinkage check trips on a change that is *good*. Whoever hits it should update `KNOWN_FAILURES.md`, **not disable the check** — which is the tempting move at the moment it fires and the one that discards the clamp's whole value.

**2. The file holds two populations with different lifecycles.** Four entries import `congress_api.core.services`, **a module that does not exist in the tree**. Those are not failing tests, they are **dead tests**, and they will never pass — so they are permanent entries in a list whose other members are all expected to disappear. Mark them, so the migration cleanup knows which entries should shrink and which need deleting outright. Left unmarked, they keep the count non-zero forever and train readers to skim a file whose whole purpose is being read.

**Severity:** hygiene, not correctness. Nothing here affects tool output. It matters because an unenumerated failing baseline is where a real regression hides, and that risk is now closed.

---

### D8 — confirmed working, protect with regression tests

- `bills:get_bill_summaries` parsed `"S 751, 119th Congress"` correctly — the flexible reference parser works.
- Error envelopes on validation failure carried error type, code, offending parameter, and provided value. This is good and unusually complete.
- Latency consistent across nine calls, no timeouts at `limit=50`.

Worth pinning with tests **before** the converter work, since PR A touches the same serialization path that produces these envelopes.

---

## D10–D16 — relocated from `fulltext/` 2026-08-15

These arrived through the bill-text work (the 2026-08-09 and 2026-08-14 code reviews, plus one automated sweep) but are defects in the **pre-existing** surface. They were triaged in `fulltext/14-defect-priority.md` and are **moved here as their permanent home**; that file keeps one-line pointers where a bill-text argument depends on them.

### D10 — `_extract_json` can silently discard the real response `[REVIEW]`

`buckets/voting_and_nominations.py:24`, **and the same wiring in three other buckets.** First-balanced-brace extraction can parse an embedded JSON snippet out of a markdown response and return a near-empty `success=True` envelope, **discarding the actual content**.

**Top of this register's own triage axis:** a success envelope hiding a dropped payload is the silent-wrongness class, and the model cannot detect it. Same failure class as bill-text `F22` (redirect exhaustion returned as `<400` success) — worth fixing with one mental model, since the two were found in the same review. **Status: OPEN.** Fix all four bucket call sites together; a fix to one is not a fix.

### D11 — `laws` router silently dropped sibling parameters `[SWEEP]`

Found by F24's guard sweep, not by a human reviewer: `get_laws` and `get_law_details` predated the `validate_operation_kwargs` convention and **cherry-picked via `kwargs.get(...)`**, so an inapplicable parameter produced **no error at all** — the caller got plausible results for a query the tool never honored.

**Status: FIXED `880cb53`.** Now raises `Operation 'get_laws' does not accept parameter(s): law_number`. **Behavior change on a public tool:** a caller who previously sent an inapplicable param to `laws` got silent results and now gets an honest rejection. That is the documented guard contract, but it is visible — worth a release note.

### D12 — parameters advertised in schemas that no routed operation accepts `[REVIEW]`

Three faces of one defect. The `validate_operation_kwargs` guard converted latent schema/implementation drift into a loud `ToolError`, which is the guard **working** — but three tools still ship stale schemas, so their *documented* call shape now fails:

- **`committee_meetings.py:302`** — `get_committee_meeting_details` dropped its previously-required `committee_code` while the `committee_intelligence` docstring still advertises it.
- **`treaties_and_summaries_tool.py:66`** — `offset` is advertised but none of the five routed operations accepts it, so **pagination via the documented parameter is impossible tool-wide**.
- **`bills_tool.py:199`** — `version` ("Text version for content operations") is advertised but unroutable. **DECISION NEEDED, not a delete:** the description reads like an *unwired seam into the bill-text feature* (route a `bills` content request by version). If that wiring was planned this is unfinished integration; if not, the param is vestigial. **A maintainer call — an implementer must not decide it.** **RULED BY MAINTAINER 2026-08-20: vestigial — delete.** There are no content operations in the legacy tools to wire it to; version-addressable retrieval is the bill-text tools' job and already ships there (`version` param on all three, §4). The capability the seam gestured at — surfacing *available* versions on request — is recorded as a requirement in `fulltext/03-data-sources.md` ("Version discovery — requirement recorded 2026-08-20"), not here.

**Status: OPEN, now wholly mechanical** — all three faces are schema cleanups; the third's decision is made (delete).

### D13 — API key in INFO logs, and it is one credential, not two `[E2E, confirmed live]`

Full `api_key=…` appeared in the congress.gov request URL at INFO level. **This is the shared-layer case this register's second triage axis is about:** GovInfo and congress.gov use the **same key**, so the `X-Api-Key` header hardening done on the new GovInfo client was undermined by the client beside it — PR 1's own dependency leaked the credential PR 1 uses. It also defeated the §17 trace-redaction rule, since a trace attached to a bug report would carry a live key anyway.

**Status: FIXED `1284500`.** Installing the redactor unconditionally **surfaced a live leak four green tests had missed** — httpx logs an `httpx.URL`, not a `str`, so the type guard skipped the argument carrying the key. Full reasoning and the generalized rule (**no secret-bearing URL may reach a log or an error `detail`; strip to `scheme+host+path`**) are in `fulltext/14-defect-priority.md` F15 and `fulltext/04-tools-responses.md` §9 — that rule binds this surface too.

### D14 — the operation guard is hand-pasted at 81 call sites `[REVIEW]`

`validate_operation_kwargs` is copied at **81 call sites across 7 routers** with nothing enforcing coverage; a forgotten call regresses to the opaque `TypeError` the guard exists to prevent. **This is the systemic root of D12** — three tools drifted because nothing checked that they had not.

**Status: coverage FIXED `880cb53`; the ergonomic fix is open.** `tests/test_bucket_operation_guard.py` now walks **every live router branch** (84 cases, non-vacuity floor ≥40) and fails any branch missing its guard call, so an omission fails a test instead of shipping. The 81 sites remain hand-written — a decorator would still be cleaner — but they are no longer unguarded against omission.

### D15 — `from_date_time` / `fromDateTime` mixed on the public surface `[REVIEW]`

`committee_reports.py:424`. Parameter-name drift was fixed in **opposite directions in the same diff** — camelCase→snake_case here, snake_case→camelCase in summaries/treaties — so both spellings are now permanent on the public MCP surface. A consistency defect a client feels directly. **Status: OPEN.** Pick one spelling repo-wide; changing either is a breaking change, so it wants a deliberate decision rather than a third drift.

### D16 — an allowlist skip that never fires `[REVIEW]`

`tests/test_invoke_all_operations_with_defaults.py:132`. The `(tool, operation, "*")` skip form never matches because only per-parameter triples exist, so the **documented exclusion is dead code** — a test exclusion that reads as deliberate and is inert. **Status: OPEN.** Test quality; low severity but it misleads a reader about what is covered.

---

### D17 — `search_bills` OR-splits on whitespace and substring-matches, so named-Act queries degrade to "newest bills" `[E2E, repro PINNED 2026-08-20 by differential probes]`

**Pinned by a probe sequence (maintainer via Claude Desktop, 2026-08-20) that falsified two prior hypotheses before landing — including the diagnosing session's own favored one (no-op filter / stringified keys; both killed by `latestAction` → 0 and `zzzqqx` → 0):**

| query | result |
|---|---|
| `Radiation Exposure Compensation Act` | 50 |
| `St. Louis RECA Readjustment Act` | same top 10, **byte-identical order** |
| `Radiation Exposure Compensation` | **0** |
| `zzzqqx` | 0 |
| `latestAction` | 0 |

**The differentials carry the diagnosis.** Dropping the single word `Act` goes 50 → 0; two queries sharing no token but `Act` return identical results in identical order — so `Act` carries the entire query and the other terms contribute nothing: **whitespace-split OR, not AND, not phrase.** And it is **substring, not token**: HCONRES 76 in the hit set matches no query token — `act` inside "imp**act**" does, which means `act` also hits *enacted*, *action*, *practice*, *transaction*, and nearly every bill record contains one.

**The pathology is precisely inverted from useful: because every federal statute is named "… Act," the filter degrades to "return the newest bills" on exactly the query class it exists to serve.** A user searching legislation by name hits the failure mode 100% of the time. Noise with a success envelope — same harm family as D3 — and the inverse of the new tools' §7 lesson: `search_bill_text` was stricter than consumers assumed (literal phrases), this is infinitely looser, and the shared root is matching semantics the caller is never told.

Mechanism attribution `[AUDIT — source read by the diagnosing session, consistent with every probe]`: `filter_by_keywords`, client-side, downstream of a fetch. Cosmetic tell recorded because it locates normalization: the hit header preserves query case, the empty message lowercases it — two formatting paths.

### D18 — `search_bills` scans a 250-bill recency window, not the corpus; `offset` pages the *candidate* window `[AUDIT — source read; behavioral confirmation: HR 4631 unreachable by its own exact title]`

**Independent of D17 and survives fixing it.** `search_limit = min(limit * 5, 250)` fetches one `updateDate desc` page, then filters it. HR 4631 (last activity July 2025) is nowhere near the 250 most-recently-updated bills of the 119th, so **even a perfect exact-phrase matcher returns zero for `St. Louis RECA Readjustment Act`** — it is a filter over a recency page wearing a search tool's name. Two structural consequences from the same design, recorded here rather than as separate entries:

- **`limit` does double duty** — it sets fetch size *and* output cap (`limit=10` scans 50; `limit=50` scans 250), so results are **not monotonic in `limit`**: a bill can appear at 50 and vanish at 10 for reasons unrelated to ranking.
- **`offset` pages the pre-filter candidate window, not the result set** — pagination over matches is not merely wrong but incoherent; matches cannot be enumerated.

### D17 + D18 together — the actual headline, and a fix constraint

**D17 is currently masking D18.** Tighten the matcher to AND/phrase and `Radiation Exposure Compensation Act` returns a clean zero — and a caller reasonably concludes the bill does not exist. That trades false positives for false negatives, **the worse trade for this tool: the noise at least looked wrong, a clean zero reads as an answer.** Therefore, binding on whoever picks this up: **do not ship a matcher fix without the window fix.** A matcher-only pass makes the tool quieter, not more correct.

**Fix direction (maintainer 2026-08-20, reinforced by the diagnosis):** this problem is already solved once in this codebase — GovInfo's `/search` endpoint does real full-text over the BILLS collection, the GovInfo client and key handling exist, and `search_bill_text`'s `query_diagnostics` discipline (`phrasing` vs `absent_term`, so a zero is readable) applies at corpus level. **Minimum honesty fix if the full fix is deferred:** response metadata — `bills_scanned`, oldest `updateDate` in the window, `window_truncated` — so "no match in the 119th Congress" and "no match among the 50 bills examined" stop rendering as the same string (the fulltext scan-that-errors rule, applied to a scan that under-looks). Whatever ships states its matching semantics in the tool description, per the rule measured into `fulltext/07-search.md`.

**Regression tests, recorded now because the failure is reproducible with a known-correct answer:**

```python
# fails today: returns 10 unrelated bills, none of them HR 4631
assert "HR 4631" in search_bills(congress=119, keywords="St. Louis RECA Readjustment Act")
assert search_bills(congress=119, keywords="Radiation Exposure Compensation") != ""
```

**Status: both OPEN. Sequencing: after PR 2**, alongside the F27 error-shape convergence — set by the maintainer 2026-08-20. Not for immediate implementation. **Audited 2026-08-21: both UNCHANGED on master** — the differential table reproduced byte-for-byte (spec-session-verified from the raw evidence JSON), `HR 4631` confirmed to exist upstream and confirmed unreachable by its own exact title, `processors.py` matcher and `api.py` window both untouched by the upstream fix round. The joint constraint stands. **Real-use corroboration 2026-08-22:** a genuine research session hunting a just-introduced bill (`119hr10115ih`) could not reach it through `search_bills` or `search_summaries` and got there only via web search + `get_member_sponsored_legislation` — the discovery gap costing an actual session, not a probe. Priority argument strengthened.

### D19 — `client_handler.py` calls the async, deprecated `ctx.error` un-awaited at four sites `[AUDIT, 2026-08-21 — reopened from bug_008's failed refutation]`

**How it got here:** ultrareview's `bug_008` (2026-08-09) flagged un-awaited `ctx.error()` calls; the 2026-08-10 refutation closed it on the premise that `Context.error` is sync in the installed mcp 2.0.0. The 2026-08-21 audit measured the premise false: it is `async def` (and `@deprecated` since 2026-07-28, SEP-2577), so the four call sites (`client_handler.py:193/223/245/264`) create coroutines that are never awaited — the client-notification never happens, Python warns `coroutine … was never awaited`, and the repo's own harness *stubs the method sync* to keep its tests green (`test_invoke_all_operations_with_defaults.py:73-76`).

**Severity LOW, stated precisely:** nothing crashes, and the error still reaches both the returned envelope and the server log — what is lost is only the in-band client notification the calls appear to provide, plus warning noise. The reviewer's finding was right in substance; the refutation's instrument was wrong.

**Fix direction (spec ruling, 2026-08-21): remove the four calls rather than await them.** The API is deprecated upstream; awaiting would invest in a surface scheduled for removal, and the envelope already carries the error. A removal also deletes the harness's sync-stub lie. Any replacement client-notification mechanism is a separate, unrequested feature.

**Status: OPEN (LOW).** No sequencing pressure; bundle with any future `client_handler.py` work (note the same file carries the F-series credential-leak history — §11's exception-path lesson — so whoever opens it should read that first).

---

## Upstream reconciliation — audit commissioned 2026-08-21

**Master moved under this register.** Upstream landed defect fixes that overlap these entries: `abb7550` ("Fix P1 defects from the 2026-08-21 functional review", #49–#52), `b04d327` ("Report Congress.gov 404/400 as NOT_FOUND / INVALID_PARAMETERS instead of SERVER_ERROR", #53), and earlier commits touching register territory (#32 null-field crashes, #35 offset paging, #36 truncation, #42/#43 schema-drift guard/CI). The maintainer's read is that at least **D1** (dead `search_members` state filter) is fixed. Register rows are therefore **suspect-stale** until audited; do not plan work from them.

**Audit protocol (implementation session), per this register's own rules:**
- For each of D1–D18 *and* the refuted section: status on current master — FIXED (name the upstream commit), PARTIAL, or UNCHANGED.
- **Behavioral evidence per row, not diff-reading alone**: where the entry records a repro, run it (D1's state filter; D2's count-vs-collection coherence; D17/D18's RECA probe set — the differential table is in their entry). A fix claim without its entry's failure mode demonstrated dead is a claim.
- **Do not re-raise refuted items**; if an upstream commit "fixes" something this register refuted, that is a finding about the commit, not the register.
- **Report which error shape #53 used.** It invested in the legacy code family (`NOT_FOUND`/`INVALID_PARAMETERS`) — this bears directly on the **F27 convergence ruling** (server-wide §9 envelope, ruled 2026-08-20) and the PR-A constraint that characterization tests must not entrench the legacy shape. If #53 deepened the legacy shape, the convergence ruling stands and its cost just went up; the audit reports, the spec session rules.
- Deliver as a table, one row per D-entry, evidence cited per row. Register updates happen here after it reports.

**AUDIT DELIVERED AND ADJUDICATED 2026-08-21** — `upstream-reconciliation-audit-2026-08-21.md` (this directory, maintainer-copied), evidence in `audit_repro_results.json` / `audit_repro2_results.json`. 55 live calls through the registered tool functions; every row carries behavioral evidence; the refuted section was re-checked without re-raising. Spec-session spot-check: the D17/D18 differential (identical top-10 byte-for-byte across the two RECA queries, `has_HR4631: false`, drop-`Act` → 0) verified directly from the raw JSON; the first evidence file's D17 block has a failed extractor (`n_listed: 0`) superseded by the second file's corrected re-run — cite the second. Repro *scripts* referenced by the audit were not copied alongside the JSONs; the JSONs are the observations of record. **Outcomes applied to the rows below: D1 FIXED (`abb7550`), D5 PARTIAL, D7 PARTIAL, D11/D13 confirmed holding, D2/D3/D4/D6/D9/D10/D12/D14–D18 confirmed UNCHANGED, `bug_008`'s refutation withdrawn → D19.** Audit caveats recorded as stated: D4+D5's walk-twice ran on one member; D18 non-monotonicity neither shown nor falsified on one pair; D10 still synthetic-only. The #53 error-shape finding is recorded at the F27 entry (`fulltext/14-defect-priority.md`).

## Closed and refuted — kept so they are not re-raised

**Three of eight findings in the 2026-08-09 review were artifacts of the review's own tooling**, not of the software. The review branch overlays only the in-scope paths onto the branch point, so ~74 out-of-scope files sat at **pre-branch state**; a reviewer reading whole files reported them accurately — about the slice, not about the shipped code.

- **`bug_002` — REFUTED 2026-08-10.** Claimed the default server path is unstartable because 33 files import `mcp.server.fastmcp`. Measured on the real branch: **0** such imports (the MCP-2 migration `0ab182c` converted them); the reviewer's 33 matches the **stale slice** exactly. The full server starts.
- **`bug_004` — REFUTED, same cause.** "`pyproject.toml` still allows `mcp>=1.26`" was true only of the frozen slice; the real branch has pinned `mcp>=2.0.0,<3` since `0ab182c`.
- **`bug_008` — REFUTED on its own premise.** Assumed `ctx.error()` is a coroutine in mcp 2.x; `Context.error` is **sync** in the installed 2.0.0, so calling it without `await` is correct. **CORRECTION 2026-08-21 (upstream audit): the refutation's premise is false — refutation withdrawn, item reopened as D19.** `inspect.iscoroutinefunction(Context.error)` → coroutine in the installed 2.0.0 (`async def error`), and the repo's own harness stubs it *sync* to make the un-awaited calls work — the refutation's instrument was a test environment authored from the same wrong model, the trimmed-fixture rule biting inside a refutation. The original review finding was right in substance and its severity was over-stated relative to what D19 records; kept here, corrected in place, per the negative-results rule.
- **`bug_005` — FIXED `950125d`.** `python -m congress_api` discarded `main()`'s return, so a `cache clear` refusal exited 0 under `-m` while the console script exited 1. Both return 1 now; `cache info` still 0. *(This is a contract the bill-text spec pins — see `fulltext/08-cache-storage.md` §10.)*
- **`bug_006` — FIXED `950125d`.** `sqlite_supports_fts5()` opened and closed a database on every tool call to probe a compile-time property; now `@functools.cache`d.
- **`bug_007` — FIXED `950125d`.** `README.md` documented `MCP_TRANSPORT`, absent from the code; row removed.

**Process lesson, recorded because it will recur.** A finding is only as valid as the tree it was measured against: when reader scope ≠ change scope, the reader manufactures false positives from the gap. The rebuilt slices carry a root `REVIEW-SCOPE.md`, but that only mitigates it — **the clean fix is to review a diff, not a worktree**, so no out-of-scope file is present to misread.

---

## Sequencing

**Before PR 1 merges:** only the D2 shared-serializer check. If the bill-text tools emit through the same path, that fix blocks; if not, nothing here does.

**PR A — envelope and converters (D2, D7).** First, despite the blast radius. D2 is about whether the structured container is emitted at all; B is about what goes in it. Fixing contents before container means testing contents twice. Run with the converter tests already in the repo, and pin D8's envelopes first. **Constraint added 2026-08-20 (F27 ruling, `fulltext/14-defect-priority.md`): the maintainer has ruled the server converges on the bill-text §9 error envelope (`error.code`/`message`/`detail`/`remediation`). PR A's envelope work and its characterization tests must target that shape — pinning the legacy `core/exceptions.py` shape would entrench what the ruling retires.**

**After PR 2, by maintainer priority (2026-08-20): the F27 error-shape convergence and D17/D18.** These outrank the lettered PRs below when PR 2 closes. D17 and D18 land together or window-first — the masking constraint in their joint entry.

**PR B — member legislation feed (D3, D4, D5).** One tool, three defects, one round of testing. Restores a use case that is currently unanswerable.

**PR C — `search_members` state normalization (D1).** Small and isolated.

**PR D — member response enrichment (D6).** A feature, not a fix. Lowest urgency; changes response size, so it wants its own measurement.

Do not bundle these into the bill-text PR. Separate PRs keep review honest and keep `git bisect` useful across 96 operations.

---

## Two process items

**Add a wire-format verification step — V17, now specified in `fulltext/10-fixtures-verification.md`.** V1–V16 verify the parser and index; none asserts that emitted responses conform to §9.

**Correcting the first draft of this proposal, because D2 is its own counterexample.** "Assert every §9 field is present and correctly typed" **would have passed D2** — `members=[]` is present and correctly typed. Presence is not the property; **population is.** The assertions that discriminate are: non-empty collections on known-matching input; **count/collection coherence** (a count field must equal the length of what it counts — D2's signature was exactly that disagreement, and no field-level check can see it); no prose blob carrying content absent from structured fields; and, for the bill-text tools, an AST assertion that they import no `response_converters`.

V17 is scoped to the three bill-text tools now. **Extending it across the other 96 operations belongs to PR A**, where it is worth considerably more — those tools have no model enforcing shape at all, which is how D2 survived.

**Add a characterization test per defect as it is fixed.** This list is a sample from an untested population; fixing the sampled items says nothing about the population's size. Without characterization tests, PR 2's end-to-end pass produces a differently-shaped list rather than a shorter one.
