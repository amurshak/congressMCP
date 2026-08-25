# What this is

This is an MCP server for searching congressional bills. It uses BOTH the congress.gov and govinfo.gov APIs to do this. 

# Conventions

See `CONTRIBUTING.md` at the repo root for code style, commit
conventions (including the commit trailer format), and the two-session
model below — this file defers to it and does not restate it.

# Two sessions

There are two sessions, one for spec maintenance and one for
implementation. The spec session MUST NOT write outside of
documentation/ and MUST NOT read the implementation code. The point of
that session is to specify, not describe what was built. There are
further instructions in documentation/CLAUDE.md for that session. The
implementation session should ignore those.

The implementation session MUST NOT write into documentation/ - that is
the exclusive domain of the spec session.

The implementation session should write unit tests for everything that
is built, and make sure that all applicable unit tests pass on the code
that was written.
