"""Spec §2 trace addendum (2026-08-24): a traced search_bills run must show
the assembled upstream query, the upstream outcome, the canary firing and
its branch, and any fallback demotion with its trigger class -- one traced
call per §6.4 row shows the row that fired. The key never reaches a trace
record.
"""
import json
import os
import sys
from unittest.mock import AsyncMock, patch

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("CONGRESS_API_KEY", "test-key-govinfo-search")

from congress_api.features.buckets.bills import api as mod  # noqa: E402


class FakeContext:
    async def info(self, *_):
        pass

    async def error(self, *_):
        pass


@pytest.fixture(autouse=True)
def _keyed(monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    monkeypatch.setattr(client_mod, "API_KEY", "sekret-key-12345")


@pytest.fixture
def trace_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CONGRESSMCP_TRACE_DIR", str(tmp_path))
    return tmp_path


class FakeSearchResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {
            "count": 0, "results": [], "offsetMark": None}

    def json(self):
        return self._payload


def _last_record(trace_dir):
    lines = (trace_dir / "bill_text_trace.jsonl").read_text().splitlines()
    assert lines, "no trace record written"
    return json.loads(lines[-1]), lines[-1]


async def _run(post_effect, **kwargs):
    post = AsyncMock(side_effect=post_effect)
    fetch = AsyncMock(return_value={"bills": []})
    with patch.object(mod, "govinfo_search_post", post), \
            patch.object(mod, "fetch_bill_data", fetch):
        await mod.search_bills(FakeContext(), **kwargs)


@pytest.mark.asyncio
async def test_traced_row_200(trace_dir):
    await _run([FakeSearchResponse(200)], keywords="RECA", congress=119)
    record, raw = _last_record(trace_dir)
    flow = record["flow"]
    assert flow["upstream_query"] == "RECA collection:bills congress:119"
    assert flow["outcome"] == "http_200"
    assert flow["canary"] is None
    assert flow["fallback_trigger"] is None
    assert record["tool"] == "search_bills"
    assert "sekret" not in raw            # key never reaches a record


@pytest.mark.asyncio
async def test_traced_row_500_canary_succeeds(trace_dir):
    await _run([FakeSearchResponse(500), FakeSearchResponse(200)],
               keywords="odd )( input")
    record, _ = _last_record(trace_dir)
    flow = record["flow"]
    assert flow["outcome"] == "http_500"
    assert flow["canary"] == {"fired": True, "result": "http_200",
                              "branch": "query_error"}
    assert flow["fallback_trigger"] is None


@pytest.mark.asyncio
async def test_traced_row_500_canary_fails(trace_dir):
    await _run([FakeSearchResponse(500), FakeSearchResponse(503)],
               keywords="climate")
    flow = _last_record(trace_dir)[0]["flow"]
    assert flow["outcome"] == "http_500"
    assert flow["canary"]["branch"] == "fallback"
    assert flow["canary"]["result"] == "http_503"
    assert flow["fallback_trigger"] == "govinfo_search_error"


@pytest.mark.asyncio
async def test_traced_row_unreachable(trace_dir):
    await _run([httpx.ConnectError("down")], keywords="climate")
    flow = _last_record(trace_dir)[0]["flow"]
    assert flow["outcome"] == "transport_error:ConnectError"
    assert flow["canary"] is None
    assert flow["fallback_trigger"] == "govinfo_unreachable"


@pytest.mark.asyncio
async def test_traced_row_429(trace_dir):
    await _run([FakeSearchResponse(429)], keywords="climate")
    flow = _last_record(trace_dir)[0]["flow"]
    assert flow["outcome"] == "http_429"
    assert flow["canary"] is None
    assert flow["fallback_trigger"] == "govinfo_rate_limited"


@pytest.mark.asyncio
async def test_traced_row_keyless(trace_dir, monkeypatch):
    from congress_api.features.bill_text import client as client_mod
    monkeypatch.setattr(client_mod, "API_KEY", None)
    await _run([], keywords="climate")
    flow = _last_record(trace_dir)[0]["flow"]
    assert flow["outcome"] == "keyless"
    assert flow["fallback_trigger"] is None


@pytest.mark.asyncio
async def test_untraced_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("CONGRESSMCP_TRACE_DIR", raising=False)
    await _run([FakeSearchResponse(200)], keywords="RECA")
    assert not (tmp_path / "bill_text_trace.jsonl").exists()
