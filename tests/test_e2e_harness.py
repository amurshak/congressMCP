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
    codex_config_overrides,
    codex_server_spec,
    make_cold_cwd,
    resolve_prompt,
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
        prompt_id=prompt_id, group="A", cell=cell, agent="claude", model="m", thinking="none",
        context="fresh", bill_text_only=False, single_step_variant=False,
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
    assert cmd[cmd.index("-s") + 1] == "read-only"
    assert 'approval_policy="never"' in cmd
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
    assert "-s" in cmd and cmd[cmd.index("-s") + 1] == "read-only"
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
