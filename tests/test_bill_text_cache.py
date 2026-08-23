"""Unit tests for the persistent bill-text cache module (spec §10): layout
ownership, platform default dirs, tunables, manifest (WAL), package DBs (no
WAL), temp/publish naming, and clear().

Run with: pytest tests/test_bill_text_cache.py
"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from congress_api.features.bill_text import cache


# ---------------------------------------------------------------------------
# Import isolation: the module the CLI imports must not boot the server stack
# ---------------------------------------------------------------------------


def test_cache_module_imports_without_the_server_stack():
    # The CLI administers a cache that may be broken enough to stop the server
    # from starting, and must not print the CONGRESS_API_KEY warnings that
    # congress_api.core.api_config emits at import. Assert from a fresh
    # interpreter: sys.modules accumulates across tests.
    script = textwrap.dedent(
        """
        import sys
        import congress_api.features.bill_text.cache
        heavy = sorted(
            m for m in sys.modules
            if m == "mcp" or m.startswith("mcp.")
            or m.startswith("congress_api.core")
            or m in ("congress_api.features.bill_text.tools",
                     "congress_api.features.bill_text.client",
                     "congress_api.mcp_app", "congress_api.main")
        )
        print("HEAVY:" + ",".join(heavy))
        """
    )
    env = {k: v for k, v in os.environ.items() if k != "CONGRESS_API_KEY"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "HEAVY:", result.stdout
    assert "CONGRESS_API_KEY" not in result.stderr


def test_package_init_still_exposes_the_tools_lazily():
    import congress_api.features.bill_text as pkg

    assert set(pkg.__all__) == {"search_bill_text", "get_bill_section", "get_bill_toc"}
    assert callable(pkg.get_bill_toc)
    with pytest.raises(AttributeError):
        pkg.no_such_thing  # noqa: B018


# ---------------------------------------------------------------------------
# Filenames and schema version
# ---------------------------------------------------------------------------


def test_package_filename_round_trip():
    name = cache.package_filename("BILLS-119s1071enr")
    assert name == f"BILLS-119s1071enr.v{cache.SCHEMA_VERSION}.db"
    parsed = cache.parse_package_filename(name)
    assert parsed == cache.PackageFilename("BILLS-119s1071enr", cache.SCHEMA_VERSION)
    assert parsed.is_current and not parsed.is_stale and not parsed.is_newer
    assert parsed.status == "current"


def test_package_filename_rejects_unsafe_ids():
    for bad in ("", "../x", "a/b", "a b", ".hidden", "x.v1.db"):
        with pytest.raises(ValueError):
            cache.package_filename(bad)


@pytest.mark.parametrize(
    "name",
    [
        "manifest.db",
        "BILLS-119s1071enr.db",
        "BILLS-119s1071enr.v.db",
        "BILLS-119s1071enr.vX.db",
        ".BILLS-119s1071enr.a3f9c1f2.tmp",
        "BILLS-119s1071enr.v1.db-journal",
        "BILLS-119s1071enr.v1.db-wal",
    ],
)
def test_parse_package_filename_rejects_non_package_names(name):
    assert cache.parse_package_filename(name) is None


def test_schema_version_classification():
    older = cache.PackageFilename("X", cache.SCHEMA_VERSION - 1)
    newer = cache.PackageFilename("X", cache.SCHEMA_VERSION + 1)
    assert older.is_stale and older.status == "stale"
    assert newer.is_newer and newer.status == "newer"
    assert cache.parse_package_filename(f"X.v{cache.SCHEMA_VERSION + 7}.db").is_newer


def test_schema_version_is_a_positive_int_and_glob_matches_the_filename():
    assert isinstance(cache.SCHEMA_VERSION, int) and cache.SCHEMA_VERSION >= 1
    name = cache.package_filename("BILLS-118hr1ih")
    assert Path(name).match(cache.PACKAGE_GLOB)


def test_temp_filename_parse():
    assert cache.parse_temp_filename(".BILLS-119s1071enr.a3f9c1f2.tmp") == "BILLS-119s1071enr"
    assert cache.parse_temp_filename("BILLS-119s1071enr.a3f9c1f2.tmp") is None
    assert cache.parse_temp_filename(".BILLS-119s1071enr.zz.tmp") is None


# ---------------------------------------------------------------------------
# Platform default directories and the env override
# ---------------------------------------------------------------------------


def test_default_cache_dir_darwin(tmp_path):
    home = tmp_path / "home"
    assert cache.default_cache_dir("Darwin", {}, home) == home / "Library" / "Caches" / "congressmcp"


def test_default_cache_dir_linux_xdg_and_fallback(tmp_path):
    home = tmp_path / "home"
    assert cache.default_cache_dir("Linux", {}, home) == home / ".cache" / "congressmcp"
    xdg = tmp_path / "xdg"
    assert cache.default_cache_dir("Linux", {"XDG_CACHE_HOME": str(xdg)}, home) == xdg / "congressmcp"
    # Empty XDG_CACHE_HOME means unset.
    assert cache.default_cache_dir("Linux", {"XDG_CACHE_HOME": ""}, home) == home / ".cache" / "congressmcp"


def test_default_cache_dir_windows(tmp_path):
    home = tmp_path / "home"
    local = tmp_path / "Local"
    assert cache.default_cache_dir("Windows", {"LOCALAPPDATA": str(local)}, home) == local / "congressmcp" / "Cache"
    assert (
        cache.default_cache_dir("Windows", {}, home)
        == home / "AppData" / "Local" / "congressmcp" / "Cache"
    )


def test_resolve_cache_dir_prefers_env_override_and_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cache.resolve_cache_dir({cache.ENV_CACHE_DIR: str(tmp_path / "c")}) == tmp_path / "c"
    assert cache.resolve_cache_dir({cache.ENV_CACHE_DIR: "~/c2"}) == Path.home() / "c2"
    # Blank override falls through to the platform default.
    assert cache.resolve_cache_dir({cache.ENV_CACHE_DIR: "  "}) == cache.default_cache_dir(environ={})


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


def test_tunables_table_matches_spec_section_10():
    table = {t.env: t.default for t in cache.TUNABLES}
    assert table == {
        "CONGRESSMCP_CACHE_DIR": "platform default",
        "CONGRESSMCP_CACHE_MAX_BYTES": "524288000",
        "CONGRESSMCP_CACHE_ENABLED": "true",
        "CONGRESSMCP_VERSION_TTL": "86400",
        "CONGRESSMCP_REVALIDATE_DAYS": "30",
    }
    assert cache.DEFAULT_CACHE_MAX_BYTES == 524288000
    assert cache.DEFAULT_VERSION_TTL_SECONDS == 86400
    assert cache.DEFAULT_REVALIDATE_DAYS == 30
    assert cache.DEFAULT_CACHE_ENABLED is True
    # The documented cost of disabling must be in the table text (§10).
    enabled = next(t for t in cache.TUNABLES if t.env == cache.ENV_CACHE_ENABLED)
    assert "re-fetches" in enabled.effect and "re-parses" in enabled.effect


def test_settings_defaults(tmp_path):
    s = cache.CacheSettings.from_env({cache.ENV_CACHE_DIR: str(tmp_path)})
    assert s.cache_dir == tmp_path
    assert s.max_bytes == 524288000
    assert s.enabled is True
    assert s.version_ttl == 86400
    assert s.revalidate_days == 30
    assert s.layout == cache.CacheLayout(tmp_path)


def test_settings_overrides(tmp_path):
    s = cache.CacheSettings.from_env(
        {
            cache.ENV_CACHE_DIR: str(tmp_path),
            cache.ENV_CACHE_MAX_BYTES: "1024",
            cache.ENV_CACHE_ENABLED: "false",
            cache.ENV_VERSION_TTL: "5",
            cache.ENV_REVALIDATE_DAYS: "2",
        }
    )
    assert (s.max_bytes, s.enabled, s.version_ttl, s.revalidate_days) == (1024, False, 5, 2)


@pytest.mark.parametrize("word,expected", [("1", True), ("yes", True), ("ON", True), ("0", False), ("No", False), ("off", False)])
def test_settings_boolean_words(tmp_path, word, expected):
    s = cache.CacheSettings.from_env({cache.ENV_CACHE_DIR: str(tmp_path), cache.ENV_CACHE_ENABLED: word})
    assert s.enabled is expected


def test_settings_malformed_values_fall_back_to_defaults(tmp_path, caplog):
    s = cache.CacheSettings.from_env(
        {
            cache.ENV_CACHE_DIR: str(tmp_path),
            cache.ENV_CACHE_MAX_BYTES: "lots",
            cache.ENV_CACHE_ENABLED: "maybe",
            cache.ENV_VERSION_TTL: "-1",
            cache.ENV_REVALIDATE_DAYS: "",
        }
    )
    assert s.max_bytes == cache.DEFAULT_CACHE_MAX_BYTES
    assert s.enabled is cache.DEFAULT_CACHE_ENABLED
    assert s.version_ttl == cache.DEFAULT_VERSION_TTL_SECONDS
    assert s.revalidate_days == cache.DEFAULT_REVALIDATE_DAYS


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_layout_paths(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    assert layout.manifest_path == tmp_path / "manifest.db"
    assert layout.packages_dir == tmp_path / "packages"
    assert layout.package_path("BILLS-119s1071enr") == tmp_path / "packages" / f"BILLS-119s1071enr.v{cache.SCHEMA_VERSION}.db"
    assert layout.package_path("BILLS-119s1071enr", 9) == tmp_path / "packages" / "BILLS-119s1071enr.v9.db"


def test_layout_temp_path_is_same_directory_hidden_and_unique(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    a = layout.temp_path("BILLS-119s1071enr")
    b = layout.temp_path("BILLS-119s1071enr")
    assert a.parent == layout.packages_dir == layout.package_path("BILLS-119s1071enr").parent
    assert re.fullmatch(r"\.BILLS-119s1071enr\.[0-9a-f]{8}\.tmp", a.name)
    assert a != b
    assert cache.parse_temp_filename(a.name) == "BILLS-119s1071enr"
    assert a.match(cache.TEMP_GLOB)
    # A temp name is never mistaken for a package file, and vice versa.
    assert cache.parse_package_filename(a.name) is None


def test_layout_listing_and_total_bytes_from_stat(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    assert layout.package_files() == [] and layout.temp_files() == [] and layout.total_bytes() == 0
    layout.ensure_dirs()
    (layout.packages_dir / "B.v1.db").write_bytes(b"x" * 10)
    (layout.packages_dir / "A.v1.db").write_bytes(b"x" * 5)
    (layout.packages_dir / "A.v0.db").write_bytes(b"x" * 3)  # stale version still counts on disk
    (layout.packages_dir / ".A.0123abcd.tmp").write_bytes(b"x" * 100)
    (layout.packages_dir / "notes.txt").write_bytes(b"x" * 1000)
    assert [p.name for p in layout.package_files()] == ["A.v0.db", "A.v1.db", "B.v1.db"]
    assert [p.name for p in layout.temp_files()] == [".A.0123abcd.tmp"]
    assert layout.total_bytes() == 18


def test_layout_from_env(tmp_path):
    assert cache.CacheLayout.from_env({cache.ENV_CACHE_DIR: str(tmp_path)}).root == tmp_path


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _row(package_id="BILLS-119s1071enr", **over) -> cache.ManifestRow:
    base = dict(
        package_id=package_id,
        filename=cache.package_filename(package_id),
        schema_version=cache.SCHEMA_VERSION,
        bytes=1234,
        created_at=1000.0,
        last_accessed_at=1000.0,
        source_format="xml",
        source_last_modified="2025-01-02T03:04:05Z",
    )
    base.update(over)
    return cache.ManifestRow(**base)


def test_manifest_is_wal_with_busy_timeout_and_spec_columns(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    with cache.Manifest(layout.manifest_path) as m:
        assert m.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert m.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert m.conn.execute("PRAGMA user_version").fetchone()[0] == cache.MANIFEST_SCHEMA_VERSION
        cols = tuple(r[1] for r in m.conn.execute("PRAGMA table_info(packages)"))
        assert cols == cache.MANIFEST_COLUMNS == (
            "package_id",
            "filename",
            "schema_version",
            "bytes",
            "created_at",
            "last_accessed_at",
            "source_format",
            "source_last_modified",
            "resolved_from_version_query",
            "version_resolved_at",
            "lease_holder",
            "lease_expires_at",
        )
        assert len(m) == 0
    assert layout.manifest_path.exists()


def test_manifest_crud_and_lru_order(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    with cache.Manifest(layout.manifest_path) as m:
        m.upsert(_row("B", last_accessed_at=20.0))
        m.upsert(_row("A", last_accessed_at=10.0))
        m.upsert(_row("C", last_accessed_at=30.0, resolved_from_version_query=True, version_resolved_at=29.0))
        assert [r.package_id for r in m.rows()] == ["A", "B", "C"]
        assert m.get("C").resolved_from_version_query is True
        assert m.get("C").version_resolved_at == 29.0
        assert m.get("A").resolved_from_version_query is False
        assert m.get("missing") is None

        m.touch("A", 40.0)
        assert [r.package_id for r in m.rows()] == ["B", "C", "A"]
        assert m.get("A").last_accessed_at == 40.0

        m.set_bytes("A", 99)
        assert m.get("A").bytes == 99

        # Upsert replaces in place (one row per package id).
        m.upsert(_row("A", bytes=7, last_accessed_at=1.0))
        assert len(m) == 3 and m.get("A").bytes == 7

        assert m.remove("B") is True and m.remove("B") is False
        assert len(m) == 2
        assert m.clear() == 2 and len(m) == 0


def test_manifest_touch_defaults_to_now(tmp_path):
    with cache.Manifest(tmp_path / "manifest.db") as m:
        m.upsert(_row("A", last_accessed_at=1.0))
        m.touch("A")
        assert m.get("A").last_accessed_at > 1_600_000_000


def test_manifest_persists_across_opens(tmp_path):
    path = tmp_path / "manifest.db"
    with cache.Manifest(path) as m:
        m.upsert(_row("A"))
    with cache.Manifest(path) as m:
        assert m.get("A") is not None


def test_manifest_corrupt_file_is_unlinked_and_rebuilt(tmp_path):
    path = tmp_path / "manifest.db"
    path.write_bytes(b"this is not a sqlite database, not even close" * 40)
    (tmp_path / "manifest.db-wal").write_bytes(b"junk")
    with cache.Manifest(path) as m:
        assert len(m) == 0
        m.upsert(_row("A"))
        assert m.get("A") is not None
    assert not (tmp_path / "manifest.db-wal").exists() or (tmp_path / "manifest.db-wal").stat().st_size != 4


def test_manifest_schema_generation_mismatch_resets(tmp_path):
    path = tmp_path / "manifest.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE packages (package_id TEXT PRIMARY KEY, other TEXT)")
    conn.execute("INSERT INTO packages VALUES ('old', 'x')")
    conn.execute(f"PRAGMA user_version = {cache.MANIFEST_SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()
    with cache.Manifest(path) as m:
        assert len(m) == 0
        cols = tuple(r[1] for r in m.conn.execute("PRAGMA table_info(packages)"))
        assert cols == cache.MANIFEST_COLUMNS


def test_manifest_unrelated_sqlite_file_is_reset_not_adopted(tmp_path):
    # A valid SQLite file that is not a manifest (user_version 0, foreign table)
    path = tmp_path / "manifest.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE something_else (x)")
    conn.commit()
    conn.close()
    with cache.Manifest(path) as m:
        assert len(m) == 0


# ---------------------------------------------------------------------------
# Package DBs: never WAL, stamped, meta table
# ---------------------------------------------------------------------------


def test_create_package_db_is_not_wal_and_is_stamped(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    temp = layout.temp_path("BILLS-119s1071enr")
    conn = cache.create_package_db(temp)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"
        assert conn.execute("PRAGMA application_id").fetchone()[0] == cache.APPLICATION_ID
        assert conn.execute("PRAGMA user_version").fetchone()[0] == cache.SCHEMA_VERSION
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert cache.PACKAGE_META_TABLE in tables
        conn.execute("CREATE TABLE t (x)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
    finally:
        conn.close()
    # No WAL sidecars ever: the file is publishable by a single rename.
    names = sorted(p.name for p in layout.packages_dir.iterdir())
    assert names == [temp.name], names


def test_create_package_db_ignores_inherited_wal_default(tmp_path):
    # Even if a caller first set WAL on the file (a pre-existing temp, or a
    # misconfigured helper), opening for build forces the rollback journal.
    path = tmp_path / "p.v1.db"
    c = sqlite3.connect(str(path))
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("CREATE TABLE x (y)")
    c.commit()
    c.close()
    conn = cache.create_package_db(path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "delete"
    finally:
        conn.close()
    assert not (tmp_path / "p.v1.db-wal").exists()
    assert not (tmp_path / "p.v1.db-shm").exists()


def test_package_meta_round_trip_and_build_complete_last(tmp_path):
    conn = cache.create_package_db(tmp_path / "p.v1.db")
    try:
        assert cache.read_package_meta(conn) == {}
        cache.write_package_meta(
            conn,
            package_id="BILLS-119s1071enr",
            source_format="xml",
            source_last_modified="2025-01-02T03:04:05Z",
            build_complete=False,
        )
        meta = cache.read_package_meta(conn)
        assert "build_complete" not in meta
        assert meta["package_id"] == "BILLS-119s1071enr"
        assert meta["schema_version"] == str(cache.SCHEMA_VERSION)
        cache.write_package_meta(
            conn,
            package_id="BILLS-119s1071enr",
            source_format="xml",
            source_last_modified=None,
            build_complete=True,
        )
        meta = cache.read_package_meta(conn)
        assert meta["build_complete"] == "1"
        assert meta["source_last_modified"] == ""
        assert set(cache.PACKAGE_META_REQUIRED) <= set(meta)
    finally:
        conn.close()


def test_read_package_meta_on_foreign_db_is_empty(tmp_path):
    c = sqlite3.connect(str(tmp_path / "x.db"))
    try:
        assert cache.read_package_meta(c) == {}
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Publication: atomic rename, loser adopts
# ---------------------------------------------------------------------------


def test_publish_package_renames_into_place(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    temp = layout.temp_path("BILLS-119s1071enr")
    final = layout.package_path("BILLS-119s1071enr")
    conn = cache.create_package_db(temp)
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    conn.close()
    path, published = cache.publish_package(temp, final)
    assert (path, published) == (final, True)
    assert final.exists() and not temp.exists()
    assert [p.name for p in layout.packages_dir.iterdir()] == [final.name]


def test_publish_package_loser_discards_temp_and_adopts_existing(tmp_path):
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    final = layout.package_path("BILLS-119s1071enr")
    final.write_bytes(b"WINNER")
    temp = layout.temp_path("BILLS-119s1071enr")
    temp.write_bytes(b"LOSER")
    temp.with_name(temp.name + "-journal").write_bytes(b"j")
    path, published = cache.publish_package(temp, final)
    assert (path, published) == (final, False)
    assert final.read_bytes() == b"WINNER"
    assert not temp.exists()
    assert not temp.with_name(temp.name + "-journal").exists()


def test_publish_package_requires_same_directory(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / ".x.00000000.tmp").write_bytes(b"")
    with pytest.raises(ValueError):
        cache.publish_package(tmp_path / "a" / ".x.00000000.tmp", tmp_path / "b" / "x.v1.db")


def test_publish_package_os_error_with_existing_destination_adopts(tmp_path, monkeypatch):
    # Windows: os.replace onto a destination another process holds open raises.
    # Simulate the race: destination appears between the exists() check and the
    # replace, and the replace refuses.
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    final = layout.package_path("X")
    temp = layout.temp_path("X")
    temp.write_bytes(b"LOSER")

    def fake_replace(src, dst):
        Path(dst).write_bytes(b"WINNER")
        raise PermissionError(13, "in use")

    monkeypatch.setattr(cache.os, "link", lambda src, dst: (_ for _ in ()).throw(OSError(95, "not supported")))
    monkeypatch.setattr(cache.os, "replace", fake_replace)
    path, published = cache.publish_package(temp, final)
    assert (path, published) == (final, False)
    assert final.read_bytes() == b"WINNER" and not temp.exists()


def test_publish_package_atomic_claim_loses_when_link_finds_destination(tmp_path, monkeypatch):
    # The race os.replace cannot see: the destination appears AFTER the exists()
    # check. os.link refuses with FileExistsError -> loser adopts, temp gone.
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    final = layout.package_path("X")
    temp = layout.temp_path("X")
    temp.write_bytes(b"LOSER")
    real_link = cache.os.link

    def racing_link(src, dst):
        Path(dst).write_bytes(b"WINNER")  # another process publishes first
        return real_link(src, dst)        # -> FileExistsError

    monkeypatch.setattr(cache.os, "link", racing_link)
    path, published = cache.publish_package(temp, final)
    assert (path, published) == (final, False)
    assert final.read_bytes() == b"WINNER" and not temp.exists()


def test_publish_package_falls_back_to_replace_where_links_are_unsupported(tmp_path, monkeypatch):
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    final = layout.package_path("X")
    temp = layout.temp_path("X")
    temp.write_bytes(b"MINE")
    monkeypatch.setattr(cache.os, "link", lambda src, dst: (_ for _ in ()).throw(OSError(95, "not supported")))
    path, published = cache.publish_package(temp, final)
    assert (path, published) == (final, True)
    assert final.read_bytes() == b"MINE" and not temp.exists()


def test_publish_package_os_error_without_destination_propagates(tmp_path, monkeypatch):
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    temp = layout.temp_path("X")
    temp.write_bytes(b"x")

    def fake_replace(src, dst):
        raise OSError(5, "disk on fire")

    monkeypatch.setattr(cache.os, "link", lambda src, dst: (_ for _ in ()).throw(OSError(95, "not supported")))
    monkeypatch.setattr(cache.os, "replace", fake_replace)
    with pytest.raises(OSError):
        cache.publish_package(temp, layout.package_path("X"))


# ---------------------------------------------------------------------------
# describe() and clear()
# ---------------------------------------------------------------------------


def _populate(tmp_path: Path) -> cache.CacheLayout:
    layout = cache.CacheLayout(tmp_path)
    layout.ensure_dirs()
    (layout.packages_dir / f"A.v{cache.SCHEMA_VERSION}.db").write_bytes(b"x" * 10)
    (layout.packages_dir / f"B.v{cache.SCHEMA_VERSION - 1}.db").write_bytes(b"x" * 20)
    (layout.packages_dir / f"C.v{cache.SCHEMA_VERSION + 1}.db").write_bytes(b"x" * 30)
    (layout.packages_dir / "weird.db").write_bytes(b"x" * 40)
    (layout.packages_dir / ".A.0123abcd.tmp").write_bytes(b"x" * 50)
    with cache.Manifest(layout.manifest_path) as m:
        m.upsert(_row("A"))
    return layout


def test_describe_reports_filesystem_truth_without_opening_manifest(tmp_path):
    layout = _populate(tmp_path)
    # Corrupt the manifest AFTER populating: info must still work.
    layout.manifest_path.write_bytes(b"garbage")
    settings = cache.CacheSettings(cache_dir=tmp_path, max_bytes=123, enabled=False)
    info = cache.describe(settings)
    assert info.path == tmp_path
    assert info.manifest_path == layout.manifest_path
    assert info.schema_version == cache.SCHEMA_VERSION
    assert info.enabled is False
    assert info.cap_bytes == 123
    assert info.total_bytes == 100
    assert info.temp_files == 1
    assert [(p.name, p.bytes, p.status) for p in info.packages] == [
        (f"A.v{cache.SCHEMA_VERSION}.db", 10, "current"),
        (f"B.v{cache.SCHEMA_VERSION - 1}.db", 20, "stale"),
        (f"C.v{cache.SCHEMA_VERSION + 1}.db", 30, "newer"),
        ("weird.db", 40, "unrecognized"),
    ]
    # describe() did not touch the garbage manifest.
    assert layout.manifest_path.read_bytes() == b"garbage"


def test_clear_removes_packages_temps_and_manifest(tmp_path):
    layout = _populate(tmp_path)
    assert layout.manifest_path.exists()
    result = cache.clear(layout)
    assert result.removed_packages == 4
    assert result.removed_temps == 1
    assert result.removed_manifest is True
    assert result.failed == []
    assert list(layout.packages_dir.iterdir()) == []
    assert layout.manifest_sidecars() == []
    # Idempotent on an empty cache.
    again = cache.clear(layout)
    assert (again.removed_packages, again.removed_temps, again.removed_manifest) == (0, 0, False)


def test_clear_on_missing_cache_dir_is_a_noop(tmp_path):
    layout = cache.CacheLayout(tmp_path / "never-created")
    result = cache.clear(layout)
    assert (result.removed_packages, result.removed_temps, result.removed_manifest, result.failed) == (0, 0, False, [])


def test_clear_reports_files_it_could_not_remove(tmp_path, monkeypatch):
    layout = _populate(tmp_path)
    real_unlink = Path.unlink

    def flaky_unlink(self, *a, **kw):
        if self.name.startswith("A."):
            raise PermissionError(13, "in use")
        return real_unlink(self, *a, **kw)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    result = cache.clear(layout)
    assert result.removed_packages == 3
    assert any(f.startswith(f"A.v{cache.SCHEMA_VERSION}.db") for f in result.failed)
    assert (layout.packages_dir / f"A.v{cache.SCHEMA_VERSION}.db").exists()
