"""Eviction and leases (spec §10): 500 MB cap across packages/, LRU by
last_accessed_at, sum of actual stat sizes, never the package being served in
the current call, best-effort cross-process lease, Windows skip-and-proceed,
never fail the user's call.

Run with: pytest tests/test_bill_text_eviction.py
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

import congress_api.features.bill_text.service as service_mod
from congress_api.features.bill_text import cache
from congress_api.features.bill_text.parser import parse_bill_xml
from congress_api.features.bill_text.store import PackageStore

FIXTURES = Path(__file__).parent / "fixtures"
XML = (FIXTURES / "bill_text_trimmed.xml").read_bytes()
LM = "2025-12-19T03:11:48Z"


def parsed_for(package_id: str):
    return parse_bill_xml(XML, package_id, "enr", LM)


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    monkeypatch.delenv(cache.ENV_CACHE_ENABLED, raising=False)
    service_mod.reset_store()
    yield tmp_path / "cache"
    service_mod.reset_store()


def make_store(max_bytes: int) -> PackageStore:
    settings = cache.CacheSettings.from_env()
    settings = cache.CacheSettings(cache_dir=settings.cache_dir, max_bytes=max_bytes)
    return PackageStore(settings, reconcile=False)


def publish(store: PackageStore, package_id: str, accessed_at: float | None = None) -> Path:
    index, _ = store.build_and_publish(parsed_for(package_id), last_modified=LM)
    index.close()
    if accessed_at is not None:
        store.manifest().touch(package_id, accessed_at)
    return store.layout.package_path(package_id)


def one_file_size(tmp_path) -> int:
    probe = PackageStore(cache.CacheSettings(cache_dir=tmp_path / "probe", max_bytes=10**12), reconcile=False)
    path = publish(probe, "BILLS-119s9")
    size = path.stat().st_size
    probe.close()
    return size


def present(store: PackageStore) -> list[str]:
    return sorted(cache.parse_package_filename(p.name).package_id for p in store.layout.package_files())


# ---------------------------------------------------------------------------
# LRU under a cap, stat sizes, protection of the served package
# ---------------------------------------------------------------------------


def test_after_each_publish_evict_oldest_until_under_cap(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))  # room for two files, not three
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    assert present(store) == ["BILLS-119s1", "BILLS-119s2"]
    publish(store, "BILLS-119s3")  # third write -> over cap -> evict LRU (s1)
    assert present(store) == ["BILLS-119s2", "BILLS-119s3"]
    report = store.last_eviction
    assert report.evicted == ["BILLS-119s1"] and report.skipped_protected == []
    assert report.total_after <= report.cap < report.total_before
    assert store.manifest().get("BILLS-119s1") is None
    assert store.layout.total_bytes() <= store.settings.max_bytes


def test_lru_is_by_last_accessed_not_creation(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    # A hit on the older file bumps it: open() touches last_accessed_at.
    idx = store.open("BILLS-119s1", LM)
    idx.close()
    publish(store, "BILLS-119s3")
    assert present(store) == ["BILLS-119s1", "BILLS-119s3"], "s2 was least recently ACCESSED"


def test_total_is_stat_sizes_not_manifest_rows(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    for pid in ("BILLS-119s1", "BILLS-119s2"):
        store.manifest().set_bytes(pid, 1)  # lying rows
    publish(store, "BILLS-119s3")
    assert store.last_eviction.evicted == ["BILLS-119s1"], "stat said over cap even though rows said 3 bytes"


def test_never_evicts_the_package_being_served_even_when_it_alone_exceeds_cap(root, tmp_path, caplog):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=size // 2)  # a single package is over the cap alone
    with caplog.at_level(logging.WARNING, logger="congress_api.features.bill_text.store"):
        index, published = store.build_and_publish(parsed_for("BILLS-119s1"), last_modified=LM)
    assert published and index.search(["icebreaker"], 3)  # served
    index.close()
    report = store.last_eviction
    assert report.skipped_protected == ["BILLS-119s1"] and report.evicted == []
    assert report.over_cap
    assert store.layout.package_path("BILLS-119s1").exists()
    assert any("still over cap" in r.message for r in caplog.records)
    # The next write evicts it (it is then the LRU and no longer protected).
    publish(store, "BILLS-119s2")
    assert present(store) == ["BILLS-119s2"]


def test_under_cap_is_a_noop_without_touching_the_manifest(root, tmp_path, monkeypatch):
    store = make_store(max_bytes=10**12)
    publish(store, "BILLS-119s1")
    calls = []
    monkeypatch.setattr(cache.Manifest, "rows", lambda self: (calls.append(1), [])[1])
    report = store.evict()
    assert report.evicted == [] and calls == []


# ---------------------------------------------------------------------------
# Leases
# ---------------------------------------------------------------------------


def test_hit_and_publish_take_a_lease(root, tmp_path):
    store = make_store(max_bytes=10**12)
    publish(store, "BILLS-119s1")
    row = store.manifest().get("BILLS-119s1")
    assert row.lease_holder == store.holder
    assert row.lease_expires_at is not None and row.lease_expires_at - time.time() <= cache.LEASE_TTL_SECONDS + 1
    assert row.lease_expires_at > time.time() + cache.LEASE_TTL_SECONDS - 60


def test_another_processes_unexpired_lease_protects_expired_does_not(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    now = time.time()
    store.manifest().lease("BILLS-119s1", "other-process:abcd", now + 200)   # live, someone else's
    store.manifest().lease("BILLS-119s2", "other-process:abcd", now - 5)     # expired
    publish(store, "BILLS-119s3")
    report = store.last_eviction
    assert report.skipped_leased == ["BILLS-119s1"]
    assert report.evicted == ["BILLS-119s2"]
    assert present(store) == ["BILLS-119s1", "BILLS-119s3"]


def test_own_lease_does_not_block_own_eviction(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    store.manifest().lease("BILLS-119s1", store.holder, time.time() + 200)
    publish(store, "BILLS-119s3")
    assert store.last_eviction.evicted == ["BILLS-119s1"]


# ---------------------------------------------------------------------------
# Windows skip-and-proceed; never fail the call
# ---------------------------------------------------------------------------


def test_unlink_refused_skips_that_candidate_and_moves_on(root, tmp_path, monkeypatch):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    p1 = publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    real_unlink = Path.unlink

    def locked_unlink(self, *a, **kw):
        if self == p1:
            raise PermissionError(32, "being used by another process")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", locked_unlink)
    publish(store, "BILLS-119s3")
    report = store.last_eviction
    assert report.skipped_locked == ["BILLS-119s1"] and report.evicted == ["BILLS-119s2"]
    assert p1.exists() and store.manifest().get("BILLS-119s1") is not None, "locked candidate kept, with its row"


def test_all_candidates_locked_proceeds_over_cap_and_logs(root, tmp_path, monkeypatch, caplog):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 1.5))
    publish(store, "BILLS-119s1", accessed_at=1000.0)
    real_unlink = Path.unlink
    monkeypatch.setattr(Path, "unlink", lambda self, *a, **kw: (_ for _ in ()).throw(PermissionError(32, "in use")) if self.name.endswith(".db") else real_unlink(self, *a, **kw))
    with caplog.at_level(logging.WARNING, logger="congress_api.features.bill_text.store"):
        index, published = store.build_and_publish(parsed_for("BILLS-119s2"), last_modified=LM)
    assert published and index.parsed.units  # the call succeeded
    index.close()
    assert store.last_eviction.over_cap and store.last_eviction.skipped_locked == ["BILLS-119s1"]
    assert any("still over cap" in r.message for r in caplog.records)


def test_eviction_failure_never_fails_the_call(root, tmp_path, monkeypatch):
    store = make_store(max_bytes=1)

    def boom(self, **kw):
        raise RuntimeError("eviction exploded")

    monkeypatch.setattr(PackageStore, "evict", boom)
    index, published = store.build_and_publish(parsed_for("BILLS-119s1"), last_modified=LM)
    assert published and index.search(["icebreaker"], 3)
    index.close()


def test_row_without_file_during_eviction_is_dropped_not_counted(root, tmp_path):
    size = one_file_size(tmp_path)
    store = make_store(max_bytes=int(size * 2.5))
    p1 = publish(store, "BILLS-119s1", accessed_at=1000.0)
    publish(store, "BILLS-119s2", accessed_at=2000.0)
    p1.unlink()  # gone behind the manifest's back
    publish(store, "BILLS-119s3")  # total = 2 files -> under cap, nothing evicted
    assert store.last_eviction.evicted == []
    # A later over-cap pass hits the orphan row first (LRU) and drops it
    # cleanly instead of counting it; the live files are protected here so
    # only the orphan-row branch runs.
    store.manifest().upsert(cache.ManifestRow("BILLS-119s1", p1.name, cache.SCHEMA_VERSION, 5, 1.0, 1.0))
    store.close()
    tight = make_store(max_bytes=1)
    report = tight.evict(protect={"BILLS-119s2", "BILLS-119s3"}, now=time.time())
    assert report.evicted == [] and sorted(report.skipped_protected) == ["BILLS-119s2", "BILLS-119s3"]
    assert tight.manifest().get("BILLS-119s1") is None
    tight.close()


def test_settings_cap_comes_from_env(root, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_MAX_BYTES, "12345")
    service_mod.reset_store()
    assert service_mod.get_store().settings.max_bytes == 12345
