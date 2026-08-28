"""A7 timing gate (fulltext §4 Amendment A7, Addendum 4 item 3).

``timing`` is emitted only when CONGRESSMCP_VERBOSE is set to any non-empty
value in the server environment, on every tool that emits a timing block.
It is the one telemetry block that is purely performance and never
load-bearing for correctness; ``cache``, ``version_resolution*``, and the
diagnostic-on-failure notes stay always-on -- asserted here so the gate can
never widen silently.

Contract tests per the item: env unset -> no ``timing`` KEY (absent, not
null) on any tool response that previously carried one; env set -> ``timing``
present with the A6 cold/warm split intact.

Run with: pytest tests/test_bill_text_timing_gate.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

import congress_api.features.bill_text.client as client_mod
import congress_api.features.bill_text.service as service_mod
import congress_api.features.bill_text.tools as tools_mod
from congress_api.features.bill_text import cache
from congress_api.features.bill_text.client import TextVersion

FIXTURES = Path(__file__).parent / "fixtures"
XML = (FIXTURES / "bill_text_trimmed.xml").read_bytes()
LM = "2025-12-19T03:11:48Z"


class FakeGovInfo:
    async def resolve(self, ctx, congress, bill_type, number):
        return [TextVersion("enr", "2025-12-19", "Enrolled Bill")]

    async def fetch(self, package_id, *, skip_download=None):
        if skip_download is not None and skip_download(package_id, LM):
            return LM, None
        return LM, XML


@pytest.fixture
def offline_tools(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    monkeypatch.delenv("CONGRESSMCP_VERBOSE", raising=False)
    service_mod.reset_store()
    fake = FakeGovInfo()
    monkeypatch.setattr(client_mod, "_resolve_versions", fake.resolve)
    monkeypatch.setattr(client_mod, "fetch_govinfo_package", fake.fetch)
    monkeypatch.setattr(service_mod, "fetch_govinfo_package", fake.fetch)
    yield monkeypatch
    service_mod.reset_store()


async def _all_three():
    search = await tools_mod.search_bill_text.__wrapped__(
        None, congress=119, bill_type="s", number=1071,
        queries=["polar security cutter"])
    section = await tools_mod.get_bill_section.__wrapped__(
        None, congress=119, bill_type="s", number=1071, section_id="D:A/T:I/S:101")
    toc = await tools_mod.get_bill_toc.__wrapped__(
        None, congress=119, bill_type="s", number=1071)
    return {"search_bill_text": search, "get_bill_section": section,
            "get_bill_toc": toc}


@pytest.mark.asyncio
async def test_env_unset_no_timing_key_on_any_tool(offline_tools):
    for name, response in (await _all_three()).items():
        assert "error" not in response, (name, response)
        # Absent, not null: a consumer keying on the field's presence must
        # see the pre-A7 shape minus the key.
        assert "timing" not in response, name
        # The always-on telemetry stays: diagnostic blocks are not gated.
        assert "cache" in response, name
        assert "version_resolution" in response, name


@pytest.mark.asyncio
async def test_env_set_timing_present_with_the_a6_split(offline_tools):
    offline_tools.setenv("CONGRESSMCP_VERBOSE", "1")
    responses = await _all_three()
    for name, response in responses.items():
        assert "error" not in response, (name, response)
        timing = response["timing"]
        assert timing is not None, name
        # The §9/A6 split fields all present (each may be null per leg).
        for key in ("resolve_ms", "download_ms", "parse_ms", "index_ms",
                    "search_ms", "total_ms"):
            assert key in timing, (name, key)
        assert timing["total_ms"] is not None, name
    # search_ms carried only by search_bill_text (the A6 rule, intact).
    assert responses["search_bill_text"]["timing"]["search_ms"] is not None
    assert responses["get_bill_toc"]["timing"]["search_ms"] is None


@pytest.mark.asyncio
async def test_gate_reads_the_environment_per_call(offline_tools):
    # A long-lived server picks up an env change without restart: unset ->
    # gated; set -> emitted; unset again -> gated, all in one process.
    first = await tools_mod.get_bill_toc.__wrapped__(
        None, congress=119, bill_type="s", number=1071)
    assert "timing" not in first
    offline_tools.setenv("CONGRESSMCP_VERBOSE", "yes")
    second = await tools_mod.get_bill_toc.__wrapped__(
        None, congress=119, bill_type="s", number=1071)
    assert "timing" in second
    offline_tools.delenv("CONGRESSMCP_VERBOSE")
    third = await tools_mod.get_bill_toc.__wrapped__(
        None, congress=119, bill_type="s", number=1071)
    assert "timing" not in third


@pytest.mark.asyncio
async def test_empty_string_env_value_means_unset(offline_tools):
    # "any non-empty value" is the contract; empty string is not set.
    offline_tools.setenv("CONGRESSMCP_VERBOSE", "")
    response = await tools_mod.get_bill_section.__wrapped__(
        None, congress=119, bill_type="s", number=1071, section_id="D:A/T:I/S:101")
    assert "timing" not in response
