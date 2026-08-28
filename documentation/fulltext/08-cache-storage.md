*(congressMCP bill-text spec — see `00-INDEX.md` for the file map, conventions, and settled decisions.)*

## 10. Cache and storage **[PR2]**

### Layout: one SQLite file per package, plus a manifest

**Not a single shared database.** Eviction from a shared DB is `DELETE`, which does not return space to the OS without `VACUUM` — needing ~2x free space and blocking while it runs, from inside a stdio server with a client waiting. Per-package files make eviction an `unlink`: instant, space reclaimed, no maintenance window, no contention between clients indexing different packages.

```
<cache_dir>/
  manifest.db                          # LRU metadata, WAL mode
  packages/
    BILLS-119s1071enr.v3.db            # schema version in the filename
    .BILLS-119s1071enr.a3f9c1.tmp      # in-progress build
```

### Governing principle: the filesystem is authoritative, the manifest is derived

The manifest is a convenience index over `packages/`. Never the source of truth. The server must function correctly if it is deleted, stale, or corrupt.

### Package DBs are closed and self-contained — no WAL

Package databases must **not** use WAL mode; WAL leaves `-wal`/`-shm` sidecars that break atomic single-file publication. Only `manifest.db` uses WAL.

### Schema versioning

Version in the filename makes staleness visible from a directory listing.

- **No migrations.** Discard and rebuild.
- On startup, unlink entries whose version is **strictly older** than current. Never delete newer ones — a downgrade/upgrade cycle would thrash the cache.
- An older binary must **ignore** a newer-schema file: not adopt it, not delete it.

### Manifest schema

`package_id`, `filename`, `schema_version`, `bytes`, `created_at`, `last_accessed_at`, `source_format`, `source_last_modified`, `resolved_from_version_query` (bool), `version_resolved_at`, `lease_holder`, `lease_expires_at`.

Set `busy_timeout=5000`. Manifest writes in short explicit transactions.

### Freshness and offline resolution

| Situation | Behavior |
|---|---|
| Explicit `version=`, index cached | Serve from cache. Revalidate only if `now - created_at > CONGRESSMCP_REVALIDATE_DAYS` (default 30): fetch `/packages/{id}/summary`, compare `lastModified`; rebuild if changed. |
| `version=None`, resolution cached and within `CONGRESSMCP_VERSION_TTL` (default 86400s) | Use cached resolution. `version_resolution: "cached"`. |
| `version=None`, TTL expired | Re-resolve via congress.gov. |
| `version=None`, network unavailable | Use last successful resolution. `version_resolution: "cached_offline"` plus `version_resolved_at`. **Disclose it.** |
| `version=None`, no cached resolution, no network | Error `version_resolution_unavailable`, listing any cached versions of that bill. |
| Package reissued under same id (`lastModified` changed) | Discard and rebuild the index. |

Explicitly cached versions remain fully queryable offline. `version=None` offline is best-effort and always labelled.

> **`version_resolution` on explicit-version calls — RULED 2026-08-22, resolving the implementer's flag (a).** An explicit-version cache hit shipped labelled `"fresh"`; measured live, that call performs **no resolution at all** (every timing leg null, zero network). `"fresh"` claims a resolution ran; `"cached"` claims a cached one was consulted; both are false. **Add the value `"pinned"`:** the caller named the version, so no resolution — fresh or cached — occurred. `cache.version_hit` stays `false` (no resolution cache was consulted), and A3's rule that `version_resolution_note` fires only on `version=None` is unchanged — a pinned call made no choice to disclose. The enum is free to extend before PR 2 ships and permanent after (the `request_note` "free now" logic); a field that makes a false claim on the most deliberate call shape is the A3/descriptive-claim failure built into the schema.
>
> **Tool-description obligations for cache/offline labels — RULED 2026-08-22, resolving flag (b): §7's rule does NOT bind here.** That rule exists for **input-shaping** semantics — a consumer cannot construct good queries without knowing what a query does. Cache labels shape no input; they qualify output, and the load-bearing disclosure (possible staleness) is carried by the **active** `version_resolution_note` — the disclosure form measured to propagate at every tier (F6/V21), and certified live here with a dated, plain-language warning. Adding cache exposition to the descriptions is width in every session for a sometimes-condition the response already discloses actively. Revisit only on consumer-layer evidence (a §17-style trace showing `cached_offline` misread).

### Concurrent publication

- Temp name `.{package_id}.{uuid4().hex[:8]}.tmp`, **same directory** (same filesystem) as the final path.
- Build → **close the DB and validate** → **claim the final name atomically** → adopt-on-loss.
- **Loser:** if the destination already exists on publish, discard your temp and adopt the published file. **The claim must be atomic — AMENDED 2026-08-22 (F34, found by V11 S3b):** the original wording invited check-then-act, and that is how it was first implemented — `exists()` then `os.replace()`, and POSIX `os.replace` **silently overwrites**, so in the race window both builders "won." The mechanism is pinned: claim with `os.link(tmp, final)` (raises `FileExistsError` if another builder got there first → loser rule), falling back to `os.replace` only on filesystems without hard links. One valid file existed either way — the defect was the loser rule, not integrity — but adoption validation's "complete by construction" argument leans on exactly-one-publisher, so it is load-bearing, not cosmetic.
- **Windows:** `os.replace()` onto a destination another process holds open raises. Catch, discard temp, use the existing file.
- **Startup:** unlink `.tmp` files older than 1 hour.

### Adoption validation — "it opens" is not enough

A package DB found without a manifest row is adopted **only** if all pass:

1. `PRAGMA application_id` equals the project constant.
2. A `meta` table containing `schema_version`, `package_id`, `source_format`, `source_last_modified`, and `build_complete = 1`.
3. `schema_version` equals current (older → unlink; newer → **ignore, leave in place**).
4. `meta.package_id` matches the filename.
5. `PRAGMA quick_check` returns `ok`.
6. Expected tables present.
7. `integrity-check` on `seg_fts` passes.

Any failure → treat as cache miss. Unlink only when the schema version is *older* or `build_complete` is absent; otherwise leave the file and skip it.

Adoption is only safe because of atomic temp-plus-rename — a file at its final name is complete by construction. **These two decisions are load-bearing on each other; do not relax the rename rule.**

### Recovery from an inconsistent manifest

| State | Behavior |
|---|---|
| Manifest row, file missing | Drop the row, treat as miss, refetch |
| File, no manifest row | Validate per above; adopt or skip |
| `manifest.db` missing | Rebuild by scanning `packages/` |
| `manifest.db` corrupt on open | Unlink, rebuild by scanning |
| Manifest `bytes` ≠ `stat` | Trust `stat`, correct the row |
| Package DB fails validation | Per adoption rules above |

Reconcile on startup (one `listdir` + one query) and lazily on any missing-file error.

### Default location — hand-rolled, no dependency

- Linux: `$XDG_CACHE_HOME/congressmcp`, else `~/.cache/congressmcp`
- macOS: `~/Library/Caches/congressmcp`
- Windows: `%LOCALAPPDATA%\congressmcp\Cache`

### Eviction

- Cap: **500 MB** across `packages/`.
- LRU by `last_accessed_at`, updated on every hit.
- After each index write, evict oldest until under cap. **Sum actual `stat` sizes, not manifest rows.**
- Never evict a package being served in the current call. Cross-process protection is a **best-effort lease** (`lease_holder`/`lease_expires_at`, 5-minute TTL); document it as best-effort rather than guaranteed.
- **Windows cannot unlink an open file.** Catch `OSError`/`PermissionError`, skip that candidate, move to the next. If all candidates fail, proceed over-cap and log — never fail the user's call.
- A single package over the cap alone: serve, evict after, log.

### Do not retain raw XML

Largest footprint contributor. Refetching is one additional document download.

### Tunables

| Variable | Default | Effect |
|---|---|---|
| *(existing congress.gov key var)* | — | Reused for GovInfo |
| `GOVINFO_API_KEY` | unset | Optional override |
| `CONGRESSMCP_CACHE_DIR` | platform default | Cache root |
| `CONGRESSMCP_CACHE_MAX_BYTES` | `524288000` | Eviction cap |
| `CONGRESSMCP_CACHE_ENABLED` | `true` | `false` → in-memory, discarded per call |
| `CONGRESSMCP_VERSION_TTL` | `86400` | Version-resolution TTL |
| `CONGRESSMCP_REVALIDATE_DAYS` | `30` | Explicit-version revalidation interval |

**Document that `CONGRESSMCP_CACHE_ENABLED=false` re-fetches and re-parses the full document on every call** — NDAA-scale latency, every time. Otherwise someone sets it and files a performance bug.

### Maintenance: CLI, not MCP tools

Expose exactly:

```
congressmcp cache info      # path, total bytes, cap, per-package listing, schema version
congressmcp cache clear     # with --yes for non-interactive
```

**Exit-code contract (pinned after §18 `bug_005`).** `cache clear` **refused** for want of `--yes` in a non-interactive context exits **`1`**; a completed `cache clear` and any `cache info` exit **`0`**. This must hold on **both** entry points — the `congressmcp` console script *and* `python -m congress_api` (the latter previously discarded `main()`'s return and exited `0` on a refusal). Recorded here because it is an observable contract a caller can script against, and there was nothing for the source to conform to before. *(§18 finding #13: a source comment claiming refusal "exits 2" is drift against this — the contract is `1`.)*

**PR 2 forward constraint (§18 finding #21).** The PR-1 `cache` CLI already hardcodes the *entire* persistent-cache layout it does not yet own — cache directory, package glob, disk-cap env var, and schema-version literal — because it ships before the cache module exists. **When PR 2 introduces the persistent-cache module, that module must own these literals, and the CLI must read them from it** (not re-declare them). If PR 2 instead reproduces the literals independently, the two must match exactly or `cache info`/`clear` will point at a different path than the cache writes to. This is a real PR1→PR2 coordination hazard; the clean resolution is single ownership in the cache module.

Rationale, for the PR description: every MCP tool's description occupies context in every session, and cache administration is never something the model should decide to do; `cache clear` is destructive and should not be in a model's reach; if the cache is corrupt enough to break the server, a CLI still works where an MCP tool may not; and it keeps this a three-tool feature. Error messages and the README must reference the commands, since the cost of this choice is discoverability.

---

---

## The cache key must include a rendering version, not only a schema version

**Measured consequence of F12 (`5a54833`).** Text rendering determines `display_text` length, which determines **byte-split chunk boundaries**, which determine chunk content and therefore bm25 ranking. F12 changed only whitespace and still reordered results in 3 of 30 replayed rounds.

§10 already forbids migrations — discard and rebuild, schema version in the filename. **That is sufficient only if the version bumps on rendering changes as well as schema changes.** A cached index built before a rendering change and read after it serves **differently-chunked content under the same key**, silently, with ids that may no longer correspond.

**Include a rendering/parser version in the cache key** and bump it for any change to segment joining, delimiter rendering, header separators, or the byte-split boundary rules. The failure mode otherwise is a stale index that looks valid, which §10's discard-and-rebuild stance was written to make impossible.

**Tripwire scope — RULED 2026-08-21, resolving the implementer's widening question.** The shipped AST fingerprint (`rendering_fingerprint()` over the §10-named symbols, pinned beside `SCHEMA_VERSION`) covers rendering but not parser *semantics* — an `AMENDATORY_RE` or `amends`-resolution change alters the **stored field values** in every cached package (the F32/F33 failure class, served from cache) with no rendering symbol touched. Widening the AST pin to the whole parser is the wrong instrument: an AST hash fires on refactors that change no output, training people to bump mechanically, and still only measures *source* — a proxy. **Measure the property itself: add a golden-build fingerprint.** Build the in-tree trimmed fixture(s) through the real build path, dump every stored row in canonical order (deterministic columns only — no timestamps), sha256 the dump, and pin the digest beside `SCHEMA_VERSION` with the same bump-both-together rule. Any change anywhere — parser, segmenter, `amends`, index schema, tokenizer — that would make a rebuilt package differ from a cached one now fails a test, with zero false trips on pure refactors. **Keep the AST tripwire as the fast first line** (it names the touched symbol in its failure message, which the golden digest cannot); the golden build is the authoritative backstop. Caveat that binds it: a trimmed fixture validates *regressions*, not parser assumptions (§13 rule) — the golden build detects *change*, which is exactly its job here; it proves nothing about correctness.

**Blind spot measured and closed 2026-08-27 (F35+F36 adjudication):** the F35 rendering change and the F36 extraction change — both exactly the classes this fingerprint exists to catch — moved the golden digest on *neither*, because the trimmed fixtures exercised neither path (no un-subdivided section with flowing designators; no hugged parenthetical subject cite). A golden build only guards the behaviors its inputs exercise — coverage of the input set is part of the instrument's validity, the same lesson as "a scan that errors must not look like one that found nothing," here as "a fixture that skips the path must not look like the path is guarded." `f35_f36_trimmed.xml` added to `GOLDEN_INPUTS`; the standing rule this creates: **when a ruling mandates a version bump, the fix must confirm the golden inputs exercise the changed path — and extend them if not.**
