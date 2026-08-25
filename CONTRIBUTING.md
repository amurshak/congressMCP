# Contributing to CongressMCP

This is the canonical source for repo conventions — humans and AI coding
agents both read this file. `.claude/CLAUDE.md` and `AGENTS.md` defer to
it for anything not restated there; if you find a conflict between this
file and one of those, this file wins. The commit-trailer rule and the
`documentation/` write restriction below are also stated inline in
`.claude/CLAUDE.md` / `AGENTS.md`, on purpose: those two are operative
constraints an agent must see even if it only ever auto-loads its own
CLAUDE.md/AGENTS.md and never opens this file.

## Development

```bash
uv run ruff check .                  # lint
uv run python -m pytest tests/ -v    # tests
```

Both must pass (or fail only on pre-existing, unrelated issues you note
in your PR) before requesting review.

## Code style

- PEP 8-compliant Python.
- Line length: ruff enforces 120 columns (`pyproject.toml`); that's the
  hard limit. Wrapping earlier, around ~80 columns, is a soft
  preference for new code where it doesn't hurt readability — not a
  rule worth reflowing existing lines to satisfy.
- Markdown is exempt from any wrap target: long lines are permitted and
  preferred there (they keep diffs to one line per edit).

## Commit conventions

- Commit each logical unit of work as you go, rather than batching
  unrelated changes into one commit. Prefer several small, clear
  commits over one large one.
- Wrap commit message bodies at ~80 columns.
- **AI-assisted commits get a trailer.** If a commit was authored or
  materially assisted by an AI coding agent, add a trailer at the end
  of the message identifying the model:

  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  ```

  Use the model that actually did the work in place of "Claude Sonnet
  5"; use that model's own vendor no-reply address (or equivalent
  identifier) in place of `noreply@anthropic.com` if it isn't a Claude
  model. Git and GitHub both parse this trailer case-insensitively, and
  GitHub's own squash-merge button emits `Co-authored-by:` (lowercase)
  regardless of what the source commits used — so don't hand-fix
  casing on squash-merged history. For commits you write directly,
  prefer the `Co-Authored-By:` casing above to match the majority of
  this repo's existing trailers.

  This applies to work on this repository specifically — a
  contributor's own private/global tooling config (e.g. a personal
  `CLAUDE.md` outside this repo) does not override it for commits that
  land here.

## The two-session model for `documentation/`

Bill-text spec work is split across two kinds of session, and this
split is an active convention, not a one-off from a past PR (most
recently exercised by PR #63, the persistent bill-text cache):

- **Spec session**: owns all of `documentation/`, and may not write
  anywhere else in the repo. It must not read implementation source —
  its job is to specify, not to describe what was built.
- **Implementation session**: owns everything outside `documentation/`.
  It must not write into `documentation/` — that stays the spec
  session's exclusive domain, full stop, not just for bill-text work —
  and it must write unit tests for everything it builds, keeping the
  applicable suite green.

Active spec work is currently concentrated in `documentation/fulltext/`
(the bill-text spec), which has its own detailed rules — formatting,
question routing, preregistration, etc. — in `documentation/CLAUDE.md`.
Read that file before writing there. The write restriction above still
covers all of `documentation/`, not just `fulltext/`.

## Pull requests

1. Fork the repository.
2. Create a feature branch.
3. Follow the conventions above.
4. Submit a pull request — see the [README](README.md#contributing).
