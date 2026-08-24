"""V11 — persistent cache sweep (spec §14 / 10-fixtures-verification.md, §10).

    Cap at ~20MB, index several bills, confirm LRU fires, files unlinked, disk
    reclaimed, manifest consistent. Then exercise every recovery row: delete a
    package DB under the manifest; delete manifest.db; truncate it; drop an
    orphan DB; drop a *newer*-schema DB and confirm it is ignored, not deleted;
    bump the schema and confirm only older files are swept. Failure injection:
    kill mid-build and confirm the .tmp is cleaned and no partial DB is adopted;
    two processes building the same package simultaneously; manifest locked;
    malformed XML; FTS5 unavailable; over-large response.

Runs OFFLINE against the real build path using the extended corpus XMLs in
tests/corpus/cache/ (populate with tests/corpus/fetch_corpus.py). Every
scenario drives the shipped code (PackageStore / service / tools) against a
real cache directory under --out and records what it observed. Kill-mid-build,
concurrent builders, the schema bump and the manifest lock run as separate OS
processes, because that is what they claim to test.

    python tests/corpus/v11.py [--out runs/v11/<ts>] [--live]

--live adds one real cold/warm/pinned pass through the service (needs
CONGRESS_API_KEY). Exit 0 iff every scenario PASSed. Writes report.json and
report.md under --out. A scenario that errors is recorded as FAIL with the
exception -- a sweep that errors must not look like a sweep that found nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import textwrap
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from congress_api.features.bill_text import cache  # noqa: E402
from congress_api.features.bill_text.client import BillTextError  # noqa: E402
from congress_api.features.bill_text.parser import parse_bill_xml  # noqa: E402
from congress_api.features.bill_text.store import PackageStore  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "cache"
CAP = 20 * 1024 * 1024
# Enrolled bills from the extended corpus, largest indexes first so the cap
# fires early. (package_id, version) -- lastModified is synthetic: the build
# path does not consult the network here.
BILLS = [
    ("BILLS-117hr7776enr", "enr"),
    ("BILLS-116hr133enr", "enr"),
    ("BILLS-116hr6395enr", "enr"),
    ("BILLS-119s1071enr", "enr"),
    ("BILLS-116s1790enr", "enr"),
    ("BILLS-115hr2810enr", "enr"),
]
LM = "2025-01-01T00:00:00Z"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


class Scenario:
    def __init__(self, name: str):
        self.name = name
        self.checks: list[tuple[str, bool]] = []
        self.observations: dict = {}
        self.error: str | None = None

    def check(self, label: str, ok: bool) -> None:
        self.checks.append((label, bool(ok)))

    @property
    def passed(self) -> bool:
        return self.error is None and bool(self.checks) and all(ok for _, ok in self.checks)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "pass": self.passed,
            "checks": [{"check": c, "ok": ok} for c, ok in self.checks],
            "observations": self.observations,
            "error": self.error,
        }


def corpus_xml(package_id: str) -> bytes:
    path = CORPUS / f"{package_id}.xml"
    if not path.exists():
        raise FileNotFoundError(f"{path} -- populate tests/corpus/cache with tests/corpus/fetch_corpus.py")
    return path.read_bytes()


def fresh_store(root: Path, *, max_bytes: int = CAP, reconcile: bool = True) -> PackageStore:
    return PackageStore(cache.CacheSettings(cache_dir=root, max_bytes=max_bytes), reconcile=reconcile)


def listing(store: PackageStore) -> dict:
    layout = store.layout
    files = sorted(p.name for p in layout.package_files())
    temps = sorted(p.name for p in layout.temp_files())
    rows = []
    m = store.manifest()
    if m is not None:
        rows = sorted(r.filename for r in m.rows())
    return {"files": files, "temps": temps, "manifest_rows": rows, "total_bytes": layout.total_bytes()}


def build(store: PackageStore, package_id: str, version: str, last_modified: str = LM):
    parsed = parse_bill_xml(corpus_xml(package_id), package_id, version, last_modified)
    index, published = store.build_and_publish(parsed, last_modified=last_modified)
    units = len(index.parsed.units)
    index.close()
    return published, units


# ---------------------------------------------------------------------------
# S1. Cap / LRU / reclaim / manifest consistency
# ---------------------------------------------------------------------------


def s1_cap_lru(root: Path) -> Scenario:
    sc = Scenario("S1 cap ~20MB: LRU fires, files unlinked, disk reclaimed, manifest consistent")
    store = fresh_store(root)
    steps = []
    access_order: list[str] = []
    try:
        for i, (pid, ver) in enumerate(BILLS):
            published, units = build(store, pid, ver)
            ev = store.last_eviction
            snap = listing(store)
            access_order = [p for p in access_order if p not in (ev.evicted if ev else [])] + [pid]
            present = {cache.parse_package_filename(f).package_id for f in snap["files"]}
            steps.append({
                "built": pid, "units": units, "published": published,
                "file_bytes": store.layout.package_path(pid).stat().st_size,
                "total_bytes_after": snap["total_bytes"],
                "evicted": list(ev.evicted) if ev else [],
                "skipped_protected": list(ev.skipped_protected) if ev else [],
                "over_cap_after": bool(ev and ev.over_cap),
                "files_after": sorted(present),
                "manifest_rows_after": snap["manifest_rows"],
            })
            # Invariants after every write.
            sc.check(f"[{pid}] manifest rows == files on disk", set(snap["manifest_rows"]) == set(snap["files"]))
            sc.check(f"[{pid}] no temp files left", snap["temps"] == [])
            sc.check(f"[{pid}] under cap, or only the just-served package is over it alone",
                     snap["total_bytes"] <= CAP or present == {pid})
            for gone in (ev.evicted if ev else []):
                sc.check(f"[{pid}] evicted {gone} is unlinked", not store.layout.package_path(gone).exists())
                sc.check(f"[{pid}] evicted {gone} has no manifest row", store.manifest().get(gone) is None)
            # LRU: anything evicted must be older in access order than everything kept.
            if ev and ev.evicted:
                kept = [p for p in access_order if p in present and p != pid]
                oldest_kept_idx = min((access_order.index(p) for p in kept), default=len(access_order))
                sc.check(f"[{pid}] evicted set is the LRU prefix",
                         all(access_order.index(g) < oldest_kept_idx if g in access_order else True for g in ev.evicted))
        sc.check("LRU fired at least once", any(s["evicted"] for s in steps))
        before_total = sum(s["file_bytes"] for s in steps)
        sc.check("disk reclaimed: final total < sum of all built files", steps[-1]["total_bytes_after"] < before_total)
        # Touch the oldest survivor, build one more: the OTHER survivor must go.
        survivors = [cache.parse_package_filename(f).package_id for f in listing(store)["files"]]
        if len(survivors) >= 2:
            m = store.manifest()
            lru = m.rows()[0].package_id
            idx = store.open(lru, None)
            idx.close()
            published, _ = build(store, "BILLS-117hr2471enr", "enr")
            ev = store.last_eviction
            sc.check("touched (recently accessed) survivor was NOT evicted", lru not in (ev.evicted if ev else []))
            steps.append({"built": "BILLS-117hr2471enr", "touched_before": lru, "evicted": list(ev.evicted) if ev else [],
                          "files_after": listing(store)["files"]})
        sc.observations["steps"] = steps
        sc.observations["cap_bytes"] = CAP
        sc.observations["final"] = listing(store)
    except Exception:
        sc.error = traceback.format_exc()
    finally:
        store.close()
    return sc


# ---------------------------------------------------------------------------
# S2. Every recovery row
# ---------------------------------------------------------------------------


def s2_recovery(root: Path) -> list[Scenario]:
    out = []
    store = fresh_store(root, max_bytes=10**12)
    a, b = BILLS[3], BILLS[5]  # two smaller bills
    build(store, *a)
    build(store, *b)
    store.close()

    # (a) delete a package DB under the manifest
    sc = Scenario("S2a manifest row, file missing -> row dropped, miss, (refetch is the caller's)")
    try:
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        path = store.layout.package_path(a[0])
        path.unlink()
        lazy = store.fresh_path(a[0], None)
        sc.check("lazy: fresh_path reports a miss", lazy is None)
        sc.check("lazy: manifest row dropped on the miss", store.manifest().get(a[0]) is None)
        # and the startup path, independently:
        store.manifest().upsert(cache.ManifestRow(a[0], path.name, cache.SCHEMA_VERSION, 1, 1.0, 1.0))
        report = store.reconcile()
        sc.check("startup: reconcile drops the row", report.rows_dropped_missing_file == 1 and store.manifest().get(a[0]) is None)
        sc.observations = {"report": report.__dict__, "listing": listing(store)}
        store.close()
        # restore for the next rows
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        build(store, *a)
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)

    # (b) delete manifest.db
    sc = Scenario("S2b manifest.db missing -> rebuilt by scanning packages/")
    try:
        layout = cache.CacheLayout(root)
        for p in layout.manifest_sidecars():
            p.unlink()
        store = fresh_store(root, max_bytes=10**12)
        rep = store.last_reconcile
        snap = listing(store)
        sc.check("rows rebuilt == files", set(snap["manifest_rows"]) == set(snap["files"]) and len(snap["files"]) == 2)
        sc.check("both adopted via validation", rep.files_adopted == 2)
        sc.observations = {"report": rep.__dict__, "listing": snap}
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)

    # (c) truncate manifest.db
    sc = Scenario("S2c manifest.db corrupt (truncated) -> unlinked and rebuilt")
    try:
        layout = cache.CacheLayout(root)
        for p in layout.manifest_sidecars():
            if p.name != cache.MANIFEST_FILENAME:
                p.unlink()
        data = layout.manifest_path.read_bytes()
        layout.manifest_path.write_bytes(data[: max(100, len(data) // 3)])
        store = fresh_store(root, max_bytes=10**12)
        rep = store.last_reconcile
        snap = listing(store)
        sc.check("store constructed", True)
        sc.check("rows rebuilt == files", set(snap["manifest_rows"]) == set(snap["files"]) and len(snap["files"]) == 2)
        sc.observations = {"truncated_to_bytes": max(100, len(data) // 3), "report": rep.__dict__, "listing": snap}
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)

    # (d) orphan DBs: one valid (adopted), one garbage (skipped, left)
    sc = Scenario("S2d file without manifest row -> validated: valid adopted, garbage skipped and left")
    try:
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        store.manifest().remove(a[0])  # make a a valid orphan
        garbage = store.layout.package_path("BILLS-111hr1enr")
        garbage.write_bytes(b"not a sqlite file" * 100)
        rep = store.reconcile()
        sc.check("valid orphan adopted", rep.files_adopted == 1 and store.manifest().get(a[0]) is not None)
        sc.check("garbage orphan skipped, not adopted", rep.files_invalid_skipped == 1 and store.manifest().get("BILLS-111hr1enr") is None)
        sc.check("garbage orphan left in place (§10: unlink only older schema / abandoned build)", garbage.exists())
        sc.observations = {"report": rep.__dict__, "listing": listing(store)}
        garbage.unlink()
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)

    # (e) newer-schema DB ignored, not deleted
    sc = Scenario("S2e newer-schema package file -> ignored in place, never adopted, never deleted")
    try:
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        newer = store.layout.packages_dir / cache.package_filename("BILLS-115hr1625enr", cache.SCHEMA_VERSION + 1)
        shutil.copy(store.layout.package_path(a[0]), newer)
        # A genuinely newer package: its meta/user_version agree with the name.
        # (Adoption validation trusts meta -- a v1 body under a v2 name would be
        # swept as older by a v2 binary, correctly.)
        conn = sqlite3.connect(str(newer))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (str(cache.SCHEMA_VERSION + 1),))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('package_id', 'BILLS-115hr1625enr')")
        conn.execute(f"PRAGMA user_version = {cache.SCHEMA_VERSION + 1}")
        conn.commit()
        conn.close()
        rep = store.reconcile()
        sc.check("reconcile counted it as newer", rep.newer_schema_ignored == 1)
        sc.check("file still present", newer.exists())
        sc.check("no manifest row for it", store.manifest().get("BILLS-115hr1625enr") is None)
        sc.check("fresh_path for that package (current schema) is a miss", store.fresh_path("BILLS-115hr1625enr", None) is None)
        sc.check("file STILL present after the miss", newer.exists())
        info = cache.describe(cache.CacheSettings(cache_dir=root))
        sc.check("cache info lists it as 'newer'", any(p.name == newer.name and p.status == "newer" for p in info.packages))
        sc.observations = {"report": rep.__dict__, "listing": listing(store)}
        store.close()
        # leave `newer` in place for (f)
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)

    # (f) bump the schema in a subprocess: only OLDER files swept
    sc = Scenario("S2f schema bumped (subprocess, SCHEMA_VERSION+1) -> only strictly-older files swept; newer ignored")
    try:
        layout = cache.CacheLayout(root)
        before = sorted(p.name for p in layout.package_files())
        much_newer = layout.packages_dir / cache.package_filename("BILLS-115hr2810enr", cache.SCHEMA_VERSION + 3)
        much_newer.write_bytes(b"x")
        script = textwrap.dedent(f"""
            import sys; sys.path.insert(0, {str(REPO)!r})
            from pathlib import Path
            from congress_api.features.bill_text import cache
            cache.SCHEMA_VERSION = {cache.SCHEMA_VERSION + 1}
            from congress_api.features.bill_text.store import PackageStore
            s = PackageStore(cache.CacheSettings(cache_dir=Path({str(root)!r}), max_bytes=10**12))
            import json; print(json.dumps(s.last_reconcile.__dict__))
        """)
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)
        rep = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else {"stderr": proc.stderr}
        after = sorted(p.name for p in layout.package_files())
        v_current = [n for n in before if cache.parse_package_filename(n).schema_version == cache.SCHEMA_VERSION]
        sc.check("subprocess ran", proc.returncode == 0)
        sc.check("every current-schema (now older) file swept", all(n not in after for n in v_current))
        sc.check("the +1 file (now current) kept", (layout.packages_dir / cache.package_filename("BILLS-115hr1625enr", cache.SCHEMA_VERSION + 1)).exists())
        sc.check("the +3 file (newer) kept", much_newer.exists())
        sc.check("report counts match", rep.get("stale_schema_removed") == len(v_current) and rep.get("newer_schema_ignored") == 1)
        sc.observations = {"before": before, "after": after, "subprocess_report": rep}
    except Exception:
        sc.error = traceback.format_exc()
    out.append(sc)
    return out


# ---------------------------------------------------------------------------
# S3. Failure injection
# ---------------------------------------------------------------------------


def s3_kill_mid_build(root: Path) -> Scenario:
    sc = Scenario("S3a kill -9 mid-build -> .tmp left, never adopted, swept by reconcile after 1h; no partial DB at final name")
    pid, ver = BILLS[3]
    script = textwrap.dedent(f"""
        import sys, time; sys.path.insert(0, {str(REPO)!r})
        from congress_api.features.bill_text import cache
        real = cache.write_package_meta
        def slow(conn, **kw):
            # the index is fully written; we stall BEFORE build_complete is written
            print("STALLING", flush=True); time.sleep(120)
        cache.write_package_meta = slow
        from congress_api.features.bill_text.store import PackageStore
        from congress_api.features.bill_text.parser import parse_bill_xml
        from pathlib import Path
        xml = Path({str(CORPUS / (pid + '.xml'))!r}).read_bytes()
        s = PackageStore(cache.CacheSettings(cache_dir=Path({str(root)!r}), max_bytes=10**12), reconcile=False)
        s.build_and_publish(parse_bill_xml(xml, {pid!r}, {ver!r}, {LM!r}), last_modified={LM!r})
    """)
    try:
        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        line = proc.stdout.readline()
        while line and "STALLING" not in line:
            line = proc.stdout.readline()
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=30)
        layout = cache.CacheLayout(root)
        temps = [p for p in layout.temp_files()]
        final = layout.package_path(pid)
        sc.check("child was killed", proc.returncode == -signal.SIGKILL)
        sc.check("a .tmp was left behind", len(temps) >= 1)
        sc.check("nothing at the final name", not final.exists())
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        sc.check("fresh_path does not adopt the partial build", store.fresh_path(pid, None) is None)
        verdicts = [cache.validate_package_file(t, expected_package_id=pid, expected_tables=("units",)) for t in temps]
        sc.check("the .tmp fails validation for want of build_complete",
                 all((not v.ok) and "build_complete" in (v.reason or "") for v in verdicts))
        # Young temp survives a normal reconcile; a >1h one is swept.
        rep_now = store.reconcile()
        sc.check("fresh .tmp (< 1h) NOT swept", rep_now.stale_temps_removed == 0 and all(t.exists() for t in temps))
        rep_later = store.reconcile(now=time.time() + cache.STALE_TEMP_SECONDS + 60)
        sc.check("stale .tmp (> 1h) swept", rep_later.stale_temps_removed == len(temps) and not any(t.exists() for t in temps))
        sc.check("still nothing adopted at the final name", not final.exists() and store.manifest().get(pid) is None)
        sc.observations = {"temps": [t.name for t in temps], "validation": [v.reason for v in verdicts],
                           "reconcile_now": rep_now.__dict__, "reconcile_later": rep_later.__dict__}
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    return sc


def s3_concurrent_builders(root: Path) -> Scenario:
    sc = Scenario("S3b two processes build the same package simultaneously -> one file, both serve, loser adopted")
    pid, ver = BILLS[3]
    start_at = time.time() + 2.0
    script = textwrap.dedent(f"""
        import sys, time, json; sys.path.insert(0, {str(REPO)!r})
        from congress_api.features.bill_text import cache
        from congress_api.features.bill_text.store import PackageStore
        from congress_api.features.bill_text.parser import parse_bill_xml
        from pathlib import Path
        xml = Path({str(CORPUS / (pid + '.xml'))!r}).read_bytes()
        parsed = parse_bill_xml(xml, {pid!r}, {ver!r}, {LM!r})
        s = PackageStore(cache.CacheSettings(cache_dir=Path({str(root)!r}), max_bytes=10**12), reconcile=False)
        while time.time() < {start_at!r}: time.sleep(0.005)
        idx, published = s.build_and_publish(parsed, last_modified={LM!r})
        print(json.dumps({{"published": published, "units": len(idx.parsed.units), "hits": len(idx.search(["Secretary"], 5))}}))
    """)
    try:
        procs = [subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        results = []
        for p in procs:
            out, err = p.communicate(timeout=300)
            results.append({"rc": p.returncode, "out": out.strip().splitlines()[-1] if out.strip() else "", "err_tail": err[-400:]})
        parsed = [json.loads(r["out"]) for r in results if r["rc"] == 0 and r["out"]]
        layout = cache.CacheLayout(root)
        snap = {"files": sorted(p.name for p in layout.package_files()), "temps": sorted(p.name for p in layout.temp_files())}
        sc.check("both processes succeeded", len(parsed) == 2)
        sc.check("exactly one package file", snap["files"] == [cache.package_filename(pid)])
        sc.check("no temp left", snap["temps"] == [])
        sc.check("both served the same content", len({p["units"] for p in parsed}) == 1 and all(p["hits"] > 0 for p in parsed))
        sc.check("exactly one publisher; the other adopted (loser rule under a real race)", sum(1 for p in parsed if p["published"]) == 1)
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        sc.check("one manifest row", [r.package_id for r in store.manifest().rows()].count(pid) == 1)
        store.close()
        sc.observations = {"processes": results, "listing": snap}
    except Exception:
        sc.error = traceback.format_exc()
    return sc


def s3_manifest_locked(root: Path) -> Scenario:
    sc = Scenario("S3c manifest locked by another process -> call still succeeds (busy_timeout, then logged)")
    pid, ver = BILLS[3]
    try:
        store = fresh_store(root, max_bytes=10**12, reconcile=False)
        if store.fresh_path(pid, None) is None:
            build(store, pid, ver)
        locker = subprocess.Popen(
            [sys.executable, "-c", textwrap.dedent(f"""
                import sqlite3, time
                c = sqlite3.connect({str(store.layout.manifest_path)!r}, isolation_level=None)
                c.execute("BEGIN IMMEDIATE"); print("LOCKED", flush=True); time.sleep(12)
                c.execute("COMMIT")
            """)],
            stdout=subprocess.PIPE, text=True,
        )
        locker.stdout.readline()  # LOCKED
        t0 = time.perf_counter()
        idx = store.open(pid, None)  # hit path: touch + lease under the lock
        open_s = time.perf_counter() - t0
        served = idx is not None and len(idx.search(["Secretary"], 3)) >= 0
        if idx:
            idx.close()
        t1 = time.perf_counter()
        other = BILLS[5]
        published, units = build(store, *other)  # publish path: upsert under the lock
        pub_s = time.perf_counter() - t1
        locker.wait(timeout=30)
        sc.check("hit served while manifest locked", served)
        sc.check("hit waited about busy_timeout (>= 4s) rather than failing instantly or hanging", 4.0 <= open_s <= 30.0)
        sc.check("publish succeeded while manifest locked", published and store.layout.package_path(other[0]).exists())
        sc.observations = {"open_seconds": round(open_s, 2), "publish_seconds": round(pub_s, 2), "busy_timeout_ms": cache.MANIFEST_BUSY_TIMEOUT_MS}
        store.close()
    except Exception:
        sc.error = traceback.format_exc()
    return sc


async def _tool_error_scenario(root: Path, name: str, fetch_impl, expected_code: str, *, break_fts: bool = False) -> Scenario:
    """Drive the SERVICE/TOOL path with a fake GovInfo fetch; assert the error
    envelope and that nothing was published or left behind."""
    import congress_api.features.bill_text.client as client_mod
    import congress_api.features.bill_text.service as service_mod
    import congress_api.features.bill_text.tools as tools_mod
    from congress_api.features.bill_text.client import TextVersion

    sc = Scenario(name)
    saved = (client_mod._resolve_versions, client_mod.fetch_govinfo_package, service_mod.fetch_govinfo_package, tools_mod.sqlite_supports_fts5)
    os.environ[cache.ENV_CACHE_DIR] = str(root)
    os.environ.pop(cache.ENV_CACHE_ENABLED, None)
    service_mod.reset_store()
    try:
        async def resolve(ctx, congress, bill_type, number):
            return [TextVersion("enr", "2025-01-01", "Enrolled Bill")]
        client_mod._resolve_versions = resolve
        client_mod.fetch_govinfo_package = fetch_impl
        service_mod.fetch_govinfo_package = fetch_impl
        if break_fts:
            tools_mod.sqlite_supports_fts5 = lambda: False
        before = listing(fresh_store(root, max_bytes=10**12, reconcile=False))
        resp = await tools_mod.search_bill_text(None, congress=119, bill_type="hr", number=9999, queries=["Secretary"], max_hits=3)
        after = listing(fresh_store(root, max_bytes=10**12, reconcile=False))
        sc.check("response is an error envelope", "error" in resp and isinstance(resp["error"], dict))
        sc.check(f"error.code == {expected_code}", resp.get("error", {}).get("code") == expected_code)
        sc.check("no package published", after["files"] == before["files"])
        sc.check("no temp left behind", after["temps"] == [])
        sc.observations = {"error": resp.get("error"), "listing_after": after}
    except Exception:
        sc.error = traceback.format_exc()
    finally:
        client_mod._resolve_versions, client_mod.fetch_govinfo_package, service_mod.fetch_govinfo_package, tools_mod.sqlite_supports_fts5 = saved
        service_mod.reset_store()
    return sc


async def s3_injections(root: Path) -> list[Scenario]:
    out = []

    async def malformed(package_id, *, skip_download=None):
        return LM, b"<bill><legis-body><section id='x'><enum>1.</enum><header>Unclosed"

    out.append(await _tool_error_scenario(root, "S3d malformed XML -> clean error envelope, nothing published", malformed, "internal_error"))

    async def fine(package_id, *, skip_download=None):
        return LM, corpus_xml(BILLS[3][0])

    out.append(await _tool_error_scenario(root, "S3e FTS5 unavailable -> fts5_unavailable, nothing published", fine, "fts5_unavailable", break_fts=True))

    from congress_api.features.bill_text.client import MAX_XML_BYTES

    async def too_large(package_id, *, skip_download=None):
        # Exactly what the real client raises once the streamed body passes MAX_XML_BYTES.
        raise BillTextError("document_too_large", f"GovInfo XML exceeded {MAX_XML_BYTES} bytes.")

    out.append(await _tool_error_scenario(root, "S3f over-large response -> document_too_large, nothing published", too_large, "document_too_large"))
    return out


# ---------------------------------------------------------------------------
# S4 (optional). Live pass through the service
# ---------------------------------------------------------------------------


async def s4_live(root: Path) -> Scenario:
    sc = Scenario("S4 (live) S.1071/119 cold -> warm (cached, no network) -> pinned")
    try:
        import httpx
        from dataclasses import dataclass
        from congress_api.core.client_handler import AppContext, SimpleCache
        from congress_api.core.api_config import BASE_URL
        import congress_api.features.bill_text.service as service_mod

        class _RC:
            def __init__(self, lc):
                self.lifespan_context = lc

        @dataclass
        class Ctx:
            request_context: _RC

            def error(self, *a, **k):
                pass

            def info(self, *a, **k):
                pass

        os.environ[cache.ENV_CACHE_DIR] = str(root)
        service_mod.reset_store()
        key = os.environ["CONGRESS_API_KEY"]
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=60, follow_redirects=True) as client:
            ctx = Ctx(_RC(AppContext(api_key=key, client=client, cache=SimpleCache(60))))
            calls = []
            for label, ver in (("cold", None), ("warm", None), ("pinned", "enr")):
                t0 = time.perf_counter()
                loaded = await service_mod.load_bill_text(ctx, 119, "s", 1071, ver)
                calls.append({"call": label, "wall_ms": round((time.perf_counter() - t0) * 1000), "index_hit": loaded.index_hit,
                              "version_resolution": loaded.version_resolution, "version_hit": loaded.version_hit, "timing": loaded.timing})
                loaded.index.close()
        sc.check("cold: fresh, miss", calls[0]["version_resolution"] == "fresh" and not calls[0]["index_hit"])
        sc.check("warm: cached + index hit, every leg null", calls[1]["version_resolution"] == "cached" and calls[1]["index_hit"]
                 and all(v is None for v in calls[1]["timing"].values()))
        sc.check("pinned: explicit version, no network", calls[2]["version_resolution"] == "pinned" and calls[2]["index_hit"]
                 and all(v is None for v in calls[2]["timing"].values()))
        sc.observations = {"calls": calls}
        service_mod.reset_store()
    except Exception:
        sc.error = traceback.format_exc()
    return sc


# ---------------------------------------------------------------------------


def render_md(scenarios: list[Scenario], out: Path) -> str:
    lines = [f"# V11 — persistent cache sweep — {now_iso()}", "", f"Artifacts: `{out}`", "",
             "| Scenario | Result | Checks |", "|---|---|---|"]
    for s in scenarios:
        n_ok = sum(1 for _, ok in s.checks if ok)
        lines.append(f"| {s.name} | {'PASS' if s.passed else 'FAIL'} | {n_ok}/{len(s.checks)} |")
    lines.append("")
    for s in scenarios:
        lines.append(f"## {s.name} — {'PASS' if s.passed else 'FAIL'}")
        for c, ok in s.checks:
            lines.append(f"- [{'x' if ok else ' '}] {c}")
        if s.error:
            lines.append("```\n" + s.error + "```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "runs" / "v11" / now_iso()))
    ap.add_argument("--live", action="store_true", help="also run S4 against the real GovInfo (needs CONGRESS_API_KEY)")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    missing = [pid for pid, _ in BILLS + [("BILLS-117hr2471enr", "enr")] if not (CORPUS / f"{pid}.xml").exists()]
    if missing:
        print(f"FATAL: corpus XML missing for {missing}; run tests/corpus/fetch_corpus.py", file=sys.stderr)
        return 2

    scenarios: list[Scenario] = []
    scenarios.append(s1_cap_lru(out / "s1"))
    scenarios.extend(s2_recovery(out / "s2"))
    scenarios.append(s3_kill_mid_build(out / "s3a"))
    scenarios.append(s3_concurrent_builders(out / "s3b"))
    scenarios.append(s3_manifest_locked(out / "s3c"))
    scenarios.extend(asyncio.run(s3_injections(out / "s3d")))
    if args.live:
        scenarios.append(asyncio.run(s4_live(out / "s4")))

    (out / "report.json").write_text(json.dumps([s.as_dict() for s in scenarios], indent=2, default=str))
    md = render_md(scenarios, out)
    (out / "report.md").write_text(md)
    print(md)
    failed = [s.name for s in scenarios if not s.passed]
    print(f"\n{len(scenarios) - len(failed)}/{len(scenarios)} scenarios PASS", file=sys.stderr)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
