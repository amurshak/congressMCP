"""Bill text retrieval service: the §10 freshness table, then serve from the
persistent cache or fetch-parse-build-publish.

| Situation | Behavior |
|---|---|
| Explicit ``version=`` (any) | ``version_resolution: "pinned"`` -- the caller named the version, no resolution ran; ``cache.version_hit`` false. |
| Explicit ``version=``, index cached | Serve from cache with no network. Revalidate only if ``now - created_at > CONGRESSMCP_REVALIDATE_DAYS``: fetch the GovInfo package summary, compare ``lastModified``; rebuild if changed. |
| ``version=None``, resolution cached and within ``CONGRESSMCP_VERSION_TTL`` | Use the cached resolution, no network. ``version_resolution: "cached"``, ``cache.version_hit: true``. |
| ``version=None``, TTL expired | Re-resolve via congress.gov (+ GovInfo package summary). |
| ``version=None``, network unavailable | Use the last successful resolution. ``version_resolution: "cached_offline"`` with ``version_resolved_at`` disclosed in ``version_resolution_note``. |
| ``version=None``, no cached resolution, no network | Error ``version_resolution_unavailable``, listing any cached versions of that bill. |
| Package reissued under the same id (``lastModified`` changed) | Discard and rebuild the index. |

Then the index: on a hit open the published file read-only (``cache.index_hit``
true, no parse); on a miss download, parse, build into a temp file,
close-and-validate, publish atomically (loser adopts), and serve the PUBLISHED
file; if the store cannot produce a servable file, serve an in-memory index --
the cache never fails the user's call. ``CONGRESSMCP_CACHE_ENABLED=false``
skips the store entirely: in-memory index, discarded per call, full re-fetch
and re-parse every time (§10 tunables).

Timing (§9): ``resolve_ms`` covers congress.gov resolution plus the GovInfo
package summary; ``download_ms`` the XML download; ``parse_ms``/``index_ms``
the parse and build. Each is null when that leg did not run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace

from mcp.server.mcpserver import Context

from . import trace
from .cache import CacheSettings, Resolution
from .client import (
    DOWNLOAD_SECONDS,
    BillTextError,
    ResolvedBillText,
    fetch_govinfo_package,
    is_offline_error,
    package_id_for,
    resolve_and_fetch_bill_text,
    utc_now,
)
from .index import BillTextIndex
from .parser import ParsedBill, parse_bill_xml
from .store import PackageBuildError, PackageStore

logger = logging.getLogger(__name__)


@dataclass
class LoadedBillText:
    resolved: ResolvedBillText
    parsed: ParsedBill
    index: BillTextIndex
    timing: dict[str, float | None] = field(default_factory=dict)
    # True when the index was served from a published package file rather than
    # parsed and built on this call (§9 ``cache.index_hit``).
    index_hit: bool = False
    # §9 ``version_resolution``: fresh | cached | cached_offline | pinned
    # ("pinned": the caller named the version; no resolution occurred).
    version_resolution: str = "fresh"
    # §9 ``cache.version_hit``: the version came from the cached resolution.
    version_hit: bool = False


_store: PackageStore | None = None
_store_key: tuple | None = None


def get_store() -> PackageStore | None:
    """The process-wide PackageStore for the current settings, or None when the
    persistent cache is disabled. Re-created if the environment's cache settings
    change (tests; operators toggling the env between calls)."""
    global _store, _store_key
    settings = CacheSettings.from_env()
    key = (settings.cache_dir, settings.enabled)
    if key != _store_key:
        if _store is not None:
            _store.close()
        _store = PackageStore(settings) if settings.enabled else None
        _store_key = key
    return _store


def reset_store() -> None:
    """Drop the cached PackageStore (tests)."""
    global _store, _store_key
    if _store is not None:
        _store.close()
    _store = None
    _store_key = None


@dataclass
class _Legs:
    """Per-call timing accumulators, seconds. None = the leg did not run."""

    resolve: float | None = None
    download: float | None = None
    parse: float | None = None
    index: float | None = None

    def add(self, leg: str, seconds: float) -> None:
        setattr(self, leg, (getattr(self, leg) or 0.0) + seconds)

    def as_ms(self) -> dict[str, float | None]:
        return {
            f"{leg}_ms": (round(value * 1000, 1) if value is not None else None)
            for leg, value in (("resolve", self.resolve), ("download", self.download),
                               ("parse", self.parse), ("index", self.index))
        }


async def load_bill_text(ctx: Context, congress: int, bill_type: str, number: int, version: str | None) -> LoadedBillText:
    store = get_store()
    settings = store.settings if store is not None else CacheSettings.from_env()
    bill_type = bill_type.lower()
    legs = _Legs()
    now = time.time()

    # -- Explicit version, index cached: serve with no network (revalidate when due).
    if version is not None and store is not None:
        served = await _serve_explicit_from_cache(store, settings, congress, bill_type, number, version.lower(), legs, now)
        if served is not None:
            return served

    # -- version=None: a cached resolution within the TTL needs no network at all.
    cached_resolution: Resolution | None = None
    if version is None and store is not None:
        cached_resolution = _get_resolution(store, congress, bill_type, number)
        if cached_resolution is not None and now - cached_resolution.resolved_at <= settings.version_ttl:
            return await _serve_cached_resolution(store, cached_resolution, "cached", legs, offline_error=None)

    # -- Fresh resolution over the network (the expired-TTL and first-call rows).
    def cached(package_id: str, last_modified: str | None) -> bool:
        # Asked by the client between the package summary and the XML download:
        # do we already hold a servable index for these exact source bytes?
        return store is not None and store.fresh_path(package_id, last_modified) is not None

    DOWNLOAD_SECONDS.set(None)
    t_resolve = time.perf_counter()
    try:
        resolved = await resolve_and_fetch_bill_text(
            ctx, congress, bill_type, number, version, skip_download=cached if store is not None else None
        )
    except Exception as exc:
        if version is None and store is not None and is_offline_error(exc):
            if cached_resolution is not None:
                # Network unavailable: last successful resolution, disclosed.
                return await _serve_cached_resolution(store, cached_resolution, "cached_offline", legs, offline_error=exc)
            raise BillTextError(
                "version_resolution_unavailable",
                f"Could not resolve the latest version of {bill_type.upper()} {number} "
                f"({congress}th Congress): the network is unavailable and no prior resolution is cached.",
                {
                    "cached_versions": store.cached_versions(congress, bill_type, number),
                    "cause": getattr(exc, "code", type(exc).__name__),
                },
                "Pass version= naming one of the cached versions to read it offline, or retry when the network is available.",
            ) from exc
        raise
    _account_network(legs, t_resolve)
    if version is None and store is not None:
        _put_resolution(store, congress, bill_type, number, resolved, now)

    return await _serve_resolved(
        store, resolved, legs,
        version_resolution="pinned" if version is not None else "fresh",
        version_hit=False, resolved_at=now,
    )


# ---------------------------------------------------------------------------
# Freshness-table rows
# ---------------------------------------------------------------------------


async def _serve_explicit_from_cache(
    store: PackageStore, settings: CacheSettings, congress: int, bill_type: str, number: int,
    version: str, legs: _Legs, now: float,
) -> LoadedBillText | None:
    """Explicit ``version=`` with a cached index: serve from cache, no network,
    unless revalidation is due (``created_at`` older than REVALIDATE_DAYS) -- then
    one package-summary call compares lastModified; a reissue is discarded and
    rebuilt (returns None so the normal path fetches); an unreachable GovInfo
    during revalidation serves the cached copy and logs."""
    package_id = package_id_for(congress, bill_type, number, version)
    if store.fresh_path(package_id, None) is None:
        return None
    row = None
    manifest = store.manifest()
    if manifest is not None:
        try:
            row = manifest.get(package_id)
        except Exception as exc:
            logger.warning("manifest read failed for %s: %s", package_id, exc)
    created_at = row.created_at if row is not None else now
    if now - created_at > settings.revalidate_days * 86400:
        t0 = time.perf_counter()
        try:
            last_modified, _ = await fetch_govinfo_package(package_id, skip_download=lambda *_: True)
        except Exception as exc:
            legs.add("resolve", time.perf_counter() - t0)
            logger.info("revalidation of %s skipped (%s); serving the cached copy", package_id, exc)
        else:
            legs.add("resolve", time.perf_counter() - t0)
            if store.fresh_path(package_id, last_modified) is None:
                return None  # reissued: fresh_path discarded it; rebuild via the normal path
            if manifest is not None:
                try:
                    manifest.set_created_at(package_id, now)
                except Exception as exc:
                    logger.warning("manifest set_created_at failed for %s: %s", package_id, exc)
    index = store.open(package_id, None)
    if index is None:
        return None
    resolved = ResolvedBillText(
        package_id=package_id,
        version=version,
        version_resolved_at=utc_now(),
        version_resolution_note=None,
        last_modified=index.parsed.last_modified,
        xml_bytes=None,
    )
    trace.set_source(package_id, version, None)
    return LoadedBillText(resolved, index.parsed, index, legs.as_ms(), index_hit=True,
                          version_resolution="pinned", version_hit=False)


async def _serve_cached_resolution(
    store: PackageStore, resolution: Resolution, mode: str, legs: _Legs, *, offline_error: BaseException | None,
) -> LoadedBillText:
    """version=None served from the cached resolution: "cached" (within TTL, no
    network) or "cached_offline" (TTL expired, network unavailable). The index
    is opened from cache; if it is gone, "cached" fetches it (the resolution is
    still trusted), "cached_offline" cannot and re-raises the network error."""
    note = resolution.note
    if mode == "cached_offline":
        disclosure = (
            f"Version resolution is being served from a cached result made at "
            f"{resolution.resolved_at_iso}; the network was unavailable, so a newer "
            f"version may exist."
        )
        note = " ".join(part for part in (note, disclosure) if part) or None
    resolved = ResolvedBillText(
        package_id=resolution.package_id,
        version=resolution.version,
        version_resolved_at=resolution.resolved_at_iso,
        version_resolution_note=note,
        last_modified=None,
        xml_bytes=None,
    )
    index = store.open(resolution.package_id, None)
    if index is None:
        if offline_error is not None:
            raise offline_error
        # Within the TTL but the index is gone (evicted, cleared): fetch it.
        DOWNLOAD_SECONDS.set(None)
        t0 = time.perf_counter()
        last_modified, xml_bytes = await fetch_govinfo_package(resolution.package_id)
        _account_network(legs, t0)
        resolved = replace(resolved, last_modified=last_modified, xml_bytes=xml_bytes)
        return await _serve_resolved(store, resolved, legs, version_resolution=mode, version_hit=True,
                                     resolved_at=resolution.resolved_at)
    resolved = replace(resolved, last_modified=index.parsed.last_modified)
    trace.set_source(resolved.package_id, resolved.version, None)
    _mark_resolved(store, resolved.package_id, resolution.resolved_at)
    return LoadedBillText(resolved, index.parsed, index, legs.as_ms(), index_hit=True,
                          version_resolution=mode, version_hit=True)


async def _serve_resolved(
    store: PackageStore | None, resolved: ResolvedBillText, legs: _Legs, *,
    version_resolution: str, version_hit: bool, resolved_at: float,
) -> LoadedBillText:
    """The index half, given a resolution that reached GovInfo: hit -> open the
    published file; miss -> download (if not already), parse, build, publish,
    serve the published file; in-memory fallback if the store cannot."""
    index: BillTextIndex | None = None
    index_hit = False
    if resolved.xml_bytes is None:
        # The store said it had the file a moment ago. Open it; if it vanished in
        # between (eviction, `cache clear`, another process), refetch -- the
        # recovery table's "file missing -> treat as miss, refetch".
        index = store.open(resolved.package_id, resolved.last_modified) if store is not None else None
        if index is not None:
            index_hit = True
        else:
            DOWNLOAD_SECONDS.set(None)
            t0 = time.perf_counter()
            last_modified, xml_bytes = await fetch_govinfo_package(resolved.package_id)
            _account_network(legs, t0)
            resolved = replace(resolved, last_modified=last_modified, xml_bytes=xml_bytes)

    # Stamp which exact bytes produced this response for replay (debug tracing only;
    # the sha256 is computed solely when CONGRESSMCP_TRACE_DIR is set).
    trace.set_source(resolved.package_id, resolved.version, resolved.xml_bytes)

    if index is None:
        assert resolved.xml_bytes is not None
        t_parse = time.perf_counter()
        parsed = parse_bill_xml(resolved.xml_bytes, resolved.package_id, resolved.version, resolved.last_modified)
        t_index = time.perf_counter()
        legs.add("parse", t_index - t_parse)
        if store is not None:
            try:
                index, _published = store.build_and_publish(parsed, last_modified=resolved.last_modified)
            except PackageBuildError as exc:
                logger.warning("%s; serving an in-memory index for this call", exc)
            except Exception as exc:  # the cache must never fail the user's call
                logger.warning("persistent cache failed for %s (%s); serving in memory", resolved.package_id, exc)
        if index is None:
            index = BillTextIndex(parsed)
        else:
            parsed = index.parsed
        legs.add("index", time.perf_counter() - t_index)
    else:
        parsed = index.parsed
    if store is not None and version_hit:
        _mark_resolved(store, resolved.package_id, resolved_at)
    return LoadedBillText(resolved, parsed, index, legs.as_ms(), index_hit=index_hit,
                          version_resolution=version_resolution, version_hit=version_hit)


# ---------------------------------------------------------------------------
# Helpers (manifest access is best-effort: the filesystem is authoritative)
# ---------------------------------------------------------------------------


def _account_network(legs: _Legs, started: float) -> None:
    """Split the elapsed network time into resolve (everything but the XML
    download) and download (what fetch_govinfo_package measured)."""
    elapsed = time.perf_counter() - started
    download = DOWNLOAD_SECONDS.get()
    if download is not None:
        legs.add("download", download)
        elapsed = max(0.0, elapsed - download)
    legs.add("resolve", elapsed)


def _get_resolution(store: PackageStore, congress: int, bill_type: str, number: int) -> Resolution | None:
    manifest = store.manifest()
    if manifest is None:
        return None
    try:
        return manifest.get_resolution(congress, bill_type, number)
    except Exception as exc:
        logger.warning("manifest resolution read failed: %s", exc)
        return None


def _put_resolution(store: PackageStore, congress: int, bill_type: str, number: int, resolved: ResolvedBillText, now: float) -> None:
    manifest = store.manifest()
    if manifest is None:
        return
    try:
        manifest.put_resolution(
            Resolution(
                congress=congress,
                bill_type=bill_type,
                number=number,
                package_id=resolved.package_id,
                version=resolved.version,
                resolved_at=now,
                resolved_at_iso=resolved.version_resolved_at,
                note=resolved.version_resolution_note,
            )
        )
    except Exception as exc:
        logger.warning("manifest resolution write failed: %s", exc)


def _mark_resolved(store: PackageStore, package_id: str, resolved_at: float) -> None:
    manifest = store.manifest()
    if manifest is None:
        return
    try:
        manifest.mark_resolved(package_id, resolved_at)
    except Exception as exc:
        logger.warning("manifest mark_resolved failed for %s: %s", package_id, exc)
