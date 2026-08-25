*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 3. Data sources and the division of labor

Two upstreams, with a strict split of responsibility.

| Concern | Source |
|---|---|
| Does this bill exist? | **congress.gov** |
| Which text versions exist, and when? | **congress.gov** |
| Document content | **GovInfo packages API** |

### Why not congress.gov for content

Its text URL is an HTML rendering with no reliable section structure. It remains the **metadata index**, never the content source.

### USLM availability — corrected by V1

Earlier drafts of this spec stated that USLM for BILLS was exposed only through `/bulkdata/BILLS/uslm/` and not through the packages API. **That is false.** A `uslmLink` is present on the `BILLS-119s1071enr` package summary. Any future USLM work should target the packages API, not bulk data, and the bulk-data special case is retired.

**Now closed (V1, live):** `enr` carries `uslmLink`; **`is`, `es`, and `eh` do not.** USLM is an enrolled-only enhancement permanently — not a transport question and never a general path. Bill DTD for all versions is the only correct choice, not a compromise. Any future USLM work is strictly an `enr`-path optimization.

### Why not bulk data as primary

Byte-identical documents, but the path requires the *session* number (`/bulkdata/BILLS/{congress}/{session}/{type}/`), not derivable from `(congress, billType, number, version)` — all a caller has. That forces a date lookup or speculative double-fetch every call for zero benefit. The packages API addresses by `packageId`, a pure function of bill identity.

```
packageId = f"BILLS-{congress}{bill_type}{number}{version}"
```
e.g. `BILLS-119s1071enr`, `BILLS-119hres463ih`. `bill_type` lowercase: `hr`, `s`, `hres`, `sres`, `hjres`, `sjres`, `hconres`, `sconres`.

### Version discovery — `/related` alone is circular, do not use it for this

`GET /related/{packageId}` requires a packageId, which **already contains the version**. It cannot be used to discover the version you don't yet have. An earlier draft of this spec claimed otherwise; that was wrong.

### Version discovery — requirement recorded 2026-08-20 (maintainer, resolving #4)

**The requirement:** a consumer must be able to ask what versions of a bill exist, and retrieval of any named version must work — **with the default unchanged: `version=None` always resolves to the most authoritative** (the maintainer reaffirmed A3's precedence-primary rule in the same ruling).

**What is already satisfied:** pinned retrieval — all three tools take `version` (§4), and `version_not_available` errors list the available versions. **What is new is only the affirmative surface:** today the version inventory reaches a consumer exclusively through an error, so discovering versions requires provoking a failure. **Partially discharged 2026-08-24 (maintainer ruling, recorded at Q3 of `../govinfo-search-spec.md`):** the rebuilt `search_bills` becomes the affirmative surface — hits carry `matched_versions`, and a fielded `congress:/billtype:/docnumber:` query through the same tool returns a bill's exact version set (measured live, S. 1071 → 4/4). The `version_not_available` error remains the pinned-version case's disclosure; whether anything of this requirement remains after that fix ships is judged then.

**The data is already in hand — no new upstream call is required.** The resolution algorithm below enumerates every text version (congress.gov `/text`, GovInfo fallback) on each `version=None` call; the server computes the full inventory and then discards all but the winner. Surfacing it is a **response-surface question, not a data-source question**. The maintainer named `/related` as a candidate mechanism; note the section above — `/related` is circular for *resolution* but is usable for *discovery given one packageId* (the resolved winner). It is recorded as a fallback candidate only: the resolver's own enumeration is strictly cheaper (zero extra calls) and already battle-tested through F20/F21/F25. If `/related` is ever reached for instead, its behavior must be measured first (does `/related/{packageId}` actually enumerate sibling BILLS versions? — one call on `119s1071enr` answers it).

**Surface design deliberately left open for PR 2 planning**, with the candidates and the governing consideration recorded: (a) a new `list_bill_versions` tool; (b) an opt-in flag on `get_bill_toc` (the navigation tool); (c) an always-on envelope field — (c) is rejected now as width on every response for a sometimes-question. Between (a) and (b), the §17 adoption measurements are the governing consideration: tool count and description obligations tax the adoption layer, which is the measured failing layer on non-Claude consumers — so the smaller routing-surface change is favored unless discoverability evidence says otherwise. Whatever ships keeps the A3 default, the `version_resolution_note` contract, and states its semantics in the tool description (§7 rule).

**Scope: not PR 1.** PR 1's parked #4 is closed by the delete ruling (register D12); this requirement queues with PR 2 planning.

**Resolution algorithm for `version=None`:**

1. `GET congress.gov /bill/{congress}/{type}/{number}/text` — enumerates text versions with type, date, and format URLs.

   > **F28 (latent, surfaced by the F21 work, 2026-08-14) — the enumeration is capped at 20 and the cap is undisclosed.** `make_api_request` applies `DEFAULT_REQUEST_PARAMS` incl. `limit: 20` (the same implicit server default the pre-F21 bypass got, so **F21 changed nothing here** — it is pre-existing, not a regression). But if a bill has **more than 20 text versions**, the resolver sees only 20, and if the true-latest (`enr`) falls outside that page, `version=None` **resolves to a superseded version with nothing disclosed** — the F1 wrong-document class, via pagination rather than precedence. *Owed measurement, not a claimed P0* (the F20 lesson): count the max text-versions per bill across a broad sample and confirm whether the endpoint paginates; **if no real bill exceeds ~20 versions this is dead-defensive**, if any does it is a live wrong-document risk needing pagination or an explicit `limit`. Route to the implementer with the measurement; do not rank until it runs.
   >
   > **RESOLVED 2026-08-14 (maintainer ran it) — dead-defensive.** Sample: **250 bills each from the 118th and 119th congresses (500 total), max = 5 text versions.** Against the `limit: 20` cap that is a **4× margin**, so the truncation is theory, not practice — no change required. *Scope caveat, minor:* the sample is two recent congresses and did not probe a pathological historical tail, but a bill with >20 distinct version stages is essentially unheard of and the 4× headroom absorbs a large error. **Optional near-zero hardening if ever wanted:** disclose on cap-hit — if the enumeration ever returns *exactly* `limit`, set a truncation note — which converts the (currently unreachable) silent wrong-document risk into a disclosed one per the "no silent caps" convention. Not required at a 4× margin.
2. Extract the GovInfo version code from each entry's XML/PDF URL (the URLs embed `BILLS-{congress}{type}{number}{code}`). If a code cannot be extracted from a URL, map it from the version-type string using a documented lookup table; log unmapped types rather than guessing.
3. **"Latest" = highest precedence, with date as tie-break within a tier.** Not latest legislative action, and **not date-primary.**

   > **Amendment A3 (spec error, found live).** This step originally read "latest = greatest text-version date," which assumed every version carries a date. Congress.gov returns **`date: null` for Enrolled Bill entries**, so a date-primary sort buries `enr` last and precedence 90 never applies. Live: `version=None` on S.1071 resolved to `eah`, meaning the motivating icebreaker query read the wrong document.
   >
   > **Handling the null is patching around a wrong default.** Version codes carry the legislative ordering intrinsically (introduced → reported → engrossed → enrolled); the date is the weaker signal — nullable, tie-prone, and the thing that broke. Precedence-primary makes the null irrelevant rather than special-cased and needs no extra network call, so backfilling from GovInfo `dateIssued` is unnecessary.

4. **Sort key:** `(precedence DESC, date DESC, version_code ASC)`. Date is the tie-break *within* a precedence tier — its actual use, e.g. two engrossed versions. Missing dates sort last within their tier and do not affect tier selection.

   **Unknown version codes get precedence 0**, lose to any known code, and are logged loudly. If *every* available version has an unknown code, fall back to date-primary among them and say so in `version_resolution_note`.

   > **Amended 2026-08-04 — surface the partial case too, not only the total one.** The note fired only when *every* code was unknown. **That surfaces the safer case and hides the more dangerous one.** With all codes unknown, the resolver falls back to date-primary and probably lands right. With *some* unknown, a new code marking the newest stage gets precedence 0 and **sorts last**, so a genuinely older version wins — actively wrong, and silent in the response.
   >
   > "Loud in the log" was accepted as sufficient detectability, but it is detectable **by an operator watching logs**, not by the caller. The caller is a model answering a legislative question from the wrong version of a bill, with nothing in the response to indicate it. That is the `state="NJ"` shape again: a wrong answer inside a success envelope.
   >
   > **Rule:** emit `version_resolution_note` whenever the version list contained **any** unrecognized code, naming the code(s), and stating that the selection may not reflect the newest version. Fire it **only when `version=None`** — if the caller named a version, resolution made no choice and the note is noise. Frequency is near zero until GPO adds a code, which is exactly when it is wanted.
   >
   > The WARNING log stays; it is now pinned by `test_order_versions_logs_unknown_codes_loudly` and remains the operator-side signal. The note is the consumer-side one. Both, not either.

   > **Validated end-to-end 2026-08-06, and it found a real gap.** §17 traces show `version: null` calls resolving to `enr` **while warning that an unrecognized `rfs` code had been sorted after recognized versions and might conceivably be newer** — the partial-unknown case firing exactly as ruled. The consumer then **acted on the note**, supplying `version: "enr"` explicitly on subsequent calls. Ruling correct, implementation correct, consumer response correct.
   >
   > **The gap it exposes: `rfs` is a real GPO code missing from the precedence table.** (Referred in Senate — it belongs in the referred tier alongside `ih`/`is`/`rih`/`ris`.) Add it, and **audit the table against GPO's full published code list** rather than adding this one and waiting for the next warning. The note is a safety net for codes that appear after an audit, not a substitute for doing one.

   **Invariant to assert:** if an `enr` version exists, `version=None` must resolve to it. Enrolled is terminal for the BILLS collection, so this holds for every bill.

   Precedence table:

```
ih is rih ris → 10      introduced / referred
rh rs rch rcs → 20      reported
pcs pap       → 30      calendar
eh es eah eas → 40      engrossed
cph cps       → 50      considered/passed
enr           → 90      enrolled
```
   Codes absent from the table get precedence 0 and sort last.

   > **Audit against GovInfo's published list, 2026-08-06 (https://www.govinfo.gov/help/bills). The table covers 17 of 53 codes, and two of the 36 gaps are correctness bugs, not coverage gaps.**
   >
   > **1. `renr` — Re-enrolled Bill — outranks `enr`, and currently sorts last.** A re-enrolled bill is the corrected final text. Under the present table `renr` gets precedence 0, so **`enr` wins and the resolver returns superseded text as final.** Same class of defect as A3, in the terminal tier where it matters most.
   >
   > **2. Simple and concurrent resolutions have no terminal code in the table at all.** They never receive `enr`. Their terminal version is `ath` / `ats` (Agreed to by House/Senate), both absent, both therefore precedence 0. **For every agreed-to resolution the resolver prefers `ih` over the agreed-to text.**
   >
   > **Testable prediction, and it touches a fixture.** `hres463` resolved to `BILLS-119hres463ih`, and §17's B2 answer volunteered *"this is the **introduced** text… the operative language could differ."* **If `hres463` has an `ath` version, that answer was drawn from a superseded document and the consumer flagged the exact defect.** Check it.
   >
   > **§3's own invariant is wrong twice over.** *"If an `enr` version exists, `version=None` must resolve to it. Enrolled is terminal for the BILLS collection, so this holds for every bill."* `renr` supersedes `enr`; resolutions never reach `enr`. Two descriptive claims about the domain, both checkable against the authoritative source, neither checked — the A3 pattern again.

   ### The model is incomplete, not just the table

   Completing 53 rows is not sufficient, because a **single linear scale cannot express what these codes mean.** GovInfo's list contains at least three kinds that are not stages:

   | Kind | Codes | Why rank alone fails |
   |---|---|---|
   | **Administrative** | `ash` `sas` `sc` (sponsor changes), `oph` `ops` (ordered printed) | Chronologically later, textually identical to the stage they annotate. Should not displace it. |
   | **Negative terminal** | `fph` `fps` `fah` (failed), `lth` `lts` (tabled), `iph` `ips` (postponed), `pav` (vitiated) | **Chronologically last and not authoritative.** A failed-passage version must never be "latest." |
   | **Re-issues** | `renr`, `reah`, `res` | Must outrank the version they re-issue, not merely sit near it. |

   Assign each code a **category** as well as a rank. `latest` means *most authoritative text*, not *most recent artifact*, and for the negative-terminal class those diverge.

   **Cross-chamber codes need placement too:** `rfh` / `rfs` (referred after receipt from the other chamber) carry the originating chamber's passed text and sit after engrossment, not with `ih` / `is`. `rfs` is the code that triggered the live warning in §17.

   `pp` is absent while its sibling `pap` sits at 30; they are peers.

   > **Digit-suffixed reissues (`pcs2`, `rh2`, `eas2`) — CONTINGENT ruling, F20 follow-on, 2026-08-14. Existence CHECKED — GovInfo search returns **zero** for `ih2`/`pcs2`/`enr2`; confirmed dead-defensive. Read the grounding note (point 3) first.** When F20 fixed the enumeration regex so digit-suffixed codes *survive*, it raised a ranking question: if such a code appeared, it is not a table entry, so `order_versions` would score it as an **unknown code** and the superseded base print (`pcs`) would win "latest." This block rules how they *would* rank — but **no real digit-suffixed BILLS package has been observed** (point 3), so this governs a case that may never occur. It is a §3 ruling recorded here rather than left to the resolver; it is **gated on existence**, not a live P0.
   >
   > **1. A code of the form `<known-base><digits>` is a *reissue of that base*, not an unknown code.** It **inherits the base's precedence rank and category** and is tagged `REISSUE` — the same principle as `renr`/`reah`/`res` (a reissue must outrank the version it reissues), reached by **decomposition** rather than by minting a table row for every `pcsN`/`rhN`/`easN`. This alone kills the F20 residual: `pcs2` now ranks *at* `pcs`, never below it as an unknown.
   >
   > **2. Order within a base by the suffix, above date.** The numeric suffix denotes a later reprint, so the reissue outranks the base print. Implement as a sort key **`reissue_number DESC` placed above `date DESC`** in the existing `(precedence DESC, …, date DESC, code ASC)` order — so the reissue wins even when the date is equal, missing, or null. This is the **same no-date-dependence rationale that earned `renr` an explicit rank above `enr`**; relying on date alone would reintroduce the A3 null-date fragility for reissues.
   >
   > **3. Grounding — the owed measurement is EXISTENCE, before direction. No real example is in hand.** The `pcs2`/`rh2`/`eas2` names trace to two sources, **neither a corpus sighting**: the code reviewer listing them as strings the *primary* regex `[a-z0-9]+` would admit, and the implementer's F20 test using a **mocked** `BILLS-119hr1234pcs2` with a **fabricated** date (`2025-06-02`). An earlier draft of this ruling cited that mock date as "a confirming observation" — **that was an error, corrected here: a test fixture is not evidence.** Positive checks run 2026-08-14: GovInfo's documented version-code set (`/help/bills`, ~53 codes incl. the prefix reissues `renr`/`reah`/`res`) contains **no digit-suffixed code**; two web searches surfaced **no real `<base>N` package**. Absence of evidence is not proof of absence — GovInfo says its list is non-exhaustive — but there is currently **zero** evidence these occur.
   >
   > **The decisive existence check** (hand to the maintainer): the GovInfo search **`billVersion` facet** enumerates the version codes actually present in the BILLS collection — if no digit-suffixed value appears there, points 1–2 are **dead-defensive** and this ruling is moot until GPO mints one. *Only if a real `<base>N` is found* does the direction question open: *expected* — it is dated no earlier than its base and is a later print of the same stage; *falsifier* — any `<base>N` dated earlier, or a suffix marking a different stage, which inverts the tiebreak. Even then the dated case is already correct via `date DESC`; the suffix key matters only for a *null-dated* reissue.
   >
   > **Net for the implementer:** the F20 *fix* is still right — admitting the codes and the letter-initial anchor (which also blocks the real `5eh`-from-bill-12345 cross-bill collision) are correct regardless. But do not treat "superseded print can win" as a demonstrated P0: it was shown only on synthetic data. Run the facet check before building the ranking machinery in points 1–2; if the facet has no numbered code, log that and stop.
   >
   > **RESOLVED 2026-08-14 (maintainer ran the check).** GovInfo search returns **zero** results for `ih2` / `pcs2` / `enr2` — no digit-suffixed version code occurs in the BILLS collection. Points 1–2 are therefore **dead-defensive: do not build the ranking machinery.** The F20 *fix* stands (shared pattern + letter-initial collision guard); this ruling is retained only as a contingency should GPO ever mint such a code, and "superseded print can win" is confirmed to have been a synthetic-only outcome, never reachable in production.
   >
   > **4. Do not use a single flat `REISSUE` rank.** `rh2` is a reprint of a *committee-report* stage and `pcs2` of a *calendar* stage; a flat reissue rank would make them comparable to — or let them outrank — `enr`. **Cross-stage order must come from the base's precedence; the suffix orders only within a stage.**
   >
   > **5. No `version_resolution_note` for a recognized-base reissue.** Once `pcs2` resolves as a reissue of the known `pcs`, it is understood, not unknown — the note must **not** fire (that was the false partial-unknown warning the F20 fix surfaced; same F17 "don't cry wolf" discipline). Reserve the unknown-code note for a genuinely unknown **base** (`<unknown><digits>` or a bare unrecognized code).
   >
   > **6. Completeness test extension.** For each of the 53 base codes, assert `<base>2` **decomposes to that base** (inherits its rank+category, is not scored unknown) and **outranks `<base>`**; a future genuinely-new *base* still falls to the unknown path and fails F1's completeness pin loudly. Route back to the implementer: this ruling is the acceptance test for the residual.

   **Keep the unknown-code warning after the audit.** GovInfo adds codes; the note is the safety net for what an audit cannot anticipate, not a substitute for doing one.
5. Construct the packageId and fetch from GovInfo.
6. **If GovInfo 404s a version congress.gov lists** (publication lag), fall back to the next-latest and set `version_resolution_note` explaining the substitution. Do not fail the call.

**Bill existence and the 404 distinction** come from step 1, not from GovInfo. If congress.gov has no such bill → "no such bill." If it has the bill but not that version → error listing the versions that do exist.

**Fallback if congress.gov is unavailable:** GovInfo search service, POST `/search` with `collection:BILLS congress:{c} billtype:{t} docnumber:{n}`, which returns all versions as separate packages. Secondary path only.

> **Fallback-trigger contract (operationalized by F21, `5dd3c69`).** "Unavailable" is decided by **error code, not exception type**, and the resolution step routes through `make_api_request`:
> - **`bill_not_found` (congress.gov 404)** is *definitive* — the bill does not exist. The GovInfo fallback is **not consulted** (asserted by a call counter), preserving "existence comes from step 1, not GovInfo."
> - **`congress_unavailable`** covers everything else that denies a usable answer — **5xx, a non-JSON 200 (e.g. an HTML `Service unavailable` body), and network failure** — and is the **one code `_resolve_versions` treats as recoverable**, so it triggers the GovInfo fallback.
> - A raw `JSONDecodeError` must **never** escape the resolution step (the F21 defect: it jumped the fallback and surfaced as `internal_error`). A malformed body is a `congress_unavailable`, not an internal error.
> - If **both** paths fail, the residual error keeps its **true label** ("Congress.gov was unreachable and the GovInfo search fallback also failed"), never a mislabel.
>
> `congress_unavailable` and `bill_not_found` are therefore load-bearing error codes; see §9's envelope. Routing through `make_api_request` also restores request-counting toward the §17 tally and the `SimpleCache` path (the #15 concern) — the direct-client bypass had lost both.

### Rate limits

GovInfo documents 36,000 req/hour, 1,200/min, 40/sec. Congress.gov's measured ceiling is **20,000/hour** — on the same key.

**V12 settled this: the buckets are independent.** Three GovInfo calls left the congress.gov counter unchanged. Indexing cannot starve the existing congress.gov tools, and no cross-service quota accounting is needed. Handle 429 with bounded exponential backoff plus jitter; respect `Retry-After` on **both 429 and 503**, capped at a maximum wait.

Refetching a document is **one additional document download** — rate-limited and counting against quota. Not "unmetered."

---

---

## Struck-in-committee text — an unexamined third context

GovInfo's bills help page documents how change is marked in bill **text** files:

- **Added** text is enclosed in quotation marks — *"these quotes should not be confused with the quotation marks that are part of the text of the bill."*
- **Deleted** text is wrapped in `<DELETED>` … `</DELETED>` tags.

**The question §6's segment model has never been asked:** does the **Bill DTD XML** carry an equivalent representation of committee-struck text, and if so, what context does the parser assign it?

This matters because the segment model has three contexts — `operative`, `quoted`, `header` — and struck-in-committee text is **none of them.** If it parses as `operative`, the tool presents text a committee **removed** as text the bill contains. That is the amendatory trap in a second guise, at a layer V4 does not cover: V4 guards *quoted* material, not *deleted* material.

**Why the fixture set cannot have caught it.** Struck text appears in **reported** versions (`rh`, `rs`) — the stage where a committee's changes are shown against the introduced text. Every fixture in the corpus is `enr`, `eh`, or `is`. **The extended scan corpus is 18 enrolled packages.** No reported version has ever been parsed.

**Check, in order:** whether Bill DTD XML represents deleted text at all; if so, what the parser currently emits for it; and if it emits `operative`, whether a fourth context or an exclusion is required. Add one `rs` or `rh` package to the extended corpus either way — an entire version class is currently unrepresented, which is how the intro-labelling hazard stayed latent at 0-of-53.
