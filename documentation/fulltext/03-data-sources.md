*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 3. Data sources and the division of labor

Two upstreams, with a strict split of responsibility.

| Concern | Source |
|---|---|
| Does this bill exist? | **congress.gov** |
| Which text versions exist, and when? | **congress.gov** |
| Document content | **GovInfo packages API** |

### Why not congress.gov for content

Its text URL is an HTML rendering with no reliable section structure. It remains the
**metadata index**, never the content source.

### USLM availability — corrected by V1

Earlier drafts of this spec stated that USLM for BILLS was exposed only through
`/bulkdata/BILLS/uslm/` and not through the packages API. **That is false.** A
`uslmLink` is present on the `BILLS-119s1071enr` package summary. Any future USLM work
should target the packages API, not bulk data, and the bulk-data special case is
retired.

**Now closed (V1, live):** `enr` carries `uslmLink`; **`is`, `es`, and `eh` do not.**
USLM is an enrolled-only enhancement permanently — not a transport question and never a
general path. Bill DTD for all versions is the only correct choice, not a compromise.
Any future USLM work is strictly an `enr`-path optimization.

### Why not bulk data as primary

Byte-identical documents, but the path requires the *session* number
(`/bulkdata/BILLS/{congress}/{session}/{type}/`), not derivable from
`(congress, billType, number, version)` — all a caller has. That forces a date lookup or
speculative double-fetch every call for zero benefit. The packages API addresses by
`packageId`, a pure function of bill identity.

```
packageId = f"BILLS-{congress}{bill_type}{number}{version}"
```
e.g. `BILLS-119s1071enr`, `BILLS-119hres463ih`.
`bill_type` lowercase: `hr`, `s`, `hres`, `sres`, `hjres`, `sjres`, `hconres`, `sconres`.

### Version discovery — `/related` alone is circular, do not use it for this

`GET /related/{packageId}` requires a packageId, which **already contains the version**.
It cannot be used to discover the version you don't yet have. An earlier draft of this
spec claimed otherwise; that was wrong.

**Resolution algorithm for `version=None`:**

1. `GET congress.gov /bill/{congress}/{type}/{number}/text` — enumerates text versions
   with type, date, and format URLs.
2. Extract the GovInfo version code from each entry's XML/PDF URL (the URLs embed
   `BILLS-{congress}{type}{number}{code}`). If a code cannot be extracted from a URL,
   map it from the version-type string using a documented lookup table; log unmapped
   types rather than guessing.
3. **"Latest" = highest precedence, with date as tie-break within a tier.**
   Not latest legislative action, and **not date-primary.**

   > **Amendment A3 (spec error, found live).** This step originally read "latest =
   > greatest text-version date," which assumed every version carries a date.
   > Congress.gov returns **`date: null` for Enrolled Bill entries**, so a date-primary
   > sort buries `enr` last and precedence 90 never applies. Live: `version=None` on
   > S.1071 resolved to `eah`, meaning the motivating icebreaker query read the wrong
   > document.
   >
   > **Handling the null is patching around a wrong default.** Version codes carry the
   > legislative ordering intrinsically (introduced → reported → engrossed → enrolled);
   > the date is the weaker signal — nullable, tie-prone, and the thing that broke.
   > Precedence-primary makes the null irrelevant rather than special-cased and needs no
   > extra network call, so backfilling from GovInfo `dateIssued` is unnecessary.

4. **Sort key:** `(precedence DESC, date DESC, version_code ASC)`. Date is the tie-break
   *within* a precedence tier — its actual use, e.g. two engrossed versions. Missing
   dates sort last within their tier and do not affect tier selection.

   **Unknown version codes get precedence 0**, lose to any known code, and are logged
   loudly. If *every* available version has an unknown code, fall back to date-primary
   among them and say so in `version_resolution_note`.

   > **Amended 2026-08-04 — surface the partial case too, not only the total one.**
   > The note fired only when *every* code was unknown. **That surfaces the safer case and
   > hides the more dangerous one.** With all codes unknown, the resolver falls back to
   > date-primary and probably lands right. With *some* unknown, a new code marking the
   > newest stage gets precedence 0 and **sorts last**, so a genuinely older version wins —
   > actively wrong, and silent in the response.
   >
   > "Loud in the log" was accepted as sufficient detectability, but it is detectable **by
   > an operator watching logs**, not by the caller. The caller is a model answering a
   > legislative question from the wrong version of a bill, with nothing in the response to
   > indicate it. That is the `state="NJ"` shape again: a wrong answer inside a success
   > envelope.
   >
   > **Rule:** emit `version_resolution_note` whenever the version list contained **any**
   > unrecognized code, naming the code(s), and stating that the selection may not reflect
   > the newest version. Fire it **only when `version=None`** — if the caller named a
   > version, resolution made no choice and the note is noise. Frequency is near zero until
   > GPO adds a code, which is exactly when it is wanted.
   >
   > The WARNING log stays; it is now pinned by
   > `test_order_versions_logs_unknown_codes_loudly` and remains the operator-side signal.
   > The note is the consumer-side one. Both, not either.

   > **Validated end-to-end 2026-08-06, and it found a real gap.** §17 traces show
   > `version: null` calls resolving to `enr` **while warning that an unrecognized `rfs`
   > code had been sorted after recognized versions and might conceivably be newer** — the
   > partial-unknown case firing exactly as ruled. The consumer then **acted on the note**,
   > supplying `version: "enr"` explicitly on subsequent calls. Ruling correct,
   > implementation correct, consumer response correct.
   >
   > **The gap it exposes: `rfs` is a real GPO code missing from the precedence table.**
   > (Referred in Senate — it belongs in the referred tier alongside `ih`/`is`/`rih`/`ris`.)
   > Add it, and **audit the table against GPO's full published code list** rather than
   > adding this one and waiting for the next warning. The note is a safety net for codes
   > that appear after an audit, not a substitute for doing one.

   **Invariant to assert:** if an `enr` version exists, `version=None` must resolve to
   it. Enrolled is terminal for the BILLS collection, so this holds for every bill.

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

   > **Audit against GovInfo's published list, 2026-08-06
   > (https://www.govinfo.gov/help/bills). The table covers 17 of 53 codes, and two of the
   > 36 gaps are correctness bugs, not coverage gaps.**
   >
   > **1. `renr` — Re-enrolled Bill — outranks `enr`, and currently sorts last.** A
   > re-enrolled bill is the corrected final text. Under the present table `renr` gets
   > precedence 0, so **`enr` wins and the resolver returns superseded text as final.**
   > Same class of defect as A3, in the terminal tier where it matters most.
   >
   > **2. Simple and concurrent resolutions have no terminal code in the table at all.**
   > They never receive `enr`. Their terminal version is `ath` / `ats` (Agreed to by
   > House/Senate), both absent, both therefore precedence 0. **For every agreed-to
   > resolution the resolver prefers `ih` over the agreed-to text.**
   >
   > **Testable prediction, and it touches a fixture.** `hres463` resolved to
   > `BILLS-119hres463ih`, and §17's B2 answer volunteered *"this is the **introduced**
   > text… the operative language could differ."* **If `hres463` has an `ath` version, that
   > answer was drawn from a superseded document and the consumer flagged the exact defect.**
   > Check it.
   >
   > **§3's own invariant is wrong twice over.** *"If an `enr` version exists, `version=None`
   > must resolve to it. Enrolled is terminal for the BILLS collection, so this holds for
   > every bill."* `renr` supersedes `enr`; resolutions never reach `enr`. Two descriptive
   > claims about the domain, both checkable against the authoritative source, neither
   > checked — the A3 pattern again.

   ### The model is incomplete, not just the table

   Completing 53 rows is not sufficient, because a **single linear scale cannot express
   what these codes mean.** GovInfo's list contains at least three kinds that are not
   stages:

   | Kind | Codes | Why rank alone fails |
   |---|---|---|
   | **Administrative** | `ash` `sas` `sc` (sponsor changes), `oph` `ops` (ordered printed) | Chronologically later, textually identical to the stage they annotate. Should not displace it. |
   | **Negative terminal** | `fph` `fps` `fah` (failed), `lth` `lts` (tabled), `iph` `ips` (postponed), `pav` (vitiated) | **Chronologically last and not authoritative.** A failed-passage version must never be "latest." |
   | **Re-issues** | `renr`, `reah`, `res` | Must outrank the version they re-issue, not merely sit near it. |

   Assign each code a **category** as well as a rank. `latest` means *most authoritative
   text*, not *most recent artifact*, and for the negative-terminal class those diverge.

   **Cross-chamber codes need placement too:** `rfh` / `rfs` (referred after receipt from
   the other chamber) carry the originating chamber's passed text and sit after engrossment,
   not with `ih` / `is`. `rfs` is the code that triggered the live warning in §17.

   `pp` is absent while its sibling `pap` sits at 30; they are peers.

   **Keep the unknown-code warning after the audit.** GovInfo adds codes; the note is the
   safety net for what an audit cannot anticipate, not a substitute for doing one.
5. Construct the packageId and fetch from GovInfo.
6. **If GovInfo 404s a version congress.gov lists** (publication lag), fall back to the
   next-latest and set `version_resolution_note` explaining the substitution. Do not
   fail the call.

**Bill existence and the 404 distinction** come from step 1, not from GovInfo. If
congress.gov has no such bill → "no such bill." If it has the bill but not that version
→ error listing the versions that do exist.

**Fallback if congress.gov is unavailable:** GovInfo search service, POST `/search` with
`collection:BILLS congress:{c} billtype:{t} docnumber:{n}`, which returns all versions as
separate packages. Secondary path only.

### Rate limits

GovInfo documents 36,000 req/hour, 1,200/min, 40/sec. Congress.gov's measured ceiling is
**20,000/hour** — on the same key.

**V12 settled this: the buckets are independent.** Three GovInfo calls left the
congress.gov counter unchanged. Indexing cannot starve the existing congress.gov tools,
and no cross-service quota accounting is needed. Handle 429 with bounded exponential backoff plus jitter;
respect `Retry-After` on **both 429 and 503**, capped at a maximum wait.

Refetching a document is **one additional document download** — rate-limited and
counting against quota. Not "unmetered."

---

---

## Struck-in-committee text — an unexamined third context

GovInfo's bills help page documents how change is marked in bill **text** files:

- **Added** text is enclosed in quotation marks — *"these quotes should not be confused
  with the quotation marks that are part of the text of the bill."*
- **Deleted** text is wrapped in `<DELETED>` … `</DELETED>` tags.

**The question §6's segment model has never been asked:** does the **Bill DTD XML** carry an
equivalent representation of committee-struck text, and if so, what context does the parser
assign it?

This matters because the segment model has three contexts — `operative`, `quoted`,
`header` — and struck-in-committee text is **none of them.** If it parses as `operative`,
the tool presents text a committee **removed** as text the bill contains. That is the
amendatory trap in a second guise, at a layer V4 does not cover: V4 guards *quoted*
material, not *deleted* material.

**Why the fixture set cannot have caught it.** Struck text appears in **reported** versions
(`rh`, `rs`) — the stage where a committee's changes are shown against the introduced text.
Every fixture in the corpus is `enr`, `eh`, or `is`. **The extended scan corpus is 18
enrolled packages.** No reported version has ever been parsed.

**Check, in order:** whether Bill DTD XML represents deleted text at all; if so, what the
parser currently emits for it; and if it emits `operative`, whether a fourth context or an
exclusion is required. Add one `rs` or `rh` package to the extended corpus either way —
an entire version class is currently unrepresented, which is how the intro-labelling
hazard stayed latent at 0-of-53.
