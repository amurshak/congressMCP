#!/usr/bin/env python3
"""§17 end-to-end prompt suite runner.

Executes the prompt manifest one fresh process at a time, captures the model's
verbatim answer and the server-side trace separately, and writes a diffable run
directory. It does NOT score: pass/fail against the pinned criteria is a human
judgment, and Group A should be scored by someone with no project history.

    CONGRESS_API_KEY=... GOVINFO_API_KEY=... \
        python -m tests.e2e.run_suite --run-dir runs/2026-08-09 --cells floor,ceiling

    python -m tests.e2e.run_suite --dry-run     # validate manifest + layout, call nothing

The harness writes its own MCP config per prompt, pointing the CLI at this repo's server
on stdio (`python -m congress_api --transport stdio`) with --strict-mcp-config, so the
tool surface is configuration rather than whatever the operator happens to have
registered -- and so the isolation cell's three tools and the floor/ceiling full surface
are real settings. The config names NO credential in any form -- the stdio child
inherits the environment, and an unset ${VAR} would arrive as that literal string and
override the working key.

The CLI runs in an empty temp directory OUTSIDE this repo. It resolves project context by
walking up from its working directory, so anywhere inside the repo -- including the
default run directory -- hands the model CLAUDE.md, the source, the spec, and the git
history. One run answered "I had to identify H.R. 3838 from your git history" before this
was fixed.

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


def write_mcp_config(dest: Path, trace_dir: Path, bill_text_only: bool) -> Path:
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

    So the env block carries only the two per-prompt variables the harness must control.
    Everything else, credentials included, comes from inheritance.
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


@dataclass
class Meta:
    prompt_id: str
    group: str
    cell: str
    model: str
    thinking: str
    context: str
    bill_text_only: bool
    single_step_variant: bool
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


def zero_trace_cells(results: list[Meta], dry_run: bool) -> list[str]:
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
    """
    if dry_run:
        return []
    totals: dict[str, int] = {}
    for meta in results:
        totals[meta.cell] = totals.get(meta.cell, 0) + meta.trace_records
    return sorted(cell for cell, total in totals.items() if total == 0)


def run_one(entry: dict, cell_name: str, cell: dict, out_root: Path,
            runner: list[str], sha: str, docs: dict, dry_run: bool,
            outside_cell_groups: bool = False) -> Meta:
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

    text = resolve_prompt(entry, cell)
    assert_prompt_is_cold(text, prompt_id)

    doc = entry.get("document")
    secrets = secret_values()
    # Unique per (run, cell, group, prompt) so no two invocations can share a trace and
    # be mistaken for one session -- the batching failure, made structurally impossible.
    config_path = write_mcp_config(dest, trace_dir, bool(cell.get("bill_text_only")))
    assert_config_carries_no_secret(config_path, secrets)

    env = dict(os.environ)
    env["CONGRESSMCP_TRACE_DIR"] = str(trace_dir)
    env["CONGRESSMCP_BILL_TEXT_ONLY"] = "1" if cell.get("bill_text_only") else ""

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    harness_failure: str | None = None
    exit_status = -1
    answer = ""

    cmd = [part.replace("{model}", cell["model"]) for part in runner] + [
        "--strict-mcp-config",          # ignore every config the operator happens to have
        "--mcp-config", str(config_path),
        "--permission-mode", "acceptEdits",
        "--allowed-tools", "mcp__congress",
        "--disallowed-tools", ",".join(DISALLOWED_BUILTINS),
    ]

    if dry_run:
        exit_status, answer = 0, "[dry-run: no model was called]"
    else:
        try:
            # The prompt goes in on STDIN, not argv. --mcp-config is variadic and will
            # swallow a trailing positional; stdin also keeps the prompt out of the
            # process table. cwd is the neutral directory, never the repo.
            proc = subprocess.run(cmd, cwd=cold_cwd, env=env, input=text,
                                  capture_output=True, text=True, timeout=900)
            exit_status = proc.returncode
            answer = proc.stdout
            if exit_status != 0:
                harness_failure = f"runner exited {exit_status}: {proc.stderr[-800:]}"
            elif not answer.strip():
                # THE INVARIANT THAT MATTERS MOST HERE. B1 at the floor made zero tool
                # calls and that was a real finding. A crashed invocation, a timeout, or
                # an empty answer must never be readable as a consumer that chose not to
                # call anything -- an errored scan must not look like one that found
                # nothing (00-INDEX).
                harness_failure = "empty answer with exit 0 -- harness failure, NOT a consumer result"
        except subprocess.TimeoutExpired:
            harness_failure = "timeout after 900s -- harness failure, NOT a consumer result"
        except FileNotFoundError as exc:
            harness_failure = f"runner not found: {exc}"

    duration = round(time.perf_counter() - t0, 2)
    finished = datetime.now(timezone.utc)

    n_records, tools, lines = read_trace(trace_dir)
    assert_no_secret_in_trace(lines, secret_values(), f"{dest}/trace")

    (dest / "answer.txt").write_text(answer)
    merged = dest / "trace.jsonl"
    merged.write_text("\n".join(lines) + ("\n" if lines else ""))

    meta = Meta(
        prompt_id=prompt_id,
        group=entry["group"],
        cell=cell_name,
        model=cell["model"],
        thinking=cell.get("thinking", "unspecified"),
        context=cell.get("context", "unspecified"),
        bill_text_only=bool(cell.get("bill_text_only")),
        single_step_variant=bool(cell.get("use_single_step_variant")),
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
        criteria={k: entry.get(k) for k in ("title", "pass", "fail", "watch",
                                            "grounding", "sourcing", "substitution")},
    )
    (dest / "meta.json").write_text(json.dumps(asdict(meta), indent=2) + "\n")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=None, help="output root (default runs/<utc-date>)")
    ap.add_argument("--cells", default="floor,ceiling, capability, isolation", help="comma-separated cell names")
    ap.add_argument("--groups", default=None, help="restrict to these groups, e.g. A,B")
    ap.add_argument("--prompts", default=None,
                    help="restrict to these prompt ids. An id named here runs in every "
                         "selected cell EVEN IF the cell's groups exclude it -- an "
                         "explicit request is a deliberate diagnostic, and the result "
                         "is marked outside_cell_groups so it cannot be read back as "
                         "part of the standard grid.")
    ap.add_argument("--runner", default="claude -p --model {model}",
                    help="command template; {model} is substituted. The harness appends "
                         "--strict-mcp-config, --mcp-config, --allowed-tools and "
                         "--disallowed-tools, and feeds the prompt on stdin.")
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

    want_groups = {g.strip() for g in args.groups.split(",")} if args.groups else None
    want_prompts = {p.strip() for p in args.prompts.split(",")} if args.prompts else None

    run_dir = Path(args.run_dir or (REPO / "runs" / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")))
    if run_dir.exists() and any(run_dir.iterdir()):
        print(f"FATAL: {run_dir} exists and is not empty. Refusing to mix two runs in "
              "one directory -- the diff by prompt id is what gives a re-run its meaning.")
        return 1
    run_dir.mkdir(parents=True, exist_ok=True)

    runner = args.runner.split()
    if not args.dry_run and shutil.which(runner[0]) is None:
        print(f"FATAL: runner {runner[0]!r} not on PATH. Pass --runner, or --dry-run.")
        return 1

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

    if want_prompts:
        known = {p["id"] for p in manifest["prompts"]}
        missing = sorted(want_prompts - known)
        if missing:
            print(f"FATAL: --prompts names unknown id(s) {missing}; manifest defines "
                  f"{sorted(known)}")
            return 1

    docs = manifest["documents"]
    planned: list[tuple[dict, str, dict, bool]] = []
    for cell_name in cells:
        cell = manifest["cells"][cell_name]
        allowed = set(cell["groups"])
        for entry in manifest["prompts"]:
            # An id named in --prompts is a deliberate diagnostic request and runs even
            # in a cell whose groups exclude it (e.g. F3 in the isolation cell). The
            # cell-group filter exists to shape the standard grid, not to forbid
            # investigation; the off-grid status is recorded, not silently normalized.
            explicitly_requested = bool(want_prompts) and entry["id"] in want_prompts
            off_cell = entry["group"] not in allowed
            if off_cell and not explicitly_requested:
                continue
            if want_groups and entry["group"] not in want_groups:
                continue
            if want_prompts and not explicitly_requested:
                continue
            planned.append((entry, cell_name, cell, off_cell))

    if not planned:
        print("FATAL: zero prompts selected. Refusing to write a run directory that "
              "would read as a completed suite.")
        return 1

    print(f"build      : {sha[:12]}{'' if working_tree_clean() else '  (DIRTY)'}")
    print(f"run dir    : {run_dir}")
    print(f"cells      : {', '.join(cells)}")
    print(f"invocations: {len(planned)}   (one fresh process each -- never batched)")
    print(f"runner     : {' '.join(runner)}{'   [DRY RUN]' if args.dry_run else ''}\n")

    off_cell_planned = [(e["id"], c) for e, c, _, off in planned if off]
    for pid, cell_name in off_cell_planned:
        print(f"  note: {pid} will run in cell {cell_name!r} OUTSIDE that cell's normal "
              "groups (explicit --prompts request; marked outside_cell_groups in meta)")
    if off_cell_planned:
        print()

    results: list[Meta] = []
    failures = 0
    for entry, cell_name, cell, off_cell in planned:
        try:
            meta = run_one(entry, cell_name, cell, run_dir, runner, sha, docs,
                           args.dry_run, outside_cell_groups=off_cell)
        except ValueError as exc:
            print(f"  {entry['id']:4s} {cell_name:11s} MANIFEST ERROR: {exc}")
            failures += 1
            continue
        results.append(meta)
        flag = "  [outside cell groups]" if meta.outside_cell_groups else ""
        if meta.harness_failure:
            flag += f"  HARNESS FAILURE: {meta.harness_failure[:60]}"
            failures += 1
        print(f"  {meta.prompt_id:4s} {cell_name:11s} {meta.duration_s:6.1f}s  "
              f"{meta.trace_records:>3} trace records  "
              f"{meta.answer_chars:>6} chars  "
              f"{'+'.join(dict.fromkeys(meta.tool_calls)) or '-'}"
              f"{flag}")

    # F23: a cell with zero trace records across EVERY invocation is an instrument
    # that never ran, scored here as a harness failure -- never a clean run. It does
    # not stop anything: all planned invocations have already executed, every other
    # cell's results stand, and the failure is recorded in the manifest and the exit
    # code rather than by aborting.
    dead_cells = zero_trace_cells(results, args.dry_run)
    failures += len(dead_cells)

    (run_dir / "run-manifest.json").write_text(json.dumps({
        "build_sha": sha,
        "working_tree_clean": working_tree_clean(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "cells": {c: manifest["cells"][c] for c in cells},
        "documents": docs,
        "runner": " ".join(runner),
        "dry_run": args.dry_run,
        "prompts": manifest["prompts"],
        "group_f_caveat": manifest["_group_f_caveat"],
        "zero_trace_cell_failures": dead_cells,
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
