# What this is

This is an MCP server for searching congressional bills. It uses BOTH the congress.gov and govinfo.gov APIs to do this.

The primary target for this server is individual user desktop use via stdio. The rate limits for the upstream APIs are: congress.gov: 20,000/hr, govinfo.gov: 36,000/hr. These are independent rate limits for two hosts, even though they share the same key. The practical implication of this is that API calls are essentially free - no individual user is going to exhaust them.

# Conventions

- PEP-8 compliant Python
- Minimum supported Python for this repo is 3.10, all code must run there. If the maintainer has a newer version, that is fine - but run all tests in both the maintainer's venv and a 3.10 venv.
- The maintainer's venv is at `~/congress-mcp-venv`. Do NOT use the repo's `.venv` - it is stale.
- Wrap at ~80 characters where possible, except for in Markdown, where long lines are permitted and desirable.

# Two sessions

There are two sessions, one for spec maintenance and one for implementation. The spec session MUST NOT write outside of documentation/ and MUST NOT read the implementation code. The point of that session is to specify, not describe what was built. There are further instructions in documentation/CLAUDE.md for that session. The implementation session should ignore those.

The implementation session MUST NOT write into documentation/ - that is the exclusive domain of the spec session.

The implementation session should write unit tests for everything that is built, and make sure that all applicable unit tests pass on the code that was written.

The e2e harness (run_suite.py) is run by the maintainer, not by agents. Stop at code + unit tests + commit; do not launch e2e runs.

# Commit conventions

- Make sure to commit each turn as you go, as you have something completed. If it can reasonably be split into two or more commits per turn, do that. Granular history during development is preferred over a tidy squashed log.
- However, when preparing to ship, we're going to prepare a new branch, rename the one with history to `archive/<branch-name>`, and squash the commits. The goal is to ship one commit to the upstream maintainer, with a commit message that doubles as the PR description.
- Wrap commit messages at ~80 columns
- End every commit message with a trailer in this exact format: `Co-authored-by: Claude Fable 5 <noreply@anthropic.com>` (substituting the actual model name and its noreply address)
