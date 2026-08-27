# Contributing to CongressMCP

This is the canonical source for repo conventions — humans and AI coding agents both read this file. `.claude/CLAUDE.md` and `AGENTS.md` (kept identical to each other; see [Keeping AGENTS.md and .claude/CLAUDE.md in sync](#keeping-agentsmd-and-claudeclaudemd-in-sync)) defer to it for anything not restated there; if you find a conflict between this file and one of those, this file wins. The commit-trailer rule and the `documentation/` write restriction below are also stated inline in `.claude/CLAUDE.md` / `AGENTS.md`, on purpose: those two are operative constraints an agent must see even if it only ever auto-loads its own CLAUDE.md/AGENTS.md and never opens this file.

Markdown in this repo is not hard-wrapped: one line per paragraph, long lines are fine. It keeps a one-word edit to a one-line diff instead of a reflow cascade. Structural content (tables, fenced code, headings) is exempt from that and formatted normally.

## Development

```bash
uv run ruff check .                                          # lint
uv run python -m pytest tests/ --continue-on-collection-errors  # tests
python tests/check_known_failures.py                         # the actual CI gate
```

`ruff check` and the plain `pytest tests/` currently do not pass clean on `master` — see `tests/KNOWN_FAILURES.md`. `check_known_failures.py` is what CI actually runs (`.github/workflows/test.yml`): it fails if the set of failing tests grows (a regression) *or* shrinks (something was fixed but `KNOWN_FAILURES.md` wasn't updated to match) — a one-way ratchet would rot back into the problem it exists to solve. If you fix a pre-existing failure, update `KNOWN_FAILURES.md` in the same PR; if you're unsure whether a failure is pre-existing, check whether it reproduces on a clean `master` checkout.

## Code style

PEP 8-compliant Python. Line length: ruff enforces 120 columns (`pyproject.toml`), which is the hard limit; wrapping earlier, around ~80 columns, is a soft preference for new code where it doesn't hurt readability, not a rule worth reflowing existing lines to satisfy. Markdown follows the one-line-per-paragraph convention above instead of a column target.

## Commit conventions

Commit each logical unit of work as you go, rather than batching unrelated changes into one commit — prefer several small, clear commits over one large one. Wrap commit message bodies at ~80 columns (commit messages are the one place in this repo that *does* get a column wrap, since they're read as fixed-width text by `git log`, not edited later).

**AI-assisted commits get a trailer.** If a commit was authored or materially assisted by an AI coding agent, add a trailer at the end of the message identifying the model, using that model's own vendor no-reply address (or equivalent identifier) if it isn't a Claude model:

```
Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

Git and GitHub both parse this trailer case-insensitively, and GitHub's own squash-merge button emits `Co-authored-by:` (lowercase) regardless of what the source commits used — don't hand-fix casing on squash-merged history. For commits you write directly, prefer the `Co-Authored-By:` casing above to match the majority of this repo's existing trailers.

This applies to work on this repository specifically — a contributor's own private/global tooling config (e.g. a personal `CLAUDE.md` outside this repo) does not override it for commits that land here.

## The two-session model for `documentation/`

Bill-text spec work is split across two kinds of session, and this split is an active, ongoing convention rather than a one-off from a past PR:

- **Spec session**: owns all of `documentation/`, and may not write anywhere else in the repo. It must not read implementation source — its job is to specify, not to describe what was built.
- **Implementation session**: owns everything outside `documentation/`. It must not write into `documentation/` — that stays the spec session's exclusive domain, full stop, not just for bill-text work — and it must write unit tests for everything it builds, keeping the applicable suite green.

Active spec work is currently concentrated in `documentation/fulltext/` (the bill-text spec), which has its own detailed rules — formatting, question routing, preregistration, etc. — in `documentation/CLAUDE.md`. Read that file before writing there. The write restriction above still covers all of `documentation/`, not just `fulltext/`.

## Keeping AGENTS.md and .claude/CLAUDE.md in sync

Different tools look for different filenames — Claude Code reads `.claude/CLAUDE.md`, most other agent CLIs read `AGENTS.md` — so this repo keeps two copies of the same content rather than picking one tool to favor. A symlink would collapse them to one file to maintain, but Git for Windows doesn't enable symlinks by default, which would turn `AGENTS.md` into a one-line text file containing a path instead of any actual conventions on a plain Windows clone — worse than the duplication it would "fix." Instead, `tests/test_conventions_sync.py` asserts the two files are byte-identical, so drift between them fails the test suite instead of silently persisting. If you edit one, edit both, or let the test catch it.

## Pull requests

1. Fork the repository.
2. Create a feature branch.
3. Follow the conventions above.
4. Submit a pull request against `master`.
