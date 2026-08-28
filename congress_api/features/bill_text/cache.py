"""Persistent bill-text cache: on-disk layout, tunables, manifest, package files.

This module OWNS the cache layout (spec §10). Every literal that describes where
the cache lives and what it is made of -- the cache root and its platform
defaults, the ``packages/`` subdirectory, the package filename pattern and glob,
the schema version, the manifest filename, the environment variable names and
their defaults -- is defined here and nowhere else. The ``congressmcp cache``
CLI reads them from this module rather than re-declaring them (§10, PR1->PR2
forward constraint): two independent copies of the layout would let ``cache
info``/``cache clear`` point at a different path than the server writes to.

Layout::

    <cache_dir>/
      manifest.db                         # derived LRU index, WAL mode
      packages/
        BILLS-119s1071enr.v1.db           # schema version in the filename
        .BILLS-119s1071enr.a3f9c1f2.tmp   # in-progress build, same directory

Two rules from §10 are load-bearing on each other and are enforced here:

* Package databases are published by build -> close -> ``os.replace`` onto the
  final name, so a file at its final name is complete by construction.
* Package databases therefore must NOT use WAL: WAL leaves ``-wal``/``-shm``
  sidecars that break single-file atomic publication. Only ``manifest.db``
  uses WAL.

The filesystem is authoritative; the manifest is a derived convenience index
and may be deleted, stale, or corrupt at any time without loss.

This module must stay importable without the MCP server stack (no ``mcp``,
no ``congress_api.core``): the CLI that administers a broken cache has to
work when the server cannot start.
"""

from __future__ import annotations

import logging
import os
import platform
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

# The on-disk format version. It appears in every package filename
# (``<package_id>.v<N>.db``) so staleness is visible from a directory listing,
# and in each package's ``meta`` table and ``PRAGMA user_version``.
#
# Bump it for ANY change that alters what a cached index would serve:
#   - the package DB schema (tables, columns, FTS tokenizer), AND
#   - text rendering / chunking -- segment joining, delimiter rendering, header
#     separators, byte-split boundary rules (§10: "the cache key must include a
#     rendering version, not only a schema version"; F12 reordered results on a
#     whitespace-only change).
# There are no migrations: a file at an older version is discarded and rebuilt;
# a file at a newer version is ignored and left in place (§10).
# v2 (2026-08-27): F35 -- structural units below section level render their
# document enum before header/text, moving byte_length and chunk boundaries
# corpus-wide; landed together with F36's amends change (one rebuild).
SCHEMA_VERSION = 2

# Tripwire for the rule above (the F26 pattern). sha256 over the AST/values of
# index.RENDERING_SYMBOLS -- segment joining, delimiter rendering, the header
# separator (the block join), whitespace/punctuation normalization, byte-split
# boundary rules, the tokenizer and the storage schema. tests pin
# index.rendering_fingerprint() to this. When a change to any of those is
# deliberate: bump SCHEMA_VERSION AND re-pin EVERY entry below to its new
# digest, in the same commit. A digest change without a version bump is the
# stale-index bug §10 exists to prevent, and CI fails on it.
#
# VERSION-KEYED (F37, ruled 2026-08-23): ``ast.dump`` of identical source is
# not stable across interpreter series -- the pin computed on 3.14 failed on
# CI's 3.12 -- so the instrument shares the failure class it detects unless
# the key names the interpreter. One entry per supported series: CI (3.12, per
# .github/workflows/test.yml) and dev (3.14). An unlisted series SKIPS the
# AST tripwire with a named reason (tests); the golden-build digest below is
# interpreter-stable (it passed on 3.12 in the same CI run) and still guards
# everywhere. Do not chase a version-independent AST normalization --
# ``ast.unparse`` is not contractually stable across versions either. To add
# a series: print ``index.rendering_fingerprint()`` under that interpreter
# (``uv python install 3.X`` / pyenv / a CI step) and add the entry.
RENDERING_FINGERPRINTS: dict[str, str] = {
    "3.12": "5a58b545ab079f1970cf9ebcd3b6b9e7e565b88ce6569625f5f9cf24096630b0",
    "3.14": "a95e941c93703a87ad8d14ecf80d7177b5d58ec38f1a92d4d4b445b2101790c6",
}


def interpreter_series(version_info=None) -> str:
    """``"3.12"``-style key for the running (or given) interpreter."""
    info = sys.version_info if version_info is None else version_info
    return f"{info[0]}.{info[1]}"


def expected_rendering_fingerprint(series: str | None = None) -> str | None:
    """The pinned AST digest for this interpreter series, or None if unlisted."""
    return RENDERING_FINGERPRINTS.get(series or interpreter_series())

# The authoritative backstop (§10 tail, ruled 2026-08-21): a golden BUILD. The
# three in-tree trimmed fixtures are built through the real build path and every
# stored row is dumped in canonical order (index.canonical_rows_digest); this
# is the sha256 over those dumps. It moves on any change that would make a
# rebuilt package differ from a cached one -- parser semantics (AMENDATORY_RE,
# amends resolution), segmenter, schema, tokenizer -- and on nothing else.
# Same rule: bump SCHEMA_VERSION AND re-pin, in one commit. (Trimmed fixtures
# detect change; they prove nothing about correctness -- §13.)
GOLDEN_BUILD_FINGERPRINT = "7fa1958addcebd798acefd4ab2929e4c4c8961633f3c63a6cbaa93cf89c7b8f8"

# ``PRAGMA application_id`` stamped into every package database. ASCII "CMCP".
# Adoption of an orphan file (present on disk, absent from the manifest) first
# checks this so an unrelated SQLite file dropped into packages/ is never
# mistaken for ours.
APPLICATION_ID = 0x434D4350

# Manifest schema generation, kept in the manifest's ``PRAGMA user_version``.
# The manifest is derived, so a mismatch simply drops and recreates it.
MANIFEST_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Filenames
# ---------------------------------------------------------------------------

MANIFEST_FILENAME = "manifest.db"
PACKAGES_SUBDIR = "packages"
PACKAGE_SUFFIX = ".db"
# Every package file, at any schema version. ``cache info`` lists and sums all
# of them: a stale-version file still occupies disk until startup unlinks it.
PACKAGE_GLOB = "*" + PACKAGE_SUFFIX
# In-progress builds: ``.{package_id}.{uuid4().hex[:8]}.tmp`` (§10).
TEMP_GLOB = ".*.tmp"
TEMP_TOKEN_HEX = 8

_PACKAGE_FILENAME_RE = re.compile(
    r"^(?P<package_id>[A-Za-z0-9][A-Za-z0-9_-]*)\.v(?P<schema_version>\d+)\.db$"
)
_TEMP_FILENAME_RE = re.compile(
    r"^\.(?P<package_id>[A-Za-z0-9][A-Za-z0-9_-]*)\.(?P<token>[0-9a-f]{"
    + str(TEMP_TOKEN_HEX)
    + r"})\.tmp$"
)


def package_filename(package_id: str, schema_version: int = SCHEMA_VERSION) -> str:
    """``BILLS-119s1071enr`` -> ``BILLS-119s1071enr.v1.db``."""
    if not _PACKAGE_FILENAME_RE.match(f"{package_id}.v{schema_version}.db"):
        raise ValueError(f"invalid package id for a cache filename: {package_id!r}")
    return f"{package_id}.v{schema_version}{PACKAGE_SUFFIX}"


@dataclass(frozen=True)
class PackageFilename:
    """A parsed ``<package_id>.v<N>.db`` name."""

    package_id: str
    schema_version: int

    @property
    def is_current(self) -> bool:
        return self.schema_version == SCHEMA_VERSION

    @property
    def is_stale(self) -> bool:
        """Strictly older than this binary's schema: unlink on startup."""
        return self.schema_version < SCHEMA_VERSION

    @property
    def is_newer(self) -> bool:
        """Written by a newer binary: ignore, never adopt, never delete."""
        return self.schema_version > SCHEMA_VERSION

    @property
    def status(self) -> str:
        if self.is_current:
            return "current"
        return "stale" if self.is_stale else "newer"


def parse_package_filename(name: str) -> PackageFilename | None:
    """Parse a package filename; ``None`` if it is not one of ours."""
    match = _PACKAGE_FILENAME_RE.match(name)
    if not match:
        return None
    return PackageFilename(match.group("package_id"), int(match.group("schema_version")))


def parse_temp_filename(name: str) -> str | None:
    """Return the package id of an in-progress temp file, or ``None``."""
    match = _TEMP_FILENAME_RE.match(name)
    return match.group("package_id") if match else None


# ---------------------------------------------------------------------------
# Tunables (the §10 table)
# ---------------------------------------------------------------------------

ENV_CACHE_DIR = "CONGRESSMCP_CACHE_DIR"
ENV_CACHE_MAX_BYTES = "CONGRESSMCP_CACHE_MAX_BYTES"
ENV_CACHE_ENABLED = "CONGRESSMCP_CACHE_ENABLED"
ENV_VERSION_TTL = "CONGRESSMCP_VERSION_TTL"
ENV_REVALIDATE_DAYS = "CONGRESSMCP_REVALIDATE_DAYS"

DEFAULT_CACHE_MAX_BYTES = 524_288_000  # 500 MiB across packages/
DEFAULT_CACHE_ENABLED = True
DEFAULT_VERSION_TTL_SECONDS = 86_400
DEFAULT_REVALIDATE_DAYS = 30

# Not tunable, but layout constants the rest of the cache shares (§10).
LEASE_TTL_SECONDS = 300          # best-effort cross-process eviction lease
STALE_TEMP_SECONDS = 3_600       # startup unlinks .tmp files older than this
MANIFEST_BUSY_TIMEOUT_MS = 5_000


@dataclass(frozen=True)
class Tunable:
    env: str
    default: str
    effect: str


# The tunables table exactly as §10 states it; README and ``cache info`` render
# from this so the documented defaults cannot drift from the ones in force.
TUNABLES: tuple[Tunable, ...] = (
    Tunable(ENV_CACHE_DIR, "platform default", "Cache root"),
    Tunable(ENV_CACHE_MAX_BYTES, str(DEFAULT_CACHE_MAX_BYTES), "Eviction cap"),
    Tunable(
        ENV_CACHE_ENABLED,
        "true",
        "false -> in-memory index, discarded per call (re-fetches and re-parses "
        "the full document on every call)",
    ),
    Tunable(ENV_VERSION_TTL, str(DEFAULT_VERSION_TTL_SECONDS), "Version-resolution TTL (seconds)"),
    Tunable(ENV_REVALIDATE_DAYS, str(DEFAULT_REVALIDATE_DAYS), "Explicit-version revalidation interval (days)"),
)

_TRUE_WORDS = {"1", "true", "yes", "on"}
_FALSE_WORDS = {"0", "false", "no", "off"}


def _env_int(environ: Mapping[str, str], name: str, default: int, *, minimum: int = 0) -> int:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        logger.warning("%s=%r is not an integer; using default %d", name, raw, default)
        return default
    if value < minimum:
        logger.warning("%s=%r is below %d; using default %d", name, raw, minimum, default)
        return default
    return value


def _env_bool(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    word = raw.strip().lower()
    if word in _TRUE_WORDS:
        return True
    if word in _FALSE_WORDS:
        return False
    logger.warning("%s=%r is not a boolean; using default %s", name, raw, default)
    return default


def default_cache_dir(
    system: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Platform default cache root (§10). Hand-rolled; no platformdirs dependency.

    - Linux (and anything else): ``$XDG_CACHE_HOME/congressmcp``, else ``~/.cache/congressmcp``
    - macOS: ``~/Library/Caches/congressmcp``
    - Windows: ``%LOCALAPPDATA%\\congressmcp\\Cache``
    """
    system = system if system is not None else platform.system()
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home
    if system == "Darwin":
        return home / "Library" / "Caches" / "congressmcp"
    if system == "Windows":
        base = environ.get("LOCALAPPDATA") or str(home / "AppData" / "Local")
        return Path(base) / "congressmcp" / "Cache"
    xdg = environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else home / ".cache"
    return base / "congressmcp"


def resolve_cache_dir(environ: Mapping[str, str] | None = None) -> Path:
    """``$CONGRESSMCP_CACHE_DIR`` (``~`` expanded) if set, else the platform default."""
    environ = os.environ if environ is None else environ
    override = environ.get(ENV_CACHE_DIR)
    if override and override.strip():
        return Path(override.strip()).expanduser()
    return default_cache_dir(environ=environ)


@dataclass(frozen=True)
class CacheSettings:
    """The tunables as read from the environment, defaults applied."""

    cache_dir: Path
    max_bytes: int = DEFAULT_CACHE_MAX_BYTES
    enabled: bool = DEFAULT_CACHE_ENABLED
    version_ttl: int = DEFAULT_VERSION_TTL_SECONDS
    revalidate_days: int = DEFAULT_REVALIDATE_DAYS

    def __post_init__(self) -> None:
        object.__setattr__(self, "cache_dir", Path(self.cache_dir))

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CacheSettings":
        environ = os.environ if environ is None else environ
        return cls(
            cache_dir=resolve_cache_dir(environ),
            max_bytes=_env_int(environ, ENV_CACHE_MAX_BYTES, DEFAULT_CACHE_MAX_BYTES),
            enabled=_env_bool(environ, ENV_CACHE_ENABLED, DEFAULT_CACHE_ENABLED),
            version_ttl=_env_int(environ, ENV_VERSION_TTL, DEFAULT_VERSION_TTL_SECONDS),
            revalidate_days=_env_int(environ, ENV_REVALIDATE_DAYS, DEFAULT_REVALIDATE_DAYS),
        )

    @property
    def layout(self) -> "CacheLayout":
        return CacheLayout(self.cache_dir)


# ---------------------------------------------------------------------------
# Layout: paths under the cache root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheLayout:
    """Paths under one cache root. Pure path arithmetic plus directory listing."""

    root: Path

    def __post_init__(self) -> None:
        # Accept a str root (direct constructors, subprocess-marshalled paths).
        object.__setattr__(self, "root", Path(self.root))

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CacheLayout":
        return cls(resolve_cache_dir(environ))

    @property
    def manifest_path(self) -> Path:
        return self.root / MANIFEST_FILENAME

    @property
    def packages_dir(self) -> Path:
        return self.root / PACKAGES_SUBDIR

    def package_path(self, package_id: str, schema_version: int = SCHEMA_VERSION) -> Path:
        return self.packages_dir / package_filename(package_id, schema_version)

    def temp_path(self, package_id: str) -> Path:
        """A fresh in-progress build name, in the SAME directory as the final
        file so ``os.replace`` is an atomic same-filesystem rename (§10)."""
        # Validate the id through the same rule the final name uses.
        package_filename(package_id)
        token = uuid.uuid4().hex[:TEMP_TOKEN_HEX]
        return self.packages_dir / f".{package_id}.{token}.tmp"

    def ensure_dirs(self) -> None:
        self.packages_dir.mkdir(parents=True, exist_ok=True)

    def package_files(self) -> list[Path]:
        """Every ``*.db`` under packages/, any schema version, sorted by name."""
        if not self.packages_dir.is_dir():
            return []
        return sorted(p for p in self.packages_dir.glob(PACKAGE_GLOB) if p.is_file())

    def temp_files(self) -> list[Path]:
        if not self.packages_dir.is_dir():
            return []
        return sorted(p for p in self.packages_dir.glob(TEMP_GLOB) if p.is_file())

    def total_bytes(self) -> int:
        """Sum of actual ``stat`` sizes of package files -- never manifest rows (§10)."""
        return sum(_size_or_zero(p) for p in self.package_files())

    def manifest_sidecars(self) -> list[Path]:
        """``manifest.db`` plus its WAL sidecars, whichever exist."""
        candidates = [
            self.manifest_path,
            self.manifest_path.with_name(MANIFEST_FILENAME + "-wal"),
            self.manifest_path.with_name(MANIFEST_FILENAME + "-shm"),
        ]
        return [p for p in candidates if p.exists()]


def _size_or_zero(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Manifest (derived index; WAL)
# ---------------------------------------------------------------------------

MANIFEST_COLUMNS: tuple[str, ...] = (
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

_MANIFEST_DDL = """
CREATE TABLE IF NOT EXISTS packages (
  package_id TEXT PRIMARY KEY,
  filename TEXT NOT NULL UNIQUE,
  schema_version INTEGER NOT NULL,
  bytes INTEGER NOT NULL,
  created_at REAL NOT NULL,
  last_accessed_at REAL NOT NULL,
  source_format TEXT,
  source_last_modified TEXT,
  resolved_from_version_query INTEGER NOT NULL DEFAULT 0,
  version_resolved_at REAL,
  lease_holder TEXT,
  lease_expires_at REAL
);
CREATE INDEX IF NOT EXISTS packages_lru ON packages(last_accessed_at);

-- Last successful version=None resolution per bill (§10 freshness table):
-- within CONGRESSMCP_VERSION_TTL it is reused without any network call
-- (version_resolution "cached"); past the TTL it is re-resolved, and if the
-- network is unavailable it is served as "cached_offline" with resolved_at
-- disclosed. Derived data like everything else here.
CREATE TABLE IF NOT EXISTS resolutions (
  congress INTEGER NOT NULL,
  bill_type TEXT NOT NULL,
  number INTEGER NOT NULL,
  package_id TEXT NOT NULL,
  version TEXT NOT NULL,
  resolved_at REAL NOT NULL,
  resolved_at_iso TEXT NOT NULL,
  note TEXT,
  PRIMARY KEY (congress, bill_type, number)
);
"""


@dataclass(frozen=True)
class ManifestRow:
    package_id: str
    filename: str
    schema_version: int
    bytes: int
    created_at: float
    last_accessed_at: float
    source_format: str | None = None
    source_last_modified: str | None = None
    resolved_from_version_query: bool = False
    version_resolved_at: float | None = None
    lease_holder: str | None = None
    lease_expires_at: float | None = None

    @classmethod
    def from_sqlite(cls, row: sqlite3.Row) -> "ManifestRow":
        return cls(
            package_id=row["package_id"],
            filename=row["filename"],
            schema_version=int(row["schema_version"]),
            bytes=int(row["bytes"]),
            created_at=float(row["created_at"]),
            last_accessed_at=float(row["last_accessed_at"]),
            source_format=row["source_format"],
            source_last_modified=row["source_last_modified"],
            resolved_from_version_query=bool(row["resolved_from_version_query"]),
            version_resolved_at=row["version_resolved_at"],
            lease_holder=row["lease_holder"],
            lease_expires_at=row["lease_expires_at"],
        )


@dataclass(frozen=True)
class Resolution:
    """The last successful ``version=None`` resolution for one bill."""

    congress: int
    bill_type: str
    number: int
    package_id: str
    version: str
    resolved_at: float
    resolved_at_iso: str
    note: str | None = None


class Manifest:
    """The derived LRU index over ``packages/``. WAL, ``busy_timeout=5000``,
    every write its own short explicit transaction (§10).

    Opening never fails on a bad file: a manifest that will not open, or whose
    ``quick_check`` is not ``ok``, is unlinked (with its WAL sidecars) and
    recreated empty -- it is derived and a scan of ``packages/`` rebuilds it.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.conn = self._open()

    # -- lifecycle -----------------------------------------------------------

    def _open(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return self._connect()
        except sqlite3.DatabaseError as exc:
            logger.warning("manifest %s unusable (%s); rebuilding", self.path, exc)
            self._unlink_files()
            return self._connect()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), isolation_level="DEFERRED")
        try:
            conn.row_factory = sqlite3.Row
            conn.execute(f"PRAGMA busy_timeout = {MANIFEST_BUSY_TIMEOUT_MS}")
            mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                # e.g. a filesystem that refuses WAL; still usable, but say so.
                logger.warning("manifest %s: journal_mode is %s, not wal", self.path, mode)
            check = conn.execute("PRAGMA quick_check").fetchone()[0]
            if check != "ok":
                raise sqlite3.DatabaseError(f"quick_check: {check}")
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            if user_version != MANIFEST_SCHEMA_VERSION:
                # Derived data: drop whatever a different generation left and
                # start over. An empty, fresh file has user_version 0.
                with conn:
                    conn.execute("DROP TABLE IF EXISTS packages")
                    conn.execute("DROP TABLE IF EXISTS resolutions")
                    conn.execute(f"PRAGMA user_version = {MANIFEST_SCHEMA_VERSION}")
            with conn:
                conn.executescript(_MANIFEST_DDL)
            return conn
        except Exception:
            conn.close()
            raise

    def _unlink_files(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            candidate = self.path.with_name(self.path.name + suffix)
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning("could not unlink %s: %s", candidate, exc)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Manifest":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- reads ---------------------------------------------------------------

    def get(self, package_id: str) -> ManifestRow | None:
        row = self.conn.execute("SELECT * FROM packages WHERE package_id = ?", (package_id,)).fetchone()
        return ManifestRow.from_sqlite(row) if row else None

    def rows(self) -> list[ManifestRow]:
        """All rows, least-recently-accessed first (eviction order)."""
        cur = self.conn.execute("SELECT * FROM packages ORDER BY last_accessed_at ASC, package_id ASC")
        return [ManifestRow.from_sqlite(r) for r in cur.fetchall()]

    def __iter__(self) -> Iterator[ManifestRow]:
        return iter(self.rows())

    def __len__(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0])

    # -- writes (each its own short transaction) -----------------------------

    def upsert(self, row: ManifestRow) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO packages (
                  package_id, filename, schema_version, bytes, created_at,
                  last_accessed_at, source_format, source_last_modified,
                  resolved_from_version_query, version_resolved_at,
                  lease_holder, lease_expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                  filename = excluded.filename,
                  schema_version = excluded.schema_version,
                  bytes = excluded.bytes,
                  created_at = excluded.created_at,
                  last_accessed_at = excluded.last_accessed_at,
                  source_format = excluded.source_format,
                  source_last_modified = excluded.source_last_modified,
                  resolved_from_version_query = excluded.resolved_from_version_query,
                  version_resolved_at = excluded.version_resolved_at,
                  lease_holder = excluded.lease_holder,
                  lease_expires_at = excluded.lease_expires_at
                """,
                (
                    row.package_id,
                    row.filename,
                    row.schema_version,
                    row.bytes,
                    row.created_at,
                    row.last_accessed_at,
                    row.source_format,
                    row.source_last_modified,
                    1 if row.resolved_from_version_query else 0,
                    row.version_resolved_at,
                    row.lease_holder,
                    row.lease_expires_at,
                ),
            )

    def touch(self, package_id: str, when: float | None = None) -> None:
        """LRU bump: ``last_accessed_at`` is updated on every hit (§10)."""
        when = time.time() if when is None else when
        with self.conn:
            self.conn.execute(
                "UPDATE packages SET last_accessed_at = ? WHERE package_id = ?",
                (when, package_id),
            )

    def set_bytes(self, package_id: str, size: int) -> None:
        """Correct a row whose ``bytes`` disagreed with ``stat`` -- ``stat`` wins (§10)."""
        with self.conn:
            self.conn.execute("UPDATE packages SET bytes = ? WHERE package_id = ?", (size, package_id))

    def lease(self, package_id: str, holder: str, expires_at: float) -> None:
        """Best-effort cross-process 'being served' marker (§10): eviction in
        another process skips a package whose lease is held by someone else and
        has not expired. Advisory only -- documented as best-effort."""
        with self.conn:
            self.conn.execute(
                "UPDATE packages SET lease_holder = ?, lease_expires_at = ? WHERE package_id = ?",
                (holder, expires_at, package_id),
            )

    def remove(self, package_id: str) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM packages WHERE package_id = ?", (package_id,))
        return cur.rowcount > 0

    def clear(self) -> int:
        with self.conn:
            cur = self.conn.execute("DELETE FROM packages")
            self.conn.execute("DELETE FROM resolutions")
        return cur.rowcount

    def set_created_at(self, package_id: str, when: float) -> None:
        """Explicit-version revalidation (§10): the package was re-checked
        against GovInfo's lastModified and is unchanged; restart the clock."""
        with self.conn:
            self.conn.execute("UPDATE packages SET created_at = ? WHERE package_id = ?", (when, package_id))

    def mark_resolved(self, package_id: str, resolved_at: float) -> None:
        """This package was reached via a version=None resolution at ``resolved_at``."""
        with self.conn:
            self.conn.execute(
                "UPDATE packages SET resolved_from_version_query = 1, version_resolved_at = ? WHERE package_id = ?",
                (resolved_at, package_id),
            )

    # -- version resolutions (§10 freshness table) -------------------------------

    def get_resolution(self, congress: int, bill_type: str, number: int) -> Resolution | None:
        row = self.conn.execute(
            "SELECT * FROM resolutions WHERE congress = ? AND bill_type = ? AND number = ?",
            (congress, bill_type.lower(), number),
        ).fetchone()
        if row is None:
            return None
        return Resolution(
            congress=int(row["congress"]),
            bill_type=row["bill_type"],
            number=int(row["number"]),
            package_id=row["package_id"],
            version=row["version"],
            resolved_at=float(row["resolved_at"]),
            resolved_at_iso=row["resolved_at_iso"],
            note=row["note"],
        )

    def put_resolution(self, resolution: Resolution) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO resolutions (congress, bill_type, number, package_id, version,
                                         resolved_at, resolved_at_iso, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(congress, bill_type, number) DO UPDATE SET
                  package_id = excluded.package_id, version = excluded.version,
                  resolved_at = excluded.resolved_at, resolved_at_iso = excluded.resolved_at_iso,
                  note = excluded.note
                """,
                (
                    resolution.congress, resolution.bill_type.lower(), resolution.number,
                    resolution.package_id, resolution.version, resolution.resolved_at,
                    resolution.resolved_at_iso, resolution.note,
                ),
            )

    def remove_resolution(self, congress: int, bill_type: str, number: int) -> bool:
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM resolutions WHERE congress = ? AND bill_type = ? AND number = ?",
                (congress, bill_type.lower(), number),
            )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Package databases (self-contained; NO WAL)
# ---------------------------------------------------------------------------

PACKAGE_META_TABLE = "meta"
# The keys adoption validation (§10) requires to find in ``meta``.
PACKAGE_META_REQUIRED: tuple[str, ...] = (
    "schema_version",
    "package_id",
    "source_format",
    "source_last_modified",
    "build_complete",
)


def create_package_db(path: Path) -> sqlite3.Connection:
    """Open a NEW package database for building, configured for single-file
    publication: rollback journal (never WAL), ``application_id`` and
    ``user_version`` stamped, empty ``meta`` table created.

    Callers build into a ``CacheLayout.temp_path`` name, write the index,
    ``write_package_meta(..., build_complete=True)``, close, then ``publish``.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level="DEFERRED")
    try:
        conn.row_factory = sqlite3.Row
        # DELETE is SQLite's default rollback journal. Set it explicitly so a
        # process-wide or inherited WAL setting can never leak in: a package
        # file with -wal/-shm sidecars cannot be published by one rename.
        mode = conn.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
        if str(mode).lower() == "wal":
            raise sqlite3.DatabaseError(f"package db {path} would be WAL; refusing")
        conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        with conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {PACKAGE_META_TABLE} "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
        return conn
    except Exception:
        conn.close()
        raise


def write_package_meta(
    conn: sqlite3.Connection,
    *,
    package_id: str,
    source_format: str,
    source_last_modified: str | None,
    build_complete: bool,
    schema_version: int = SCHEMA_VERSION,
) -> None:
    """Write the ``meta`` rows adoption validation reads. ``build_complete``
    is written LAST and only as ``1`` when the index is fully written; a file
    lacking it is an abandoned build and may be unlinked (§10)."""
    rows = [
        ("schema_version", str(schema_version)),
        ("package_id", package_id),
        ("source_format", source_format),
        ("source_last_modified", source_last_modified or ""),
    ]
    with conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO {PACKAGE_META_TABLE}(key, value) VALUES (?, ?)", rows
        )
        if build_complete:
            conn.execute(
                f"INSERT OR REPLACE INTO {PACKAGE_META_TABLE}(key, value) VALUES ('build_complete', '1')"
            )
        else:
            conn.execute(f"DELETE FROM {PACKAGE_META_TABLE} WHERE key = 'build_complete'")


def read_package_meta(conn: sqlite3.Connection) -> dict[str, str]:
    """The ``meta`` table as a dict; empty if the table is absent."""
    try:
        cur = conn.execute(f"SELECT key, value FROM {PACKAGE_META_TABLE}")
    except sqlite3.DatabaseError:
        return {}
    return {str(k): str(v) for k, v in cur.fetchall()}


@dataclass(frozen=True)
class PackageValidation:
    """Outcome of the §10 adoption validation for one package file.

    ``ok`` means every rule passed and the file may be served. When not ok,
    ``reason`` names the first failing rule and ``unlink_advised`` says whether
    §10 permits removing the file: only a *strictly older* schema version or an
    absent ``build_complete`` (an abandoned build). Anything else -- a newer
    schema, a foreign application_id, an unreadable file -- is left in place
    and skipped.
    """

    ok: bool
    reason: str | None
    schema_version: int | None
    unlink_advised: bool
    meta: dict[str, str]


def validate_package_file(
    path: Path,
    *,
    expected_package_id: str,
    expected_tables: tuple[str, ...],
    fts_tables: tuple[str, ...] = (),
) -> PackageValidation:
    """The seven adoption rules (§10), in order. "It opens" is not enough.

    1. ``PRAGMA application_id`` equals the project constant.
    2. ``meta`` holds schema_version, package_id, source_format,
       source_last_modified and ``build_complete = 1``.
    3. ``schema_version`` equals current (older -> unlink; newer -> ignore).
    4. ``meta.package_id`` matches the filename's package id.
    5. ``PRAGMA quick_check`` is ``ok``.
    6. Expected tables present.
    7. ``integrity-check`` passes on each FTS table.

    Used both before publication (close-and-validate of a fresh build) and when
    adopting a file found on disk. Never raises for a bad file.
    """
    path = Path(path)

    def fail(reason: str, *, unlink: bool = False, version: int | None = None, meta: dict | None = None):
        return PackageValidation(False, reason, version, unlink, meta or {})

    try:
        # Read-write open: FTS5's integrity-check is issued as an INSERT and a
        # read-only connection refuses it. It reads only; nothing is modified.
        conn = sqlite3.connect(str(path), isolation_level="DEFERRED")
    except sqlite3.Error as exc:
        return fail(f"cannot open: {exc}")
    try:
        try:
            app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            return fail(f"not a database: {exc}")
        if app_id != APPLICATION_ID:
            return fail(f"application_id {app_id:#x} != {APPLICATION_ID:#x}")
        meta = read_package_meta(conn)
        missing = [k for k in PACKAGE_META_REQUIRED if k not in meta]
        if "build_complete" in missing:
            return fail("build_complete absent (abandoned build)", unlink=True, meta=meta)
        if missing:
            return fail(f"meta missing {missing}", meta=meta)
        if meta.get("build_complete") != "1":
            return fail(f"build_complete={meta.get('build_complete')!r}", unlink=True, meta=meta)
        try:
            version = int(meta["schema_version"])
        except ValueError:
            return fail(f"schema_version {meta['schema_version']!r} not an int", meta=meta)
        if version < SCHEMA_VERSION:
            return fail(f"schema_version {version} older than {SCHEMA_VERSION}", unlink=True, version=version, meta=meta)
        if version > SCHEMA_VERSION:
            return fail(f"schema_version {version} newer than {SCHEMA_VERSION}; ignoring", version=version, meta=meta)
        if meta["package_id"] != expected_package_id:
            return fail(f"meta.package_id {meta['package_id']!r} != {expected_package_id!r}", version=version, meta=meta)
        check = conn.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            return fail(f"quick_check: {check}", version=version, meta=meta)
        present = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        }
        absent = [t for t in expected_tables if t not in present]
        if absent:
            return fail(f"tables missing: {absent}", version=version, meta=meta)
        for table in fts_tables:
            try:
                conn.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
            except sqlite3.DatabaseError as exc:
                return fail(f"{table} integrity-check failed: {exc}", version=version, meta=meta)
        return PackageValidation(True, None, version, False, meta)
    except sqlite3.DatabaseError as exc:
        return fail(f"database error: {exc}")
    finally:
        conn.close()


def publish_package(temp_path: Path, final_path: Path) -> tuple[Path, bool]:
    """Atomically move a closed, validated temp build onto its final name.

    Returns ``(path_to_use, published)``. If another process already published
    the same package (destination exists), or the rename is refused because
    the destination is held open (Windows), the temp is discarded and the
    existing file adopted -- the loser rule (§10). The temp must be CLOSED
    before calling; a live connection would leave a journal behind.
    """
    temp_path = Path(temp_path)
    final_path = Path(final_path)
    if temp_path.parent != final_path.parent:
        raise ValueError("temp and final paths must share a directory (atomic rename)")
    if final_path.exists():
        _discard(temp_path)
        return final_path, False
    # Claim the final name ATOMICALLY: os.link fails with FileExistsError if
    # another builder got there first, which os.replace would silently
    # overwrite (two concurrent builders both "won" in V11 before this). Where
    # hard links are unsupported (some filesystems), fall back to os.replace.
    try:
        os.link(temp_path, final_path)
    except FileExistsError:
        logger.info("lost publication race for %s; adopting existing", final_path.name)
        _discard(temp_path)
        return final_path, False
    except OSError as exc:
        try:
            os.replace(temp_path, final_path)
        except OSError as exc2:
            if final_path.exists():
                logger.info("lost publication race for %s (%s); adopting existing", final_path.name, exc2)
                _discard(temp_path)
                return final_path, False
            raise
        logger.debug("published %s via os.replace (link unsupported: %s)", final_path.name, exc)
        return final_path, True
    _discard(temp_path)
    return final_path, True


def _discard(path: Path) -> None:
    for candidate in (path, path.with_name(path.name + "-journal")):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("could not remove %s: %s", candidate, exc)


# ---------------------------------------------------------------------------
# Administration (what the CLI renders)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackageFileInfo:
    name: str
    bytes: int
    package_id: str | None
    schema_version: int | None
    status: str  # current | stale | newer | unrecognized


@dataclass(frozen=True)
class CacheInfo:
    path: Path
    manifest_path: Path
    schema_version: int
    enabled: bool
    total_bytes: int
    cap_bytes: int
    packages: list[PackageFileInfo]
    temp_files: int


def describe(settings: CacheSettings) -> CacheInfo:
    """Everything ``congressmcp cache info`` prints, from the filesystem alone.
    Deliberately does not open the manifest: info must work on a broken one."""
    layout = settings.layout
    packages: list[PackageFileInfo] = []
    for path in layout.package_files():
        parsed = parse_package_filename(path.name)
        packages.append(
            PackageFileInfo(
                name=path.name,
                bytes=_size_or_zero(path),
                package_id=parsed.package_id if parsed else None,
                schema_version=parsed.schema_version if parsed else None,
                status=parsed.status if parsed else "unrecognized",
            )
        )
    return CacheInfo(
        path=layout.root,
        manifest_path=layout.manifest_path,
        schema_version=SCHEMA_VERSION,
        enabled=settings.enabled,
        total_bytes=sum(p.bytes for p in packages),
        cap_bytes=settings.max_bytes,
        packages=packages,
        temp_files=len(layout.temp_files()),
    )


@dataclass(frozen=True)
class ClearResult:
    removed_packages: int
    removed_temps: int
    removed_manifest: bool
    failed: list[str]


def clear(layout: CacheLayout) -> ClearResult:
    """``congressmcp cache clear``: unlink every package file, every temp build,
    and the manifest with its sidecars. Files that cannot be unlinked (Windows
    holding them open) are reported, never fatal."""
    failed: list[str] = []

    def _unlink(path: Path) -> bool:
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            failed.append(f"{path.name}: {exc.strerror or exc}")
            return False

    removed_packages = sum(1 for p in layout.package_files() if _unlink(p))
    removed_temps = sum(1 for p in layout.temp_files() if _unlink(p))
    manifest_files = layout.manifest_sidecars()
    # Attempt every sidecar (no short-circuit): a surviving -wal next to a
    # removed manifest.db would be replayed into the next fresh manifest.
    manifest_results = [_unlink(p) for p in manifest_files]
    removed_manifest = bool(manifest_files) and all(manifest_results)
    return ClearResult(removed_packages, removed_temps, removed_manifest, failed)
