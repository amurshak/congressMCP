# Contributing to CongressMCP

This is the canonical source for repo conventions — humans and AI coding
agents both read this file. `.claude/CLAUDE.md` and `AGENTS.md` defer to
it rather than restating it; if you find a conflict, this file wins.

## Code style

- PEP 8-compliant Python.
- Wrap Python source at ~80 columns where reasonably possible.
- Markdown is exempt from the 80-column wrap: long lines are permitted
  and preferred there (they keep diffs to one line per edit).

## Commit conventions

- Commit each logical unit of work as you go, rather than batching
  unrelated changes into one commit. Prefer several small, clear
  commits over one large one.
- Wrap commit message bodies at ~80 columns.
- **AI-assisted commits get a trailer.** If a commit was authored or
  materially assisted by an AI coding agent (Claude Code or otherwise),
  add a trailer at the end of the message identifying the model:

  ```
  Co-Authored-By: <Model Name> <noreply@anthropic.com>
  ```

  This repo's history settles the "sign or don't sign" question:
  `Co-Authored-By:` (this exact casing) is the convention actually in
  use across the great majority of commits, so it's the one documented
  here. It applies to work on this repository specifically — a
  contributor's own private/global tooling config (e.g. a personal
  `CLAUDE.md` outside this repo) does not override it for commits that
  land here.

## The two-session model for `documentation/fulltext/`

Bill-text spec work (`documentation/fulltext/`) is split across two
kinds of session, and this split is an active convention, not a
one-off from a past PR:

- **Spec session**: owns `documentation/`. It may not write outside
  that directory, and must not read implementation source — its job is
  to specify, not to describe what was built. Its own detailed rules
  (formatting, routing questions, preregistration, etc.) live in
  `documentation/CLAUDE.md` and bind only within that scope.
- **Implementation session**: owns everything outside `documentation/`.
  It must not write into `documentation/` — that stays the spec
  session's exclusive domain — and it must write unit tests for
  everything it builds, keeping the applicable suite green.

If you're picking up bill-text spec or implementation work, read the
scoped rules in `documentation/CLAUDE.md` before writing there. Outside
of bill-text work, this split doesn't apply — most of the repo has no
spec/implementation session distinction.

## Pull requests

1. Fork the repository.
2. Create a feature branch.
3. Follow the commit conventions above.
4. Submit a pull request.
