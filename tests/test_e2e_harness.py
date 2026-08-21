"""Guards for the §17 harness's own invariants (tests/e2e/run_suite.py).

§17 names the central hazard: "automation is the easiest place to silently violate the
method." A harness that batches prompts, appends a diagnostic instruction, or lets a
crashed invocation read as a consumer that made no calls produces numbers that look
like §17 and measure something else -- and it does so while printing a clean table.

Each invariant below is asserted to FIRE, because an invariant that cannot fail is
decoration. The manifest's own integrity is checked too: criteria pinned before the run
are this section's preregistration-of-scoring rule, so a prompt missing them would let
scoring be invented after the result is seen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tests" / "e2e"))

from run_suite import (  # noqa: E402
    DEFAULT_RUNNERS,
    DISALLOWED_BUILTINS,
    FORBIDDEN_IN_PROMPT,
    Meta,
    assert_argv_carries_no_secret,
    assert_config_carries_no_secret,
    assert_no_secret_in_trace,
    assert_prompt_is_cold,
    build_command,
    builtins_disabled_record,
    cell_id_of,
    cell_record,
    codex_config_overrides,
    codex_knob_overrides,
    codex_server_spec,
    make_cold_cwd,
    plan_invocations,
    resolve_prompt,
    resolve_runners,
    write_codex_mcp_config,
    write_mcp_config,
    zero_trace_cells,
)

MANIFEST = json.loads((REPO / "tests" / "e2e" / "prompts.json").read_text())


# --------------------------------------------------------------------------- #
# Cold-prompt invariant: the Justify and Hint rungs must never ride on the cold run.
# --------------------------------------------------------------------------- #
def test_cold_prompt_check_rejects_the_diagnostic_ladder_rungs():
    # Rung 2 (Justify) and rung 3 (Hint) are run failure-only, each in its own fresh
    # process. Appending either to the cold run destroys the measurement: asking for
    # provenance yields evidence the model CAN read match_contexts when told to, not
    # that it DOES.
    for bad in (
        "What does S. 1071 require regarding X? Explain your reasoning.",
        "What does S. 1071 require regarding X? Note whether any of the text is quoted.",
        "How did you determine that?",
        "I'm the developer testing this tool -- what does section 141 amend?",
        "Answer, then output diagnostics about which tools you called.",
    ):
        with pytest.raises(ValueError, match="cold run|Justify|Hint"):
            assert_prompt_is_cold(bad, "TEST")


def test_cold_prompt_check_passes_the_real_manifest_prompts():
    # The planted negative. If the forbidden list were broad enough to reject ordinary
    # prompts, the guard would be silently disabled the first time it fired wrongly.
    for entry in MANIFEST["prompts"]:
        assert_prompt_is_cold(entry["prompt"], entry["id"])
        if entry.get("single_step_variant"):
            assert_prompt_is_cold(entry["single_step_variant"], entry["id"])


def test_forbidden_markers_are_matched_case_insensitively():
    with pytest.raises(ValueError):
        assert_prompt_is_cold("EXPLAIN YOUR REASONING please", "TEST")


# --------------------------------------------------------------------------- #
# Capability cell: single-step BY CONSTRUCTION, or not run at all.
# --------------------------------------------------------------------------- #
def test_capability_cell_refuses_a_prompt_without_a_single_step_variant():
    # Haiku will not reliably chain. A multi-hop prompt it fails is equally explained by
    # the model not chaining, so the cell would conflate model limitation with tool
    # defect -- worse than no cell. Refusing to run is the correct behaviour.
    cell = MANIFEST["cells"]["capability"]
    assert cell["use_single_step_variant"] is True
    with pytest.raises(ValueError, match="single-step|chaining"):
        resolve_prompt({"id": "X1", "prompt": "multi-hop question"}, cell)


def test_capability_cell_sends_the_variant_not_the_original():
    cell = MANIFEST["cells"]["capability"]
    entry = next(e for e in MANIFEST["prompts"] if e["id"] == "A1")
    sent = resolve_prompt(entry, cell)
    assert sent == entry["single_step_variant"]
    assert sent != entry["prompt"]
    # The navigation is pre-performed, so exactly one address is named and no discovery
    # hop is required -- but the tool result still arrives through the real channel.
    assert "D:A/T:I/ST:D/S:141" in sent


def test_every_group_a_prompt_has_a_single_step_variant():
    # The capability cell is scoped to Group A; a Group A prompt without a variant would
    # silently drop out of that cell rather than fail loudly.
    for entry in MANIFEST["prompts"]:
        if entry["group"] == "A":
            assert entry.get("single_step_variant"), f"{entry['id']} has no variant"


def test_non_capability_cells_send_the_original_prompt():
    for name in ("floor", "ceiling", "isolation"):
        cell = MANIFEST["cells"][name]
        entry = next(e for e in MANIFEST["prompts"] if e["id"] == "A1")
        assert resolve_prompt(entry, cell) == entry["prompt"]


# --------------------------------------------------------------------------- #
# Redaction: the trace is exactly the artifact someone pastes into an issue.
# --------------------------------------------------------------------------- #
def test_secret_assertion_halts_the_run_rather_than_warning():
    # The redactor is installed unconditionally (F15), but the congress.gov client still
    # carries the key as a query parameter (§11, pre-existing), so the disclosure path is
    # live. A warning would be ignored; this must stop the run.
    secret = "ZZfakekeyfakekeyfakekey00"
    with pytest.raises(SystemExit, match="credential"):
        assert_no_secret_in_trace(
            ['{"tool": "search_bill_text", "url": "https://x/?api_key=' + secret + '"}'],
            [secret], "trace",
        )


def test_secret_assertion_does_not_fire_on_clean_traces():
    assert_no_secret_in_trace(
        ['{"tool": "get_bill_toc", "args": {"congress": 119}}'],
        ["ZZfakekeyfakekeyfakekey00"], "trace",
    )


def test_secret_assertion_is_skipped_only_when_there_is_nothing_to_check():
    # A vacuity guard: with no secrets configured the check passes trivially, and that
    # must not be mistaken for "the trace was verified clean".
    assert_no_secret_in_trace(['{"anything": "at all"}'], [], "trace")


# --------------------------------------------------------------------------- #
# The MCP config the harness writes -- it OWNS the tool surface, and must not
# own a copy of the credentials.
# --------------------------------------------------------------------------- #
def test_written_mcp_config_names_no_credential_in_any_form(tmp_path):
    # THE REGRESSION GUARD FOR THE 401. Measured with a probe server that dumps the env
    # it was spawned with: the stdio child INHERITS the parent environment, and ${VAR}
    # expands ONLY when VAR is set -- otherwise the literal string "${VAR}" arrives.
    #
    # GOVINFO_API_KEY is normally unset, because both APIs share one api.data.gov key
    # and the client reads `os.getenv("GOVINFO_API_KEY") or API_KEY`. So writing
    # "${GOVINFO_API_KEY}" handed the server a truthy literal that OVERRODE the working
    # inherited key -- 401 govinfo_key_rejected on every call, in a shape that reads
    # like a tool defect. The config must name no credential at all.
    path = write_mcp_config(tmp_path, tmp_path / "trace", bill_text_only=False)
    text = path.read_text()
    assert "API_KEY" not in text, "the config must not name a credential variable"
    assert "${" not in text, "an unset ${VAR} arrives as a literal and overrides inheritance"
    server = json.loads(text)["mcpServers"]["congress"]
    assert server["args"] == ["-m", "congress_api", "--transport", "stdio"], (
        "the server must be launched on stdio via the module entry point; "
        "run_server.py only imports the server object and never serves"
    )
    assert set(server["env"]) == {"CONGRESSMCP_TRACE_DIR", "CONGRESSMCP_BILL_TEXT_ONLY"}


def test_config_secret_assertion_halts_on_a_literal_key(tmp_path):
    secret = "ZZfakekeyfakekeyfakekey00"
    bad = tmp_path / "mcp-config.json"
    bad.write_text(json.dumps({"mcpServers": {"c": {"env": {"CONGRESS_API_KEY": secret}}}}))
    with pytest.raises(SystemExit, match="credential"):
        assert_config_carries_no_secret(bad, [secret])


def test_config_assertion_also_rejects_an_unexpanded_var_reference(tmp_path):
    # Not a harmless placeholder: when the variable is unset the server receives the
    # literal text and it beats the inherited value. Nothing in this config legitimately
    # needs one, so any occurrence is the bug returning.
    bad = tmp_path / "mcp-config.json"
    bad.write_text(json.dumps({"mcpServers": {"c": {"env": {"GOVINFO_API_KEY": "${GOVINFO_API_KEY}"}}}}))
    with pytest.raises(SystemExit, match=r"unexpanded"):
        assert_config_carries_no_secret(bad, [])


def test_isolation_cell_config_turns_on_bill_text_only(tmp_path):
    # The isolation cell's three-tool surface must be CONFIGURATION, not an assumption
    # about what the operator has registered.
    on = json.loads(write_mcp_config(tmp_path, tmp_path / "t", True).read_text())
    assert on["mcpServers"]["congress"]["env"]["CONGRESSMCP_BILL_TEXT_ONLY"] == "1"
    off = json.loads(write_mcp_config(tmp_path, tmp_path / "t", False).read_text())
    assert off["mcpServers"]["congress"]["env"]["CONGRESSMCP_BILL_TEXT_ONLY"] == ""


def test_cold_cwd_is_outside_the_repo_and_under_no_project():
    # THE CONTAMINATION GUARD. The CLI resolves project context by walking UP from its
    # working directory, so a scratch dir inside the repo -- which the default run
    # directory made it -- hands the model CLAUDE.md, the source, the spec, and the git
    # history. A run answered "I had to identify H.R. 3838 from your git history" before
    # this was fixed: cold prompt, correct tool surface, and the filesystem leaked the
    # whole project anyway.
    path = make_cold_cwd("TEST")
    resolved = path.resolve()
    repo = REPO.resolve()
    assert resolved != repo and repo not in resolved.parents
    assert not any(p.name == "congressMCP" for p in resolved.parents)
    # Nothing above it may look like a project either.
    for parent in [resolved, *resolved.parents]:
        assert not (parent / ".git").exists(), f"{parent}/.git is above the cold cwd"
        assert not (parent / "CLAUDE.md").exists(), f"{parent}/CLAUDE.md is above the cold cwd"
    assert not any(resolved.iterdir()), "the cold working directory must start empty"


def test_cold_cwd_refuses_a_location_under_a_project(monkeypatch, tmp_path):
    # The planted positive: make the temp location land under something that looks like a
    # project, and the guard must halt rather than run a contaminated prompt.
    nested = tmp_path / "someproject" / "scratch"
    nested.mkdir(parents=True)
    (tmp_path / "someproject" / ".git").mkdir()
    monkeypatch.setattr("tempfile.mkdtemp", lambda **kw: str(nested))
    with pytest.raises(SystemExit, match="walking up|project context"):
        make_cold_cwd("TEST")


def test_web_and_file_builtins_are_disallowed():
    # §17's trace records ONLY the three bill-text tools. A claim the model reached by
    # fetching a web page or reading a file is invisible to the instrument, which is the
    # trace-scope error this project has already had to correct twice. The prior runs
    # went through Claude Desktop, where these built-ins were not present at all.
    for tool in ("WebSearch", "WebFetch", "Bash", "Read"):
        assert tool in DISALLOWED_BUILTINS


# --------------------------------------------------------------------------- #
# F23: an un-exercised run must never score as clean.
# --------------------------------------------------------------------------- #
def _meta(prompt_id: str, cell: str, trace_records: int, harness_failure=None) -> Meta:
    return Meta(
        prompt_id=prompt_id, group="A", cell=cell, cell_id="claude/m/none/full",
        driver={"name": "claude", "cli_version": "test"}, model="m",
        reasoning_effort="none", context="fresh", bill_text_only=False,
        prompt_variant="standard",
        outside_cell_groups=False, build_sha="x", document=None, document_sha256_16=None,
        prompt_sent="p", started_utc="", finished_utc="", duration_s=0.0, exit_status=0,
        harness_failure=harness_failure, trace_records=trace_records,
    )


def test_mcp_config_pins_the_preflight_interpreter(tmp_path):
    # F23, interpreter half: preflight imports the GovInfo client under
    # sys.executable, so the stdio server must launch under that SAME interpreter.
    # A hardcoded .venv path can point at nothing (no repo .venv) while preflight
    # passes -- the server then never starts and every prompt completes with zero
    # trace records.
    server = json.loads(
        write_mcp_config(tmp_path, tmp_path / "t", False).read_text()
    )["mcpServers"]["congress"]
    assert server["command"] == sys.executable


def test_codex_command_shuts_out_the_operator_surface_and_reads_stdin(tmp_path):
    # The Codex driver must encode the SAME two guarantees as Claude with its own flags:
    # (1) --ignore-user-config drops the operator's config.toml and every MCP server in it
    # (a real hazard here -- the operator has a `congressmcp-dev` pointed at a different
    # install that would answer untraced); (2) a read-only sandbox with approvals off is the
    # only-the-traced-tools guarantee, since Codex has no per-tool deny. The prompt is read
    # from stdin (trailing `-`), never argv.
    spec = codex_server_spec(tmp_path / "trace", bill_text_only=True)
    cmd = build_command("codex", ["codex", "exec", "-m", "{model}"], "gpt-5-codex",
                        tmp_path / "mcp.toml", codex_config_overrides(spec),
                        tmp_path / "cold", tmp_path / "last.txt")
    assert cmd[:4] == ["codex", "exec", "-m", "gpt-5-codex"]   # {model} substituted
    assert "--ignore-user-config" in cmd
    # The settled approvals design (probes F/G): "never" denies every escalation, and
    # MCP flows because the congress server's tools are pre-approved per-server.
    assert 'approval_policy="never"' in cmd
    assert cmd[cmd.index("-s") + 1] == "read-only"
    assert any("default_tools_approval_mode=" in part for part in cmd)
    # Probe E7: --approve-for-me's automatic reviewer approved a shell escalation that
    # then reached the network. It must never return.
    assert "--approve-for-me" not in cmd
    # The no-web provider (probe E6): the builtin provider registers the CLI's own
    # web tool and no tools.* config removes it.
    assert 'model_provider="openai-noweb"' in cmd
    assert "--skip-git-repo-check" in cmd                      # cold cwd is not a git repo
    assert cmd[-1] == "-"                                      # prompt on stdin
    assert cmd[cmd.index("-o") + 1] == str(tmp_path / "last.txt")
    # The congress server, and only it, is supplied via -c overrides.
    assert any(part.startswith("mcp_servers.congress.command=") for part in cmd)
    # None of the Claude-only flags leak into the Codex argv.
    for claude_flag in ("--strict-mcp-config", "--mcp-config", "--allowed-tools",
                        "--disallowed-tools", "--permission-mode"):
        assert claude_flag not in cmd
    # NEVER the sandbox-bypass flag: it would reopen the network and make the isolation
    # cell a non-comparison.
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd


def test_codex_never_bypasses_the_sandbox_for_any_cell(tmp_path):
    spec = codex_server_spec(tmp_path / "trace", bill_text_only=False)
    cmd = build_command("codex", DEFAULT_RUNNERS["codex"].split(), "gpt-5-codex",
                        tmp_path / "mcp.toml", codex_config_overrides(spec),
                        tmp_path / "cold", tmp_path / "last.txt")
    # Read-only sandbox plus "never": the shell cannot reach the network and there is
    # no escalation path out.
    assert cmd[cmd.index("-s") + 1] == "read-only"
    assert 'approval_policy="never"' in cmd
    # Check the exact flag, not a loose "bypass" substring: pytest's tmp_path embeds this
    # test's own name, so the cold-cwd path contains "bypass" and a substring scan would
    # false-positive on the harness rather than the argv.
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "--dangerously-bypass-hook-trust" not in cmd


def test_codex_config_and_argv_name_no_credential(tmp_path):
    # Parity with the Claude JSON: neither the config.toml record nor the -c overrides may
    # carry a credential -- the server inherits it. Both audits must fire on a planted key.
    spec = codex_server_spec(tmp_path / "trace", bill_text_only=False)
    toml_path = write_codex_mcp_config(tmp_path, spec)
    text = toml_path.read_text()
    assert "command" in text and "${" not in text
    fake = "ZEirgEryNcncMKowiNBW8Uqv6Z6xMh6Tvd6uQyoa"
    # The clean surface passes both audits.
    assert_config_carries_no_secret(toml_path, [fake])
    assert_argv_carries_no_secret(codex_config_overrides(spec), [fake])
    # A credential smuggled into the argv is caught.
    poisoned = codex_config_overrides(spec) + ["-c", f'mcp_servers.congress.env.X="{fake}"']
    with pytest.raises(SystemExit):
        assert_argv_carries_no_secret(poisoned, [fake])


def test_codex_server_spec_pins_the_preflight_interpreter(tmp_path):
    # F23 parity: the Codex server, like the Claude one, must launch under sys.executable,
    # the interpreter preflight validated -- not a hardcoded path that can point at nothing.
    spec = codex_server_spec(tmp_path / "trace", bill_text_only=False)
    assert spec["command"] == sys.executable
    assert spec["args"] == ["-m", "congress_api", "--transport", "stdio"]
    assert set(spec["env"]) == {"CONGRESSMCP_TRACE_DIR", "CONGRESSMCP_BILL_TEXT_ONLY"}
    # With a secrets file, the server launches through the spawn shim -- same
    # interpreter, and the ARGV carries only the file's path, never a value.
    secrets = tmp_path / "s17-secrets.env"
    shimmed = codex_server_spec(tmp_path / "trace", False, secrets_file=secrets)
    assert shimmed["command"] == sys.executable
    assert shimmed["args"][0].endswith("spawn_server.py")
    assert shimmed["args"][1:] == ["--secrets-file", str(secrets)]


# --------------------------------------------------------------------------- #
# Key delivery (maintainer directive 2026-08-19): Codex does not forward the parent
# env to MCP servers, and every channel it does offer is recorded verbatim in run
# artifacts -- so keys travel through the spawn shim's 0600 file, path-only in
# artifacts, values nowhere.
# --------------------------------------------------------------------------- #
SHIM = REPO / "tests" / "e2e" / "spawn_server.py"


def test_secrets_reach_artifacts_as_a_path_never_a_value(tmp_path):
    from run_suite import write_codex_mcp_config

    fake = "ZEirgEryNcncMKowiNBW8Uqv6Z6xMh6Tvd6uQyoa"
    secrets = tmp_path / "secrets.env"
    secrets.write_text(f"CONGRESS_API_KEY={fake}\n")
    spec = codex_server_spec(tmp_path / "trace", True, secrets_file=secrets)
    config = write_codex_mcp_config(tmp_path, spec)
    text = config.read_text()
    assert str(secrets) in text          # the path is the record
    assert fake not in text              # the value is not
    assert_config_carries_no_secret(config, [fake])
    assert_argv_carries_no_secret(codex_config_overrides(spec), [fake])


def test_write_secrets_file_is_0600_outside_the_run_tree(tmp_path, monkeypatch):
    from run_suite import write_secrets_file

    monkeypatch.setenv("CONGRESS_API_KEY", "fake-key-for-this-test-only")
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    run_dir = tmp_path / "runs" / "now"
    run_dir.mkdir(parents=True)
    path = write_secrets_file(run_dir)
    try:
        assert path is not None
        mode = path.stat().st_mode & 0o777
        assert mode == 0o600, f"secrets file is {oct(mode)}, must be 0600"
        assert run_dir.resolve() not in path.resolve().parents
        assert REPO.resolve() not in path.resolve().parents
        assert path.read_text() == "CONGRESS_API_KEY=fake-key-for-this-test-only\n"
    finally:
        if path:
            path.unlink()


def test_write_secrets_file_returns_none_with_no_keys(tmp_path, monkeypatch):
    from run_suite import write_secrets_file

    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    assert write_secrets_file(tmp_path) is None


def test_write_secrets_file_refuses_to_land_inside_the_run_tree(tmp_path, monkeypatch):
    # The run directory is exactly what an operator tars up and attaches to an issue.
    import run_suite as rs

    monkeypatch.setenv("CONGRESS_API_KEY", "fake-key-for-this-test-only")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    inside = run_dir / "s17-secrets-oops.env"

    def mkstemp_in_run_tree(**kwargs):
        import os as _os
        fd = _os.open(inside, _os.O_RDWR | _os.O_CREAT | _os.O_EXCL, 0o600)
        return fd, str(inside)

    monkeypatch.setattr(rs.tempfile, "mkstemp", mkstemp_in_run_tree)
    with pytest.raises(SystemExit, match="outside the run tree"):
        rs.write_secrets_file(run_dir)
    assert not inside.exists(), "the misplaced file must be deleted, not left behind"


def _run_shim(args, env=None):
    import subprocess
    return subprocess.run([sys.executable, str(SHIM), *args],
                          capture_output=True, text=True, env=env, timeout=30)


def test_shim_refuses_a_group_or_world_readable_secrets_file(tmp_path):
    fake = "ZEirgEryNcncMKowiNBW8Uqv6Z6xMh6Tvd6uQyoa"
    secrets = tmp_path / "secrets.env"
    secrets.write_text(f"CONGRESS_API_KEY={fake}\n")
    secrets.chmod(0o644)
    proc = _run_shim(["--secrets-file", str(secrets)])
    assert proc.returncode == 2
    assert "chmod 600" in proc.stderr
    assert fake not in proc.stderr and fake not in proc.stdout, (
        "the shim must never print a credential value, even while refusing one"
    )


def test_shim_injects_the_keys_and_execs_the_server_module(tmp_path):
    # The full channel, measured: value in the 0600 file -> child process env, with the
    # value appearing on no command line. --exec-module swaps in a dump module so the
    # test does not need a live MCP server.
    import os
    (tmp_path / "envdump.py").write_text(
        "import os\nprint(os.getenv('CONGRESS_API_KEY', 'MISSING'))\n"
    )
    fake = "fake-key-for-this-test-only"
    secrets = tmp_path / "secrets.env"
    secrets.write_text(f"CONGRESS_API_KEY={fake}\n")
    secrets.chmod(0o600)
    env = dict(os.environ)
    env.pop("CONGRESS_API_KEY", None)
    env["PYTHONPATH"] = str(tmp_path)
    proc = _run_shim(["--secrets-file", str(secrets), "--exec-module", "envdump"], env=env)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == fake


def test_shim_fails_loudly_on_a_missing_secrets_file(tmp_path):
    proc = _run_shim(["--secrets-file", str(tmp_path / "gone.env")])
    assert proc.returncode == 2
    assert "cannot stat" in proc.stderr


# --------------------------------------------------------------------------- #
# F29 (amending F23's no-canary ratification): a new driver's cell is gated by a
# forced-call canary BEFORE any prompt is spent, and the verdict is written into the
# artifacts -- never only an exit code. The void Codex run reproduced F23's defining
# state (dead cell scored clean) on the path the sibling heuristic cannot protect:
# when the DRIVER kills every call client-side, there are no live siblings.
# --------------------------------------------------------------------------- #
def test_canary_is_required_for_codex_and_not_for_the_ratified_claude_path():
    from run_suite import CANARY_REQUIRED_DRIVERS

    assert "codex" in CANARY_REQUIRED_DRIVERS
    # The 2026-08-14 ratification stands for Claude: sibling liveness, no canary.
    assert "claude" not in CANARY_REQUIRED_DRIVERS


def test_canary_entry_forces_one_call_on_a_corpus_grounded_document():
    from run_suite import CANARY_ENTRY

    # A forced call, deliberately not cold: it names the tool and the arguments,
    # because it measures the instrument, never the consumer.
    assert "get_bill_toc" in CANARY_ENTRY["prompt"]
    assert CANARY_ENTRY["document"] in MANIFEST["documents"], (
        "the canary must target a document the corpus manifest pins, or its own "
        "failure could be a missing fixture rather than a dead instrument"
    )
    # Its group must not collide with any real cell's groups, so it can never be
    # planned as a prompt.
    for cell in MANIFEST["cells"].values():
        assert CANARY_ENTRY["group"] not in cell["groups"]


def test_canary_resolves_and_runs_in_every_canary_gated_cell(tmp_path):
    # The regression that shipped: the canary rides through resolve_prompt, and the
    # cross-vendor-floor cell requires the single-step variant -- which the canary
    # entry did not define, so the gate CRASHED the live run instead of guarding it.
    # Dry runs skip canaries, so only a direct exercise of this path can catch it:
    # run the canary through run_one in dry-run mode for every cell whose driver
    # requires a canary.
    from run_suite import CANARY_ENTRY, CANARY_REQUIRED_DRIVERS, resolve_prompt, run_one

    gated = {name: cell for name, cell in MANIFEST["cells"].items()
             if cell.get("driver") in CANARY_REQUIRED_DRIVERS}
    assert gated, "no canary-gated cells in the manifest -- the fixture is vacuous"
    for name, cell in gated.items():
        assert resolve_prompt(CANARY_ENTRY, cell) == CANARY_ENTRY["prompt"]
        meta = run_one(CANARY_ENTRY, name, cell, tmp_path / name,
                       {"codex": ["codex", "exec", "-m", "{model}"]},
                       {"codex": "test"}, "sha", MANIFEST["documents"], dry_run=True)
        assert meta.prompt_id == "CANARY" and meta.cell == name


def test_canary_verdict_is_live_only_on_a_server_side_trace():
    from run_suite import canary_verdict

    live = _meta("CANARY", "cross-vendor-floor", trace_records=2)
    assert canary_verdict(live)[0] == "live"
    # Zero traces with a clean exit is exactly the void run's shape: client-side
    # denial or server startup failure, invisible to the exit status.
    dead = _meta("CANARY", "cross-vendor-floor", trace_records=0)
    verdict, reason = canary_verdict(dead)
    assert verdict == "void"
    assert "BEFORE its prompts were spent" in reason
    # A crashed canary invocation is void too, never scored as an instrument check
    # that passed.
    crashed = _meta("CANARY", "cross-vendor-floor", trace_records=3,
                    harness_failure="runner exited 1")
    assert canary_verdict(crashed)[0] == "void"


def test_a_canary_proven_cell_with_all_zero_prompts_is_adoption_not_death():
    # F23 rule 1, realized: a passing canary means a later zero-call cell is a genuine
    # consumer result (mass abstention -- a loud adoption finding), never flagged as a
    # dead instrument. Without the canary proof the same shape stays dead.
    rows = [_meta("A1", "cv", 0), _meta("A2", "cv", 0), _meta("A3", "cv", 0)]
    assert zero_trace_cells(rows, dry_run=False, live_cells=frozenset({"cv"})) == []
    assert zero_trace_cells(rows, dry_run=False) == ["cv"]


def test_codex_api_key_resolution_prefers_env_then_auth_json(tmp_path, monkeypatch):
    # The no-web provider authenticates via OPENAI_API_KEY in the codex process env;
    # the key is resolved at preflight from the operator's env or codex's own
    # auth.json, and refused loudly when neither has one -- a keyless cell would just
    # be the next voided run.
    from run_suite import resolve_codex_api_key

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    assert resolve_codex_api_key() == "from-env"
    monkeypatch.delenv("OPENAI_API_KEY")
    (tmp_path / "auth.json").write_text(json.dumps(
        {"auth_mode": "apikey", "OPENAI_API_KEY": "from-auth-json"}))
    assert resolve_codex_api_key() == "from-auth-json"
    (tmp_path / "auth.json").write_text(json.dumps(
        {"auth_mode": "chatgpt", "OPENAI_API_KEY": None}))
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        resolve_codex_api_key()


def test_codex_server_spec_preapproves_its_tools_in_config_and_overrides(tmp_path):
    # Probe F/G: approval_policy="never" cancels MCP calls client-side unless the
    # server's tools are pre-approved per-server. The mode must appear in BOTH the
    # on-disk record and the executed overrides, since they must never drift.
    from run_suite import write_codex_mcp_config

    spec = codex_server_spec(tmp_path / "trace", True)
    assert spec["default_tools_approval_mode"] == "approve"
    flags = codex_config_overrides(spec)
    assert any("default_tools_approval_mode=" in part for part in flags)
    text = write_codex_mcp_config(tmp_path, spec).read_text()
    assert 'default_tools_approval_mode = "approve"' in text


def test_codex_auth_mode_reads_codex_home(tmp_path, monkeypatch):
    from run_suite import codex_auth_mode

    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}))
    assert codex_auth_mode() == "chatgpt"
    (tmp_path / "auth.json").write_text("not json")
    assert codex_auth_mode() is None
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "missing"))
    assert codex_auth_mode() is None


def test_cell_void_marker_lands_in_the_cell_directory(tmp_path):
    from run_suite import write_cell_void

    write_cell_void(tmp_path, "cross-vendor-floor", "canary", "no trace record")
    marker = tmp_path / "cross-vendor-floor" / "CELL-VOID.json"
    assert marker.exists(), "the verdict must be IN the artifacts, not only an exit code"
    data = json.loads(marker.read_text())
    assert data["verdict"] == "void" and data["source"] == "canary"
    assert "Do not score" in data["scoring_rule"]


def test_claude_command_is_unchanged_by_the_codex_addition(tmp_path):
    # Regression: adding the driver switch must not alter the Claude argv the prior runs
    # were produced under, or a re-run stops being comparable with them.
    cmd = build_command("claude", ["claude", "-p", "--model", "{model}"], "opus",
                        tmp_path / "mcp.json", [], tmp_path / "cold", None)
    assert cmd == [
        "claude", "-p", "--model", "opus",
        "--strict-mcp-config", "--mcp-config", str(tmp_path / "mcp.json"),
        "--permission-mode", "acceptEdits",
        "--allowed-tools", "mcp__congress",
        "--disallowed-tools", ",".join(DISALLOWED_BUILTINS),
    ]


def test_a_cell_with_zero_trace_records_everywhere_is_a_harness_failure():
    # F23, reporting half (§17 harness contract): zero traces means "never
    # called", and a cell where EVERY invocation recorded zero -- exit 0, answers
    # present -- is an instrument that never ran, not seventy consumers who all
    # chose not to call. It must be reported as a harness failure, not a clean run.
    dead = [_meta("A1", "floor", 0), _meta("A2", "floor", 0), _meta("B1", "floor", 0)]
    live = [_meta("A1", "ceiling", 4), _meta("A2", "ceiling", 0), _meta("B1", "ceiling", 2)]
    assert zero_trace_cells(dead + live, dry_run=False) == ["floor"]


def test_a_single_zero_call_prompt_among_live_siblings_stays_a_finding():
    # The B1 precedent: one prompt with zero calls in a cell whose siblings have
    # traces is a real consumer finding. Only the cell-wide zero is the
    # cannot-distinguish-from-a-dead-server case.
    results = [_meta("A1", "floor", 3), _meta("B1", "floor", 0)]
    assert zero_trace_cells(results, dry_run=False) == []


def test_dry_runs_are_exempt_from_the_zero_trace_check():
    # A dry run calls nothing by design; flagging it would train operators to
    # ignore the failure that matters.
    results = [_meta("A1", "floor", 0)]
    assert zero_trace_cells(results, dry_run=True) == []


# --------------------------------------------------------------------------- #
# Manifest integrity -- criteria pinned BEFORE the run.
# --------------------------------------------------------------------------- #
def test_every_scored_prompt_pins_its_criteria_and_its_evidence():
    # Pinning pass/fail in the manifest is §17's preregistration-of-scoring rule; a
    # prompt without them lets a criterion be invented after the result is seen, which
    # is what A4's post-hoc lesson was about. Group F is exempt BY DESIGN -- its
    # naturalism makes per-prompt criteria impossible, and it is scored against the four
    # invariants instead.
    for entry in MANIFEST["prompts"]:
        assert entry.get("grounding"), f"{entry['id']} asserts no evidence"
        if entry["group"] == "F":
            assert entry["pass"] is None and entry["fail"] is None
            assert entry.get("sourcing", "").startswith("DERIVED"), (
                f"{entry['id']}: Group F entries here are derived, not verbatim "
                "originals, and must say so"
            )
        else:
            assert entry.get("pass"), f"{entry['id']} has no pinned pass criterion"
            assert entry.get("fail"), f"{entry['id']} has no pinned fail criterion"


def test_group_f_carries_its_sourcing_caveat():
    # §17 requires Group F questions be verbatim originals from prior research, not
    # composed by someone who has read the spec. These were derived, which is the
    # contamination the rule exists to prevent -- so the manifest must say so loudly
    # enough that a scorer cannot mistake them for measurements.
    caveat = MANIFEST["_group_f_caveat"]
    assert "INDICATIVE ONLY" in caveat
    assert "verbatim" in caveat
    f_prompts = [e for e in MANIFEST["prompts"] if e["group"] == "F"]
    assert f_prompts, "Group F is empty"
    assert len(f_prompts) < 8, (
        "if Group F ever reaches the stated minimum of 8 VERBATIM questions, "
        "this guard and the caveat should be revisited together"
    )


def test_every_prompt_names_its_congress_except_the_two_that_must_not():
    # §17: "Every prompt names its Congress explicitly, deliberately." Bill numbers
    # recycle every two years and the corpus spans three Congresses, so an implicit
    # Congress tests reference resolution AND the property under test at once, and a
    # failure cannot be attributed to either. D4 and D5 are the designated exceptions --
    # reference resolution IS their hypothesis. Group F is naturalistic by design.
    exempt = {"D4", "D5"}
    for entry in MANIFEST["prompts"]:
        if entry["id"] in exempt or entry["group"] == "F":
            continue
        text = entry["prompt"]
        assert ("Congress" in text or "th Congress" in text), (
            f"{entry['id']} does not name its Congress: {text!r}"
        )


def test_prompt_ids_are_unique():
    ids = [e["id"] for e in MANIFEST["prompts"]]
    assert len(ids) == len(set(ids)), "duplicate prompt id -- the run diff is keyed on it"


def test_every_cell_declares_what_it_establishes():
    for name, cell in MANIFEST["cells"].items():
        assert cell.get("role"), f"cell {name} does not say what it establishes"
        assert cell.get("model") and cell.get("groups")


# --------------------------------------------------------------------------- #
# The driver axis (§17 ruling, 2026-08-18): a cell is identified by (driver, model,
# effort, surface, context condition, prompt variant), knobs are recorded verbatim in
# the driver's native vocabulary, and a codex result can never silently substitute for
# a Claude gate cell.
# --------------------------------------------------------------------------- #
def test_every_cell_declares_its_driver():
    # The driver is part of the instrument. A cell without one would silently default,
    # and a Claude-Codex disagreement could then be misattributed to the model alone.
    for name, cell in MANIFEST["cells"].items():
        assert cell.get("driver") in ("claude", "codex"), f"cell {name} names no driver"


def test_no_codex_cell_is_merge_gating_and_all_carry_cross_vendor_roles():
    # Rule 1: floor/ceiling/capability-floor are Claude-matrix roles; every codex cell
    # carries a cross-vendor role and merge_gating false, whatever its tier -- landing
    # in PR 1 is not gating, and the Group A gate remains the Claude cells.
    codex_cells = {n: c for n, c in MANIFEST["cells"].items() if c["driver"] == "codex"}
    assert codex_cells, "the cross-vendor cells are missing from the manifest"
    for name, cell in codex_cells.items():
        assert cell["role"] in ("cross-vendor", "cross-vendor-floor"), (
            f"{name}: a codex cell must carry a cross-vendor role, never a "
            f"Claude-matrix one (got {cell['role']!r})"
        )
        assert cell.get("merge_gating") is False, f"{name} must not gate the merge"


def test_codex_cells_default_to_the_isolation_surface_and_group_a():
    # Rule 2: the three-tool surface is the cheap form of this cell, and A4's
    # fabrication check is attribution-dependent, which only trace-scope == tool-surface
    # supports.
    for name, cell in MANIFEST["cells"].items():
        if cell["driver"] != "codex":
            continue
        assert cell["bill_text_only"] is True, f"{name} must run the isolation surface"
        assert cell["groups"] == ["A"], f"{name} must be scoped to Group A"


def test_cross_vendor_floor_is_the_haiku_cells_twin():
    # Maintainer selection 2026-08-18: Luna, Group A only, single-step variant --
    # so a chaining limitation is never scored as a tool defect, exactly as the Haiku
    # cell dissolved the same confound.
    cell = MANIFEST["cells"]["cross-vendor-floor"]
    haiku = MANIFEST["cells"]["capability"]
    assert cell["use_single_step_variant"] is True
    assert cell["role"] == "cross-vendor-floor"
    assert cell["groups"] == haiku["groups"] == ["A"]
    # Knobs stay in each driver's native vocabulary: the codex cell must carry
    # reasoning_effort and must NOT carry a Claude thinking budget.
    assert cell.get("reasoning_effort") and "thinking" not in cell


def test_terra_probe_is_a_single_prompt_a4_cell_outside_the_default_grid():
    # Maintainer 2026-08-18: Terra, if run at all, is a single-prompt A4
    # characterization probe on the STANDARD variant, never a group cell.
    cell = MANIFEST["cells"]["terra-a4-probe"]
    assert cell["prompts"] == ["A4"]
    assert cell["role"] == "cross-vendor"
    assert not cell.get("use_single_step_variant"), (
        "the A4 probe runs the standard variant -- its question is which failure mode "
        "the tier chooses when the data runs out, not disclosure-reading"
    )


def test_plan_honors_a_cell_prompt_allowlist():
    planned = plan_invocations(MANIFEST, ["terra-a4-probe"], None, None)
    assert [(e["id"], off) for e, _, _, off in planned] == [("A4", False)], (
        "the probe must plan exactly A4, on-grid"
    )
    # Forcing another id in via --prompts is a deliberate diagnostic and must be marked
    # off-grid, never silently normalized into the cell.
    forced = plan_invocations(MANIFEST, ["terra-a4-probe"], None, {"A1"})
    assert [(e["id"], off) for e, _, _, off in forced] == [("A1", True)]


def test_plan_covers_group_a_in_the_cross_vendor_floor_cell():
    planned = plan_invocations(MANIFEST, ["cross-vendor-floor"], None, None)
    assert [e["id"] for e, _, _, off in planned if not off] == ["A1", "A2", "A3", "A4"]


def test_cell_id_carries_driver_model_effort_and_surface():
    assert cell_id_of(MANIFEST["cells"]["cross-vendor-floor"]) == "codex/gpt-5.6-luna/medium/iso"
    assert cell_id_of(MANIFEST["cells"]["floor"]) == "claude/claude-sonnet-5/none/full"
    assert cell_id_of(MANIFEST["cells"]["isolation"]) == "claude/claude-sonnet-5/none/iso"


def test_cell_record_keeps_knobs_verbatim_and_never_translates():
    # Codex reasoning_effort "medium" is NOT "the floor", and a Claude thinking budget
    # is not an effort level: each record carries its own driver's value verbatim.
    versions = {"claude": "claude 2.0 (test)", "codex": "codex-cli 0.99 (test)"}
    codex = cell_record("cross-vendor-floor", MANIFEST["cells"]["cross-vendor-floor"],
                        versions, {"sandbox_mode": "read-only"})
    claude = cell_record("floor", MANIFEST["cells"]["floor"], versions, {})
    assert codex["reasoning_effort"] == "medium"          # codex vocabulary, verbatim
    assert claude["reasoning_effort"] == "none"           # Claude's thinking value, verbatim
    assert codex["driver"] == {"name": "codex", "cli_version": "codex-cli 0.99 (test)"}
    assert claude["driver"] == {"name": "claude", "cli_version": "claude 2.0 (test)"}
    assert codex["prompt_variant"] == "single_step" and claude["prompt_variant"] == "standard"
    assert codex["surface"] == "bill_text_only" and claude["surface"] == "full"
    assert codex["merge_gating"] is False and claude["merge_gating"] is True
    for key in ("cell_id", "driver", "model", "reasoning_effort", "surface",
                "context_condition", "prompt_variant", "groups", "role",
                "merge_gating", "builtins_disabled"):
        assert key in codex and key in claude, f"per-cell record lacks {key}"


def test_codex_knob_overrides_carry_effort_verbatim_and_web_search_off():
    flags = codex_knob_overrides(MANIFEST["cells"]["cross-vendor-floor"])
    assert "tools.web_search=false" in flags
    assert 'model_reasoning_effort="medium"' in flags


def test_builtins_disabled_is_asserted_from_the_claude_argv(tmp_path):
    cmd = build_command("claude", ["claude", "-p", "--model", "{model}"], "m",
                        tmp_path / "mcp.json", [], tmp_path / "cold", None)
    record = builtins_disabled_record("claude", cmd)
    assert record["strict_mcp_config"] is True
    assert record["allowed_tools"] == "mcp__congress"
    assert set(DISALLOWED_BUILTINS) <= set(record["disallowed_tools"])
    # The planted positive: a command that does not close the channel must halt the
    # run, because a record produced from intent rather than the argv could report a
    # closed channel that was open.
    stripped = [part for part in cmd if part != "--strict-mcp-config"]
    with pytest.raises(SystemExit, match="strict-mcp-config"):
        builtins_disabled_record("claude", stripped)


def test_builtins_disabled_is_asserted_from_the_codex_argv(tmp_path):
    cell = MANIFEST["cells"]["cross-vendor-floor"]
    spec = codex_server_spec(tmp_path / "trace", bill_text_only=True)
    overrides = codex_config_overrides(spec) + codex_knob_overrides(cell)
    cmd = build_command("codex", ["codex", "exec", "-m", "{model}"], "m",
                        tmp_path / "mcp.toml", overrides, tmp_path / "cold",
                        tmp_path / "last.txt")
    record = builtins_disabled_record("codex", cmd)
    assert record["sandbox_mode"] == "read-only"
    assert record["approvals"].startswith("never")
    assert record["model_provider"].startswith("openai-noweb")
    assert record["ignore_user_config"] is True
    # F30: the closed-channel entries must read as configuration, never as verified
    # effect -- the void run recorded a bare `false` while the model self-reported
    # web.run.
    assert "configured" in record["tools.web_search"]
    assert "NOT assumed" in record["tools.web_search"]
    # Web search left to its default is an assumption, not configuration: the override
    # must be present in the argv or the record must refuse to exist.
    no_web = [part for part in cmd if part != "tools.web_search=false"]
    with pytest.raises(SystemExit, match="web_search"):
        builtins_disabled_record("codex", no_web)
    # Losing the per-server approval mode silently regresses to the F29 dead cell:
    # "never" cancels every MCP call client-side (probe F).
    no_mcp_approve = [part for part in cmd
                      if "default_tools_approval_mode=" not in part]
    with pytest.raises(SystemExit, match="dead-cell|default_tools_approval_mode"):
        builtins_disabled_record("codex", no_mcp_approve)
    # Losing the no-web provider silently restores the CLI's own web tool (probe E6).
    no_provider = [part for part in cmd if not part.startswith("model_provider=")]
    with pytest.raises(SystemExit, match="model_provider"):
        builtins_disabled_record("codex", no_provider)
    # --approve-for-me returning would reopen the escalation door (probe E7).
    with pytest.raises(SystemExit, match="approve-for-me"):
        builtins_disabled_record("codex", cmd + ["--approve-for-me"])
    # And approvals silently loosening from "never" loses the escalation denial.
    no_never = [part for part in cmd if part != 'approval_policy="never"']
    with pytest.raises(SystemExit, match="approval_policy"):
        builtins_disabled_record("codex", no_never)


def test_web_activity_scan_reads_the_driver_event_streams():
    from run_suite import scan_web_activity

    # The F30 evidence shape: the model self-reported web.run while the config said off.
    assert scan_web_activity("", "tool call: web.run {query}") == ["web.run"]
    assert scan_web_activity("event: web_search started", "") == ["web_search"]
    # THE FORM THAT WAS MISSED: codex 0.147.0 prints "web search: <query>" (with a
    # space) -- run 2026-08-19T045521Z searched six times per prompt and the scan
    # reported the run web-silent because only underscore/dot forms were listed.
    assert "web search" in scan_web_activity("", "web search: S. 1071 478 aircraft")
    # The API-auth function-tool form.
    assert "web__run" in scan_web_activity("", "tool functions.web__run invoked")
    # Case-insensitive, both streams scanned.
    assert scan_web_activity("Using WEB.RUN now", "") == ["web.run"]
    # Clean streams stay clean -- an MCP congress call must not trip it.
    assert scan_web_activity("tool call: mcp__congress get_bill_toc", "") == []


def test_runner_override_refuses_a_mixed_driver_selection():
    # A single --runner template handed to both CLIs would arrive as seventy harness
    # errors mid-run; the refusal belongs at argument time.
    with pytest.raises(SystemExit, match="one driver|span"):
        resolve_runners({"claude", "codex"}, "some-cli -x {model}")
    both = resolve_runners({"claude", "codex"}, None)
    assert both["claude"][0] == "claude" and both["codex"][0] == "codex"
    solo = resolve_runners({"codex"}, "my-codex exec -m {model}")
    assert solo["codex"][0] == "my-codex"
