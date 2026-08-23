"""The regression path of tests/check_known_failures.py must print the failing
tests' captured output (F37 incident, 2026-08-23): the comparison pass runs
--tb=no, so without a second pass a CI failure is a one-line test name.

Run with: pytest tests/test_check_known_failures_output.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests"))

import check_known_failures as ckf  # noqa: E402


def _known() -> tuple[set[str], set[str]]:
    return ckf.parse_baseline(ckf.BASELINE_DOC.read_text())


def test_report_returns_the_regressed_targets_only(capsys):
    known = {"tests/a.py::old"}
    live = {"tests/a.py::old", "tests/b.py::new"}
    assert ckf.report("failure", live, known) == ["tests/b.py::new"]
    out = capsys.readouterr().out
    assert "REGRESSION  failure: tests/b.py::new" in out
    # A fixed entry is reported but is not a target to re-run.
    assert ckf.report("failure", set(), known) == []
    assert "NOW PASSING" in capsys.readouterr().out


def test_regression_reruns_the_regressed_targets_with_full_output(monkeypatch, capsys):
    known_f, known_c = _known()
    regressed = "tests/test_bill_text_rendering_tripwire.py::test_rendering_fingerprint_is_pinned_beside_schema_version"
    monkeypatch.setattr(ckf, "run_suite", lambda: (known_f | {regressed}, set(known_c)))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 1,
            stdout="____ test_rendering_fingerprint ____\nE   AssertionError: digest differs\n"
                   "---- Captured stdout call ----\n3.12 -> 3520d3\n",
            stderr="",
        )

    monkeypatch.setattr(ckf.subprocess, "run", fake_run)
    assert ckf.main() == 1
    out = capsys.readouterr().out
    assert "REGRESSION DETAIL" in out
    assert "AssertionError: digest differs" in out and "3.12 -> 3520d3" in out
    # The rerun targets exactly the regressed node id, with full tracebacks.
    assert len(calls) == 1
    cmd = calls[0]
    assert regressed in cmd and "--tb=long" in cmd and "-rA" in cmd
    assert not any(t.endswith("tests/") for t in cmd), "rerun must not be the whole suite"


def test_shrink_only_change_fails_without_a_rerun(monkeypatch, capsys):
    known_f, known_c = _known()
    assert known_f, "baseline must have entries for this test to mean anything"
    fewer = set(sorted(known_f)[1:])
    monkeypatch.setattr(ckf, "run_suite", lambda: (fewer, set(known_c)))
    monkeypatch.setattr(ckf.subprocess, "run",
                        lambda *a, **k: pytest.fail("no rerun on a shrink-only change"))
    assert ckf.main() == 1
    out = capsys.readouterr().out
    assert "NOW PASSING" in out and "REGRESSION DETAIL" not in out


def test_matching_baseline_exits_zero(monkeypatch, capsys):
    known_f, known_c = _known()
    monkeypatch.setattr(ckf, "run_suite", lambda: (set(known_f), set(known_c)))
    assert ckf.main() == 0
    assert "Baseline matches" in capsys.readouterr().out


def test_explain_regressions_really_runs_pytest_on_a_failing_target(tmp_path):
    # End to end on a real failing test file: the captured output and the
    # traceback must come back, because that is the whole point.
    bad = REPO / "tests" / "_tmp_ckf_probe_test.py"
    bad.write_text("def test_boom():\n    print('captured-marker-xyz')\n    assert 1 == 2\n")
    try:
        text = ckf.explain_regressions([f"tests/{bad.name}::test_boom"])
    finally:
        bad.unlink()
    assert "captured-marker-xyz" in text
    assert "assert 1 == 2" in text
