"""F39 standing guard: no secret-shaped string in the tracked tree.

The maintainer's live api.data.gov key was committed as the e2e
harness's "fake" secret fixture, and for this provider a leaked
credential is PERMANENT -- api.data.gov keys cannot be revoked (measured
2026-08-25: a new signup left the old key live), so prevention is the
entire defense. This test scans every tracked text file for
api.data.gov-shaped strings: exactly-40-character alphanumeric tokens
carrying all three character classes (upper, lower, digit -- the shape
of a real key; 40-hex git SHAs have no uppercase and never qualify). A
candidate passes only when it is visibly fake (carries a fake marker) or
sits in the explicit allowlist of measured non-secrets.

Fixture secrets are fake by construction -- the fourth channel
(fulltext/09-safety.md section 11): a fixture that must be key-SHAPED
for its consumer still must not be key-VALUED.
"""
import os
import re
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Exactly 40 alphanumerics, bounded by non-alphanumerics.
_TOKEN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{40}(?![A-Za-z0-9])")

# A visibly-fake token is exempt: the point is key-shaped-but-not-a-key.
_FAKE_MARKERS = ("fake", "test", "example", "dummy", "sample",
                 "placeholder", "xxxx", "redacted")

# Measured non-secrets (content hashes etc.), listed explicitly as
# (relative path, token). Empty today; every addition needs a comment
# saying what the token is and how that was established.
ALLOWLIST: "set[tuple[str, str]]" = set()


def _is_candidate(token: str) -> bool:
    return (any(c.isupper() for c in token)
            and any(c.islower() for c in token)
            and any(c.isdigit() for c in token))


def _is_visibly_fake(token: str) -> bool:
    lowered = token.lower()
    return any(marker in lowered for marker in _FAKE_MARKERS)


def _tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                         capture_output=True, check=True)
    return [name for name in out.stdout.decode().split("\0") if name]


def _scan():
    findings = []
    for rel in _tracked_files():
        path = os.path.join(REPO_ROOT, rel)
        try:
            with open(path, "rb") as handle:
                blob = handle.read()
        except OSError:
            continue
        if b"\0" in blob[:8192]:
            continue  # binary
        text = blob.decode("utf-8", errors="replace")
        for match in _TOKEN.finditer(text):
            token = match.group(0)
            if not _is_candidate(token):
                continue
            if _is_visibly_fake(token):
                continue
            if (rel, token) in ALLOWLIST:
                continue
            findings.append((rel, token[:6] + "..." + token[-4:]))
    return findings


def test_tracked_tree_carries_no_secret_shaped_string():
    findings = _scan()
    assert findings == [], (
        "Secret-shaped string(s) in the tracked tree (40-char "
        "alphanumeric, mixed case + digit, not visibly fake). If one is "
        "a measured non-secret, allowlist it WITH a comment; if it is a "
        "credential, it is already permanently leaked (api.data.gov keys "
        f"cannot be revoked) -- abandon it: {findings}")


def test_guard_is_not_vacuous():
    # The instrument must catch the shape it exists for. Built at
    # runtime so this file never contains a key-shaped literal itself.
    synthetic = ("Zx" + "9aB" * 12 + "Qk")[:40]
    assert len(synthetic) == 40
    assert _TOKEN.search("prefix " + synthetic + " suffix")
    assert _is_candidate(synthetic)
    assert not _is_visibly_fake(synthetic)
    # And the e2e fixture's replacement is caught by the FAKE branch,
    # not by absence: still key-shaped for its consumer.
    fixture = "Fake" * 9 + "0000"
    assert len(fixture) == 40
    assert _is_candidate(fixture)
    assert _is_visibly_fake(fixture)


def test_fixture_shape_survives_in_e2e_harness():
    # The three F39 sites must stay key-shaped (their consumer audits a
    # secret's round-trip) while being visibly fake.
    path = os.path.join(REPO_ROOT, "tests", "test_e2e_harness.py")
    text = open(path, encoding="utf-8").read()
    fixture = "Fake" * 9 + "0000"
    assert text.count(fixture) == 3
