"""The persistence path: build a package file, publish it atomically, serve
from it (spec §10).

    BillTextIndex(parsed, conn=create_package_db(temp))   # build into a temp
    -> close -> validate_package_file(temp)                # close-and-validate
    -> publish_package(temp, final)                        # os.replace; loser adopts
    -> BillTextIndex.from_connection(open read-only)       # serve the PUBLISHED file

Every consumer of a package file goes through ``PackageStore`` so the four
steps above are the only way a file reaches its final name (§10: adoption is
safe only because a file at its final name is complete by construction).

Manifest writes here are best-effort and never fail the user's call: the
filesystem is authoritative, the manifest is derived (§10).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import cache
from .index import FTS_TABLE, PACKAGE_TABLES, BillTextIndex
from .parser import ParsedBill

logger = logging.getLogger(__name__)

SOURCE_FORMAT = "bill_dtd"


class PackageBuildError(Exception):
    """A freshly built package failed close-and-validate; nothing was published."""


@dataclass(frozen=True)
class _Stamp:
    mtime_ns: int
    size: int
    ino: int


def _stamp(path: Path) -> _Stamp | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return _Stamp(st.st_mtime_ns, st.st_size, st.st_ino)


@dataclass
class ReconcileReport:
    """What one reconcile pass did (§10 recovery table + startup sweeps)."""

    stale_temps_removed: int = 0
    stale_schema_removed: int = 0
    newer_schema_ignored: int = 0
    unrecognized_ignored: int = 0
    rows_dropped_missing_file: int = 0
    files_adopted: int = 0
    files_invalid_unlinked: int = 0
    files_invalid_skipped: int = 0
    bytes_corrected: int = 0
    errors: list[str] = field(default_factory=list)

    def changed(self) -> bool:
        return any(
            getattr(self, name)
            for name in (
                "stale_temps_removed", "stale_schema_removed", "rows_dropped_missing_file",
                "files_adopted", "files_invalid_unlinked", "bytes_corrected",
            )
        )


@dataclass
class EvictionReport:
    """What one eviction pass did (§10)."""

    total_before: int = 0
    total_after: int = 0
    cap: int = 0
    evicted: list[str] = field(default_factory=list)
    skipped_protected: list[str] = field(default_factory=list)
    skipped_leased: list[str] = field(default_factory=list)
    skipped_locked: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def over_cap(self) -> bool:
        return self.total_after > self.cap


class PackageStore:
    """Package files under one cache root.

    ``fresh_path`` / ``open`` answer "is there a servable file for this package
    at this source lastModified"; ``build_and_publish`` turns a ParsedBill into
    one. A validated file is remembered by its stat signature so the seven-rule
    check (which includes an FTS integrity-check) runs once per distinct file,
    not on every hit.
    """

    def __init__(self, settings: cache.CacheSettings, *, reconcile: bool = True):
        self.settings = settings
        self.layout = settings.layout
        self._validated: dict[Path, tuple[_Stamp, str]] = {}
        self._manifest: cache.Manifest | None = None
        # Lease holder id for the best-effort cross-process eviction lease.
        self.holder = f"{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.last_reconcile: ReconcileReport | None = None
        self.last_eviction: EvictionReport | None = None
        if reconcile:
            # Startup reconcile (§10): one listdir + one manifest query. Never
            # fails construction -- a cache that cannot be reconciled is served
            # as found, and the filesystem is authoritative anyway.
            try:
                self.last_reconcile = self.reconcile()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("cache reconcile failed: %s", exc)

    # -- manifest (derived; best-effort) ------------------------------------

    def manifest(self) -> cache.Manifest | None:
        if self._manifest is None:
            try:
                self._manifest = cache.Manifest(self.layout.manifest_path)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("manifest unavailable: %s", exc)
                return None
        return self._manifest

    def _record_publish(self, package_id: str, path: Path, last_modified: str | None) -> None:
        manifest = self.manifest()
        if manifest is None:
            return
        try:
            now = time.time()
            manifest.upsert(
                cache.ManifestRow(
                    package_id=package_id,
                    filename=path.name,
                    schema_version=cache.SCHEMA_VERSION,
                    bytes=path.stat().st_size,
                    created_at=now,
                    last_accessed_at=now,
                    source_format=SOURCE_FORMAT,
                    source_last_modified=last_modified,
                )
            )
        except Exception as exc:
            logger.warning("manifest upsert failed for %s: %s", package_id, exc)

    def _record_hit(self, package_id: str) -> None:
        manifest = self.manifest()
        if manifest is None:
            return
        try:
            manifest.touch(package_id)
            manifest.lease(package_id, self.holder, time.time() + cache.LEASE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("manifest touch failed for %s: %s", package_id, exc)

    def close(self) -> None:
        if self._manifest is not None:
            self._manifest.close()
            self._manifest = None

    # -- lookup ---------------------------------------------------------------

    def _validate(self, path: Path, package_id: str) -> cache.PackageValidation:
        stamp = _stamp(path)
        if stamp is None:
            return cache.PackageValidation(False, "missing", None, False, {})
        remembered = self._validated.get(path)
        if remembered is not None and remembered[0] == stamp:
            return cache.PackageValidation(True, None, cache.SCHEMA_VERSION, False, {"source_last_modified": remembered[1]})
        verdict = cache.validate_package_file(
            path,
            expected_package_id=package_id,
            expected_tables=PACKAGE_TABLES,
            fts_tables=(FTS_TABLE,),
        )
        if verdict.ok:
            self._validated[path] = (stamp, verdict.meta.get("source_last_modified", ""))
        else:
            self._validated.pop(path, None)
        return verdict

    def _drop_row(self, package_id: str) -> None:
        """Lazy reconcile on a missing-file error (§10 recovery table: "manifest
        row, file missing -> drop the row, treat as miss")."""
        self._validated.pop(self.layout.package_path(package_id), None)
        manifest = self.manifest()
        if manifest is None:
            return
        try:
            if manifest.remove(package_id):
                logger.info("manifest row for %s dropped: file missing", package_id)
        except Exception as exc:
            logger.warning("manifest remove failed for %s: %s", package_id, exc)

    def fresh_path(self, package_id: str, last_modified: str | None) -> Path | None:
        """The published file for ``package_id`` if it validates and was built
        from the same source ``lastModified``. A file built from a different
        lastModified is a reissue (§10 freshness table: discard and rebuild); a
        file failing validation is skipped, and unlinked only where §10 allows.
        """
        path = self.layout.package_path(package_id)
        if not path.exists():
            self._drop_row(package_id)
            return None
        verdict = self._validate(path, package_id)
        if not verdict.ok:
            logger.info("package %s not servable: %s", path.name, verdict.reason)
            if verdict.unlink_advised:
                self._unlink(path, package_id)
            return None
        if last_modified is not None and verdict.meta.get("source_last_modified", "") != last_modified:
            logger.info(
                "package %s was built from lastModified %r, source now %r; discarding",
                path.name, verdict.meta.get("source_last_modified"), last_modified,
            )
            self._unlink(path, package_id)
            return None
        return path

    def open(self, package_id: str, last_modified: str | None) -> BillTextIndex | None:
        """Serve ``package_id`` from its published file, or ``None`` on a miss."""
        path = self.fresh_path(package_id, last_modified)
        if path is None:
            return None
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            index = BillTextIndex.from_connection(conn)
        except (sqlite3.Error, OSError, ValueError, KeyError) as exc:
            # Vanished or broke between validation and open: a miss, never an error.
            logger.warning("could not open package %s: %s", path.name, exc)
            self._validated.pop(path, None)
            if not path.exists():
                self._drop_row(package_id)
            return None
        self._record_hit(package_id)
        return index

    # -- build + publish -------------------------------------------------------

    def build_and_publish(self, parsed: ParsedBill, *, last_modified: str | None) -> tuple[BillTextIndex, bool]:
        """Build ``parsed`` into a temp file, close-and-validate, publish, and
        return the index SERVED FROM THE PUBLISHED FILE plus whether this call
        was the publisher. If another process published first, our temp is
        discarded and theirs is served (the loser rule). Raises
        ``PackageBuildError`` if the result cannot be served; the caller falls
        back to an in-memory index."""
        package_id = parsed.package_id
        self.layout.ensure_dirs()
        temp = self.layout.temp_path(package_id)
        conn = cache.create_package_db(temp)
        try:
            BillTextIndex(parsed, conn=conn)
            cache.write_package_meta(
                conn,
                package_id=package_id,
                source_format=SOURCE_FORMAT,
                source_last_modified=last_modified,
                build_complete=True,
            )
        except Exception:
            conn.close()
            _discard(temp)
            raise
        conn.close()  # closed BEFORE validation and publication; no journal may remain

        verdict = cache.validate_package_file(
            temp,
            expected_package_id=package_id,
            expected_tables=PACKAGE_TABLES,
            fts_tables=(FTS_TABLE,),
        )
        if not verdict.ok:
            _discard(temp)
            raise PackageBuildError(f"fresh build of {package_id} failed validation: {verdict.reason}")

        final = self.layout.package_path(package_id)
        path, published = cache.publish_package(temp, final)
        if published:
            self._record_publish(package_id, path, last_modified)
        else:
            logger.info("package %s was published concurrently; adopting the existing file", final.name)

        index = self.open(package_id, last_modified)
        if index is None:
            # The file at the final name (ours or the winner's) is not servable.
            raise PackageBuildError(f"published package {final.name} is not servable")
        if published:
            # After each index write, evict oldest until under cap (§10). Never
            # the package being served in this call; never fail the call.
            try:
                self.last_eviction = self.evict(protect={package_id})
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("eviction failed: %s", exc)
        return index, published

    def cached_versions(self, congress: int, bill_type: str, number: int) -> list[str]:
        """Version codes of this bill that have a package file on disk at the
        current schema (the filesystem is authoritative). Listed in the
        version_resolution_unavailable error so a caller can pin one offline."""
        import re as _re

        prefix = f"BILLS-{congress}{bill_type.lower()}{number}"
        pattern = _re.compile(rf"^{_re.escape(prefix)}([a-z][a-z0-9]*)$")
        versions = []
        for path in self.layout.package_files():
            parsed = cache.parse_package_filename(path.name)
            if parsed is None or not parsed.is_current:
                continue
            match = pattern.match(parsed.package_id)
            if match:
                versions.append(match.group(1))
        return sorted(set(versions))

    # -- startup reconcile / recovery (§10) ----------------------------------------

    def reconcile(self, *, now: float | None = None) -> ReconcileReport:
        """Bring manifest and disk back into agreement, disk winning (§10):

        - ``.tmp`` builds older than STALE_TEMP_SECONDS: unlink.
        - Package files at a *strictly older* schema: unlink (and drop the row);
          newer schema: ignore in place; unrecognized names: ignore.
        - Manifest row whose file is missing: drop the row.
        - File without a row: validate; adopt (row from stat + meta) or skip,
          unlinking only where validation says §10 allows.
        - Row whose ``bytes`` disagrees with ``stat``: trust stat, correct the row.
        - ``manifest.db`` missing or corrupt is handled by Manifest itself
          (created / unlinked-and-recreated), after which this scan rebuilds it.

        Exactly one directory listing and one manifest query; per-file
        validation happens only for files that have no row.
        """
        now = time.time() if now is None else now
        report = ReconcileReport()
        self.layout.ensure_dirs()
        current: dict[str, Path] = {}
        try:
            entries = list(self.layout.packages_dir.iterdir())  # the one listdir
        except OSError as exc:
            report.errors.append(f"listdir: {exc}")
            return report
        for path in entries:
            name = path.name
            if not path.is_file():
                continue
            if cache.parse_temp_filename(name) is not None:
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age > cache.STALE_TEMP_SECONDS:
                    if self._unlink_quiet(path):
                        report.stale_temps_removed += 1
                continue
            parsed = cache.parse_package_filename(name)
            if parsed is None:
                report.unrecognized_ignored += 1
                continue
            if parsed.is_stale:
                if self._unlink_quiet(path):
                    report.stale_schema_removed += 1
                continue
            if parsed.is_newer:
                report.newer_schema_ignored += 1
                continue
            current[parsed.package_id] = path

        manifest = self.manifest()
        if manifest is None:
            return report
        try:
            rows = {row.package_id: row for row in manifest.rows()}  # the one query
        except Exception as exc:
            report.errors.append(f"manifest query: {exc}")
            return report

        for package_id, row in rows.items():
            path = current.get(package_id)
            if path is None or path.name != row.filename:
                try:
                    manifest.remove(package_id)
                    report.rows_dropped_missing_file += 1
                except Exception as exc:
                    report.errors.append(f"drop {package_id}: {exc}")

        for package_id, path in current.items():
            stamp = _stamp(path)
            if stamp is None:
                continue
            row = rows.get(package_id)
            if row is not None and row.filename == path.name:
                if row.bytes != stamp.size:
                    try:
                        manifest.set_bytes(package_id, stamp.size)
                        report.bytes_corrected += 1
                    except Exception as exc:
                        report.errors.append(f"bytes {package_id}: {exc}")
                continue
            verdict = self._validate(path, package_id)
            if not verdict.ok:
                if verdict.unlink_advised:
                    self._unlink(path, package_id)
                    report.files_invalid_unlinked += 1
                else:
                    report.files_invalid_skipped += 1
                logger.info("reconcile: %s not adopted: %s", path.name, verdict.reason)
                continue
            try:
                st = path.stat()
                manifest.upsert(
                    cache.ManifestRow(
                        package_id=package_id,
                        filename=path.name,
                        schema_version=cache.SCHEMA_VERSION,
                        bytes=st.st_size,
                        created_at=st.st_mtime,
                        last_accessed_at=st.st_mtime,
                        source_format=verdict.meta.get("source_format") or SOURCE_FORMAT,
                        source_last_modified=verdict.meta.get("source_last_modified") or None,
                    )
                )
                report.files_adopted += 1
            except Exception as exc:
                report.errors.append(f"adopt {package_id}: {exc}")
        if report.changed() or report.errors:
            logger.info("cache reconcile: %s", report)
        return report

    def _unlink_quiet(self, path: Path) -> bool:
        self._validated.pop(path, None)
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.warning("could not unlink %s: %s", path.name, exc)
            return False

    # -- eviction (§10) --------------------------------------------------------------

    def evict(self, *, protect: set[str] | frozenset[str] = frozenset(), now: float | None = None) -> EvictionReport:
        """LRU-evict package files until the cap is met (§10).

        - Cap is CONGRESSMCP_CACHE_MAX_BYTES across packages/; the total is the
          sum of actual ``stat`` sizes of every package file, never manifest rows.
        - Candidates are manifest rows, least-recently-accessed first.
        - Never evict a package in ``protect`` (being served in this call), nor
          one whose lease is held by another process and unexpired (best-effort).
        - Windows cannot unlink an open file: an OSError skips that candidate and
          moves on. If every candidate is skipped, proceed over cap and log.
        - Never raises for the user's call.
        """
        now = time.time() if now is None else now
        report = EvictionReport(cap=self.settings.max_bytes)
        report.total_before = report.total_after = self.layout.total_bytes()
        if report.total_after <= report.cap:
            return report
        manifest = self.manifest()
        if manifest is None:
            logger.warning("cache over cap (%d > %d) and no manifest to evict by", report.total_after, report.cap)
            return report
        try:
            rows = manifest.rows()  # LRU order
        except Exception as exc:
            report.errors.append(f"manifest query: {exc}")
            return report
        for row in rows:
            if report.total_after <= report.cap:
                break
            if row.package_id in protect:
                report.skipped_protected.append(row.package_id)
                continue
            if (
                row.lease_holder
                and row.lease_holder != self.holder
                and row.lease_expires_at is not None
                and row.lease_expires_at > now
            ):
                report.skipped_leased.append(row.package_id)
                continue
            path = self.layout.packages_dir / row.filename
            size = _size(path)
            if size is None:
                # Row without a file: drop it (recovery table) and move on.
                self._drop_row(row.package_id)
                continue
            self._validated.pop(path, None)
            try:
                path.unlink()
            except FileNotFoundError:
                self._drop_row(row.package_id)
                continue
            except OSError as exc:
                report.skipped_locked.append(row.package_id)
                logger.info("eviction skipped %s: %s", row.filename, exc)
                continue
            report.total_after -= size
            report.evicted.append(row.package_id)
            try:
                manifest.remove(row.package_id)
            except Exception as exc:
                report.errors.append(f"row {row.package_id}: {exc}")
        if report.over_cap:
            logger.warning(
                "cache still over cap after eviction: %d > %d bytes (evicted %d; protected %d, leased %d, locked %d)",
                report.total_after, report.cap, len(report.evicted),
                len(report.skipped_protected), len(report.skipped_leased), len(report.skipped_locked),
            )
        elif report.evicted:
            logger.info("evicted %d package(s): %s", len(report.evicted), ", ".join(report.evicted))
        return report

    # -- helpers ------------------------------------------------------------------

    def _unlink(self, path: Path, package_id: str) -> None:
        self._validated.pop(path, None)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            # Windows: held open elsewhere. Skip; the file stays a non-servable miss.
            logger.warning("could not unlink %s: %s", path.name, exc)
            return
        manifest = self.manifest()
        if manifest is not None:
            try:
                manifest.remove(package_id)
            except Exception as exc:
                logger.warning("manifest remove failed for %s: %s", package_id, exc)


def _size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def _discard(path: Path) -> None:
    for candidate in (path, path.with_name(path.name + "-journal")):
        try:
            os.unlink(candidate)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("could not remove %s: %s", candidate, exc)
