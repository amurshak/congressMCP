*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 0. Scope for this iteration

**In scope:** GovInfo client, Bill DTD XML parsing, structural chunking, segment-level
FTS5 index, three MCP tools, local cache with LRU eviction and recovery, a cache CLI,
README.

**Explicitly out of scope — do not implement:**

- **USLM ingestion.** Not this iteration. Bill DTD only, for every version including
  `enr`. V1 has since confirmed `uslmLink` **does** exist on BILLS package summaries —
  this does not change scope, it changes what a *future* iteration would build against.
- Cross-version diffing (Bill DTD section GUIDs are not stable across versions).
- Embedding/vector search.
- Amendment-direction inference.
- **Resolving named-Act titles.** The U.S. Code shorthand form is now IN scope (see
  §6, amendment A1); named-Act forms are not. "Section 3 of the Food and Nutrition Act
  of 2008" is never mapped to the Act — only its parenthetical U.S. Code cite is.
  **This explicitly includes the Internal Revenue Code cited by bare section number.**
  Settled boundary, not a gap to close later — see §6 "Not covered."

### PR split — implement PR 1

Produce the split proposal in the issue, then **implement PR 1** unless the issue
explicitly asks for a single PR.

- **PR 1:** GovInfo client, version resolution, parsing, chunking, segment model, FTS5
  index built **in memory**, the three tools, CLI skeleton. Fully functional; re-parses
  on every call.
- **PR 2:** persistence, cache layout, LRU eviction, recovery, freshness, README.

Sections below marked **[PR2]** belong to the second PR. Everything else is PR 1.

---

---

## 1. Deployment context

Runs **locally on the user's machine over stdio**. Not a hosted service.

1. **Disk is the user's disk.** Size-capped, LRU-evicted, conventional platform location.
2. **Latency is felt by a waiting client.** First-call indexing of a large bill takes
   seconds; clients may have timeouts.
3. **This is an architectural change.** congressmcp has been a thin veneer over
   `api.congress.gov`. It now fetches multi-megabyte documents, parses them, builds
   full-text indexes, and persists them locally.

### The problem

Motivating query: **"What does the NDAA say about icebreakers?"** ~1100+ pages. Any
design returning whole bills — or whole tables of contents — into a context window has
failed. This is a **retrieval** problem; XML is parsed server-side and the model never
sees raw markup.

---

---

## 2. API key: reuse the existing one — NOT a setup change

**api.congress.gov and api.govinfo.gov both sit behind the api.data.gov gateway, and one
api.data.gov key works for both.** The Library of Congress directs Congress.gov users to
the Data.gov signup page (the endpoint is `api.data.gov/congress/v3`); GovInfo says to
use an existing api.data.gov key. Keys are reusable across participating services.

**Existing users change nothing.** Do not add a required credential.

- **Default:** reuse whatever env var the repo already uses for the congress.gov key.
  Read the repo; do not invent a name.
- **Optional override:** `GOVINFO_API_KEY`, used only if set.
- **Probe, do not assert.** On 401/403 **specifically from `api.govinfo.gov`**, emit a
  targeted error: the existing key was rejected by GovInfo, these services normally
  share one api.data.gov key, `GOVINFO_API_KEY` overrides. Not a raw passthrough.
- **The server must start regardless.** No startup credential validation.
- **Never persist the key** in `govinfo_url`, logs, cached URLs, or error payloads.

---

---

## 15. Constraints

- Follow existing congressmcp conventions for tool registration, HTTP client, config, and
  error types. Read neighboring implementations first.
- **No new dependencies.** Hand-roll cache-dir resolution rather than adding
  `platformdirs`. Do not add an HTTP library or XML parser if one is already present.
- Out-of-scope list in §0 is binding.
- Unit tests run against committed trimmed fixtures, never live network. Live acceptance
  runs are opt-in and use the gitignored developer cache.

---

## 16. Report on completion

Results for every V-step; the V2 measurements including the fetch/parse/index split;
V3/V4 acceptance outcomes; which version of 119hr1 carries the RECA expansion; whether
the enrolled S. 1071 carries the Polar Security Cutter provisions and in which division;
whether `uslmLink` now exists; the real quoting element names; tokenizer behavior;
the V12 rate-limit finding; the V13 `amends` false-positive rate and the concrete
verb-proximity window used; whether a non-enrolled package carries `uslmLink`; and any
design choice you had to make that this spec did not cover.

**Documented boundary settled by the implementation:** `amends` stops at the U.S. Code
and does not resolve named Acts, including the IRC by bare section number. Evidence:
119hr1 `S:70401` carries both anchored and bare forms **within one section**, so a
mapping would fire on drafting style rather than on substance. Recorded as a stated
limitation, not a gap.

**Process note.** Two HIGH defects traced to spec errors (§3 assumed every version
carries a date; §5 never said where `<preamble>` sits) — the implementation was faithful
to what it was given. But the credential-free steps V5/V7/V9/V10 were skipped despite the
implementer's own status block flagging that they needed no credentials and should land
first, and V5 against a real resolution was the check that would have caught the largest
bug. Both are true; neither excuses the other.

**Flag intentional divergences as amendments, not drift.** **Five now exist** — A1
(`amends` two-form), A2 (`timing` block), A3 (version resolution), A4 (structural
discovery, later extended to bind every unit-emitting path), A5 (longhand USC verb gate).
Number the next A6. Any further divergence is recorded the same way: what the spec said,
what was measured, what changed, and why the measurement beat the spec.

### Still unanswered as of 2026-08-04 — these gate the completion report

Verification is complete (V1–V17) and the merge list is closed, but several §16 questions
have no answer on the record. **"All V-steps pass" is not the completion bar; this list
is.**

- Which version of 119hr1 carries the RECA expansion.
- Whether `uslmLink` now exists, and whether any **non-enrolled** package carries it. This
  one has standing consequences: USLM being enrolled-only is why Bill DTD was chosen for
  all versions, and it is on the settled list. If that changed upstream, the settled item
  needs re-examining rather than silently aging.
- Tokenizer behavior, stated concretely rather than by reference.
- Any design choice made that this spec did not cover — the open-ended item, and the one
  most likely to be skipped. A5, the intro-labeling fix, and V17's scoping all began as
  decisions someone could have made silently.

**Answered 2026-08-04 — self-sufficiency.** The three tools resolve, fetch, and navigate
from `congress` + `bill_type` + `number` alone, with no dependency on the other 96
operations. `CONGRESSMCP_BILL_TEXT_ONLY` makes that enforceable rather than merely true.
This was a design choice the spec never stated and belongs in the completion report.

**Answered since this section was written:** the real quoting element names (`<quote>`,
`<quoted-block>`; V16 sampled 5,176 of them), the V12 rate-limit finding, the V13
false-positive rates per form, the verb-proximity window — now an exact adjacency rule
rather than a window, see A5 — and S. 1071's Coast Guard content, which is Division G.
