"""Startup reconcile + recovery (spec §10): the six recovery-table rows, the
stale-schema sweep (older only; newer ignored in place), `.tmp` older than
one hour, manifest<->disk reconcile on startup (one listdir + one query) and
lazily on a missing-file error.

Run with: pytest tests/test_bill_text_reconcile.py
"""

from __future__ import annotations

import os
import sqlite3
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


def make_store(*, reconcile=False) -> PackageStore:
    return PackageStore(cache.CacheSettings.from_env(), reconcile=reconcile)


def publish(store: PackageStore, package_id: str) -> Path:
    index, _ = store.build_and_publish(parsed_for(package_id), last_modified=LM)
    index.close()
    return store.layout.package_path(package_id)


def age(path: Path, seconds: float) -> None:
    t = time.time() - seconds
    os.utime(path, (t, t))


def names(layout: cache.CacheLayout) -> list[str]:
    return sorted(p.name for p in layout.packages_dir.iterdir())


# ---------------------------------------------------------------------------
# Sweeps
# ---------------------------------------------------------------------------


def test_stale_temps_removed_fresh_temps_kept(root):
    store = make_store()
    store.layout.ensure_dirs()
    old = store.layout.packages_dir / ".BILLS-119s1.0123abcd.tmp"
    fresh = store.layout.packages_dir / ".BILLS-119s2.0123abcd.tmp"
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    age(old, cache.STALE_TEMP_SECONDS + 60)
    report = store.reconcile()
    assert report.stale_temps_removed == 1
    assert not old.exists() and fresh.exists()


def test_stale_schema_unlinked_newer_ignored_unrecognized_ignored(root):
    store = make_store()
    store.layout.ensure_dirs()
    older = store.layout.packages_dir / cache.package_filename("BILLS-119s1", cache.SCHEMA_VERSION - 1)
    newer = store.layout.packages_dir / cache.package_filename("BILLS-119s2", cache.SCHEMA_VERSION + 1)
    weird = store.layout.packages_dir / "notes.db"
    for p in (older, newer, weird):
        p.write_bytes(b"whatever")
    report = store.reconcile()
    assert report.stale_schema_removed == 1
    assert report.newer_schema_ignored == 1
    assert report.unrecognized_ignored == 1
    assert not older.exists() and newer.exists() and weird.exists()
    # Idempotent: a second pass finds nothing to do.
    again = store.reconcile()
    assert not again.changed() and again.newer_schema_ignored == 1


# ---------------------------------------------------------------------------
# The recovery table
# ---------------------------------------------------------------------------


def test_row_without_file_is_dropped(root):
    store = make_store()
    path = publish(store, "BILLS-119s1")
    assert store.manifest().get("BILLS-119s1") is not None
    path.unlink()
    report = store.reconcile()
    assert report.rows_dropped_missing_file == 1
    assert store.manifest().get("BILLS-119s1") is None


def test_file_without_row_is_validated_and_adopted(root):
    store = make_store()
    path = publish(store, "BILLS-119s1")
    store.manifest().remove("BILLS-119s1")
    age(path, 3600)  # adoption takes created_at / last_accessed_at from the file
    report = store.reconcile()
    assert report.files_adopted == 1
    row = store.manifest().get("BILLS-119s1")
    assert row is not None
    assert row.filename == path.name
    assert row.bytes == path.stat().st_size
    assert abs(row.created_at - path.stat().st_mtime) < 1
    assert row.source_last_modified == LM and row.source_format == "bill_dtd"
    assert row.schema_version == cache.SCHEMA_VERSION


def test_rowless_abandoned_build_is_unlinked_but_garbage_is_left(root):
    store = make_store()
    store.layout.ensure_dirs()
    abandoned = store.layout.package_path("BILLS-119s1")
    conn = cache.create_package_db(abandoned)
    cache.write_package_meta(conn, package_id="BILLS-119s1", source_format="bill_dtd", source_last_modified=LM, build_complete=False)
    conn.close()
    garbage = store.layout.package_path("BILLS-119s2")
    garbage.write_bytes(b"not a database" * 50)
    report = store.reconcile()
    assert report.files_invalid_unlinked == 1 and not abandoned.exists()
    assert report.files_invalid_skipped == 1 and garbage.exists()
    assert store.manifest().get("BILLS-119s1") is None and store.manifest().get("BILLS-119s2") is None


def test_missing_manifest_is_rebuilt_from_disk(root):
    store = make_store()
    publish(store, "BILLS-119s1")
    publish(store, "BILLS-119s2")
    store.close()
    for p in store.layout.manifest_sidecars():
        p.unlink()
    assert not store.layout.manifest_path.exists()
    fresh = make_store(reconcile=True)
    assert fresh.last_reconcile.files_adopted == 2
    assert sorted(r.package_id for r in fresh.manifest().rows()) == ["BILLS-119s1", "BILLS-119s2"]
    fresh.close()


def test_corrupt_manifest_is_unlinked_and_rebuilt(root):
    store = make_store()
    publish(store, "BILLS-119s1")
    store.close()
    store.layout.manifest_path.write_bytes(b"garbage" * 200)
    fresh = make_store(reconcile=True)
    assert fresh.last_reconcile.files_adopted == 1
    assert [r.package_id for r in fresh.manifest().rows()] == ["BILLS-119s1"]
    fresh.close()


def test_bytes_mismatch_trusts_stat(root):
    store = make_store()
    path = publish(store, "BILLS-119s1")
    store.manifest().set_bytes("BILLS-119s1", 1)
    report = store.reconcile()
    assert report.bytes_corrected == 1
    assert store.manifest().get("BILLS-119s1").bytes == path.stat().st_size


def test_valid_file_with_row_is_not_revalidated_at_startup(root, monkeypatch):
    store = make_store()
    publish(store, "BILLS-119s1")
    store._validated.clear()
    calls = []
    real = cache.validate_package_file
    monkeypatch.setattr(cache, "validate_package_file", lambda path, **kw: (calls.append(path), real(path, **kw))[1])
    store.reconcile()
    assert calls == [], "files with a row are trusted at startup; validated lazily on open"


# ---------------------------------------------------------------------------
# Cost and robustness
# ---------------------------------------------------------------------------


def test_reconcile_is_one_listdir_and_one_manifest_query(root, monkeypatch):
    store = make_store()
    publish(store, "BILLS-119s1")
    publish(store, "BILLS-119s2")
    listdirs, queries = [], []
    real_iterdir = Path.iterdir
    real_rows = cache.Manifest.rows
    monkeypatch.setattr(Path, "iterdir", lambda self: (listdirs.append(self), real_iterdir(self))[1])
    monkeypatch.setattr(cache.Manifest, "rows", lambda self: (queries.append(1), real_rows(self))[1])
    store.reconcile()
    assert len(listdirs) == 1 and len(queries) == 1


def test_reconcile_never_raises_on_a_broken_manifest_op(root, monkeypatch):
    store = make_store()
    publish(store, "BILLS-119s1")
    store.manifest().remove("BILLS-119s1")

    def boom(self, row):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(cache.Manifest, "upsert", boom)
    report = store.reconcile()
    assert report.errors and "adopt BILLS-119s1" in report.errors[0]


def test_store_construction_runs_reconcile_once(root, monkeypatch):
    store = make_store()
    publish(store, "BILLS-119s1")
    store.manifest().remove("BILLS-119s1")
    store.close()
    fresh = make_store(reconcile=True)
    assert fresh.last_reconcile is not None and fresh.last_reconcile.files_adopted == 1
    fresh.close()
    # And the service's process-wide store does it on first use.
    service_mod.reset_store()
    s = service_mod.get_store()
    assert s is not None and s.last_reconcile is not None
    assert s.manifest().get("BILLS-119s1") is not None


def test_lazy_reconcile_drops_row_when_file_vanishes(root):
    store = make_store()
    path = publish(store, "BILLS-119s1")
    assert store.manifest().get("BILLS-119s1") is not None
    path.unlink()  # e.g. `cache clear` from another process
    assert store.fresh_path("BILLS-119s1", LM) is None
    assert store.manifest().get("BILLS-119s1") is None, "row dropped lazily on the missing-file miss"


def test_lazy_reconcile_on_open_failure(root, monkeypatch):
    store = make_store()
    path = publish(store, "BILLS-119s1")
    real_connect = sqlite3.connect

    def vanish_then_connect(*a, **kw):
        if path.exists():
            path.unlink()
        return real_connect(*a, **kw)

    # fresh_path passes (file present, validation memoized), then the open finds it gone.
    assert store.fresh_path("BILLS-119s1", LM) is not None
    monkeypatch.setattr(sqlite3, "connect", vanish_then_connect)
    assert store.open("BILLS-119s1", LM) is None
    monkeypatch.undo()
    assert store.manifest().get("BILLS-119s1") is None
