# congressMCP — pre-existing tool defect register

Defects in the **existing** tools, found during end-to-end testing of the bill-text
feature. Separate artifact from `fulltext/` — that directory specifies the three new tools;
this one tracks the surface they landed on.


---

## Triage axes

**Silent wrongness before visible failure.** A tool that returns a *wrong* answer with a
success envelope is the same harm class as reporting struck text as operative — the model
has no way to detect it. A tool that errors is annoying and self-announcing. Sort by
this, not by tool popularity.

**Shared-layer before isolated.** A defect underneath the bill-text feature is not a
"pre-existing tool bug"; it is a bug the new feature's verification ran on top of.

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
| D9 | hygiene | 16 known-failing tests, clamped not fixed | repo-wide | out of scope |

---

### D1 — `search_members` state filter is dead in every code path

Validation accepts only a 2-char code; the post-fetch filter compares against the API's
full state name. `state="NJ"` → 0 results. `state="New Jersey"` → `INVALID_PARAMETER`.
Reproduced with `state="CA", chamber="Senate"` → 0.

**Severity is higher than "dead."** Dead would error. This returns **success with an empty
set**, so a model asking who represents New Jersey is told *nobody does*, with no signal
that a filter silently ate the result. That is a wrong answer, not a failure.

**Fix:** code→name normalization before comparison, or filter API-side. Prefer API-side if
the endpoint supports it — it removes the dual representation rather than translating
between them.

**Regression test:** assert non-empty for a known state in both chambers, and assert the
two spellings agree rather than merely that one works.

---

### D2 — top-level `members` / `committees` arrays never populated

Every response carries an empty structured array while all real content sits in a
`summary` markdown blob. `results_count` reports correctly, so **the counter and the
serializer disagree** — which means the data exists at serialization time and is being
dropped on the way out. Programmatic consumers must regex markdown.

**Locus (found 2026-08-04):** `response_converters.py:82`,
`convert_members_committees_response`. The members/committees impls return pre-formatted
markdown, so `_extract_json` returns `None` and control reaches the branch at line 96 that
hard-returns `members=[]`, `committees=[]`, `summary=<raw>`. The array-population code at
lines 108–141 runs only for JSON input, which never arrives. The function's own comment
concedes the empty branch is the normal path for every one of these tools.
`results_count` comes from a separate regex over the markdown (`_extract_result_count`),
which is exactly why the counter reports nonzero against empty arrays.

**Does not block PR 1 — cleared on two independent lines.** *Structural:* the bill-text
tools import no `convert_*_response`; they build their own Pydantic models
(`SearchBillTextResponse`, `BillSectionResponse`, `BillTocResponse`), populate structured
fields inline, and return `model_dump()` directly — no markdown round-trip. *Empirical:*
live against GovInfo, `search_bill_text` returns a populated `hits` list with every §9
`SearchHit` field present, `get_bill_section` returns `text`/`children`/`node_kind`/
`subtree_byte_length`/`truncated` as first-class fields, and neither carries a top-level
summary blob.

**Fix:** populate the structured array; keep the markdown summary as a convenience field,
not the payload. Add the missing verification step (see below).

---

### D3 — amendment records destroy the sponsored-legislation feed

~60% of 350 records rendered as `UNKNOWN Unknown (Congress N) / No title available`.
Offset 300 was 47/50 unusable. The converter reads bill-shaped keys (`type`, `number`,
`title`) against amendment objects, which carry `amendmentNumber` and
`purpose`/`description`.

**Two changes, kept separate:** (a) detect `/amendment/` in the URL and map the correct
fields; (b) add a `type` filter so callers can request bills only. (a) is the defect;
(b) is ergonomics and should not be the fix for (a).

**Pattern worth auditing beyond this bug.** This is the third instance of "every record
carries field X" being false — A3 was null `date` on version records, and amendments are
again where date fields go missing. Grep the converters for unguarded field access on
optional keys; there is likely a fourth.

---

### D4 — feed is not partitioned by congress

Sorting appears to be `updateDate desc`, so recently-touched old measures float into the
middle of the stream: 43 consecutive 114th-Congress amendments between offsets ~81–142;
S 1081/114, S 3742/116, S 4732/117 appearing individually near offset 277, surrounded on
both sides by 119th bills.

**Silent truncation.** A consumer that stops paginating at the first off-target congress
reports a partial answer as complete. The result set is unbounded in time — you cannot
know you are done without walking everything.

**Fix:** `congress` param on both member-legislation tools.

---

### D5 — page boundaries are non-deterministic

0→50 duplicated `samdt/5404` and **dropped** `samdt/5408`. 100→150 duplicated `S 3806`.
50→100 and 150→200 clean. Inconsistent overlap rules out off-by-one and points to an
unstable sort on tied `updateDate` values.

The duplicate is harmless and detectable. **The drop is invisible data loss.**

**Fix:** stable secondary sort key (bill type, then number) plus client-side dedupe in any
exhaustive walk.

---

### D4 + D5 together — the actual headline

Neither is as bad alone as the pair is jointly. **D4 means an exhaustive walk is the only
correct strategy. D5 means an exhaustive walk still loses records.** Together they make
"list all legislation sponsored by member X" unanswerable with confidence — the one
question these tools exist to answer.

Fix them in the same PR and verify them together: walk a member's full feed twice with
different page sizes and assert identical sets. Neither fix alone makes that test pass.

---

### D6 — no summary, introduced date, policy area, or latest action

Member tools return number/type/congress/title only, forcing N+1 calls for any
"summarize each" request.

**The risk is not the extra calls — it is what a less cautious agent does instead.**
Producing the test document required inferring from titles. That works for
`Zero Food Waste Act` and fails completely for acronym titles: `REDACT`, `GAAME`,
`SECURES`, `FOCUS`, `NOTICE`, `PROSPECT`, `RAISE`. 24 entries were marked † rather than
guessed. An agent without that discipline confabulates, and the output looks identical.

Same value system as `amends` precision: a field shape that invites inference is worse
than one that returns nothing.

**Fix:** an `include` param for summary/date/policy-area/latest-action rather than
unconditional inflation of every response.

---

### D7 — `get_bill_summaries` returns raw HTML; absence is ambiguous

S 751 came back with `<p>`, `<strong>`, `&nbsp;` unconverted. Same converter family as D2.

**Second half, separate defect:** S 4977 (introduced ~July 2026) returned the bare string
`No summaries found`, which cannot distinguish **"CRS has not written one yet"** from
**"the lookup failed."** Those warrant different consumer behavior — one is worth
retrying, the other is not. Same ambiguity-of-absence problem §6 worked through for empty
`amends`, and it deserves the same answer: make the two cases distinguishable in the
response rather than in a human's interpretation of a string.

---

### D9 — 16 known-failing tests, repo-scope. Clamped, not fixed.

Pre-existing in the **repo**, not in the bill-text feature. Mostly **MCP 2.x migration**
fallout plus dead code. Outside PR 1 and PR 2 scope by decision, recorded here so the
decision is deliberate rather than forgotten.

**Clamped, correctly.** `tests/KNOWN_FAILURES.md` enumerates all 16 with causes;
`tests/check_known_failures.py` fails on **growth or shrinkage**, both verified by
simulation. Failing only on growth would let a silently-fixed entry leave the list stale
until it is fiction — a bigger version of the problem the clamp solves.

**Two things to note before someone hits them cold:**

**1. The ratchet will fire loudly during the MCP 2.x migration, and that is correct.** Most
of these resolve at once when the migration lands, so the shrinkage check trips on a change
that is *good*. Whoever hits it should update `KNOWN_FAILURES.md`, **not disable the check** —
which is the tempting move at the moment it fires and the one that discards the clamp's whole
value.

**2. The file holds two populations with different lifecycles.** Four entries import
`congress_api.core.services`, **a module that does not exist in the tree**. Those are not
failing tests, they are **dead tests**, and they will never pass — so they are permanent
entries in a list whose other members are all expected to disappear. Mark them, so the
migration cleanup knows which entries should shrink and which need deleting outright. Left
unmarked, they keep the count non-zero forever and train readers to skim a file whose whole
purpose is being read.

**Severity:** hygiene, not correctness. Nothing here affects tool output. It matters because
an unenumerated failing baseline is where a real regression hides, and that risk is now
closed.

---

### D8 — confirmed working, protect with regression tests

- `bills:get_bill_summaries` parsed `"S 751, 119th Congress"` correctly — the flexible
  reference parser works.
- Error envelopes on validation failure carried error type, code, offending parameter,
  and provided value. This is good and unusually complete.
- Latency consistent across nine calls, no timeouts at `limit=50`.

Worth pinning with tests **before** the converter work, since PR A touches the same
serialization path that produces these envelopes.

---

## Sequencing

**Before PR 1 merges:** only the D2 shared-serializer check. If the bill-text tools emit
through the same path, that fix blocks; if not, nothing here does.

**PR A — envelope and converters (D2, D7).** First, despite the blast radius. D2 is about
whether the structured container is emitted at all; B is about what goes in it. Fixing
contents before container means testing contents twice. Run with the converter tests
already in the repo, and pin D8's envelopes first.

**PR B — member legislation feed (D3, D4, D5).** One tool, three defects, one round of
testing. Restores a use case that is currently unanswerable.

**PR C — `search_members` state normalization (D1).** Small and isolated.

**PR D — member response enrichment (D6).** A feature, not a fix. Lowest urgency; changes
response size, so it wants its own measurement.

Do not bundle these into the bill-text PR. Separate PRs keep review honest and keep
`git bisect` useful across 96 operations.

---

## Two process items

**Add a wire-format verification step — V17, now specified in `fulltext/10-fixtures-verification.md`.**
V1–V16 verify the parser and index; none asserts that emitted responses conform to §9.

**Correcting the first draft of this proposal, because D2 is its own counterexample.**
"Assert every §9 field is present and correctly typed" **would have passed D2** —
`members=[]` is present and correctly typed. Presence is not the property; **population
is.** The assertions that discriminate are: non-empty collections on known-matching input;
**count/collection coherence** (a count field must equal the length of what it counts —
D2's signature was exactly that disagreement, and no field-level check can see it); no
prose blob carrying content absent from structured fields; and, for the bill-text tools,
an AST assertion that they import no `response_converters`.

V17 is scoped to the three bill-text tools now. **Extending it across the other 96
operations belongs to PR A**, where it is worth considerably more — those tools have no
model enforcing shape at all, which is how D2 survived.

**Add a characterization test per defect as it is fixed.** This list is a sample from an
untested population; fixing the sampled items says nothing about the population's size.
Without characterization tests, PR 2's end-to-end pass produces a differently-shaped list
rather than a shorter one.
