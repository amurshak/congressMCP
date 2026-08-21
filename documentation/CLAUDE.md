# Working in `documentation/fulltext/` — the bill-text spec

## Role and scope

This directory **is** the spec. Write authority is here and nowhere else in the repo.

- **Do not read or modify implementation source.** The job is to specify, not to describe what was built.
- A separate implementation session owns the code. **Its reports are claims, not ground truth** — see "Rules that have earned their place" below.

## Markdown formatting — decided 2026-08-15

**One line per paragraph. No hard wrapping, no fixed column.** The files were previously a mix of ~80-column wrapped and unwrapped prose; that mix makes exact-match edits fragile and turns a one-word change into a reflow cascade across several lines. One line per paragraph keeps a prose edit to a single changed line.

- **Leave structural lines alone:** tables (one row per line), fenced code blocks, headings, horizontal rules.
- **Blockquotes follow the same rule inside:** one line per quoted paragraph, each line prefixed `> `. Preserve nesting indent — a quote inside a numbered list stays `   > `.
- **Join hazard — hyphens.** Never join a line that ends in a hyphen by inserting a space: `load-` + `bearing` is **`load-bearing`**, not `load- bearing`. Suspended hyphens (`word- and phrase-level`, `chapter- or subtitle-level`) are already correct and must keep their space.
- A reflow is content-preserving only if it passes: whitespace-stripped text identical (ignoring collapsed `>` prefixes), and table/fence/heading/blockquote-block counts unchanged.

## Routing a question

- **Requirements or product** → ask the maintainer. Never guess.
- **Empirical** → do not assert. State the measurement that would settle it and hand it over.
- **IR/technical judgment** → decide it, and record the rationale in the spec.

## Rules that have earned their place

- **Measurement over assertion.** Never state a result as fact — cite something in this directory or name the experiment. **A mocked test fixture is not evidence** (a fabricated `pcs2` date once got cited here as an observation).
- **Preregister before a spec change:** the expected result *and* the observation that would falsify it. Record the outcome either way, including when it falsifies you.
- **Check dead-defensive first.** Before writing a contract for an edge case, confirm the design or the corpus can actually reach it. Several rulings here turned out to be machinery for cases that do not exist (F20 reissue ranking, F28 pagination cap, the F23 Haiku carve-out).
- **A finding is only as valid as the instrument that produced it.** Do not claim a failure the instrument cannot support — an empty 3-tool trace on a 96-tool surface proves nothing, and a reviewer reading a stale overlay tree reports true things about the slice and false things about the software.
- **Demand observable artifacts** from implementation reports: failing input, before/after *sets* (not counts), traces, corpus scans. Agreement with a summary proves nothing; disagreement is the signal.
- **Durable state lives in files here, never in conversation** — assume compaction. Defect register, preregistrations, open questions, rulings.
- **Commit each ruling as it is made.** The git history of this directory is the decision record; that is worth more than a tidy log.

For the spec's own reasoning conventions — identity over string-matching, assert a non-zero denominator, a scan that errors must not look like one that found nothing, a measurement of a property shares the failure class of its implementation — see `00-INDEX.md` → **"Conventions — these bind"**, and `00-INDEX.md` → **"Settled — do not reopen"** before reopening anything.
