# What this is

This is an MCP server for searching congressional bills. It uses BOTH the congress.gov and govinfo.gov APIs to do this. 

# Conventions

- PEP-8 complaint Python
- Wrap at ~80 characters where possible, excpept for in Markdown, where long lines are permitted and desiralble.

# Two sessions

There are two sessions, one for spec maintenacne and one for implementation,. The spec session MUST NOT write outside of documentation/ and MUST NOT read the implementation code. The point of that session is to specify, not describe what was built. There are further instructions in documentation/CLAUDE.md for that session. The implementation session should ignore those.

The implementation session MUST NOT write into documentation/ - that is the exclusive domain of the spec session.

The implementation session should write unit tests for everything that is built, and make sure that all applicable unit tests pass on the code that was written.

# Commit conventions

- Make sure to commit each turn as you go, as you have something comppleted. If it can be reasonably be split into two or more commits per turn, do that. Clear history is perferred to a clean git log.
- Wrap commit messages at ~80 columns 
- Insert a Co-authored by: <model name> at the end of every commit message.