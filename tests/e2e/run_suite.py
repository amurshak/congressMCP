#!/usr/bin/env python3
"""§17 end-to-end prompt suite runner.

Executes the prompt manifest one fresh process at a time, captures the model's
verbatim answer and the server-side trace separately, and writes a diffable run
directory. It does NOT score: pass/fail against the pinned criteria is a human
judgment, and Group A should be scored by someone with no project history.

    CONGRESS_API_KEY=... GOVINFO_API_KEY=... \
        python -m tests.e2e.run_suite --run-dir runs/2026-08-09 --cells floor,ceiling

    python -m tests.e2e.run_suite --cells cross-vendor-floor    # the Codex Luna cell
    python -m tests.e2e.run_suite --dry-run     # validate manifest + layout, call nothing

The harness writes its own MCP config per prompt, pointing the CLI at this repo's server
on stdio (`python -m congress_api --transport stdio`) with --strict-mcp-config, so the
tool surface is configuration rather than whatever the operator happens to have
registered -- and so the isolation cell's three tools and the floor/ceiling full surface
are real settings. The config names NO credential in any form -- the stdio child
inherits the environment, and an unset ${VAR} would arrive as that literal string and
override the working key.

THE DRIVER IS PART OF THE INSTRUMENT (§17 driver-axis ruling, 2026-08-18). Each cell in
the manifest declares its own `driver` (claude or codex), and a cell is identified by
(driver, model, effort, surface, context condition, prompt variant) -- two cells that
differ in driver also differ in system prompt, tool-call formatting, and client-side
behavior the server trace cannot see, so a Claude-Codex disagreement is a cross-instrument
observation, never attributed to the model alone. The measurement itself is
driver-agnostic BY CONSTRUCTION -- the trace is the SERVER's JSONL, not the model's own
account -- so switching drivers changes who is being measured without changing how. Only
the invocation differs, and each driver's flags encode the SAME two guarantees:
(1) the operator's own tool surface is shut out (Claude --strict-mcp-config; Codex
--ignore-user-config, which drops the operator's config.toml -- and its MCP servers,
including an unrelated `congressmcp-dev` pointed at a different install -- while still
loading auth from CODEX_HOME), and (2) the only way to answer is the traced congress
tools. Claude enforces (2) by denying its built-ins; Codex has no per-tool deny, so it
runs in the read-only sandbox with approval_policy="never" -- every escalation denied
-- while the congress server's tools are pre-approved per-server
(default_tools_approval_mode="approve"), so the only grant approval can ever make is a
traced congress call. The web channel needed its own campaign, all of it measured (see
CODEX_NOWEB_PROVIDER and the probe records): ChatGPT auth attaches the backend web.run
tool nothing client-side removes; the builtin API provider registers the CLI's own web
tool (functions.web__run) that survives every tools.* config; and --approve-for-me's
automatic reviewer approves the model's own sandbox-escape requests. The resolution is
a custom no-web provider over the Responses API plus "never" approvals -- so a grounded
answer has nowhere to come from but the MCP server. The provider authenticates via
OPENAI_API_KEY, resolved at preflight and delivered by process env only. Both configurations are
ASSERTED against the argv actually executed and recorded per cell as `builtins_disabled`,
in each driver's own vocabulary (never translated -- Codex `reasoning_effort` is not a
Claude thinking budget, and no mapping between the scales is recorded anywhere). Codex
model ids differ from Claude's; a Claude model id handed to codex fails loudly at the
CLI, never silently.

The CLI runs in an empty temp directory OUTSIDE this repo. It resolves project context by
walking up from its working directory, so anywhere inside the repo -- including the
default run directory -- hands the model CLAUDE.md, the source, the spec, and the git
history. One run answered "I had to identify H.R. 3838 from your git history" before this
was fixed.

THE CACHE AXIS (§17-PR2, 2026-08-22). PR 2 gave the server a persistent bill-text
cache, and a persistent cache is shared state between invocations: a timing observed
on a cell that inherited the platform-default cache dir -- or another prompt's -- is
uninterpretable, and cross-prompt reuse is undisclosed shared state of the same family
as the cold-cwd rule. So every invocation gets a FRESH, EMPTY cache directory created
by the harness outside the repo, passed to the spawned server as CONGRESSMCP_CACHE_DIR
(beside CONGRESSMCP_TRACE_DIR / CONGRESSMCP_BILL_TEXT_ONLY), and recorded in meta.json
as `cache: {dir, mode, ...}`. Mode `cold` (the default, required for every
timing-sensitive cell) is that empty directory. Mode `warm` names packages in the
cell config; the harness warms them by DIRECT server-side calls through the tool
function (tests/e2e/warm_cache.py, a separate process with the trace switch off, so
the warming never burns a model turn and never appears in the cell's trace), asserts
each named package file exists on disk and that the cell's trace is still empty, and
only then runs the prompt in a fresh process against that directory. The warmed
package ids and each warm call's envelope fields are recorded in meta.json.

THE CENTRAL HAZARD, restated from §17: automation is the easiest place to silently
violate the method. A script that runs all prompts in one session, appends a diagnostic
instruction, or reads the model's own account of its tool calls produces numbers that
look like §17 and measure something else. Every invariant below is one of the method's
rules turned into a machine constraint, and each is asserted rather than assumed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MANIFEST = HERE / "prompts.json"

# Framings that would identify the operator as the developer or solicit the model's own
# account of its tool calls. §17: both change the thing being measured -- a model told a
# developer is watching becomes more careful and more explicit about provenance, which
# is precisely the behaviour Group A exists to detect the ABSENCE of. Asserted against
# the exact bytes sent, so no code path can smuggle one in.
FORBIDDEN_IN_PROMPT = (
    "diagnostic", "output your tool", "list your tool", "which tools did you",
    "i'm the developer", "i am the developer", "as the developer", "for testing",
    "explain your reasoning", "how did you determine", "note whether",
    "step by step", "show your work", "debug",
)


# Claude Code's own built-ins. §17's trace records ONLY the three bill-text tools, so a
# claim the model reached by fetching a web page or reading a file is invisible to the
# instrument -- the exact trace-scope error already corrected twice in this project (the
# P.L. 119-60 claim, and A3's "zero tool calls" verdict). The prior runs went through
# Claude Desktop, where these were not present at all; leaving them on here would make
# this re-run non-comparable with the findings it exists to diff against.
DISALLOWED_BUILTINS = (
    "WebSearch", "WebFetch", "Bash", "Read", "Write", "Edit",
    "Glob", "Grep", "Task", "NotebookEdit",
)

# The default command template per driver. {model} is substituted from the cell exactly
# as for Claude; the harness appends the driver-specific isolation flags in build_command.
DEFAULT_RUNNERS = {
    "claude": "claude -p --model {model}",
    "codex": "codex exec -m {model}",
}

# The standard grid. Cells outside it (terra-a4-probe; the §17-PR2 isolation-warm-a4
# and isolation-vd cells) run only on an explicit --cells, each being a one-off
# measurement with its own preregistration rather than part of the recurring matrix.
DEFAULT_CELLS = "floor,ceiling,capability,isolation,cross-vendor-floor"


# The cache axis (§17-PR2). CACHE_ENV is the server's own switch (cache.ENV_CACHE_DIR);
# it is spelled here as a literal on purpose, beside the other two per-prompt env
# names, so the MCP config a run writes is readable without importing the server.
CACHE_ENV = "CONGRESSMCP_CACHE_DIR"
CACHE_MODES = ("cold", "warm")
# Tunables that, if set in the harness's own environment, reach a Claude-driver server
# by inheritance (and a codex-driver server not at all). Recorded per row when set, so
# a non-default TTL or cap is disclosed beside the timing it shaped.
CACHE_TUNABLE_ENVS = (
    "CONGRESSMCP_CACHE_ENABLED", "CONGRESSMCP_CACHE_MAX_BYTES",
    "CONGRESSMCP_VERSION_TTL", "CONGRESSMCP_REVALIDATE_DAYS",
)


def cache_config(cell: dict, docs: dict) -> dict:
    """The cell's cache axis, validated: {"mode": cold|warm, "packages": [ids]}.

    Absent config means cold -- the default, and the only mode a timing-sensitive
    cell may run in. `warm` must name at least one package, each present in the
    manifest's `documents` table (that table carries the congress/type/number/version
    the warm call needs, and the sha the document is pinned at). `cold` must name
    none: a cold cell that lists packages is a config that means two things.
    """
    raw = cell.get("cache") or {}
    if not isinstance(raw, dict):
        raise ValueError("cell `cache` must be an object {mode, packages?}")
    mode = raw.get("mode", "cold")
    if mode not in CACHE_MODES:
        raise ValueError(f"cell cache mode {mode!r} is not one of {CACHE_MODES}")
    packages = list(raw.get("packages") or [])
    if mode == "warm":
        if not packages:
            raise ValueError("a warm cell must name the packages to pre-warm")
        unknown = [p for p in packages if p not in docs]
        if unknown:
            raise ValueError(
                f"warm packages {unknown} are not in the manifest's documents table; "
                "the warm call needs the congress/type/number/version recorded there"
            )
    elif packages:
        raise ValueError("a cold cell must not name packages (cold means empty)")
    return {"mode": mode, "packages": packages}


def make_cache_dir(prompt_id: str) -> Path:
    """A fresh, EMPTY cache directory per invocation, outside the repo.

    Never the platform default and never another invocation's: a cell that
    inherits a populated cache records a timing that some earlier run shaped, and a
    cell that shares one with its siblings carries undisclosed state between prompts.
    mkdtemp guarantees fresh; the rest is asserted rather than assumed. The directory
    is left in place after the run (like the cold cwd) so a warm cell's package files
    can be inspected; its path is in meta.json.
    """
    path = Path(tempfile.mkdtemp(prefix=f"s17-cache-{prompt_id}-"))
    resolved = path.resolve()
    if resolved == REPO.resolve() or REPO.resolve() in resolved.parents:
        raise SystemExit(
            f"FATAL: cache directory {resolved} is inside {REPO}. Package files are "
            "megabytes each and the run tree is what gets attached to an issue; set "
            "TMPDIR outside the repo."
        )
    sys.path.insert(0, str(REPO))
    from congress_api.features.bill_text import cache as cache_mod  # noqa: PLC0415

    inherited = cache_mod.resolve_cache_dir(os.environ).resolve()
    if resolved == inherited:
        raise SystemExit(
            f"FATAL: the fresh cache directory {resolved} IS the directory the server "
            "would use anyway (CONGRESSMCP_CACHE_DIR or the platform default). A cell "
            "must never inherit a persistent cache."
        )
    if any(resolved.iterdir()):
        raise SystemExit(f"FATAL: fresh cache directory {resolved} is not empty.")
    return path


def cache_tunables_in_env() -> dict[str, str]:
    """Cache tunables set in the harness's own environment, for disclosure."""
    return {name: os.environ[name] for name in CACHE_TUNABLE_ENVS
            if os.getenv(name, "").strip()}


def warm_cache(cache_dir: Path, package_ids: list[str], docs: dict,
               trace_dir: Path) -> list[dict]:
    """Warm `package_ids` into `cache_dir` by direct server-side calls; verify on disk.

    Spawns tests/e2e/warm_cache.py with the cell's CONGRESSMCP_CACHE_DIR and the
    trace switch OFF (it refuses otherwise), feeds it the package coordinates from
    the manifest's documents table, and then asserts two things the §17-PR2 contract
    makes load-bearing: every named package file exists in the cell's cache dir, and
    the cell's trace dir is still empty -- the warm never appears in the measurement.
    Halts the run on either failure; a warm cell that is not warm would record a
    cold timing under a warm label.
    """
    specs = [{"package_id": pid, **{k: docs[pid][k] for k in
              ("congress", "bill_type", "number", "version")}}
             for pid in package_ids]
    env = dict(os.environ)
    env[CACHE_ENV] = str(cache_dir)
    env.pop("CONGRESSMCP_TRACE_DIR", None)
    env.pop("CONGRESSMCP_BILL_TEXT_ONLY", None)
    proc = subprocess.run([sys.executable, str(HERE / "warm_cache.py")],
                          cwd=REPO, env=env, input=json.dumps(specs),
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise SystemExit(
            f"FATAL: warm_cache.py exited {proc.returncode} for {package_ids}: "
            f"{proc.stderr[-800:]}"
        )
    try:
        records = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"FATAL: warm_cache.py printed no JSON: {exc}") from None
    sys.path.insert(0, str(REPO))
    from congress_api.features.bill_text import cache as cache_mod  # noqa: PLC0415

    layout = cache_mod.CacheLayout(cache_dir)
    for pid in package_ids:
        path = layout.package_path(pid)
        if not path.exists():
            record = next((r for r in records if r.get("package_id") == pid), None)
            raise SystemExit(
                f"FATAL: warm cell named {pid} but {path} does not exist after "
                f"warming. The cell is NOT warm; refusing to record a cold timing "
                f"under a warm label. warm record: {json.dumps(record)[:600]}"
            )
    if any(trace_dir.iterdir()):
        raise SystemExit(
            f"FATAL: the cell's trace dir {trace_dir} is not empty after warming. "
            "The warming calls must never appear in the measurement."
        )
    return records


def toml_quote(value: str) -> str:
    """Quote a string as a TOML basic string, for Codex `-c key=value` overrides.

    Codex parses the value of `-c key=value` as TOML and falls back to a literal only when
    that parse fails. A path or arg is therefore ambiguous unquoted (a value that happens to
    look like a TOML number/array/bool would be coerced), so every string is quoted and its
    backslashes and quotes escaped -- the argv is passed as a list, so there is no shell
    layer, only TOML's.
    """
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def codex_server_spec(trace_dir: Path, bill_text_only: bool,
                      secrets_file: Path | None = None, *,
                      cache_dir: Path) -> dict:
    """The single congress MCP server Codex is given -- the exact analog of the Claude JSON.

    Same server, same interpreter rule (sys.executable, per F23), same three per-prompt
    env vars (trace dir, surface, cache dir) and NO credential (see write_mcp_config for why naming one would be a bug, not a
    convenience). The whole surface is one server, and --ignore-user-config guarantees it is
    the ONLY one.

    KEY DELIVERY (F31 postmortem, maintainer directive 2026-08-19): Codex does not
    forward the parent environment to MCP servers, so the inheritance channel the Claude
    driver relies on delivers nothing here -- the first live run's server came up keyless.
    And both channels Codex does offer are artifacts: the config env table is written to
    mcp-config.toml in the run directory, and -c overrides land verbatim in meta.json's
    `command`. So with `secrets_file` set, the server is launched through the
    spawn_server.py shim, which reads the 0600 file (outside the run tree, deleted at
    run end) and execs the real server with the keys in its environment. Only the PATH
    appears in any artifact.
    """
    if secrets_file is not None:
        args = [str(HERE / "spawn_server.py"), "--secrets-file", str(secrets_file)]
    else:
        args = ["-m", "congress_api", "--transport", "stdio"]
    return {
        "command": sys.executable,
        "args": args,
        "cwd": str(REPO),
        # Pre-approve this server's tools so approval_policy="never" can deny
        # everything else. Measured (probe G, 2026-08-19): under plain "never" codex
        # CANCELS MCP calls client-side ("user cancelled MCP tool call", zero server
        # traces -- F29's dead-cell shape); with this per-server mode the same call
        # produces a server-side trace record. This is what breaks the catch-22
        # between "never" (kills MCP) and --approve-for-me (auto-approves the
        # model's own shell-escalation requests, reopening the network).
        "default_tools_approval_mode": "approve",
        "env": {
            "CONGRESSMCP_TRACE_DIR": str(trace_dir),
            "CONGRESSMCP_BILL_TEXT_ONLY": "1" if bill_text_only else "",
            CACHE_ENV: str(cache_dir),
        },
    }


def write_secrets_file(run_dir: Path) -> Path | None:
    """The 0600 credentials file the spawn shim reads; None when no key is set.

    Sourced from THE HARNESS'S OWN ENVIRONMENT -- the same CONGRESS_API_KEY /
    GOVINFO_API_KEY exports the Claude driver inherits directly. Operators never
    create or pass this file; the harness writes it, wires its path into the codex
    config, and deletes it at run end. It exists only because codex strips its own
    environment when spawning MCP servers, so the export cannot make the last hop
    unaided.

    Written OUTSIDE both the run tree and the repo -- the run directory is exactly what
    an operator tars up and attaches to an issue, and the repo is what gets committed.
    mkstemp creates the file 0600; the shim independently refuses anything looser, so
    a chmod between write and spawn fails loudly rather than leaking quietly. The
    harness deletes the file when the run ends.
    """
    values = {name: os.getenv(name, "").strip()
              for name in ("CONGRESS_API_KEY", "GOVINFO_API_KEY")}
    values = {k: v for k, v in values.items() if v}
    if not values:
        return None
    fd, raw_path = tempfile.mkstemp(prefix="s17-secrets-", suffix=".env")
    path = Path(raw_path).resolve()
    for forbidden in (run_dir.resolve(), REPO.resolve()):
        if path == forbidden or forbidden in path.parents:
            os.close(fd)
            path.unlink(missing_ok=True)
            raise SystemExit(
                f"FATAL: secrets file would land inside {forbidden}. It must live "
                "outside the run tree and the repo; set TMPDIR elsewhere."
            )
    with os.fdopen(fd, "w") as handle:
        for name, value in values.items():
            handle.write(f"{name}={value}\n")
    return path


def codex_config_overrides(spec: dict) -> list[str]:
    """Flatten the server spec into Codex `-c mcp_servers.congress.*` argv flags.

    Codex has no `--mcp-config <file>`; the surface is passed as config overrides. Built
    from the SAME dict written to the on-disk artifact, so the file the run directory keeps
    and the flags actually executed cannot drift.
    """
    flags: list[str] = []

    def add(key: str, toml_value: str) -> None:
        flags.extend(["-c", f"{key}={toml_value}"])

    add("mcp_servers.congress.command", toml_quote(spec["command"]))
    add("mcp_servers.congress.args", "[" + ", ".join(toml_quote(a) for a in spec["args"]) + "]")
    add("mcp_servers.congress.cwd", toml_quote(spec["cwd"]))
    add("mcp_servers.congress.default_tools_approval_mode",
        toml_quote(spec["default_tools_approval_mode"]))
    for name, value in spec["env"].items():
        add(f"mcp_servers.congress.env.{name}", toml_quote(value))
    return flags


def codex_knob_overrides(cell: dict) -> list[str]:
    """Codex knobs as explicit -c overrides: effort verbatim, web search OFF.

    `tools.web_search=false` is written even though it is Codex's default, because §17's
    builtins ruling demands the effective configuration be configuration, not an
    assumption about a default that a CLI upgrade could flip -- a live web search is
    exactly the untraced channel the ruling closes (codified law standing in for bill
    location, the F7 shape). `model_reasoning_effort` carries the cell's
    `reasoning_effort` verbatim -- Codex's own vocabulary, never a translation of a
    Claude thinking budget.
    """
    flags = ["-c", "tools.web_search=false"]
    effort = cell.get("reasoning_effort")
    if effort:
        flags += ["-c", f"model_reasoning_effort={toml_quote(effort)}"]
    return flags


# The provider that closes the web channel, measured 2026-08-19/20 on codex-cli
# 0.147.0 by listing the model-visible toolset under each candidate config:
#
#   * ChatGPT auth: the backend attaches `web.run`; nothing client-side removes it.
#   * API-key auth, builtin `openai` provider: the CLI itself registers the web tool
#     (functions.web__run) because ModelProviderInfo for the builtin declares
#     `supports_standalone_web_search` -- and it survives tools.web_search=false,
#     tools.web_search.mode="disabled", and --disable standalone_web_search. The live
#     run 2026-08-19T045521Z answered every prompt from `web search:` events with
#     zero MCP calls.
#   * Builtin providers cannot be overridden (the CLI refuses `model_providers.openai`),
#     but a CUSTOM provider pointing at the same Responses API does not declare the
#     capability, and the web tool vanishes from the toolset (probe E6: 3 tools, no
#     web__run).
#
# The custom provider authenticates via env_key, so the codex child needs
# OPENAI_API_KEY in its environment -- resolve_codex_api_key() supplies it from the
# operator's env or codex's own auth.json, and it reaches codex by process env only,
# never an artifact.
#
# Effect-level verification (probe H, 2026-08-19), under the FULL final config with a
# prompt demanding live web data: zero web-search events, the sandboxed curl failed
# DNS resolution, no escalation was granted, and the model answered "live web access
# is unavailable in the current environment; I don't want to guess." The web channel
# is closed in effect, not merely in configuration.
CODEX_NOWEB_PROVIDER = "openai-noweb"


def codex_provider_overrides() -> list[str]:
    return [
        "-c", f'model_providers.{CODEX_NOWEB_PROVIDER}.name="OpenAI (no standalone web tool)"',
        "-c", f'model_providers.{CODEX_NOWEB_PROVIDER}.base_url="https://api.openai.com/v1"',
        "-c", f'model_providers.{CODEX_NOWEB_PROVIDER}.env_key="OPENAI_API_KEY"',
        "-c", f'model_providers.{CODEX_NOWEB_PROVIDER}.wire_api="responses"',
        "-c", f'model_provider={toml_quote(CODEX_NOWEB_PROVIDER)}',
    ]


def builtins_disabled_record(driver: str, cmd: list[str]) -> dict:
    """The per-cell `builtins_disabled` record, ASSERTED from the argv actually executed.

    §17 driver-axis rule 3: the record carries the effective configuration in the
    driver's own keys, asserted rather than assumed. So this function does not describe
    what the harness intends -- it scans the command line run_one is about to execute
    and halts if any required flag is missing, then returns what it verified. A record
    produced any other way could drift from the argv and report a closed channel that
    was open.
    """
    def missing(what: str) -> SystemExit:
        return SystemExit(
            f"FATAL: the {driver} argv lacks {what}. The builtins_disabled record must "
            "be asserted from the executed command, and this command does not close "
            "the channel it claims to. Harness bug; run halted."
        )

    if driver == "claude":
        if "--strict-mcp-config" not in cmd:
            raise missing("--strict-mcp-config")
        try:
            disallowed = cmd[cmd.index("--disallowed-tools") + 1].split(",")
            allowed = cmd[cmd.index("--allowed-tools") + 1]
        except (ValueError, IndexError):
            raise missing("--disallowed-tools/--allowed-tools") from None
        for tool in ("WebSearch", "WebFetch", "Bash", "Read"):
            if tool not in disallowed:
                raise missing(f"{tool} in --disallowed-tools")
        return {
            "strict_mcp_config": True,
            "allowed_tools": allowed,
            "disallowed_tools": disallowed,
        }

    # codex: no per-tool deny exists, so the closed channels are the read-only sandbox
    # (no writes, no network for the model's shell), approval_policy="never" (denies
    # every escalation; the congress tools are pre-approved per-server so MCP still
    # flows -- probe G), the no-web provider (removes the CLI's own web tool from the
    # toolset), the operator's config dropped, and web search config off as belt.
    #
    # F30 caveat, recorded in the value itself: this record is the CONFIGURATION the
    # argv carries. The effect-level channels are the per-cell canary (MCP liveness, a
    # server-side trace record) and the per-row web_activity_suspected scan over the
    # captured runner streams; a scorer must read those for what actually happened.
    try:
        sandbox = cmd[cmd.index("-s") + 1]
    except (ValueError, IndexError):
        raise missing("-s <sandbox_mode>") from None
    if sandbox != "read-only":
        raise missing(f"-s read-only (got {sandbox!r})")
    if 'approval_policy="never"' not in cmd:
        raise missing('-c approval_policy="never" (denies the model\'s escalation '
                      "requests; MCP flows via the per-server approval mode)")
    if "--approve-for-me" in cmd:
        # Probe E7: the auto-reviewer APPROVED a shell escalation that then reached
        # the network. This flag must never return.
        raise missing("no --approve-for-me: its automatic reviewer approves the "
                      "model's own sandbox-escape requests (observed reaching the "
                      "network, probe E7)")
    if f"model_provider={toml_quote(CODEX_NOWEB_PROVIDER)}" not in cmd:
        raise missing(f"-c model_provider=\"{CODEX_NOWEB_PROVIDER}\" (the builtin "
                      "provider registers the CLI's own web tool and no tools.* "
                      "config removes it)")
    if "mcp_servers.congress.default_tools_approval_mode=" + toml_quote("approve") not in cmd:
        raise missing("-c mcp_servers.congress.default_tools_approval_mode=\"approve\" "
                      "(without it, approval_policy=\"never\" cancels every MCP call "
                      "client-side -- the F29 dead-cell shape, probe F)")
    if "--ignore-user-config" not in cmd:
        raise missing("--ignore-user-config")
    if "tools.web_search=false" not in cmd:
        raise missing("-c tools.web_search=false")
    return {
        "sandbox_mode": "read-only",
        "approvals": 'never (escalations denied; congress MCP tools pre-approved '
                     'per-server via default_tools_approval_mode="approve")',
        "model_provider": f"{CODEX_NOWEB_PROVIDER} (custom Responses-API provider; "
                          "does not register the CLI web tool)",
        "ignore_user_config": True,
        "tools.web_search": "false (configured; effect NOT assumed -- see canary and "
                            "per-row web_activity_suspected, F30)",
    }


def codex_auth_mode() -> str | None:
    """The codex CLI's auth mode from $CODEX_HOME/auth.json; None if unreadable.

    This decides whether web can actually be turned off. Measured 2026-08-20 on
    codex-cli 0.147.0, ChatGPT auth, by listing the model-visible toolset under each
    candidate config: `web.run` is attached BACKEND-side -- it survives
    `tools.web_search=false` (valid key, accepted, ineffective) and
    `tools.web_search.mode="disabled"` (accepted, ineffective), and `web_search_mode`
    is not user config at all (`allowed_web_search_modes` is enterprise policy). The
    namespaces say why: client-built tools are all `functions.*`; `web.run` and
    `image_gen.imagegen` are backend namespaces the ChatGPT endpoint attaches on its
    own. API-key auth talks to the Responses API directly, where the toolset is fully
    client-built and web search exists only if --search requests it.
    """
    home = Path(os.getenv("CODEX_HOME", "") or (Path.home() / ".codex"))
    try:
        return json.loads((home / "auth.json").read_text()).get("auth_mode")
    except (OSError, json.JSONDecodeError):
        return None


def resolve_codex_api_key() -> str:
    """The OpenAI API key the no-web provider authenticates with, or a loud refusal.

    The codex cells run through CODEX_NOWEB_PROVIDER, which authenticates via the
    OPENAI_API_KEY env var of the codex process -- so a key must exist, whatever
    auth mode codex is logged in with. Sources, in order: the operator's environment,
    then codex's own auth.json (populated by `codex login --api-key`). The value
    reaches codex by PROCESS ENV only -- never an argv, config file, or manifest,
    which are all run artifacts.

    Without a key the cells cannot run at all: ChatGPT auth attaches the backend
    web.run tool that no client-side config removes (measured 2026-08-19/20), so
    there is no fallback path worth failing into slowly.
    """
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        home = Path(os.getenv("CODEX_HOME", "") or (Path.home() / ".codex"))
        try:
            key = (json.loads((home / "auth.json").read_text())
                   .get("OPENAI_API_KEY") or "").strip()
        except (OSError, json.JSONDecodeError):
            key = ""
    if not key:
        raise SystemExit(
            "FATAL: the codex cells need an OpenAI platform API key and none was "
            "found in OPENAI_API_KEY or in codex's auth.json. They run through a "
            "custom no-web provider (the only measured way to keep the web tool out "
            "of the toolset -- ChatGPT auth attaches backend web.run, and the builtin "
            "API provider registers its own web tool); that provider authenticates "
            "via OPENAI_API_KEY. Fix: `codex login --api-key <key>` or export "
            "OPENAI_API_KEY."
        )
    return key


def cli_version(executable: str) -> str:
    """The driver CLI's version string, recorded at run time -- never assumed.

    §17's per-cell record requires it: two runs of "the same" cell under different CLI
    versions are different instruments, and the difference is invisible unless captured
    when it is true.
    """
    try:
        out = subprocess.run([executable, "--version"], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"UNKNOWN (--version failed: {type(exc).__name__})"
    first = ((out.stdout or out.stderr).strip().splitlines() or ["UNKNOWN"])[0]
    return first.strip() or "UNKNOWN"


def cell_id_of(cell: dict) -> str:
    """(driver, model, effort, surface[, cache]) as one id -- §17's cell identity.

    Shared by the per-prompt meta row and the per-cell manifest record so the two can
    never disagree about which instrument produced a result.
    """
    driver = cell.get("driver", "claude")
    effort = cell.get("reasoning_effort", cell.get("thinking", "unspecified"))
    iso = bool(cell.get("bill_text_only"))
    base = f"{driver}/{cell['model']}/{effort}/{'iso' if iso else 'full'}"
    # The cache axis (§17-PR2) is part of the instrument: a warm cell and its cold
    # twin measure different things. Cold is the default and the state every prior
    # run was in, so its id is unchanged; warm is marked.
    if (cell.get("cache") or {}).get("mode", "cold") == "warm":
        base += "/cache-warm"
    return base


def cell_record(name: str, cell: dict, driver_versions: dict,
                builtins: dict | None) -> dict:
    """The per-cell record for run-manifest.json, in the §17 driver-axis shape.

    All drivers, one shape -- the Claude cells adopt it too. `reasoning_effort` is the
    cell's knob in its driver's native vocabulary, verbatim: Claude cells carry their
    `thinking` value, codex cells their `reasoning_effort`, and no translation between
    the scales exists here or anywhere.
    """
    driver = cell.get("driver", "claude")
    effort = cell.get("reasoning_effort", cell.get("thinking", "unspecified"))
    iso = bool(cell.get("bill_text_only"))
    record = {
        "cell_id": cell_id_of(cell),
        "driver": {"name": driver, "cli_version": driver_versions.get(driver)},
        "model": cell["model"],
        "reasoning_effort": effort,
        "surface": "bill_text_only" if iso else "full",
        "context_condition": cell.get("context", "unspecified"),
        "prompt_variant": "single_step" if cell.get("use_single_step_variant") else "standard",
        "groups": cell["groups"],
        "role": cell["role"],
        "merge_gating": bool(cell.get("merge_gating", False)),
        "builtins_disabled": builtins if builtins is not None else {},
        # The cache axis as configured (mode + packages to warm); each row's
        # meta.json carries the directory and what the warm actually did.
        "cache": {"mode": (cell.get("cache") or {}).get("mode", "cold"),
                  "packages": list((cell.get("cache") or {}).get("packages") or [])},
    }
    if cell.get("prompts"):
        record["prompts"] = cell["prompts"]
    if cell.get("notes"):
        record["notes"] = cell["notes"]
    return record


def write_codex_mcp_config(dest: Path, spec: dict) -> Path:
    """Write the Codex MCP surface as config.toml -- the run-directory record and the thing
    the no-secret assertion scans, mirroring write_mcp_config's mcp-config.json for Claude.

    This file documents the surface; codex_config_overrides passes it to the CLI. Both come
    from `spec`, so the audit that clears this file clears what actually ran.
    """
    lines = [
        "[mcp_servers.congress]",
        f"command = {toml_quote(spec['command'])}",
        "args = [" + ", ".join(toml_quote(a) for a in spec["args"]) + "]",
        f"cwd = {toml_quote(spec['cwd'])}",
        f"default_tools_approval_mode = {toml_quote(spec['default_tools_approval_mode'])}",
        "",
        "[mcp_servers.congress.env]",
    ]
    for name, value in spec["env"].items():
        lines.append(f"{name} = {toml_quote(value)}")
    path = dest / "mcp-config.toml"
    path.write_text("\n".join(lines) + "\n")
    return path


def build_command(agent: str, runner: list[str], model: str, config_path: Path | None,
                  codex_overrides: list[str], cold_cwd: Path, answer_file: Path | None) -> list[str]:
    """Assemble the full argv for the selected driver.

    Both branches append flags that shut out the operator's tool surface and leave the
    traced congress tools as the only answer path -- the two invariants §17 turns into
    configuration -- but the mechanisms are different and each is spelled out where it lives.
    """
    base = [part.replace("{model}", model) for part in runner]
    if agent == "claude":
        return base + [
            "--strict-mcp-config",          # ignore every config the operator happens to have
            "--mcp-config", str(config_path),
            "--permission-mode", "acceptEdits",
            "--allowed-tools", "mcp__congress",
            "--disallowed-tools", ",".join(DISALLOWED_BUILTINS),
        ]
    # codex
    return base + [
        # --ignore-user-config is the --strict-mcp-config analog: it drops the operator's
        # $CODEX_HOME/config.toml -- and with it every MCP server they have registered,
        # including a `congressmcp-dev` pointed at a DIFFERENT install that would answer
        # untraced -- while auth still loads from CODEX_HOME, so a logged-in operator stays
        # authenticated. The congress server is then supplied entirely by the -c overrides.
        "--ignore-user-config",
        # The approvals design, settled by probe after two wrong turns (both preserved
        # in this file's history and in runs/):
        #   * approval_policy="never" ALONE cancels MCP calls client-side ("user
        #     cancelled MCP tool call", zero server traces -- probe F) => dead cell.
        #   * --approve-for-me approves MCP but ALSO auto-approves the model's own
        #     shell-escalation requests: a curl that failed in the sandbox was retried
        #     "outside" on request and SUCCEEDED (probe E7) => open network.
        # The pair below is the resolution: "never" denies every escalation, and the
        # congress server's tools are pre-approved per-server in the MCP spec
        # (default_tools_approval_mode="approve"), so the ONLY thing approval can ever
        # grant is a traced congress call (probe G: 1 trace record, 0 cancellations).
        # Never --dangerously-bypass-*: that reopens the network wholesale.
        "-c", 'approval_policy="never"',
        # Read-only sandbox: the shell can neither write nor reach the network, and
        # with "never" there is no path to escalate out of it.
        "-s", "read-only",
        # The no-web provider: the builtin openai provider registers the CLI's own
        # web tool (functions.web__run) under API-key auth and no tools.* config
        # removes it -- see CODEX_NOWEB_PROVIDER for the probe record.
        *codex_provider_overrides(),
        "--skip-git-repo-check",           # the cold cwd is deliberately not a git repo
        "--ephemeral",                     # persist no session state between prompts
        "-C", str(cold_cwd),
        "-o", str(answer_file),            # final agent message, clean, separate from logs
        *codex_overrides,
        "-",                               # read the prompt from stdin (never argv)
    ]


def write_mcp_config(dest: Path, trace_dir: Path, bill_text_only: bool,
                     cache_dir: Path) -> Path:
    """Write the per-prompt MCP config the CLI is pointed at.

    The harness owns the tool surface rather than inheriting whatever the operator has
    configured. That is the difference between a reproducible cell and a run that
    silently measured a different surface than it recorded -- and it is what makes the
    floor/ceiling "full surface" and the isolation cell's three tools actual
    configuration instead of an assumption.

    NO CREDENTIALS APPEAR HERE, in any form -- not literally, and not as ${VAR}
    references. Measured, not assumed, with a probe server that dumps the env it was
    spawned with:

      * The stdio child INHERITS the parent environment. A key exported in the shell
        that runs this harness reaches the server without being named here at all.
      * ${VAR} expands only when VAR IS SET. When it is not, the value arrives as the
        LITERAL string "${VAR}" -- not empty, not absent.

    Those two together are why the first version of this function was wrong and would
    have failed every run. `GOVINFO_API_KEY` is normally unset, because api.congress.gov
    and api.govinfo.gov share one api.data.gov key; the client reads
    `os.getenv("GOVINFO_API_KEY") or API_KEY`. Writing "${GOVINFO_API_KEY}" therefore
    handed the server a truthy literal, which overrode the working inherited key and
    was sent to GovInfo verbatim -- 401 govinfo_key_rejected on every single call, in a
    shape that reads like a tool defect rather than a harness bug.

    So the env block carries only the three per-prompt variables the harness must
    control (trace dir, surface, cache dir). Everything else, credentials included,
    comes from inheritance.
    """
    config = {
        "mcpServers": {
            "congress": {
                # sys.executable, never a hardcoded venv path (F23): preflight
                # validates imports under THIS interpreter, and the server must run
                # under the same one or the validation attaches to nothing. A path
                # that points at a different (or absent) environment makes every
                # prompt complete with zero trace records -- the empty run the
                # zero-trace check exists to catch, created by the harness itself.
                "command": sys.executable,
                "args": ["-m", "congress_api", "--transport", "stdio"],
                "cwd": str(REPO),
                "env": {
                    "CONGRESSMCP_TRACE_DIR": str(trace_dir),
                    "CONGRESSMCP_BILL_TEXT_ONLY": "1" if bill_text_only else "",
                    CACHE_ENV: str(cache_dir),
                },
            }
        }
    }
    path = dest / "mcp-config.json"
    path.write_text(json.dumps(config, indent=2) + "\n")
    return path


def make_cold_cwd(prompt_id: str) -> Path:
    """An empty working directory OUTSIDE this repository, per prompt.

    The CLI resolves project context by walking UP from its working directory: it finds
    the enclosing git repository and any CLAUDE.md above it. So a scratch directory
    inside the repo -- which `runs/<timestamp>/<cell>/<group>/<prompt>/cwd` was, since
    the default run directory lives in the repo -- hands the model this project's
    CLAUDE.md, source, spec, and git history. That is the most complete developer
    framing available, delivered silently, and §17 exists to measure a consumer that has
    none of it.

    Not hypothetical: a run produced the answer "I had to identify H.R. 3838 from your
    git history." The prompt was cold and the tool surface was right; the *filesystem*
    leaked the project. A temp directory is the only version of "fresh, no project
    memory" that survives contact with a tool that reads its surroundings.
    """
    path = Path(tempfile.mkdtemp(prefix=f"s17-{prompt_id}-"))
    resolved = path.resolve()
    if resolved == REPO.resolve() or REPO.resolve() in resolved.parents:
        raise SystemExit(
            f"FATAL: cold working directory {resolved} is inside {REPO}. The CLI would "
            "read this project's git history and CLAUDE.md as context, which is exactly "
            "the developer framing §17 forbids."
        )
    # Being outside THIS repo is necessary but not sufficient -- the CLI walks up until
    # it finds a git root or a CLAUDE.md, so a temp directory nested under any other
    # project would pick that up instead. Check the whole ancestry, deterministically,
    # rather than relying on a probe run to notice afterwards.
    for parent in [resolved, *resolved.parents]:
        for leak in (".git", "CLAUDE.md"):
            if (parent / leak).exists():
                raise SystemExit(
                    f"FATAL: {parent / leak} sits above the cold working directory "
                    f"{resolved}. The CLI resolves project context by walking up, so "
                    "the model would run with that project's context. Set TMPDIR to a "
                    "location with no project above it."
                )
    return path


def assert_config_carries_no_secret(path: Path, secrets: list[str]) -> None:
    text = path.read_text()
    for secret in secrets:
        if secret in text:
            raise SystemExit(
                f"FATAL: {path} contains a live credential. The config must name no "
                "credential at all -- the stdio child inherits them. Run halted; "
                "delete this file."
            )
    # An unset ${VAR} arrives at the server as that literal string, so a reference here
    # is not a harmless placeholder: it silently overrides the inherited value with
    # nonsense. Since nothing in this config legitimately needs one, any occurrence is
    # a bug, and this catches it at the file rather than at the 401.
    if "${" in text:
        raise SystemExit(
            f"FATAL: {path} contains an unexpanded ${{VAR}} reference. When the variable "
            "is unset the server receives the literal text, overriding the inherited "
            "value. Pass credentials by exporting them, not by naming them here."
        )


def assert_argv_carries_no_secret(cmd: list[str], secrets: list[str]) -> None:
    """The Codex surface travels in argv (-c overrides), not only in a file, so scan it too.

    The file audit (assert_config_carries_no_secret) covers the on-disk record; this covers
    what is actually executed. Same rule for both drivers: a credential reaches the server by
    inheritance, never by being named on a command line (where it would also land in the
    process table and this run's meta.json `command`).
    """
    joined = "\n".join(cmd)
    for secret in secrets:
        if secret in joined:
            raise SystemExit(
                "FATAL: a live credential appears in the runner argv. Credentials must reach "
                "the server by inheritance, never on the command line. Run halted."
            )


@dataclass
class Meta:
    prompt_id: str
    group: str
    cell: str
    # The full cell identity, driver included (§17 driver-axis ruling): the driver is
    # part of the instrument, so a row that named only the model would under-identify
    # the measurement that produced it.
    cell_id: str
    driver: dict  # {"name": ..., "cli_version": <recorded at run time, never assumed>}
    model: str
    # The cell's knob in its driver's native vocabulary, verbatim -- a Claude thinking
    # budget or a Codex effort level, never a translation of one into the other.
    reasoning_effort: str
    context: str
    bill_text_only: bool
    prompt_variant: str  # "single_step" | "standard"
    # True when --prompts forced this prompt into a cell whose groups would not
    # normally include it -- a deliberate diagnostic run, not part of the standard
    # grid. Recorded so the result can never be read back as a grid cell.
    outside_cell_groups: bool
    build_sha: str
    document: str | None
    document_sha256_16: str | None
    prompt_sent: str
    started_utc: str
    finished_utc: str
    duration_s: float
    exit_status: int
    harness_failure: str | None
    trace_records: int
    tool_calls: list[str] = field(default_factory=list)
    answer_chars: int = 0
    # The exact argv, so the tool surface a result was produced under is part of the
    # record rather than inferred from the cell name.
    command: list[str] = field(default_factory=list)
    # Where the CLI ran. Must be outside the repo, or the model reads the project.
    cold_cwd: str = ""
    criteria: dict = field(default_factory=dict)
    # The effective closed-channel configuration, asserted from `command` by
    # builtins_disabled_record -- driver-native keys, per §17 driver-axis rule 3.
    builtins_disabled: dict = field(default_factory=dict)
    # Web-tool markers found in the driver's captured stdout/stderr event streams
    # (F30). Non-empty means the "web off" configuration was NOT effective for this
    # invocation and its claims cannot be read as tool-attributable.
    web_activity_suspected: list[str] = field(default_factory=list)
    # The cache axis (§17-PR2): {dir, mode, warm_packages, warmed, packages_after,
    # tunables_in_harness_env}. `dir` is fresh and empty per invocation; `warmed` is
    # what warm_cache.py recorded for each named package (envelope fields of the
    # direct server-side calls, the file, its size); `packages_after` lists the
    # package files in the dir once the prompt finished.
    cache: dict = field(default_factory=dict)


def build_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                         capture_output=True, text=True)
    return out.stdout.strip() or "UNKNOWN"


def working_tree_clean() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                         capture_output=True, text=True)
    return not out.stdout.strip()


def preflight_credentials() -> str | None:
    """Confirm the server can actually reach GovInfo BEFORE running 70 prompts.

    CONGRESS_API_KEY alone is sufficient: api.congress.gov and api.govinfo.gov share one
    api.data.gov key, and the client reads `os.getenv("GOVINFO_API_KEY") or API_KEY`, so
    GOVINFO_API_KEY is an optional override rather than a second requirement.

    This exists because a credential problem does not announce itself as one. Every tool
    call returns govinfo_key_rejected, every answer says it cannot find the bill, and the
    run records seventy consumer failures that are really one missing export -- an
    errored scan reading as a scan that found nothing, which is the discipline this
    project keeps relearning. Fail here, loudly, once.
    """
    if not (os.getenv("CONGRESS_API_KEY", "").strip() or os.getenv("GOVINFO_API_KEY", "").strip()):
        return ("neither CONGRESS_API_KEY nor GOVINFO_API_KEY is set. CONGRESS_API_KEY "
                "alone is enough -- the two APIs share one api.data.gov key.")
    import asyncio

    sys.path.insert(0, str(REPO))
    try:
        from congress_api.features.bill_text.client import fetch_govinfo_package
    except Exception as exc:  # noqa: BLE001
        return f"could not import the GovInfo client: {type(exc).__name__}: {exc}"
    try:
        # hres463 is the smallest package in the corpus, so this costs one small fetch.
        asyncio.run(fetch_govinfo_package("BILLS-119hres463ih"))
    except Exception as exc:  # noqa: BLE001
        return (f"live GovInfo probe failed: {type(exc).__name__}: {str(exc)[:160]}. "
                "Every prompt would record a tool failure that reads like a consumer "
                "result.")
    return None


def secret_values() -> list[str]:
    """Every credential that could reach a trace, for the redaction assertion."""
    out = []
    for name in ("GOVINFO_API_KEY", "CONGRESS_API_KEY"):
        value = os.getenv(name, "").strip()
        if len(value) >= 8:
            out.append(value)
    return out


def resolve_prompt(entry: dict, cell: dict) -> str:
    """The exact text sent. Nothing is appended, ever.

    The Haiku cell substitutes the pre-resolved address so the prompt is single-step
    by construction -- the chaining a stronger model does inline is pre-performed, not
    removed from the measurement. The tool result still arrives through the real
    channel; only the navigation is gone.
    """
    if cell.get("use_single_step_variant"):
        variant = entry.get("single_step_variant")
        if not variant:
            raise ValueError(
                f"{entry['id']}: cell requires a single-step variant and none is defined. "
                "A multi-hop prompt in the capability cell conflates a chaining "
                "limitation with a tool defect, which is worse than not running it."
            )
        return variant
    return entry["prompt"]


def assert_prompt_is_cold(text: str, prompt_id: str) -> None:
    lowered = text.casefold()
    for marker in FORBIDDEN_IN_PROMPT:
        if marker in lowered:
            raise ValueError(
                f"{prompt_id}: prompt contains {marker!r}. That is a Justify/Hint rung, "
                "not a cold run; automating it onto the cold run destroys the "
                "measurement. Run those separately, failure-only, each in its own "
                "fresh process."
            )


# Tokens the Codex event stream uses for its web tool. The void run's model answered
# with live web citations while tools.web_search=false was recorded (F30) -- so the
# harness scans the driver's own event output for web-tool activity and records what it
# finds. This is detection over the driver's event stream, not scoring of the answer:
# content-based judgment stays with the scorer. "web search" (with the space) is the
# literal event-line prefix codex 0.147.0 prints ("web search: <query>") -- the
# 2026-08-19T045521Z run's searches were missed because only the underscore/dot forms
# were listed, so the run scored web-silent while stderr said `web search:` six times
# per prompt. Never remove the spaced form.
WEB_ACTIVITY_MARKERS = ("web.run", "web_search", "web-search", "web search", "web__run")


def scan_web_activity(*streams: str) -> list[str]:
    """Which web-tool markers appear in the driver's captured output streams.

    Callers pass EVENT streams only, never answer content -- for Claude that means
    stderr alone (its stdout IS the answer, and an answer saying "I cannot perform a
    web search" must not read as web activity); codex prints events to both streams.
    """
    lowered = [(s or "").casefold() for s in streams]
    return [m for m in WEB_ACTIVITY_MARKERS if any(m in s for s in lowered)]


def read_trace(trace_dir: Path) -> tuple[int, list[str], list[str]]:
    """Return (record count, tool names in order, raw lines) from the server's JSONL."""
    lines: list[str] = []
    for path in sorted(trace_dir.glob("*.jsonl")):
        lines.extend(path.read_text(errors="replace").splitlines())
    tools = []
    for line in lines:
        try:
            tools.append(json.loads(line).get("tool", "?"))
        except json.JSONDecodeError:
            tools.append("?UNPARSEABLE")
    return len(lines), tools, lines


def assert_no_secret_in_trace(lines: list[str], secrets: list[str], where: str) -> None:
    """The redactor is installed unconditionally (F15). Assert anyway.

    A trace is exactly the artifact someone pastes into an issue, and the congress.gov
    client still carries the key as a query parameter (§11, pre-existing and out of
    PR 1's scope), so the disclosure path is live. An assertion here costs nothing and
    is the only thing standing between a regression and a published credential.
    """
    if not secrets:
        return
    for n, line in enumerate(lines, start=1):
        for secret in secrets:
            if secret in line:
                raise SystemExit(
                    f"FATAL: live credential found in {where} line {n}. "
                    "Run halted; do not publish this directory."
                )


def zero_trace_cells(results: list[Meta], dry_run: bool,
                     live_cells: frozenset[str] = frozenset()) -> list[str]:
    """F23, the reporting half of the §17 harness contract.

    Zero trace records means the tools were NEVER CALLED -- a server outside a
    working environment fails loudly rather than running untraced -- so a cell
    where every invocation recorded zero traces is an instrument that never ran,
    not a set of consumers who all chose not to call. The aggregate is per CELL,
    not per prompt: a single zero-call prompt among live siblings is a real
    consumer finding (B1 at the floor), proven readable as such precisely because
    its siblings' traces show the instrument was live. When a cell is zero
    everywhere -- including a deliberate single-prompt run -- the two cases are
    indistinguishable, and indistinguishable-from-broken must read as broken.

    `live_cells` (F29 amendment): a cell whose pre-cell canary produced a
    server-side trace record has PROVEN its instrument live out of band, so an
    all-zero prompt set there is a set of genuine adoption findings, not a dead
    cell -- exactly the F23 rule-1 distinction the canary exists to draw.
    """
    if dry_run:
        return []
    totals: dict[str, int] = {}
    for meta in results:
        totals[meta.cell] = totals.get(meta.cell, 0) + meta.trace_records
    return sorted(cell for cell, total in totals.items()
                  if total == 0 and cell not in live_cells)


# F29 (amending F23's no-canary ratification, maintainer 2026-08-19): the ratified
# sibling-liveness heuristic assumed the Claude driver's failure modes; the first Codex
# run reproduced F23's defining state -- a dead cell scored clean row by row -- on a
# path the sibling heuristic cannot protect, because when the DRIVER kills every call
# client-side (approval auto-deny, MCP startup failure) there are no live siblings to
# tell instrument death from mass abstention. So a NEW driver's cells are gated by a
# forced-call canary BEFORE any prompt is spent: one invocation whose prompt explicitly
# demands a single MCP call, asserted to have produced a server-side trace record. The
# Claude cells keep the ratified sibling heuristic unchanged.
CANARY_REQUIRED_DRIVERS = frozenset({"codex"})

# The canary's one call targets the smallest corpus package -- the same document the
# credential preflight fetches, so its availability is already proven out of band.
# This prompt is deliberately NOT cold: it names the tool and the arguments, because
# the canary measures the instrument (can a call get through?), never the consumer.
_CANARY_PROMPT = (
    "Use the get_bill_toc tool from the congress MCP server with congress=119, "
    'bill_type="hres", number=463, and reply with the number of top-level '
    "entries in the table of contents it returns."
)
CANARY_ENTRY = {
    "id": "CANARY",
    "group": "_canary",
    "prompt": _CANARY_PROMPT,
    # The canary is single-step BY CONSTRUCTION -- it names the exact call -- so it is
    # its own variant. Without this, a cell that requires the single-step variant
    # (cross-vendor-floor does) refuses the canary at resolve_prompt and the gate
    # crashes the run instead of guarding it.
    "single_step_variant": _CANARY_PROMPT,
    "document": "BILLS-119hres463ih",
    "title": "forced-call canary -- instrument liveness, not a consumer measurement",
    "grounding": "same package the credential preflight fetches; smallest in the corpus",
}


def canary_verdict(meta: Meta) -> tuple[str, str]:
    """(verdict, reason) for a canary invocation: live only on a server-side trace."""
    if meta.harness_failure:
        return "void", f"canary invocation failed: {meta.harness_failure}"
    if meta.trace_records == 0:
        return "void", (
            "canary produced no server-side trace record: the driver's MCP channel is "
            "dead (client-side approval denial, server startup failure, or total "
            "adoption collapse -- runner-stderr.txt has the driver's own account). "
            "The cell was voided BEFORE its prompts were spent."
        )
    return "live", f"canary produced {meta.trace_records} server-side trace record(s)"


def write_cell_void(run_dir: Path, cell_name: str, source: str, reason: str) -> None:
    """The cell-level verdict marker, written INTO the artifacts (F29).

    The void Codex run was scored clean because the verdict lived only in the exit
    code and a top-level manifest field: every row a scorer opened said
    harness_failure: null. This marker sits in the cell directory itself, where no
    per-row reading can miss the directory listing.
    """
    dest = run_dir / cell_name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "CELL-VOID.json").write_text(json.dumps({
        "cell": cell_name,
        "verdict": "void",
        "source": source,
        "reason": reason,
        "scoring_rule": "Do not score any row of this cell as a consumer result.",
    }, indent=2) + "\n")


def plan_invocations(manifest: dict, cells: list[str],
                     want_groups: set[str] | None,
                     want_prompts: set[str] | None) -> list[tuple[dict, str, dict, bool]]:
    """The (prompt x cell) grid, honoring each cell's group scope AND prompt allowlist.

    A cell may carry an explicit `prompts` list (the Terra A4 probe is a single-prompt
    cell by ruling); prompts outside it are off-grid for that cell exactly as an
    out-of-scope group is. An id named in --prompts still runs anywhere as a deliberate
    diagnostic, marked outside_cell_groups so it can never be read back as part of the
    standard grid.
    """
    planned: list[tuple[dict, str, dict, bool]] = []
    for cell_name in cells:
        cell = manifest["cells"][cell_name]
        allowed = set(cell["groups"])
        cell_prompts = set(cell.get("prompts") or [])
        for entry in manifest["prompts"]:
            explicitly_requested = bool(want_prompts) and entry["id"] in want_prompts
            off_cell = (entry["group"] not in allowed
                        or (bool(cell_prompts) and entry["id"] not in cell_prompts))
            if off_cell and not explicitly_requested:
                continue
            if want_groups and entry["group"] not in want_groups:
                continue
            if want_prompts and not explicitly_requested:
                continue
            planned.append((entry, cell_name, cell, off_cell))
    return planned


def resolve_runners(drivers: set[str], runner_arg: str | None) -> dict[str, list[str]]:
    """One command template per driver in use.

    --runner is a single template, so it is only meaningful when the selected cells
    share one driver; applying it across drivers would hand a Claude invocation to the
    Codex CLI (or vice versa) and the failure would arrive as seventy harness errors
    rather than one clear refusal here.
    """
    if runner_arg and len(drivers) > 1:
        raise SystemExit(
            f"FATAL: --runner given but the selected cells span drivers "
            f"{sorted(drivers)}. A single template cannot serve both CLIs; select "
            "cells of one driver, or drop --runner to use each driver's default."
        )
    return {d: (runner_arg or DEFAULT_RUNNERS[d]).split() for d in sorted(drivers)}


def run_one(entry: dict, cell_name: str, cell: dict, out_root: Path,
            runners: dict[str, list[str]], driver_versions: dict, sha: str,
            docs: dict, dry_run: bool, outside_cell_groups: bool = False,
            secrets_file: Path | None = None,
            codex_api_key: str | None = None) -> Meta:
    agent = cell.get("driver", "claude")
    runner = runners[agent]
    prompt_id = entry["id"]
    dest = out_root / cell_name / entry["group"] / prompt_id
    dest.mkdir(parents=True, exist_ok=True)
    trace_dir = dest / "trace"
    trace_dir.mkdir(exist_ok=True)
    # A NEUTRAL working directory, per prompt. Running the CLI inside this repo would
    # put CLAUDE.md, the spec, and the implementation in the model's reach -- the most
    # complete developer framing available, handed over silently. §17: "no memory of
    # this project, no developer framing." An empty directory is the only way to mean it.
    cold_cwd = make_cold_cwd(prompt_id)
    # A fresh, empty cache directory per invocation (§17-PR2 cache axis) -- never the
    # platform default, never another prompt's. Warmed below, after the configs are
    # written and before the CLI is spawned, when the cell asks for it.
    cache_cfg = cache_config(cell, docs)
    cache_dir = make_cache_dir(prompt_id)

    text = resolve_prompt(entry, cell)
    assert_prompt_is_cold(text, prompt_id)

    doc = entry.get("document")
    secrets = secret_values()
    bill_text_only = bool(cell.get("bill_text_only"))
    # The MCP surface is written per (run, cell, group, prompt) so no two invocations can
    # share a trace and be mistaken for one session -- the batching failure, made
    # structurally impossible. Each driver names the surface its own way (Claude a JSON file
    # it reads; Codex a config.toml record plus -c overrides), but both are audited to carry
    # no credential, and the answer for Codex comes from --output-last-message, not stdout.
    codex_overrides: list[str] = []
    answer_file: Path | None = None
    if agent == "claude":
        config_path = write_mcp_config(dest, trace_dir, bill_text_only, cache_dir)
    else:
        spec = codex_server_spec(trace_dir, bill_text_only, secrets_file,
                                 cache_dir=cache_dir)
        config_path = write_codex_mcp_config(dest, spec)
        # The cell's knobs (effort verbatim, web search off) travel in the same -c
        # channel as the MCP surface, so the argv audit below covers them too.
        codex_overrides = codex_config_overrides(spec) + codex_knob_overrides(cell)
        answer_file = dest / "agent-last-message.txt"
    assert_config_carries_no_secret(config_path, secrets)

    env = dict(os.environ)
    env["CONGRESSMCP_TRACE_DIR"] = str(trace_dir)
    env["CONGRESSMCP_BILL_TEXT_ONLY"] = "1" if bill_text_only else ""
    env[CACHE_ENV] = str(cache_dir)
    if agent == "codex" and codex_api_key:
        # The no-web provider authenticates via env_key=OPENAI_API_KEY. Process env
        # only: it appears in no config file, no argv, and no meta row.
        env["OPENAI_API_KEY"] = codex_api_key

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    harness_failure: str | None = None
    exit_status = -1
    answer = ""
    stdout_text = ""
    stderr_text = ""

    cmd = build_command(agent, runner, cell["model"], config_path, codex_overrides,
                        cold_cwd, answer_file)
    assert_argv_carries_no_secret(cmd, secrets)
    # Asserted from the argv about to be executed, never assumed (§17 driver-axis rule
    # 3): halts here if the command does not actually close the untraced channels.
    builtins = builtins_disabled_record(agent, cmd)

    # Warm BEFORE the CLI process exists, never through it. Skipped on a dry run
    # (no network, no model), and recorded as skipped rather than as warm.
    warmed: list[dict] | None = None
    if cache_cfg["mode"] == "warm" and not dry_run:
        warmed = warm_cache(cache_dir, cache_cfg["packages"], docs, trace_dir)

    if dry_run:
        exit_status, answer = 0, "[dry-run: no model was called]"
    else:
        try:
            # The prompt goes in on STDIN, not argv (Claude's --mcp-config is variadic and
            # would swallow a trailing positional; Codex reads stdin when the prompt arg is
            # `-`). stdin also keeps the prompt out of the process table. cwd is the neutral
            # directory, never the repo.
            proc = subprocess.run(cmd, cwd=cold_cwd, env=env, input=text,
                                  capture_output=True, text=True, timeout=900)
            exit_status = proc.returncode
            stdout_text, stderr_text = proc.stdout, proc.stderr
            # Claude prints the final result to stdout; Codex prints progress there and
            # writes the final message to the -o file, so take the answer from whichever
            # the driver uses (and keep Codex's stdout as a debugging artifact).
            if agent == "codex":
                (dest / "runner-stdout.txt").write_text(stdout_text)
                answer = (answer_file.read_text() if answer_file and answer_file.exists()
                          else stdout_text)
            else:
                answer = stdout_text
            if exit_status != 0:
                harness_failure = f"runner exited {exit_status}: {stderr_text[-800:]}"
            elif not answer.strip():
                # THE INVARIANT THAT MATTERS MOST HERE. B1 at the floor made zero tool
                # calls and that was a real finding. A crashed invocation, a timeout, or
                # an empty answer must never be readable as a consumer that chose not to
                # call anything -- an errored scan must not look like one that found
                # nothing (00-INDEX).
                harness_failure = "empty answer with exit 0 -- harness failure, NOT a consumer result"
        except subprocess.TimeoutExpired as exc:
            harness_failure = "timeout after 900s -- harness failure, NOT a consumer result"
            partial = exc.stderr
            stderr_text = (partial.decode(errors="replace")
                           if isinstance(partial, bytes) else (partial or ""))
        except FileNotFoundError as exc:
            harness_failure = f"runner not found: {exc}"
        # F30: Codex reports MCP server startup failures ONLY on stderr, and the void
        # run discarded it -- the one channel that named the defect. Keep it verbatim,
        # for every driver, whatever the exit status.
        (dest / "runner-stderr.txt").write_text(stderr_text)

    duration = round(time.perf_counter() - t0, 2)
    finished = datetime.now(timezone.utc)

    n_records, tools, lines = read_trace(trace_dir)
    assert_no_secret_in_trace(lines, secret_values(), f"{dest}/trace")

    (dest / "answer.txt").write_text(answer)
    merged = dest / "trace.jsonl"
    merged.write_text("\n".join(lines) + ("\n" if lines else ""))

    effort = cell.get("reasoning_effort", cell.get("thinking", "unspecified"))
    meta = Meta(
        prompt_id=prompt_id,
        group=entry["group"],
        cell=cell_name,
        cell_id=cell_id_of(cell),
        driver={"name": agent, "cli_version": driver_versions.get(agent)},
        model=cell["model"],
        reasoning_effort=effort,
        context=cell.get("context", "unspecified"),
        bill_text_only=bill_text_only,
        prompt_variant="single_step" if cell.get("use_single_step_variant") else "standard",
        outside_cell_groups=outside_cell_groups,
        build_sha=sha,
        document=doc,
        document_sha256_16=(docs.get(doc) or {}).get("sha256_16") if doc else None,
        prompt_sent=text,
        started_utc=started.isoformat(),
        finished_utc=finished.isoformat(),
        duration_s=duration,
        exit_status=exit_status,
        harness_failure=harness_failure,
        trace_records=n_records,
        tool_calls=tools,
        answer_chars=len(answer),
        command=cmd,
        cold_cwd=str(cold_cwd),
        # Criteria travel WITH the result so a scorer never has to reconstruct them,
        # and so editing one after seeing a result is visible in the diff.
        criteria={k: entry.get(k) for k in ("title", "pass", "fail", "scoring",
                                            "watch", "grounding", "sourcing",
                                            "substitution")},
        builtins_disabled=builtins,
        web_activity_suspected=(scan_web_activity(stdout_text, stderr_text)
                                if agent == "codex"
                                else scan_web_activity(stderr_text)),
        cache={
            "dir": str(cache_dir),
            "mode": cache_cfg["mode"],
            "warm_packages": cache_cfg["packages"],
            "warmed": (warmed if warmed is not None else
                       ("[dry-run: not warmed]" if cache_cfg["mode"] == "warm"
                        else None)),
            "packages_after": sorted(
                p.name for p in (cache_dir / "packages").glob("*.db")
            ) if (cache_dir / "packages").is_dir() else [],
            "tunables_in_harness_env": cache_tunables_in_env(),
        },
    )
    (dest / "meta.json").write_text(json.dumps(asdict(meta), indent=2) + "\n")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=None, help="output root (default runs/<utc-date>)")
    # terra-a4-probe is deliberately NOT in the default grid: it is the optional
    # single-prompt characterization probe, run on explicit maintainer call or as the
    # upgrade path after a cross-vendor-floor failure (§17, maintainer 2026-08-18).
    ap.add_argument("--cells", default=DEFAULT_CELLS,
                    help="comma-separated cell names (default: the standard grid; the "
                         "§17-PR2 cells isolation-warm-a4 and isolation-vd, and the "
                         "terra-a4-probe, run on explicit maintainer call)")
    ap.add_argument("--groups", default=None, help="restrict to these groups, e.g. A,B")
    ap.add_argument("--prompts", default=None,
                    help="restrict to these prompt ids. An id named here runs in every "
                         "selected cell EVEN IF the cell's groups exclude it -- an "
                         "explicit request is a deliberate diagnostic, and the result "
                         "is marked outside_cell_groups so it cannot be read back as "
                         "part of the standard grid.")
    ap.add_argument("--agent", default=None, choices=sorted(DEFAULT_RUNNERS),
                    help="restrict the selected cells to this driver (each cell declares "
                         "its own driver in the manifest -- the driver is part of the "
                         "instrument, so it is a cell property, not a run property). "
                         "E.g. --agent codex runs only the codex cells.")
    ap.add_argument("--runner", default=None,
                    help="command template; {model} is substituted. Defaults per driver "
                         "(claude: 'claude -p --model {model}'; codex: 'codex exec -m {model}'). "
                         "Only valid when the selected cells share one driver. The harness "
                         "appends the driver-specific isolation flags and feeds the prompt "
                         "on stdin.")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate manifest, cells, and layout without calling any model")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="permit a dirty working tree (results then attach to no known build)")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    sha = build_sha()
    if not working_tree_clean() and not args.allow_dirty and not args.dry_run:
        print("FATAL: working tree is dirty. A result that attaches to no known code "
              "state is unreadable later (§17 trace constraint 3). Commit, or pass "
              "--allow-dirty and accept that the build sha is approximate.")
        return 1

    cells = [c.strip() for c in args.cells.split(",") if c.strip()]
    unknown = [c for c in cells if c not in manifest["cells"]]
    if unknown:
        print(f"FATAL: unknown cell(s) {unknown}; manifest defines "
              f"{sorted(manifest['cells'])}")
        return 1
    if args.agent:
        dropped = [c for c in cells
                   if manifest["cells"][c].get("driver", "claude") != args.agent]
        cells = [c for c in cells if c not in dropped]
        if dropped:
            print(f"note: --agent {args.agent} drops cell(s) {dropped} (other driver)")
        if not cells:
            print(f"FATAL: --agent {args.agent} leaves zero cells. Each cell declares "
                  "its driver in the manifest; select cells of that driver instead.")
            return 1

    # The cache axis is validated for every selected cell BEFORE anything is spent,
    # so a misconfigured warm cell fails here and not after its siblings ran.
    for c in cells:
        try:
            cache_config(manifest["cells"][c], manifest["documents"])
        except ValueError as exc:
            print(f"FATAL: cell {c!r} cache axis: {exc}")
            return 1

    want_groups = {g.strip() for g in args.groups.split(",")} if args.groups else None
    want_prompts = {p.strip() for p in args.prompts.split(",")} if args.prompts else None

    # Resolve and validate the drivers BEFORE creating the run directory, so an
    # argument error leaves no empty run dir behind.
    drivers = {manifest["cells"][c].get("driver", "claude") for c in cells}
    runners = resolve_runners(drivers, args.runner)
    if not args.dry_run:
        for d in sorted(drivers):
            if shutil.which(runners[d][0]) is None:
                print(f"FATAL: {d} runner {runners[d][0]!r} not on PATH. Install it, "
                      "narrow --cells to one driver, or --dry-run.")
                return 1

    run_dir = Path(args.run_dir or (REPO / "runs" / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")))
    if run_dir.exists() and any(run_dir.iterdir()):
        print(f"FATAL: {run_dir} exists and is not empty. Refusing to mix two runs in "
              "one directory -- the diff by prompt id is what gives a re-run its meaning.")
        return 1
    run_dir.mkdir(parents=True, exist_ok=True)
    # The CLI version is part of the instrument identity and is recorded AT RUN TIME,
    # never assumed (§17 driver-axis ruling). A dry run invokes no CLI, so it records
    # none rather than a guess.
    driver_versions = ({d: None for d in drivers} if args.dry_run
                       else {d: cli_version(runners[d][0]) for d in sorted(drivers)})
    codex_auth: str | None = None
    codex_api_key: str | None = None

    if not args.dry_run:
        # F23: assert at startup that the interpreter the MCP configs will name can
        # actually load the server package from the repo. Preflight validates under
        # sys.executable and the config now launches under sys.executable, so this
        # is the one check that keeps "validated" and "executed" the same thing.
        probe = subprocess.run([sys.executable, "-c", "import congress_api"],
                               cwd=REPO, capture_output=True, text=True)
        if probe.returncode != 0:
            print(f"FATAL: {sys.executable} cannot import congress_api from {REPO}: "
                  f"{probe.stderr.strip()[-300:]}\n"
                  "The stdio server would never start and every prompt would complete "
                  "with zero trace records -- an empty run wearing a clean table. Fix "
                  "the environment (or run the harness under the right interpreter).")
            return 1
        problem = preflight_credentials()
        if problem:
            print(f"FATAL: {problem}")
            print("Export the key in the shell that runs this harness; the stdio server "
                  "inherits it. Do NOT name it in the MCP config -- an unset ${VAR} "
                  "arrives as that literal string and overrides the working value.")
            return 1
        print("preflight  : GovInfo reachable with the configured key.")
        # The cache axis needs the cache ON: a cold cell with the cache disabled is
        # still "cold" but a warm one is a lie, and the disabled switch would reach
        # only the Claude-driver servers (by inheritance) -- an undisclosed
        # asymmetry. Refuse rather than record it.
        from congress_api.features.bill_text import cache as cache_mod  # noqa: PLC0415
        if not cache_mod.CacheSettings.from_env().enabled:
            print("FATAL: CONGRESSMCP_CACHE_ENABLED is off in this environment. The "
                  "cache axis (§17-PR2) requires the cache enabled; unset it.")
            return 1
        print("preflight  : cache enabled; fresh CONGRESSMCP_CACHE_DIR per invocation"
              + (f"; tunables in env: {cache_tunables_in_env()}"
                 if cache_tunables_in_env() else ""))
        if "codex" in drivers:
            # F30 residual: the codex cells run through the no-web provider, which
            # needs an OpenAI API key. Resolve it now -- before any canary or prompt
            # is spent -- and record only the auth MODE, never the key.
            codex_auth = codex_auth_mode()
            codex_api_key = resolve_codex_api_key()
            print(f"preflight  : codex auth_mode={codex_auth!r}; API key resolved for "
                  f"the {CODEX_NOWEB_PROVIDER} provider (delivered by process env only).")

    if want_prompts:
        known = {p["id"] for p in manifest["prompts"]}
        missing = sorted(want_prompts - known)
        if missing:
            print(f"FATAL: --prompts names unknown id(s) {missing}; manifest defines "
                  f"{sorted(known)}")
            return 1

    docs = manifest["documents"]
    # An id named in --prompts is a deliberate diagnostic request and runs even in a
    # cell whose groups (or prompt allowlist) exclude it -- e.g. F3 in the isolation
    # cell. The filters shape the standard grid, not forbid investigation; the off-grid
    # status is recorded, not silently normalized.
    planned = plan_invocations(manifest, cells, want_groups, want_prompts)

    if not planned:
        print("FATAL: zero prompts selected. Refusing to write a run directory that "
              "would read as a completed suite.")
        return 1

    print(f"build      : {sha[:12]}{'' if working_tree_clean() else '  (DIRTY)'}")
    print(f"run dir    : {run_dir}")
    print(f"cells      : {', '.join(cells)}")
    print(f"invocations: {len(planned)}   (one fresh process each -- never batched)")
    for d in sorted(drivers):
        version = driver_versions[d] or "(not recorded: dry run)"
        print(f"driver     : {d}  {' '.join(runners[d])}  [{version}]"
              f"{'   [DRY RUN]' if args.dry_run else ''}")
    print()

    off_cell_planned = [(e["id"], c) for e, c, _, off in planned if off]
    for pid, cell_name in off_cell_planned:
        print(f"  note: {pid} will run in cell {cell_name!r} OUTSIDE that cell's normal "
              "groups (explicit --prompts request; marked outside_cell_groups in meta)")
    if off_cell_planned:
        print()

    # Codex does not inherit the parent environment into MCP servers, so its cells get
    # the keys through the spawn shim's 0600 file -- created once here, outside the run
    # tree, deleted when the run ends whatever happens in between.
    secrets_file = (write_secrets_file(run_dir)
                    if "codex" in drivers and not args.dry_run else None)

    results: list[Meta] = []
    canaries: list[Meta] = []
    canary_by_cell: dict[str, dict] = {}
    voided: dict[str, str] = {}
    live_by_canary: set[str] = set()
    failures = 0
    try:
        for run_cell_name in cells:
            run_cell = manifest["cells"][run_cell_name]
            cell_planned = [p for p in planned if p[1] == run_cell_name]
            if not cell_planned:
                continue
            # F29: a new driver's cell is gated by a forced-call canary BEFORE any
            # prompt is spent. The verdict is written into the artifacts (canary.json,
            # and CELL-VOID.json on failure), never only into an exit code -- the void
            # run was scored clean because every row a scorer opened looked clean.
            if (run_cell.get("driver", "claude") in CANARY_REQUIRED_DRIVERS
                    and not args.dry_run):
                canary_meta = run_one(CANARY_ENTRY, run_cell_name, run_cell, run_dir,
                                      runners, driver_versions, sha, docs, False,
                                      secrets_file=secrets_file,
                                      codex_api_key=codex_api_key)
                canaries.append(canary_meta)
                verdict, reason = canary_verdict(canary_meta)
                canary_by_cell[run_cell_name] = {
                    "verdict": verdict, "reason": reason,
                    "trace_records": canary_meta.trace_records,
                }
                (run_dir / run_cell_name / "canary.json").write_text(
                    json.dumps(canary_by_cell[run_cell_name], indent=2) + "\n")
                print(f"  CANARY {run_cell_name}: {verdict.upper()}  "
                      f"({canary_meta.trace_records} trace records)")
                if verdict == "void":
                    write_cell_void(run_dir, run_cell_name, "canary", reason)
                    voided[run_cell_name] = reason
                    failures += 1
                    print(f"  CELL VOIDED before spending prompts: {run_cell_name} -- "
                          f"{len(cell_planned)} prompt(s) skipped. See "
                          f"{run_dir / run_cell_name / 'CELL-VOID.json'} and the "
                          "canary's runner-stderr.txt.")
                    continue
                live_by_canary.add(run_cell_name)
            for entry, cell_name, cell, off_cell in cell_planned:
                try:
                    meta = run_one(entry, cell_name, cell, run_dir, runners, driver_versions,
                                   sha, docs, args.dry_run, outside_cell_groups=off_cell,
                                   secrets_file=secrets_file,
                                   codex_api_key=codex_api_key)
                except ValueError as exc:
                    print(f"  {entry['id']:4s} {cell_name:11s} MANIFEST ERROR: {exc}")
                    failures += 1
                    continue
                results.append(meta)
                flag = "  [outside cell groups]" if meta.outside_cell_groups else ""
                if meta.harness_failure:
                    flag += f"  HARNESS FAILURE: {meta.harness_failure[:60]}"
                    failures += 1
                if meta.web_activity_suspected:
                    # An open web channel is an instrument breach, not a consumer
                    # behavior: the row's claims are no longer tool-attributable, so it
                    # counts as a harness failure even when the invocation itself
                    # exited cleanly (F30).
                    flag += (f"  WEB ACTIVITY SUSPECTED "
                             f"({','.join(meta.web_activity_suspected)})"
                             " -- claims not tool-attributable")
                    failures += 1
                print(f"  {meta.prompt_id:4s} {cell_name:11s} {meta.duration_s:6.1f}s  "
                      f"{meta.trace_records:>3} trace records  "
                      f"{meta.answer_chars:>6} chars  "
                      f"{'+'.join(dict.fromkeys(meta.tool_calls)) or '-'}"
                      f"{flag}")
    finally:
        # The credential file outlives nothing: deleted on success, failure, and ^C
        # alike. The shim's stat-time check means a server started after this point
        # fails loudly rather than reading a stale path.
        if secrets_file is not None:
            secrets_file.unlink(missing_ok=True)

    # F23: a cell with zero trace records across EVERY invocation is an instrument
    # that never ran, scored here as a harness failure -- never a clean run. It does
    # not stop anything: all planned invocations have already executed, every other
    # cell's results stand, and the failure is recorded in the manifest and the exit
    # code rather than by aborting. A cell whose canary proved the instrument live is
    # exempt: its zero-call prompts are genuine adoption findings (F23 rule 1).
    dead_cells = zero_trace_cells(results, args.dry_run, frozenset(live_by_canary))
    failures += len(dead_cells)
    for dead in dead_cells:
        # F29: the verdict goes INTO the artifacts, never only into the exit code and
        # a top-level manifest field -- the void run was scored clean because every
        # row a scorer opened said harness_failure: null. The cell directory gets the
        # unmissable marker, and every row of the dead cell is stamped post hoc.
        reason = ("every invocation in this cell recorded zero trace records: the "
                  "instrument never ran (post-hoc sibling-liveness check, F23)")
        write_cell_void(run_dir, dead, "zero_trace_post_hoc", reason)
        for m in results:
            if m.cell != dead:
                continue
            row_path = run_dir / m.cell / m.group / m.prompt_id / "meta.json"
            row = json.loads(row_path.read_text())
            row["cell_void"] = reason
            row_path.write_text(json.dumps(row, indent=2) + "\n")

    # The per-cell records adopt the §17 driver-axis shape for ALL drivers. Each cell's
    # builtins_disabled comes from its own executed argv (any of its results -- the
    # record is identical across a cell by construction); a cell that produced no result
    # rows gets an empty record rather than an invented one.
    builtins_by_cell = {}
    for m in results:
        builtins_by_cell.setdefault(m.cell, m.builtins_disabled)
    (run_dir / "run-manifest.json").write_text(json.dumps({
        "build_sha": sha,
        "working_tree_clean": working_tree_clean(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "cells": {c: {**cell_record(c, manifest["cells"][c], driver_versions,
                                    builtins_by_cell.get(c)),
                      **({"canary": canary_by_cell[c]} if c in canary_by_cell else {})}
                  for c in cells},
        "documents": docs,
        "runners": {d: " ".join(runners[d]) for d in sorted(drivers)},
        "dry_run": args.dry_run,
        "prompts": manifest["prompts"],
        "group_f_caveat": manifest["_group_f_caveat"],
        "zero_trace_cell_failures": dead_cells,
        "voided_cells": voided,
        "canaries": [asdict(m) for m in canaries],
        # Instrument identity for the codex driver: which auth mode ran. ChatGPT auth
        # never reaches here (the preflight refuses it -- backend web.run), so a
        # recorded value documents that the web channel was closable by construction.
        "codex_auth_mode": codex_auth,
        "results": [asdict(m) for m in results],
    }, indent=2) + "\n")

    # A dry run calls nothing, so every row has zero trace records. Reporting those as
    # "the consumer chose not to call" would be the harness committing the exact error
    # its own invariant forbids -- an absence of calls that is really an absence of a run.
    # A prompt inside a dead cell is excluded for the same reason: with the whole cell
    # at zero there is no live sibling to prove the instrument ran, so it is part of the
    # cell's harness failure, not a consumer finding.
    zero_call = [] if args.dry_run else [
        m for m in results
        if m.trace_records == 0 and not m.harness_failure and m.cell not in dead_cells
    ]
    print(f"\nwrote {len(results)} result dirs to {run_dir}")
    print(f"harness failures: {failures}  (these are NOT consumer results)")
    for cell_name in dead_cells:
        n = sum(1 for m in results if m.cell == cell_name)
        print(f"  HARNESS FAILURE: cell {cell_name!r} recorded ZERO trace records across "
              f"all {n} invocation(s). The tools were never called -- this is an empty "
              "run, not a clean one. Do not score it.")
    if zero_call:
        print(f"zero-tool-call runs that COMPLETED cleanly: "
              f"{[m.prompt_id + '/' + m.cell for m in zero_call]}")
        print("  These are real findings, not errors -- the invocation succeeded and the "
              "consumer chose not to call. Verify independently before calling anything "
              "fabricated: the trace sees only the three bill-text tools.")
    print("\nThis harness does not score. Pass/fail against the pinned criteria in each "
          "meta.json is a human judgment, and Group A should be scored by someone with "
          "no project history.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
