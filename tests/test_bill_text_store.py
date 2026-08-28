"""The persistence path (spec §10): build -> temp -> close-and-validate ->
publish -> serve from the PUBLISHED file, loser-adopts live, and the service
wiring around it (skip the XML download on a fresh hit; refetch when the file
vanishes; in-memory fallback; CONGRESSMCP_CACHE_ENABLED=false).

Run with: pytest tests/test_bill_text_store.py
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from pathlib import Path

import pytest

import congress_api.features.bill_text.client as client_mod
import congress_api.features.bill_text.service as service_mod
import congress_api.features.bill_text.tools as tools_mod
from congress_api.features.bill_text import cache
from congress_api.features.bill_text.client import ResolvedBillText, TextVersion
from congress_api.features.bill_text.index import PACKAGE_TABLES, BillTextIndex
from congress_api.features.bill_text.parser import Segment, Unit, parse_bill_xml
from congress_api.features.bill_text.service import LoadedBillText
from congress_api.features.bill_text.store import PackageBuildError, PackageStore

FIXTURES = Path(__file__).parent / "fixtures"
PACKAGE_ID = "BILLS-119s1071enr"
LAST_MODIFIED = "2025-12-19T03:11:48Z"
XML = (FIXTURES / "bill_text_trimmed.xml").read_bytes()


def parsed_fixture(last_modified: str | None = LAST_MODIFIED):
    return parse_bill_xml(XML, PACKAGE_ID, "enr", last_modified)


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    monkeypatch.delenv(cache.ENV_CACHE_ENABLED, raising=False)
    service_mod.reset_store()
    s = PackageStore(cache.CacheSettings.from_env())
    yield s
    s.close()
    service_mod.reset_store()


def _dir_listing(layout: cache.CacheLayout) -> list[str]:
    return sorted(p.name for p in layout.packages_dir.iterdir()) if layout.packages_dir.exists() else []


def _hits(index: BillTextIndex, queries, max_hits=10):
    return [
        (h.unit.section_id, round(h.score, 9), h.match_contexts, h.matched_queries, h.snippet)
        for h in index.search(queries, max_hits)
    ]


# ---------------------------------------------------------------------------
# Build -> temp -> validate -> publish -> serve
# ---------------------------------------------------------------------------


def test_build_and_publish_produces_one_closed_file_and_serves_it(store):
    parsed = parsed_fixture()
    index, published = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    assert published is True
    final = store.layout.package_path(PACKAGE_ID)
    assert _dir_listing(store.layout) == [final.name], "exactly the published file: no temp, no -wal/-shm/-journal"
    # Served from the PUBLISHED file, read-only.
    assert index.parsed.package_id == PACKAGE_ID
    with pytest.raises(sqlite3.OperationalError):
        index.conn.execute("CREATE TABLE scribble (x)")
    # Meta rows adoption validation needs, and the source lastModified.
    conn = sqlite3.connect(str(final))
    meta = cache.read_package_meta(conn)
    assert meta["build_complete"] == "1"
    assert meta["package_id"] == PACKAGE_ID
    assert meta["schema_version"] == str(cache.SCHEMA_VERSION)
    assert meta["source_format"] == "bill_dtd"
    assert meta["source_last_modified"] == LAST_MODIFIED
    assert conn.execute("PRAGMA application_id").fetchone()[0] == cache.APPLICATION_ID
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] != "wal"
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert set(PACKAGE_TABLES) <= tables
    # Probe scratch tables must NOT be in the file (they are TEMP, per connection).
    assert "probe_fts" not in tables and "probe_vocab" not in tables
    conn.close()
    index.close()


def test_reconstructed_parsed_bill_equals_the_original(store):
    parsed = parsed_fixture()
    index, _ = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    back = index.parsed
    assert back.package_id == parsed.package_id and back.version == parsed.version
    assert back.last_modified == parsed.last_modified
    assert back.sections_indexed == parsed.sections_indexed
    assert back.struck_sections_excluded == parsed.struck_sections_excluded
    assert back.subtree_bytes == parsed.subtree_bytes
    assert back.quotes_seen == parsed.quotes_seen
    assert len(back.units) == len(parsed.units) > 0
    for a, b in zip(parsed.units, back.units):
        assert dataclasses.astuple(a) == dataclasses.astuple(b), a.section_id
        # Derived properties recompute identically from the stored segments.
        assert (a.display_text, a.byte_length, a.is_amendatory, a.amends) == (
            b.display_text, b.byte_length, b.is_amendatory, b.amends,
        )
    # Segment.inline survives the round trip (it drives rendering; F12).
    inline_flags = [s.inline for u in parsed.units for s in u.segments]
    assert inline_flags == [s.inline for u in back.units for s in u.segments]
    index.close()


def test_file_backed_index_answers_identically_to_in_memory(store):
    parsed = parsed_fixture()
    mem = BillTextIndex(parsed)
    disk, _ = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    queries = [["icebreaker"], ["Coast Guard"], ["amended"], ["zzzqqx"], ["icebreaker", "vessel"], ["Secretary"]]
    for q in queries:
        assert _hits(mem, q) == _hits(disk, q), q
        assert mem.query_matches(q[0]) == disk.query_matches(q[0])
        dm, dd = mem.diagnose(" ".join(q)), disk.diagnose(" ".join(q))
        assert (dm.terms, dm.absent, dm.verdict) == (dd.terms, dd.absent, dd.verdict)
    disk.close()
    mem.close()


def test_serving_never_writes_to_the_published_file(store):
    parsed = parsed_fixture()
    index, _ = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    final = store.layout.package_path(PACKAGE_ID)
    before = final.read_bytes()
    for _ in range(3):
        index.search(["icebreaker", "vessel"], 10)
        index.diagnose("icebreaking vessels")
        index.query_matches("Coast Guard")
    assert final.read_bytes() == before
    assert _dir_listing(store.layout) == [final.name]
    index.close()


def test_open_hits_and_records_manifest(store):
    parsed = parsed_fixture()
    index, _ = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    index.close()
    row = store.manifest().get(PACKAGE_ID)
    assert row is not None
    assert row.filename == store.layout.package_path(PACKAGE_ID).name
    assert row.bytes == store.layout.package_path(PACKAGE_ID).stat().st_size
    assert row.source_last_modified == LAST_MODIFIED and row.source_format == "bill_dtd"
    assert row.schema_version == cache.SCHEMA_VERSION
    first_access = row.last_accessed_at
    store.manifest().touch(PACKAGE_ID, first_access - 100)  # age it
    again = store.open(PACKAGE_ID, LAST_MODIFIED)
    assert again is not None
    assert store.manifest().get(PACKAGE_ID).last_accessed_at >= first_access
    again.close()


def test_validation_runs_once_per_file_signature(store, monkeypatch):
    parsed = parsed_fixture()
    index, _ = store.build_and_publish(parsed, last_modified=LAST_MODIFIED)
    index.close()
    calls = []
    real = cache.validate_package_file

    def counting(path, **kw):
        calls.append(path)
        return real(path, **kw)

    monkeypatch.setattr(cache, "validate_package_file", counting)
    for _ in range(3):
        assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is not None
    assert calls == [], "unchanged file (same mtime/size/inode) is not re-validated"
    # Touch the file's content -> signature changes -> validated again.
    final = store.layout.package_path(PACKAGE_ID)
    final.write_bytes(final.read_bytes() + b"\0")  # appended junk: still opens; quick_check decides
    store.fresh_path(PACKAGE_ID, LAST_MODIFIED)
    assert calls == [final]


# ---------------------------------------------------------------------------
# Loser adopts
# ---------------------------------------------------------------------------


def _variant_parsed():
    """Same package id, distinguishable content: the unit texts carry a marker."""
    parsed = parsed_fixture()
    units = []
    for u in parsed.units:
        segs, marked = [], False
        for s in u.segments:
            if not marked and s.context == "operative":
                segs.append(Segment(context=s.context, text="WINNERMARK " + s.text, inline=s.inline))
                marked = True
            else:
                segs.append(Segment(context=s.context, text=s.text, inline=s.inline))
        units.append(Unit(section_id=u.section_id, ancestor_path=u.ancestor_path, header=u.header, segments=segs, child_ids=list(u.child_ids)))
    return dataclasses.replace(parsed, units=units)


def test_loser_discards_temp_and_adopts_the_published_file(store, monkeypatch):
    # Another process published first: simulate by publishing a variant of the
    # same package, then racing a second build through the real code path.
    winner = _variant_parsed()
    w_index, w_pub = store.build_and_publish(winner, last_modified=LAST_MODIFIED)
    assert w_pub is True
    w_index.close()
    final = store.layout.package_path(PACKAGE_ID)
    winner_bytes = final.read_bytes()

    # Now our build: temp is created, validated, then publish finds the
    # destination present -> discard ours, adopt theirs.
    loser = parsed_fixture()
    l_index, l_pub = store.build_and_publish(loser, last_modified=LAST_MODIFIED)
    assert l_pub is False
    assert final.read_bytes() == winner_bytes, "published file untouched"
    assert _dir_listing(store.layout) == [final.name], "our temp was discarded"
    # And what we SERVE is the winner's content, not what we parsed.
    texts = " ".join(u.display_text for u in l_index.parsed.units)
    assert "WINNERMARK" in texts
    l_index.close()


def test_loser_rule_when_os_replace_itself_refuses(store, monkeypatch):
    # Windows shape: destination appears between the exists() check and the
    # rename, and os.replace raises because it is held open. Adopt, don't fail.
    winner = _variant_parsed()
    w_index, _ = store.build_and_publish(winner, last_modified=LAST_MODIFIED)
    w_index.close()
    final = store.layout.package_path(PACKAGE_ID)
    winner_bytes = final.read_bytes()
    final.unlink()  # make publish take the rename path...
    real_replace = cache.os.replace

    def racing_replace(src, dst):
        Path(dst).write_bytes(winner_bytes)  # ...and have "another process" win mid-flight
        raise PermissionError(13, "in use")

    def unsupported_link(src, dst):
        raise OSError(95, "Operation not supported")  # e.g. a filesystem without hard links

    monkeypatch.setattr(cache.os, "link", unsupported_link)
    monkeypatch.setattr(cache.os, "replace", racing_replace)
    l_index, l_pub = store.build_and_publish(parsed_fixture(), last_modified=LAST_MODIFIED)
    monkeypatch.setattr(cache.os, "replace", real_replace)
    assert l_pub is False
    assert final.read_bytes() == winner_bytes
    assert _dir_listing(store.layout) == [final.name]
    assert "WINNERMARK" in " ".join(u.display_text for u in l_index.parsed.units)
    l_index.close()


# ---------------------------------------------------------------------------
# Freshness (reissue) and adoption rules
# ---------------------------------------------------------------------------


def test_lastmodified_change_discards_and_rebuilds(store):
    index, _ = store.build_and_publish(parsed_fixture(), last_modified=LAST_MODIFIED)
    index.close()
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is not None
    assert store.fresh_path(PACKAGE_ID, "2026-01-01T00:00:00Z") is None, "reissued package is not fresh"
    assert not store.layout.package_path(PACKAGE_ID).exists(), "discarded"
    assert store.manifest().get(PACKAGE_ID) is None
    # Rebuild at the new lastModified publishes cleanly (no stale loser-adopt).
    index2, pub = store.build_and_publish(parsed_fixture("2026-01-01T00:00:00Z"), last_modified="2026-01-01T00:00:00Z")
    assert pub is True
    assert store.fresh_path(PACKAGE_ID, "2026-01-01T00:00:00Z") is not None
    index2.close()


def test_unknown_lastmodified_accepts_any_build(store):
    index, _ = store.build_and_publish(parsed_fixture(), last_modified=LAST_MODIFIED)
    index.close()
    assert store.fresh_path(PACKAGE_ID, None) is not None


def _write_meta(path: Path, **over):
    conn = sqlite3.connect(str(path))
    for k, v in over.items():
        if v is None:
            conn.execute("DELETE FROM meta WHERE key = ?", (k,))
        else:
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()


def _published(store) -> Path:
    index, _ = store.build_and_publish(parsed_fixture(), last_modified=LAST_MODIFIED)
    index.close()
    store._validated.clear()
    return store.layout.package_path(PACKAGE_ID)


def test_adoption_rejects_garbage_file_and_leaves_it(store):
    final = store.layout.package_path(PACKAGE_ID)
    store.layout.ensure_dirs()
    final.write_bytes(b"not sqlite at all" * 100)
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert final.exists(), "§10: unlink only for older schema / absent build_complete"


def test_adoption_rejects_foreign_application_id_and_leaves_it(store):
    final = _published(store)
    conn = sqlite3.connect(str(final))
    conn.execute("PRAGMA application_id = 12345")
    conn.commit()
    conn.close()
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert final.exists()


def test_adoption_unlinks_abandoned_build(store):
    final = _published(store)
    _write_meta(final, build_complete=None)
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert not final.exists()


def test_adoption_unlinks_older_schema(store):
    final = _published(store)
    _write_meta(final, schema_version=cache.SCHEMA_VERSION - 1)
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert not final.exists()


def test_adoption_ignores_newer_schema_and_leaves_it(store):
    final = _published(store)
    _write_meta(final, schema_version=cache.SCHEMA_VERSION + 1)
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert final.exists()


def test_adoption_rejects_package_id_mismatch_and_leaves_it(store):
    final = _published(store)
    _write_meta(final, package_id="BILLS-118hr1ih")
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert final.exists()


def test_adoption_rejects_missing_table(store):
    final = _published(store)
    conn = sqlite3.connect(str(final))
    conn.execute("DROP TABLE document")
    conn.commit()
    conn.close()
    assert store.fresh_path(PACKAGE_ID, LAST_MODIFIED) is None
    assert final.exists()


def test_validate_package_file_reports_each_rule():
    # Direct, order-sensitive checks of the validator on a hand-built file.
    import tempfile
    d = Path(tempfile.mkdtemp())
    path = d / "X.v1.db"
    conn = cache.create_package_db(path)
    conn.close()
    v = cache.validate_package_file(path, expected_package_id="X", expected_tables=("t",))
    assert not v.ok and "build_complete absent" in v.reason and v.unlink_advised
    conn = cache.create_package_db(path)
    cache.write_package_meta(conn, package_id="X", source_format="bill_dtd", source_last_modified="lm", build_complete=True)
    conn.close()
    v = cache.validate_package_file(path, expected_package_id="X", expected_tables=("t",))
    assert not v.ok and "tables missing" in v.reason and not v.unlink_advised
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE t (x)")
    conn.execute("CREATE VIRTUAL TABLE f USING fts5(x)")
    conn.commit()
    conn.close()
    v = cache.validate_package_file(path, expected_package_id="X", expected_tables=("t", "f"), fts_tables=("f",))
    assert v.ok and v.schema_version == cache.SCHEMA_VERSION and v.meta["source_last_modified"] == "lm"
    v = cache.validate_package_file(path, expected_package_id="Y", expected_tables=("t",))
    assert not v.ok and "package_id" in v.reason


def test_fresh_build_failing_validation_publishes_nothing(store, monkeypatch):
    monkeypatch.setattr(
        cache, "validate_package_file",
        lambda path, **kw: cache.PackageValidation(False, "forced", None, False, {}),
    )
    with pytest.raises(PackageBuildError):
        store.build_and_publish(parsed_fixture(), last_modified=LAST_MODIFIED)
    assert _dir_listing(store.layout) == [], "temp discarded, nothing at the final name"


# ---------------------------------------------------------------------------
# Service wiring
# ---------------------------------------------------------------------------


class FakeGovInfo:
    """Stands in for congress.gov resolution + GovInfo fetch. Honors the
    skip_download hook exactly as the real client does: summary always,
    download only when not skipped."""

    def __init__(self, last_modified=LAST_MODIFIED):
        self.last_modified = last_modified
        self.summaries = 0
        self.downloads = 0

    async def resolve(self, ctx, congress, bill_type, number):
        return [TextVersion("enr", "2025-12-19", "Enrolled Bill")]

    async def fetch(self, package_id, *, skip_download=None):
        self.summaries += 1
        if skip_download is not None and skip_download(package_id, self.last_modified):
            return self.last_modified, None
        self.downloads += 1
        return self.last_modified, XML


@pytest.fixture
def govinfo(monkeypatch):
    fake = FakeGovInfo()
    monkeypatch.setattr(client_mod, "_resolve_versions", fake.resolve)
    monkeypatch.setattr(client_mod, "fetch_govinfo_package", fake.fetch)
    monkeypatch.setattr(service_mod, "fetch_govinfo_package", fake.fetch)
    return fake


@pytest.mark.asyncio
async def test_service_cold_then_warm(store, govinfo):
    cold = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    assert cold.index_hit is False
    assert govinfo.downloads == 1 and govinfo.summaries == 1
    assert cold.timing["parse_ms"] is not None
    assert store.layout.package_path(PACKAGE_ID).exists()
    # Cold call already serves from the published file.
    with pytest.raises(sqlite3.OperationalError):
        cold.index.conn.execute("CREATE TABLE scribble (x)")
    cold.index.close()

    warm = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    assert warm.index_hit is True
    assert govinfo.downloads == 1, "XML not re-downloaded on a hit"
    # Within CONGRESSMCP_VERSION_TTL the cached resolution is used: no network at all.
    assert govinfo.summaries == 1 and warm.version_resolution == "cached" and warm.version_hit is True
    assert warm.resolved.xml_bytes is None
    assert warm.timing["parse_ms"] is None and warm.timing["index_ms"] is None, "§4: null the legs that did not run"
    assert warm.parsed.sections_indexed == cold.parsed.sections_indexed
    assert _hits(warm.index, ["icebreaker"]) == _hits(service_mod.BillTextIndex(cold.parsed), ["icebreaker"])
    warm.index.close()


@pytest.mark.asyncio
async def test_service_reissue_rebuilds(store, govinfo):
    first = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    first.index.close()
    govinfo.last_modified = "2026-02-02T00:00:00Z"
    # A reissue is noticed when the version is re-resolved (TTL expired): age the
    # cached resolution past the TTL.
    res = service_mod.get_store().manifest().get_resolution(119, "s", 1071)
    service_mod.get_store().manifest().put_resolution(dataclasses.replace(res, resolved_at=res.resolved_at - 10**6))
    second = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    assert second.index_hit is False
    assert govinfo.downloads == 2
    assert second.resolved.last_modified == "2026-02-02T00:00:00Z"
    meta = cache.read_package_meta(sqlite3.connect(str(store.layout.package_path(PACKAGE_ID))))
    assert meta["source_last_modified"] == "2026-02-02T00:00:00Z"
    second.index.close()


@pytest.mark.asyncio
async def test_service_refetches_when_file_vanishes_between_check_and_open(store, govinfo, monkeypatch):
    first = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    first.index.close()
    real_open = PackageStore.open
    state = {"vanish": True}

    def flaky_open(self, package_id, last_modified):
        if state["vanish"]:
            state["vanish"] = False
            store.layout.package_path(package_id).unlink()  # gone between check and open
            return real_open(self, package_id, last_modified)
        return real_open(self, package_id, last_modified)

    monkeypatch.setattr(PackageStore, "open", flaky_open)
    second = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    assert second.index_hit is False
    assert govinfo.downloads == 2, "refetched: missing file -> miss -> refetch"
    assert store.layout.package_path(PACKAGE_ID).exists(), "and rebuilt"
    second.index.close()


@pytest.mark.asyncio
async def test_service_falls_back_to_memory_when_build_fails(store, govinfo, monkeypatch):
    def boom(self, parsed, *, last_modified):
        raise PackageBuildError("forced")

    monkeypatch.setattr(PackageStore, "build_and_publish", boom)
    loaded = await service_mod.load_bill_text(None, 119, "s", 1071, None)
    assert loaded.index_hit is False
    assert loaded.index.search(["icebreaker"], 5)  # served anyway
    assert _dir_listing(store.layout) == []
    loaded.index.close()


@pytest.mark.asyncio
async def test_service_cache_disabled_never_touches_disk(tmp_path, monkeypatch, govinfo):
    monkeypatch.setenv(cache.ENV_CACHE_DIR, str(tmp_path / "cache"))
    monkeypatch.setenv(cache.ENV_CACHE_ENABLED, "false")
    service_mod.reset_store()
    assert service_mod.get_store() is None
    for _ in range(2):
        loaded = await service_mod.load_bill_text(None, 119, "s", 1071, None)
        assert loaded.index_hit is False
        assert loaded.resolved.xml_bytes is not None
        loaded.index.close()
    assert govinfo.downloads == 2, "re-fetches and re-parses every call"
    assert not (tmp_path / "cache").exists()
    service_mod.reset_store()


@pytest.mark.asyncio
async def test_envelope_reports_index_hit_and_null_parse_ms(monkeypatch):
    # A7: timing is env-gated on the wire; assert the verbose shape here.
    monkeypatch.setenv("CONGRESSMCP_VERBOSE", "1")
    parsed = parsed_fixture()
    loaded = LoadedBillText(
        resolved=ResolvedBillText(PACKAGE_ID, "enr", "2026-08-21T00:00:00Z", None, LAST_MODIFIED, None),
        parsed=parsed,
        index=BillTextIndex(parsed),
        timing={"resolve_ms": 1.0, "download_ms": None, "parse_ms": None, "index_ms": None},
        index_hit=True,
    )

    async def fake_load(ctx, congress, bill_type, number, version):
        return loaded

    monkeypatch.setattr(tools_mod, "load_bill_text", fake_load)
    toc = await tools_mod.get_bill_toc(None, congress=119, bill_type="s", number=1071, depth=2)
    assert toc["cache"] == {"index_hit": True, "version_hit": False}
    assert toc["timing"]["parse_ms"] is None and toc["timing"]["index_ms"] is None
    assert toc["timing"]["total_ms"] >= 0
    # Wire-safe: the envelope round-trips through JSON with the null.
    json.dumps(toc)
    search = await tools_mod.search_bill_text(None, congress=119, bill_type="s", number=1071, queries=["icebreaker"], max_hits=5)
    assert search["cache"]["index_hit"] is True and search["hits"]
