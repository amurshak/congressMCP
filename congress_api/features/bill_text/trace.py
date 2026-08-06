"""Out-of-band request/response tracing for the bill-text tools -- DEBUG ONLY.

Enabled solely by the presence of CONGRESSMCP_TRACE_DIR (a filesystem path). Absence
means off, with no default location, so nothing is ever written by accident -- point it
somewhere OUTSIDE the developer cache (§13 keeps those separate for the same reason).

One JSON object per invocation (JSONL) appended to <dir>/bill_text_trace.jsonl:
timestamp, tool, args-as-issued, response, duration, and source provenance
(package_id + version + source sha256). The provenance stamp extends the two-fixture
policy so a trace can be re-scored against invariants weeks later -- worth most for
Group F answers, which are scored against invariants rather than pre-registered
criteria.

Two properties this module is responsible for:

  FAITHFULNESS -- the logged `response` is the exact object the tool returned (the same
  dict the caller receives from model_dump()), not a re-render. A trace built on a
  parallel serialization path can look right while the wire is wrong -- D2's shape.

  KEY SAFETY -- the API key travels as a query parameter on the congress.gov path, and a
  trace is exactly what gets pasted into a bug report. Every known key value is redacted
  at WRITE time, before any line touches disk.

What this does NOT record: the model's answer. The trace is what the server received and
returned; the verbatim answer still comes from the client transcript. The failure that
matters most -- correct data here paired with a wrong answer in the transcript -- is only
visible by comparing the two.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_TRACE_DIR_ENV = "CONGRESSMCP_TRACE_DIR"
_TRACE_FILE = "bill_text_trace.jsonl"

# Source provenance for the invocation currently on this task's stack, set by the load
# path (which is the only layer holding the raw bytes) and read by the tool decorator.
_source: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "bill_text_trace_source", default=None
)


def trace_dir() -> Path | None:
    raw = os.getenv(_TRACE_DIR_ENV, "").strip()
    return Path(raw) if raw else None


def enabled() -> bool:
    return trace_dir() is not None


def clear_source() -> None:
    _source.set(None)


def set_source(package_id: str, version: str, xml_bytes: bytes) -> None:
    """Record which exact bytes produced this response. sha256 is only computed when
    tracing is on, so the hash cost never touches the normal path."""
    if not enabled():
        return
    _source.set(
        {
            "package_id": package_id,
            "version": version,
            "sha256": hashlib.sha256(xml_bytes).hexdigest(),
        }
    )


def _secret_values() -> list[str]:
    values: set[str] = set()
    for name in ("GOVINFO_API_KEY", "CONGRESS_API_KEY", "API_KEY"):
        v = os.getenv(name)
        if v and len(v) >= 8:
            values.add(v)
    try:
        from ...core.api_config import API_KEY  # noqa: PLC0415

        if API_KEY and len(API_KEY) >= 8:
            values.add(API_KEY)
    except Exception:  # noqa: BLE001
        pass
    return list(values)


def redact(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, "[REDACTED]")
    return text


def write(tool: str, kwargs: dict[str, Any], response: Any, duration_ms: float) -> None:
    """Append one JSONL record. Never raises -- tracing must not break a tool call."""
    directory = trace_dir()
    if directory is None:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "args": kwargs,          # ctx is excluded; the new tools are keyword-only
        "response": response,    # the exact dict the caller receives (faithfulness)
        "duration_ms": duration_ms,
        "source": _source.get(),
    }
    try:
        line = redact(json.dumps(record, default=str, ensure_ascii=False))
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / _TRACE_FILE).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:  # noqa: BLE001 -- debug tracing is best-effort, never fatal
        pass
