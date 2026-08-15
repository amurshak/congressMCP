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
| D1 | HIGH | **Silent wrong answer** — valid empty result | no | C |
| D2 | HIGH | **Silent** — contract unmet, counter disagrees with serializer | **likely — check** | A |
| D3 | HIGH | Garbage presented as data | feed converter | B |
| D4 | HIGH | **Silent truncation** | feed | B |
| D5 | HIGH | **Silent data loss** | feed | B |
| D6 | MED | Enables confabulation | no | D |
| D7 | MED | Visible garbage + ambiguous absence | converter family | A |
| D8 | — | Working, protect with regression tests | — | — |
| D9 | hygiene | Known-failing test baseline, clamped not fixed | repo-wide | out of scope |
| D10 | HIGH | **Silent data loss** — `_extract_json` discards real content behind a success envelope | converter family (4 buckets) | OPEN |
| D11 | MED | **Silent wrong answer** — `laws` router dropped sibling params via `kwargs.get` | router | **FIXED** `880cb53` |
| D12 | MED | Advertised-but-unroutable params → every documented use `ToolError`s | 3 tools | OPEN (one needs a decision) |
| D13 | MED | Credential in INFO logs — congress.gov client, same key as GovInfo | **yes — under bill-text** | **FIXED** `1284500` |
| D14 | MED | Guard hand-pasted at 81 sites, nothing enforced coverage | 7 routers | **coverage FIXED** `880cb53`; decorator open |
| D15 | LOW | `from_date_time` / `fromDateTime` mixed permanently on the public surface | public MCP surface | OPEN |
| D16 | LOW | Allowlist skip that never fires — documented exclusion is dead code | test quality | OPEN |

---

### D1 — `search_members` state filter is dead in every code path

Validation accepts only a 2-char code; the post-fetch filter compares against the API's full state name. `state="NJ"` → 0 results. `state="New Jersey"` → `INVALID_PARAMETER`. Reproduced with `state="CA", chamber="Senate"` → 0.

**Severity is higher than "dead."** Dead would error. This returns **success with an empty set**, so a model asking who represents New Jersey is told *nobody does*, with no signal that a filter silently ate the result. That is a wrong answer, not a failure.

**Fix:** code→name normalization before comparison, or filter API-side. Prefer API-side if the endpoint supports it — it removes the dual representation rather than translating between them.

**Regression test:** assert non-empty for a known state in both chambers, and assert the two spellings agree rather than merely that one works.

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
- **`bills_tool.py:199`** — `version` ("Text version for content operations") is advertised but unroutable. **DECISION NEEDED, not a delete:** the description reads like an *unwired seam into the bill-text feature* (route a `bills` content request by version). If that wiring was planned this is unfinished integration; if not, the param is vestigial. **A maintainer call — an implementer must not decide it.**

**Status: OPEN** (first two are mechanical; the third is blocked on the decision).

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

## Closed and refuted — kept so they are not re-raised

**Three of eight findings in the 2026-08-09 review were artifacts of the review's own tooling**, not of the software. The review branch overlays only the in-scope paths onto the branch point, so ~74 out-of-scope files sat at **pre-branch state**; a reviewer reading whole files reported them accurately — about the slice, not about the shipped code.

- **`bug_002` — REFUTED 2026-08-10.** Claimed the default server path is unstartable because 33 files import `mcp.server.fastmcp`. Measured on the real branch: **0** such imports (the MCP-2 migration `0ab182c` converted them); the reviewer's 33 matches the **stale slice** exactly. The full server starts.
- **`bug_004` — REFUTED, same cause.** "`pyproject.toml` still allows `mcp>=1.26`" was true only of the frozen slice; the real branch has pinned `mcp>=2.0.0,<3` since `0ab182c`.
- **`bug_008` — REFUTED on its own premise.** Assumed `ctx.error()` is a coroutine in mcp 2.x; `Context.error` is **sync** in the installed 2.0.0, so calling it without `await` is correct.
- **`bug_005` — FIXED `950125d`.** `python -m congress_api` discarded `main()`'s return, so a `cache clear` refusal exited 0 under `-m` while the console script exited 1. Both return 1 now; `cache info` still 0. *(This is a contract the bill-text spec pins — see `fulltext/08-cache-storage.md` §10.)*
- **`bug_006` — FIXED `950125d`.** `sqlite_supports_fts5()` opened and closed a database on every tool call to probe a compile-time property; now `@functools.cache`d.
- **`bug_007` — FIXED `950125d`.** `README.md` documented `MCP_TRANSPORT`, absent from the code; row removed.

**Process lesson, recorded because it will recur.** A finding is only as valid as the tree it was measured against: when reader scope ≠ change scope, the reader manufactures false positives from the gap. The rebuilt slices carry a root `REVIEW-SCOPE.md`, but that only mitigates it — **the clean fix is to review a diff, not a worktree**, so no out-of-scope file is present to misread.

---

## Sequencing

**Before PR 1 merges:** only the D2 shared-serializer check. If the bill-text tools emit through the same path, that fix blocks; if not, nothing here does.

**PR A — envelope and converters (D2, D7).** First, despite the blast radius. D2 is about whether the structured container is emitted at all; B is about what goes in it. Fixing contents before container means testing contents twice. Run with the converter tests already in the repo, and pin D8's envelopes first.

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
