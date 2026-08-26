"""
AGENTS.md and .claude/CLAUDE.md exist so that different tools find the
same conventions under the filename each one looks for. They must stay
byte-identical, or a session that only auto-loads one of them silently
sees different (or missing) rules than a session that auto-loads the
other -- the exact drift issue #46 was filed to fix. See CONTRIBUTING.md
("Keeping AGENTS.md and .claude/CLAUDE.md in sync") for why this is a
plain synced file rather than a symlink.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_agents_md_matches_claude_md():
    agents_md = REPO_ROOT / "AGENTS.md"
    claude_md = REPO_ROOT / ".claude" / "CLAUDE.md"

    agents_text = agents_md.read_text()
    claude_text = claude_md.read_text()

    assert agents_text == claude_text, (
        "AGENTS.md and .claude/CLAUDE.md have drifted apart. Keep them "
        "byte-identical -- copy one over the other -- and see "
        "CONTRIBUTING.md for why both files exist."
    )
