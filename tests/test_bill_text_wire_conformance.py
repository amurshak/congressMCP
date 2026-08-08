"""V17 -- wire-format conformance for the three bill-text tools (spec §9).

Exercises the SERIALIZER, not the fetch: load_bill_text is patched to return a
fixture-built LoadedBillText, so a green run here is NOT an end-to-end acceptance --
it asserts the response CONTRACT that no V1-V16 step covered. D2 is the reason this
gap is load-bearing: a tool can pass every parser/index step and still emit an empty
structured array with all content in a prose blob.

The two assertions that carry the weight -- both catch D2, where field-presence would
not (members=[] is present and correctly typed; presence is not the property):

  POPULATION -- collections are non-empty for inputs known to match. The check is that
    the tool PUT the data in the structured field, not that the field exists.

  COUNT/COLLECTION COHERENCE -- every count field equals the size of what it counts
    (chunks_indexed == #units, sections_indexed, chunks_searched, toc depth == measured
    tree depth). D2's actual signature is results_count disagreeing with an empty
    serializer; a per-field check structurally cannot see that, a cross-field invariant
    catches it on the first run. Same family as `amends != [] => is_amendatory`.

Plus a no-prose-blob guard, and -- the durable half, the only assertion that guards a
FUTURE failure rather than confirming today's behavior -- an AST check that the
bill_text package never imports the shared response_converters. That is exactly how
someone "routing the new tools through the shared converter for consistency" would
silently inherit D2; it is one line and it outlives the rest.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

import pytest

import congress_api.features.bill_text.tools as tools
from congress_api.features.bill_text import trace
from congress_api.features.bill_text.client import ResolvedBillText
from congress_api.features.bill_text.index import BillTextIndex
from congress_api.features.bill_text.parser import parse_bill_xml
from congress_api.features.bill_text.service import LoadedBillText

FIXTURE = Path(__file__).parent / "fixtures" / "bill_text_trimmed.xml"
PKG, VER = "BILLS-119s1071enr", "enr"
_QUERY = "polar security cutter"      # present in the fixture's quoted material
_SECTION_ID = "D:B/T:I/S:102"          # a real leaf section in the fixture


def _loaded() -> LoadedBillText:
    raw = FIXTURE.read_bytes()
    parsed = parse_bill_xml(raw, PKG, VER, "2025-12-19T03:11:48Z")
    resolved = ResolvedBillText(
        package_id=PKG, version=VER, version_resolved_at="2025-12-19T03:11:48Z",
        version_resolution_note=None, last_modified="2025-12-19T03:11:48Z", xml_bytes=raw,
    )
    return LoadedBillText(resolved=resolved, parsed=parsed, index=BillTextIndex(parsed),
                          timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0})


LOADED = _loaded()


class _Ctx:  # never touched: load_bill_text is patched, so the fetch path never runs
    pass


def _call(coro_fn, *args, **kwargs):
    async def fake_load(ctx, congress, bill_type, number, version):
        # mirror the real load path's provenance stamp so trace tests see it
        trace.set_source(LOADED.resolved.package_id, LOADED.resolved.version, LOADED.resolved.xml_bytes)
        return LOADED
    with patch.object(tools, "load_bill_text", new=fake_load):
        return asyncio.run(coro_fn(_Ctx(), *args, **kwargs))


def _measured_depth(nodes: list[dict]) -> int:
    """Max nesting depth of a toc forest (1 per level, 0 for empty)."""
    if not nodes:
        return 0
    return 1 + max(_measured_depth(n.get("children") or []) for n in nodes)


# --------------------------------------------------------------------------- #
# search_bill_text
# --------------------------------------------------------------------------- #
def test_search_populates_hits_and_counts_cohere():
    res = _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
                queries=[_QUERY], max_hits=10)
    assert "summary" not in res                          # no prose-blob smuggling
    # POPULATION: a matching query must return a non-empty structured array
    assert isinstance(res["hits"], list) and len(res["hits"]) > 0
    # COHERENCE: reported index/search counts must equal reality
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed
    assert res["chunks_searched"] == res["chunks_indexed"]   # the whole bill was searched
    assert len(res["hits"]) <= 10                            # respects max_hits
    # each hit is a structured object carrying the §9 payload, not a string
    assert all(isinstance(h, dict) and h.get("section_id") for h in res["hits"])


# --------------------------------------------------------------------------- #
# get_bill_section
# --------------------------------------------------------------------------- #
def test_section_populates_text_and_counts_cohere():
    res = _call(tools.get_bill_section, congress=119, bill_type="s", number=1071,
                section_id=_SECTION_ID)
    assert "summary" not in res
    # POPULATION: the statutory text lives in a structured field, non-empty
    assert isinstance(res["text"], str) and res["text"].strip()
    assert res["section_id"] == _SECTION_ID
    # COHERENCE
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed
    # children coherence: when present it is a list; each entry a structured object
    if res.get("children") is not None:
        assert isinstance(res["children"], list)
        assert all(isinstance(c, dict) and c.get("section_id") for c in res["children"])


# --------------------------------------------------------------------------- #
# get_bill_toc
# --------------------------------------------------------------------------- #
def test_toc_populates_tree_and_depth_coheres():
    res = _call(tools.get_bill_toc, congress=119, bill_type="s", number=1071, depth=5)
    assert "summary" not in res
    # POPULATION: a bill with sections must yield a non-empty toc
    assert isinstance(res["toc"], list) and len(res["toc"]) > 0
    # COHERENCE (count/collection): the toc roots are exactly the bill's top-level
    # structures -- every one represented, none invented.
    top_level = {u.section_id.split("/")[0] for u in LOADED.parsed.units}
    assert len(res["toc"]) == len(top_level)
    # `depth` is the effective depth BOUND (requested, reduced by the node cap), not a
    # measurement -- so the tree must respect it, but need not reach it.
    assert 1 <= _measured_depth(res["toc"]) <= res["depth"]
    assert res["chunks_indexed"] == len(LOADED.parsed.units)
    assert res["sections_indexed"] == LOADED.parsed.sections_indexed


# --------------------------------------------------------------------------- #
# The durable half: bill_text must never inherit the shared members/committees
# serializer (response_converters), which is where D2 lives. This guards the
# realistic future regression, not today's behavior.
# --------------------------------------------------------------------------- #
def test_bill_text_never_imports_shared_response_converters():
    pkg_dir = Path(tools.__file__).parent
    offenders: list[str] = []
    for py in sorted(pkg_dir.glob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            mods: list[str] = []
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                mods.append(node.module)
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                mods.extend(alias.name for alias in node.names)
            if any("response_converters" in m for m in mods) or any(
                n.startswith("convert_") and n.endswith("_response") for n in names
            ):
                offenders.append(f"{py.name}: {mods or names}")
    assert not offenders, (
        "bill_text imports the shared response converter -- D2's serializer. Build the "
        f"response models directly instead: {offenders}"
    )


def test_trace_is_off_unless_trace_dir_is_set(tmp_path, monkeypatch):
    # DEBUG ONLY, provably off: presence of CONGRESSMCP_TRACE_DIR is the only enable.
    monkeypatch.delenv("CONGRESSMCP_TRACE_DIR", raising=False)
    _call(tools.search_bill_text, congress=119, bill_type="s", number=1071, queries=[_QUERY], max_hits=2)
    assert not list(tmp_path.iterdir())                    # nothing written anywhere when unset


def test_trace_writes_jsonl_with_faithful_response_and_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("CONGRESSMCP_TRACE_DIR", str(tmp_path))
    live = _call(tools.search_bill_text, congress=119, bill_type="s", number=1071, queries=[_QUERY], max_hits=2)

    trace_file = tmp_path / "bill_text_trace.jsonl"
    assert trace_file.exists()
    lines = trace_file.read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["tool"] == "search_bill_text"
    assert rec["args"]["number"] == 1071 and rec["args"]["queries"] == [_QUERY]
    # FAITHFULNESS: the logged response is the object the caller received, byte for byte
    assert rec["response"] == live
    # replay stamp extends the two-fixture policy: package_id + version + source sha256
    assert rec["source"]["package_id"] == "BILLS-119s1071enr"
    assert rec["source"]["version"] == "enr"
    assert len(rec["source"]["sha256"]) == 64
    assert "ts" in rec and isinstance(rec["duration_ms"], (int, float))


def test_trace_redacts_api_key_at_write_time(tmp_path, monkeypatch):
    # A trace is what gets pasted into a bug report; a live key must never reach disk.
    # Force the key into traced content (as a query string) and assert it is redacted.
    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    monkeypatch.setenv("CONGRESSMCP_TRACE_DIR", str(tmp_path))
    _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
          queries=["icebreaker", secret], max_hits=2)
    body = (tmp_path / "bill_text_trace.jsonl").read_text()
    assert secret not in body            # no logged line matches the key
    assert "[REDACTED]" in body          # and redaction actually fired on the traced content


def test_f15_trace_mode_redacts_the_key_from_log_output_too(tmp_path, monkeypatch, caplog):
    # F15: §3 has GovInfo and congress.gov sharing one api.data.gov key, and the
    # congress.gov client sends it as a QUERY PARAMETER -- so httpx's INFO URL line
    # prints a live credential (confirmed on a live run). Redacting only the JSONL is
    # necessary-but-insufficient: a user debugging a bill-text problem attaches the
    # logs next to the trace, and the artifact the redaction rule exists to protect
    # still carries the key. Same disclosure path, same redaction.
    import logging

    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    monkeypatch.setenv("CONGRESSMCP_TRACE_DIR", str(tmp_path))
    original_factory = logging.getLogRecordFactory()
    try:
        _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
              queries=["icebreaker"], max_hits=2)
        logger = logging.getLogger("httpx")
        with caplog.at_level(logging.INFO, logger="httpx"):
            # The EXACT shape of the real leak, reproduced from httpx's own call:
            #   logger.info('HTTP Request: %s %s "%s %d %s"', method, request.url, ...)
            # request.url is an httpx.URL OBJECT, not a str. The first version of this
            # fix guarded on isinstance(value, str), so it skipped precisely this arg
            # -- and a test that passed a plain string went green while the live run
            # still printed the key. Use a real httpx.URL so the test cannot drift
            # back into asserting the easy case.
            import httpx

            url = httpx.URL(f"https://api.congress.gov/v3/bill/119/s/1071/text?api_key={secret}")
            assert not isinstance(url, str)          # the property that broke it
            logger.info('HTTP Request: %s %s "%s %d %s"', "GET", url, "HTTP/1.1", 200, "OK")
            # ... and the plain-string and msg-inline shapes still redact.
            logger.info("HTTP Request: %s", f"GET https://x/?api_key={secret}")
            logger.info("bare message carrying %s inline" % f"key={secret}")
        rendered = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in rendered
        assert "[REDACTED]" in rendered
    finally:
        logging.setLogRecordFactory(original_factory)


def test_f15_log_redaction_is_installed_regardless_of_trace_mode(monkeypatch, caplog):
    # UNCONDITIONAL by design. The key reaches INFO logs whether or not tracing is on,
    # and so does the disclosure path (logs pasted into an issue), so gating the
    # protection would remove it exactly when nobody is watching. Redaction can only
    # remove a credential from output -- there is no case where the key is wanted in a
    # log line -- so the gate bought nothing and made protection contingent on an
    # unrelated variable.
    import logging

    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.delenv("CONGRESSMCP_TRACE_DIR", raising=False)
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    assert not trace.enabled()                      # tracing is OFF
    assert trace._log_redaction_installed is True   # redaction is on anyway (import-time)
    with caplog.at_level(logging.INFO, logger="httpx"):
        logging.getLogger("httpx").info("HTTP Request: %s", f"GET https://x/?api_key={secret}")
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in rendered
    assert "[REDACTED]" in rendered


def test_f15_log_record_factory_chains_to_the_previous_one(monkeypatch):
    # setLogRecordFactory is process-global. If this package is imported into a host
    # application rather than run as a server, replacing the host's factory outright
    # silently discards whatever it adds. Pinned: a bare `def factory(...)` that
    # ignored `previous` would fail here while still passing every redaction test.
    import logging

    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    original = logging.getLogRecordFactory()
    try:
        def host_factory(*args, **kwargs):
            record = original(*args, **kwargs)
            record.host_attribute = "set-by-host"
            return record

        logging.setLogRecordFactory(host_factory)
        monkeypatch.setattr(trace, "_log_redaction_installed", False)
        trace.install_log_redaction()

        record = logging.getLogRecordFactory()(
            "n", logging.INFO, "p", 1, "key=%s", (secret,), None
        )
        assert getattr(record, "host_attribute", None) == "set-by-host"  # host survived
        assert secret not in record.getMessage()                        # and redaction ran
    finally:
        logging.setLogRecordFactory(original)
        trace._log_redaction_installed = True


def test_f4_struck_text_note_is_active_and_reaches_every_tool(monkeypatch):
    # F4 disclosure. Passive fields depend on the reader: §17 measured a consumer
    # acting on version_resolution_note while ignoring match_contexts on the SAME
    # response, so the exclusion is disclosed through the mechanism that demonstrably
    # propagates -- a response-level note, on all three tools, naming the count and
    # where the text is still readable.
    from congress_api.features.bill_text.parser import parse_bill_xml
    from congress_api.features.bill_text.service import LoadedBillText

    xml = (
        b"<bill><legis-body>"
        b'<section changed="deleted"><enum>1</enum><header>Struck</header><text>gone</text></section>'
        b"<section><enum>1</enum><header>Substitute</header><text>polar security cutter</text></section>"
        b"</legis-body></bill>"
    )
    parsed = parse_bill_xml(xml, PKG, "rs", None)
    loaded = LoadedBillText(
        resolved=ResolvedBillText(PKG, "rs", "2026-08-08T00:00:00Z", None, None, xml),
        parsed=parsed, index=BillTextIndex(parsed),
        timing={"fetch_ms": 0.0, "parse_ms": 0.0, "index_ms": 0.0},
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools, "load_bill_text", fake_load)

    for call, kwargs in (
        (tools.search_bill_text, {"queries": ["polar security cutter"]}),
        (tools.get_bill_section, {"section_id": "1"}),
        (tools.get_bill_toc, {}),
    ):
        res = asyncio.run(call(_Ctx(), congress=119, bill_type="s", number=4726, **kwargs))
        note = res["struck_text_note"]
        assert note, f"{call.__name__} did not disclose the exclusion"
        assert "1 section(s) struck" in note
        assert "version=" in note                  # says where the text is still readable

    # Null -- not absent, and not a zero-count sentence -- when nothing was struck.
    # A note that fires on documents with nothing to disclose trains the reader to
    # skip it, which is how the passive-field failure starts.
    clean = _call(tools.get_bill_toc, congress=119, bill_type="s", number=1071, depth=2)
    assert "struck_text_note" in clean and clean["struck_text_note"] is None


def test_f15_traceback_channel_is_redacted_including_under_rich(monkeypatch):
    # Residual 1: a TRACEBACK does not pass through msg/args, so the record-factory
    # redaction misses it. Reachable for real -- httpx's raise_for_status embeds the
    # full request URL in its message, and the congress.gov client sends the key as a
    # query parameter (§11), so logger.exception renders a live credential.
    import io
    import logging

    import httpx

    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    request = httpx.Request("GET", f"https://api.congress.gov/v3/x?api_key={secret}")
    try:
        httpx.Response(500, request=request).raise_for_status()
    except httpx.HTTPStatusError:
        import sys

        exc_info = sys.exc_info()
        # Precondition: the traceback carries the key -- in URL-ENCODED form, which
        # is exactly the shape a literal substring match would sail past.
        rendered_tb = "".join(__import__("traceback").format_exception(*exc_info))
        assert quote(secret, safe="") in rendered_tb
        record = logging.getLogRecordFactory()(
            "n", logging.ERROR, "p", 1, "Unexpected error in %s", ("get_bill_section",), exc_info
        )

    # stdlib formatter path: honors the pre-set exc_text
    rendered = logging.Formatter("%(message)s").format(record)
    assert secret not in rendered and quote(secret, safe="") not in rendered

    # rich path: renders exc_info DIRECTLY and ignores exc_text, so exc_text alone
    # would pass the assertion above and still leak in this server's actual output.
    rich_logging = pytest.importorskip("rich.logging")
    from rich.console import Console

    buffer = io.StringIO()
    handler = rich_logging.RichHandler(
        console=Console(file=buffer, width=250), rich_tracebacks=True, show_path=False
    )
    handler.emit(record)
    assert secret not in buffer.getvalue() and quote(secret, safe="") not in buffer.getvalue()


def test_f15_error_envelope_never_carries_the_key_to_the_caller(monkeypatch):
    # Residual 2, and the worse one: an error envelope reaches the CALLER, not just
    # the operator. _unexpected interpolates the exception into `message`, and
    # httpx's raise_for_status message embeds the key-bearing URL.
    import httpx

    secret = "SüP3rSecretKeyValue0123456789"
    monkeypatch.setenv("CONGRESS_API_KEY", secret)
    request = httpx.Request("GET", f"https://api.congress.gov/v3/x?api_key={secret}")
    try:
        httpx.Response(500, request=request).raise_for_status()
    except httpx.HTTPStatusError as exc:
        assert quote(secret, safe="") in str(exc)       # precondition: carried, URL-encoded
        envelope = tools._unexpected("get_bill_section", exc)

    # ensure_ascii=False deliberately: the default ESCAPES non-ASCII (ü -> ü), so
    # `secret not in json.dumps(x)` is vacuously true for a non-ASCII secret whether or
    # not redaction ran. That assertion passed against an unredacted envelope.
    def _leaks(payload) -> bool:
        body = json.dumps(payload, ensure_ascii=False)
        return secret in body or quote(secret, safe="") in body

    assert not _leaks(envelope)
    assert "[REDACTED]" in envelope["error"]["message"]

    # _unexpected alone does not prove the guarantee: logger.exception runs first and
    # redacts the exception's args in place, so the envelope comes out clean even with
    # _error's redaction removed. That safety is an ORDERING accident -- reorder the
    # log call after the return and it leaks. Exercise the construction point directly,
    # which is where the durable guarantee lives, covering every error path including
    # future ones.
    for form in (secret, quote(secret, safe="")):
        other = tools._error("x", f"m {form}", {"url": f"u {form}", "n": 1}, f"r {form}")
        assert not _leaks(other)
        assert other["error"]["detail"]["n"] == 1       # non-strings pass through intact


def test_f15_log_redaction_never_breaks_logging(monkeypatch):
    # An unconditional process-global factory that raises would take down the host's
    # logging entirely. Losing redaction on one line beats that, so failure falls back
    # to the unredacted record.
    import logging

    monkeypatch.setattr(trace, "_secret_values", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    record = logging.getLogRecordFactory()("n", logging.INFO, "p", 1, "still logged", (), None)
    assert record.getMessage() == "still logged"


@pytest.mark.parametrize("fn", [tools.search_bill_text, tools.get_bill_section, tools.get_bill_toc])
def test_new_tools_params_are_keyword_only(fn):
    # Freeze-now: every param except ctx is keyword-only, so argument ORDER can never
    # ossify into a contract callers depend on (a reorder would otherwise be breaking).
    # Scoped to the new bill-text tools by design. MCP passes args by name, so this is a
    # Python-level guard with zero wire impact -- the input schema is unchanged.
    params = list(inspect.signature(fn).parameters.values())
    assert params[0].name == "ctx"
    offenders = [p.name for p in params[1:] if p.kind is not inspect.Parameter.KEYWORD_ONLY]
    assert not offenders, f"{fn.__name__}: params not keyword-only: {offenders}"


@pytest.mark.parametrize("missing", ["hits", "text", "toc"])
def test_conformance_fields_are_the_ones_that_matter(missing):
    # Guards the guard: if these payload keys are renamed, the population checks above
    # would silently pass on .get(); pin the names the assertions depend on.
    shapes = {
        "hits": _call(tools.search_bill_text, congress=119, bill_type="s", number=1071,
                      queries=[_QUERY], max_hits=10),
        "text": _call(tools.get_bill_section, congress=119, bill_type="s", number=1071,
                      section_id=_SECTION_ID),
        "toc": _call(tools.get_bill_toc, congress=119, bill_type="s", number=1071, depth=5),
    }
    assert missing in shapes[missing]


def test_bill_text_only_env_parsing(monkeypatch):
    import congress_api.mcp_server as srv

    monkeypatch.delenv("CONGRESSMCP_BILL_TEXT_ONLY", raising=False)
    assert srv._bill_text_only() is False
    for val in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CONGRESSMCP_BILL_TEXT_ONLY", val)
        assert srv._bill_text_only() is True
    for val in ("", "0", "false", "no"):
        monkeypatch.setenv("CONGRESSMCP_BILL_TEXT_ONLY", val)
        assert srv._bill_text_only() is False


def test_bill_text_only_isolation_registers_just_the_three():
    # The three tools are self-sufficient (version resolution + GovInfo fetch are
    # internal), so CONGRESSMCP_BILL_TEXT_ONLY yields a standalone bill-text server.
    # Run in a fresh interpreter: tool registration accumulates on the module singleton,
    # so isolation can only be asserted from a clean process.
    import os
    import subprocess
    import sys
    import textwrap

    repo = Path(__file__).resolve().parent.parent
    script = textwrap.dedent(
        """
        import asyncio
        from congress_api.mcp_server import initialize_mcp_features, mcp
        initialize_mcp_features()
        async def main():
            print("TOOLS:" + ",".join(sorted(t.name for t in await mcp.list_tools())))
        asyncio.run(main())
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(repo),
        env={**os.environ, "CONGRESSMCP_BILL_TEXT_ONLY": "1"},
    )
    line = next((l for l in result.stdout.splitlines() if l.startswith("TOOLS:")), None)
    assert line == "TOOLS:get_bill_section,get_bill_toc,search_bill_text", result.stdout + result.stderr
