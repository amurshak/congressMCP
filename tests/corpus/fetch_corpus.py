"""Populate the extended bill-text corpus into the gitignored developer cache.

The corpus is committed as a MANIFEST (package_id + version + sha256), never as bytes:
reproducible, credential-gated, zero repo weight (spec §10 disposable-cache stance).
Run this once to fetch; the corpus-conditional tests in test_bill_text_corpus.py then
run against whatever the cache holds and skip cleanly when it is empty.

    GOVINFO_API_KEY=... python -m tests.corpus.fetch_corpus
    # or point the cache elsewhere:
    BILL_TEXT_CORPUS_CACHE=/path/to/cache GOVINFO_API_KEY=... python -m tests.corpus.fetch_corpus

Fetched bytes are verified against the manifest sha256; a mismatch is fatal (the
published enrolled text changed, or the wrong package resolved).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def cache_dir(manifest: dict) -> Path:
    import os

    repo_root = HERE.parent.parent
    default = repo_root / manifest["cache_default"]
    return Path(os.getenv(manifest["cache_env"], str(default)))


async def main() -> int:
    sys.path.insert(0, str(HERE.parent.parent))
    from congress_api.features.bill_text.client import fetch_govinfo_package

    manifest = load_manifest()
    dest_dir = cache_dir(manifest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ok = skipped = failed = 0
    for entry in manifest["packages"]:
        pkg, want = entry["package_id"], entry["sha256"]
        dest = dest_dir / f"{pkg}.xml"
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == want:
            skipped += 1
            print(f"  cached  {pkg}")
            continue
        try:
            _, data = await fetch_govinfo_package(pkg)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL    {pkg}: {type(exc).__name__}: {str(exc)[:80]}")
            continue
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            failed += 1
            print(f"  HASH!!  {pkg}: manifest {want[:12]} != fetched {got[:12]} -- NOT written")
            continue
        dest.write_bytes(data)
        ok += 1
        print(f"  OK      {pkg}  {len(data):,} bytes")
    print(f"\nfetched={ok}  cached={skipped}  failed={failed}  -> {dest_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
