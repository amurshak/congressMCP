"""Freshness and offline resolution (spec §10 freshness table, verbatim):

| Explicit version=, index cached | serve from cache; revalidate via /summary lastModified only past CONGRESSMCP_REVALIDATE_DAYS; rebuild if changed |
| version=None, resolution within CONGRESSMCP_VERSION_TTL | cached resolution, no network; version_resolution "cached" |
| version=None, TTL expired | re-resolve |
| version=None, network unavailable | last resolution, "cached_offline" + version_resolved_at disclosed |
| version=None, no cached resolution, no network | version_resolution_unavailable listing cached versions |
| package reissued (lastModified changed) | discard and rebuild |

Plus cache.version_hit live and the §9 timing split (resolve_ms / download_ms,
each null when that leg did not run).

Run with: pytest tests/test_bill_text_freshness.py
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import httpx
import pytest

import congress_api.features.bill_text.client as client_mod
import congress_api.features.bill_text.service as service_mod
import congress_api.features.bill_text.tools as tools_mod
from congress_api.features.bill_text import cache
from congress_api.features.bill_text.client import BillTextError, TextVersion
from congress_api.features.bill_text.models import Timing

FIXTURES = Path(__file__).parent / "fixtures"
XML = (FIXTURES / "bill_text_trimmed.xml").read_bytes()
LM = "2025-12-19T03:11:48Z"
PID = "BILLS-119s1071enr"


class FakeGovInfo:
    """congress.gov resolution + GovInfo fetch double. Honors skip_download like
    the real client, reports a download leg into DOWNLOAD_SECONDS, and can be
    switched offline (every network call raises a transport/unavailable error)."""

    def __init__(self):
        self.last_modified = LM
        self.offline = False
        self.resolves = 0
        self.summaries = 0
        self.downloads = 0

    async def resolve(self, ctx, congress, bill_type, number):
        self.resolves += 1
        if self.offline:
            raise BillTextError("congress_unavailable", "offline", None, "retry")
        return [TextVersion("enr", "2025-12-19", "Enrolled Bill")]

    async def fetch(self, package_id, *, skip_download=None):
        if self.offline:
            raise httpx.ConnectError("offline")
        self.summaries += 1
        if skip_download is not None and skip_download(package_id, self.last_modified):
            return self.last_modified, None
        self.downloads += 1
        client_mod.DOWNLOAD_SECONDS.set((client_mod.DOWNLOAD_SECONDS.get() or 0.0) + 0.002)
        return self.last_modified, XML


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    monkeypatch.delenv(cache.ENV_CACHE_ENABLED, raising=False)
    monkeypatch.delenv(cache.ENV_VERSION_TTL, raising=False)
    monkeypatch.delenv(cache.ENV_REVALIDATE_DAYS, raising=False)
    service_mod.reset_store()
    yield tmp_path / "cache"
    service_mod.reset_store()


@pytest.fixture
def govinfo(monkeypatch, env):
    fake = FakeGovInfo()
    monkeypatch.setattr(client_mod, "_resolve_versions", fake.resolve)
    monkeypatch.setattr(client_mod, "fetch_govinfo_package", fake.fetch)
    monkeypatch.setattr(service_mod, "fetch_govinfo_package", fake.fetch)
    return fake


def age_resolution(seconds: float) -> None:
    m = service_mod.get_store().manifest()
    res = m.get_resolution(119, "s", 1071)
    m.put_resolution(dataclasses.replace(res, resolved_at=res.resolved_at - seconds))


def age_package(package_id: str, seconds: float) -> None:
    m = service_mod.get_store().manifest()
    row = m.get(package_id)
    m.set_created_at(package_id, row.created_at - seconds)


async def load(version=None):
    loaded = await service_mod.load_bill_text(None, 119, "s", 1071, version)
    loaded.index.close()
    return loaded


# ---------------------------------------------------------------------------
# version=None: TTL rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cached_resolution_within_ttl_needs_no_network(govinfo):
    cold = await load()
    assert (cold.version_resolution, cold.version_hit, cold.index_hit) == ("fresh", False, False)
    assert (govinfo.resolves, govinfo.summaries, govinfo.downloads) == (1, 1, 1)
    warm = await load()
    assert (warm.version_resolution, warm.version_hit, warm.index_hit) == ("cached", True, True)
    assert (govinfo.resolves, govinfo.summaries, govinfo.downloads) == (1, 1, 1), "no network at all"
    assert warm.timing == {"resolve_ms": None, "download_ms": None, "parse_ms": None, "index_ms": None}
    assert warm.resolved.version == "enr" and warm.resolved.package_id == PID
    assert warm.resolved.version_resolved_at == cold.resolved.version_resolved_at, "the cached resolution's timestamp"
    assert warm.resolved.last_modified == LM, "from the package's stored document row"
    assert warm.resolved.version_resolution_note is None
    # The package row records it was reached via a version=None resolution.
    row = service_mod.get_store().manifest().get(PID)
    assert row.resolved_from_version_query is True and row.version_resolved_at is not None


@pytest.mark.asyncio
async def test_ttl_expired_re_resolves(govinfo):
    await load()
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)
    again = await load()
    assert again.version_resolution == "fresh" and again.version_hit is False
    assert govinfo.resolves == 2 and govinfo.summaries == 2
    assert govinfo.downloads == 1 and again.index_hit is True, "index still fresh at the same lastModified"
    assert again.timing["resolve_ms"] is not None and again.timing["download_ms"] is None


@pytest.mark.asyncio
async def test_ttl_from_env(govinfo, monkeypatch):
    monkeypatch.setenv(cache.ENV_VERSION_TTL, "0")
    service_mod.reset_store()
    await load()
    age_resolution(1)
    await load()
    assert govinfo.resolves == 2


@pytest.mark.asyncio
async def test_reissue_after_ttl_discards_and_rebuilds(govinfo):
    await load()
    govinfo.last_modified = "2026-03-03T00:00:00Z"
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)
    rebuilt = await load()
    assert rebuilt.index_hit is False and govinfo.downloads == 2
    assert rebuilt.resolved.last_modified == "2026-03-03T00:00:00Z"
    assert rebuilt.timing["download_ms"] is not None and rebuilt.timing["parse_ms"] is not None


@pytest.mark.asyncio
async def test_cached_resolution_with_evicted_index_refetches_the_document(govinfo):
    await load()
    service_mod.get_store().layout.package_path(PID).unlink()  # evicted / cleared
    again = await load()
    assert again.version_resolution == "cached" and again.version_hit is True
    assert again.index_hit is False and govinfo.resolves == 1 and govinfo.downloads == 2
    assert again.timing["resolve_ms"] is None or again.timing["resolve_ms"] >= 0  # summary leg only
    assert again.timing["download_ms"] is not None


# ---------------------------------------------------------------------------
# version=None: offline rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offline_with_expired_resolution_serves_cached_offline_and_discloses(govinfo):
    cold = await load()
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)
    govinfo.offline = True
    off = await load()
    assert off.version_resolution == "cached_offline" and off.version_hit is True and off.index_hit is True
    assert off.resolved.version_resolved_at == cold.resolved.version_resolved_at
    assert "cached result" in off.resolved.version_resolution_note
    assert cold.resolved.version_resolved_at in off.resolved.version_resolution_note
    assert "newer version may exist" in off.resolved.version_resolution_note
    assert off.timing == {"resolve_ms": None, "download_ms": None, "parse_ms": None, "index_ms": None}


@pytest.mark.asyncio
async def test_offline_with_expired_resolution_but_no_index_raises_the_network_error(govinfo):
    await load()
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)
    service_mod.get_store().layout.package_path(PID).unlink()
    govinfo.offline = True
    with pytest.raises(BillTextError) as info:
        await load()
    assert info.value.code == "congress_unavailable"


@pytest.mark.asyncio
async def test_offline_with_no_resolution_errors_listing_cached_versions(govinfo):
    # Only an explicit-version package is cached (no version=None resolution).
    await load(version="enr")
    govinfo.offline = True
    with pytest.raises(BillTextError) as info:
        await load()
    err = info.value
    assert err.code == "version_resolution_unavailable"
    assert err.detail["cached_versions"] == ["enr"]
    assert err.detail["cause"] == "congress_unavailable"
    assert "version=" in err.remediation
    # And the tool renders it as a §9 error envelope.
    resp = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=1)
    assert resp["error"]["code"] == "version_resolution_unavailable"
    assert resp["error"]["detail"]["cached_versions"] == ["enr"]


@pytest.mark.asyncio
async def test_offline_with_nothing_cached_lists_no_versions(govinfo):
    govinfo.offline = True
    with pytest.raises(BillTextError) as info:
        await load()
    assert info.value.code == "version_resolution_unavailable"
    assert info.value.detail["cached_versions"] == []


@pytest.mark.asyncio
async def test_transport_errors_count_as_offline(govinfo, monkeypatch):
    await load()
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)

    async def boom(ctx, congress, bill_type, number):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(client_mod, "_resolve_versions", boom)
    off = await load()
    assert off.version_resolution == "cached_offline"


@pytest.mark.asyncio
async def test_not_found_is_not_offline(govinfo, monkeypatch):
    await load()
    age_resolution(cache.DEFAULT_VERSION_TTL_SECONDS + 1)

    async def gone(ctx, congress, bill_type, number):
        raise BillTextError("bill_not_found", "no such bill", None, "check")

    monkeypatch.setattr(client_mod, "_resolve_versions", gone)
    with pytest.raises(BillTextError) as info:
        await load()
    assert info.value.code == "bill_not_found", "a definitive answer is not served from a stale resolution"


# ---------------------------------------------------------------------------
# Explicit version rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_version_cached_is_served_offline_with_no_network(govinfo):
    first = await load(version="enr")
    assert first.index_hit is False and govinfo.resolves == 1
    # "pinned" on EVERY explicit-version call (§10 ruling): the caller named
    # the version, so neither a fresh nor a cached resolution occurred.
    assert (first.version_resolution, first.version_hit) == ("pinned", False)
    govinfo.offline = True
    second = await load(version="enr")
    assert second.index_hit is True
    assert (second.version_resolution, second.version_hit) == ("pinned", False), "no resolution happened"
    assert second.timing == {"resolve_ms": None, "download_ms": None, "parse_ms": None, "index_ms": None}
    assert second.resolved.last_modified == LM
    assert govinfo.resolves == 1, "explicit cached version: no network at all"


@pytest.mark.asyncio
async def test_explicit_version_case_insensitive(govinfo):
    await load(version="enr")
    govinfo.offline = True
    assert (await load(version="ENR")).index_hit is True


@pytest.mark.asyncio
async def test_explicit_revalidation_after_revalidate_days_unchanged(govinfo):
    await load(version="enr")
    age_package(PID, cache.DEFAULT_REVALIDATE_DAYS * 86400 + 60)
    reval = await load(version="enr")
    assert reval.index_hit is True
    assert govinfo.summaries == 2 and govinfo.downloads == 1, "one summary call, no download"
    assert reval.timing["resolve_ms"] is not None and reval.timing["download_ms"] is None
    # The clock restarted: the next call is silent again.
    await load(version="enr")
    assert govinfo.summaries == 2


@pytest.mark.asyncio
async def test_explicit_revalidation_detects_reissue_and_rebuilds(govinfo):
    await load(version="enr")
    age_package(PID, cache.DEFAULT_REVALIDATE_DAYS * 86400 + 60)
    govinfo.last_modified = "2026-04-04T00:00:00Z"
    rebuilt = await load(version="enr")
    assert rebuilt.index_hit is False and govinfo.downloads == 2
    assert rebuilt.resolved.last_modified == "2026-04-04T00:00:00Z"


@pytest.mark.asyncio
async def test_explicit_revalidation_offline_serves_the_cached_copy(govinfo, caplog):
    await load(version="enr")
    age_package(PID, cache.DEFAULT_REVALIDATE_DAYS * 86400 + 60)
    govinfo.offline = True
    served = await load(version="enr")
    assert served.index_hit is True and served.resolved.last_modified == LM


@pytest.mark.asyncio
async def test_revalidate_days_from_env(govinfo, monkeypatch):
    monkeypatch.setenv(cache.ENV_REVALIDATE_DAYS, "0")
    service_mod.reset_store()
    await load(version="enr")
    age_package(PID, 1)
    await load(version="enr")
    assert govinfo.summaries == 2


@pytest.mark.asyncio
async def test_cache_disabled_never_caches_resolution(govinfo, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_ENABLED, "false")
    service_mod.reset_store()
    for _ in range(2):
        loaded = await load()
        assert (loaded.version_resolution, loaded.version_hit, loaded.index_hit) == ("fresh", False, False)
    assert govinfo.resolves == 2 and govinfo.downloads == 2


# ---------------------------------------------------------------------------
# Wire: timing split and cache block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timing_split_and_cache_block_on_the_wire(govinfo):
    cold = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=1)
    assert cold["version_resolution"] == "fresh"
    assert cold["cache"] == {"index_hit": False, "version_hit": False}
    t = cold["timing"]
    assert set(t) == {"resolve_ms", "download_ms", "parse_ms", "index_ms", "search_ms", "total_ms"}
    assert "fetch_ms" not in t
    assert t["resolve_ms"] is not None and t["download_ms"] is not None and t["parse_ms"] is not None and t["index_ms"] is not None
    warm = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=1)
    assert warm["version_resolution"] == "cached"
    assert warm["cache"] == {"index_hit": True, "version_hit": True}
    assert warm["timing"]["resolve_ms"] is None and warm["timing"]["download_ms"] is None
    assert warm["timing"]["parse_ms"] is None and warm["timing"]["index_ms"] is None
    assert warm["timing"]["total_ms"] >= 0
    json.dumps(warm)
    Timing(**warm["timing"])
    pinned = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=1, version="enr")
    assert pinned["version_resolution"] == "pinned"
    assert pinned["cache"] == {"index_hit": True, "version_hit": False}
    assert pinned["version_resolution_note"] is None
