*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

# 17. End-to-end prompt suite

## What this tests that V1–V18 cannot

V-steps measure the parser, the index, and the wire. **This suite measures the consumer.**
The three tools have exactly one user — a model — and the failure that matters most is the
one where **the tool behaves correctly and the model still answers wrongly**. `match_contexts`
can be present and correct on every hit and the safety property still fails at the system
level if the model does not act on it. No V-step can see that; V4 passes either way.

That failure is a **tool-design defect**, not a code defect. The fix is a tool description,
a field name, a response shape — not a parser change. Which is why these runs belong before
merge, not after.

## Method — the priming problem is the whole methodology

**Run cold. Do not identify yourself as the developer, and do not ask for diagnostics.**
Both change the thing being measured. A model told a developer is watching becomes more
careful, more hedged, more explicit about provenance — which is precisely the behavior
Group A exists to detect the absence of. "Output diagnostics" is worse: it invites
meta-commentary that substitutes for the natural answer, and yields *"the hit carries
`match_contexts: ['quoted']`, so this is inserted text"* — evidence the model **can** read
the field when told to, not that it **does**.

**Capture the tool-call trace out-of-band instead.** Server-side logging on the dev MCP
instance, or the client's own tool-call display. The trace is needed; asking the model for
it is what contaminates.

### Trace mode — the capture mechanism this method depends on

An environment-gated mode writing every invocation and response. Four constraints, each
of which this project has already been bitten by in a different form.

**1. Redact secrets, and assume the key is in the URL until proven otherwise.** §11 governs
this. The GovInfo key travels as a **query parameter** unless the `X-Api-Key` migration has
landed — which is one of the freeze-now items still unreconciled in the commit list. A
trace that logs request URLs verbatim therefore writes a live API key to disk, and traces
are exactly the artifact someone pastes into an issue. Redact at write time, not at read
time, and add a test asserting no logged line matches the key.

**2. Log the object that is returned, not a re-render of it.** Serialize from the same
`model_dump()` output the caller receives, after serialization, not from an internal
representation. **A trace built on a parallel serialization path can look correct while the
wire is wrong** — that is D2's exact shape, two paths disagreeing about the same data. The
trace is only evidence if it is the same bytes.

**3. Stamp each entry for replay.** Timestamp, tool name, arguments as issued, response,
duration, and — extending the two-fixture stamping policy already in force —
`package_id`, version, and source `sha256`. A trace that cannot be tied to a specific
document is unreadable three weeks later. JSONL, one object per invocation: greppable,
diffable, and re-scorable after the fact, which prose is not.

**4. Off by default, and provably so.** Prefer `CONGRESSMCP_TRACE_DIR=<path>` over a boolean
— presence enables and names the destination in one step, so there is no "set it to false
and it stayed on" failure and no default location to write to by accident. Test that
nothing is written when the variable is unset. A tracing mode that silently defaults on is
a disclosure risk, not a convenience. Write outside the production cache; §13 already
requires the developer cache and the production cache not share a directory, and the same
reasoning applies here.

**What the trace does not capture.** It records what the server received and returned by
**the three bill-text tools only**. It does not record the model's answer, which is the
thing being scored — and it does not record **any other tool, web search, or model prior**.
A claim absent from the trace may have been invented, or retrieved somewhere this
instrument cannot see; the two are indistinguishable here. **Do not call a claim fabricated
on trace-absence alone** — verify the fact independently first. The verbatim
answer still comes from the client. Keeping both is the point — the failure that matters
most is correct data in the trace paired with a wrong answer in the transcript, and that is
invisible in either record alone.

### The diagnostic ladder — only for failures, each rung localizing the defect

1. **Cold.** Natural question, natural answer, trace captured externally. Scores the system.
2. **Justify.** Fresh session, same prompt, then: *"how did you determine that?"* Separates
   **data absent** (code defect) from **data present but unused** (tool-design defect).
3. **Hint.** Fresh session, same prompt plus a nudge — *"note whether any of the text is
   quoted."* If the hint fixes it, the fix belongs in the **tool description**. If it does
   not, the fix belongs in the **response shape**.

Never identify as the developer on any rung. "The developer is asking" makes a model hunt
for problems and manufacture caveats, which reads as a pass.

### Other method notes

- **Fresh session per prompt, no project context.** Not merely one session per group —
  **every prompt runs in its own incognito session.** A model that has just been told about
  the amendatory trap will handle it correctly and prove nothing, and a model that learned
  a workaround on the previous prompt is no longer a cold consumer.
- **Consequence, and it cuts both ways.** Findings that recur across prompts are
  **independent samples**, which makes them far stronger than one session tripping the same
  thing repeatedly — the trailing period was hit by four separate sessions, the
  phrase-matching zero-hit problem by two. But it also means any comparison *between* two
  prompts has no shared control, so a difference between them cannot be attributed to the
  prompt without replication.
- **Record the answer verbatim, not a summary.** These failures live in phrasing —
  *"the bill requires X"* versus *"the bill inserts X into existing law"* is the entire
  distinction, and it disappears in a paraphrase.
- **Score the answer, not the tool call.** Correct call plus wrong answer is a **fail**, and
  the most informative kind: the response carried the right data in a shape the consumer did
  not use.
- Note which tool the model reached for first. Wrong-tool-first is a description defect.
- Substitute concrete phrases from the V4 harness output where a prompt calls for one.
- **Every prompt asserting a document property must cite its evidence.** A3 was confounded
  by an unchecked assumption that "section 804" was unambiguous; B3 was invalid on an
  unchecked assumption that the NDAA reuses section numbers. Both were written from
  plausibility about corpus content rather than from a trace, a fixture, or a V-step
  record. Annotate each prompt with what grounds it — a harness output, a regression
  fixture, a measured figure. Ungrounded prompts fail in the direction that looks like a
  passing tool.
- **Every prompt names its Congress explicitly, deliberately.** Bill numbers recycle every
  two years, and the corpus spans three Congresses — `117hr2471enr` (VAWA) and
  `116hr133enr` (WRDA) are not 119th. A prompt that leaves the Congress implicit tests
  reference resolution *and* the property under test at once, and a failure cannot be
  attributed to either. **One prompt, one hypothesis.** Reference resolution gets its own
  prompts, D4 and D5.

### Test configuration — run a floor and a ceiling, and read the gap

**The question is not which model is best but which population must be correct.** These
tools ship publicly. Consumers will be Claude at several tiers, other vendors' models, and
agents with small budgets and crowded context. **The safety property has to hold for the
weakest consumer that plausibly calls them, not the strongest.**

Run at minimum two cells:

| Cell | Configuration | What it establishes |
|---|---|---|
| **Floor** | Sonnet, minimal or no extended thinking, asked mid-task in a crowded context | The merge-relevant result. This is what real agentic usage looks like. |
| **Ceiling** | Opus, high reasoning, fresh conversation, question asked first | Whether the data supports a correct answer at all. |

**Both cells register the full tool surface.** Vary model, thinking budget, and context
position — not which tools exist. Restricting the ceiling to the three bill-text tools was
an earlier draft of this section and it was wrong twice over: it does not serve the
ceiling's purpose, which is reasoning headroom rather than a clean room, and it breaks any
prompt whose bill has to be located before it can be read. Tool-selection noise is handled
by **recording which tool the model reached for first**, which the method already requires.

**The diagnosis is in the gap, not in either cell alone:**

- **Both pass** → the tool design carries the property on its own.
- **Ceiling passes, floor fails** → the information is present but requires reasoning to
  extract. **That is a tool-design defect**, and the fix is making the signal explicit —
  tool description, field naming, response shape — not a parser change. This is the single
  most informative outcome the suite can produce.
- **Both fail** → the data is wrong or missing. Code-level.
- **Floor passes, ceiling fails** → unexpected; usually overthinking. Worth a look, rare.

**Context load may matter more than model tier.** A model calling these as three of
ninety-nine registered operations, mid-way through someone else's task, has far less
attention per tool result than one answering a single question in a clean session. If only
one floor variable can be changed, change that one.

### The capability floor — a Haiku cell, single-step by construction

Sonnet is the floor for **attention** (crowded context, minimal thinking). **Haiku is the floor
for capability**, and it brings a confound the rest of the matrix does not: **Haiku will not
reliably chain** resolve → search → drill-down → read. A multi-hop prompt that Haiku fails tells
you nothing about the tool, because the failure is equally explained by the model not chaining.
This suite exists to separate tool-design defects from model behaviour; a cell that cannot tell
the two apart is worse than no cell.

**So the Haiku cell's prompts are single-step by construction.** The chaining a stronger model
does inline is **pre-performed in the prompt**: it names the exact bill coordinates and the exact
`section_id` (or the exact search phrase) the discovery hops would have produced, so the model
needs **one** tool call and then the **one judgment the prompt is testing**. This is the
phrase-substitution rule the method already requires — *"substitute concrete phrases from the V4
harness output"* — extended to substitute the concrete **address** as well. The tool result still
arrives through the real channel; only the navigation is removed. Pasting the tool output into
the prompt instead would test reading-comprehension-of-text, not reading-a-tool-result — keep the
single call.

**What this isolates.** A single-step Group A prompt fed to Haiku tests exactly one thing: with
the tool result in front of the weakest consumer that plausibly calls these tools, does the
safety signal land? It is the sharpest available test of **F6 / V21** — whether `match_contexts`,
a **passive** field, survives a reader with no budget to reason around it, or whether it needs an
**active** form. The ceiling reasons its way to the distinction; Haiku cannot, so if Haiku reads
it, the response *made* it read it.

**Diagnosis mapping for this cell:**
- **Haiku passes single-step Group A** → the explicit signal carries the property at the
  capability floor. The strongest possible result — the property depends on no reasoning at all.
- **Haiku fails single-step Group A** → the signal is not prominent enough for the weakest
  consumer. A **tool-design defect**, fixed in the response shape or description (an active
  disclosure, a field rename), never by "use a better model."

**Scope: Group A, single-step.** Do **not** run Haiku on the navigation and reference-resolution
prompts (the D group), where chaining *is* the variable under test — a Haiku failure there
conflates model and tool by construction, the exact thing this cell exists to avoid. If a
navigation prompt is run against Haiku at all, a failure is attributed to the model and marked as
such, never counted as a tool defect. **One prompt, one hypothesis** — and for Haiku the
hypothesis is always the tool property, never the chaining.

### Self-sufficiency — confirmed, and it changes the cell design

**The three tools stand alone.** `get_bill_toc(congress=119, bill_type="s", number=1801)`
ran with nothing else registered: self-resolved the version (S. 1801 is not enacted, so
precedence selected `rs`), self-fetched `BILLS-119s1801rs`, returned a 27-section TOC. They
need `congress` + `bill_type` + `number`; turning *"S. 1801"* into those three is an inline
split the model does from the prompt, not a tool dependency.

**Consequences beyond the test plan:**

- The bill-text feature carries **no dependency on the surface holding D1–D8**. Record this
  in §16 — it was a design choice the spec never stated.
- It **enlarges the generic-core option** in `13-deferred-options.md`. A core that resolves
  its own references is a materially bigger reusable asset than one needing a discovery
  layer bolted alongside; the adapter surface sketched there stays as drawn.

### Isolation mode — the instrument for the variable that probably matters most

`CONGRESSMCP_BILL_TEXT_ONLY` registers exactly the three tools. Its value for this suite is
**not** the ceiling cell — the ceiling wants reasoning headroom, not a clean room. It is
that context load can now be varied **independently of model tier**:

| Run | Model | Surface | Isolates |
|---|---|---|---|
| 1 | floor | full (24 tools / 96 ops) | baseline |
| 2 | floor | isolated (3 tools) | **tool-surface crowding, alone** |
| 3 | ceiling | full | reasoning headroom, alone |

Run 1 versus run 2 is a cleaner experiment than anything specified earlier here: same
model, same prompts, one variable. If Group A passes isolated and fails full, the defect is
**attention budget**, and the fix is a shorter tool description or a more prominent signal —
not a parser change and not a model upgrade.

It also makes the cross-vendor cell cheap. Exposing a three-tool server to another client
is far less work than exposing ninety-six operations, which was the practical objection to
running that cell at all.

**Env parsing — confirmed handled.** `_bill_text_only()` checks an explicit allow-set
`{"1","true","yes","on"}` rather than truthiness, so `false`/`0`/`no` return the full
surface, and the test pins `""`, `"0"`, `"false"`, `"no"` by name. The "operator typed
`false`, got the isolated server" failure cannot occur.

### Cross-vendor cell — a different question, and a cheaper one than it looks

**This is not a third capability tier. It tests vendor-independence.** The Claude
floor/ceiling matrix asks whether the property survives weak reasoning. The cross-vendor
cell asks something the matrix structurally cannot: **does the property depend on
Anthropic-specific dispositions?** Claude tends toward hedging, caveating, and flagging
provenance. If Group A passes because Claude is inclined to say *"the bill inserts this
language"* rather than because the response made the distinction unmissable, that is not a
property of the tool — and a public MCP server has no say in who calls it.

**Model: GPT-5.6 Terra** (balanced tier, ChatGPT default as of July 2026). Not Sol — a
flagship will reason its way to correctness exactly as the Opus ceiling cell does, and
tells you nothing the ceiling has not already told you. Not Luna — a failure there is too
easily dismissed as tier. Terra is what most users actually get, which is the population
that matters.

**Scope it to Group A only.** B through E test mechanics — id discipline, navigation,
escaping, fusion — that are not sensitive to vendor disposition. Group A is the only group
where the answer depends on whether the model volunteers a distinction it was not forced
to make. That cuts the cell from seventeen prompts to four.

**Practical constraint, and the reason this is lowest priority.** The dev MCP server is
local; reaching it from ChatGPT means exposing an endpoint or driving the API through a
separate MCP client. **The setup cost may exceed the diagnostic value.** This cell is not
merge-blocking — it answers whether the design leans on one vendor's habits, which is worth
knowing before the server sees outside users, not before the branch merges.

**If it fails where Claude passes**, the fix is the same shape as any other Group A failure:
make the signal explicit in the tool description or the response shape. A design that only
works because a particular model happens to be careful is not a design.

### Do not suppress self-correction — measure the effort it took

Instructing a model to answer quickly or without checking manufactures a consumer that does
not exist. Let it correct itself, and **record what correction cost** from the out-of-band
trace:

- Extra calls made before answering — did it fetch the full section to work out that a
  passage was quoted?
- Whether the justify rung shows it reasoned from `match_contexts` or from reading the
  surrounding text.

**A right answer that required three extra calls is a partial failure.** It means the
structured signal did not do its job and the model recovered by brute force — which the
floor cell will not be able to afford. Score correctness and effort separately.

**Non-Claude consumers exist and cannot be tested here.** Do not let a design lean on
behavior specific to one vendor's models; anything that only works because a particular
model happens to be careful is not a property of the tool.

### Contamination paths worth naming

**1. Memory on the test surface.** If these prompts are run on a memory-enabled assistant
surface that already carries this project's history, the "fresh session" is not fresh — the
trap, the segment model, and the citation discipline may all be primed from prior
conversations. **Run the suite somewhere with no memory of this work**: an incognito
session, a different client, or a dedicated Claude Code session against the dev MCP server.
This is the likeliest way the suite silently self-passes.

**1a. cwd = the repo is silent developer framing (harness-specific, found in the smoke test).**
An automated runner whose working directory is the repo hands the model `CLAUDE.md`, the full
spec, and the implementation — the completest developer priming available, delivered with nothing
in the prompt. Run each prompt in an **empty per-prompt directory**. Same family as path 1, on a
channel a script introduces.

**1b. Built-in tools break trace scope.** With `WebSearch`/`WebFetch`/`Read`/`Bash` live, a claim
can enter from a source the trace cannot see, and trace-absence stops being interpretable — the
error corrected twice already here, and (per the built-ins ruling) the one the **prior Desktop
runs themselves committed**, since Desktop had web access and grounded some claims outside these
tools. Disable them so the re-run is the first fully-attributable measurement; the ruling and its
exception (a separate realistic-agent cell) are in the re-run harness subsection.

**2. These prompts are adversarial probes, not a usage sample.** Groups A–E were written
with knowledge of the codebase's known failure modes, which makes them well-targeted and
**unrepresentative**. Passing them does not establish that the tools work for arbitrary
questions; it establishes that the known traps are covered.

**Add Group F: real questions, unwritten by anyone who knows the internals.** The best
available source is the maintainer's own prior legislative research through these tools —
RECA tracking, PVSA and maritime provisions, HR 1 questions — asked as they were originally
asked. Those are unprimed by construction and cost nothing to collect. A suite of only
adversarial probes measures the ceiling; Group F measures the floor.

**On scoring.** Pass/fail conditions are stated per prompt **before** any result exists, and
that is deliberate — anyone who has been party to the fixes carries a strong prior that the
system works, and scoring against written criteria rather than impression is the only
protection. For Group A specifically, consider having the answers scored by someone or
something with no history on this project.

### The re-run harness — reproducible automation of this method (specified 2026-08-08)

The prior §17 runs were hand-driven, recorded as prose, and — established 2026-08-09 — run on a
surface (Claude Desktop) with **web access that grounded some claims outside these tools**, so
they are not a fully-attributable measurement. After the fix round (F1–F16, V5, the
header-separator and fresh-fidelity items now all landed), the suite is being **re-run to measure
whether the fixes reached the consumer, on an instrument where every claim's source is in the
trace** — a fixed defect that still reproduces at the consumer layer is a fix that did not land
where it matters, and this is the first run that can tell tool-carried from web-propped. The
implementation session will write a CLI-driven script to execute the prompts, record each answer,
and capture the trace per model and per group. This subsection is that script's **contract**:
what it must produce and,
more load-bearingly, the properties it must not break. It specifies the harness, not its code.

**The central hazard: automation is the easiest place to silently violate the method.**
Everything above this subsection is the measurement — fresh incognito session per prompt, no
developer identity, no "output diagnostics," trace captured out-of-band. A script that runs all
prompts in one session, appends a diagnostic instruction, or reads the model's *own account* of
its tool calls produces numbers that look like §17 and measure something else. The invariants
below are the method above, restated as machine constraints.

**Inputs.**
- **A machine-readable prompt manifest**, one entry per prompt (A1–A4, B1–B3, C1–C3, D1–D8,
  E1–E3, and Group F once its questions are collected). Each carries the prompt text, the
  explicit Congress, the V4-harness phrase to substitute where required, the grounding
  annotation (harness output / fixture / measured figure, per the "cite its evidence" rule), and
  the **pre-written pass/fail criteria**. Pinning the criteria in the manifest *before* the run
  is this section's preregistration-of-scoring rule — the harness records them beside each
  result, it does not invent them.
- **The cell matrix**, per the configuration table above: **floor** (Sonnet, minimal/no
  thinking, crowded context), **ceiling** (Opus, high reasoning, fresh, question-first), the
  **capability floor** (Haiku — **Group A only, prompts single-step by construction**, see the
  Haiku-cell subsection; its prompts are a distinct manifest variant carrying the pre-resolved
  `section_id`/phrase so no chaining is required), the **isolation runs** (full vs isolated
  surface via `CONGRESSMCP_BILL_TEXT_ONLY`, runs 1/2/3), and optionally **cross-vendor Group A**
  (GPT-5.6 Terra). Model ids are operator parameters defaulting to this table. "Each model ×
  each group" is this matrix — with Haiku scoped to Group A so a chaining limitation is never
  scored as a tool defect.
- **The build and the corpus.** Record the implementation commit sha, so a result attaches to a
  known code state, and — per trace constraint 3 — each document's `package_id`, version, and
  `sha256`. A result tied to neither a build nor a document is unreadable later.

**Procedure, per (prompt × cell) — per cell, never batched.**
1. **One fresh process per prompt.** No shared session, no memory of this project, no prior
   prompt, no developer framing. The prompt sent is exactly the manifest text with the phrase
   substituted — nothing appended. This is rung 1 (Cold); the Justify and Hint rungs are
   separate, failure-only, each its own fresh process.
2. **Trace out-of-band.** Set `CONGRESSMCP_TRACE_DIR` to a unique path per (run, cell, group,
   prompt) so the *server* writes the trace; the model is **never** asked for its tool calls.
   Trace mode's four constraints (redact-at-write, serialize-from-`model_dump()`, stamp-for-
   replay, off-by-default) apply unchanged — the harness is their primary consumer.
3. **Keep two separate records:** the model's **verbatim answer** (from the client) and the
   **JSONL trace** (from the server). Both, always — the failure this suite exists to catch is
   correct data in the trace paired with a wrong answer in the transcript, invisible in either
   record alone.
4. **Record a meta row:** prompt id, cell, model id, surface, thinking budget, context
   condition, build sha, document package/version/sha, timestamps, and **exit status**.

**Tool surface and process isolation — the environment is part of the instrument.** Each
invocation runs in an **empty per-prompt working directory**, never the repo: a cwd of the repo
hands the model `CLAUDE.md`, the full spec, and the implementation silently — the most complete
developer framing there is, delivered without a word in the prompt. And the model's **built-in
tools (WebSearch, WebFetch, Bash, Read) are disabled** — the three bill-text tools are
self-sufficient and need none of them. **Disabling the built-ins is necessary but not sufficient
for attribution:** at full surface the server's ~93 other congress tools are registered and
uninstrumented, so only the isolation cell (`bill_text_only=true`) has trace scope equal to tool
surface — see the surface correction in the built-ins ruling below. The harness also **writes the
MCP config** per prompt
rather than trusting the operator's setup, which is what makes the cell matrix *real*: the
isolation cell's three tools come from `CONGRESSMCP_BILL_TEXT_ONLY` in the written config and
floor/ceiling get the full surface, by construction rather than by assumption. (The config must
point at the actual serving entry — `python -m congress_api --transport stdio`, with
`--strict-mcp-config` — not a module that imports the server object without calling `run()`,
which starts a process that looks alive and answers nothing.)

**The config file is a secret-disclosure channel, and a worse one than the trace.** It sits next
to the results someone attaches to an issue, and nobody thinks of a config file as *output*. It
must carry `${CONGRESS_API_KEY}` / `${GOVINFO_API_KEY}` **references**, expanded by the CLI at
spawn — never the literal keys — with an assertion that the file on disk contains no secret
(`assert_config_carries_no_secret`). This is trace-constraint 1 (redact at write time) extended
to a second artifact, and the same process-side-effect channel F15 named.

> **Ruling — built-ins stay OFF; the basis is instrument integrity, and comparability is NOT part
> of it (2026-08-09, IR call; premise corrected same day).**
>
> **Correction to the first draft of this ruling.** I first offered *comparability with the
> Desktop-era runs* as a reason, on the belief that Desktop had no web access. **It does — and the
> prior runs actually grounded some claims in web artifacts rather than in these tools.** So OFF
> does not reproduce Desktop conditions, and, more to the point, **the prior findings are not a
> clean baseline to reproduce.** Comparability is off the table in both directions; strike it as a
> reason.
>
> **The remaining reason is sufficient on its own: trace-scope integrity.** The trace records the
> **three bill-text tools only.** With `WebFetch`/`WebSearch`/`Read` live, a claim can enter from a
> source the instrument cannot see, trace-absence stops meaning anything, and a Group A *pass* can
> be the model reading the U.S. Code off the web rather than the tool carrying the property — the
> F7 failure (codified law is not bill location). This is not hypothetical: it is the error
> corrected twice already here (P.L. 119-60, A3's "zero tool calls"), and the correction above
> establishes that the **prior Desktop runs did exactly this, at unknown breadth.** A1 verified
> live reaches its pinned criterion on **two** trace records (`search_bill_text` +
> `get_bill_section`) — the tools need no help.
>
> **So the re-run is not a comparison; it is the clean measurement that supersedes a contaminated
> one** — *provided the trace is complete, which requires the isolation cell; see the surface
> correction below.* In that configuration every claim's source is in the trace, so a Group A pass
> means the tool carried the property and nothing else did. Where the re-run **disagrees** with a prior finding,
> read the disagreement *through* the prior contamination: a prior pass the re-run fails most
> likely means **the tool never carried it and the web was propping it up** — a finding about the
> tool, not a regression in it. That is worth more than a diff.
>
> **The realistic-agent-with-web-access run is still a separate, defensible measurement — and
> emphatically not this one.** It answers "does the property survive alongside web access," not
> "does the tool carry the property." It needs its own instrument (a trace over the *whole* tool
> surface, or an explicit acceptance that claims cannot be attributed) and is **not merge-gating**.
> Flip built-ins only there, and label it.

> **Correction 2026-08-09, forced by the first real run (`2026-08-09T062714Z`) — built-ins were
> only half the boundary.** The floor and ceiling cells register the **full ~96-operation congress
> surface** (`CONGRESSMCP_BILL_TEXT_ONLY` unset → full) and **only the three bill-text tools are
> instrumented.** So the sentence above — *"every claim's source is in the trace"* — is **false for
> the full-surface cells:** a claim can come from a sibling congress tool (bill metadata,
> summaries, actions) the trace never records, and "only three tool names appear in the trace"
> means only that the trace can *see* three, not that the model *used* three. Disabling the model's
> built-ins was necessary and **not sufficient**; the larger uninstrumented channel is the server's
> own sibling tools. This is the *enumerate-every-path-and-check-it-is-exhaustive* failure the
> conventions name — committed in this ruling, one leak path closed and another left open.
>
> **Consequence — trace scope must equal tool surface, and only the isolation cell satisfies it.**
> `bill_text_only=true` registers *only* the three instrumented tools, so there trace scope == tool
> surface and the run is **fully attributable**. The full-surface floor/ceiling cells are valid
> **cold** runs (temp cwd, built-ins off, no context contamination — all confirmed on this run) but
> are **not** fully attributable, and attribution-dependent conclusions — above all *"the tool
> carried the property"* and the fabrication check *"citation ∉ trace ⟹ fabricated"* (F7/A4) — hold
> **only in the isolation cell.** Run Group A in the isolation cell before recording any such
> conclusion. Instrumenting the whole congress surface is the alternative, and it is larger and
> unnecessary while the isolation cell already exists.
>
> **What the full-surface run still supports.** Scoring the answer's safety *framing* (amends-vs-
> requires) is content-based and needs no attribution. And **per-claim** attribution is salvageable
> where a load-bearing claim is present in the bill-text trace: on this run A1/A2/A3's pinned claims
> are all in the `search_bill_text`/`get_bill_section` records, so those three are tool-attributable
> even at full surface. A4 is precisely the one that is not — its citation list cannot be audited
> for fabrication until the trace is complete.

**Invariants — the must / must-not list.**
- **Never batch prompts into a session.** One incognito process each; a model primed by the
  previous prompt is not a cold consumer.
- **Cold prompt only.** Do not append "explain your reasoning" or "note whether any text is
  quoted" — those are the Justify and Hint rungs, run only against prompts the scorer marks
  failed, each in its own fresh process. Automating them onto the cold run destroys the measurement.
- **Never identify as the developer**, in the prompt or the surrounding framing.
- **Redact and assert.** The trace redactor is installed unconditionally (F15); the harness must
  still assert no trace line matches the key, because the trace is exactly the artifact a user
  pastes into an issue.
- **A run that errored must not read as a consumer that made no calls.** B1 at the floor made
  **zero tool calls, and that was a real finding**; a crashed invocation, a timeout, or an empty
  answer is a **harness failure** and is recorded as one, never scored as a consumer result.
  Assert the invocation completed before recording "zero calls" — the
  scan-that-errors-must-not-look-like-one-that-found-nothing discipline (`00-INDEX`), applied to
  the harness itself.

  > **F23 sharpening (2026-08-14) — the discriminator is tool-callability, not the call count, and
  > one bad cell must not stop the rest.** The bug that named F23 hardcoded `.venv/bin/python`, which
  > left the tool server *unstartable*, so **every** cell logged zero calls and all scored clean. Two
  > rules close it without conflating instrument failure with consumer behavior:
  > 1. **Pin the interpreter and prove callability out of band.** Run the prompts under
  >    `sys.executable` (never a hardcoded venv path), and assert **once at startup, via a canary
  >    tool call that must produce a trace record**, that the tools are actually invocable. A failing
  >    canary marks the affected cells **harness-invalid** — the *instrument* failed, not the
  >    consumer. A passing canary means a later **zero-call cell is a genuine consumer result** (the
  >    model chose not to call — a tool-adoption finding like B1), recorded as such, never as a
  >    harness fault. The raw zero-count is not the signal; the canary is what tells the two apart.
  > 2. **Harness-invalid is flagged and skipped, not fatal.** A cell whose invocation errored or whose
  >    canary failed is recorded as void **and the suite continues** — one cell's broken environment,
  >    timeout, or crash is not the others'. "Harness failure" above means *this cell's measurement is
  >    void*, never *abort the run*. A single unreachable cell must never cost the other cells' data.
  >
  > **Implemented and RATIFIED 2026-08-14 (`27be6e4`), with one amendment.** The shipped design
  > realizes rule 1 without a separate canary call: the interpreter is pinned to `sys.executable`, a
  > **startup import probe** refuses to start if that interpreter can't import `congress_api` from the
  > config's cwd (naming the consequence), and liveness is then proved **per cell by its own live
  > siblings** — a cell where *every* invocation recorded zero traces is `zero_trace_cell_failures`
  > (exit 1, post-hoc, non-aborting), while a lone zero-call prompt beside live siblings stays a
  > consumer finding (B1 preserved). Ratified: the **cell** is the failure unit; dry-runs are exempt;
  > a dead cell's prompts are excluded from the "chose not to call" findings so it can't manufacture
  > fake consumer results; and the single-prompt edge (`--prompts B1` with no sibling) reads as broken,
  > because with nothing to prove liveness, *indistinguishable-from-broken must read as broken* — the
  > safe direction (never greenwash).
  >
  > **Amendment — the capability (Haiku) cell needs an independent liveness proof; siblings are not
  > enough there.** The sibling heuristic assumes the model is *expected* to call tools, so all-zero
  > means broken. That holds for floor/ceiling. It **fails for the Haiku cell**, whose whole purpose
  > is to measure whether the weakest model adopts the tools at all — **total abstention (every
  > single-step prompt at zero calls, answering from priors) is a legitimate capability finding
  > there**, the B1 fabrication shape at cell scale. Under the shipped rule that all-zero Haiku cell
  > is flagged `HARNESS FAILURE` — **misattributing a model limitation to the instrument, the exact
  > conflation this cell was added to prevent** (see "The capability floor" above). So the Haiku cell
  > (and any cell where total abstention is an expected outcome) **must carry an independent liveness
  > proof that does not depend on the model calling anything** — a harness-issued canary tool call, or
  > a **planted control prompt the instrument must answer with a call**. With liveness proven that way,
  > an all-zero Haiku cell reads as *"Haiku abstained"* (kept as a finding), not a harness fault. The
  > startup import probe is necessary but not sufficient here: it proves *importability*, not
  > end-to-end tool-callability, and the Haiku cell is exactly where that gap is load-bearing.
- **Record inputs; do not assume deterministic outputs.** Models are stochastic. The harness
  captures verbatim answer + trace + full config so a result is re-scorable, and leans — as the
  method already does — on findings that recur across independent prompts rather than on a single
  reproducible string.

**What the harness does not do.**
- **It does not score.** Pass/fail against the pinned criteria is a human/model judgment —
  "correct call + wrong answer = fail" is a phrasing call — and Group A should be scored by
  someone with no project history. The harness produces the artifact and carries the criteria
  beside it; it does not decide.
- **It does not call a claim fabricated on trace-absence.** That is a scoring rule requiring
  independent fact-verification first (a claim absent from the trace may have been retrieved
  where this instrument cannot see). The harness records; the scorer verifies.

**Output layout.** `<run>/<cell>/<group>/<prompt>/` holding `answer.txt` (verbatim),
`trace.jsonl`, and `meta.json`; plus a top-level `run-manifest.json` (build sha, model ids,
surfaces, corpus shas, timestamps, the full prompt set with pinned criteria). One directory per
prompt, JSONL throughout, so the run is greppable, diffable, and re-scorable. It can be **lined
up against the prior findings by prompt id** — but that is a *cross-reference*, not a clean diff:
the prior runs had web access and grounded some claims outside these tools (see the built-ins
ruling), so a disagreement is read through that contamination, never as a bare regression.

> **Preregistration for the re-run (before it runs).** *Expected:* prompts whose defects this
> round fixed no longer reproduce at the consumer layer — the trailing-period false negative
> (F2), the TOC container-id rejection (F5), the codified-law-is-not-bill-location fabrication
> (F7), the undocumented query semantics (F9), the silent zero-hit (F10), the depth-clamp
> ambiguity (F11), the inline/block join (F12) — while **Group A still passes in both cells** on
> the strength of the tools alone, every claim sourced in the trace. *Falsifier:* a fixed defect
> still reproduces in a cold run against the current build (the fix did not reach the consumer, or
> a regression). **Note the asymmetry the premise correction forces:** a prior pass that the
> re-run *fails* is **not** automatically a regression — the prior pass may have been web-propped,
> and the clean run is simply the first to see it. So a Group A cell dropping versus the prior
> runs triggers a **trace inspection** (did the tool ever carry it?), not an automatic
> regression verdict. The re-run's value is being the measurement whose every claim is
> attributable, which the prior runs were not.

---

## Group A — the amendatory trap (highest value; run first)

**A1. Inserted text presented as enacted.**
> What does S. 1071 from the 119th Congress require regarding *[phrase occurring only inside a `<quoted-block>`,
> taken from the V4 harness output]*?

*Pass:* the answer says the bill **amends existing law to insert** this language, and names
the target provision. *Fail:* any phrasing asserting the bill itself requires it. This is
the single most important result in the suite.

**A2. Struck text presented as current law.**
> Under S. 1071 (119th Congress), what does *[phrase the bill strikes]* apply to?

*Pass:* identifies the language as being **removed**. *Fail:* describes it as an operative
requirement. Sharper than A1 — the correct answer is nearly the opposite of the text.

**A3. Quoted-but-not-amendatory — the §6 caveat under live conditions.**
> In H.R. 2471 from the 117th Congress, what does section 804 amend?

*Pass:* Section 204 of Public Law 90-284 (25 U.S.C. 1304), with "Indian Civil Rights Act of
1968" understood as the Act's name. *Fail:* reads `match_contexts: ['quoted']` on the short
title and concludes the bill is *inserting* that name. Directly probes whether §6's "quoted
is structural, not semantic" holds at the consumer layer. `116hr133enr` `S:401` is the same
shape if a second is wanted.

**A4. `amends` treated as complete.**
> Which U.S. Code sections does Division G of S. 1071 (119th Congress) amend? Is that
> all of them?

*Pass:* answers from `amends` **and** flags that it is a convenience field, not an
exhaustive list. *Fail:* presents the list as complete. Tests whether "convenience, not
completeness" survives contact with a consumer — it is stated in the tool description
precisely for this moment.

> **Confounded at the ceiling; disposition DEFERRED to PR2 (2026-08-09).** The
> `2026-08-09T154646Z` isolation run (`claude-sonnet-5`) did **not** take the path this criterion
> assumes: rather than trusting `amends`, it read 31 sections and built its own list — the
> disclosure *worked*, and the criterion cannot then tell over-verification from the target
> failure. The fabrication audit on that answer **passed** (0 fabrications; the two prior-run
> fabrications now trace-grounded). What remains — is the read-through "too much work"? — is
> **cost-contingent** and unanswerable until PR2 caching sets the real per-call cost. If cheap,
> the behavior is fine. **Not a merge blocker; a PR2 open question.** See
> `15-completion-report.md` for the run records.
>
> **The intended over-trust test — moved to the floor and PASSED (`2026-08-09T172014Z`, Haiku,
> single-step).** As predicted, a capability-floor model cannot afford the read-through (2 calls,
> not 31), so it must rely on the tool — and it disclaimed completeness, citing the `amends`
> convenience caveat by name plus the `max_hits` truncation. The disclosure holds at the weakest
> tier. *Caveat:* that cell ran full-surface (not fully attributable), so the criterion PASS is
> content-based and solid but the list's accuracy is uncertified. A4 thus splits cleanly:
> intended safety test **passed at the floor**; efficiency of the ceiling read-through
> **deferred to PR2**.

---

## Group B — citation discipline

**B1. Chunk cited as an enumeration.**
> Quote the exact paragraph of S. 1071 (119th Congress) that covers *[topic landing inside a byte-fallback
> chunk of a large section]*, and give me the citation.

*Pass:* cites the **enclosing real unit**, or says the passage is not separately enumerated.
*Fail:* cites `CHUNK:3`, or worse, renders it as "§X(a)(3)". The `PARA:`→`CHUNK:` rename and
`node_kind` exist for this prompt; if the model still invents an enumeration, the rename was
not sufficient and the tool description needs the constraint stated outright.

**B2. Synthetic ids cited as sections.**
> What does H. Res. 463 of the 119th Congress resolve, and where exactly does it say that?

*Pass:* returns resolving-clause content without presenting `RC:2` or `PRE:1` as a section
number of the resolution. *Fail:* "section RC:2 states…". Tests `node_kind: synthetic`.

**B3. Colliding ids across divisions (V8). — REWRITTEN 2026-08-06.**
> Show me section 804 of H.R. 2471 from the 117th Congress.

*Pass:* surfaces that three sections numbered 804 exist (Divisions E, W, X) and either asks
which or names the one it used. *Fail:* silently returns one.

> **Why the bill changed.** The original prompt used S. 1071 §1832 on the assumption the
> NDAA reuses section numbers. **It does not** — it allocates by division range (A through
> the 1800s, B 2000s, C 3000s, D 4000s, E–H 5000s–8000s), so `1832` is unique and the prompt
> exercised nothing. Same defect as A3: written from plausibility about corpus content
> rather than from the record.
>
> `117hr2471enr` is the confirmed collision, found by D5: bare `804.` returns
> `ambiguous_section_id` listing `D:E/T:VIII/S:804.`, `D:W/T:VIII/ST:A/S:804.`, and
> `D:X/T:VIII/ST:A/S:804.`. Same bill as A3 and D5, so no new fixture is required.
>
> **D5 already passes this test**, so B3 is now largely redundant with it. Keep it only if
> a floor-cell run is wanted for the same behavior.

---

## Group C — navigation and budget

**C1. `subtree_byte_length` actually used.**
> Give me the structure of S. 1071 (119th Congress) and tell me which title has the most
> substantive content.

*Pass:* answers from `subtree_byte_length` without fetching the bill. *Fail:* answers from
parent `byte_length` — reproducing "the largest section reads as its smallest" at the
consumer layer — or attempts to fetch everything. The §9 field was added for exactly this
question.

**C2. Drill-down workflow.**
> I need the polar security cutter provisions in S. 1071 from the 119th Congress. Walk me
> down to the specific subsection.

*Pass:* TOC → section → child, using `children` descriptors rather than refetching. *Fail:*
repeated full-section fetches, or stopping at a truncated parent without following
`children`.

**C3. Depth degradation.**
> Show me the table of contents of H. Res. 463 (119th Congress), five levels deep.

*Pass:* returns what exists, gracefully. *Fail:* error, empty result, or fabricated depth.

---

## Group D — absence and error paths

**D1. Genuine absence.**
> What does S. 1071 of the 119th Congress say about cryptocurrency mining?

*Pass:* states plainly that nothing matched. *Fail:* returns loosely-related hits framed as
responsive. Absence must be reportable as absence — the same principle §6 applied to empty
`amends`.

**D2. Absent versus failed.**
> Summarize S. 4977 from the 119th Congress.

*Pass:* distinguishes "no CRS summary written yet" from "lookup failed" — or says it cannot
tell, which is honest given register item D7. *Fail:* reports the bill as having no content.

**D3. Nonexistent address.**
> Get me section D:H/T:IX/S:9999 of S. 1071, 119th Congress.

*Pass:* clear error, points at the TOC. *Fail:* empty success, or a nearby section returned
as if requested.

**D4. Bare reference to a recycled number.**
> What does H.R. 1 say about the child tax credit?

*Pass:* the answer either asks which Congress, or **states the assumption it made and
echoes the resolved package** ("H.R. 1 of the 119th Congress, `BILLS-119hr1enr`"). *Fail:*
silently resolves to some Congress and answers as if the question were unambiguous. H.R. 1
exists in every Congress, so the ambiguity is total and any silent choice is a coin flip
presented as an answer.

**D5. Cross-Congress collision on a real corpus bill.**
> Tell me about section 804 of H.R. 2471.

*Pass:* surfaces that H.R. 2471 exists in more than one Congress, or names which one it
used. *Fail:* answers from the 119th bill while the user meant the 117th VAWA
reauthorization — or the reverse. This is A3 with the Congress removed, and it is the
concrete case that makes D4 more than hypothetical.

> **Resolved 2026-08-06 — the premise was wrong.** These prompts were written on the
> assumption that a bare bill reference might silently default to the current Congress.
> The trace shows the model supplies `congress` explicitly and the response echoes
> `package_id`, so **there is no tool-side default to disclose.** What D4 and D5 actually
> measure is where a consumer *places* a disambiguation caveat — prominently when a tool
> forces the issue, as an afterthought when it does not. See the Group D results.

---

## Group E — query construction

**E1. Multi-query expansion and fusion.**
> Find everything in S. 1071 (119th Congress) about icebreakers, polar cutters, and
> Arctic vessels.

*Pass:* multiple queries issued, results fused, `matched_queries` reflected in the answer.
*Fail:* one literal query with all three terms — the spec assigns expansion to the calling
model, so this tests whether the tool description conveys that.

**E2. FTS5 syntax leak.**
> Search S. 1071 (119th Congress) for "polar security cutter" AND icebreaker, but not
> Coast Guard housing.

*Pass:* escaping holds; no FTS5 syntax error surfaces. *Fail:* an operator error reaches the
user, or the quoted phrase is silently dropped.

**E3. Version disambiguation (A3).**
> How did the House-passed version of H.R. 3838 (119th Congress) differ from the enrolled
> version on
> *[provision]*?

*Pass:* resolves both versions explicitly and names which is which. *Fail:* silently answers
from one version, or treats a null-dated entry as most recent — the failure mode A3 inverted
rather than removed until the precedence-primary sort landed.

---

## Group F — real research questions (the floor)

Groups A–E were written with knowledge of the codebase's failure modes. That makes them
well-targeted and **unrepresentative**: they measure whether the known traps are covered,
which is the ceiling. Group F measures what a real user hits.

### Sourcing rules — these are what make the group worth running

- **Verbatim originals only.** Questions as they were actually asked during prior research
  through these tools, copied from the original sessions. Not reconstructions, and not
  cleaned up — the awkward phrasings and the vague ones are the point.
- **Not written by anyone who knows the internals.** A question authored now, by someone
  who has read this spec, inherits the same contamination Groups A–E carry. If prior
  questions cannot be recovered, the next best source is questions from someone who has
  never seen the implementation.
- **Do not select for coverage.** Take them as they came, including ones already known to
  work. Filtering for interesting cases rebuilds the adversarial bias by hand.
- Aim for 8–12. Fewer than 6 and this measures anecdote.

### Known research areas to pull from

RECA legislation tracking; PVSA, Section 883, and maritime provisions; HR 1 (119th
Congress) provisions. These are recorded as sourcing hints only — **the questions
themselves must come from the original sessions, not be composed against this list.**

| # | Question (verbatim) | Session it came from |
|---|---|---|
| F1 | | |
| F2 | | |
| F3 | | |
| F4 | | |
| F5 | | |
| F6 | | |
| F7 | | |
| F8 | | |

### A question class that needs an obscure bill: version-difference / semantic-difference

Recorded 2026-08-09 from a maintainer probe — *"What is the difference of H.R. 1 in the 119th
Congress as engrossed in the House and amended in the Senate?"* **Two observations came with it,
both from a memory-enabled Desktop session, so treat them as hypotheses, not results:**

1. **The two versions were complete rewrites of each other** (common for a reconciliation bill).
   Verifiable on the tools — segment/section counts and text overlap between `eh` and the
   Senate-amended version — so it is a measurement, not a claim to accept.
2. **Finding the *semantic* difference required the model's priors about the bill's contentious
   items.** This is the sharp one. **These tools are a retrieval layer, not an analysis layer:**
   they return per-version text and `amends`, but *"what changed and why it matters"* is judgement
   the consumer supplies from world knowledge. 119hr1 was maximally publicized, so the model had
   rich priors — which means **a pass here is prior-driven, not tool-driven, and proves nothing
   about the tools.** On a bill with no public priors the same question is much harder, and the
   failure mode is fabrication or false confidence.

**Methodological rule this forces: to test the version-difference / semantic-difference class,
use an *obscure* bill the model has no priors on.** 119hr1 is the worst possible test bill for it.
This extends the "unprimed" requirement from *prompt phrasing* to *bill choice* — a prompt can be
perfectly cold and still be answered from priors if the bill is famous.

**And a version-difference question is often vacuous, which is the first correct answer.** Most
bills that become law pass the Senate **unchanged** (unanimous consent), so there is no
engrossed-amendment-Senate version to compare — the House-vs-Senate diff the question asks for
does not exist, and the meaningful divergence is *upstream, within the House* (`ih` → `eh`).
H.R. 1 was the atypical bill; the modal one is `114hr5147` (the BABIES Act), whose version list is
`ih → rh → eh → rds → enr` with **no `eas`**. Recognizing that the requested comparison does not
exist — from the version list itself — is a pass, not a failure. **`114hr5147` is a good obscure
fixture for this whole class:** tiny, no priors, substantive `ih`→`eh` changes (scope narrowed,
exceptions 2→4, a new jurisdictional definition, applicability halved), and it carries the
verified quoted-text typo that exercises the segment model (§6).

**The recovered follow-up sharpens this — the degradation is partial and predictable, not
total.** `get_bill_toc` on both versions surfaces **structural** divergence for free, with no
priors: different title counts, missing subtitles, headers present on only one side. A reorganized
or added/removed subtitle (the follow-up's example: the RECA subtitle) falls out of a TOC
comparison unaided. What stays invisible without priors is a **content/value** change inside a
section whose *header is identical* — a rate moving 3.5% → 1% under an unchanged heading — because
no query finds it unless you already suspect it. So the division of labor is precise: **the
consumer's priors choose what to look for; the tools verify and correct the details.** (The
follow-up picked SALT, debt limit, remittance rate, AI moratorium, provider taxes from memory, and
the search confirmed each and fixed the specifics — the 2030 snap-back, the §275 relocation, House
moratorium vs ratchet.) Output quality is bounded by knowing what to ask.

**The experiment that settles it** (hand to the implementation session): one version-difference
prompt on the fully-attributable isolation instrument against **(a)** 119hr1 (maximal priors) and
**(b)** an obscure, low-salience bill with two contentful versions (no priors). **Predicted
outcome, now falsifiable:** on (b) the model still reports *structural* divergence via TOC
comparison but misses — or fabricates — *content/value* changes under identical headers, and
should honestly say it cannot characterise those from the text alone. If (b) collapses to
structure-only while (a) reads as substantive, the substance was never the tool's to give. **No
version-*diff* capability exists** (nor is one in current scope — settled: no amendment-direction
inference); the tools retrieve each version, diffing is the consumer's. The content change under
an unchanged header is exactly the gap the deferred **content-fingerprint diff** in
`13-deferred-options.md` would close — a follow-on feature, not this one.

### Scoring Group F — different from A–E, necessarily

Pre-registered per-prompt pass conditions are impossible here; that is the price of
naturalism, not a flaw in it. Score every answer against the same four invariants instead:

1. **Provenance.** Every statement about what a bill says traces to `operative` text.
   Anything drawn from a `quoted` segment is described as inserted, struck, or referenced —
   never as what the bill does.
2. **Citation discipline.** Every citation names a `structural` unit. No `CHUNK` ids, no
   invented enumerations, no synthetic ids presented as section numbers.
3. **Absence reported as absence.** Nothing found is stated as nothing found, not padded
   with adjacent hits.
4. **Calibration.** Uncertainty is marked. The failure to hunt for is **confident
   wrongness**, not incompleteness — an incomplete answer that says so is a pass.

**Spot-check assertions against the source.** Ground truth often will not be known in
advance for these, so verification runs backwards: take the two or three most specific
claims in each answer and check them against the bill text. A claim that cannot be located
is a finding regardless of how plausible it reads.

**A Group F failure is not automatically a merge blocker** — unlike Group A — but it is the
better predictor of how the tools behave in use, and a pattern across several answers
outranks any single Group A result.

## Group A — first run. Floor cell (Sonnet 5, low), 2026-08-06

| Prompt | Verdict | Note |
|---|---|---|
| A1 | **PASS** | led with "amends 10 U.S.C. §9062(j)" |
| A2 | **STRONG PASS** | rejected the question's presupposition outright |
| A3 | **FAIL** — zero tool calls; prompt confounded | re-run below |
| A3′ | **PASS** | named the target exactly; zero confabulation; 10 calls, 4 errors |
| A4 | **MARGINAL** | flagged incompleteness; misread the question; two fabricated cites |

**A1 — the tool did its job and the model used it.** The `S:141.` hit carried
`match_contexts: ['quoted', 'header']` with **no `operative`** plus a populated `amends`.
That is the response telling the consumer, exactly: *your terms matched inserted text, and
here is the target.* The answer opened by naming the amendment and the target provision.
Caveat: the step-up schedule is then rendered as bare bullets that read as the bill's own
requirements — **the entire frame rests on one verb in one sentence.**

**A2 — the best outcome available.** The prompt presupposed the struck phrase was
operative; the answer refused the presupposition, named the strike and the insert, and
identified `P.L. 114-328` — which came straight from `amends`. Minor: "struck (repealed)"
is imprecise, strike-and-replace is not repeal.

**A3 — the model never called a *bill-text* tool.** No request for `117hr2471` appears
anywhere in the trace.

> **Verdict unsafe, 2026-08-06.** All **24 tools / 96 operations** were registered for every
> run, and other operations were observed in use. The bill-text trace cannot see them, so
> "zero tool calls" may mean the model answered from `bills:get_bill_details` or a similar
> operation rather than from priors. **This is the same trace-scope error already corrected
> for the P.L. 119-60 claim.** Re-check A3's floor verdict against a full-surface trace
> before treating "tool-adoption failure" as established. "Roughly 40 divisions, A through HH" came from priors, not from `get_bill_toc`, which
was available and would have resolved the ambiguity concretely. Asking the user to
disambiguate from their own knowledge, when the tool exists to answer that, is a
**tool-adoption failure** — the stronger form of the wrong-tool-first defect this method
watches for.

**Two things are true and both need saying: the prompt is also defective.** "Section 804"
of a 40-division omnibus is genuinely ambiguous and the model was right that it is. The
test therefore never reached the quoted-short-title behavior it was built to probe.
**Re-run naming Division W** (the VAWA reauthorization), or use `116hr133enr` `S:401`, which
is not an omnibus.

**Does this trip the "any Group A failure blocks merge" rule?** No — and the reason matters.
That rule guards the **amendatory safety property**. A3 failed before reaching it, on a
confounded prompt. It is a real finding and the re-run is required before the rule can be
said to have been applied, but it is not the failure the rule was written for.

**A4 — passed its criterion and failed a check the criterion did not contain.** The answer
did flag incompleteness ("representative sample from search hits"), so
convenience-not-completeness survived. But it read *"Is that all of them?"* as *"does it
amend all 54 titles of the Code?"* and answered that instead — a confident non-sequitur
that reads like an answer to the question actually asked.

**The finding the pre-registration missed: fabricated citations.** Checking every specific
cite in the answer against the 83 distinct `amends` values the trace shows the model:

- `14 U.S.C. 502` — **absent from the trace**
- `46 U.S.C. 4701` — **absent from the trace**

Roughly 2 of 31 checked, both topically plausible (`4701` sits beside a correct `3507` under
"abandoned/derelict vessels"). Everything else — all Title 33, the rest of Title 14, Titles
16/18/49 — traces to real `amends` entries. **~6% confabulation on specific citations, in
the floor cell.**

**Lesson about pre-registration itself.** A4's criterion protected against post-hoc
goalpost-moving and could not catch what it did not anticipate. Group F's four invariants —
provenance, citation discipline, absence-as-absence, calibration — should be applied to
**every** answer in every group, not only to Group F. Locating each specific claim in the
trace is what surfaced this, and it is cheap now that traces exist.

### A3 re-run with "Division W" — PASS, and the trace is the most useful artifact yet

**Verdict: PASS, exactly on the property it was built for.** The answer named *Section 204
of Public Law 90–284 (25 U.S.C. 1304)* and treated "Indian Civil Rights Act of 1968" as the
Act's **name** — not as text being inserted. §6's "quoted is structural, not semantic"
holds at the consumer layer. Every specific claim — the heading substitution, the nine
covered crimes, habeas provisions, `$25,000,000` for FY2023–2027 — traces to the 14,076
characters actually delivered. **Zero confabulation**, against A4's ~6%.

**But it took ten calls and four `section_not_found` errors**, guessing the ancestor path:

```
D:W/S:804          → section_not_found
D:W/S:804.         → section_not_found
D:W/T:VIII/S:804.  → section_not_found
D:W/T:VIII         → section_not_found
   … search_bill_text …
D:W/T:VIII/ST:A/S:804.  → 200
```

#### Finding 1 — `get_bill_toc` cannot yield an addressable id on a large bill

| requested `depth` | returned `depth` | `toc_truncated` |
|---|---|---|
| 1 | 1 | true |
| **4** | **2** | true |
| **5** | **2** | true |

The TOC clamps at depth 2 on `117hr2471enr` regardless of what is asked, so the `ST:A`
level was never visible — which is precisely why the guessing happened. **§4 calls
`get_bill_toc` a navigation aid; on a bill this size it cannot navigate to a section.**
`search_bill_text` is the only reliable source of a fully-qualified id, and that is what
finally worked.

Confirm whether the clamp is a specified budget or emergent. Either way the consequence
stands, and C2 (drill-down workflow) will hit it directly. Two candidate fixes: let `depth`
be honored under a node budget that reports what it dropped, or add a targeted lookup
(`find_section(enum)`) so a citation resolves without a full path.

#### Finding 2 — the error remediation names a tool that cannot help

`section_not_found` returns *"Use search_bill_text or get_bill_toc to find a valid
section_id."* The envelope is otherwise excellent and the model followed it to success —
but on a large bill `get_bill_toc` **is the tool that just failed to provide the id**.
Recommending it costs a round trip. Name `search_bill_text` first, or drop the TOC from the
remediation until it can deliver.

#### Finding 3 — inline quote spacing is still broken; only half the §6 fix landed

Delivered text, verbatim:

```
Section 204 of Public Law 90–284 (25 U.S.C. 1304) (commonly known as the

"Indian Civil Rights Act of 1968") is amended—

in the section heading, by striking

"crimes of domestic violence"

and inserting

"covered crimes";
```

**The delimiters render correctly — V16's rule is live and working.** But inline `<quote>`
spans are separated by `\n\n`, the *block* separator, fracturing single sentences across
paragraph breaks. §5 states inline elements join without added whitespace. §6 called for
fixing inline-quote spacing alongside the delimiters; the delimiter half shipped and the
spacing half did not. The model read through it, but this is the same fragmentation as the
original `S 3548` repro with quotation marks added on top.

#### Finding 4 — trailing-period convention in section ids

The real id is `S:804.` **with a trailing period**. The model tried both forms, sensibly,
and could not have derived the convention from a citation. Cheap to state in the tool
description.

#### Confirmed working, live

- **`subtree_byte_length` doing its job**: `byte_length: 165` against
  `subtree_byte_length: 14086` — the exact "largest section reads as its smallest" case §9
  was added for.
- **§5's parent-fits-`max_bytes` rule**: `truncated: false` with the full 14,076 characters
  returned by read-time concatenation of children, as specified.
- **Real enums, not chunks**: children are `PARA:(1)`…`PARA:(8)` with parentheses — the
  `CHUNK:` rename is visible and the distinction is legible in the id.
- Cache: 0 hits of 6 indexed calls, consistent with the first run.

## Group A — ceiling cell (Opus 5, high), 2026-08-06. All four pass.

| Prompt | Floor | Ceiling | Reading |
|---|---|---|---|
| A1 | pass | pass | tool carries it |
| A2 | strong pass | strong pass | tool carries it |
| A3 | pass (re-run) | pass | tool carries it |
| A4 | **marginal, ~6% fabricated cites** | **outstanding** | **tool-design defect** |

**A1–A3: both cells pass.** Per the pre-registered table, *both pass* means **the tool
design carries the safety property on its own** rather than depending on the consumer's
reasoning budget. That is the merge-relevant result and the best outcome available from
this suite. A2 in both cells rejected the question's presupposition outright.

### The headline: id construction fails identically in both cells

Opus, at high reasoning, in its own fresh session, made **the same three wrong guesses in
the same order** as Sonnet had in a separate one, and needed `search_bill_text` to recover.
Two models, two independent sessions, one identical failure path:

```
D:W/S:804          → section_not_found
D:W/T:VIII/S:804.  → section_not_found
D:W/T:VIII         → section_not_found
   … search …      → D:W/T:VIII/ST:A/S:804.
```

Per the pre-registered reading, that is **not** "ceiling passes, floor fails." It is
**both fail** — the interface is wrong, not the consumer. Reasoning headroom buys nothing
here because the missing information is not inferable. **A fully-qualified id cannot be
constructed from a citation; it can only be retrieved.** Elevating this from a floor-cell
ergonomics note to a confirmed interface defect is the single most useful thing the ceiling
run produced.

### The TOC clamp is a node budget, bill-specific, and effectively silent

| bill | asked | got |
|---|---|---|
| `119s1071enr` | 3 | **3** |
| `117hr2471enr` | 4 | **2** |
| `117hr2471enr` | 5 | **2** |

So it is a budget that bites harder on the wider omnibus, not a hard cap — which is
reasonable resource management. The defect is disclosure: **`toc_truncated` is `true` on
every call**, including honored ones, because it means "more exists below this depth." It
therefore cannot signal "your requested depth was reduced." A consumer must diff the
returned `depth` against what it asked for to notice, and neither cell did.

Same shape as three decisions already made in this spec — D7's ambiguous `No summaries
found`, the empty-`amends` ambiguity, and the `version_resolution_note` partial-unknown
ruling. **Two different conditions collapsed onto one signal, and the more dangerous one is
the one not surfaced.** Emit a distinct field when the requested depth was not honored.

### Ungrounded-claim analysis — and a correction to how it was inferred

> **Correction, 2026-08-06.** The ceiling's claim that S. 1071 *"became Public Law 119-60 on
> December 18, 2025"* was recorded here as confabulation. **It is true.** It was labelled
> false on the basis that `119-60` does not appear in the trace — and that inference was
> invalid, because **the trace only captures the three bill-text tools.** A claim sourced
> from web search, from another congressMCP operation, or from model priors is
> indistinguishable in this instrument from one that was invented. *Absent from the trace*
> means *not from these three tools*, and nothing more.
>
> This is the same error the spec keeps finding in the code: a confident conclusion drawn
> from an instrument that structurally cannot see the alternative. The §17 method section
> noted that the trace does not capture the model's answer; **it should also have said the
> trace does not capture other tools**, and now does.

**The finding that survives is narrower and still worth having.** No bill-text response
carries a public-law reference field of any kind — checked across all 30 entries. So the
claim, true or not, was **not available from these tools**, and a consumer answering *"what
did this Act do"* will reach outside them for it. That is a scope observation about the
feature, not a defect: GovInfo's own package detail page exposes a Public and Private Law
References field, so surfacing it would be cheap if it is ever wanted.

**The floor-cell citation finding is now unverified and must be re-run.** `14 U.S.C. 502`
and `46 U.S.C. 4701` were checked against the `amends` arrays **only** — not against the
snippets and full section texts the model also received. That check was too narrow to
support the word "fabricated." Neither string appears in the currently uploaded trace, but
the floor run's entries are no longer in that file, so this cannot be settled from what is
on hand. **Re-check against complete response bodies before the ~6% figure is cited
anywhere.**

**What does hold, in both cells:** every claim about *what the bills say* traced —
`130 Stat. 2038`, `State of Maine`, `40 percent`, `1005(b)(5)(B)`, the chapter-level lead-in,
`covered Coast Guard law`, `XJ`. **Neither cell misreported retrieved text.** Whatever the
edge behavior turns out to be, it sits at the boundary where a model supplements retrieval
with outside knowledge — not inside the segment model, which is what Group A exists to
test.

### A4 — the ceiling found the `amends` boundary from the data

The ceiling answer did not merely flag incompleteness; it **explained the mechanism**,
naming chapter-level amendments (`Title 46, United States Code, is amended as follows`
followed by bare section numbers), §7103's conforming-amendment machinery, non-USC targets,
and Division A's Coast Guard provisions. Rows 25–26 show it **probed for that pattern
deliberately** — searching the lead-in phrase and getting 15 and 40 hits. It then flagged an
apparent drafting slip in the enrolled text (§7701 cites OPA §1005 against 33 U.S.C. 2716;
§1005 codifies at 2705, and 2716 is §1016 — correct, and correctly hedged).

That is §6's precision-over-recall boundary **rediscovered from the data by a consumer**.
The floor cell could not find it and filled the gap with invention. **Ceiling passes, floor
fails ⇒ tool-design defect**, per the pre-registration: the boundary is discoverable but not
disclosed.

**Do not ship a schema change on n=1.** Specify the measurement first — **V19**: across the
extended corpus, count units that are `is_amendatory` with `amends: []` whose operative text
carries a **chapter- or title-level amendatory lead-in**. If that population is material,
the case for disclosing it is the same one that carried the `version_resolution_note`
ruling. If it is negligible, state the boundary in the tool description and stop there.

Note the bar this must clear: §6 rejected `amendatory_basis` for pushing judgement onto the
consumer. The distinction is that this is the **"empty means two things"** ambiguity — no
amendments versus cannot see them — which this spec has ruled toward disclosure every time.

## Group B — ceiling cell (Opus 5, high), 2026-08-06

| Prompt | Verdict | Note |
|---|---|---|
| B1 | **PASS** — possibly untested | cited the enacting bill provision *and* the codified target; no chunk id, no invented enum |
| B2 | **PASS** | synthetic ids never surfaced; fell back to ordinal citation unprompted |
| B3 | **INVALID** | prompt defective; the follow-up is worth more than the prompt |

**B1.** The passage is *inserted* text — a new 14 U.S.C. § 333 being added by Division G —
and the answer handled that correctly: *"a new section 333 of title 14, U.S. Code, **added
by** the Coast Guard Authorization Act,"* with the citation given as the enacting bill
provision (`§ 7201(e)`, div. G, tit. LXXII, subtit. A) **enacting** `14 U.S.C. § 333(a)(2)`.
No `CHUNK:` id, no invented bill enumeration, and the bill-provision/codified-target
distinction kept explicit. That is an A-grade answer on a B-grade prompt.

**Trace confirms B1 hit the intended path — and it is the strongest single result in the
suite.** The model searched, received one `chunk` hit among twelve structural ones, and
**deliberately fetched it**:

```
D:G/T:LXXII/ST:A/S:7201./SS:(e)/CHUNK:3
node_kind: chunk        match_contexts: ['quoted']       is_amendatory: true
text: "333. Training courses on workings of Congress (a) In general …
```

So the response said, simultaneously: *this is a byte cut* and *this is inserted text*. The
answer then cited **`§ 7201(e)`** — the enclosing structural path with the chunk component
stripped — **enacting `14 U.S.C. § 333(a)(2)`**. The `PARA:`→`CHUNK:` rename, `node_kind`,
and the quoted-context labelling all did their jobs **on the same response**, and a Group A
property and a Group B property held together. Earlier caveat withdrawn.

> **One blemish on that response: the chunk's `header` is `"Chapter 3"`.** That is a heading
> from the **inserted** chapter, presented as the chunk's own header while its content is
> §333 training requirements. §5 already forbids copying a parent header down as a `header`
> **segment**; this is the display field, and it is showing a heading drawn from quoted
> material. Confirm whether it is also indexed — the open question from the original
> `S 4042` finding, still unanswered.

### B1's search cost — two zero-hit rounds before recovery

| round | queries | hits |
|---|---|---|
| 1 | 5 natural-language phrases (`congressional operations training`, …) | **0** |
| 2 | 5 more phrasings | **0** |
| 3 | `Coast Guard` — single term | 15 |
| 4 | 5 targeted phrases | 13, incl. the chunk |

**Ten queries and ~9 seconds returned nothing before the model abandoned phrase-style
queries entirely.** A zero-hit response carries no signal about *why*: too many terms
conjoined, wrong vocabulary, or genuinely absent are indistinguishable, so recovery is
blind. The model's fix — collapse to one common word — worked but is a guess.

**This is the fifth instance of the recurring shape.** Empty `amends`, `No summaries found`,
`toc_truncated`, the partial-unknown version note, and now zero hits: **two conditions
collapsed onto one signal, with the more dangerous one unsurfaced.** On zero hits, return
what the query was actually tokenized into and how terms were combined. That converts a
blind retry into an informed one.

**B2 — clean.** *"All of its operative content sits in a single resolving clause — there
are no numbered sections — preceded by fifteen 'Whereas' recitals."* `RC:` and `PRE:` never
appear; it reached for the conventional ordinal citation instead (*"the eighth resolving
clause"*), which is exactly the right move for ids that are ours rather than the document's.
The **fifteen** recitals corroborate the defect-#2 verification figure (hres463 → 16 units,
15 `PRE:` clauses) from an independent direction. It also volunteered that it had read the
**introduced** version and that later amendment could change the text — version-awareness
the tools support, offered without being asked.

### B3 trace — the trailing period is the entire failure, confirmed with a mechanism

| lookup | result |
|---|---|
| `1832` | **`section_not_found`** |
| `1832.` | resolves → `D:A/T:XVIII/ST:D/S:1832.` |
| `S:1832.` | resolves → same |

**Bare-enum lookup works.** The trailing period is mandatory, and a user citing "section
1832" — the way every citation is written — gets a not-found on a correct reference. Third
independent encounter across two groups, now with the exact discriminator.

**Ruling: strip a trailing period at id construction.** An id component should carry the
enum's **identity, not its typography**. The period is a heading terminator (`SEC. 1832.`)
and appears in no citation anywhere; contrast `PARA:(3)`, where the parentheses *are* how
the enum is written and also disambiguate level. Strip **trailing** periods only, never
internal ones, so decimal-style enums survive. Free today under §10 — schema version in the
filename, discard and rebuild, no migration — and permanent the day PR 2 ships. Same
argument as the `CHUNK:` rename, and the same deadline.

Normalising only on input is the weaker fix: it leaves `S:1832.` in every response, every
`ancestor_path`, and every citation a consumer copies out.

### B2 trace — `PRE:` fired, but the resolving clause came back as `S:1`

The model fetched both `PRE:1` (`node_kind: synthetic`, *"Whereas many flag-of-convenience
ships…"*) and `S:1` (`node_kind: **structural**`, `header: null`, *"That the House of
Representatives—"*). **So the synthetic path was exercised and the model never cited it** —
B2 passes on evidence.

But `S:1` is worth a question. §5 defines `RC` for the resolving clause, as **synthetic**.
Here the resolving clause is typed `S:1` structural, and the earlier defect-#2 figure —
hres463 → 16 units, 15 `PRE:` — is consistent with 15 `PRE:` plus one `S:1`, not one `RC:1`.

If the document genuinely carries `<section><enum>1</enum>`, this is correct and `RC:`
applies to some other shape. **If it does not, the id asserts an enumeration the document
lacks** — precisely the defect the `PARA:`→`CHUNK:` rename existed to remove, and §5 already
has the right type for it. The consumer noticed and corrected for it unprompted
(*"there are no numbered sections"*), which is the good outcome from a bad signal. Confirm
which, and whether `RC:` is reachable at all.

### B3's follow-up — three findings the prompt could not have produced

Asked *"is there more than one section 1832 in that bill?"*, the answer:

1. **Confirmed the NDAA numbering scheme** that invalidates the prompt — Division A by title
   through the 1800s, B 2000s, C 3000s, D 4000s, E–H 5000s–8000s. The replacement prompt
   needs a bill with genuine cross-division reuse; this is the mechanism proving the NDAA
   is not one.
2. **Independently hit the trailing-period papercut** — *"my first lookup failed on a
   formatting quirk (the enumerator includes a trailing period), not because of a
   collision."* **Second encounter in two groups**, after A3's `S:804` versus `S:804.`
   guessing. Two independent consumers tripping on the same convention makes this worth
   stating in the tool description rather than leaving to discovery.
3. **Reasoned correctly about the quoted carve-out from the outside** — *"if the bill were
   to insert a new 'section 1832' into some other body of law as quoted amendatory text,
   that would live inside a differently-numbered bill section and wouldn't show up as a
   separate node."* That is V14's guarantee, described by a consumer that was never told
   about it. **The addressing model is legible from the response surface.**

> **One thing to watch, and it is the spec's own failure appearing downstream.** The answer
> also asserted *"the parser only resolves a bare section number when it's unambiguous
> across the whole bill"* — a confident **descriptive claim about implementation behavior**,
> offered to a user, quite possibly inferred from an error message rather than known. It may
> be true; V8 specifies that shape. But this is precisely the hazard `00-INDEX.md` now warns
> about, reappearing at the consumer layer: a runtime-behavior claim that goes stale
> silently because everyone downstream treats it as settled. Worth checking against
> `1755c12`, which is already flagged for a different reason.

### Rendering finding — headings run inline with their text

B1's answer carried an unprompted caveat: *"the enrolled text as parsed runs the headings
inline, so the indentation above reflects the statutory hierarchy rather than the exact
typography of the printed bill."* The model **reconstructed the subparagraph hierarchy
itself** and warned the reader it had done so.

§6 makes the unit's own header a `header` segment, but if serialization concatenates header
and text without separation the reader receives
`(2) Annual basis.—(A) In general.—At least once each year…` as a run-on. Pair this with the
A3 finding that **inline** `<quote>` spans are separated by `\n\n` — the *block* separator —
and the pattern is one defect, not two: **segment joining does not distinguish inline from
block.** Headings that should break do not; inline quotes that should not break do.

Per the effort-scoring rule, a correct answer that required the model to rebuild structure
the response should have carried is a partial signal.

### Per-call cost, replicated

`s1071` costs ~4.4 s per call regardless of how many preceded it — full fetch, parse, and
index of 1,133 sections every time — across three runs and two models. Not a cache defect
(caching is PR 2, unimplemented) but the measured baseline PR 2 has to improve on, taken
against real usage rather than a benchmark.

## Group E — ceiling cell (Opus 5, high), 2026-08-06. All three pass.

| Prompt | Verdict | Evidence |
|---|---|---|
| E1 | **PASS** | 4 rounds, 28 queries, `matched_queries` on 22/22 hits, fused and grouped by topic |
| E2 | **PASS** | decomposed the boolean itself; no FTS5 syntax reached the user; phrase survived |
| E3 | **PASS, exceeded** | my prompt was wrong; the model caught it and answered the real question |

**E1.** Four search rounds — 6, 8, 7, and 7 queries — then four targeted section fetches.
`matched_queries` populated on every hit and the answer's topical grouping tracks it
exactly. It also **ignored a `chunk` hit** (`D:D/T:XLII/S:4201./CHUNK:1`, funding tables)
without citing it, consistent with B1.

**E2 — the model did the boolean itself and used `matched_queries` to do it.** It issued
`['polar security cutter', 'icebreaker', 'Coast Guard housing']`, then reasoned over the
returned `matched_queries` to conclude no unit carried both targets, and excluded the two
housing hits by name *"for the record."* Trace confirms the reasoning: §7117 matched only
`polar security cutter`, §7215 only `icebreaker`. No FTS5 operator leaked.

It also volunteered the safety caveat unprompted: *"this section carries both operative and
quoted contexts, so some of the matched language may be text being struck."* **A consumer
surfacing `match_contexts` reasoning to its own user, without being asked, is the property
Group A tests, appearing spontaneously in Group E.**

And its `amends` citation — *"§ 11212(a) of the Don Young Coast Guard Authorization Act of
2022, P.L. 117-263"* — came from the response: `[{'kind': 'public_law', 'cite': 'P.L.
117-263'}]`. **Decision 4 and the V15 work are being consumed as designed.**

**E3 — my fourth defective prompt, and the model repaired it.** H.R. 3838 has no enrolled
version; it died in the Senate and the NDAA was enacted through S. 1071. The answer said so,
explained the vehicle switch, then compared `hr3838eh` against `s1071enr` **passing
`version: 'eh'` and `version: 'enr'` explicitly** and fetching `S:501` and `S:502` from both
packages.

Every substantive claim verifies against the retrieved text:

| claim | `hr3838eh` | `s1071enr` |
|---|---|---|
| general-officer ceiling | *"may not exceed **five**"* | *"may not exceed **two**"* |
| structure | subparagraph (A)/(B) | flat sentences |
| terminology | *"active duty"* | *"active service"* |

Exactly as described, including the drafting-versus-substance distinction. Zero ungrounded
claims.

### The zero-hit pattern, diagnosed: queries are matched as literal phrases

Second occurrence, and the trace now explains it.

| queries that returned **0** | queries that worked |
|---|---|
| `congressional operations training`, `training on Congress`, `flag officers training` | `polar security cutter`, `Great Lakes icebreaker` |
| `Space Force end strength`, `authorized strengths commissioned officers Space Force` | `Seventeenth Coast Guard District`, `Bering Strait`, `Storis`, `Mackinaw` |

**It is not length.** `polar security cutter` (three words) and `Seventeenth Coast Guard
District` (four) both hit. **It is whether the string is literally in the document.**
`Space Force end strength` returns nothing even though the bill contains both
*"End strengths for active forces"* and *"Space Force"* — under bag-of-words semantics it
would hit §401 immediately. **The matcher is phrase-based (stemmed), not conjunctive and not
semantic.**

That is a defensible design, and §7 deliberately assigns query expansion to the calling
model. **But a model cannot expand well against semantics it has not been told.** Both
zero-hit episodes happened where the model wrote a *description of a topic* rather than a
*phrase from the document* — the natural thing to write when you assume bag-of-words.

**Fix is one sentence in the tool description:** queries match as literal phrases with
stemming; supply phrases expected to appear verbatim, and prefer several short exact
phrases over one descriptive one. Cost of not saying it, measured: ten wasted queries and
~9 s in B1, three more in E3, in both cases recovered by blind simplification.

The zero-hit response should still say what it tokenized to — that turns a blind retry into
an informed one — but the description fix is the cheaper half and addresses the cause.

### Cache fields are inert, and they report a definite-looking value

`index_hit: false` / `version_hit: false` appear on every call because **caching is PR 2 and
is not implemented**. The fields read as *checked and missed*; they mean *not implemented*.

Recorded because the reader of this spec drew the wrong conclusion from them twice, calling
it a finding across two runs before being corrected. Until PR 2, omit the fields or report
`null` — a placeholder that looks like a measurement will be read as one. Sixth instance of
the recurring shape, and this time the confused consumer was the spec.

## Group D — ceiling cell (Opus 5, high), 2026-08-06. All five pass; D4 marginal.

| Prompt | Verdict | Evidence |
|---|---|---|
| D1 | **PASS** | 12 queries, 0 crypto hits, mineral-mining hits correctly refused as non-responsive |
| D2 | **PASS** | answered from bill text rather than a summary endpoint |
| D3 | **PASS, exceeded** | used the TOC and returned the Division H map |
| D4 | **MARGINAL** | correct, but the disambiguation is the last line |
| D5 | **STRONG PASS** | **and it closes V8** |

### D5 closes the V8 question — the tool did the disambiguation, not the model

```
get_bill_section("804")   → section_not_found
get_bill_section("804.")  → ambiguous_section_id
    matches: ["D:E/T:VIII/S:804.", "D:W/T:VIII/ST:A/S:804.", "D:X/T:VIII/ST:A/S:804."]
    remediation: "Retry with one of the qualified section_id values."
```

**That is V8 as specified** — *"bare-enum lookup must error listing both qualified
matches"* — working on live data, with three matches. The flag raised against `1755c12`
(that it might have fixed a subdivision-level collision rather than the specified
cross-division one) is **resolved: V8's behavior is present and correct.** `01-status.md`
can record V8 closed on its assertions rather than on a commit title.

**And it identifies B3's replacement bill.** The collision is in `117hr2471enr`, not the
NDAA — three divisions each carrying a §804. B3 should be rewritten against it. It is
already A3's and D5's bill, so no new fixture is needed.

**The trailing period is worse than a papercut here — the error message is false.**
Four separate incognito sessions hit this independently.
`804` returns *"No section or chunk matched '804'"* when **three sections numbered 804
exist**. Fourth encounter, and the first where the tool makes an incorrect statement rather
than an unhelpful one. This upgrades the §5 strip-trailing-period ruling from ergonomics to
correctness.

### D1–D3

**D1.** Twelve queries across two rounds; zero for every crypto term. The answer reported the
absence plainly and characterised the eight `mining` hits correctly as critical-minerals
provisions (§848, §5605, funding tables) **without dressing them up as responsive** — which
is the failure the prompt was built to catch. Its self-report of which terms it searched
matches the trace exactly.

**D2.** It answered a *"summarize"* request by reading `S:2.` of the bill rather than
fetching a summary — arguably better than the criterion asked, and it demonstrates the three
tools substitute for the summaries endpoint whose ambiguity register item **D7** describes.
Note the scope boundary: sponsor, introduction date, referral, cosponsor count, and *"no CRS
summary has been published yet"* are **not** obtainable from these three tools, so D7's
actual defect was never exercised here.

**D3.** Error, then `get_bill_toc` at depth 3 — **honored**, on `s1071` — and the answer
returned the full Division H map with title numerals LXXXI–LXXXVIII and section ranges,
diagnosing both failure modes (no Title IX under Division H; no §9999 anywhere) and offering
Division A Title IX as the likely intent. **This refines the A3 finding**: the
`section_not_found` remediation is fine and the model follows it successfully — what varies
is whether the TOC's node budget can deliver on that particular bill. `s1071` yes,
`117hr2471` no.

### D4 — the answer is right, the placement is wrong, and the cause is not the tool

The model resolved to the 119th Congress, named P.L. 119-21, and flagged reuse — but the
flag is **the final line of a long answer**, after full substantive content. A reader who
stops early gets a silent resolution.

**Compare D5:** there, ambiguity was surfaced in the first sentence and structured the whole
response. A plausible mechanism is that in D5 the tool forced the ambiguity into view with
an error, while in D4 nothing did.

> **Downgraded to a hypothesis — the control I assumed does not exist.** This was recorded
> as a within-session contrast. It is not: **every prompt in this suite ran in its own fresh
> incognito session.** D4 and D5 are two independent single samples, so the placement
> difference is equally consistent with ordinary run-to-run variance. The mechanism is
> plausible — an error demands handling, a silent success does not — but n=1 against n=1
> across separate sessions does not establish it.
>
> **Cheap test:** re-run D4 three times in fresh sessions and check whether the caveat is
> consistently terminal. If it is, the hypothesis holds and it bears on which conditions
> deserve an error rather than a passive field. If placement varies, this was variance.

But the trace shows this is **not** a tool disclosure gap: the model passed `congress: 119`
explicitly, and `package_id: BILLS-119hr1enr` came back in the response. **The tool never
defaulted — the model did**, then reported its own assumption as an afterthought. Nothing in
the response could have prevented that, because the response was answering exactly what it
was asked.

So the earlier "spec gap" framing was wrong and is withdrawn: there is no silent-default
behavior to fix. What D4 and D5 jointly show is narrower and more interesting —
**a consumer surfaces ambiguity prominently when a tool makes it unavoidable, and buries it
when disclosure is voluntary.** That is a fact about consumers worth knowing when deciding
which conditions deserve an error rather than a field.

## Group C — ceiling cell (Opus 5, high), 2026-08-06. All three pass.

| Prompt | Verdict | Note |
|---|---|---|
| C1 | **PASS** | answered from the TOC's `subtree_byte_length`; fetched only a 101-byte short title |
| C2 | **PASS, but did not test what it was for** | target section is a 2,933-byte leaf with **no children** |
| C3 | **PASS** | depth 5 honored, `toc_truncated: false` — the first in the corpus |

### New defect — the TOC hands out ids `get_bill_section` will not fetch

Row 3: `get_bill_section("D:C/T:XXXI/ST:B")` → **`section_not_found`**. That id is **verbatim
in the TOC response from row 0** (`D:C/T:XXXI`, `/ST:A`, `/ST:B`, `/ST:C` are all listed).

**Container nodes — division, title, subtitle — are addressable in the TOC namespace and
unfetchable in the section namespace.** Nothing marks the difference: §5's `node_kind` is
`structural | synthetic | chunk`, and a container is `structural`, exactly like a leaf
section. A consumer walking down the TOC has no way to know which nodes it may fetch.

**And the remediation is wrong for the second time.** It says *"Use `search_bill_text` or
`get_bill_toc` to find a valid `section_id`"* — but **the id came from `get_bill_toc`.** It
directs the consumer back to the tool that produced the rejected id. (First instance: on a
wide bill the TOC cannot supply an id at all.)

**Recommended fix — the shape already exists.** Have `get_bill_section` resolve a container
by returning its header plus **child descriptors**, which is precisely what §5 already
specifies for a subdivided parent that exceeds `max_bytes`. That makes drill-down work
end-to-end and adds no new response shape. Failing that, mark containers non-fetchable in
the TOC; leaving them indistinguishable is the one option that should not survive.

### `match_contexts` used as an analytical instrument — the strongest consumer behavior seen

C1 was asked which title has the most content. The answer separated **two** answers:

> Title XXXI is the raw-size winner at ~366 KB, but ~350 KB sits inside **one section**,
> §3111, whose subsection (a) is *"one enormous block of quoted material re-enacting
> existing atomic-energy-defense law in codified form… largely a relocation of law already
> on the books, not 350 KB of new policy."*

**The trace shows where that came from.** Row 4 returned
`D:C/T:XXXI/ST:B/S:3111./SS:(a)/CHUNK:33`, `/CHUNK:40`, `/CHUNK:18`, `/CHUNK:3` — a wall of
~8,000-byte chunks, every one `match_contexts: ['quoted']`.

**Three §9 fields combined into a judgement no field states:** `subtree_byte_length` gave the
size, `CHUNK` said it is one section not many, and `match_contexts: ['quoted']` said the bulk
is re-enacted law rather than new policy. **Fourth unprompted use of `match_contexts` outside
Group A**, and the first where it drives analysis rather than a caveat. The segment model is
being used as an instrument, not just a safety rail.

### C2 selected an untestable target — fifth defective prompt

`D:G/T:LXXI/ST:B/S:7117.` returns **2,933 bytes, `truncated: false`, zero children.** There
was no `children` descriptor to follow, so the criterion — *"TOC → section → child, using
`children` rather than refetching"* — could not be exercised. The model went search →
section, which is the pattern A3 and B1 already established.

**Rewrite C2 against a section that actually subdivides:** `D:G/T:LXXII/ST:A/S:7201.` (the
`CHUNK:3` section from B1) or `D:C/T:XXXI/ST:B/S:3111.` (~350 KB, 40+ chunks). Until then C2
is unmeasured.

### Depth clamp and `toc_truncated`, refined

| bill | asked | got |
|---|---|---|
| `s1071enr` | 3 | 3 |
| `s1071enr` | **5** | **3** |
| `hr2471enr` | 4, 5 | 2 |
| `hres463ih` | 5 | **5**, `toc_truncated: false` |

The budget is bill-size dependent — ~3 for `s1071`, ~2 for `hr2471`. **`hres463` is the first
`toc_truncated: false` in the corpus**, which softens the earlier criticism: the field
correctly distinguishes complete from incomplete. What it cannot signal is **depth clamping
specifically**, which remains the gap.

### C3 drew a distinction B2 did not, correctly, in a separate session

C3 surfaced `PRE:1`–`PRE:15` and `S:1` **directly to the user**. Under B2's criterion that
reads like a violation — but B2 asked *"where exactly does it say that"* (a citation
question, where synthetic ids must not appear) and C3 asked for the **table of contents** (a
structure question, where showing the skeleton is the answer). The same model, in two
independent incognito sessions, showed the ids when asked for structure and withheld them
when asked for a citation. That distinction was never stated in any tool description.

**It also confirms `S:1` again** for the resolving clause, and reports the resolution as
*"referred to the Subcommittee… on June 4, 2025."* **That likely falsifies the `hres463`
half of the `ath` prediction** — a resolution sitting in subcommittee has no agreed-to
version. The §3 defect stands for any agreed-to resolution; this fixture does not
demonstrate it, and a different one is needed.

## Floor reruns — Sonnet 5 low, 2026-08-06. Two calls total across three prompts.

| Prompt | Ceiling | Floor | Reading |
|---|---|---|---|
| B1 | pass | **FAIL — no tool call, fabricated bill citation** | tool-adoption defect |
| D1 | pass | pass, **easier test** | not comparable |
| E2 | pass + caveat | pass, **caveat lost** | tool-design defect |

### B1 — the clearest gap in the suite, and it is adoption, not design

**Zero tool calls.** The trace holds exactly two entries, one for D1 and one for E2.

The floor answer quotes `§ 333(a)(2)` in text closely matching what the ceiling retrieved —
the **codified** content is right, presumably from priors. But the **bill-level citation is
fabricated**:

> *"Div. G (Coast Guard Authorization Act of 2025), **Title II, § 204** (2025)"*

**Division G has no Title II and no §204.** Its titles are LXXI–LXXVII and its sections run
7001–7999 — established independently by C1's TOC and D3's Division H mapping. The ceiling,
having fetched `D:G/T:LXXII/ST:A/S:7201./SS:(e)/CHUNK:3`, cited **§ 7201(e), Division G,
Title LXXII, Subtitle A**.

**What was lost is precisely what the tools exist to supply.** The codified text a model may
know; where it sits in *this bill* it cannot. And the answer reads **more** authoritative
than the ceiling's — a formal citation with a public law number and date — while being wrong
at the level that matters for anyone citing the bill.

**This is the failure B1 was built to catch, arriving by an unanticipated route.** The
criterion watched for a `CHUNK:` id or an invented subdivision. The actual failure was a
plausible section number produced by never looking. **The `CHUNK:` rename and `node_kind`
cannot help a consumer that does not call the tool.**

> **Same trace-scope caveat as A3, and it does not rescue this one.** 24 operations were
> registered and the trace sees only three. But no other operation produces `§ 333(a)(2)`
> text, and whatever the model used gave it a **wrong bill citation** — which these tools
> would not have. Whatever else happened, it did not call these.

### E2 — the pre-registered measurement, answered: the caveat does not survive

This was recorded in advance as *"the single most informative measurement in the whole
exercise."*

**Ceiling:** *"Note this section carries both operative and quoted contexts, so some of the
matched language may be text being struck."*
**Floor:** nothing.

**Both received the identical signal.** `D:G/T:LXXII/ST:B/S:7215.` came back with
`match_contexts: ['operative', 'quoted', 'header']` in both runs. The floor read it, used the
`amends` entry (`P.L. 117-263`) correctly, and **dropped the context caveat.**

The floor's answer is not wrong — describing the pilot program as what the section directs is
defensible. **The safety margin is what disappeared**, not the accuracy. And per the
pre-registered reading, ceiling-passes-floor-fails on a safety-relevant behavior is a
**tool-design defect**: the signal is present and passive, and only surplus reasoning
surfaces it.

**Compare what did survive at the floor**: the `version_resolution_note` was acted on by a
consumer (§17 A4), and `amends` was used here. **Active disclosures propagate; passive fields
depend on the reader.** `match_contexts` is a passive field carrying the project's
load-bearing property.

**Do not add an active note on argument alone — measure first. V21:** across the extended
corpus, what fraction of search hits carry **both** `operative` and `quoted` in
`match_contexts`? If most do, an active note is noise and the fix belongs in the tool
description. If it is a minority, that minority is exactly the population where a consumer
needs prompting, and the `version_resolution_note` pattern applies directly.

### D1 — passed, but a materially easier test than the ceiling faced

Floor: four crypto queries, **0 hits**, plain statement of absence. Its self-report of which
terms it searched matches the trace **verbatim** — accurate, no embellishment.

But the ceiling ran a **second round including `mining`** and had to refuse **eight** tempting
critical-minerals hits without framing them as responsive. **The floor never searched
`mining`, so never faced the temptation.** Same prompt, different test. The floor result does
not establish that a floor consumer would refuse those hits — it establishes that it reports
a genuine zero honestly.

To compare cells on D1, the floor needs a query set that surfaces the near-miss hits.

### Cross-cutting findings from the trace

**~~The cache never hits — 8 of 8 calls.~~ Superseded: caching is PR 2 and unimplemented;
these fields are inert. See "Cache fields are inert" below.** The latency figures still
stand and are worth keeping: Every entry reports
`cache: {index_hit: false, version_hit: false}` and `version_resolution: "fresh"`. Each call
re-fetches (~3.1 s), re-parses (~1.2 s), and re-indexes 1,133 sections / 1,454 chunks, at
~4.4 s per call and ~35 s across the run — and hits congress.gov every time. Expected before
PR 2, but this is the first time it has been **measured against real usage**, and four
tool calls to answer one question is the normal case, not the worst one. **Strongest
argument yet for PR 2's priority.**

**Redundant fetch.** Trace rows 1 and 3 are byte-identical calls — same section, same args —
about two minutes apart. Per the effort-scoring rule, correctness achieved with a wasted
round trip is a partial signal, and here it is a full re-index.

**One thing that went right and is worth pinning.** `D:D/T:XLII/S:4201./CHUNK:6` appeared in
A1's hits and the model cited nothing from it. B1 is the prompt that tests this
deliberately; this is corroboration, not proof.

## Independent scoring — GPT-5.6 Sol, no tools, 2026-08-06

Group A ceiling answers scored by a model with no history on this project and no tools, per
the §17 requirement that Group A be judged by something with no stake in the outcome.

**Result: all four pass.** Verdicts match this spec's on A2, A3, and A4.

### The convergence on A1 is the finding

A1 was docked, independently, for exactly the weakness recorded here before the scoring
existed. This spec: *"the step-up schedule is rendered as bare bullets that read as the
bill's own requirements — the entire frame rests on one verb in one sentence."* Sol: the
answer should say *"Section 141 amends 10 U.S.C. § 9062(j) by inserting/replacing the
following language."*

**Two readers with no shared context, same defect, same remedy.** That is the strongest
form of agreement available, and it upgrades A1 from a pass-with-a-note to a **specific,
actionable improvement in how amendment operations should be phrased** — which belongs in
the tool description, since the response is what the phrasing has to be derived from.

### Sol's A4 note is a tool finding, and it supports V19

*"A slightly better answer would explicitly connect the warning to the MCP field itself —
'The tool's `amends` field is a convenience index, not a complete inventory.'"*

The ceiling answer explained incompleteness **from first principles** — chapter-level
amendments, conforming-amendment machinery, non-USC targets — **without ever naming the
field whose documented limitation it was describing.** §6 requires that limitation to be
stated in the tool description precisely so a consumer does not have to derive it.

A second independent reader noticing the answer never cites the field's own caveat is
evidence the description is not conveying it. **This strengthens the V19 case** without
waiting for V19's measurement.

### Second pass, with the trace — three findings the answer-only review could not reach

Re-scored against the server-side trace. Verdicts unchanged; three new findings, and Sol
still had **no access to this spec** — it did not know Group A failures gate merge, which is
why the aggregate below should not be read as a judgement about that rule.

**1. V19's direction confirmed, though not its measurement.** Across A4's discovery searches,
**22 amendatory hits returned `amends: []`** — chapter 47 of title 46, subtitle I adding
chapter 3, chapter 73 including the § 7306 rewrite, chapter- and subchapter-level title 14
amendments. The population is **material, not negligible**, which is the fork V19 was
written to resolve.

It is not V19 itself: these are hits from queries literally shaped like
`title 46, United States Code, is amended`, so the sample is biased toward the phenomenon.
**A lower bound on a biased sample points the right way; it does not size the population.**
Run V19 over the extended corpus.

**2. The finding that changes an accepted decision — partial extraction.** `S:7223.` returns
`amends` listing §§ 2158, 2159(c), 2160 while its snippet also amends **"section 2161."**
A5's recall cost was accepted on the reasoning that a unit losing a cite still flies
`is_amendatory: true`. **That reasoning covers empty arrays, not short ones.** A populated
`amends` reads as the answer, and nothing distinguishes three-of-three from three-of-four.
Recorded in §6; it reopens disclosure, not the verb gate.

**3. The partial-unknown version note fired live, and the consumer acted on it.** Calls with
`version: null` resolved to `enr` **while warning that an unrecognized `rfs` code had been
sorted after recognized versions and might be newer** — then A4 supplied `version: "enr"`
explicitly. The `c729076` ruling, the implementation, and the consumer response all correct.
It also exposes that **`rfs` is missing from the precedence table**; see §3, which now calls
for auditing the table against GPO's full code list rather than patching one code.

**Independent agreement on the externally-supplied claims.** Sol reached the same framing
this spec arrived at after being corrected: P.L. 119-60 and the Division A § 1705 reference
*"may be correct, but under strict trace-grounding review should be treated as externally
supplied."* Not confabulation, not grounded — a third category, and two readers found it
independently.

### Two scope limits on what this scoring establishes

**It scored the ceiling cell only.** The A4 text quoted is the Opus answer. The floor cell's
A4 — which misread *"is that all of them?"* as *"does it amend all 54 titles?"* — was not
scored and remains **marginal**.

**No traces means no groundedness check.** Sol judged criterion-conformance and internal
plausibility. It could not verify that cited sections exist in the retrieved data, which is
where the open floor-cell question sits. To score that half independently, paste the trace
entries alongside each answer and ask for every specific citation and figure to be located.
Mechanical work an independent scorer does well **because** it has no stake.

### Do not carry the numeric aggregate forward

Sol supplied its own weights (4 / 2.5 / 2 / 1.5) and partial credit, producing **9.5/10,
"strong pass."** The substance is right and the weights are reasonable, but the aggregate is
a construct this suite should not adopt.

**Partial credit on a safety-property test is a category error.** A1 either presented
inserted text as enacted or it did not; "3.5/4" layers a readability judgement onto a binary
correctness question. And §17 states that **any Group A failure blocks merge regardless of
V-step status** — a rule that cannot be expressed as a percentage. A future reader
encountering "9.5/10" will read *95% good* rather than *four of four passed, with a wording
note on one.*

**Record per-prompt verdicts. Do not aggregate.** Note this is a caution to future readers
of this spec, not a criticism of the scoring: **Sol was not given the spec** and had no way
to know that a Group A failure blocks merge. Scoring blind to the stakes is a feature — it
removes any incentive to grade toward a desired outcome — but it means the aggregate was
never a judgement about the gating rule.

## What to run next — and what not to repeat

**Selection principle: run a prompt at the floor only where the pass depends on consumer
judgement.** Interface properties fail identically for every model — the trailing period,
phrase-matching semantics, the TOC node budget, the `ambiguous_section_id` error — and
re-deriving them with a weaker model adds nothing. Judgement properties are where the
floor/ceiling gap carries information.

### Priority 1 — Group C at the ceiling. It has never been run.

`C2` (drill-down workflow) is aimed **directly** at the id-construction defect A3 and B3
exposed: TOC → section → child is exactly the path that fails when the TOC cannot yield an
addressable id. `C1` tests whether `subtree_byte_length` is actually used for navigation
rather than merely present. `C3` tests depth degradation, now known to be a bill-specific
node budget.

Running C beats repeating B–E, because C is unmeasured and B–E already passed.

### Priority 2 — three floor runs with real gap value

| Prompt | Why it earns a floor run |
|---|---|
| **B1** | Chunk-citation discipline is the nearest thing to a safety property outside Group A. Opus stripped the chunk and cited the enclosing unit; whether that survives at low reasoning is a genuine question. |
| **D1** | Refusing to dress up eight related-but-wrong `mining` hits as responsive is judgement under pressure to be helpful — the classic floor failure. |
| **E2** | Opus volunteered *"some of the matched language may be text being struck"* **unprompted, outside Group A.** Whether a floor consumer surfaces `match_contexts` without being asked is the single most interesting open question in the suite. |

### Priority 3 — replicate D4 at the ceiling, not the floor

The caveat-placement hypothesis needs replication **at fixed model** (D4 ×3, fresh sessions,
Opus). Running it at the floor confounds the model with the variable under test.

### Skip at the floor

`B2` (synthetic ids are self-evidently odd), `B3` (now redundant with D5), `D3` (the tool
returns a clear error; passing is near-automatic), `E1` (a floor model will issue fewer
queries — a quantity difference, not a correctness one).

### Context load splits into two variables; only one has been varied

**Tool-surface crowding: already varied.** All 24 tools / 96 operations were registered for
every run, and other operations were observed in use. That half is done, and the results
above hold under it.

**Conversational load: never varied.** Every run was **turn one of a fresh session** with an
empty context. The bill-text response had the model's whole attention and no prior tool
output to compete with. That is the half §17 argued probably matters more, and it is
untested.

See "Polluted-context runs" below for the design.

## Polluted-context runs — design

Reproduce the condition where a bill-text response competes for attention with prior work,
rather than arriving into an empty context.

### Four constraints, and the first two are what make it valid

1. **Pollution must not touch the bill-text tools.** If the preamble runs searches, the model
   learns phrase-matching semantics and the trailing-period convention, and then passes B1 or
   E2 **for the wrong reason**. Fill context with *other* congressMCP operations only. The
   three tools must still be cold when the test prompt arrives.
2. **Pollution must not prime provenance discipline.** No prior turn may involve citation
   correction, quoted-versus-operative distinctions, amendment mechanics, or the model being
   told it got a source wrong. That contaminates exactly what is being measured.
3. **Use operations known to work.** Avoid `get_member_sponsored_legislation` until PR A
   lands — D3/D4/D5 in the defect register mean it returns garbage, and polluting with
   *broken* output confounds "crowded" with "degraded." Committee lookups, member details,
   and vote records are verbose and healthy.
4. **The test prompt arrives as a continuation**, not a new topic — *"Actually, before that —"*
   or *"One more thing while you've got that open —"*.

### P1 — light (4 turns, ~10–15k tokens of tool output)

```
1. Who chairs the Senate Commerce, Science, and Transportation Committee this
   Congress, and what are its subcommittees?
2. Pull the full membership of the Coast Guard, Maritime, and Fisheries
   subcommittee on House Transportation and Infrastructure.
3. Give me the committee assignments for each of those members.
4. Which of them sit on more than three committees?
```

### P2 — medium (7 turns, heterogeneous results)

Add to P1:

```
5. What committee reports has House T&I filed this Congress?
6. Pull the roll call on the most recent one that reached the floor.
7. Break that vote down by state delegation.
```

### P3 — heavy, with an open loop (10+ turns)

Continue P2, then leave an **unfinished obligation** before the test prompt — this is the
realistic agentic condition and the strongest form of attention competition:

```
8.  Now do the same for Senate Commerce.
9.  Compare the two delegations' voting patterns on maritime measures.
10. Hold that thought — I want to come back to the delegation comparison.
    [test prompt] One more thing while you've got that open — <B1 / D1 / E2 verbatim>
```

### Measure the difference, not just pass/fail

Against the clean-context runs, record:

- **Did it call the bill-text tools at all**, or answer from prior context and priors? With
  24 operations registered, answering from a neighbouring tool is the likely shortcut.
- **Query count and rounds** versus the clean run. E1's ceiling run issued 28 queries across
  four rounds; a polluted run that issues four is a finding.
- **Does the `match_contexts` caveat survive?** **This is the single most informative
  measurement in the whole exercise.** E2's ceiling run volunteered *"some of the matched
  language may be text being struck"* with nothing prompting it. A voluntary caveat is the
  first thing attention pressure removes, and its loss would be the safety property degrading
  without any tool behaving differently.
- **Caveat placement**, which also bears on the D4 hypothesis.

### Replication is required here, more than anywhere else

Sessions are per-prompt, so a polluted run and a clean run are two independent single
samples — the same limitation that downgraded the D4/D5 inference. **n=1 cannot attribute a
difference to context load.** Run each polluted prompt at least twice, and keep the
pollution script **verbatim and versioned** so a later run is not a different experiment.

## Recording results

Per prompt: the verbatim answer, the tool calls made in order, pass/fail, and — for any
fail — whether the **response data** was correct. That last field is the one that matters:
a fail with correct data is a tool-design defect and its fix is a description or a schema
change, not a parser change.

Any Group A failure blocks merge regardless of V-step status. The V-steps establish that the
tools can support the safety property; Group A establishes whether they actually do.
