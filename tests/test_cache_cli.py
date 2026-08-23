"""The `congressmcp cache` CLI (spec §10).

Two contracts:

* The CLI re-declares NO layout literal -- cache dir and platform defaults,
  packages/ glob, cap env var, schema version all come from
  congress_api.features.bill_text.cache (the PR1->PR2 forward constraint).
* Exit codes, on BOTH entry points (console script and `python -m`): a
  `cache clear` refused for want of --yes in a non-interactive context exits 1;
  a completed `cache clear` and any `cache info` exit 0.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from congress_api import __main__ as entry
from congress_api.features.bill_text import cache

REPO = Path(__file__).resolve().parent.parent


def _run_module(args, env):
    return subprocess.run(
        [sys.executable, "-m", "congress_api", *args],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        stdin=subprocess.DEVNULL,
    )


def _console_script() -> str | None:
    # The console script generated from [project.scripts], if this interpreter's
    # environment installed it. Same bin dir as the interpreter.
    candidate = Path(sys.executable).with_name("congressmcp")
    if candidate.exists():
        return str(candidate)
    return shutil.which("congressmcp")


def _run_console(args, env):
    script = _console_script()
    if script is None:
        pytest.skip("congressmcp console script not installed in this environment")
    return subprocess.run(
        [script, *args],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=env,
        stdin=subprocess.DEVNULL,
    )


@pytest.fixture
def cache_env(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "CONGRESS_API_KEY"}
    env[cache.ENV_CACHE_DIR] = str(tmp_path / "cache")
    env[cache.ENV_CACHE_MAX_BYTES] = "4096"
    return env


def _populate(root: Path) -> cache.CacheLayout:
    layout = cache.CacheLayout(root)
    layout.ensure_dirs()
    (layout.packages_dir / cache.package_filename("BILLS-119s1071enr")).write_bytes(b"x" * 10)
    (layout.packages_dir / cache.package_filename("BILLS-118hr1ih", cache.SCHEMA_VERSION - 1)).write_bytes(b"x" * 20)
    (layout.packages_dir / ".BILLS-119s1071enr.0123abcd.tmp").write_bytes(b"x" * 5)
    with cache.Manifest(layout.manifest_path):
        pass
    return layout


# ---------------------------------------------------------------------------
# Ownership: the CLI holds no layout literals of its own
# ---------------------------------------------------------------------------


def test_main_module_declares_no_layout_literals():
    src = Path(entry.__file__).read_text()
    for literal in (
        "524288000",
        "CONGRESSMCP_CACHE_MAX_BYTES",
        "CONGRESSMCP_CACHE_DIR",
        "Library",
        "Caches",
        "LOCALAPPDATA",
        "XDG_CACHE_HOME",
        '"packages"',
        "*.db",
        "in-memory-pr1",
        "platform.system",
    ):
        assert literal not in src, f"__main__.py re-declares cache layout literal {literal!r}"
    assert not hasattr(entry, "_cache_dir"), "the cache dir resolver belongs to the cache module"
    # The source comment must not drift against the §10 contract (#13).
    assert "exits 2" not in src


def test_info_reads_path_cap_and_schema_version_from_the_cache_module(tmp_path, cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "info"])
    assert entry.main() == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert f"path: {layout.root}" in lines
    assert f"manifest: {layout.manifest_path}" in lines
    assert f"schema_version: {cache.SCHEMA_VERSION}" in lines
    assert "cap_bytes: 4096" in lines
    assert "total_bytes: 30" in lines
    assert "enabled: true" in lines
    assert "in_progress_builds: 1" in lines
    assert f"  - {cache.package_filename('BILLS-119s1071enr')}\t10\tcurrent" in lines
    assert f"  - {cache.package_filename('BILLS-118hr1ih', cache.SCHEMA_VERSION - 1)}\t20\tstale" in lines


def test_info_on_empty_cache(tmp_path, cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "info"])
    assert entry.main() == 0
    out = capsys.readouterr().out
    assert "packages: []" in out
    assert "total_bytes: 0" in out
    # info never creates the cache directory.
    assert not Path(cache_env[cache.ENV_CACHE_DIR]).exists()


def test_info_follows_the_platform_default_when_unset(monkeypatch, capsys):
    monkeypatch.delenv(cache.ENV_CACHE_DIR, raising=False)
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "info"])
    assert entry.main() == 0
    out = capsys.readouterr().out
    assert f"path: {cache.default_cache_dir()}" in out.splitlines()


# ---------------------------------------------------------------------------
# Exit-code contract, in-process
# ---------------------------------------------------------------------------


def test_clear_without_yes_non_interactive_refuses_with_1_and_removes_nothing(cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))
    before = sorted(p.name for p in layout.packages_dir.iterdir())
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))  # not a tty
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "clear"])
    assert entry.main() == 1
    err = capsys.readouterr().err
    assert "--yes" in err
    assert sorted(p.name for p in layout.packages_dir.iterdir()) == before
    assert layout.manifest_path.exists()


def test_clear_with_yes_removes_everything_and_exits_0(cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "clear", "--yes"])
    assert entry.main() == 0
    out = capsys.readouterr().out.splitlines()
    assert "removed_packages: 2" in out
    assert "removed_in_progress_builds: 1" in out
    assert "removed_manifest: true" in out
    assert list(layout.packages_dir.iterdir()) == []
    assert layout.manifest_sidecars() == []


def test_clear_interactive_prompt_yes_and_no(cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))

    class Tty(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Tty())
    monkeypatch.setattr(sys, "stdout", Tty())
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache", "clear"])

    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert entry.main() == 1
    assert layout.manifest_path.exists()

    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    assert entry.main() == 0
    assert list(layout.packages_dir.iterdir()) == []


def test_cache_without_subcommand_is_a_usage_error(cache_env, capsys, monkeypatch):
    for key, value in cache_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["congressmcp", "cache"])
    assert entry.main() == 2


# ---------------------------------------------------------------------------
# Exit-code contract, both real entry points in fresh processes
# ---------------------------------------------------------------------------


def test_module_entry_point_exit_codes(cache_env):
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))

    info = _run_module(["cache", "info"], cache_env)
    assert info.returncode == 0, info.stderr
    assert f"schema_version: {cache.SCHEMA_VERSION}" in info.stdout
    assert f"path: {layout.root}" in info.stdout
    # Not a server boot: no credential warning leaks into the CLI.
    assert "CONGRESS_API_KEY" not in info.stderr

    refused = _run_module(["cache", "clear"], cache_env)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert layout.manifest_path.exists()

    cleared = _run_module(["cache", "clear", "--yes"], cache_env)
    assert cleared.returncode == 0, cleared.stderr
    assert list(layout.packages_dir.iterdir()) == []


def test_console_script_entry_point_exit_codes(cache_env):
    layout = _populate(Path(cache_env[cache.ENV_CACHE_DIR]))

    info = _run_console(["cache", "info"], cache_env)
    assert info.returncode == 0, info.stderr
    assert f"schema_version: {cache.SCHEMA_VERSION}" in info.stdout

    refused = _run_console(["cache", "clear"], cache_env)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert layout.manifest_path.exists()

    cleared = _run_console(["cache", "clear", "--yes"], cache_env)
    assert cleared.returncode == 0, cleared.stderr
    assert list(layout.packages_dir.iterdir()) == []
