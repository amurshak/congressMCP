#!/usr/bin/env python3
"""§17 end-to-end prompt suite runner.

Executes the prompt manifest one fresh process at a time, captures the model's
verbatim answer and the server-side trace separately, and writes a diffable run
directory. It does NOT score: pass/fail against the pinned criteria is a human
judgment, and Group A should be scored by someone with no project history.

    BILL_TEXT_CORPUS_CACHE=... GOVINFO_API_KEY=... CONGRESS_API_KEY=... \
        python -m tests.e2e.run_suite --run-dir runs/2026-08-09 --cells floor,ceiling

    python -m tests.e2e.run_suite --dry-run     # validate manifest + layout, call nothing

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
    criteria: dict = field(default_factory=dict)


def build_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                         capture_output=True, text=True)
    return out.stdout.strip() or "UNKNOWN"


def working_tree_clean() -> bool:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                         capture_output=True, text=True)
    return not out.stdout.strip()


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


def run_one(entry: dict, cell_name: str, cell: dict, out_root: Path,
            runner: list[str], sha: str, docs: dict, dry_run: bool) -> Meta:
    prompt_id = entry["id"]
    dest = out_root / cell_name / entry["group"] / prompt_id
    dest.mkdir(parents=True, exist_ok=True)
    trace_dir = dest / "trace"
    trace_dir.mkdir(exist_ok=True)

    text = resolve_prompt(entry, cell)
    assert_prompt_is_cold(text, prompt_id)

    doc = entry.get("document")
    env = dict(os.environ)
    # Unique per (run, cell, group, prompt) so no two invocations can share a trace and
    # be mistaken for one session -- the batching failure, made structurally impossible.
    env["CONGRESSMCP_TRACE_DIR"] = str(trace_dir)
    env["CONGRESSMCP_BILL_TEXT_ONLY"] = "1" if cell.get("bill_text_only") else ""

    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    harness_failure: str | None = None
    exit_status = -1
    answer = ""

    if dry_run:
        exit_status, answer = 0, "[dry-run: no model was called]"
    else:
        cmd = [part.replace("{model}", cell["model"]) for part in runner] + [text]
        try:
            proc = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True,
                                  text=True, timeout=900)
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
    ap.add_argument("--cells", default="floor,ceiling", help="comma-separated cell names")
    ap.add_argument("--groups", default=None, help="restrict to these groups, e.g. A,B")
    ap.add_argument("--prompts", default=None, help="restrict to these prompt ids")
    ap.add_argument("--runner", default="claude -p --model {model}",
                    help="command template; {model} is substituted, prompt appended as argv")
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

    docs = manifest["documents"]
    planned: list[tuple[dict, str, dict]] = []
    for cell_name in cells:
        cell = manifest["cells"][cell_name]
        allowed = set(cell["groups"])
        for entry in manifest["prompts"]:
            if entry["group"] not in allowed:
                continue
            if want_groups and entry["group"] not in want_groups:
                continue
            if want_prompts and entry["id"] not in want_prompts:
                continue
            planned.append((entry, cell_name, cell))

    if not planned:
        print("FATAL: zero prompts selected. Refusing to write a run directory that "
              "would read as a completed suite.")
        return 1

    print(f"build      : {sha[:12]}{'' if working_tree_clean() else '  (DIRTY)'}")
    print(f"run dir    : {run_dir}")
    print(f"cells      : {', '.join(cells)}")
    print(f"invocations: {len(planned)}   (one fresh process each -- never batched)")
    print(f"runner     : {' '.join(runner)}{'   [DRY RUN]' if args.dry_run else ''}\n")

    results: list[Meta] = []
    failures = 0
    for entry, cell_name, cell in planned:
        try:
            meta = run_one(entry, cell_name, cell, run_dir, runner, sha, docs, args.dry_run)
        except ValueError as exc:
            print(f"  {entry['id']:4s} {cell_name:11s} MANIFEST ERROR: {exc}")
            failures += 1
            continue
        results.append(meta)
        flag = ""
        if meta.harness_failure:
            flag = f"  HARNESS FAILURE: {meta.harness_failure[:60]}"
            failures += 1
        print(f"  {meta.prompt_id:4s} {cell_name:11s} {meta.duration_s:6.1f}s  "
              f"{meta.trace_records:>3} trace records  "
              f"{meta.answer_chars:>6} chars  "
              f"{'+'.join(dict.fromkeys(meta.tool_calls)) or '-'}"
              f"{flag}")

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
        "results": [asdict(m) for m in results],
    }, indent=2) + "\n")

    # A dry run calls nothing, so every row has zero trace records. Reporting those as
    # "the consumer chose not to call" would be the harness committing the exact error
    # its own invariant forbids -- an absence of calls that is really an absence of a run.
    zero_call = [] if args.dry_run else [
        m for m in results if m.trace_records == 0 and not m.harness_failure
    ]
    print(f"\nwrote {len(results)} result dirs to {run_dir}")
    print(f"harness failures: {failures}  (these are NOT consumer results)")
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
