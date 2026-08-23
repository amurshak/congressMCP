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

  This redaction covers LOG OUTPUT too, and has to (F15). §3 has both services sharing
  one api.data.gov key, and the congress.gov client passes it as a query parameter, so
  httpx's INFO-level URL logging prints a live credential -- confirmed on a live run.
  Redacting only the JSONL would be necessary-but-insufficient: a user debugging a
  bill-text problem attaches the logs alongside the trace, and the artifact the
  redaction rule exists to make safe would still carry the key. The disclosure path is
  shared, so the redaction follows it. This does NOT fix the congress.gov client's
  query-parameter defect (pre-existing, and out of PR 1's scope) -- it stops that defect
  from reaching the file a user hands to someone else.

  The log half is installed on IMPORT and is not gated on the trace switch, unlike
  everything else here. The key reaches the logs whether or not tracing is on, so
  gating would remove the protection exactly when nobody is watching; and redaction
  can only remove a credential from output, so there is nothing to trade off against.
  See install_log_redaction for the three properties that makes it safe to import.

What this does NOT record: the model's answer. The trace is what the server received and
returned; the verbatim answer still comes from the client transcript. The failure that
matters most -- correct data here paired with a wrong answer in the transcript -- is only
visible by comparing the two.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

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


def set_source(package_id: str, version: str, xml_bytes: bytes | None) -> None:
    """Record which exact bytes produced this response. sha256 is only computed when
    tracing is on, so the hash cost never touches the normal path. When the
    response was served from a persisted index (no XML in hand) the sha256 is
    None and ``served_from_cache`` says so, so a replay knows the bytes were not
    re-downloaded on this call."""
    if not enabled():
        return
    _source.set(
        {
            "package_id": package_id,
            "version": version,
            "sha256": hashlib.sha256(xml_bytes).hexdigest() if xml_bytes is not None else None,
            "served_from_cache": xml_bytes is None,
        }
    )


_SECRET_ENV_NAMES = ("GOVINFO_API_KEY", "CONGRESS_API_KEY", "API_KEY")
_secret_cache: tuple[tuple[str | None, ...], list[str]] | None = None


def _secret_values() -> list[str]:
    """Known key values, memoized against the environment they were read from.

    Memoized because the log-redaction factory runs on EVERY LogRecord in the
    process, so this is hot in a way it never was when it only served trace writes.
    The fingerprint is three dict lookups, and a changed env recomputes -- so a key
    set (or monkeypatched) after import is still picked up.
    """
    global _secret_cache
    fingerprint = tuple(os.getenv(name) for name in _SECRET_ENV_NAMES)
    if _secret_cache is not None and _secret_cache[0] == fingerprint:
        return _secret_cache[1]
    values: set[str] = set()
    for value in fingerprint:
        if value and len(value) >= 8:
            values.add(value)
    try:
        from ...core.api_config import API_KEY  # noqa: PLC0415

        if API_KEY and len(API_KEY) >= 8:
            values.add(API_KEY)
    except Exception:  # noqa: BLE001
        pass
    # Also match the PERCENT-ENCODED form. The disclosure channel is a URL, and a URL
    # encodes what it carries: httpx renders a key containing any character outside
    # the unreserved set as e.g. %C3%BC, which a literal substring match sails past.
    # An api.data.gov key is alphanumeric and encodes to itself, so this is a no-op
    # for the real one -- but redaction must not silently depend on the shape of the
    # secret it is redacting.
    for value in list(values):
        encoded = quote(value, safe="")
        if encoded != value:
            values.add(encoded)
    resolved = list(values)
    _secret_cache = (fingerprint, resolved)
    return resolved


def redact(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, "[REDACTED]")
    return text


def _redact_log_arg(value: Any, secrets: list[str]) -> Any:
    """Redact one logging arg, which is NOT necessarily a string.

    This is where the first version of F15 leaked. httpx logs
    'HTTP Request: %s %s "%s %d %s"' with request.url as an httpx.URL OBJECT, so an
    isinstance(value, str) guard skips exactly the argument carrying the key, and the
    %s formatting stringifies it back with the credential intact at emit time. The
    unit test passed a str and went green while the live run still leaked -- the
    vacuous green this project keeps guarding against, caught only by grepping a real
    log.

    Non-string args are stringified ONLY to test them, and replaced only when they
    actually carry a secret, so %d and friends keep their original objects and their
    formatting semantics.
    """
    if isinstance(value, str):
        return redact(value) if any(secret in value for secret in secrets) else value
    try:
        text = str(value)
    except Exception:  # noqa: BLE001 -- a repr that raises must not break logging
        return value
    return redact(text) if any(secret in text for secret in secrets) else value


def _redact_exception_channel(record: logging.LogRecord, secrets: list[str]) -> None:
    """Redact a key carried by an exception attached to a log record.

    A TRACEBACK does not pass through msg/args at all, so the record-factory
    redaction misses it entirely. It is reachable: httpx's raise_for_status builds
    "Server error '500 ...' for url '<full url>'", and the congress.gov client sends
    the key as a query parameter (§11, pre-existing), so logger.exception renders a
    live credential.

    Two channels, because one is not enough:

      exc_text -- the stdlib Formatter caches the rendered traceback here and reuses
        it if already set. Set only when a secret is actually present, so ordinary
        errors keep default formatting.

      exception args -- rich's handler with rich_tracebacks renders exc_info DIRECTLY
        and ignores exc_text (measured; this server logs through rich), so exc_text
        alone would have been a fix that passes a stdlib test and leaks in the actual
        deployment -- the same shape as the isinstance(str) miss. Redacting args
        neutralises the message for any renderer that stringifies the exception.

    KNOWN LIMIT, stated rather than papered over: a renderer configured to show
    locals can still reach exc.request.url, and this cannot mitigate that. All of
    this is downstream of the root cause -- the key belongs in a header, not a query
    parameter (§11) -- and mitigation shrinks the surface without closing it. The
    durable fix is the congress.gov client change, which is a separate PR.
    """
    exc_info = record.exc_info
    if not exc_info or not isinstance(exc_info, tuple) or exc_info[1] is None:
        return
    exception = exc_info[1]
    if exception.args:
        redacted_args = tuple(_redact_log_arg(arg, secrets) for arg in exception.args)
        if redacted_args != exception.args:
            exception.args = redacted_args
    if not record.exc_text:
        import traceback as _traceback  # noqa: PLC0415 -- only on the error path

        text = "".join(_traceback.format_exception(exc_info[0], exception, exc_info[2]))
        if any(secret in text for secret in secrets):
            record.exc_text = redact(text)


_log_redaction_installed = False


def install_log_redaction() -> None:
    """Redact known key values from every LogRecord in this process (F15).

    UNCONDITIONAL, deliberately. The key reaches INFO logs whether or not tracing is
    on, and the disclosure path -- logs pasted into an issue -- does not depend on
    tracing either, so gating it would make the protection absent exactly when nobody
    is watching. Redaction can only ever REMOVE a credential from output; there is no
    scenario in which the key is wanted in a log line, so the gate bought nothing and
    added a failure mode where protection is contingent on an unrelated variable.
    Relying on production log level is explicitly not a fix either (§11): any
    contributor can flip it to INFO while debugging something else, and the failure is
    silent.

    Implemented as a LogRecord factory rather than a filter on a logger or handler,
    because both of those are scoped: a filter on a logger sees only records made
    through that logger, and a filter on a handler sees only handlers that already
    existed when it was attached. The leak is httpx's INFO URL line today, but the
    property wanted is "no log record carries the key", and only the factory covers
    every logger and every handler including ones configured later.

    Three properties this needs because it is unconditional and process-global:

      CHAINS -- setLogRecordFactory is process-global, so the previously installed
        factory is captured and called rather than discarded. If this package is
        imported into a host application rather than run as a server, replacing the
        host's factory outright would silently drop whatever it adds. Pinned by test.

      NEVER RAISES -- a factory that throws breaks logging for the whole process, so
        any failure falls back to the unredacted record. Losing redaction on one line
        beats taking down the host's logging.

      IDEMPOTENT -- installing twice would chain the redaction to itself, which is
        harmless but pointless; the flag makes repeat imports free.
    """
    global _log_redaction_installed
    if _log_redaction_installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        try:
            secrets = _secret_values()
            if not secrets:
                return record
            if isinstance(record.msg, str) and any(value in record.msg for value in secrets):
                record.msg = redact(record.msg)
            if record.args:
                # args are substituted into msg at format time, and httpx puts the
                # URL (with the key) there rather than in msg -- a msg-only redaction
                # passes its test and leaks in production. Args are not necessarily
                # strings either; see _redact_log_arg.
                if isinstance(record.args, dict):
                    record.args = {
                        key: _redact_log_arg(value, secrets)
                        for key, value in record.args.items()
                    }
                else:
                    record.args = tuple(
                        _redact_log_arg(value, secrets) for value in record.args
                    )
            # A traceback bypasses msg/args entirely; stack_info is already a string.
            _redact_exception_channel(record, secrets)
            if record.stack_info and any(s in record.stack_info for s in secrets):
                record.stack_info = redact(record.stack_info)
        except Exception:  # noqa: BLE001 -- never break the host's logging
            return record
        return record

    logging.setLogRecordFactory(factory)
    _log_redaction_installed = True


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


# Log redaction is NOT part of the debug-tracing switch: the key reaches INFO logs
# regardless, so this installs on import and stays installed. Everything else in this
# module remains gated on CONGRESSMCP_TRACE_DIR.
install_log_redaction()
